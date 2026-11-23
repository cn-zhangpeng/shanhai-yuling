// 冒烟自检：不建窗口，只跑生灵包注册表 —— 扫描、认帧、量锚点、拼 URL、拼载荷
// 跑法：node_modules\electron\dist\electron.exe tests\smoke-creature.js
// 结果写到 tests\_smoke.json（Windows 上 electron.exe 是 GUI 子系统，stdout 常常拿不到）
const fs = require('fs');
const path = require('path');
const { app, nativeImage } = require('electron');
const pack = require('../creature-pack');

const OUT = path.join(__dirname, '_smoke.json');
let lines = '';
const say = (...a) => {
  lines += a.map((x) => (typeof x === 'string' ? x : JSON.stringify(x))).join(' ') + '\n';
  try { fs.writeFileSync(OUT, lines, 'utf8'); } catch (e) { /* 写不进去也要继续跑 */ }
};

/* 固定测试用的用户目录：别去动真实那份 %APPDATA%\山海遇灵 */
app.setName('山海遇灵');
app.setPath('userData', path.join(__dirname, '_smoke_userdata'));

app.whenReady().then(() => {
  const reg = pack.createRegistry({
    appDir: path.resolve(__dirname, '..'),
    userDataDir: app.getPath('userData'),
    nativeImage,
    log: (m) => say('[pack]', m)
  });
  reg.ensureUserCreatureDir(path.join(path.resolve(__dirname, '..'), 'assets'));

  const brief = reg.brief();
  say('BRIEF', brief.map((c) => ({
    id: c.id, name: c.displayName, status: c.status, frames: c.frameCount,
    missing: c.missing, companion: c.hasCompanion, lines: c.lineCount
  })));

  const p = reg.payload(brief[0].id);
  say('WINDOW', p.window);
  say('FRAMES', Object.keys(p.frames).length);
  say('CAPS', p.caps);
  say('LINES', p.lines.length, 'sample=', p.lines[0]);
  const rows = Object.entries(p.frames).map(([k, v]) => [k, Math.round(v.ratio * 1360)]).sort((a, b) => a[1] - b[1]);
  say('ANCHOR_PX', Object.fromEntries(rows));
  say('URL_BASE', p.frames.base.url);
  say('URL_COMPANION', p.companion && p.companion.url);
  say('RESOLVE_OK', reg.resolve(p.id, p.frames.base.rel) ? 'yes' : 'no');
  say('RESOLVE_ESCAPE', reg.resolve(p.id, '../../../package.json') ? 'LEAK' : 'blocked');
  say('TRACKS', Object.keys(p.tracks || {}));
  say('PHASES', p.phases);
  say('SEQUENCES', p.sequences);
  say('DIAG', p.diagnostics);

  const sample = brief.find((c) => c.id === 'sample');
  if (sample) say('SAMPLE', { status: sample.status, caps: sample.caps, frames: sample.frameCount });

  /* 断言：清单 v2 的载荷必须自洽，诊断里不能有 error，路径逃逸必须被挡 */
  const failures = [];
  const wanted = ['idle', 'blink', 'walk', 'rope'];
  for (const t of wanted) if (!p.tracks || !p.tracks[t]) failures.push('缺少轨道 ' + t);
  if (!p.phases || !p.phases.blink) failures.push('缺少 phases.blink');
  if (!(p.frames.base && p.frames.base.rel)) failures.push('frames.base 缺少 rel');
  else if (!reg.resolve(p.id, p.frames.base.rel)) failures.push('frames.base.rel 解析不到：' + p.frames.base.rel);
  const errs = (p.diagnostics || []).filter((d) => d.level === 'error');
  if (errs.length) failures.push('诊断里有 error：' + JSON.stringify(errs));
  if (reg.resolve(p.id, '../../../package.json')) failures.push('路径逃逸没有被挡住');
  if (failures.length) {
    say('ASSERT_FAIL', failures.join(' | '));
    process.exit(1);
  }
  say('ASSERT_OK', 'tracks=' + Object.keys(p.tracks).length, 'sequences=' + Object.keys(p.sequences || {}).length);
  process.exit(0);
}).catch((e) => {
  say('ERROR ' + (e && e.stack || e));
  process.exit(1);
});
