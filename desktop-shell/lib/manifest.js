'use strict';
/**
 * 生灵清单 v2 —— 校验 + 默认值合成（纯函数，不依赖 Electron）
 *
 * 借鉴 DSH 宠物插件（@linxin666/dsh-pet）的 manifest 设计：
 *   tracks     一条轨道 = 一串帧 + 每帧时长 + 是否循环 + 播完回落（fallback）
 *   sequences  一个序列 = 按顺序播几条轨道（序列里的循环轨道只播一遍）
 *   phases     相位 → 轨道名（blink / greet / walk / rope / phone / stand …）
 *
 * v1（只有 frames + companion）继续能用：没有 tracks 时按现有 25 帧自动合成默认轨道，
 * 每一步硬编码时长（眨眼 150ms、走一步 200ms、跳绳 185ms…）都收进这里，
 * 渲染层以后只认清单，不再散落魔法数字。
 *
 * 校验口径（fail-closed，与 DSH 一致）：
 *   · 轨道结构坏（没 frames、帧全不存在）→ 丢弃该轨道，记一条 error 诊断
 *   · 部分帧不存在 / durations 长度不对 / fallback 成环 → 尽量修好，记 warn 诊断
 *   · sequences / phases 引用不存在的轨道 → 丢弃引用，记 warn 诊断
 * 诊断交给设置页和 validate 工具显示，而不是静默降级。
 */

const TRACK_KEYS = new Set(['frames', 'durations', 'loop', 'fallback', 'ambient']);
const DEFAULT_DURATION = 200;

function isObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

/* ---------------- 默认值：把现在写死在 desk-pet.html 里的节拍收进来 ---------------- */

function buildDefaultTracks(frames) {
  const has = (n) => Object.prototype.hasOwnProperty.call(frames, n);
  const tracks = {};
  const single = (name, ms, extra) => Object.assign({ frames: [name], durations: [ms], loop: false }, extra || {});
  const ambient = (name, ms, extra) => single(name, ms, Object.assign({ ambient: true }, extra || {}));

  if (has('base')) tracks.idle = { frames: ['base'], durations: [600], loop: true };
  if (has('blink')) tracks.blink = single('blink', 150, { fallback: 'idle' });

  /* 坐着的小动作（ambient = 可以进待机随机池） */
  if (has('turn')) tracks.turn = ambient('turn', 720, { fallback: 'idle' });
  if (has('turnL')) tracks.turnL = ambient('turnL', 720, { fallback: 'idle' });
  if (has('smile')) tracks.smile = ambient('smile', 1500, { fallback: 'idle' });
  if (has('talk')) tracks.talk = ambient('talk', 600, { fallback: 'idle' });
  if (has('wave')) tracks.wave = single('wave', 1100, { fallback: 'idle' });
  if (has('footSwing')) tracks.footSwing = ambient('footSwing', 1200, { fallback: 'idle' });
  if (has('handEar')) tracks.handEar = ambient('handEar', 1200, { fallback: 'idle' });

  /* 放下伴生灵之后的空手版 */
  if (has('ntTurn')) tracks.ntTurn = ambient('ntTurn', 720, { fallback: 'idle' });
  if (has('ntTurnL')) tracks.ntTurnL = ambient('ntTurnL', 720, { fallback: 'idle' });
  if (has('ntSmile')) tracks.ntSmile = ambient('ntSmile', 1500, { fallback: 'idle' });
  if (has('ntWave')) tracks.ntWave = single('ntWave', 1100, { fallback: 'idle' });
  if (has('ntBlink')) tracks.ntBlink = single('ntBlink', 150, { fallback: 'idle' });
  if (has('ntFootSwing')) tracks.ntFootSwing = ambient('ntFootSwing', 1200, { fallback: 'idle' });
  if (has('ntHandEar')) tracks.ntHandEar = ambient('ntHandEar', 1200, { fallback: 'idle' });

  if (has('stand')) tracks.stand = single('stand', 430, { fallback: 'idle' });
  if (has('phone')) tracks.phone = single('phone', 1000, { fallback: 'idle' });

  /* 走路：四姿态循环，顺序就是步态顺序（接触左 / 过渡 / 接触右 / 过渡） */
  const walk = ['walkA', 'walkP1', 'walkB', 'walkP2'].filter(has);
  if (walk.length >= 2) {
    tracks.walk = { frames: walk, durations: walk.map(() => 200), loop: true };
  }

  /* 跳绳：腾空 / 落地 两帧循环 */
  if (has('ropeAir') && has('ropeLand')) {
    tracks.rope = { frames: ['ropeAir', 'ropeLand'], durations: [185, 185], loop: true };
  }

  return tracks;
}

