#requires -Version 5.1
<# .SYNOPSIS
Optional wrapper for install.py. Use Python directly if existing policy forbids PS scripts.
No execution-policy, security, registry, PATH, or system locale changes.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param([string]$AppDir, [string]$PythonPath, [string]$CodexPath, [string]$InstallRoot,
      [string]$OutputDir, [string]$CodexHome, [string]$PackagePath,
      [switch]$ReplaceExisting, [switch]$SkipDoctor, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
$Python = Find-FastmeanPython $PythonPath
$Arguments = @('-X', 'utf8', (Join-Path $PSScriptRoot 'install.py'))
foreach ($pair in @(@('--app-dir', $AppDir), @('--python', $Python), @('--codex-path', $CodexPath),
    @('--install-dir', $InstallRoot), @('--output-dir', $OutputDir), @('--codex-home', $CodexHome), @('--package-path', $PackagePath))) {
    if ($pair[1]) { $Arguments += $pair }
}
if ($ReplaceExisting) { $Arguments += '--replace-existing' }
if ($SkipDoctor) { $Arguments += '--skip-doctor' }
if ($DryRun) { $Arguments += '--dry-run' }
elseif (-not $PSCmdlet.ShouldProcess('FASTMEAN MCP user installation', 'Create/upgrade private venv and register only fastmean in Codex')) {
    $Arguments += '--dry-run'
}
Invoke-FastmeanPython $Python $Arguments
