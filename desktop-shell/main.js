// 山海遇灵 · 桌面壳（过渡预览版）
// 目标：透明无边框置顶窗口 + 分区鼠标穿透，渲染层与浏览器原型共用同一套素材与状态机。
// 最终交付走 Tauri 2；此壳用于先把"能浮在桌面上的实物"跑起来。
//
// 形象不再写死在代码里：每个生灵是一个目录，全部住在「生灵目录」（%APPDATA%/山海遇灵/creatures/<ID>/），
// 冉冉也在里面；程序目录的 assets/ 只是首次启动时的种子。帧按文件名认领语义，主进程扫描 → 量锚点 → 通过 pet:// 协议喂给渲染层。见 creature-pack.js。
const { app, BrowserWindow, screen, ipcMain, Menu, Tray, nativeImage, globalShortcut, session, protocol, shell, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

const pack = require('./creature-pack');
const { createStore } = require('./settings-store');

/* 应用名要在 ready 之前定死：它决定 app.getPath('userData')。
   不改的话开发态（package.json 里的 name 是 shanhai-yuling-desktop-shell）和打包态
   （productName 是 山海遇灵）会落在两个不同目录，生灵包和设置各存一份，谁也找不到谁 */
app.setName('山海遇灵');

/* 运行时尺寸：随生灵变（旧值 620×760 是冉冉的比例，别的比例换成对应值） */
let WIN_W = 620;
let WIN_H = 760;
const DEFAULT_SCALE = 0.8;   // 默认按 80% 开窗（496×608），太大挡桌面

let win = null;
let settingsWin = null;
let tray = null;
let petRects = [];          // 渲染层上报的精灵包围盒（窗口坐标）
let ignoring = true;        // 当前是否处于穿透态
let dragOrigin = null;      // 拖拽起点
let glideTimer = null;      // 走位动画
let winScale = DEFAULT_SCALE;  // 缩放倍率（1 = 原始尺寸）
let pinned = !(process.env.PET_PIN === '0');   // 钉住：默认钉在右下角，不再被场景平移（PET_PIN=0 可关）
let locked = false;         // 锁定：鼠标完全穿透，像 QQ 音乐桌面歌词锁那样点不到

let registry = null;        // 生灵包注册表（app ready 后建）
let store = null;           // settings.json
let currentId = null;
let currentIcon = { ico: null, png: null };
let petCaps = null;         // 当前生灵支持哪些场景（null = 未知，菜单全开）

function log(tag, msg) {
  try { fs.appendFileSync(path.join(__dirname, '_scene.log'), `${new Date().toISOString()} [${tag}] ${msg}\n`); } catch (e) {}
}

function winSize() {
  return { w: Math.round(WIN_W * winScale), h: Math.round(WIN_H * winScale) };
}

/* 缩放：渲染层用 zoom 整体缩放，窗口同步缩到对应尺寸（底部为锚点，脚不离地） */
function setScale(s) {
  if (!win || win.isDestroyed()) return;
  const oldH = win.getBounds().height;
  const [px, py] = win.getPosition();
  const area = screen.getDisplayNearestPoint({ x: px, y: py }).workArea;
  /* 上限由屏幕高度决定：窗口比工作区还高，她的头顶就会被屏幕切掉 */
  const maxS = Math.min(1.8, (area.height + 16) / WIN_H);
  winScale = Math.max(0.4, Math.min(maxS, s));
  const { w, h } = winSize();
  if (glideTimer) { clearInterval(glideTimer); glideTimer = null; }
  const ny = Math.max(area.y - 10, py + (oldH - h));
  win.setBounds({ x: px, y: ny, width: w, height: h }, false);
  win.webContents.send('pet-scale', winScale);
  refreshMenus();
}

function setPinned(v) {
  pinned = !!v;
  if (win && !win.isDestroyed()) win.webContents.send('pet-pin', pinned);
  refreshMenus();
}

/* 锁定 = 鼠标完全穿透：精灵本体上也不再翻转成可点击，点哪儿都落到她后面的窗口。
   解锁入口只有托盘菜单和 Ctrl+Alt+5（因为锁定后窗口本身已经点不到了） */
function setLocked(v) {
  locked = !!v;
  if (win && !win.isDestroyed()) {
    ignoring = true;
    win.setIgnoreMouseEvents(true, { forward: true });
    win.webContents.send('pet-lock', locked);
  }
  refreshMenus();
  log('main', 'lock=' + locked);
}

/* ---------------- 开机自启 ----------------
   直接读写 HKCU\Software\Microsoft\Windows\CurrentVersion\Run：
   不需要管理员权限、不碰计划任务，和"任务管理器 → 启动"里看到的是同一条。
   不用 app.setLoginItemSettings 两处原因（实测）：
     1) 它在 Windows 上回读按 path+args 匹配，刚写完就回读会是 false，菜单勾选永远对不上；
     2) 它写出的命令不带引号，项目一旦挪到带空格的目录（C:\Program Files\…）就起不来。
   开发态跑的是 node_modules\electron\dist\electron.exe，必须把 app 目录当参数带上；
   打包态跑自身 exe，不带参数。这样"设成自启的"和"当前正在跑的"永远是同一个东西 */
const AUTOSTART_NAME = 'ShanhaiYuling';
/* 旧值名是"应用名+当前生灵"时代的，留着迁移用：老用户升级后不许变成两条自启项 */
const AUTOSTART_NAME_LEGACY = 'ShanhaiYulingRanran';
const RUN_KEY = 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run';

function autostartTarget() {
  if (app.isPackaged) return { path: process.execPath, args: [] };
  return { path: process.execPath, args: [__dirname] };
}

/* 启动命令行：每段都加引号，路径里有空格也不会被 Windows 切断 */
function autostartCommand() {
  const { path: p, args } = autostartTarget();
  return [p].concat(args).map(s => `"${s}"`).join(' ');
}

/* reg.exe 用绝对路径：某些启动方式（精简 PATH、从工具链拉起的进程）里 System32 不在 PATH 上，
   直接写 'reg.exe' 会 ENOENT，自启就静默退化成 Electron 接口的不可靠实现 */
const REG_EXE = (function () {
  const p = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'reg.exe');
  try { return fs.existsSync(p) ? p : 'reg.exe'; } catch (e) { return 'reg.exe'; }
})();

