#requires -Version 5.1
<# .SYNOPSIS
Optional wrapper for Python stdio MCP verification; starts no native analysis.
#>
[CmdletBinding()]
param([string]$InstallRoot, [string]$PythonPath, [switch]$SkipProtocol)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
$Python = Find-FastmeanPython $PythonPath
$Arguments = @('-X', 'utf8', (Join-Path $PSScriptRoot 'doctor.py'))
if ($InstallRoot) { $Arguments += @('--install-dir', $InstallRoot) }
if ($SkipProtocol) { $Arguments += '--skip-protocol' }
Invoke-FastmeanPython $Python $Arguments
