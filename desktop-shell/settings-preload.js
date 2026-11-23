const { contextBridge, ipcRenderer } = require('electron');

/* 设置页能用的全部能力。只走 invoke / 单向事件，不暴露 ipcRenderer */
contextBridge.exposeInMainWorld('settingsAPI', {
  getState: () => ipcRenderer.invoke('settings:state'),
  selectCreature: (id) => ipcRenderer.invoke('settings:select', id),
  saveLines: (cid, lines) => ipcRenderer.invoke('settings:save-lines', { cid, lines }),
  resetLines: (cid) => ipcRenderer.invoke('settings:reset-lines', cid),
  preview: (text) => ipcRenderer.invoke('settings:preview', text),
  openFolder: (which) => ipcRenderer.invoke('settings:open-folder', which),
  frames: () => ipcRenderer.invoke('settings:frames'),
  cloneCreature: () => ipcRenderer.invoke('settings:clone'),
  uploadFrame: (name) => ipcRenderer.invoke('settings:frame-upload', name),
  clearFrame: (name) => ipcRenderer.invoke('settings:frame-clear', name),
  onStateChanged: (cb) => ipcRenderer.on('settings:state-changed', (_e, s) => cb(s))
});
