@echo off
chcp 65001 >nul
title Deep Fusion - Proxy Auto Setup

echo ============================================
echo  Deep Fusion Proxy 自动配置工具
echo ============================================
echo.

set PORTS=7897 7890 7891 7892 10809 10810 10811 8080 3128
set FOUND_PORT=

for %%p in (%PORTS%) do (
    netstat -ano | findstr /C:":%%p " >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] 发现代理端口: %%p
        set FOUND_PORT=%%p
        goto :SET_PROXY
    )
)

if "%FOUND_PORT%"=="" (
    echo [WARN] 未发现常见代理端口。
    echo [INFO] 请手动设置: set HTTP_PROXY=http://127.0.0.1:你的端口
    pause
    exit /b 1
)

:SET_PROXY
setx HTTP_PROXY "http://127.0.0.1:%FOUND_PORT%" >nul
setx HTTPS_PROXY "http://127.0.0.1:%FOUND_PORT%" >nul
setx NO_PROXY "localhost,127.0.0.1,192.168.*.*,10.*,*.local" >nul
echo [OK] 环境变量已设置 (端口 %FOUND_PORT%)
echo [INFO] 请重启终端或运行下面命令使新环境变量生效:
echo.
echo     set HTTP_PROXY=http://127.0.0.1:%FOUND_PORT%
echo     set HTTPS_PROXY=http://127.0.0.1:%FOUND_PORT%
echo.
echo [INFO] 验证:
echo     echo %%HTTP_PROXY%%
echo.
pause
