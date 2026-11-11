#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ProfileDirectory = 'C:\JanuaPort\windows',
    [string]$Target
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$BackupNamePattern = '^jnpt-[0-9]{8}T[0-9]{9}Z-[a-f0-9]{32}\.jnpt-backup$'

function Get-CurrentAccount { [Security.Principal.WindowsIdentity]::GetCurrent().Name }

function Invoke-BackupDocker {
    param([string[]]$Arguments)
    # The distroless core has no shell or file utilities. Guard the actual
    # native adapter as well as its callers; no compose cp or second image.
    if ($Arguments.Count -lt 4 -or $Arguments[0] -cne 'exec' -or
        $Arguments[1] -cne '-T' -or $Arguments[2] -cne 'jnpt' -or $Arguments[3] -cne '/jnpt') {
        throw 'Im Kern-Container ist nur /jnpt erlaubt.'
    }
    # Core output may contain secrets; it is never printed by the entry point.
    $output = & docker compose @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Docker-Sicherung fehlgeschlagen.' }
    return $output
}

function Remove-StagedBackup {
    param([string]$Path)
    $resolved = [IO.Path]::GetFullPath($Path)
    $staging = [IO.Path]::GetFullPath((Join-Path $ProfileDirectory 'backups')).TrimEnd('\')
    if ([IO.Path]::GetDirectoryName($resolved) -ine $staging -or
        [IO.Path]::GetFileName($resolved) -cnotmatch $BackupNamePattern) {
        throw 'Nur benannte Sicherungsdateien im Staging loeschen.'
    }
    if (Test-Path -LiteralPath $resolved -PathType Leaf) { Remove-Item -LiteralPath $resolved -Force }
}

function Clear-StagedBackups {
    $staging = Join-Path $ProfileDirectory 'backups'
    foreach ($file in @(Get-ChildItem -LiteralPath $staging -File)) {
        if ($file.Name -cmatch $BackupNamePattern) { Remove-StagedBackup $file.FullName }
    }
}

function Assert-BackupCopy {
    param([string]$Path, [long]$Size, [string]$Digest)
    if ((Get-Item -LiteralPath $Path).Length -ne $Size) { throw 'Sicherungsgroesse stimmt nicht.' }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Digest) {
        throw 'SHA-256 der Sicherung stimmt nicht.'
    }
}

function Invoke-JnptBackup {
    if ((Get-CurrentAccount) -ine ($env:COMPUTERNAME + '\jnpt-dienst')) {
        throw 'Sicherung nur in der Sitzung von jnpt-dienst starten.'
    }
    if ($Target -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$))') {
        throw 'Absolutes Sicherungsziel erforderlich.'
    }
    $Target = [IO.Path]::GetFullPath($Target)
    $marker = Join-Path $Target '.jnpt-backup-ziel'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw 'Markerdatei am Sicherungsziel fehlt.' }
    foreach ($file in @('docker-compose.yml', '.env')) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProfileDirectory $file) -PathType Leaf)) {
            throw 'Profil unvollstaendig.'
        }
    }
    $name = 'jnpt-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [Guid]::NewGuid().ToString('N') + '.jnpt-backup'
    $staging = Join-Path $ProfileDirectory 'backups'
    if (-not (Test-Path -LiteralPath $staging -PathType Container)) { throw 'Sicherungs-Staging fehlt.' }
    # Recover only generated leftovers from previous failed runs, never foreign
    # files or older backups on the external destination.
    Clear-StagedBackups
    $source = Join-Path $staging $name
    $remote = '/backups/' + $name
    $final = Join-Path $Target $name
    $partial = $final + '.teil'
    $ownsPartial = $false
    $ownsFinal = $false
    $success = $false
    Push-Location -LiteralPath $ProfileDirectory
    try {
        Invoke-BackupDocker @('exec', '-T', 'jnpt', '/jnpt', 'backup', '--output', $remote) | Out-Null
        [long]$size = (Get-Item -LiteralPath $source).Length
        if ($size -le 0) { throw 'Leere Sicherungsdatei im Staging.' }
        $digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
        # Copy exactly this backup; the master key remains in /data.
        $stream = [IO.File]::Open($partial, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $ownsPartial = $true
        $stream.Dispose()
        Copy-Item -LiteralPath $source -Destination $partial -Force
        Assert-BackupCopy $partial $size $digest
        Move-Item -LiteralPath $partial -Destination $final
        $ownsFinal = $true
        Assert-BackupCopy $final $size $digest
        Remove-StagedBackup $source
        $success = $true
        Write-Host ('Sicherung geprueft: ' + $final)
    } finally {
        try { Remove-StagedBackup $source } finally {
            Pop-Location
            if ($ownsPartial -and (Test-Path -LiteralPath $partial)) { Remove-Item -LiteralPath $partial -Force }
            if (-not $success -and $ownsFinal -and (Test-Path -LiteralPath $final)) { Remove-Item -LiteralPath $final -Force }
        }
    }
}

function Start-JnptBackup {
    try { Invoke-JnptBackup; exit 0 } catch {
        # Do not print native output or exception invocation text (could contain
        # secrets). Task Scheduler records this nonzero result.
        [Console]::Error.WriteLine('Sicherung fehlgeschlagen (jnpt-dienst, Marker, Ziel und Docker pruefen).')
        exit 1
    }
}

if ($MyInvocation.InvocationName -ne '.') { Start-JnptBackup }
