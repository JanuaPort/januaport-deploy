#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ProfileDirectory = 'C:\JanuaPort\windows',
    [string]$Target
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'einrichten.ps1')
$UpdateRepository = 'ghcr.io/januaport/januaport'

function Write-UpdateLog {
    param([string]$Message)
    # Only explicit audit values, never native output, reason or exception text.
    $Message = $Message.Replace("`r", '\r').Replace("`n", '\n')
    foreach ($identity in @($env:USERPROFILE, $env:USERNAME, 'jnpt-dienst')) {
        if ($identity) { $Message = $Message.Replace($identity, '[redacted]') }
    }
    $path = Join-Path $ProfileDirectory 'log\update.log'
    $lines = @()
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $lines = @([IO.File]::ReadAllLines($path) | Select-Object -Last 99)
    }
    $lines += ([DateTime]::UtcNow.ToString('o') + "`t" + $Message)
    [IO.File]::WriteAllLines($path, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
}

function Invoke-UpdateProcess {
    param([string]$Command, [int]$TimeoutSeconds)
    # A separate PS 5.1 process bounds native calls even while Docker starts.
    # EAP=Continue inside it: native stderr must not become a terminating error.
    $commandText = "`$ErrorActionPreference='Continue'; [Console]::OutputEncoding=New-Object Text.UTF8Encoding(`$false); " + $Command
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $env:SystemRoot + '\System32\WindowsPowerShell\v1.0\powershell.exe'
    $start.Arguments = '-NoProfile -EncodedCommand ' +
        [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($commandText))
    $start.WorkingDirectory = $ProfileDirectory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        $process.Start() | Out-Null
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill()
            throw 'Zeitlimit fuer Kindprozess erreicht.'
        }
        return [pscustomobject]@{ExitCode=$process.ExitCode; Output=$stdout.GetAwaiter().GetResult()}
    } finally { $process.Dispose() }
}

function Invoke-UpdateDocker {
    param([string[]]$Arguments)
    # Guard the real adapter, including callers added in future changes.
    $command = $Arguments -join ' '
    $allowed = $command -ceq 'compose exec -T jnpt /jnpt update plan --json' -or
        $command -ceq 'compose up -d' -or
        $command -ceq 'compose run --rm --no-deps --entrypoint openssl cert-init x509 -in /certs/cert.pem -noout -fingerprint -sha256'
    if ($Arguments.Count -ge 8 -and
        ($Arguments[0..6] -join ' ') -ceq 'compose exec -T jnpt /jnpt update record') { $allowed = $true }
    if ($Arguments.Count -eq 2 -and $Arguments[0] -ceq 'pull' -and
        $Arguments[1] -cmatch ('\A' + [regex]::Escape($UpdateRepository) + '@sha256:[a-f0-9]{64}\z')) { $allowed = $true }
    if (-not $allowed) { throw 'Docker-Aufruf ausserhalb des Update-Vertrags.' }
    $quoted = @($Arguments | ForEach-Object { "'" + $_.Replace("'", "''") + "'" })
    # Native output stays private; only LASTEXITCODE determines command success.
    return Invoke-UpdateProcess ("& docker " + ($quoted -join ' ') + ' 2>$null; exit $LASTEXITCODE') 30
}

function Read-UpdatePlan {
    $native = Invoke-UpdateDocker @('compose', 'exec', '-T', 'jnpt', '/jnpt', 'update', 'plan', '--json')
    if ($native.ExitCode -ne 0) { throw 'Plan nicht lesbar.' }
    # Exactly one JSON object line; a final CRLF/LF is permitted, empty lines not.
    if ($native.Output -cnotmatch '\A[^\r\n]+(?:\r?\n)?\z') { throw 'Genau eine JSON-Zeile erforderlich.' }
    $plan = ConvertFrom-Json -InputObject $native.Output
    if ($plan -isnot [pscustomobject]) { throw 'JSON-Objekt erforderlich.' }
    $fields = @('current', 'latest', 'digest', 'action', 'on_failure', 'reason')
    foreach ($field in $fields) {
        if ($null -eq $plan.PSObject.Properties[$field] -or $plan.$field -isnot [string]) {
            throw 'Planfeld ungueltig.'
        }
    }
    if (@('none', 'unattended', 'approved', 'rollback') -cnotcontains $plan.action) { throw 'Unbekannte action.' }
    return $plan
}

function Write-UpdateRecord {
    param($Plan, [string]$Result)
    $arguments = @('compose', 'exec', '-T', 'jnpt', '/jnpt', 'update', 'record',
        ('--result=' + $Result), ('--from=' + $Plan.current), ('--to=' + $Plan.latest))
    if ($Plan.digest) { $arguments += '--digest=' + $Plan.digest }
    try {
        $native = Invoke-UpdateDocker $arguments
        if ($native.ExitCode -ne 0) { throw 'Ergebnis nicht buchbar.' }
        Write-UpdateLog ('record ' + $Result)
    } catch {
        # A failed record must never change the result of the update itself.
        try { Write-UpdateLog ('record failed result=' + $Result + ' from=' + $Plan.current + ' to=' + $Plan.latest + ' digest=' + $Plan.digest) } catch { }
    }
}

