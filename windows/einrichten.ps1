#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$Directory = 'C:\JanuaPort\windows',
    [switch]$NeuesZertifikat
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Dieser Release-Tag muss vor dem veroeffentlichten Aufruf existieren und
# unveraenderlich bleiben. Kein main/Branch als Downloadquelle.
$ProfileRef = 'windows-v0.2.0'
$ProfileBase = "https://raw.githubusercontent.com/JanuaPort/januaport-deploy/$ProfileRef/windows"
$Repository = 'ghcr.io/januaport/januaport'
$ProfileFiles = @('docker-compose.yml', 'Caddyfile', 'einrichten.ps1', '.gitignore',
    'README.md', 'README.en.md', 'RUNBOOK.md', 'dienst-einrichten.ps1',
    'jnpt-backup.ps1', 'jnpt-sperren.ps1', 'PRUEFSTEIN-B4.md')

function Invoke-Docker {
    param([string[]]$Arguments)
    $output = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker fehlgeschlagen: $($Arguments[0])" }
    return $output
}

function Test-ProfileFiles {
    param([string]$Path)
    # External licensed binary: pinned here, downloaded/verified separately by
    # dienst-einrichten.ps1. It is not part of the public profile distribution.
    $expected = $ProfileFiles + @('Autologon64.exe')
    $seen = @{}
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $Path 'SHA256SUMS'))) {
        if ($line -cnotmatch '^([a-f0-9]{64})  ([A-Za-z0-9.-]+)$') { throw 'Ungueltige SHA256SUMS-Zeile.' }
        $digest = $Matches[1]
        $name = $Matches[2]
        if ($expected -cnotcontains $name -or $seen.ContainsKey($name)) { throw 'Unerwarteter Summeneintrag.' }
        $seen[$name] = $true
        if ($name -ceq 'Autologon64.exe') { continue }
        $file = [IO.File]::OpenRead((Join-Path $Path $name))
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            $actual = ([BitConverter]::ToString($sha.ComputeHash($file))).Replace('-', '').ToLowerInvariant()
        } finally { $sha.Dispose(); $file.Dispose() }
        if ($actual -cne $digest) {
            throw "SHA-256-Pruefung fehlgeschlagen: $name"
        }
    }
    if ($seen.Count -ne $expected.Count) { throw 'Unvollstaendige SHA256SUMS.' }
}

function Resolve-CoreImage {
    param([string]$Value)
    $Value = $Value.Trim()
    if ($Value -cmatch '^(?:ghcr\.io/januaport/januaport@)?sha256:([a-f0-9]{64})$') {
        return @($Repository, $Matches[1])
    }
    if ($Value -cnotmatch '^(?:ghcr\.io/januaport/januaport:)?([A-Za-z0-9_][A-Za-z0-9_.-]{0,127})$') {
        throw 'Image-Tag oder sha256:<64 kleine Hex-Zeichen> erforderlich.'
    }
    $tagged = "${Repository}:$($Matches[1])"
    Invoke-Docker @('pull', $tagged) | Out-Host
    $digests = (Invoke-Docker @('image', 'inspect', '--format', '{{json .RepoDigests}}', $tagged)) -join '' | ConvertFrom-Json
    foreach ($item in $digests) {
        if ($item -cmatch '^ghcr\.io/januaport/januaport@sha256:([a-f0-9]{64})$') {
            return @($tagged, $Matches[1])
        }
    }
    throw 'Registry lieferte keinen passenden Repository-Digest.'
}