function regSync(argv) {
  try {
    const { spawnSync } = require('child_process');
    return spawnSync(REG_EXE, argv, { encoding: 'utf8', windowsHide: true });
  } catch (e) {
    return { status: -1, stdout: '', stderr: e.message };
  }
}

/* 以注册表为准回读，而不是记在内存里：用户可能在任务管理器里禁了它，
   菜单勾选也得跟着走，不能自己骗自己。
   旧值名（ShanhaiYulingRanran）也算"开着"：勾选态不会因为改名而突然变没，
   下一次 syncAutostartPath 会把它迁到新名下 */
function getAutostart() {
  for (const name of [AUTOSTART_NAME, AUTOSTART_NAME_LEGACY]) {
    const r = regSync(['query', RUN_KEY, '/v', name]);
    if (r.status === 0) {
      if (new RegExp(name).test(r.stdout || '')) return true;
      continue;
    }
    if (r.status === 1) continue;                /* 这个值不存在，看下一个名字 */
    break;                                       /* reg.exe 不可用：走下面的兜底 */
  }
  /* reg.exe 不可用（极端环境）时退回 Electron 接口 */
  try { return !!app.getLoginItemSettings().openAtLogin; } catch (e) { return false; }
}

function setAutostart(v) {
  const want = !!v;
  let ok = false;
  const r = want
    ? regSync(['add', RUN_KEY, '/v', AUTOSTART_NAME, '/t', 'REG_SZ', '/d', autostartCommand(), '/f'])
    : regSync(['delete', RUN_KEY, '/v', AUTOSTART_NAME, '/f']);
  ok = r.status === 0 || (!want && r.status === 1);   /* 关掉时"本来就没有"也算成功 */
  if (!ok) {
    /* 写注册表被拦（组策略/杀软）时兜底一次 Electron 接口 */
    const { path: p, args } = autostartTarget();
    try { app.setLoginItemSettings({ openAtLogin: want, path: p, args, name: AUTOSTART_NAME, enabled: true }); } catch (e) {}
  }
  /* 新名字写好后把旧名字那条删掉：两个值名指向同一份程序，会变成两条自启项 */
  regSync(['delete', RUN_KEY, '/v', AUTOSTART_NAME_LEGACY, '/f']);
  /* 写完回读一次：以注册表实际状态为准，权限不足时菜单不会假装成功 */
  const real = getAutostart();
  log('main', `setAutostart want=${want} regOk=${ok} real=${real} cmd=${autostartCommand()}`);
  refreshMenus();
  return real;
}

/* 自启项可能指向另一个路径：装到别的目录、换机器拷贝、从开发态换成安装版。
   开着自启的实例每次启动都把它对齐到"当前正在跑的这个 exe"，
   用户不必记得重新勾一次（没开的话这里一个字都不写） */
function syncAutostartPath() {
  if (!getAutostart()) return;
  /* 不做字符串比对：中文路径的 reg 输出是 GBK，比也是白比；
       直接按当前目标重写，注册表项内容本来就该只有一份 */
  setAutostart(true);
}

/* 让窗口在桌面上平滑走一小段（渲染层按场景调用）：一次缓动，不逐帧硬设。
   缓动曲线用"梯形速度"而不是 easeInOutQuad：
   quad 的峰值速度是平均速度的 2 倍，配上本来就快的步频，看起来就是在桌面上滑过去；
   梯形只在头尾各 12% 的时间里加减速，中段匀速，和人迈步的匀速感对得上 */
function easeTrapezoid(t, ramp = 0.12) {
  const v = 1 / (1 - ramp);                 // 平台段速度（保证总位移等于 1）
  if (t < ramp) return v * t * t / (2 * ramp);
  if (t > 1 - ramp) { const u = 1 - t; return 1 - v * u * u / (2 * ramp); }
  return v * ramp / 2 + v * (t - ramp);
}

function glideBy(dx, ms) {
  if (!win || win.isDestroyed()) return;
  if (pinned) return;                                       /* 钉住了就不许被场景拖走 */
  const { w, h } = winSize();
  const [x0, y0] = win.getPosition();
  const area = screen.getDisplayNearestPoint({ x: x0, y: y0 }).workArea;
  const nxTarget = Math.max(area.x - 10, Math.min(area.x + area.width - w + 10, x0 + dx));
  const t0 = Date.now();
  if (glideTimer) clearInterval(glideTimer);
  glideTimer = setInterval(() => {
    const t = Math.min(1, (Date.now() - t0) / ms);
    const k = easeTrapezoid(t);
    const nx = Math.round(x0 + (nxTarget - x0) * k);
    /* setBounds 带上显式宽高：只 setPosition 时 Windows 会在移动过程中把窗口物理尺寸带偏 */
    win.setBounds({ x: nx, y: y0, width: w, height: h }, false);
    if (t >= 1) { clearInterval(glideTimer); glideTimer = null; }
  }, 16);
}

/* ---------------- 生灵包 ----------------
   payload = 当前生灵的全部运行时数据（帧 URL + 锚点比例 + 伴生灵 + 台词 + 支持能力）
   设置页换形象走 applyCreature；渲染层开场用 creature:get 自己拉一次 */
function currentPayload() {
  if (!registry || !currentId) return null;
  return registry.payload(currentId, { lines: store ? store.getLines(currentId) : null });
}

function payloadFor(id) {
  if (!registry || !id) return null;
  return registry.payload(id, { lines: store ? store.getLines(id) : null });
}

/* 不发给窗口，只把尺寸/图标/能力切过来（启动早期用） */
function prepareCreature(id) {
  const p = payloadFor(id);
  if (!p) return null;
  currentId = p.id;
  WIN_W = p.window.w;
  WIN_H = p.window.h;
  petCaps = p.caps;
  currentIcon = p.icon || { ico: null, png: null };
  return p;
}

