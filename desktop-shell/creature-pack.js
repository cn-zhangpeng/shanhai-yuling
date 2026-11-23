'use strict';
/**
 * 生灵包（creature pack）注册表 —— 主进程侧
 *
 * 一个"生灵"就是一个目录，目录里的图按**文件名**认领语义（帧名），不写代码就能加：
 *
 *   生灵目录：<%APPDATA%>/山海遇灵/creatures/<名字>/   （只有这一个根，一个目录 = 一只，新建丢一套图即可）
 *   种子：    <app 目录>/assets/                        （首次启动复制成 生灵目录/冉冉，运行时不再读）
 *
 * 帧名认领顺序：
 *   1) creature.json 里 frames.<name>.file 显式指定
 *   2) 文件名按非字母数字切成 token，token 里出现该帧名就算命中（不区分大小写）
 *      所以 ranran_base_2x.png → token: ranran / base / 2x   → 认领 base
 *         ranran_ntBlink_2x.png → token: ranran / ntblink / 2x → 认领 ntBlink（不会误认 blink）
 *   3) 同名多个候选时优先 frames/ 子目录里的
 *
 * 顶部锚点（气泡头顶位置）不靠手量：用 nativeImage 把图缩到 128 宽后扫 alpha，
 * 取最上面一行不透明像素，换算成"相对显示高度的比例"再交给渲染层。
 */

const fs = require('fs');
const path = require('path');
const { validateManifest } = require('./lib/manifest');

/* 25 个规范帧名。顺序即语义分组，改名前先看 docs/生灵包规范.md */
const CANONICAL_FRAMES = [
  /* 坐姿待机（她会抱着伴生灵的那一套） */
  'base', 'blink', 'talk', 'smile', 'turn', 'turnL', 'wave', 'noant',
  /* 站姿与走动 */
  'stand', 'walkA', 'walkB', 'walkP1', 'walkP2',
  /* 场景姿态 */
  'phone', 'ropeAir', 'ropeLand',
  /* 放下伴生灵之后的坐姿差分（空手版） */
  'ntTurn', 'ntTurnL', 'ntSmile', 'ntWave', 'ntBlink',
  /* 坐着的小动作 */
  'footSwing', 'handEar', 'ntFootSwing', 'ntHandEar'
];

/* 站立/位移类帧：这些不算"坐姿"，其余坐姿帧在伴生灵落地时可以换成空手版 */
const STANDING_FRAMES = new Set(['stand', 'walkA', 'walkB', 'walkP1', 'walkP2', 'phone', 'ropeAir', 'ropeLand']);

const MIME = {
  '.png': 'image/png',
  '.webp': 'image/webp',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.json': 'application/json'
};

const ANCHOR_CACHE = new Map();   /* file|mtime|size -> 顶边比例 */
const SIZE_CACHE = new Map();     /* file|mtime|size -> {w,h} */

/* 用户生灵目录里落一份纯文字说明，别人打开文件夹就知道怎么放图（不依赖任何脚本环境） */
const USER_README = `山海遇灵 · 生灵目录说明

这里是唯一存放形象的地方：一个文件夹 = 一只萌宠，文件夹名就是它的名字。

  生灵目录\\
    冉冉\\              内置这只（首次启动从程序目录复制过来），可以直接改
    用户自定义1\\       设置页「复制为新形象」生成
    用户自定义2\\

怎么用：
  · 想改哪只：设置页 → 素材 → 找到那一帧点「替换」，图直接落进它的 frames\\ 里
  · 想另起一只：设置页 → 素材 →「复制为新形象」，或在这里自己新建一个文件夹
  · 自己建的话：文件夹里建 frames 子目录，文件名直接用帧名（base.png / walkA.png …）
  · 回桌宠 → 右键 → 设置 → 形象 → 点「重新扫描」，下拉框里就多一只

图的要求：
  · 透明底 PNG：四角必须透明，不要带白底或背景（带底色的图会连背景一起贴到桌面上）
  · 一套图宽高必须完全一致：冉冉这套是 900 × 1360；按这个尺寸画最省事，等比缩小（450 × 680）也行
  · 站姿和 4 张走路帧的脚要踩在同一条水平线上，否则走路时会浮空或陷进桌面
  · 统一朝画面左边画（往右走时程序会整体镜像）
  · 头顶位置不用管，程序会自己量

可选：
  · creature.json —— 改显示名、窗口高度、伴生灵
  · lines.json —— 台词（也可以直接在设置页「常用语」里改）

程序目录里的 assets\\ 只是原始素材种子：改了它不会影响桌面上的她，真正生效的是这里的副本。
更详细的帧名表见设置页 → 形象 →「怎么再加一只生灵」展开的那段。
`;