function Get-CertificateSAN {
    $sans = @('IP:127.0.0.1', 'DNS:localhost', ('DNS:' + [Net.Dns]::GetHostName()))
    foreach ($adapter in [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
        foreach ($address in $adapter.GetIPProperties().UnicastAddresses) {
            if ($address.Address.AddressFamily -eq [Net.Sockets.AddressFamily]::InterNetwork) {
                $sans += 'IP:' + $address.Address.ToString()
            }
        }
    }
    return (($sans | Select-Object -Unique) -join ',')
}

function Get-LeafFingerprint {
    # Aus genau dem PEM im eigenen Volume, ohne Schluessel-Export zum Host.
    $line = (Invoke-Docker @('compose', 'run', '--rm', '--no-deps', '--entrypoint', 'openssl',
        'cert-init', 'x509', '-in', '/certs/cert.pem', '-noout', '-fingerprint', '-sha256')) -join ''
    if ($line -notmatch '^sha256 Fingerprint=([A-Fa-f0-9]{2}(?::[A-Fa-f0-9]{2}){31})$') {
        throw 'Ungueltige Zertifikats-Fingerprint-Ausgabe.'
    }
    return $Matches[1].Replace(':', '').ToLowerInvariant()
}

function Get-ServedLeafFingerprint {
    $client = New-Object Net.Sockets.TcpClient
    $stream = $null
    try {
        $client.Connect('127.0.0.1', 443)
        # Nur fuer die lokale Ausgabe des Pins; der Laeufer verifiziert ihn.
        $acceptLocal = [Net.Security.RemoteCertificateValidationCallback]{ param($sender, $certificate, $chain, $errors) return $true }
        $stream = New-Object Net.Security.SslStream($client.GetStream(), $false, $acceptLocal)
        $stream.ReadTimeout = 5000
        $stream.WriteTimeout = 5000
        $stream.AuthenticateAsClient('localhost', $null, [Security.Authentication.SslProtocols]::Tls12, $false)
        $sha = [Security.Cryptography.SHA256]::Create()
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($stream.RemoteCertificate.GetRawCertData()))).Replace('-', '').ToLowerInvariant()
        } finally { $sha.Dispose() }
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $client.Close()
    }
}

function Initialize-MailSecret {
    param([string]$Path)
    $secretDirectory = Join-Path $Path 'secrets'
    New-Item -ItemType Directory -Path $secretDirectory -Force | Out-Null
    # OpenOrCreate legt nur bei Bedarf an und kuerzt vorhandene Secrets nicht.
    foreach ($name in @('smtp_password', 'graph_client_secret')) {
        $file = [IO.File]::Open((Join-Path $secretDirectory $name),
            [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $file.Dispose()
    }
}

function Test-LegacyProfile {
    param([string]$Path)
    # Exact published windows-v0.1.0 bytes, independent of an optional local
    # SHA256SUMS. An altered installation is not an automatic upgrade source.
    $legacy = @{
        'docker-compose.yml' = '40f294bcc40fe7a3f431685ef7c913e17b33f0524402cefde24e348c1aa28da1'
        'Caddyfile' = 'd73ab75fd9ade61067160a660828effcb37dc3176816ace9ce826ae77d96355d'
        'einrichten.ps1' = '2a3671e5ccd5b9cc47ff0753594d712ea18119500b3c611fadd250587cbcbae3'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $Path '.env') -PathType Leaf)) { return $false }
    foreach ($name in $legacy.Keys) {
        $file = Join-Path $Path $name
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { return $false }
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $legacy[$name]) { return $false }
    }
    return $true
}

