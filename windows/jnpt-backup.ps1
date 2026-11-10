#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ProfileDirectory = 'C:\JanuaPort\windows',
    [string]$Target
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-CurrentAccount { [Security.Principal.WindowsIdentity]::GetCurrent().Name }

function Invoke-BackupDocker {
    param([string[]]$Arguments)
    # Docker/kernel output can contain secrets. Only the checked metadata is
    # returned to our caller; native stderr is deliberately suppressed.
    $output = & docker compose @Arguments 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Docker-Sicherung fehlgeschlagen.' }
    return $output
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
    $remote = '/data/backups/' + $name
    $final = Join-Path $Target $name
    $partial = $final + '.teil'
    $ownsPartial = $false
    $ownsFinal = $false
    $success = $false
    Push-Location -LiteralPath $ProfileDirectory
    try {
        Invoke-BackupDocker @('exec', '-T', 'jnpt', '/jnpt', 'backup', '--output', $remote) | Out-Null
        $sizeText = (Invoke-BackupDocker @('exec', '-T', 'jnpt', 'stat', '-c', '%s', $remote)) -join ''
        [long]$size = 0
        if ($sizeText -cnotmatch '^[1-9][0-9]*$' -or -not [long]::TryParse($sizeText, [ref]$size)) {
            throw 'Ungueltige Sicherungsgroesse im Container.'
        }
        $hashText = (Invoke-BackupDocker @('exec', '-T', 'jnpt', 'sha256sum', $remote)) -join ''
        if ($hashText -cnotmatch ('^([a-f0-9]{64})  ' + [regex]::Escape($remote) + '$')) {
            throw 'Ungueltiger SHA-256 im Container.'
        }
        $digest = $Matches[1]
        # Reserve only our own unique partial file. No directory/broad /data copy:
        # the master key remains separate, including when stored next to the DB.
        $stream = [IO.File]::Open($partial, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $ownsPartial = $true
        $stream.Dispose()
        Invoke-BackupDocker @('cp', ('jnpt:' + $remote), $partial) | Out-Null
        Assert-BackupCopy $partial $size $digest
        Move-Item -LiteralPath $partial -Destination $final
        $ownsFinal = $true
        Assert-BackupCopy $final $size $digest
        # After reading back the destination hash, remove exactly this container
        # copy. No retention/deletion of older backups in v1.
        Invoke-BackupDocker @('exec', '-T', 'jnpt', 'rm', '--', $remote) | Out-Null
        $success = $true
        Write-Host ('Sicherung geprueft: ' + $final)
    } finally {
        Pop-Location
        if ($ownsPartial -and (Test-Path -LiteralPath $partial)) { Remove-Item -LiteralPath $partial -Force }
        if (-not $success -and $ownsFinal -and (Test-Path -LiteralPath $final)) { Remove-Item -LiteralPath $final -Force }
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