function buildDefaultPhases(tracks) {
  const wanted = {
    idle: 'idle',
    blink: 'blink',
    greet: 'wave',
    walk: 'walk',
    rope: 'rope',
    phone: 'phone',
    stand: 'stand'
  };
  const out = {};
  for (const [phase, track] of Object.entries(wanted)) {
    if (tracks[track]) out[phase] = track;
  }
  return out;
}

/*
 * 默认待机序列：她每隔一会儿自己演一小段（先转头、回坐姿、再笑一下）。
 * 只有在三张帧都存在时才给，缺帧的静态形象不会凭空多出动作。
 */
function buildDefaultSequences(tracks) {
  if (tracks.turn && tracks.idle && tracks.smile) {
    return { idle: ['turn', 'idle', 'smile'] };
  }
  return {};
}

/* ---------------- 校验 ---------------- */

function validateTracks(rawTracks, hasFrame, add) {
  const out = {};

  for (const [name, raw] of Object.entries(rawTracks)) {
    if (!isObject(raw)) {
      add('error', 'bad-track', `轨道 ${name} 不是对象，已丢弃`, `tracks.${name}`);
      continue;
    }
    for (const key of Object.keys(raw)) {
      if (!TRACK_KEYS.has(key)) {
        add('warn', 'unknown-field', `轨道 ${name} 的字段 ${key} 不认识，已忽略`, `tracks.${name}.${key}`);
      }
    }

    if (!Array.isArray(raw.frames)) {
      add('error', 'bad-track', `轨道 ${name} 没有 frames 数组，已丢弃`, `tracks.${name}.frames`);
      continue;
    }

    const frames = [];
    const missing = [];
    for (const f of raw.frames) {
      if (typeof f !== 'string' || !f) {
        add('warn', 'bad-frame', `轨道 ${name} 里有非字符串帧名，已忽略`, `tracks.${name}.frames`);
        continue;
      }
      if (!hasFrame(f)) { missing.push(f); continue; }
      frames.push(f);
    }
    if (missing.length) {
      add('warn', 'unknown-frame', `轨道 ${name} 引用了不存在的帧：${missing.join('、')}，已跳过`, `tracks.${name}.frames`);
    }
    if (!frames.length) {
      add('error', 'empty-track', `轨道 ${name} 没有可用帧，已丢弃`, `tracks.${name}.frames`);
      continue;
    }

    let durations = raw.durations;
    if (durations === undefined) durations = [DEFAULT_DURATION];
    if (!Array.isArray(durations)) {
      add('warn', 'bad-duration', `轨道 ${name} 的 durations 不是数组，按 ${DEFAULT_DURATION}ms 处理`, `tracks.${name}.durations`);
      durations = [DEFAULT_DURATION];
    }
    const nums = durations.map(Number).filter((n) => Number.isFinite(n) && n > 0);
    if (nums.length !== durations.length) {
      add('warn', 'bad-duration', `轨道 ${name} 有非法时长（必须 > 0），已忽略`, `tracks.${name}.durations`);
    }
    let ds = nums.length ? nums : [DEFAULT_DURATION];
    if (ds.length < frames.length) {
      add('warn', 'bad-duration', `轨道 ${name} 的 durations 少于帧数，用最后一个补齐`, `tracks.${name}.durations`);
      while (ds.length < frames.length) ds.push(ds[ds.length - 1]);
    }
    if (ds.length > frames.length) ds = ds.slice(0, frames.length);

    const track = { frames, durations: ds };

    if (raw.loop === true) track.loop = true;
    else if (raw.loop !== undefined && typeof raw.loop !== 'boolean') {
      add('warn', 'bad-loop', `轨道 ${name} 的 loop 不是布尔值，按 false 处理`, `tracks.${name}.loop`);
    }

    if (raw.fallback !== undefined) {
      if (typeof raw.fallback === 'string' && raw.fallback) track.fallback = raw.fallback;
      else add('warn', 'unknown-fallback', `轨道 ${name} 的 fallback 不是字符串，已忽略`, `tracks.${name}.fallback`);
    }

    if (raw.ambient === true) track.ambient = true;

    out[name] = track;
  }

  return out;
}