function Install-Profile {
    Assert-DienstSession
    Get-Command docker -ErrorAction Stop | Out-Null
    Invoke-Docker @('compose', 'version') | Out-Host
    $upgrade = Test-LegacyProfile $Directory
    if ((Test-Path -LiteralPath $Directory) -and -not $upgrade) {
        foreach ($name in (@('SHA256SUMS') + $ProfileFiles)) {
            if (-not (Test-Path -LiteralPath (Join-Path $Directory $name) -PathType Leaf)) {
                throw 'Ziel existiert bereits und ist kein vollstaendiges Profil.'
            }
        }
        Test-ProfileFiles $Directory
        # B2 stages a verified profile before the first interactive installation.
        if (-not (Test-Path -LiteralPath (Join-Path $Directory '.env'))) {
            $image = Resolve-CoreImage (Read-Host 'JanuaPort Image-Tag (z.B. 0.87.1) oder sha256:Digest')
            $envText = "JANUAPORT_IMAGE=$($image[0])`nJANUAPORT_IMAGE_DIGEST=$($image[1])`n"
            [IO.File]::WriteAllText((Join-Path $Directory '.env'), $envText, (New-Object Text.UTF8Encoding($false)))
        }
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $staging = Join-Path ([IO.Path]::GetTempPath()) ('jnpt-profile-' + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $staging | Out-Null
        try {
            foreach ($name in (@('SHA256SUMS') + $ProfileFiles)) {
                Invoke-WebRequest -UseBasicParsing -Uri "$ProfileBase/$name" -OutFile (Join-Path $staging $name)
            }
            Test-ProfileFiles $staging
            if (-not $upgrade) {
                $image = Resolve-CoreImage (Read-Host 'JanuaPort Image-Tag (z.B. 0.87.1) oder sha256:Digest')
                New-Item -ItemType Directory -Path $Directory | Out-Null
            }
            # Only release-managed files. Preserve .env, secrets and Docker
            # volumes; the complete download was verified before any replacement.
            foreach ($name in (@('SHA256SUMS') + $ProfileFiles)) {
                Copy-Item -LiteralPath (Join-Path $staging $name) -Destination (Join-Path $Directory $name)
            }
            if (-not $upgrade) {
                $envText = "JANUAPORT_IMAGE=$($image[0])`nJANUAPORT_IMAGE_DIGEST=$($image[1])`n"
                [IO.File]::WriteAllText((Join-Path $Directory '.env'), $envText, (New-Object Text.UTF8Encoding($false)))
            }
        } finally {
            # Ausschliesslich der oben selbst angelegte temporaere Ordner.
            $resolvedStaging = [IO.Path]::GetFullPath($staging)
            $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
            if (-not $resolvedStaging.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Temporaerer Pfad liegt ausserhalb des Temp-Verzeichnisses.'
            }
            Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
        }
    }
    Initialize-MailSecret $Directory
    Push-Location $Directory
    try {
        Invoke-Docker @('compose', 'config', '--quiet') | Out-Host
        if ($NeuesZertifikat) {
            Invoke-Docker @('compose', 'stop', 'caddy') | Out-Host
            Invoke-Docker @('compose', 'run', '--rm', '--no-deps', '--entrypoint', '/bin/sh',
                'cert-init', '-ec', 'rm -f /certs/cert.pem /certs/key.pem') | Out-Host
        }
        Invoke-Docker @('compose', 'run', '--rm', '--no-deps', '-e',
            ('CERT_SAN=' + (Get-CertificateSAN)), 'cert-init') | Out-Host
        $fingerprint = Get-LeafFingerprint
        Invoke-Docker @('compose', 'up', '-d') | Out-Host
        $ready = $false
        for ($attempt = 0; $attempt -lt 90; $attempt++) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8484/healthz' -TimeoutSec 3
                if ($response.StatusCode -eq 200) { $ready = $true; break }
            } catch { }
            Start-Sleep -Seconds 2
        }
        if (-not $ready) { throw 'Gateway nicht bereit. Diagnose: docker compose logs jnpt' }
        $tlsReady = $false
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try {
                if ((Get-ServedLeafFingerprint) -ceq $fingerprint) { $tlsReady = $true; break }
            } catch { }
            Start-Sleep -Seconds 2
        }
        if (-not $tlsReady) { throw 'Caddy liefert nicht das eingerichtete Zertifikat. Diagnose: docker compose logs caddy' }
        Write-Host "Profil: $Directory"
        Write-Host 'Admin-GUI: http://127.0.0.1:8484'
        Write-Host "SHA-256 des Caddy-Leaf-Zertifikats: $fingerprint"
        Write-Host ".\desktop-runner.exe pair --url https://<LAN-IP> --code <KOPPLUNGSCODE> --fingerprint $fingerprint"
        Write-Host 'CA nie in einen Zertifikatsspeicher importieren. Fingerprint lokal vertrauenswuerdig weitergeben.'
    } finally { Pop-Location }
}

# Dot-Sourcing erlaubt Adaptertests der Funktionen ohne Installation.
function Get-CurrentAccount { [Security.Principal.WindowsIdentity]::GetCurrent().Name }

function Assert-DienstSession {
    if ((Get-CurrentAccount) -ine ($env:COMPUTERNAME + '\jnpt-dienst')) {
        throw 'Installation nur in der Sitzung von jnpt-dienst starten.'
    }
}

if ($MyInvocation.InvocationName -ne '.') { Install-Profile }
