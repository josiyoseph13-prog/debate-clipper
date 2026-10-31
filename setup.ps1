param(
  [switch]$Legacy,
  [string]$PythonPath,
  [string]$VenvPath,
  [string]$FFmpegDirectory
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Set-Location $PSScriptRoot

Write-Host '=== Debate Clipper setup ===' -ForegroundColor Cyan
if (-not $PythonPath) {
  foreach ($Name in @('py', 'python')) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Command) { $PythonPath = $Command.Source; break }
  }
  if (-not $PythonPath -and (Test-Path '.venv\Scripts\python.exe')) {
    $PythonPath = (Resolve-Path '.venv\Scripts\python.exe').Path
  }
}
if (-not $PythonPath) { throw 'Python 3.11+ was not found. Supply -PythonPath to a native Python executable.' }
& $PythonPath -c 'import sys; print(sys.version); raise SystemExit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
if (-not $VenvPath) { $VenvPath = if ($Legacy) { '.venv' } else { '.venv_dc' } }
$VenvPython = Join-Path $VenvPath 'Scripts\python.exe'

if ($FFmpegDirectory) {
  $env:FFMPEG_PATH = (Resolve-Path (Join-Path $FFmpegDirectory 'ffmpeg.exe')).Path
  $env:FFPROBE_PATH = (Resolve-Path (Join-Path $FFmpegDirectory 'ffprobe.exe')).Path
} elseif (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Warning 'FFmpeg is not on PATH. Install a full build with libass, HarfBuzz and libx264 before rendering.'
} else {
  Write-Host "FFmpeg found: $((Get-Command ffmpeg).Source)" -ForegroundColor Green
}

if (-not (Test-Path $VenvPython)) {
  & $PythonPath -m venv $VenvPath
  if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
}
if ($Legacy) {
  & $VenvPython -m pip install -r requirements.txt
} else {
  & $VenvPython -m pip install --require-hashes -r requirements.lock
  if ($LASTEXITCODE -ne 0) { throw 'Core dependency installation failed; setup is incomplete.' }
  & $VenvPython -m pip install --require-hashes -r requirements-asr-windows.lock
  if ($LASTEXITCODE -ne 0) { throw 'ASR dependency installation failed; setup is incomplete.' }
  & $VenvPython -m pip install --require-hashes -r requirements-vision-windows.lock
  if ($LASTEXITCODE -ne 0) { throw 'Vision dependency installation failed; setup is incomplete.' }
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; setup is incomplete.' }
if (-not $Legacy) {
  $Tools = @{}
  if (Test-Path 'config\local_tools.json') {
    $Existing = Get-Content 'config\local_tools.json' -Raw | ConvertFrom-Json
    foreach ($Property in $Existing.PSObject.Properties) { $Tools[$Property.Name] = $Property.Value }
  }
  $Tools['windows'] = @{ python = (Resolve-Path $VenvPython).Path }
  if ($env:FFMPEG_PATH) { $Tools['windows']['ffmpeg'] = $env:FFMPEG_PATH }
  if ($env:FFPROBE_PATH) { $Tools['windows']['ffprobe'] = $env:FFPROBE_PATH }
  $Tools | ConvertTo-Json -Depth 4 | Set-Content 'config\local_tools.json' -Encoding UTF8
}
& $VenvPython -m dc doctor
if ($LASTEXITCODE -ne 0) { throw 'Doctor found blocking failures.' }

Write-Host ''
Write-Host 'Setup completed. Run .\run.ps1 for Review Studio or .\run.ps1 -Legacy for the old Streamlit shell.' -ForegroundColor Green
