// boot-renderer.js 用的最小 petAPI 替身：只喂 getCreature，其余交互全部空实现
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('petAPI', {
  reportRects: () => {},
  dragStart: () => {},
  dragMove: () => {},
  dragEnd: () => {},
  ctxMenu: () => {},
  glide: () => {},
  onScene: () => {},
  onScale: () => {},
  onPin: () => {},
  onLock: () => {},
  getCreature: () => ipcRenderer.invoke('creature:get'),
  onCreature: () => {},
  reportCapabilities: () => {},
  onLines: () => {},
  onPreview: () => {}
});
