# Builds build\app : embedded Python + Forja3D + dependencies (no system Python needed on the user's PC).
# Usage (from repo root, with Python 3.12 x64 on PATH):  powershell -File packaging\windows\build.ps1
$ErrorActionPreference = "Stop"
$PyVer = "3.12.8"
$Root = (Resolve-Path "$PSScriptRoot\..\..").Path
$App = Join-Path $Root "build\app"
$Py = Join-Path $App "python"

if (Test-Path $App) { Remove-Item -Recurse -Force $App }
New-Item -ItemType Directory -Force -Path $Py, "$App\bin" | Out-Null

Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile "$env:TEMP\pyembed.zip"
Expand-Archive "$env:TEMP\pyembed.zip" -DestinationPath $Py -Force

# enable site-packages (needed for pip and for installing AI engines later)
$pth = Get-ChildItem $Py -Filter "python3*._pth" | Select-Object -First 1
Set-Content $pth.FullName "python312.zip`r`n.`r`nLib\site-packages`r`nimport site"

python -m pip install --upgrade pip
python -m pip install --target "$Py\Lib\site-packages" pip "$Root"

Set-Content "$App\Forja3D.cmd" "@echo off`r`ntitle Forja3D - inchide aceasta fereastra ca sa opresti aplicatia`r`n`"%~dp0python\python.exe`" -m forja3d ui %*"
Set-Content "$App\bin\forja3d.cmd" "@echo off`r`n`"%~dp0..\python\python.exe`" -m forja3d %*"
Copy-Item "$Root\LICENSE", "$Root\README.md" $App

& "$Py\python.exe" -m forja3d --version
Write-Host "OK: $App"
