$ErrorActionPreference = "Stop"

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {}

$RawBase = if ($env:AGY_STATUSLINE_RAW_BASE) {
    $env:AGY_STATUSLINE_RAW_BASE
} else {
    "https://raw.githubusercontent.com/kkrr6840/agy-statusline/main"
}

function Test-Python3 {
    param(
        [Parameter(Mandatory = $true)][string]$ExePath,
        [switch]$UsePyLauncher
    )
    try {
        $ver = if ($UsePyLauncher) {
            & $ExePath -3 -c "import sys; print(sys.version_info[0])" 2>$null
        } else {
            & $ExePath -c "import sys; print(sys.version_info[0])" 2>$null
        }
        return ($LASTEXITCODE -eq 0 -and ($ver | Out-String).Trim() -eq "3")
    } catch {
        return $false
    }
}

$PyCmd = $null
$UsePyLauncher = $false

foreach ($includeWindowsApps in @($false, $true)) {
    foreach ($candidate in @("python", "python3", "py")) {
        $foundList = @(Get-Command $candidate -CommandType Application -All -ErrorAction SilentlyContinue)
        foreach ($found in $foundList) {
            if (-not $found -or -not $found.Source) { continue }
            $isWindowsApps = $found.Source -like "*WindowsApps*"
            if ($includeWindowsApps -ne $isWindowsApps) { continue }
            $isPy = $found.Name -ieq "py.exe"
            if (Test-Python3 -ExePath $found.Source -UsePyLauncher:$isPy) {
                $PyCmd = $found.Source
                $UsePyLauncher = $isPy
                break
            }
        }
        if ($PyCmd) { break }
    }
    if ($PyCmd) { break }
}

if (-not $PyCmd) {
    Write-Error "Python 3 is required to install agy-statusline."
    exit 1
}

$TmpInstaller = Join-Path ([System.IO.Path]::GetTempPath()) "agy-statusline-install-$PID.py"
try {
    Invoke-RestMethod -Uri "$RawBase/install.py" -OutFile $TmpInstaller
    if ($UsePyLauncher) {
        & $PyCmd -3 $TmpInstaller @args
    } else {
        & $PyCmd $TmpInstaller @args
    }
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Remove-Item -Path $TmpInstaller -Force -ErrorAction SilentlyContinue
}
