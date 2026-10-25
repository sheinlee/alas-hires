# alas-hires · Alas 高分辨率补丁

[English](README.en.md)

**High-resolution patch for [Alas](https://github.com/LmeSzinc/AzurLaneAutoScript).** 让 Alas（碧蓝航线脚本）在 2K/4K 等 16:9 的模拟器画面下运行，不用为了跑脚本把模拟器切回 1280x720。

Alas 官方只支持 1280x720，作者在 [#4177](https://github.com/LmeSzinc/AzurLaneAutoScript/issues/4177) 说明过不打算支持其他分辨率。**本项目是第三方的非官方补丁，与 Alas 开发组无关。**

## 原理

补丁在运行时加载，不改 Alas 的文件和设置，Alas 自动更新后照常可用。画面是 1280x720 时，所有改动都不起作用，和原版完全一样。

- **截图**：先缩回 1280x720 再交给 Alas，Alas 的模板、颜色判断、OCR 和海图识别全部照常工作。
- **点击**：ADB、uiautomator2 和 MuMu 截图接口（nemu_ipc）这几种点击方式用的是设备像素坐标，补丁会按比例放大。minitouch 和 MaaTouch 本来就会自己换算，不用改。
- **控件树坐标**（国服登录协议弹窗等）按比例缩回 720p。
- **分辨率检查**：放宽为接受任意 16:9 画面。
- **小号文字**：游戏在高分辨率下渲染的小号文字笔画更细、更亮，缩回 720p 后和原模板对不上，比如"周回模式"从 1.00 掉到 0.69。补丁给这类按钮另配了一张从 4K 画面切出来的模板，原模板认不出时再试这一张。
- **近似匹配记录**：高分辨率下，差一点就过阈值的匹配会把截图存到 `alas_hires\runs\`，方便补模板。
- **截图方式**：在 MuMu 上，如果 Alas 设置的截图方式是 uiautomator2、ADB 这类慢的，这次运行会改用 nemu_ipc（4K 下一张约 40 毫秒，adb 约 1.2 秒）。不改 Alas 的设置。

## 实测

环境：MuMu 模拟器 12，3840x2160；国服；Alas 2026-10 版；点击方式 minitouch。

- **截图打分**：两轮各截约 140 张，720p 原生画面和 4K 缩回 720p 后的画面一一对比。720p 下明确认出的 2716 处按钮里，4K 下认不出的有 12 处。逐张看图后，真正因渲染不同而认不出的只有文字按钮，已配 4K 版模板；OCR 读数（石油、金币、指挥喵等级和容量、大世界行动力、演习次数、大舰队兑换次数、后宅食物）两种画面完全一致。大世界海图识别（格子、舰队位置、世界地图定位）也一致。
- **实跑**：10/20 起每天用补丁跑日常，覆盖委托、战术学院、科研、后宅、大舰队、领奖励、商店、主线、困难、活动、每日、认知觉醒、信标、大世界探索、隐秘/深渊/塞壬要塞等。补丁本身没有出问题；陆续碰到的都是某个文字按钮在 4K 下认不出，补一张模板即可（见"已知限制"）。期间遇到一次大世界拖地图死循环，是 Alas 原有的问题 [#5360](https://github.com/LmeSzinc/AzurLaneAutoScript/issues/5360)，1280x720 下也会出现。

## 安装

1. 到 [Releases](../../releases) 下载 `alas-hires-v*.zip`，解压到 **AzurLaneAutoScript 所在的文件夹**，也就是和它同级：

   ```text
   AlasApp\
   ├─ AzurLaneAutoScript\     ← Alas
   ├─ alas_hires\             ← 补丁
   └─ AlasHires.bat
   ```

2. 把模拟器分辨率设成 16:9，例如 3840x2160、2560x1440 或 1920x1080，重启模拟器。
3. 双击 `AlasHires.bat`，打开 AlasHires 窗口，选配置，点"启动"。
4. 窗口里"模拟器画面"一栏显示 `3840x2160 ×3` 之类，或者日志里有下面这行，就说明补丁生效了：

   ```text
   ALAS-HIRES: device scale 3.000 (3840x2160 -> 1280x720)
   ```

用 [daily-hub](https://github.com/sheinlee/daily-hub) 调度 Alas 时，在碧蓝航线的"自定义启动脚本"里填 `..\alas_hires\run_alas.py`（相对于 AzurLaneAutoScript 文件夹）。daily-hub 0.1.2 起不会把空闲的 AlasHires 窗口当成"Alas 已在运行"。

要卸载，删掉 `alas_hires\` 和 `AlasHires.bat` 即可，改回用 Alas 自己的界面启动。

## AlasHires 窗口

- 用 Alas 自带的 Python 运行，界面显示在 Edge 的独立窗口里（本机 127.0.0.1 上的小服务，不联网；没有 Edge 时用默认浏览器打开）。
- **启动 / 停止**：Alas 作为独立进程运行，关掉窗口不会停止它，再双击 `AlasHires.bat` 就能看到正在跑的那个。Alas 自己的界面、daily-hub 或控制台已经在跑调度时，"启动"不可用；停止别处启动的 Alas 前会先确认。
- **调度**：和 Alas 总览页一样的"运行中 / 队列中 / 等待中"，从 Alas 的配置、优先级表和翻译文件现读，Alas 更新后自动跟上。改任务设置仍在 Alas 自己的界面里改，两个窗口可以同时开着。
- **状态**：当前任务、模拟器画面和缩放倍数、截图方式、4K 版模板数、近似匹配和警告/错误数；日志可以只看重点。
- 不想用窗口的话，在 AzurLaneAutoScript 文件夹里运行 `toolkit\python.exe ..\alas_hires\run_alas.py alas` 效果相同。

## 已知限制

- **4K 版文字模板只做了国服**，共 12 张：周回模式（2 张）、自律寻敌，普通、安全、隐秘、深渊海域，塞壬要塞，商店左栏"补给商店"，私人宿舍标题，船坞为空，每日任务"快速挑战"。**档案海域还没有。** 其他服务器，或者游戏更新后文字变了，对应按钮可能认不出，需要自己补（见下）。实测下来，4K 下认不出的几乎都是文字按钮，每新跑一类任务就可能碰到一个；Alas 卡住或请求人工接管时，先看 `alas_hires\runs\` 里的近似匹配记录。
- 只在 MuMu 12 的 3840x2160 下实测过。2560x1440、1920x1080 用同一套缩放，但文字模板是从 4K 画面切的，在这两个分辨率下不一定对得上。
- 在 Alas 自己的界面里启动的调度不经过补丁，高分辨率下仍会停在 "Resolution not supported"。

## 补 4K 版文字模板

实跑中某个按钮认不出时，到 `alas_hires\runs\<时间>\near\` 里找它的截图，然后在 AzurLaneAutoScript 文件夹里运行：

```bat
toolkit\python.exe ..\alas_hires\make_alt.py add --button os.ZONE_ARCHIVE --crop ..\alas_hires\runs\<时间>\near\<文件>.png
toolkit\python.exe ..\alas_hires\make_alt.py add --button handler.CLEAR_MODE_TITLE --shot <高分辨率截图.png>
toolkit\python.exe ..\alas_hires\make_alt.py check --shots <一批高分辨率截图的文件夹>
```

- 按钮名是 `模块.按钮`，对应 Alas `module/<模块>/assets.py` 里的名字。
- 其他服务器要在命令前加 `--server en`、`jp` 或 `tw`。
- 运行中的 Alas 每 10 秒检查一次模板清单，新加的模板不用重启就能用上。
- 原模板被 Alas 更新改动后，对应的 4K 版会自动停用，日志里会提示。
- 文字标题在不同底色上的渲染会有差别（活动图的"周回模式"用主线图切的 4K 版模板只有 0.849）。`make_alt.py similarity --button handler.CLEAR_MODE_TITLE 0.8` 只给这个按钮的 4K 版模板降低阈值，之后用 `check` 确认不会误认；阈值不会高于 Alas 自己的。
- 近似匹配的日志和 `near_miss.csv` 里同时有原模板和 4K 版模板的分数。

环境变量：

- `ALAS_HIRES_SCREENSHOT=keep`：不自动更换截图方式。
- `ALAS_HIRES_RUNS=<目录>`：近似匹配记录存到别处。

## 注意

- **这是非官方补丁。用补丁时遇到的问题，请不要提交到 Alas 的仓库或群里。** 先在不用补丁、模拟器 1280x720 的条件下确认能复现，再按 Alas 的要求反馈。
- [Alas](https://github.com/LmeSzinc/AzurLaneAutoScript) 是 LmeSzinc 等人开发的免费开源软件（GPL-3.0）。使用 Alas 请遵守 [Alas 社区准则](https://github.com/LmeSzinc/AzurLaneAutoScript/discussions/1416)。
- 自动化脚本可能违反游戏的用户协议，请自行承担风险。本项目与游戏厂商无关。
- `alas_hires\alt\` 里的模板是游戏界面文字的截图，版权归游戏厂商所有。

## 许可证

[GPL-3.0](LICENSE)。补丁在运行时导入并替换 Alas 的函数，属于 Alas 的衍生作品，所以和 Alas 一样使用 GPL-3.0。

Copyright (C) 2026 sheinlee
