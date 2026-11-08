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

# Microsoft C++ runtime: some packages (rtree, ...) need msvcp140.dll, which is missing on PCs
# without the "Visual C++ Redistributable". These DLLs are redistributable with the app.
foreach ($dll in "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "concrt140.dll", "vcruntime140.dll", "vcruntime140_1.dll") {
  $src = Join-Path $env:WINDIR "System32\$dll"
  if (-not (Test-Path (Join-Path $Py $dll)) -and (Test-Path $src)) { Copy-Item $src $Py }
}
if (-not (Test-Path (Join-Path $Py "msvcp140.dll"))) { throw "msvcp140.dll lipseste din pachet" }

# launchers (CRLF line endings for cmd.exe)
foreach ($pair in @(@("Forja3D.cmd", "$App\Forja3D.cmd"), @("forja3d-cli.cmd", "$App\bin\forja3d.cmd"))) {
  $text = (Get-Content -Raw (Join-Path $PSScriptRoot $pair[0])) -replace "`r?`n", "`r`n"
  [IO.File]::WriteAllText($pair[1], $text, (New-Object Text.ASCIIEncoding))
}
Copy-Item "$Root\LICENSE", "$Root\README.md", "$Root\CHANGELOG.md" $App

& "$Py\python.exe" -m forja3d --version
Write-Host "OK: $App"
