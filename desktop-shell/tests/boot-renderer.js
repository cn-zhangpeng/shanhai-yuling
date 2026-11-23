// 渲染层启动集成测试：在真 Electron 里加载 desk-pet.html，灌入真实生灵 payload，
// 验证"清单轨道 → 播放器 → setFrame"整条链路。用法（先清 ELECTRON_RUN_AS_NODE）：
//   Start-Process .\desktop-shell\node_modules\electron\dist\electron.exe `
//     -ArgumentList "desktop-shell\tests\boot-renderer.js" -Wait -NoNewWindow
// 注意：窗口必须真正显示（隐藏/离屏时 Chromium 会节流甚至停发 rAF），测试跑约 8s。
'use strict';
const { app, BrowserWindow, protocol, ipcMain, nativeImage, session } = require('electron');
const path = require('path');
const fs = require('fs');
const pack = require('../creature-pack');

protocol.registerSchemesAsPrivileged([{
  scheme: 'pet',
  privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true }
}]);

const errors = [];

app.whenReady().then(async () => {
  const registry = pack.createRegistry({
    appDir: path.join(__dirname, '..'),
    userDataDir: path.join(__dirname, '_boot_userdata'),
    nativeImage,
    log: (m) => console.log('[pack]', m)
  });
  registry.ensureUserCreatureDir();
  const payload = registry.payload('ranran');
  if (!payload) { console.log('FATAL 没有可用生灵'); app.exit(2); return; }
  console.log('PAYLOAD', payload.id, 'frames=', Object.keys(payload.frames).length, 'tracks=', Object.keys(payload.tracks).length);

  ipcMain.handle('creature:get', () => payload);
  protocol.handle('pet', (req) => {
    let u;
    try { u = new URL(req.url); } catch (e) { return new Response('bad', { status: 400 }); }
    const segs = u.pathname.split('/').filter(Boolean);
    if (segs.length < 2 || u.hostname !== 'creature') return new Response('bad', { status: 400 });
    const file = registry.resolve(decodeURIComponent(segs[0]), segs.slice(1).map(decodeURIComponent).join('/'));
    if (!file) return new Response('not found', { status: 404 });
    try {
      return new Response(fs.readFileSync(file), {
        headers: { 'Content-Type': pack.MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', 'Cache-Control': 'no-cache' }
      });
    } catch (e) { return new Response('read fail', { status: 500 }); }
  });

  try { await session.defaultSession.clearCache(); } catch (e) {}
  const win = new BrowserWindow({
    show: true, x: 120, y: 120, width: 420, height: 760,
    webPreferences: { contextIsolation: true, nodeIntegration: false, preload: path.join(__dirname, 'stub-preload.js') }
  });
  win.webContents.on('console-message', (e, level, msg) => {
    if (level >= 2) console.log('[page]', level, msg);
    if (level >= 3) errors.push(msg);
  });

  await win.loadFile(path.join(__dirname, '..', 'desk-pet.html'));
  /* 无头/测试环境下 rAF 可能不派发，换成 setTimeout 泵让播放器 tick 跑起来（正式运行用原生 rAF） */
  await win.webContents.executeJavaScript(`
    requestAnimationFrame = function (cb) { return setTimeout(function () { cb(performance.now()); }, 16); };
    cancelAnimationFrame = function (id) { clearTimeout(id); };
    true;
  `);

  for (let i = 0; i < 60; i++) {
    const ok = await win.webContents.executeJavaScript('typeof BOOTED !== "undefined" && BOOTED === true').catch(() => false);
    if (ok) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  /* 静音自主调度（眨眼/小动作/问候都被拖拽状态挡住）；开场 1.6s 的直排问候等它演完 */
  await win.webContents.executeJavaScript('S.dragging = true;');
  await new Promise((r) => setTimeout(r, 2400));

  const r = await win.webContents.executeJavaScript(`(async () => {
    const out = {
      hasPetState: !!window.PetState,
      tracks: Object.keys(TRACKS).length,
      sequences: Object.keys(SEQUENCES).length,
      phases: Object.keys(PHASES).length,
      diag: DIAG.length,
      frames: Object.keys(imgs).length,
      caps: CAPS
    };
    playTrack('turn');
    await new Promise(r => setTimeout(r, 130));
    out.afterTurn = curFrame;
    playSequence('idle');
    const seen = [];
    const t = performance.now();
    while (performance.now() - t < 3400) {
      if (seen[seen.length - 1] !== curFrame) seen.push(curFrame);
      await new Promise(r => setTimeout(r, 30));
    }
    out.seen = seen;
    out.seqEnd = curFrame;
    return out;
  })()`);

  console.log('RESULT ' + JSON.stringify(r));
  const idx = (f) => r.seen.indexOf(f);
  const seqOk = idx('turn') >= 0 && idx('base') > idx('turn') && idx('smile') > idx('base') && r.seqEnd === 'base';
  const bad = !r.hasPetState || r.tracks < 10 || r.diag > 0 || r.afterTurn !== 'turn' || !seqOk;
  console.log(bad ? 'BOOT_ASSERT_FAIL' : 'BOOT_ASSERT_OK');
  app.exit(bad || errors.length ? 1 : 0);
}).catch((e) => { console.log('FATAL', e && e.stack || e); app.exit(1); });
