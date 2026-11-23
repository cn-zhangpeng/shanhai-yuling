const { contextBridge, ipcRenderer } = require('electron');

/* 渲染层（桌宠本体）能用的全部能力。白名单，不暴露 ipcRenderer 本身 */
contextBridge.exposeInMainWorld('petAPI', {
  reportRects: (rects) => ipcRenderer.send('pet-rects', rects),
  dragStart: (x, y) => ipcRenderer.send('drag-start', { x, y }),
  dragMove: (x, y) => ipcRenderer.send('drag-move', { x, y }),
  dragEnd: () => ipcRenderer.send('drag-end'),
  ctxMenu: () => ipcRenderer.send('ctx-menu'),
  glide: (dx, ms) => ipcRenderer.send('pet-glide', { dx, ms }),
  onScene: (cb) => ipcRenderer.on('pet-scene', (_e, name) => cb(name)),
  onScale: (cb) => ipcRenderer.on('pet-scale', (_e, s) => cb(s)),
  onPin: (cb) => ipcRenderer.on('pet-pin', (_e, v) => cb(v)),
  onLock: (cb) => ipcRenderer.on('pet-lock', (_e, v) => cb(v)),

  /* 生灵包：开场拉一次当前生灵，之后设置页换形象时由主进程推 pet-creature */
  getCreature: () => ipcRenderer.invoke('creature:get'),
  onCreature: (cb) => ipcRenderer.on('pet-creature', (_e, payload) => cb(payload)),
  /* 这套图支持哪些场景/动作，报给主进程用来把菜单项置灰 */
  reportCapabilities: (caps) => ipcRenderer.send('pet-caps', caps),
  /* 常用语保存后热更新，不重启 */
  onLines: (cb) => ipcRenderer.on('pet-lines', (_e, lines) => cb(lines)),
  /* 设置页点"试一句"，主进程让这只桌宠把气泡弹出来 */
  onPreview: (cb) => ipcRenderer.on('pet-preview', (_e, text) => cb(text))
});
