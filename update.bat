@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   Proxy 节点订阅 - 一键更新
echo ============================================================
where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] 找不到 python 命令，请确认 Python 已安装并加入 PATH
    echo.
    pause
    exit /b 1
)
python update.py %*
set RC=%errorlevel%
echo.
if "%RC%"=="0" (
    echo 全部完成，可以关闭本窗口。
) else (
    echo 执行失败（退出码 %RC%），请查看上面提示。
)
echo.
pause