function validateManifest(manifest, frames) {
  const diagnostics = [];
  const add = (level, code, message, where) => {
    diagnostics.push({ level, code, message, where: where || '' });
  };

  const frameMap = isObject(frames) ? frames : {};
  const hasFrame = (n) => Object.prototype.hasOwnProperty.call(frameMap, n);
  const src = isObject(manifest) ? manifest : {};

  let schemaVersion = src.schemaVersion;
  if (schemaVersion === undefined) schemaVersion = 1;
  if (schemaVersion !== 1 && schemaVersion !== 2) {
    add('error', 'bad-schema', `未知的 schemaVersion：${String(schemaVersion)}，按 1 处理`, 'schemaVersion');
    schemaVersion = 1;
  }

  /* 没写 tracks（v1 清单）就用现有帧合成默认轨道；写了就只认写的（DSH 的 v2 口径） */
  const declaredTracks = isObject(src.tracks) ? src.tracks : null;
  const tracks = declaredTracks
    ? validateTracks(declaredTracks, hasFrame, add)
    : buildDefaultTracks(frameMap);

  if (!tracks.idle && hasFrame('base')) {
    tracks.idle = { frames: ['base'], durations: [600], loop: true };
    add('warn', 'no-idle', '没有 idle 轨道，已按 base 补一条', 'tracks.idle');
  }

  /* fallback：目标必须存在，且不能成环 */
  for (const [name, track] of Object.entries(tracks)) {
    if (!track.fallback) continue;
    if (!tracks[track.fallback]) {
      add('warn', 'unknown-fallback', `轨道 ${name} 的 fallback 指向不存在的轨道 ${track.fallback}，已断开`, `tracks.${name}.fallback`);
      delete track.fallback;
      continue;
    }
    const seen = new Set([name]);
    let cur = track.fallback;
    let depth = 0;
    while (cur && depth < 16) {
      if (seen.has(cur)) {
        add('warn', 'fallback-cycle', `fallback 成环：${name} → … → ${cur}，已断开`, `tracks.${name}.fallback`);
        delete track.fallback;
        break;
      }
      seen.add(cur);
      cur = tracks[cur] && tracks[cur].fallback;
      depth++;
    }
  }

  /* sequences：数组，逐个引用轨道；引用不到的条目丢弃 */
  const sequences = {};
  if (isObject(src.sequences)) {
    for (const [name, seq] of Object.entries(src.sequences)) {
      if (!Array.isArray(seq)) {
        add('warn', 'bad-sequence', `序列 ${name} 不是数组，已丢弃`, `sequences.${name}`);
        continue;
      }
      const cleaned = [];
      for (const ref of seq) {
        if (typeof ref === 'string' && tracks[ref]) cleaned.push(ref);
        else add('warn', 'unknown-sequence-track', `序列 ${name} 引用了不存在的轨道 ${String(ref)}，已跳过`, `sequences.${name}`);
      }
      if (!cleaned.length) {
        add('warn', 'empty-sequence', `序列 ${name} 没有可用轨道，已丢弃`, `sequences.${name}`);
        continue;
      }
      sequences[name] = cleaned;
    }
  } else if (src.sequences !== undefined) {
    add('warn', 'bad-sequence', 'sequences 不是对象，已忽略', 'sequences');
  }

  /* phases：相位 → 轨道；用户写错的丢掉，其余用默认相位补 */
  const phases = buildDefaultPhases(tracks);
  if (isObject(src.phases)) {
    for (const [phase, ref] of Object.entries(src.phases)) {
      if (typeof ref === 'string' && tracks[ref]) phases[phase] = ref;
      else add('warn', 'unknown-phase-track', `相位 ${phase} 指向不存在的轨道 ${String(ref)}，已丢弃`, `phases.${phase}`);
    }
  } else if (src.phases !== undefined) {
    add('warn', 'unknown-phase-track', 'phases 不是对象，已忽略', 'phases');
  }

  /* 用户没写 sequences 时给一条默认待机小序列（只当相关帧齐全） */
  if (!isObject(src.sequences)) {
    Object.assign(sequences, buildDefaultSequences(tracks));
  }

  return { schemaVersion, tracks, sequences, phases, diagnostics };
}

module.exports = {
  DEFAULT_DURATION,
  buildDefaultTracks,
  buildDefaultPhases,
  buildDefaultSequences,
  validateManifest
};
