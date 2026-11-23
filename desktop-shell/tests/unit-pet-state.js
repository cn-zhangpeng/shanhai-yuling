'use strict';
// 帧轨道播放器单元测试：node tests/unit-pet-state.js
const assert = require('assert');
const { createPlayer } = require('../lib/pet-state');

let failed = 0;
function test(name, fn) {
  try { fn(); console.log('ok   ' + name); }
  catch (e) { failed++; console.log('FAIL ' + name + '\n     ' + (e && e.message)); }
}

function harness() {
  const clock = { t: 0 };
  const seen = [];
  const settled = [];
  const p = createPlayer({
    tracks: {
      a: { frames: ['a1'], durations: [100], fallback: 'b' },
      b: { frames: ['b1'], durations: [50], loop: true },
      x: { frames: ['x1'], durations: [100], loop: true },
      y: { frames: ['y1', 'y2'], durations: [50, 50] },
      yf: { frames: ['y1'], durations: [50], fallback: 'b' },
      z: { frames: ['z1'], durations: [10] }
    },
    sequences: { s: ['x', 'y'], sf: ['x', 'yf'] },
    clock: () => clock.t,
    onFrame: (f, info) => seen.push([f, info.track, info.index, info.loop]),
    onSettle: (tag) => settled.push(tag)
  });
  return { p, clock, seen, settled };
}

test('非循环播完走 fallback，fallback 循环后一直播', () => {
  const { p, clock, seen, settled } = harness();
  p.play('a');                       // t=0 -> a1
  clock.t = 100; p.tick();           // a 播完 -> b1
  clock.t = 150; p.tick();           // b 循环 -> b1
  assert.deepEqual(seen.map((s) => s[0]), ['a1', 'b1', 'b1']);
  assert.equal(seen[2][3], true, 'fallback 轨道 loop=true');
  assert.deepEqual(settled, [], '没有 settle');
});

test('没有 fallback 的轨道停在末帧并 onSettle', () => {
  const { p, clock, settled } = harness();
  p.play('z');
  clock.t = 10; p.tick();
  assert.deepEqual(settled, ['z']);
  assert.ok(p.settled());
  assert.equal(p.current().frame, 'z1');
});

test('序列按顺序播，循环轨道只播一轮', () => {
  const { p, clock, seen, settled } = harness();
  p.playSequence('s');               // t=0 -> x1
  clock.t = 100; p.tick();           // x 结束 -> y1
  clock.t = 150; p.tick();           // y -> y2
  clock.t = 200; p.tick();           // y 结束 -> settle('s')
  assert.deepEqual(seen.map((s) => s[0]), ['x1', 'y1', 'y2']);
  assert.deepEqual(settled, ['s']);
  assert.equal(p.current().done, true);
});

test('序列最后一条有 fallback：演完回落，不把最后一帧挂住', () => {
  const { p, clock, seen, settled } = harness();
  p.playSequence('sf');              // x1
  clock.t = 100; p.tick();           // x 结束 -> y1
  clock.t = 150; p.tick();           // yf 结束 -> fallback b1
  clock.t = 200; p.tick();           // b 循环 -> b1
  assert.deepEqual(seen.map((s) => s[0]), ['x1', 'y1', 'b1', 'b1']);
  assert.deepEqual(settled, [], '序列有回落时不该 settle');
  assert.equal(p.current().track, 'b');
});

test('切后台回来一次大跳：补帧有上限，不死循环', () => {
  const { p, clock, seen } = harness();
  p.play('x');
  clock.t = 1e9; p.tick();
  assert.ok(seen.length <= 1002, '补帧不超过 1000 次：' + seen.length);
});

test('stop / 播不存在的轨道都不残留状态', () => {
  const { p } = harness();
  assert.equal(p.play('nope'), false);
  assert.equal(p.current(), null);
  p.play('z');
  p.stop();
  assert.equal(p.current(), null);
  p.tick();                          // 不抛
});

if (failed) { console.log('\n' + failed + ' 个用例失败'); process.exit(1); }
console.log('\n全部通过');
