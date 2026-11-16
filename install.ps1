$ErrorActionPreference = "Stop"

$RawBase = if ($env:AGY_STATUSLINE_RAW_BASE) {
    $env:AGY_STATUSLINE_RAW_BASE
} else {
    "https://raw.githubusercontent.com/kkrr6840/agy-statusline/main"
}

$PyCmd = $null
foreach ($candidate in @("python", "py")) {
    $found = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($found -and $found.Source -notlike "*WindowsApps*") {
        $PyCmd = $found.Source
        break
    }
}
if (-not $PyCmd) {
    $found = Get-Command python -ErrorAction SilentlyContinue
    if ($found) { $PyCmd = $found.Source }
}
if (-not $PyCmd) {
    Write-Error "Python 3 is required to install agy-statusline."
    exit 1
}

$TmpInstaller = Join-Path ([System.IO.Path]::GetTempPath()) "agy-statusline-install-$PID.py"
try {
    Invoke-RestMethod -Uri "$RawBase/install.py" -OutFile $TmpInstaller
    if ($PyCmd -like "*\py.exe") {
        & $PyCmd -3 $TmpInstaller @args
    } else {
        & $PyCmd $TmpInstaller @args
    }
} finally {
    Remove-Item -Path $TmpInstaller -Force -ErrorAction SilentlyContinue
}
