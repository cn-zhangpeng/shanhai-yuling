'use strict';
// 清单校验单元测试：node tests/unit-manifest.js
const assert = require('assert');
const { validateManifest } = require('../lib/manifest');

let failed = 0;
function test(name, fn) {
  try { fn(); console.log('ok   ' + name); }
  catch (e) { failed++; console.log('FAIL ' + name + '\n     ' + (e && e.message)); }
}

const ALL = ['base', 'blink', 'turn', 'turnL', 'smile', 'talk', 'wave', 'footSwing', 'handEar',
  'stand', 'phone', 'walkA', 'walkP1', 'walkB', 'walkP2', 'ropeAir', 'ropeLand',
  'ntTurn', 'ntTurnL', 'ntSmile', 'ntWave', 'ntFootSwing', 'ntHandEar', 'ntBlink'];
const F = (names) => Object.fromEntries(names.map((n) => [n, { rel: n + '.png' }]));
const all = F(ALL);
const codes = (r) => r.diagnostics.map((d) => d.code);

test('v1 清单（没写 tracks）自动合成默认轨道/相位/待机序列', () => {
  const r = validateManifest({ schemaVersion: 1 }, all);
  assert.equal(r.schemaVersion, 1);
  assert.ok(r.tracks.idle && r.tracks.idle.frames[0] === 'base' && r.tracks.idle.loop);
  assert.ok(r.tracks.walk && r.tracks.walk.frames.length === 4, '走路 4 姿态');
  assert.ok(r.tracks.rope && r.tracks.rope.durations[0] === 185, '跳绳 185ms');
  assert.equal(r.phases.blink, 'blink');
  assert.equal(r.phases.greet, 'wave');
  assert.deepEqual(r.sequences.idle, ['turn', 'idle', 'smile']);
  assert.deepEqual(r.diagnostics, [], '默认值不该产生诊断');
});

test('只有 base 的静态形象：不凭空生成缺帧的轨道', () => {
  const r = validateManifest({}, F(['base']));
  assert.deepEqual(Object.keys(r.tracks), ['idle']);
  assert.deepEqual(r.phases, { idle: 'idle' });
  assert.deepEqual(r.sequences, {});
});

test('显式 v2 轨道：缺帧跳过并 warn、空轨道丢弃并 error、durations 补齐', () => {
  const r = validateManifest({
    schemaVersion: 2,
    tracks: {
      idle: { frames: ['base'], durations: [600], loop: true },
      walk: { frames: ['walkA', 'nope', 'walkB'], durations: [200], loop: true },
      odd: { frames: [] },
      bad: { frames: 'oops' }
    }
  }, all);
  assert.deepEqual(r.tracks.walk.frames, ['walkA', 'walkB'], '缺帧被跳过');
  assert.deepEqual(r.tracks.walk.durations, [200, 200], 'durations 用最后一个补齐');
  assert.ok(!r.tracks.odd && !r.tracks.bad, '空轨道/坏轨道丢弃');
  const c = codes(r);
  assert.ok(c.includes('unknown-frame'), '缺帧 warn');
  assert.ok(c.includes('empty-track'), '空轨道 error');
  assert.ok(c.includes('bad-track'), '坏轨道 error');
  assert.ok(c.includes('bad-duration'), '时长补齐 warn');
});

test('fallback 成环被断开，不存在的 fallback 被清掉', () => {
  const r = validateManifest({
    schemaVersion: 2,
    tracks: {
      idle: { frames: ['base'], durations: [600], loop: true },
      a: { frames: ['turn'], durations: [100], fallback: 'b' },
      b: { frames: ['turnL'], durations: [100], fallback: 'a' },
      c: { frames: ['smile'], durations: [100], fallback: 'ghost' }
    }
  }, all);
  const c1 = codes(r);
  assert.ok(c1.includes('fallback-cycle'), '成环 warn');
  assert.ok(c1.includes('unknown-fallback'), '悬空 fallback warn');
  const t = r.tracks;
  assert.ok(!(t.a.fallback === 'b' && t.b.fallback === 'a'), '成环至少断掉一条');
  assert.ok(!t.c.fallback, '悬空 fallback 清掉');
});

test('未知字段与未知 schemaVersion：warn / error 且按 1 处理', () => {
  const r = validateManifest({ schemaVersion: 9, tracks: { idle: { frames: ['base'], speed: 3 } } }, all);
  assert.equal(r.schemaVersion, 1);
  const c = codes(r);
  assert.ok(c.includes('bad-schema'), '未知版本 error');
  assert.ok(c.includes('unknown-field'), '未知字段 warn');
});

test('序列/相位引用不存在的轨道时逐条丢弃', () => {
  const r = validateManifest({
    schemaVersion: 2,
    tracks: { idle: { frames: ['base'], durations: [600], loop: true } },
    sequences: { s: ['idle', 'ghost'], empty: ['ghost'] },
    phases: { blink: 'ghost' }
  }, all);
  assert.deepEqual(r.sequences.s, ['idle']);
  assert.ok(!r.sequences.empty, '整条空序列丢弃');
  assert.ok(!r.phases.blink, '错误相位不生效');
  const c = codes(r);
  assert.ok(c.includes('unknown-sequence-track'));
  assert.ok(c.includes('empty-sequence'));
  assert.ok(c.includes('unknown-phase-track'));
});

if (failed) { console.log('\n' + failed + ' 个用例失败'); process.exit(1); }
console.log('\n全部通过');
