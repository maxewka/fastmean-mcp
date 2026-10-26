# Optional PowerShell wrapper helpers. Lifecycle operations live in Python.
Set-StrictMode -Version Latest

function Test-FastmeanPython([string]$Executable, [string[]]$Prefix = @()) {
    if (-not $Executable -or $Executable -match '(?i)\\Microsoft\\WindowsApps\\python(?:3)?\.exe$') { return $null }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $arguments = @($Prefix) + @('-X', 'utf8', '-I', '-c', "import sys,venv; print('%s.%s.%s' % sys.version_info[:3]); print(sys.executable)")
        $lines = @(& $Executable @arguments 2>$null)
        if ($LASTEXITCODE -ne 0 -or $lines.Count -lt 2) { return $null }
        $version = $null
        if ([version]::TryParse([string]$lines[0], [ref]$version) -and $version -ge [version]'3.12' -and
            (Test-Path -LiteralPath ([string]$lines[1]) -PathType Leaf)) { return [string]$lines[1] }
    } catch { return $null }
    finally { $ErrorActionPreference = $previous }
    return $null
}

function Find-FastmeanPython([string]$Explicit) {
    if ($Explicit) {
        $result = Test-FastmeanPython $Explicit
        if ($result) { return $result }
        throw 'PythonPath must point to a working existing Python 3.12+ with venv.'
    }
    $launcher = Get-Command py.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($launcher) {
        foreach ($selector in @('-3', '-3.14', '-3.13', '-3.12')) {
            $result = Test-FastmeanPython $launcher.Source @($selector)
            if ($result) { return $result }
        }
    }
    foreach ($name in @('python.exe', 'python3.exe')) {
        foreach ($command in @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)) {
            $result = Test-FastmeanPython $command.Source
            if ($result) { return $result }
        }
    }
    $result = Test-FastmeanPython (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
    if ($result) { return $result }
    throw 'Use an existing Python 3.12+ (-PythonPath), or run the equivalent distribution/install.py from an approved Python host. No execution-policy changes are made.'
}

function Invoke-FastmeanPython([string]$Python, [string[]]$Arguments) {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "FASTMEAN MCP Python command failed with exit code $LASTEXITCODE. Review the error above." }
}