function Set-UpdateEnvironment {
    param([string]$Digest)
    $path = Join-Path $ProfileDirectory '.env'
    $text = [IO.File]::ReadAllText($path, (New-Object Text.UTF8Encoding($false, $true)))
    $imageLines = [regex]::Matches($text, '(?m)^JANUAPORT_IMAGE=[^\r\n]*')
    $digestLines = [regex]::Matches($text, '(?m)^JANUAPORT_IMAGE_DIGEST=[^\r\n]*')
    if ($imageLines.Count -ne 1 -or $digestLines.Count -ne 1) { throw 'Genau zwei Image-Zeilen erforderlich.' }
    Write-UpdateLog $imageLines[0].Value
    Write-UpdateLog $digestLines[0].Value
    $text = [regex]::Replace($text, '(?m)^JANUAPORT_IMAGE=[^\r\n]*', ('JANUAPORT_IMAGE=' + $UpdateRepository))
    $text = [regex]::Replace($text, '(?m)^JANUAPORT_IMAGE_DIGEST=[^\r\n]*', ('JANUAPORT_IMAGE_DIGEST=' + $Digest.Substring(7)))
    $temp = Join-Path $ProfileDirectory ([Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temp, $text, (New-Object Text.UTF8Encoding($false)))
        # Replace retains the destination DACL; no permission-writing adapter.
        [IO.File]::Replace($temp, $path, [NullString]::Value)
    } finally {
        if (Test-Path -LiteralPath $temp -PathType Leaf) { Remove-Item -LiteralPath $temp -Force }
    }
}

function Get-UpdateLeafFingerprint {
    $native = Invoke-UpdateDocker @('compose', 'run', '--rm', '--no-deps', '--entrypoint', 'openssl',
        'cert-init', 'x509', '-in', '/certs/cert.pem', '-noout', '-fingerprint', '-sha256')
    if ($native.ExitCode -ne 0 -or $native.Output.TrimEnd("`r", "`n") -cnotmatch '\Asha256 Fingerprint=([A-Fa-f0-9]{2}(?::[A-Fa-f0-9]{2}){31})\z') {
        throw 'Zertifikat nicht lesbar.'
    }
    return $Matches[1].Replace(':', '').ToLowerInvariant()
}

function Test-UpdateHealth {
    $fingerprint = Get-UpdateLeafFingerprint
    $ready = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8484/healthz' -TimeoutSec 3
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw 'Gateway nicht bereit.' }
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try { if ((Get-ServedLeafFingerprint) -ceq $fingerprint) { return } } catch { }
        Start-Sleep -Seconds 2
    }
    throw 'TLS-Fingerprint abweichend.'
}

function Invoke-JnptUpdate {
    try {
        Assert-DienstSession
        foreach ($file in @('.env', 'docker-compose.yml', 'Caddyfile', 'einrichten.ps1', 'jnpt-backup.ps1')) {
            if (-not (Test-Path -LiteralPath (Join-Path $ProfileDirectory $file) -PathType Leaf)) { throw 'Profil unvollstaendig.' }
        }
        foreach ($directory in @('log', 'backups')) {
            if (-not (Test-Path -LiteralPath (Join-Path $ProfileDirectory $directory) -PathType Container)) { throw 'Profilordner fehlt.' }
        }
    } catch { return 1 }
    try { $plan = Read-UpdatePlan } catch {
        Write-UpdateLog 'Plan nicht lesbar; Docker-Bereitschaft pruefen; exit=2'
        [Console]::Error.WriteLine('Update-Plan nicht lesbar; Docker-Bereitschaft und log\update.log pruefen.')
        return 2
    }
    if ($plan.action -ceq 'none') { Write-UpdateRecord $plan 'none'; return 0 }
    if ($plan.action -ceq 'rollback') { Write-UpdateLog 'RUNBOOK.md: Rueckweg von Hand; exit=2'; return 2 }
    if (-not ($plan.digest -cmatch '\Asha256:[a-f0-9]{64}\z')) { Write-UpdateLog 'Digest ungueltig; exit=2'; return 2 }
    try {
        $backupScript = (Join-Path $ProfileDirectory 'jnpt-backup.ps1').Replace("'", "''")
        $profileArgument = $ProfileDirectory.Replace("'", "''")
        $targetArgument = $Target.Replace("'", "''")
        $backup = Invoke-UpdateProcess ("& '$backupScript' -ProfileDirectory '$profileArgument' -Target '$targetArgument'; exit `$LASTEXITCODE") 600
        if ($backup.ExitCode -ne 0) { throw 'Sicherung fehlgeschlagen.' }
        $image = $UpdateRepository + '@' + $plan.digest
        $pull = Invoke-UpdateDocker @('pull', $image)
        if ($pull.ExitCode -ne 0) { throw 'Pull fehlgeschlagen.' }
        Set-UpdateEnvironment $plan.digest
    } catch { Write-UpdateLog 'Sicherung, Pull oder Dateiaustausch fehlgeschlagen; exit=3'; return 3 }
    try {
        $up = Invoke-UpdateDocker @('compose', 'up', '-d')
        if ($up.ExitCode -ne 0) { throw 'Start fehlgeschlagen.' }
        Test-UpdateHealth
    } catch {
        Write-UpdateRecord $plan 'failed'
        Write-UpdateLog 'Update fehlgeschlagen; RUNBOOK.md: Rueckweg von Hand; exit=6'
        return 6
    }
    Write-UpdateRecord $plan 'installed'
    Write-UpdateLog 'Update installiert; exit=0'
    return 0
}

function Start-JnptUpdate {
    try { exit (Invoke-JnptUpdate) } catch {
        [Console]::Error.WriteLine('Update fehlgeschlagen; log\update.log und RUNBOOK.md pruefen.')
        exit 3
    }
}

if ($MyInvocation.InvocationName -ne '.') { Start-JnptUpdate }
