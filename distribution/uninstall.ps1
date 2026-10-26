#requires -Version 5.1
<# .SYNOPSIS
Optional uninstall.py wrapper; results/backups stay by default.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param([string]$InstallRoot, [string]$PythonPath, [bool]$KeepResults = $true, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
$Python = Find-FastmeanPython $PythonPath
$Arguments = @('-X', 'utf8', (Join-Path $PSScriptRoot 'uninstall.py'))
if ($InstallRoot) { $Arguments += @('--install-dir', $InstallRoot) }
if (-not $KeepResults) { $Arguments += '--remove-results' }
if ($DryRun) { $Arguments += '--dry-run' }
elseif (-not $PSCmdlet.ShouldProcess('Owned FASTMEAN MCP installation', 'Remove only its MCP entry and owned files')) {
    $Arguments += '--dry-run'
}
Invoke-FastmeanPython $Python $Arguments
