# 重新打包 exe（需要 Python 3.10+，第一次会联网装 PyInstaller）
# 用法：在 weread_pc 目录下执行  powershell -ExecutionPolicy Bypass -File .\打包exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    $candidates = @(
        "$env:USERPROFILE\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    )
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $found) { throw "没找到 Python，请先安装 Python 3.10+ 并勾选 Add to PATH" }
    $python = $found
}

& $python -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 安装失败" }

Write-Host "==> 单文件版" -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "微信读书答题助手" --icon "app.ico" `
    --distpath dist --workpath ".build\pj_onefile" --specpath .build `
    weread_helper.py

Write-Host "==> 便携文件夹版" -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm --clean --onedir --windowed `
    --name "微信读书答题助手" --icon "app.ico" `
    --distpath ".build\portable" --workpath ".build\pj_onedir" --specpath .build `
    weread_helper.py

$zip = "dist\微信读书答题助手-便携版.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path ".build\portable\微信读书答题助手" -DestinationPath $zip

Get-ChildItem dist | Select-Object Name, @{n="MB";e={[math]::Round($_.Length/1MB,1)}}
Write-Host "完成。产物在 dist\" -ForegroundColor Green
