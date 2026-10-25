@echo off
chcp 65001 >nul
rem ============================================================
rem  AlasHires：带高分辨率补丁启动、停止和查看 Alas（窗口用 Edge 打开）。
rem  路径都相对于本文件：.\AzurLaneAutoScript 是 Alas，.\alas_hires 是补丁。
rem  用 Alas 自带的 pythonw.exe 运行，不留控制台；关掉窗口不会停止 Alas。
rem ============================================================
set "ROOT=%~dp0"
if not exist "%ROOT%AzurLaneAutoScript\toolkit\pythonw.exe" (
  echo [错误] 找不到 %ROOT%AzurLaneAutoScript\toolkit\pythonw.exe
  pause
  exit /b 2
)
if not exist "%ROOT%alas_hires\alashires.pyw" (
  echo [错误] 找不到 %ROOT%alas_hires\alashires.pyw
  pause
  exit /b 2
)
start "" "%ROOT%AzurLaneAutoScript\toolkit\pythonw.exe" "%ROOT%alas_hires\alashires.pyw"
