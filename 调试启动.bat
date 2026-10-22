@echo off
setlocal
title 微信读书答题助手（调试模式）
cd /d "%~dp0"
echo 调试模式：出错信息会显示在这个窗口里。
echo 关闭本窗口即退出程序。
echo.

set "PY="
set "CAND=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if exist "%CAND%" (
  "%CAND%" -c "import PIL" >nul 2>nul
  if not errorlevel 1 set "PY=%CAND%"
)
if not defined PY (
  for %%V in (314 313 312 311 310) do (
    if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
      "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import PIL" >nul 2>nul
      if not errorlevel 1 set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    )
  )
)
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import PIL" >nul 2>nul
    if not errorlevel 1 set "PY=python"
  )
)
if not defined PY (
  echo 没有找到带 Pillow 的 Python，先执行: pip install pillow
  pause
  exit /b 1
)

"%PY%" "%~dp0weread_helper.py"
echo.
echo 程序已退出，退出码 %errorlevel%
pause
