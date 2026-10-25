# alas_hires

Alas 高分辨率补丁的运行文件夹。说明、安装方法和许可证见 <https://github.com/sheinlee/alas-hires>。

| 文件 | 用途 |
|---|---|
| `run_alas.py` | 先装补丁，再执行 `AzurLaneAutoScript(<配置名>).loop()` |
| `alas_hires.py` | 补丁本体 |
| `alashires.pyw`、`alashires_ui.html` | AlasHires 窗口：选配置、启动和停止 Alas，看调度队列、运行状态和日志。只用 Alas 自带 python 的标准库和 psutil。文件名别改：[daily-hub](https://github.com/sheinlee/daily-hub) 靠 `alashires.pyw` 认出它 |
| `alashires.json` | AlasHires 记住的配置名和它上次启动的 Alas（运行时生成） |
| `alt/` | 4K 版文字模板和 `manifest.json`。原模板被 Alas 更新改动后，对应的 4K 版自动停用；运行中的 Alas 每 10 秒检查一次清单 |
| `make_alt.py` | 生成和检查 4K 版模板（在 AzurLaneAutoScript 文件夹里用 `toolkit\python.exe` 运行） |
| `runs/<时间>/` | 运行时生成：高分辨率下差一点没认出的按钮（`near_miss.csv`、裁图、当时的 720p 画面），用来补模板 |
| `runs/console-<时间>.log` | AlasHires 启动的 Alas 的控制台输出（保留最近 20 个），Alas 写日志之前就崩溃时看这里 |

所有路径都相对于本文件夹，可以连同 `AlasHires.bat` 一起放在 AzurLaneAutoScript 旁边的任意位置。
