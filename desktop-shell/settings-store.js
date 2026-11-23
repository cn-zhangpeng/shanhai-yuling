'use strict';
/**
 * 运行时设置（跟安装目录无关，装到哪、升级都不丢）
 *   <userData>/settings.json
 *   {
 *     "creatureId": "ranran",          当前选中的生灵
 *     "mode": "quiet",                 安静 / 活泼
 *     "lines": { "ranran": [ ... ] }   每个生灵的常用语覆盖；没写就用它目录里的 lines.json
 *   }
 * 写盘一律「临时文件 + rename」，中途断电不会留下半个 JSON；
 * 读到坏文件先备份成 .bak 再用默认值，不让程序起不来。
 */
const fs = require('fs');
const path = require('path');

const DEFAULT_STATE = { creatureId: null, mode: 'quiet', lines: {} };

function createStore(file, log) {
  const say = log || (() => {});
  let state = load();

  function normalize(obj) {
    return {
      creatureId: typeof obj.creatureId === 'string' && obj.creatureId ? obj.creatureId : null,
      mode: obj.mode === 'lively' ? 'lively' : 'quiet',
      lines: (obj.lines && typeof obj.lines === 'object' && !Array.isArray(obj.lines)) ? obj.lines : {}
    };
  }

  function load() {
    try {
      if (!fs.existsSync(file)) return { ...DEFAULT_STATE };
      const raw = fs.readFileSync(file, 'utf8');
      const obj = JSON.parse(raw);
      return normalize(obj);
    } catch (e) {
      say('settings.json 读不动，已备份为 .bak 并用默认值: ' + e.message);
      try { fs.copyFileSync(file, file + '.bak'); } catch (_) { /* 备份失败也不能拦着启动 */ }
      return { ...DEFAULT_STATE };
    }
  }

  function save(patch) {
    state = normalize(Object.assign({}, state, patch || {}));
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const tmp = file + '.tmp';
    const body = {
      _说明: '这个文件是「山海遇灵」的运行时设置，程序会自己读写；手改也可以，写完保存即生效。',
      ...state
    };
    fs.writeFileSync(tmp, JSON.stringify(body, null, 2), 'utf8');
    fs.renameSync(tmp, file);
    return state;
  }

  return {
    path: file,
    get: () => ({ ...state, lines: { ...state.lines } }),
    getCreatureId: () => state.creatureId,
    getMode: () => state.mode,
    setCreatureId: (id) => save({ creatureId: id }),
    setMode: (mode) => save({ mode }),
    getLines: (id) => {
      const v = state.lines[id];
      return Array.isArray(v) && v.length ? v : null;
    },
    setLines: (id, lines) => {
      const next = { ...state.lines };
      if (Array.isArray(lines) && lines.length) next[id] = lines;
      else delete next[id];
      return save({ lines: next });
    },
    clearLines: (id) => {
      const next = { ...state.lines };
      delete next[id];
      return save({ lines: next });
    },
    reload: () => { state = load(); return state; }
  };
}

module.exports = { createStore, DEFAULT_STATE };