/* ---------------- 小工具 ---------------- */

function safeStat(p) {
  try { return fs.statSync(p); } catch (e) { return null; }
}

function readJson(p) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch (e) { return null; }
}

function writeJson(p, data) {
  const tmp = p + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf8');
  fs.renameSync(tmp, p);
}

function tokenize(stem) {
  return stem.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

function isImageFile(name) {
  return /\.(png|webp|jpg|jpeg)$/i.test(name);
}

function cacheKey(file) {
  const st = safeStat(file);
  return st ? `${file}|${Math.round(st.mtimeMs)}|${st.size}` : file;
}

function relOf(dir, file) {
  return path.relative(dir, file).split(path.sep).join('/');
}

/* pet:// 素材地址。id 放路径不放 host：host 会被 URL 解析强制小写，中文目录名还会被 punycode。
   host 传 'thumb' 走缩略图路由（设置页素材表用，不为了 76px 的预览去拉整张 900×1360） */
function buildAssetUrl(id, dir, rel, host) {
  const p = safeStat(path.resolve(dir, rel));
  const v = p ? Math.round(p.mtimeMs) : 0;
  return `pet://${host || 'creature'}/${encodeURIComponent(id)}/${rel.split('/').map(encodeURIComponent).join('/')}?v=${v}`;
}

/* 目录下的图片：只看本层和下一层（frames/、companion/ 这种），忽略 _ 开头的中间产物 */
function collectImages(dir) {
  const out = [];
  const walk = (d, depth) => {
    if (depth > 2) return;
    let ents;
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch (e) { return; }
    for (const e of ents) {
      if (e.name.startsWith('_') || e.name.startsWith('.')) continue;
      const full = path.join(d, e.name);
      if (e.isDirectory()) walk(full, depth + 1);
      else if (isImageFile(e.name)) out.push(full);
    }
  };
  walk(dir, 0);
  return out;
}

/* ---------------- 锚点 / 尺寸 ---------------- */

function imageSize(nativeImage, file) {
  const key = cacheKey(file);
  if (SIZE_CACHE.has(key)) return SIZE_CACHE.get(key);
  let size = null;
  try {
    const img = nativeImage.createFromPath(file);
    if (img && !img.isEmpty()) size = img.getSize();
  } catch (e) { size = null; }
  SIZE_CACHE.set(key, size);
  return size;
}

/**
 * 最上面一行不透明像素的位置，返回 0~1 的比例（相对图片高度）。
 * 缩到 384 宽再扫：900×1360 的原图逐像素扫 25 帧会拖慢启动，
 * 384 宽时每行大约对应 2 个原图像素，换算到 600 高的显示尺寸上误差不到 1px。
 */
function topRatio(nativeImage, file) {
  const key = cacheKey(file);
  if (ANCHOR_CACHE.has(key)) return ANCHOR_CACHE.get(key);
  let ratio = null;
  try {
    const img = nativeImage.createFromPath(file);
    if (img && !img.isEmpty()) {
      const small = img.resize({ width: 384 });
      const { width, height } = small.getSize();
      const bmp = small.toBitmap();                    /* BGRA */
      for (let y = 0; y < height && ratio === null; y++) {
        for (let x = 0; x < width; x++) {
          if (bmp[(y * width + x) * 4 + 3] > 8) { ratio = y / height; break; }
        }
      }
      if (ratio === null) ratio = 0;                   /* 全透明：贴到头顶 */
    }
  } catch (e) { ratio = null; }
  ANCHOR_CACHE.set(key, ratio);
  return ratio;
}

/* ---------------- 帧名认领 ---------------- */

function buildFrameIndex(dir, images) {
  const byToken = new Map();
  for (const img of images) {
    const stem = path.basename(img, path.extname(img));
    for (const tk of tokenize(stem)) {
      if (!byToken.has(tk)) byToken.set(tk, []);
      byToken.get(tk).push(img);
    }
  }
  const prefFramesDir = (f) => {
    const parts = relOf(dir, f).split('/');
    const stem = path.basename(f, path.extname(f));
    const tks = tokenize(stem);
    let score = 0;
    if (parts.length > 1 && /^frames$/i.test(parts[0])) score += 10;   /* frames/ 优先 */
    if (tks.includes('2x')) score += 5;                               /* 同一帧有 _hi/_s/_2x 时用 2x */
    return score;
  };
  const resolved = {};
  for (const name of CANONICAL_FRAMES) {
    const cands = (byToken.get(name.toLowerCase()) || []).slice();
    if (cands.length) {
      cands.sort((a, b) => prefFramesDir(b) - prefFramesDir(a));   /* frames/ 优先 */
      resolved[name] = cands[0];
    }
  }
  return resolved;
}

function findCompanion(dir, images, manifest) {
  const explicit = manifest && manifest.companion && manifest.companion.file;
  if (explicit) {
    const p = path.join(dir, explicit);
    if (safeStat(p)) return p;
  }
  const hits = images.filter((f) => {
    const stem = path.basename(f, path.extname(f));
    const tks = tokenize(stem);
    return tks.includes('ant') || tks.includes('companion') || tks.includes('pet');
  });
  if (!hits.length) return null;
  hits.sort((a, b) => {
    const aIn = relOf(dir, a).includes('/');
    const bIn = relOf(dir, b).includes('/');
    return (aIn ? 0 : 1) - (bIn ? 0 : 1);   /* companion/ 子目录里的优先 */
  });
  return hits[0];
}

/* ---------------- 单个生灵的静态描述 ---------------- */

function describe(rootDir, id, nativeImage) {
  const manifest = readJson(path.join(rootDir, 'creature.json')) || {};
  const images = collectImages(rootDir);
  const frameFiles = buildFrameIndex(rootDir, images);

  /* manifest 里显式指定的帧覆盖自动认领，并允许指向目录外的相对路径 */
  if (manifest.frames && typeof manifest.frames === 'object') {
    for (const [name, spec] of Object.entries(manifest.frames)) {
      const file = typeof spec === 'string' ? spec : spec && spec.file;
      if (!file) continue;
      const p = path.resolve(rootDir, file);
      if (safeStat(p)) frameFiles[name] = p;
    }
  }

  const baseFile = frameFiles.base || null;
  const status = !baseFile ? 'broken'
    : (frameFiles.stand && frameFiles.walkA && frameFiles.walkB && frameFiles.walkP1 && frameFiles.walkP2)
      ? 'full' : 'static';

  const companionFile = findCompanion(rootDir, images, manifest);
  const baseSize = baseFile ? imageSize(nativeImage, baseFile) : null;
  const petHeight = Number((manifest.window && manifest.window.petHeight) || 600);
  const aspect = (baseSize && baseSize.height) ? baseSize.width / baseSize.height : 0.66;
  /* 620 = round(600 * 0.6618 * 1.562)：沿用旧窗口比例，换别的比例的生灵也不会被裁 */
  const winW = Math.max(360, Math.round(petHeight * aspect * 1.562));
  const winH = Math.round(petHeight + 160);

  const frames = {};
  const missing = [];
  for (const name of CANONICAL_FRAMES) {
    const file = frameFiles[name];
    if (!file) { missing.push(name); continue; }
    const spec = (manifest.frames && manifest.frames[name]) || {};
    const measured = topRatio(nativeImage, file);
    const size = imageSize(nativeImage, file);
    const override = Number(spec.headTop);
    const ratio = (isFinite(override) && override > 0 && size && size.height)
      ? Math.min(1, override / size.height)
      : (measured == null ? 0.2 : measured);
    frames[name] = {
      file,
      rel: relOf(rootDir, file),
      ratio,
      sit: typeof spec.sit === 'boolean' ? spec.sit : !STANDING_FRAMES.has(name),
      noAnt: spec.noAnt || null
    };
  }
  /* noAnt 没写就按名字猜：ntXxx 站在 Xxx 上（ntTurn←turn），否则没有空手版 */
  const noAntMap = {};
  for (const name of Object.keys(frames)) {
    if (frames[name].noAnt) { noAntMap[name] = frames[name].noAnt; continue; }
    if (/^nt/.test(name)) {
      const target = name.slice(2);
      const lower = target.charAt(0).toLowerCase() + target.slice(1);
      if (frames[lower]) noAntMap[name] = lower;
    }
  }
  /* 坐姿帧在伴生灵落地时要换成空手版；有 noant 这张兜底就至少能换过去 */
  if (frames.noant) {
    for (const name of Object.keys(frames)) {
      if (frames[name].sit && !noAntMap[name] && name !== 'noant' && name !== 'base') noAntMap[name] = 'noant';
    }
    noAntMap.base = 'noant';
  }

  const companion = companionFile ? buildCompanion(rootDir, companionFile, manifest, petHeight, nativeImage) : null;
  const lines = loadLines(rootDir, manifest);
  const icon = findIcon(rootDir);

  /* 一套图宽高一致是硬要求（不一致换帧会跳尺寸），这里顺手查出来交给设置页提示 */
  const sizeMismatch = [];
  if (baseSize) {
    for (const [name, f] of Object.entries(frames)) {
      const s = imageSize(nativeImage, f.file);
      if (s && (s.width !== baseSize.width || s.height !== baseSize.height)) sizeMismatch.push(name);
    }
  }

  const caps = {
    walk: !!(frames.stand && frames.walkA && frames.walkB && frames.walkP1 && frames.walkP2),
    rope: !!(frames.ropeAir && frames.ropeLand),
    phone: !!frames.phone,
    play: !!(companion && frames.base),
    blink: !!frames.blink,
    gestures: ['turn', 'turnL', 'smile', 'talk', 'footSwing', 'handEar']
      .filter((n) => frames[n])
  };

  /* 清单 v2：轨道 / 序列 / 相位。v1 清单在这里被合成一套默认轨道，渲染层行为不变 */
  const state = validateManifest(manifest, frames);

  return {
    id,
    dir: rootDir,
    displayName: (manifest.displayName || id),
    manifest,
    status,
    frames,
    noAntMap,
    companion,
    lines,
    icon,
    window: { petHeight, w: winW, h: winH, aspect },
    caps,
    size: baseSize ? { w: baseSize.width, h: baseSize.height } : null,
    sizeMismatch,
    missing,
    schemaVersion: state.schemaVersion,
    tracks: state.tracks,
    sequences: state.sequences,
    phases: state.phases,
    diagnostics: state.diagnostics
  };
}

function buildCompanion(rootDir, file, manifest, petHeight, nativeImage) {
  const size = imageSize(nativeImage, file);
  const width = size ? size.width : 0;
  const height = size ? size.height : 0;
  const conf = (manifest && manifest.companion) || {};
  const frames = Number(conf.frames) || (width && width % 9 === 0 ? 9 : 1);
  const cellW = Number(conf.cellW) || (width && frames ? Math.round(width / frames) : width) || 340;
  const cellH = Number(conf.cellH) || height || 332;
  const contentW = Number(conf.contentW) || cellW;
  const displayH = Number(conf.displayH) || Math.round(petHeight * 0.25);
  return { file, rel: relOf(rootDir, file), frames, cellW, cellH, contentW, displayH };
}

function loadLines(rootDir, manifest) {
  const name = (manifest && manifest.lines) || 'lines.json';
  const p = path.join(rootDir, name);
  const data = readJson(p);
  if (!data) return [];
  const list = Array.isArray(data) ? data : (data.lines || []);
  if (!Array.isArray(list)) return [];
  return list.map(normalizeLine).filter((l) => l.i && l.t);
}

/* 台词两种写法都认：渲染层紧凑写法（i/c/t/w/cd/tags/fu）与人写的详细写法（id/category/...） */
function normalizeLine(l) {
  if (!l || typeof l !== 'object') return { i: '', c: '', t: '' };
  const tags = l.tags || l.modeTags || ['quiet', 'lively'];
  const fu = l.fu || (l.followUp ? { t: l.followUp.text, d: l.followUp.delaySec } : null);
  const num = (v, d) => (typeof v === 'number' && isFinite(v) ? v : d);
  return {
    i: String(l.id || l.i || ''),
    c: String(l.category || l.c || 'idle'),
    t: String(l.text || l.t || ''),
    w: num(l.weight != null ? l.weight : l.w, 3),
    cd: num(l.cooldownSec != null ? l.cooldownSec : l.cd, 900),
    tags: Array.isArray(tags) && tags.length ? tags : ['quiet', 'lively'],
    ...(fu && fu.t ? { fu: { t: String(fu.t), d: num(fu.d, 8) } } : {}),
    ...(l.trigger ? { trigger: l.trigger } : {}),
    ...(l.note ? { note: l.note } : {})
  };
}

/* 存回文件时展开成人能读的样子 */
function expandLine(l) {
  const out = {
    id: l.i,
    category: l.c,
    text: l.t,
    weight: l.w,
    cooldownSec: l.cd,
    modeTags: l.tags
  };
  if (l.fu) out.followUp = { text: l.fu.t, delaySec: l.fu.d };
  return out;
}

function findIcon(rootDir) {
  let ico = null, png = null;
  const walk = (d, depth) => {
    if (depth > 2) return;
    let ents;
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch (e) { return; }
    for (const e of ents) {
      if (e.name.startsWith('_') || e.name.startsWith('.')) continue;
      const full = path.join(d, e.name);
      if (e.isDirectory()) { walk(full, depth + 1); continue; }
      if (!ico && /\.ico$/i.test(e.name)) ico = full;
      if (!png && /icon.*\.png$/i.test(e.name)) {
        const m = /_(\d+)\.png$/i.exec(e.name);
        if (m && Number(m[1]) >= 64 && Number(m[1]) <= 256) png = full;
      }
    }
  };
  walk(rootDir, 0);
  return { ico, png };
}

/* ---------------- 注册表 ---------------- */

function createRegistry({ appDir, userDataDir, nativeImage, log }) {
  const builtinRoot = path.join(appDir, 'assets');
  const userRoot = path.join(userDataDir, 'creatures');
  const say = log || (() => {});
  const dirMap = new Map();        /* id -> 真实目录，供 pet:// 协议用 */

  function userDirs() {
    let ents = [];
    try { ents = fs.readdirSync(userRoot, { withFileTypes: true }); } catch (e) { return []; }
    return ents
      .filter((e) => e.isDirectory() && !e.name.startsWith('_') && !e.name.startsWith('.'))
      .map((e) => ({ id: e.name, dir: path.join(userRoot, e.name) }));
  }

  function scanAll() {
    const list = [];

    /* 只认「生灵目录」这一个根：一个文件夹 = 一只。冉冉也在这里（首次启动从 assets 复制一份种子） */
    for (const { id, dir } of userDirs()) {
      if (!safeStat(path.join(dir, 'creature.json')) && !collectImages(dir).length) continue;
      try {
        list.push({ ...describe(dir, id, nativeImage), builtin: false });
      } catch (e) { say('生灵 ' + id + ' 解析失败: ' + e.message); }
    }

    dirMap.clear();
    for (const c of list) dirMap.set(c.id, c.dir);
    return list;
  }

  /* 给渲染层的载荷：URL 走 pet://<id>/<相对路径>，带 mtime 做缓存版本号 */
  function payload(id, opts) {
    const all = scanAll();
    const meta = all.find((c) => c.id === id) || all[0];
    if (!meta) return null;
    const overrides = (opts && opts.lines) || null;
  const assetUrl = (rel) => buildAssetUrl(meta.id, meta.dir, rel);

  const frames = {};
  for (const [name, f] of Object.entries(meta.frames)) {
    frames[name] = { url: assetUrl(f.rel), rel: f.rel, ratio: f.ratio, sit: f.sit };
  }
  const companion = meta.companion ? {
    url: assetUrl(meta.companion.rel),
    frames: meta.companion.frames,
    cellW: meta.companion.cellW,
    cellH: meta.companion.cellH,
    contentW: meta.companion.contentW,
    displayH: meta.companion.displayH
  } : null;

    return {
      id: meta.id,
      displayName: meta.displayName,
      status: meta.status,
      builtin: meta.builtin,
      icon: meta.icon,
      window: meta.window,
      frames,
      companion,
      noAntMap: meta.noAntMap,
      lines: (overrides && overrides.length ? overrides : meta.lines).map(normalizeLine),
      behavior: meta.manifest.behavior || null,
      profile: meta.manifest.profile || {},
      caps: meta.caps,
      missing: meta.missing,
      schemaVersion: meta.schemaVersion,
      tracks: meta.tracks,
      sequences: meta.sequences,
      phases: meta.phases,
      diagnostics: meta.diagnostics
    };
  }

  /* 设置页要的清单：不带图，只带状态 */
  function brief() {
    return scanAll().map((c) => ({
      id: c.id,
      displayName: c.displayName,
      status: c.status,
      builtin: c.builtin,
      dir: c.dir,
      frameCount: Object.keys(c.frames).length,
      missing: c.missing,
      hasCompanion: !!c.companion,
      lineCount: c.lines.length,
      caps: c.caps,
      size: c.size,
      sizeMismatch: c.sizeMismatch,
      trackCount: Object.keys(c.tracks || {}).length,
      diagnostics: c.diagnostics || []
    }));
  }

  function resolve(id, rel) {
    const base = dirMap.get(id);
    if (!base) return null;
    const file = path.resolve(base, rel);
    const guard = path.resolve(base) + path.sep;
    if (!file.startsWith(guard)) return null;               /* 不允许逃出目录 */
    if (!/\.(png|webp|jpg|jpeg|ico|json)$/i.test(file)) return null;
    if (!safeStat(file)) return null;
    return file;
  }

/* 首次启动把程序目录里的冉冉复制成「生灵目录\冉冉\」：之后所有形象一视同仁——
   都在这一个根下、都能直接换帧，没有"内置只读"这一档。assets/ 只当原始素材种子，运行时不再读它。 */
const SEED_NAME = '冉冉';

function ensureUserCreatureDir() {
  try { fs.mkdirSync(userRoot, { recursive: true }); }
  catch (e) { say('建生灵目录失败: ' + e.message); return false; }

  let seeded = false;
  const dest = path.join(userRoot, SEED_NAME);
  const srcOk = safeStat(path.join(builtinRoot, 'creature.json')) || safeStat(path.join(builtinRoot, 'ranran_base_2x.png'));
  if (!safeStat(dest) && srcOk) {
    try {
      fs.mkdirSync(path.join(dest, 'frames'), { recursive: true });
      fs.mkdirSync(path.join(dest, 'companion'), { recursive: true });
      const manifest = readJson(path.join(builtinRoot, 'creature.json')) || {};
      const images = collectImages(builtinRoot);
      const idx = buildFrameIndex(builtinRoot, images);

      const frames = {};
      for (const name of CANONICAL_FRAMES) {
        const src = idx[name];
        if (!src) continue;
        const ext = (path.extname(src) || '.png').toLowerCase();
        const rel = `frames/${name}${ext}`;
        fs.copyFileSync(src, path.join(dest, rel));
        const oldSpec = manifest.frames && manifest.frames[name];
        const spec = (oldSpec && typeof oldSpec === 'object') ? Object.assign({}, oldSpec) : {};
        spec.file = rel;
        frames[name] = spec;
      }

      const companion = findCompanion(builtinRoot, images, manifest);
      let companionRel = null;
      if (companion) {
        companionRel = `companion/${path.basename(companion)}`;
        fs.copyFileSync(companion, path.join(dest, companionRel));
      }

      const icons = findIcon(builtinRoot);
      for (const p of [icons.ico, icons.png]) {
        if (!p) continue;
        try { fs.copyFileSync(p, path.join(dest, path.basename(p))); } catch (e) {}
      }
      const linesFile = path.join(builtinRoot, manifest.lines || 'lines.json');
      if (safeStat(linesFile)) { try { fs.copyFileSync(linesFile, path.join(dest, 'lines.json')); } catch (e) {} }

      const out = Object.assign({}, manifest, { id: SEED_NAME, displayName: manifest.displayName || SEED_NAME, frames });
      if (companionRel) out.companion = Object.assign({}, manifest.companion || {}, { file: companionRel });
      writeJson(path.join(dest, 'creature.json'), out);
      seeded = true;
      say(`种子形象已铺好: ${SEED_NAME}（${Object.keys(frames).length} 帧）`);
    } catch (e) {
      say('铺种子形象失败: ' + e.message);
    }
  }

  /* 说明文件跟着结构变：内容不一致就重写（老版本留下的是"英文 id、新建文件夹"那套旧文案） */
  const readme = path.join(userRoot, '说明.txt');
  const want = '\ufeff' + USER_README;
  let cur = '';
  try { cur = fs.readFileSync(readme, 'utf8'); } catch (e) { cur = ''; }
  if (cur !== want) {
    try { fs.writeFileSync(readme, want, 'utf8'); }
    catch (e) { say('写说明文件失败: ' + e.message); }
  }
  return seeded;
}

  return { builtinRoot, userRoot, scanAll, payload, brief, resolve, ensureUserCreatureDir };
}

module.exports = {
  CANONICAL_FRAMES,
  STANDING_FRAMES,
  MIME,
  createRegistry,
  normalizeLine,
  expandLine,
  readJson,
  writeJson,
  buildAssetUrl,
  collectImages,
  buildFrameIndex,
  tokenize,
  topRatio,
  imageSize
};
