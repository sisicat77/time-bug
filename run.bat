@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo.
    echo 没有找到 Python。请先安装 Python 3.9+：
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
  )
  set "PY=py -3"
)

echo.
echo 1/2  跑实验，生成三张图 ...
%PY% demo.py
if errorlevel 1 (
  echo.
  echo 生成失败。请把上面的错误信息发给 AI。
  pause
  exit /b 1
)

echo.
echo 2/2  生成阅读页面 ...
%PY% build_site.py
if errorlevel 1 (
  echo.
  echo 页面生成失败。请把上面的错误信息发给 AI。
  pause
  exit /b 1
)

echo.
echo 完成。正在打开 index.html ...
start "" "index.html"
pause
