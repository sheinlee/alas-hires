# alas_hires

Alas 高分辨率补丁的运行文件夹。说明、安装方法和许可证见 <https://github.com/sheinlee/alas-hires>。

| 文件 | 用途 |
|---|---|
| `run_alas.py` | 先装补丁，再执行 `AzurLaneAutoScript(<配置名>).loop()` |
| `alas_hires.py` | 补丁本体 |
| `alt/` | 4K 版文字模板和 `manifest.json`。原模板被 Alas 更新改动后，对应的 4K 版自动停用 |
| `make_alt.py` | 生成和检查 4K 版模板（在 AzurLaneAutoScript 文件夹里用 `toolkit\python.exe` 运行） |
| `runs/<时间>/` | 运行时生成：高分辨率下差一点没认出的按钮（`near_miss.csv`、裁图、当时的 720p 画面） |

所有路径都相对于本文件夹，可以连同 `用补丁跑Alas.bat` 一起放在 AzurLaneAutoScript 旁边的任意位置。
