# Optional source-built, per-process Russian UI helper. FASTMEAN is not bundled.
# Normal Windows/organization application-control policies remain in force.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $FastmeanExe,
    [string] $Destination,
    [switch] $CreateShortcut,
    [switch] $VerifyLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-UnderDirectory {
    param([string] $Path, [string] $Root)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $fullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    return $fullPath.Equals($fullRoot, [StringComparison]::OrdinalIgnoreCase) -or
        $fullPath.StartsWith($fullRoot + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}

function Remove-PrivateDirectory {
    param([string] $Path, [string] $Parent, [string] $Prefix)
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return }
    $resolved = [System.IO.Path]::GetFullPath($Path)
    $expectedParent = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\', '/')
    $actualParent = [System.IO.Path]::GetDirectoryName($resolved).TrimEnd('\', '/')
    if (-not $actualParent.Equals($expectedParent, [StringComparison]::OrdinalIgnoreCase) -or
        -not [System.IO.Path]::GetFileName($resolved).StartsWith($Prefix, [StringComparison]::Ordinal)) {
        throw "Refusing to remove a directory outside the private installer staging area: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

function Assert-FileHash {
    param([string] $Path, [string] $Expected)
    $actual = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    if (-not $actual.Equals($Expected, [StringComparison]::OrdinalIgnoreCase)) {
        throw "SHA256 verification failed for $([System.IO.Path]::GetFileName($Path)). Expected $Expected; got $actual. Nothing will be launched."
    }
}

function Get-ApplicationControlError {
    param([Exception] $Exception)
    $current = $Exception
    while ($null -ne $current) {
        $nativeProperty = $current.PSObject.Properties['NativeErrorCode']
        if ($null -ne $nativeProperty -and [int] $nativeProperty.Value -in @(4551, 577, 1260)) {
            return $true
        }
        $current = $current.InnerException
    }
    return $false
}

$releaseUrl = 'https://github.com/xupefei/Locale-Emulator/releases/download/v2.5.0.1/Locale.Emulator.2.5.0.1.zip'
$releaseSha256 = '808FF584426D52CC775AD6406DA00622F454BE95BD4C8FBCA42EEF4B7235AD5C'
$dllHashes = @{
    'LoaderDll.dll' = '82FAE0F44F4CA0C9C37907DF74CEF2415EEB5FAE1CF8D4F36F34FFCAF7E3CC0C'
    'LocaleEmulator.dll' = 'C79C175FDAD174AA46A72197D148316299A56F950AAAB1B84930D09EE1084A88'
}
$repository = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$sources = Join-Path $repository 'font-fix\src'
$licenses = Join-Path $repository 'font-fix\licenses'
$temporaryRoot = [System.IO.Path]::GetTempPath()
$downloadDirectory = $null
$buildDirectory = $null
$destinationParent = $null

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'The optional Russian UI helper is available on Windows only.'
    }
    $targetItem = Get-Item -LiteralPath $FastmeanExe
    if ($targetItem.PSIsContainer -or -not $targetItem.Name.Equals('Fastmean.exe', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'FastmeanExe must name an existing, separately installed Fastmean.exe.'
    }
    $target = $targetItem.FullName
    if (-not $Destination) {
        $localData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
        $Destination = Join-Path $localData 'fastmean-mcp\RussianUI-helper'
    }
    $Destination = [System.IO.Path]::GetFullPath($Destination)
    if (Test-UnderDirectory -Path $Destination -Root $repository) {
        throw 'Keep runtime EXE/DLL files outside the source repository. Choose a Destination outside this checkout.'
    }
    if (Test-Path -LiteralPath $Destination) {
        throw "Destination already exists and will not be overwritten: $Destination. Choose a new empty destination path."
    }
    foreach ($required in @('FastmeanRuRunner.cs', 'FastmeanRuRunner.manifest')) {
        if (-not (Test-Path -LiteralPath (Join-Path $sources $required) -PathType Leaf)) {
            throw "Source file is missing: $required"
        }
    }
    foreach ($required in @('COPYING', 'COPYING.LESSER')) {
        if (-not (Test-Path -LiteralPath (Join-Path $licenses $required) -PathType Leaf)) {
            throw "License file is missing: $required"
        }
    }
    $compiler = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)) 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
    if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
        throw 'The .NET Framework 4.x x86 C# compiler was not found. Install the Windows .NET Framework build prerequisites separately, or use MCP without this optional helper.'
    }

    # Download only the pinned official release. No mirrors or alternate loader.
    $downloadDirectory = Join-Path $temporaryRoot ('fastmean-fontfix-download-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $downloadDirectory | Out-Null
    $archive = Join-Path $downloadDirectory 'Locale.Emulator.2.5.0.1.zip'
    Write-Host 'Downloading the pinned official Locale Emulator release...'
    Invoke-WebRequest -Uri $releaseUrl -OutFile $archive -UseBasicParsing
    Assert-FileHash -Path $archive -Expected $releaseSha256

    $destinationParent = [System.IO.Path]::GetDirectoryName($Destination)
    New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
    $buildDirectory = Join-Path $destinationParent ('.fontfix-build-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $buildDirectory | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
    try {
        # Extract only these two fixed filenames. Installer/updater/GUI EXEs
        # from the upstream archive are never extracted or executed.
        foreach ($name in $dllHashes.Keys) {
            $entries = @($zip.Entries | Where-Object { $_.FullName.Equals($name, [StringComparison]::Ordinal) })
            if ($entries.Count -ne 1) { throw "Pinned upstream archive has an unexpected entry for $name" }
            $entryStream = $entries[0].Open()
            $fileStream = [System.IO.File]::Open((Join-Path $buildDirectory $name), [System.IO.FileMode]::CreateNew)
            try { $entryStream.CopyTo($fileStream) }
            finally { $fileStream.Dispose(); $entryStream.Dispose() }
            Assert-FileHash -Path (Join-Path $buildDirectory $name) -Expected $dllHashes[$name]
        }
    }
    finally { $zip.Dispose() }

    foreach ($name in @('FastmeanRuRunner.cs', 'FastmeanRuRunner.manifest')) {
        Copy-Item -LiteralPath (Join-Path $sources $name) -Destination (Join-Path $buildDirectory $name)
    }
    foreach ($name in @('COPYING', 'COPYING.LESSER')) {
        Copy-Item -LiteralPath (Join-Path $licenses $name) -Destination (Join-Path $buildDirectory $name)
    }
    Copy-Item -LiteralPath (Join-Path $repository 'font-fix\NOTICE.md') -Destination (Join-Path $buildDirectory 'NOTICE.md')
    $helper = Join-Path $buildDirectory 'FastmeanRuRunner.exe'
    $compilerArguments = @('/nologo', '/target:winexe', '/platform:x86', '/optimize+',
        '/reference:System.Windows.Forms.dll', ('/out:' + $helper),
        ('/win32manifest:' + (Join-Path $buildDirectory 'FastmeanRuRunner.manifest')),
        (Join-Path $buildDirectory 'FastmeanRuRunner.cs'))
    Write-Host 'Building the x86 helper from the included source...'
    & $compiler @compilerArguments
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $helper -PathType Leaf)) {
        throw "C# compilation failed with exit code $LASTEXITCODE. No helper was launched."
    }
    $metadata = [ordered] @{
        component = 'Optional FASTMEAN Russian UI helper'
        sourceLicense = 'LGPL-3.0-only'
        upstreamRelease = $releaseUrl
        upstreamArchiveSHA256 = $releaseSha256
        sourceSHA256 = (Get-FileHash -LiteralPath (Join-Path $sources 'FastmeanRuRunner.cs') -Algorithm SHA256).Hash
        helperSHA256 = (Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash
        targetFastmean = $target
        globalWindowsSettingsChanged = $false
        compatibilityVerified = $false
    }
    $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $buildDirectory 'installation.json') -Encoding UTF8
    # Same-volume move publishes the completed folder and refuses replacement.
    [System.IO.Directory]::Move($buildDirectory, $Destination)
    $buildDirectory = $null
    $helper = Join-Path $Destination 'FastmeanRuRunner.exe'
    $shortcut = $null

    if ($CreateShortcut) {
        $desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
        $shortcut = Join-Path $desktop 'FASTMEAN (Russian UI helper).lnk'
        if (Test-Path -LiteralPath $shortcut) {
            $shortcut = Join-Path $desktop ('FASTMEAN (Russian UI helper ' + [Guid]::NewGuid().ToString('N').Substring(0, 6) + ').lnk')
        }
        $shell = New-Object -ComObject WScript.Shell
        $link = $shell.CreateShortcut($shortcut)
        $link.TargetPath = $helper
        $link.Arguments = '"' + $target + '"'
        $link.WorkingDirectory = $Destination
        $link.IconLocation = $target + ',0'
        $link.Save()
    }
    if ($VerifyLaunch) {
        Write-Host 'Starting the optional helper once. A FASTMEAN window may open.'
        $started = Start-Process -FilePath $helper -ArgumentList ('"' + $target + '"') -WorkingDirectory $Destination -WindowStyle Hidden -Wait -PassThru
        if ($started.ExitCode -ne 0) {
            throw "The optional helper stopped with exit code $($started.ExitCode). Use FASTMEAN MCP without it; no fallback or security-policy change is attempted."
        }
        $metadata.compatibilityVerified = $true
        $metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Destination 'installation.json') -Encoding UTF8
    }
    Write-Host "Optional helper installed at: $Destination"
    if (-not $VerifyLaunch) {
        Write-Host 'Not launched or compatibility-tested. Windows Application Control / Smart App Control may block it.'
    }
    Write-Host 'FASTMEAN MCP works without this optional UI helper. No Windows locale, registry or security policy was changed.'
    [PSCustomObject] @{ destination = $Destination; helper = $helper; shortcut = $shortcut; compatibilityVerified = [bool] $metadata.compatibilityVerified }
}
catch {
    if (Get-ApplicationControlError -Exception $_.Exception) {
        throw 'Windows Application Control / Smart App Control blocked the optional component. Installation or verification stopped. Use FASTMEAN MCP without this helper; no alternate loader, elevation or policy change will be attempted.'
    }
    throw
}
finally {
    if ($buildDirectory) {
        Remove-PrivateDirectory -Path $buildDirectory -Parent $destinationParent -Prefix '.fontfix-build-'
    }
    if ($downloadDirectory) {
        Remove-PrivateDirectory -Path $downloadDirectory -Parent $temporaryRoot -Prefix 'fastmean-fontfix-download-'
    }
}
