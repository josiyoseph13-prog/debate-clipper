param(
  [switch]$Legacy,
  [switch]$Lan
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Set-Location $PSScriptRoot
$Python = if ($Legacy) { '.venv\Scripts\python.exe' } else { '.venv_dc\Scripts\python.exe' }
if (-not $Legacy -and (Test-Path 'config\local_tools.json')) {
  $Tools = Get-Content 'config\local_tools.json' -Raw | ConvertFrom-Json
  if ($Tools.windows.python) { $Python = $Tools.windows.python }
  if ($Tools.windows.ffmpeg) { $env:FFMPEG_PATH = $Tools.windows.ffmpeg }
  if ($Tools.windows.ffprobe) { $env:FFPROBE_PATH = $Tools.windows.ffprobe }
}
if (-not (Test-Path $Python)) { throw 'Virtual environment not found. Run .\setup.ps1 first.' }

if ($Legacy) {
  & $Python -m streamlit run app.py
} elseif ($Lan) {
  & $Python -m dc studio --lan
} else {
  & $Python -m dc studio
}