function resizeWindowForCreature() {
  if (!win || win.isDestroyed()) return;
  const oldH = win.getBounds().height;
  const [px, py] = win.getPosition();
  const area = screen.getDisplayNearestPoint({ x: px, y: py }).workArea;
  const { w, h } = winSize();
  const ny = Math.max(area.y - 10, py + (oldH - h));
  const nx = Math.min(area.x + area.width - w + 10, px);
  win.setBounds({ x: nx, y: ny, width: w, height: h }, false);
}

function updateTrayIcon() {
  if (!tray) return;
  const p = currentIcon && (currentIcon.png || currentIcon.ico);
  if (!p) return;
  try {
    const img = nativeImage.createFromPath(p).resize({ width: 32, height: 32 });
    if (!img.isEmpty()) tray.setImage(img);
  } catch (e) { /* 图标坏了不影响桌宠本体 */ }
}

/* 切生灵：写盘 → 调窗口尺寸 → 推给渲染层（渲染层预加载完再一次性换，不会半新半旧） */
function applyCreature(id, persist) {
  if (!registry) return null;
  const p = payloadFor(id);
  if (!p) return null;
  currentId = p.id;
  WIN_W = p.window.w;
  WIN_H = p.window.h;
  petCaps = p.caps;
  currentIcon = p.icon || { ico: null, png: null };
  if (persist && store) store.setCreatureId(p.id);
  if (win && !win.isDestroyed()) {
    resizeWindowForCreature();
    win.webContents.send('pet-creature', p);
    win.webContents.send('pet-scale', winScale);
  }
  updateTrayIcon();
  refreshMenus();
  notifySettings();
  log('main', `creature=${p.id} status=${p.status} frames=${Object.keys(p.frames).length}`);
  return p;
}

/* 设置页要的状态：生灵清单 + 当前 + 当前台词 */
function settingsState() {
  if (!registry) return { creatures: [], currentId: null, lines: [], relation: '', petHeight: 600, frameNames: pack.CANONICAL_FRAMES };
  const p = currentPayload();
  return {
    creatures: registry.brief(),
    currentId: currentId,
    lines: p ? p.lines : [],
    relation: (p && p.profile && p.profile.relation) || '',
    displayName: p ? p.displayName : '',
    status: p ? p.status : '',
    caps: p ? p.caps : null,
    userRoot: registry.userRoot,
    builtinRoot: registry.builtinRoot,
    frameNames: pack.CANONICAL_FRAMES
  };
}

function notifySettings() {
  if (settingsWin && !settingsWin.isDestroyed()) {
    settingsWin.webContents.send('settings:state-changed', settingsState());
  }
}

