# 贡献指南

这是个个人项目，代码集中在 `desktop-shell/`（Electron 过渡壳）与 `tools/`（构建/素材脚本）。动手前先看根 [README.md](README.md) 和 [desktop-shell/README.md](desktop-shell/README.md)，那里写了行为真值与调试开关。

## 改代码

只改渲染层（`desktop-shell/desk-pet.html`、`creature-pack.js`、`lib/*.js`）时，用浏览器直接打开 `desktop-shell/desk-pet.html` 就能看效果，`#s=walk`、`#s=rope`、`#g=footSwing`、`#near` 这些 hash 见根 README 的「调试开关」一节。

提 PR 前跑一遍单元测试（纯 Node，不需要图形界面）：

```powershell
node desktop-shell/tests/unit-manifest.js
node desktop-shell/tests/unit-pet-state.js
```

动了 Electron 主进程（窗口、鼠标穿透、托盘、开机自启）的，再跑一次冒烟自检：

```powershell
desktop-shell\node_modules\electron\dist\electron.exe desktop-shell\tests\smoke-creature.js
```

结果写在 `desktop-shell\tests\_smoke.json`（Electron 是 GUI 子系统，控制台常常拿不到输出）。

## 改素材

- 先读 [docs/生灵包规范.md](docs/生灵包规范.md)：目录结构、25 个帧名、`creature.json` 字段、画图硬要求（透明底、同一套图宽高完全一致、站姿与走路帧脚底同一条基线）。
- 批量核对用 `python tools/check_creature.py <生灵目录>`，`--scan` 一次扫内置与自定义生灵；命令行核对帧轨道用 `node desktop-shell/tools/validate-creature.js <生灵目录>`。
- 角色形象是对外的约定（刺绣兔耳帽、白毛绒玩偶服、粉裙、白靴、珊瑚粉小蚂蚁）：不怀抱布偶蚂蚁、不加金冠、帽圈不画兔脸、不加任何挂件。

## 提 Issue

- 说明 Windows 版本，以及跑的是 `npx electron .` 还是打包版。
- 行为问题附上 `desktop-shell\_scene.log` 的相关片段（`[main] triggerScene` / `[renderer] [scene] recv` 两行最关键）。
- 素材问题附一张图 + 期望效果，别只描述。

## 许可证

提交代码或素材即表示同意以 **MIT** 许可证发布，见 [LICENSE](LICENSE)。
