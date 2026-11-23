'use strict';
// 生灵包清单核对：node tools/validate-creature.js [目录]
// 目录缺省为 desktop-shell/assets。有 error 诊断时 exit 1（warn 只打印）。
const fs = require('fs');
const path = require('path');
const pack = require('../creature-pack');
const { validateManifest } = require('../lib/manifest');

const dir = path.resolve(process.argv[2] || path.join(__dirname, '..', 'assets'));
if (!fs.existsSync(dir)) { console.error('目录不存在：' + dir); process.exit(2); }

const images = pack.collectImages(dir);
const idx = pack.buildFrameIndex(dir, images);
const frames = {};
for (const [name, file] of Object.entries(idx)) {
  frames[name] = { rel: path.relative(dir, file).split(path.sep).join('/') };
}
const manifest = pack.readJson(path.join(dir, 'creature.json')) || {};
const r = validateManifest(manifest, frames);

console.log('生灵目录：' + dir);
console.log('认出帧：' + Object.keys(frames).length + ' / ' + pack.CANONICAL_FRAMES.length + '  ' + Object.keys(frames).join(' '));
console.log('schemaVersion：' + r.schemaVersion + '（creature.json 写的是 ' +
  (manifest.schemaVersion === undefined ? '未写，按 v1' : manifest.schemaVersion) + '）');
console.log('轨道：' + (Object.keys(r.tracks).join('、') || '（无）'));
console.log('相位：' + JSON.stringify(r.phases));
console.log('序列：' + JSON.stringify(r.sequences));
if (r.diagnostics.length) {
  console.log('\n诊断：');
  for (const d of r.diagnostics) {
    console.log((d.level === 'error' ? '[错误] ' : '[警告] ') + d.code + ' @ ' + (d.where || '-') + ' — ' + d.message);
  }
} else {
  console.log('\n诊断：（无）');
}

const errs = r.diagnostics.filter((d) => d.level === 'error');
if (!Object.keys(frames).length) { console.log('[错误] 一张帧都没认出来：检查目录与文件名'); process.exit(1); }
process.exit(errs.length ? 1 : 0);