function openSettings(tab) {
  const hash = (tab === 'lines' || tab === 'frames') ? tab : '';
  if (settingsWin && !settingsWin.isDestroyed()) {
    /* 已经开着就按需要翻页签，不再新开窗 */
    if (hash) settingsWin.loadFile(path.join(__dirname, 'settings.html'), { hash });
    settingsWin.show(); settingsWin.focus(); return;
  }
  settingsWin = new BrowserWindow({
    width: 820,
    height: 720,
    minWidth: 720,
    minHeight: 560,
    title: '山海遇灵 · 设置',
    autoHideMenuBar: true,
    backgroundColor: '#FCFAF6',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'settings-preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  settingsWin.loadFile(path.join(__dirname, 'settings.html'), hash ? { hash } : undefined);
  settingsWin.webContents.on('did-fail-load', (_e, code, desc, url) => log('settings', 'did-fail-load', code, desc, url));
  settingsWin.webContents.on('preload-error', (_e, p, err) => log('settings', 'preload-error', p, String(err)));
  settingsWin.once('ready-to-show', () => { log('settings', 'ready-to-show'); settingsWin.show(); });
  settingsWin.on('closed', () => { settingsWin = null; });
}

function createWindow() {
  const area = screen.getPrimaryDisplay().workArea;
  const { w, h } = winSize();
  /* 默认就钉在右下角：贴工作区右边留 90px（和菜单里"回到右下角"同一个坐标），底边留 6px */
  const x = area.x + area.width - w - 90;
  const y = area.y + area.height - h - 6;

  win = new BrowserWindow({
    width: w,
    height: h,
    x,
    y,
    transparent: true,
    frame: false,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    icon: currentIcon.ico || currentIcon.png || undefined,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.setAlwaysOnTop(true, 'screen-saver');
  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadFile(path.join(__dirname, 'desk-pet.html'));

  /* 开窗时窗口就是 80% 尺寸，渲染层也得按同样倍率缩放，否则画面会被裁掉一块 */
  win.webContents.on('did-finish-load', () => {
    win.webContents.send('pet-scale', winScale);
    /* 默认钉住这件事得同步告诉渲染层，否则它还会按"能走"来排日程 */
    win.webContents.send('pet-pin', pinned);
  });

  /* 场景链路留痕：点菜单 / 按快捷键 / PET_SCENE 都会在这里记一行，
     渲染层的 console 也一并收进来，用来确认"点了到底有没有反应" */
  win.webContents.on('console-message', (_e, _lvl, message, line) => {
    if (/\[scene\]|\[scale\]|\[pin\]|\[creature\]|\[caps\]|scene error|Uncaught|not defined|未就绪/i.test(message)) log('renderer', message + ' @' + line);
  });

  /* 调试：PET_SCENE=walk/rope/phone/play 启动后自动演一场（用来验收走位） */
  if (process.env.PET_SCENE) {
    win.webContents.on('did-finish-load', () => {
      setTimeout(() => triggerScene(process.env.PET_SCENE), 3000);
    });
  }

  /* 调试：PET_SCALE=0.8 启动即按该倍率缩放；PET_PIN=1 启动即钉住 */
  if (process.env.PET_SCALE) {
    win.webContents.on('did-finish-load', () => {
      setTimeout(() => setScale(parseFloat(process.env.PET_SCALE)), 1500);
    });
  }
  if (process.env.PET_PIN === '0') {
    win.webContents.on('did-finish-load', () => setTimeout(() => setPinned(false), 1500));
  }

  win.on('closed', () => { win = null; });

  /* 诊断开关：PET_DEBUG_BOUNDS=1 时把每次 move / resize 记进 _bounds.log */
  if (process.env.PET_DEBUG_BOUNDS) {
    const logPath = path.join(__dirname, '_bounds.log');
    const logB = (tag) => {
      try { fs.appendFileSync(logPath, `${new Date().toISOString()} ${tag} ${JSON.stringify(win.getBounds())}\n`); } catch (e) {}
    };
    win.on('move', () => logB('move'));
    win.on('resize', () => logB('resize'));
  }
}

// 30Hz 轮询光标：只有在精灵本体上才关掉穿透，其余区域一律穿到底下的窗口
function pollCursor() {
  if (!win || win.isDestroyed() || win.isVisible() === false) return;
  if (dragOffset) return;                       /* 拖拽期间别翻转穿透，否则会丢鼠标捕获 */
  if (locked) {                                 /* 锁定了就一直穿透，光标压在她身上也不接管 */
    if (!ignoring) { win.setIgnoreMouseEvents(true, { forward: true }); ignoring = true; }
    return;
  }
  const pt = screen.getCursorScreenPoint();
  const b = win.getBounds();
  const inside = petRects.some(r => {
    const x1 = b.x + r.x;
    const y1 = b.y + r.y;
    return pt.x >= x1 && pt.x <= x1 + r.w && pt.y >= y1 && pt.y <= y1 + r.h;
  });
  if (inside && ignoring) {
    win.setIgnoreMouseEvents(false);
    ignoring = false;
  } else if (!inside && !ignoring) {
    win.setIgnoreMouseEvents(true, { forward: true });
    ignoring = true;
  }
}

ipcMain.on('pet-rects', (_e, rects) => {
  petRects = Array.isArray(rects) ? rects : [];
});

/* 拖拽：由主进程按光标屏幕坐标算，不信渲染层传来的 screenX/screenY。
   原因：渲染层坐标是 CSS 像素（受 DPR、zoom 影响），和 setPosition 的 DIP 单位对不上，
   按住不动时差值会被反复放大，窗口就一直往一个方向飘，两只精灵看着像被扯开。
   主进程拿 getCursorScreenPoint 和窗口位置直接对账，单位天然一致，也不会累积误差 */
let dragOffset = null;
let dragTimer = null;

ipcMain.on('drag-start', () => {
  if (!win || win.isDestroyed()) return;
  const b = win.getBounds();
  const c = screen.getCursorScreenPoint();
  dragOffset = { dx: c.x - b.x, dy: c.y - b.y, w: b.width, h: b.height };
  if (dragTimer) clearInterval(dragTimer);
  dragTimer = setInterval(() => {
    if (!win || win.isDestroyed() || !dragOffset) return;
    const pt = screen.getCursorScreenPoint();
    /* setBounds 带显式宽高：只 setPosition 时 Windows 会把窗口物理尺寸改掉（实测 622 变 624） */
    win.setBounds({
      x: Math.round(pt.x - dragOffset.dx),
      y: Math.round(pt.y - dragOffset.dy),
      width: dragOffset.w,
      height: dragOffset.h
    }, false);
  }, 16);
});

/* 渲染层仍会发 drag-move（用来判定"这是点击还是拖动"），位置交给上面的轮询，这里不重复设 */
ipcMain.on('drag-move', () => {});

ipcMain.on('drag-end', () => {
  dragOffset = null;
  if (dragTimer) { clearInterval(dragTimer); dragTimer = null; }
});

ipcMain.on('pet-glide', (_e, p) => {
  if (!p) return;
  glideBy(Math.round(p.dx || 0), Math.max(200, p.ms || 3000));
});

/* 渲染层一个小场景结束，或用户从菜单点"走两步" */
function triggerScene(name) {
  if (!win || win.isDestroyed()) return;
  log('main', 'triggerScene ' + name);
  if (win.isVisible() === false) win.show();
  win.webContents.send('pet-scene', name);
}

/* 渲染层实测完能力会报一次（缺帧时菜单要置灰，不能点了才发现没反应） */
ipcMain.on('pet-caps', (_e, caps) => {
  if (!caps || typeof caps !== 'object') return;
  petCaps = caps;
  refreshMenus();
});

ipcMain.on('ctx-menu', () => {
  if (!win) return;
  const menu = Menu.buildFromTemplate(actionItems().concat([
    { type: 'separator' },
    { label: '退出', click: () => app.quit() }
  ]));
  menu.popup({ window: win });
});

/* 右键菜单与托盘菜单共用同一套动作项，两边永远一致 */
function sceneItem(label, name, key) {
  const ok = !petCaps || petCaps[key] !== false;
  return {
    label: ok ? label : `${label}（这套图没有对应帧）`,
    enabled: ok,
    click: () => triggerScene(name)
  };
}

function actionItems() {
  const scaleItem = {
    label: '大小',
    submenu: [0.5, 0.8, 1, 1.2, 1.4].map(s => ({
      label: s === 1 ? `标准（${Math.round(WIN_W * s)}×${Math.round(WIN_H * s)}）` : `${Math.round(s * 100)}%`,
      type: 'radio',
      checked: Math.abs(winScale - s) < 0.01,
      click: () => setScale(s)
    }))
  };
  return [
    sceneItem('让她走两步', 'walk', 'walk'),
    sceneItem('跳个绳', 'rope', 'rope'),
    sceneItem('躲角落玩手机', 'phone', 'phone'),
    sceneItem('陪小蚂蚁玩', 'play', 'play'),
    { type: 'separator' },
    { label: '设置', submenu: [
      { label: '换形象（选生灵）', click: () => openSettings('creature') },
      { label: '上传素材（逐帧换图）', click: () => openSettings('frames') },
      { label: '改常用语（她说什么）', click: () => openSettings('lines') },
      { type: 'separator' },
      scaleItem,
      { label: '开机自启（登录 Windows 后自动出现）', type: 'checkbox', checked: getAutostart(), click: () => setAutostart(!getAutostart()) },
      { label: '钉在这个位置（不再走动）', type: 'checkbox', checked: pinned, click: () => setPinned(!pinned) },
      { label: '锁定（鼠标点不到，点击穿到底下）', type: 'checkbox', checked: locked, click: () => setLocked(!locked) }
    ] },
    { type: 'separator' },
    { label: '让她待着（隐藏 5 分钟）', click: () => { win.hide(); setTimeout(() => win && win.show(), 5 * 60 * 1000); } },
    { label: '回到右下角', click: () => {
      const area = screen.getPrimaryDisplay().workArea;
      const { w, h } = winSize();
      win.setPosition(area.x + area.width - w - 90, area.y + area.height - h - 6);
    } }
  ];
}

ipcMain.on('quit', () => app.quit());

function createTray() {
  /* 托盘图标单独一套：原来的整身立绘缩到 20px 只剩一团白，认不出是谁 */
  const iconPath = (currentIcon && (currentIcon.png || currentIcon.ico)) || undefined;
  const img = iconPath
    ? nativeImage.createFromPath(iconPath).resize({ width: 32, height: 32 })
    : nativeImage.createEmpty();
  tray = new Tray(img);
  tray.setToolTip('山海遇灵');
  tray.setContextMenu(buildTrayMenu());
}

function buildTrayMenu() {
  return Menu.buildFromTemplate([
    { label: '显示 / 隐藏', click: () => { if (!win) return; win.isVisible() ? win.hide() : win.show(); } },
    { type: 'separator' }
  ].concat(actionItems(), [
    { type: 'separator' },
    { label: '退出', click: () => app.quit() }
  ]));
}
/* 改了缩放/钉住要重建托盘菜单，否则勾选状态不同步 */
function refreshMenus() {
  if (tray) tray.setContextMenu(buildTrayMenu());
}

/* ---------------- 生灵包 IPC ---------------- */

ipcMain.handle('creature:get', () => currentPayload());
ipcMain.handle('creature:list', () => (registry ? registry.brief() : []));
ipcMain.handle('creature:select', (_e, id) => {
  const p = applyCreature(id, true);
  return p ? { ok: true, id: p.id } : { ok: false, error: '这个目录读不出来' };
});

ipcMain.handle('settings:state', () => settingsState());
ipcMain.handle('settings:select', (_e, id) => {
  const p = applyCreature(id, true);
  return p ? { ok: true, id: p.id, displayName: p.displayName } : { ok: false, error: '这个目录读不出来' };
});
ipcMain.handle('settings:save-lines', (_e, arg) => {
  if (!store || !arg || !arg.cid) return { ok: false, error: '参数不全' };
  const lines = (arg.lines || []).map(pack.normalizeLine).filter(l => l.i && l.t);
  store.setLines(arg.cid, lines);
  if (arg.cid === currentId && win && !win.isDestroyed()) {
    win.webContents.send('pet-lines', (currentPayload() || {}).lines || []);
  }
  notifySettings();
  return { ok: true, count: lines.length };
});
ipcMain.handle('settings:reset-lines', (_e, cid) => {
  if (!store || !cid) return { ok: false, error: '参数不全' };
  store.clearLines(cid);
  if (cid === currentId && win && !win.isDestroyed()) {
    win.webContents.send('pet-lines', (currentPayload() || {}).lines || []);
  }
  notifySettings();
  return { ok: true };
});
ipcMain.handle('settings:preview', (_e, text) => {
  if (!win || win.isDestroyed() || !text) return { ok: false };
  if (win.isVisible() === false) win.show();
  win.webContents.send('pet-preview', String(text).slice(0, 60));
  return { ok: true };
});
ipcMain.handle('settings:open-folder', (_e, which) => {
  if (!registry) return { ok: false };
  const target = which === 'builtin' ? registry.builtinRoot : registry.userRoot;
  try { fs.mkdirSync(registry.userRoot, { recursive: true }); } catch (e) {}
  shell.openPath(target);
  return { ok: true, path: target };
});

/* ---------------- 素材页：逐帧上传 ----------------
   一张图 = 一个动作帧。上传落在当前生灵目录的 frames/<帧名>.png|webp，
   并往 creature.json 的 frames.<帧名>.file 写显式绑定（比靠文件名猜稳），
   然后走 applyCreature 热切换：先加载完新帧再换，不会半新半旧。
   然后走 applyCreature 热切换：先加载完新帧再换，不会半新半旧。
   所有形象（含冉冉）都在生灵目录下、都可写；想留底就「复制为新形象」生成用户自定义N。 */

function creatureMeta(id) {
  if (!registry) return null;
  return registry.scanAll().find((c) => c.id === (id || currentId)) || null;
}

function patchManifestFrames(dir, name, spec) {
  const file = path.join(dir, 'creature.json');
  const cur = pack.readJson(file) || {};
  const frames = Object.assign({}, cur.frames || {});
  if (spec === null) delete frames[name];
  else {
    const prev = (frames[name] && typeof frames[name] === 'object') ? frames[name] : {};
    frames[name] = Object.assign({}, prev, spec);
  }
  cur.frames = frames;
  pack.writeJson(file, cur);
}

/* 四角必须透明：带白底 / 背景的图会连背景一起贴到桌面上 */
function cornersTransparent(img, size) {
  const bmp = img.toBitmap();                       /* BGRA */
  const alphaAt = (x, y) => bmp[(y * size.width + x) * 4 + 3];
  return [alphaAt(0, 0), alphaAt(size.width - 1, 0), alphaAt(0, size.height - 1), alphaAt(size.width - 1, size.height - 1)]
    .every((v) => v <= 8);
}

/* 新形象名：用户自定义1 / 用户自定义2 …（取第一个没被占用的号） */ipcMain.handle('settings:frames', () => {
  const meta = creatureMeta();
  if (!meta) return { ok: false, error: '读不到当前生灵' };
  const base = meta.size;
  const rows = pack.CANONICAL_FRAMES.map((name) => {
    const f = meta.frames[name];
    const size = f ? pack.imageSize(nativeImage, f.file) : null;
    return {
      name,
      has: !!f,
      rel: f ? f.rel : '',
      file: f ? path.basename(f.file) : '',
      url: f ? pack.buildAssetUrl(meta.id, meta.dir, f.rel, 'thumb') : '',
      size,
      mismatch: !!(f && base && size && (size.width !== base.w || size.height !== base.h))
    };
  });
  return {
    ok: true,
    id: meta.id,
    displayName: meta.displayName,
    dir: meta.dir,
    builtin: !!meta.builtin,
    size: base,
    rows,
    missing: meta.missing,
    caps: meta.caps
  };
});

/* 新形象名：用户自定义1 / 用户自定义2 …（取第一个没被占用的号） */
function nextCustomName() {
  let names = [];
  try {
    names = fs.readdirSync(registry.userRoot, { withFileTypes: true })
      .filter((e) => e.isDirectory()).map((e) => e.name);
  } catch (e) { /* 目录还没建：从 1 开始 */ }
  const used = new Set(names.map((n) => n.toLowerCase()));
  let n = 1;
  while (used.has(('用户自定义' + n).toLowerCase())) n++;
  return '用户自定义' + n;
}

/* 把当前这只整体复制成一只新形象（用户自定义N），落进同一个生灵目录 */
function doClone() {
  if (!registry) return { ok: false, error: '生灵注册表没建起来' };
  const meta = creatureMeta();
  if (!meta) return { ok: false, error: '读不到当前生灵' };

  const newId = nextCustomName();
  const newDir = path.join(registry.userRoot, newId);
  const srcManifest = meta.manifest || {};
  const manifest = Object.assign({}, srcManifest);
  try {
    fs.mkdirSync(path.join(newDir, 'frames'), { recursive: true });
    fs.mkdirSync(path.join(newDir, 'companion'), { recursive: true });

    /* 只搬“认过的帧”，中间产物（_raw / _matted）不带过去 */
    const frames = {};
    for (const [name, f] of Object.entries(meta.frames)) {
      const ext = (path.extname(f.file) || '.png').toLowerCase();
      const rel = `frames/${name}${ext}`;
      fs.copyFileSync(f.file, path.join(newDir, rel));
      const oldSpec = srcManifest.frames && srcManifest.frames[name];
      const spec = (oldSpec && typeof oldSpec === 'object') ? Object.assign({}, oldSpec) : {};
      spec.file = rel;
      frames[name] = spec;
    }

    manifest.id = newId;
    manifest.displayName = newId;
    manifest.frames = frames;

    if (meta.companion) {
      const rel = `companion/${path.basename(meta.companion.file)}`;
      fs.copyFileSync(meta.companion.file, path.join(newDir, rel));
      manifest.companion = Object.assign({}, srcManifest.companion || {}, { file: rel });
    }

    for (const p of [meta.icon.ico, meta.icon.png]) {
      if (!p) continue;
      try { fs.copyFileSync(p, path.join(newDir, path.basename(p))); } catch (e) { /* 图标缺了不影响主体 */ }
    }

    const linesFile = path.join(meta.dir, srcManifest.lines || 'lines.json');
    if (fs.existsSync(linesFile)) {
      try { fs.copyFileSync(linesFile, path.join(newDir, 'lines.json')); } catch (e) {}
    }

    pack.writeJson(path.join(newDir, 'creature.json'), manifest);
  } catch (e) {
    log('main', 'clone fail ' + e.message);
    return { ok: false, error: '复制失败：' + e.message };
  }

  const p = applyCreature(newId, true);
  log('main', `clone ${meta.id} -> ${newId} frames=${Object.keys(meta.frames).length}`);
  return { ok: true, id: newId, dir: newDir, displayName: p ? p.displayName : manifest.displayName };
}
ipcMain.handle('settings:clone', () => doClone());

ipcMain.handle('settings:frame-upload', async (_e, name) => {
  if (!pack.CANONICAL_FRAMES.includes(name)) return { ok: false, error: '未知帧名' };
  const meta = creatureMeta();
  if (!meta) return { ok: false, error: '读不到当前生灵' };

  const parent = (settingsWin && !settingsWin.isDestroyed()) ? settingsWin
    : (win && !win.isDestroyed() ? win : null);
  const picked = await dialog.showOpenDialog(parent, {
    title: `给「${name}」选一张图`,
    buttonLabel: '用这张',
    filters: [{ name: '透明底图片', extensions: ['png', 'webp'] }],
    properties: ['openFile']
  });
  if (picked.canceled || !picked.filePaths.length) return { ok: false, canceled: true };
  return applyFrameUpload(name, picked.filePaths[0]);
});

/* 校验 → 落盘 → 写显式绑定 → 热切换。选文件在 handler 里做，这里只认路径（自测钩子也走这段） */
async function applyFrameUpload(name, src) {
  const meta = creatureMeta();
  if (!meta) return { ok: false, error: '读不到当前生灵' };

  const ext = path.extname(src).toLowerCase();
  if (!/^\.(png|webp)$/.test(ext)) {
    return { ok: false, error: '只收 PNG / WebP：JPG 没有透明通道，贴到桌面上会带一块底色' };
  }
  const img = nativeImage.createFromPath(src);
  if (!img || img.isEmpty()) return { ok: false, error: '这个文件读不出图像，可能已经损坏' };

  const size = img.getSize();
  const base = meta.size;                       /* {w,h}，见 describe() 里的 size */
  if (base && (size.width !== base.w || size.height !== base.h)) {
    /* 尺寸不一致换帧会跳大小，挡在入口比事后修便宜 */
    return { ok: false, error: `尺寸不对：这张是 ${size.width}×${size.height}，这套图统一是 ${base.w}×${base.h}（先等比缩放到这个尺寸再传）` };
  }
  if (!cornersTransparent(img, size)) {
    return { ok: false, error: '底不透明：四角必须是透明像素；带白底 / 背景的图会连背景一起贴到桌面上' };
  }

  const rel = `frames/${name}${ext}`;
  try {
    fs.mkdirSync(path.join(meta.dir, 'frames'), { recursive: true });
    fs.copyFileSync(src, path.join(meta.dir, rel));
  } catch (e) {
    return { ok: false, error: '写文件失败：' + e.message };
  }
  patchManifestFrames(meta.dir, name, { file: rel });

  const p = applyCreature(currentId, false);
  log('main', `frame upload ${meta.id}/${name} <- ${path.basename(src)} ${size.width}x${size.height}`);
  return { ok: true, rel, file: path.basename(src), applied: !!p };
}

ipcMain.handle('settings:frame-clear', (_e, name) => {
  if (!pack.CANONICAL_FRAMES.includes(name)) return { ok: false, error: '未知帧名' };
  const meta = creatureMeta();
  if (!meta) return { ok: false, error: '读不到当前生灵' };

  patchManifestFrames(meta.dir, name, null);
  /* 只删我们自己落盘的那一份；用户手放的素材一律不碰 */
  for (const ext of ['.png', '.webp']) {
    const p = path.join(meta.dir, 'frames', name + ext);
    try { if (fs.existsSync(p)) fs.unlinkSync(p); } catch (e) { /* 删不掉就留着，绑定已经解除 */ }
  }

  const p = applyCreature(currentId, false);
  const after = creatureMeta();
  const still = !!(after && after.frames[name]);
  return {
    ok: true,
    applied: !!p,
    still,
    note: still ? `这张来自目录里的 ${(after.frames[name] || {}).rel}，只在清单里解除了绑定；要彻底去掉请在文件夹里删掉那个文件` : ''
  };
});

/* ---------------- 生灵图片协议 ----------------
   pet://creature/<id>/<相对路径>?v=<mtime>   原图
   pet://thumb/<id>/<相对路径>?v=<mtime>      128px 预览（设置页素材表用）
   id 放路径不放 host：host 会被 URL 解析强制小写，中文目录名还会被 punycode。
   只吐注册表认过的目录里的图片，且挡掉 .. 逃逸。 */

/* 25 张 900×1360 全进渲染内存没必要，现缩现给，按 file|mtime|size 缓存 */
const THUMB_CACHE = new Map();
function thumbOf(file) {
  let st;
  try { st = fs.statSync(file); } catch (e) { return null; }
  const key = `${file}|${Math.round(st.mtimeMs)}|${st.size}`;
  if (THUMB_CACHE.has(key)) return THUMB_CACHE.get(key);
  let buf = null;
  try {
    const img = nativeImage.createFromPath(file);
    if (img && !img.isEmpty()) buf = img.resize({ height: 128 }).toPNG();
  } catch (e) { buf = null; }
  if (THUMB_CACHE.size > 80) THUMB_CACHE.clear();
  THUMB_CACHE.set(key, buf);
  return buf;
}

function servePetAsset(req) {
  let u;
  try { u = new URL(req.url); } catch (e) { return new Response('bad url', { status: 400 }); }
  const segs = u.pathname.split('/').filter(Boolean);
  const isThumb = u.hostname === 'thumb';
  if (u.hostname !== 'creature' && !isThumb) return new Response('bad path', { status: 400 });
  if (segs.length < 2) return new Response('bad path', { status: 400 });
  const id = decodeURIComponent(segs[0]);
  const rel = segs.slice(1).map(decodeURIComponent).join('/');
  const file = registry ? registry.resolve(id, rel) : null;
  if (!file) return new Response('not found', { status: 404 });
  try {
    if (isThumb) {
      const thumb = thumbOf(file);
      if (!thumb) return new Response('not found', { status: 404 });
      return new Response(thumb, {
        headers: { 'Content-Type': 'image/png', 'Cache-Control': 'no-cache' }
      });
    }
    const buf = fs.readFileSync(file);
    const ext = path.extname(file).toLowerCase();
    return new Response(buf, {
      headers: {
        'Content-Type': pack.MIME[ext] || 'application/octet-stream',
        'Cache-Control': 'no-cache'
      }
    });
  } catch (e) {
    return new Response('read fail', { status: 500 });
  }
}

/* 自定义协议必须在 app ready 之前登记权限，否则渲染层拿不到 fetch/图片加载权限 */
protocol.registerSchemesAsPrivileged([{
  scheme: 'pet',
  privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true }
}]);

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  /* 任务栏/托盘按这个 ID 归组，否则 Windows 会给它挂一个默认的 Electron 图标 */
  app.setAppUserModelId('com.shanhaiyuling');
  app.on('second-instance', () => { if (win) win.show(); });
  app.whenReady().then(async () => {
    /* 素材是就地替换文件的（同名），Chromium 会拿磁盘缓存里那份，
       结果就是"图换了、窗口里还是旧的"。每次启动先清一次缓存 */
    try { await session.defaultSession.clearCache(); } catch (e) { console.log('clearCache fail', e.message); }

    /* 生灵包：只有「生灵目录」一个根（%APPDATA%/山海遇灵/creatures/），冉冉首次启动从 assets 铺种子 */
    registry = pack.createRegistry({
      appDir: app.getAppPath(),
      userDataDir: app.getPath('userData'),
      nativeImage,
      log: (m) => log('pack', m)
    });
    const seeded = registry.ensureUserCreatureDir();
    store = createStore(path.join(app.getPath('userData'), 'settings.json'), (m) => log('settings', m));
    if (seeded) log('main', 'seeded builtin creature into 生灵目录');

    protocol.handle('pet', servePetAsset);

    /* 选谁：PET_CREATURE=<id> 用于验收指定生灵；否则设置里记的那个 → 第一个能用的（通常是冉冉） */
    const list = registry.brief();
    const forced = process.env.PET_CREATURE;
    const wanted = (forced && list.some(c => c.id === forced && c.status !== 'broken')) ? forced : store.getCreatureId();
    const pick = (wanted && list.some(c => c.id === wanted && c.status !== 'broken')) ? wanted
      : (list.find(c => c.status !== 'broken') || {}).id;
    if (pick) {
      /* 存的那个 id 已经不在了（删了目录 / 从旧版 ranran-mine 迁移过来）：把落地的那只记下来，别每次启动都回落 */
      if (!forced && store.getCreatureId() !== pick) store.setCreatureId(pick);
      prepareCreature(pick);
    }

    /* 验收用钩子，正式运行不设这些环境变量就不会进：
       PET_OPEN_SETTINGS=1 开机弹设置窗；PET_SHOT_PET/PET_SHOT_SETTINGS 给路径就截图 */
    if (process.env.PET_OPEN_SETTINGS) {
      const tab = (process.env.PET_OPEN_SETTINGS === 'lines' || process.env.PET_OPEN_SETTINGS === 'frames')
        ? process.env.PET_OPEN_SETTINGS : 'creature';
      setTimeout(() => openSettings(tab), 1200);
    }
    if (process.env.PET_SHOT_PET) setTimeout(async () => {
      try {
        const b = win.getContentBounds();
        const x = Math.round(b.width / 2);
        const y = Math.round(b.height * 0.6);
        win.webContents.sendInputEvent({ type: 'mouseDown', x, y, button: 'left', clickCount: 1 });
        win.webContents.sendInputEvent({ type: 'mouseUp', x, y, button: 'left', clickCount: 1 });
        await new Promise(r => setTimeout(r, 1500));
        const img = await win.webContents.capturePage();
        fs.writeFileSync(process.env.PET_SHOT_PET, img.toPNG());
        log('debug', 'pet shot saved');
      } catch (e) { log('debug', 'pet shot fail ' + e); }
    }, Number(process.env.PET_SHOT_PET_DELAY || 2500));
    if (process.env.PET_SWITCH) setTimeout(() => {
      try { applyCreature(process.env.PET_SWITCH, false); log('debug', 'switch to ' + process.env.PET_SWITCH); }
      catch (e) { log('debug', 'switch fail ' + e); }
    }, 5000);
    /* 素材页自测钩子（验收用，不设环境变量就不跑）：
       PET_FRAME_CLONE=1             启动即把当前形象复制成「用户自定义N」
       PET_FRAME_UPLOAD=<帧名>=<图>   跳过选文件对话框，直接走一遍上传校验 */
    if (process.env.PET_FRAME_CLONE) setTimeout(() => {
      try { log('debug', 'clone ' + JSON.stringify(doClone())); }
      catch (e) { log('debug', 'clone fail ' + e); }
    }, 1500);
    if (process.env.PET_FRAME_UPLOAD) setTimeout(async () => {
      const raw = process.env.PET_FRAME_UPLOAD;
      const at = raw.indexOf('=');
      try { log('debug', 'upload ' + JSON.stringify(await applyFrameUpload(raw.slice(0, at), raw.slice(at + 1)))); }
      catch (e) { log('debug', 'upload fail ' + e); }
    }, 2500);
    if (process.env.PET_SHOT_SETTINGS) setTimeout(async () => {
      try {
        const scroll = Number(process.env.PET_SHOT_SCROLL || 0);
        if (scroll) {
          await settingsWin.webContents.executeJavaScript(`document.querySelector('main').scrollTop = ${scroll}`);
          await new Promise(r => setTimeout(r, 300));
        }
        const img = await settingsWin.webContents.capturePage();
        fs.writeFileSync(process.env.PET_SHOT_SETTINGS, img.toPNG());
        log('debug', 'settings shot saved');
      } catch (e) { log('debug', 'settings shot fail ' + e); }
    }, 4000);
    log('main', `boot creatures=${list.map(c => c.id + ':' + c.status).join(',')} current=${currentId}`);

    createWindow();
    createTray();
    /* 开着自启的，每次启动把注册表项对齐到当前这份 exe（换目录重装后不用重新勾） */
    log('main', 'syncAutostartPath on boot');
    syncAutostartPath();
    /* 调试/无人值守：PET_AUTOSTART=1 启动即打开自启，=0 即关闭（用来验注册表链路，省得点菜单） */
    if (process.env.PET_AUTOSTART === '1' || process.env.PET_AUTOSTART === '0') {
      setTimeout(() => setAutostart(process.env.PET_AUTOSTART === '1'), 1000);
    }
    /* 快捷键换动作：Ctrl+Alt+1 走两步 / 2 跳绳 / 3 躲角落 / 4 陪蚂蚁 / 5 锁定开关 */
    const HOTKEYS = [
      ['CommandOrControl+Alt+1', 'walk'],
      ['CommandOrControl+Alt+2', 'rope'],
      ['CommandOrControl+Alt+3', 'phone'],
      ['CommandOrControl+Alt+4', 'play']
    ];
    for (const [accel, scene] of HOTKEYS) {
      let ok = false;
      try { ok = globalShortcut.register(accel, () => triggerScene(scene)); } catch (e) {}
      log('main', 'hotkey ' + accel + '=' + ok);
    }
    /* 锁定后窗口本身点不到，必须留一个键盘出口，否则只能靠托盘解锁 */
    {
      let ok = false;
      try { ok = globalShortcut.register('CommandOrControl+Alt+5', () => setLocked(!locked)); } catch (e) {}
      log('main', 'hotkey Ctrl+Alt+5=' + ok);
    }
    if (process.env.PET_LOCK === '1') setTimeout(() => setLocked(true), 1200);
    setInterval(pollCursor, 33);
    app.on('activate', () => { if (!win) createWindow(); });
  });
  app.on('will-quit', () => globalShortcut.unregisterAll());
  app.on('window-all-closed', () => {
    /* 设置窗口关掉不该带着桌宠一起退：桌宠窗口全没了才退 */
    if (!win) app.quit();
  });
}
