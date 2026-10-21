@echo off
chcp 65001 >nul
setlocal
title Alas（高分辨率补丁）- Ctrl+C 停止

rem ============================================================
rem  用途：带高分辨率补丁运行 Alas（模拟器 16:9、高于 1280x720 时用；1280x720 下补丁不起作用）。
rem  路径都相对于本文件：.\AzurLaneAutoScript 是 Alas，.\alas_hires 是补丁。
rem  用法：双击 = 跑配置 alas；命令行里可以带配置名，例如：用补丁跑Alas.bat alas
rem ============================================================

set "ROOT=%~dp0"
set "ALAS=%ROOT%AzurLaneAutoScript"
set "CFG=%~1"
if "%CFG%"=="" set "CFG=alas"
set "PYTHONIOENCODING=utf-8"

if not exist "%ALAS%\toolkit\python.exe" (
  echo [错误] 找不到 %ALAS%\toolkit\python.exe
  pause
  exit /b 2
)
if not exist "%ROOT%alas_hires\run_alas.py" (
  echo [错误] 找不到 %ROOT%alas_hires\run_alas.py
  pause
  exit /b 2
)

echo 先确认 Alas 界面和总控都没在跑碧蓝航线。
echo 配置：%CFG%
echo 差一点没认出的按钮会存到 %ROOT%alas_hires\runs\
echo.
cd /d "%ALAS%"
"%ALAS%\toolkit\python.exe" "%ROOT%alas_hires\run_alas.py" %CFG%
echo.
echo Alas 已退出。
pause
endlocal
