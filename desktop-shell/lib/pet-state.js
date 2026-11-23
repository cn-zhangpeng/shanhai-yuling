'use strict';
/**
 * 帧轨道播放器（纯逻辑，时钟可注入；浏览器和 Node 都能加载）
 *
 * 契约对齐 DSH 宠物插件的 frames2d 渲染器：清单里的 track 是一串帧 + 每帧时长 +
 * loop + fallback。这里只负责"当前该显示第几帧"，真正的绘制由调用方在 onFrame 里做。
 *
 *   const p = PetState.createPlayer({ tracks, sequences, onFrame(frame, info) });
 *   p.play('blink');          // 单轨：非循环播完走 fallback，再没有就停住并 onSettle
 *   p.playSequence('idle');   // 序列：按顺序把每条轨道播一遍（轨道内的 loop 只播一轮）
 *   p.tick(now);              // 由 requestAnimationFrame 驱动；一帧都不跳、追帧有上限
 *
 * 用法要点：
 *   · onFrame 只在帧变化时回调，调用方不要在里面再触发播放器，否则会递归。
 *   · tick 允许"补帧"（切后台回来时一次追多帧），但最多追 1000 帧，防死循环。
 *   · stop() 之后 current() 为 null；settled() 表示没在播 / 已停住。
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PetState = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function defaultClock() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
  }

  function createPlayer(opts) {
    const o = opts || {};
    const tracks = o.tracks || {};
    const sequences = o.sequences || {};
    const clock = typeof o.clock === 'function' ? o.clock : defaultClock;
    const onFrame = typeof o.onFrame === 'function' ? o.onFrame : function () {};
    const onSettle = typeof o.onSettle === 'function' ? o.onSettle : function () {};

    let state = null;   /* { name, index, startedAt, seq, seqIndex, depth, done } */

    function durationAt(track, i) {
      const ds = track && Array.isArray(track.durations) ? track.durations : null;
      if (!ds || !ds.length) return 200;
      const v = Number(ds[Math.min(i, ds.length - 1)]);
      return Number.isFinite(v) && v > 0 ? v : 200;
    }

    function emit(name, index) {
      const track = tracks[name];
      if (!track || !Array.isArray(track.frames) || !track.frames.length) return;
      onFrame(track.frames[Math.min(index, track.frames.length - 1)], {
        track: name,
        index: Math.min(index, track.frames.length - 1),
        loop: !!track.loop
      });
    }

    function start(name, extra) {
      const track = tracks[name];
      if (!track || !Array.isArray(track.frames) || !track.frames.length) return false;
      const e = extra || {};
      state = {
        name,
        index: 0,
        startedAt: clock(),
        seq: e.seq || null,
        seqIndex: e.seqIndex || 0,
        depth: e.depth || 0,
        done: false
      };
      emit(name, 0);
      return true;
    }

    function finishSeq() {
      const track = tracks[state.name];
      /* 序列演完不能把最后一帧（比如笑）永远挂在脸上：
         和单轨一样走 fallback 回落（通常是 idle 循环），没有 fallback 才停住 */
      if (track && track.fallback && state.depth < 4 && tracks[track.fallback]) {
        start(track.fallback, { depth: state.depth + 1 });
        return;
      }
      state.index = track.frames.length - 1;
      state.done = true;
      onSettle(state.seq);
    }

    function nextInSequence() {
      const list = sequences[state.seq];
      const next = state.seqIndex + 1;
      if (!Array.isArray(list) || next >= list.length) return false;
      return start(list[next], { seq: state.seq, seqIndex: next, depth: state.depth });
    }

    function advance() {
      const track = tracks[state.name];
      if (!track) { state = null; return; }
      const nextIndex = state.index + 1;

      if (nextIndex < track.frames.length) {
        state.index = nextIndex;
        emit(state.name, state.index);
        return;
      }

      /* 序列里的轨道：loop 只播一轮，播完直接进入下一条 */
      if (state.seq) {
        if (nextInSequence()) return;
        finishSeq();
        return;
      }

      if (track.loop) {
        state.index = 0;
        emit(state.name, 0);
        return;
      }

      if (track.fallback && state.depth < 4 && tracks[track.fallback]) {
        start(track.fallback, { depth: state.depth + 1 });
        return;
      }

      state.index = track.frames.length - 1;
      state.done = true;
      onSettle(state.name);
    }

    return {
      play(name) {
        state = null;
        return start(name);
      },
      playSequence(name) {
        const list = sequences[name];
        if (!Array.isArray(list) || !list.length) return false;
        state = null;
        return start(list[0], { seq: name, seqIndex: 0 });
      },
      tick(now) {
        if (!state || state.done) return;
        const t = (now === undefined || now === null) ? clock() : now;
        let guard = 0;
        while (guard++ < 1000) {
          const track = tracks[state.name];
          if (!track) { state = null; return; }
          const dur = durationAt(track, state.index);
          if (t - state.startedAt < dur) return;
          state.startedAt += dur;
          advance();
          if (!state || state.done) return;
        }
      },
      stop() { state = null; },
      current() {
        if (!state) return null;
        const track = tracks[state.name];
        if (!track) return null;
        const index = Math.min(state.index, track.frames.length - 1);
        return { track: state.name, index, frame: track.frames[index], seq: state.seq, done: state.done };
      },
      isPlaying(name) { return !!state && state.name === name && !state.done; },
      isActive() { return !!state && !state.done; },
      settled() { return !state || state.done; }
    };
  }

  return { createPlayer };
});
