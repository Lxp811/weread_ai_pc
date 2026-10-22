@echo off
setlocal
title 微信读书答题助手
cd /d "%~dp0"
set "PY="

set "CAND=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe"
if exist "%CAND%" (
  "%CAND%" -c "import PIL" >nul 2>nul
  if not errorlevel 1 set "PY=%CAND%"
)

if not defined PY call :try_local
if not defined PY call :try_path

if not defined PY (
  echo.
  echo 没有找到可用的 Python：需要 Python 3.10+ ，并且装了 Pillow。
  echo 安装方法：
  echo   1^) 安装 Python 3.10 或更高版本，勾选 Add python.exe to PATH
  echo   2^) 打开命令行执行：pip install pillow
  echo.
  pause
  exit /b 1
)

start "" "%PY%" "%~dp0weread_helper.py"
exit /b 0

:try_local
for %%V in (314 313 312 311 310) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe" -c "import PIL" >nul 2>nul
    if not errorlevel 1 set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe"
  )
)
exit /b 0

:try_path
where pythonw >nul 2>nul
if errorlevel 1 exit /b 0
pythonw -c "import PIL" >nul 2>nul
if errorlevel 1 exit /b 0
set "PY=pythonw"
exit /b 0
