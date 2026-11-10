#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$BackupTarget,
    [switch]$KennwortNeu
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$DienstDirectory = 'C:\JanuaPort\windows'
. (Join-Path $PSScriptRoot 'einrichten.ps1')

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrative PowerShell erforderlich.'
    }
}

function New-DienstPassword {
    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
        # Fixed complexity prefix plus 384 random bits; only a SecureString is
        # returned. No transcript, credential manager or password file.
        return ConvertTo-SecureString ('aA1!' + [Convert]::ToBase64String($bytes)) -AsPlainText -Force
    } finally { $rng.Dispose(); [Array]::Clear($bytes, 0, $bytes.Length) }
}

function Get-DienstProfilePath {
    param($User)
    $entry = Get-CimInstance Win32_UserProfile | Where-Object { $_.SID -eq $User.SID.Value }
    if ($entry) { return $entry.LocalPath }
    if (-not ('Jnpt.UserProfile' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
namespace Jnpt {
    public static class UserProfile {
        [DllImport("userenv.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern int CreateProfile(string sid, string name, StringBuilder path, uint size);
    }
}
'@
    }
    $path = New-Object Text.StringBuilder 1024
    $result = [Jnpt.UserProfile]::CreateProfile($User.SID.Value, $User.Name, $path, 1024)
    if ($result -ne 0) { throw 'Windows-Benutzerprofil konnte nicht angelegt werden.' }
    return $path.ToString()
}

function Clear-DienstExplicitAccess {
    param([string]$Path)
    $acl = [IO.Directory]::GetAccessControl($Path, [Security.AccessControl.AccessControlSections]::Access)
    foreach ($existing in @($acl.Access)) {
        if (-not $existing.IsInherited) { $acl.RemoveAccessRuleSpecific($existing) }
    }
    [IO.Directory]::SetAccessControl($Path, $acl)
}

function Protect-DienstDirectory {
    param([string]$Path, $SID)
    # Remove previous explicit grants as well; /grant:r alone would keep grants
    # to other accounts. Inherited C:\ grants are removed by icacls itself.
    Clear-DienstExplicitAccess $Path
    $grants = @(("*" + [string]$SID + ':(OI)(CI)F'),
        '*S-1-5-32-544:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F')
    & icacls.exe $Path '/inheritance:r' '/grant:r' @grants *> $null
    if ($LASTEXITCODE -ne 0) { throw 'icacls fuer Dienstordner fehlgeschlagen.' }
}

function Protect-DienstRoot {
    param($SID)
    $root = Split-Path -Path $DienstDirectory -Parent
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Protect-DienstDirectory $root $SID
}

function Set-DienstScreenLock {
    param([string]$ProfilePath, $SID)
    $hive = 'Registry::HKEY_USERS\' + [string]$SID
    $loadedHere = -not (Test-Path -LiteralPath $hive)
    if ($loadedHere) {
        & reg.exe load ('HKU\' + [string]$SID) (Join-Path $ProfilePath 'NTUSER.DAT') *> $null
        if ($LASTEXITCODE -ne 0) { throw 'Benutzer-Hive konnte nicht geladen werden.' }
    }
    try {
        $key = $hive + '\Software\Policies\Microsoft\Windows\Control Panel\Desktop'
        New-Item -Path $key -Force | Out-Null
        foreach ($setting in @(@('ScreenSaveActive','1'), @('ScreenSaveTimeOut','60'),
                @('ScreenSaverIsSecure','1'), @('SCRNSAVE.EXE', ($env:SystemRoot + '\System32\scrnsave.scr')))) {
            New-ItemProperty -LiteralPath $key -Name $setting[0] -Value $setting[1] -PropertyType String -Force | Out-Null
        }
    } finally {
        if ($loadedHere) {
            [GC]::Collect(); [GC]::WaitForPendingFinalizers()
            & reg.exe unload ('HKU\' + [string]$SID) *> $null
            if ($LASTEXITCODE -ne 0) { throw 'Benutzer-Hive konnte nicht entladen werden.' }
        }
    }
}

function Test-DockerDesktopSettings {
    param([string]$ProfilePath)
    $path = Join-Path $ProfilePath 'AppData\Roaming\Docker\settings-store.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $path = Join-Path $ProfilePath 'AppData\Roaming\Docker\settings.json'
    }
    $settings = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    foreach ($requirement in @(@('autoStart',$true), @('exposeDockerAPIOnTCP2375',$false),
            @('autoDownloadUpdates',$false), @('disableUpdate',$true), @('silentModulesUpdate',$false))) {
        $property = $settings.PSObject.Properties[$requirement[0]]
        if ($null -eq $property -or $property.Value -isnot [bool] -or $property.Value -ne $requirement[1]) {
            throw ('Docker Desktop manuell in jnpt-dienst pruefen: ' + $requirement[0])
        }
    }
}

function Get-AutologonBinary {
    param([string]$ManifestDirectory = $PSScriptRoot)
    $rows = @([IO.File]::ReadAllLines((Join-Path $ManifestDirectory 'SHA256SUMS')) |
        Where-Object { $_ -cmatch '^[a-f0-9]{64}  Autologon64\.exe$' })
    if ($rows.Count -ne 1) { throw 'SHA-256-Pin fuer Autologon64.exe fehlt oder ist doppelt.' }
    $expected = $rows[0].Substring(0,64)
    $temp = Join-Path ([IO.Path]::GetTempPath()) ('jnpt-autologon-' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $zip = Join-Path $temp 'AutoLogon.zip'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://download.sysinternals.com/files/AutoLogon.zip' -OutFile $zip
        Expand-Archive -LiteralPath $zip -DestinationPath $temp
        $binary = Join-Path $temp 'Autologon64.exe'
        if ((Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) {
            throw 'SHA-256-Pruefung fuer Autologon64.exe fehlgeschlagen.'
        }
        $signature = Get-AuthenticodeSignature -FilePath $binary
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Microsoft Corporation(?:,|$)') {
            throw 'Authenticode fuer Autologon64.exe ungueltig.'
        }
        $destination = Join-Path $ManifestDirectory 'Autologon64.exe'
        Copy-Item -LiteralPath $binary -Destination $destination -Force
        return $destination
    } finally {
        $resolved = [IO.Path]::GetFullPath($temp)
        $root = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        if (-not $resolved.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw 'Temp-Pfad ungueltig.' }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

function Test-DienstAutologon {
    $key = Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
    return ($null -ne $key.PSObject.Properties['AutoAdminLogon'] -and $key.AutoAdminLogon -eq '1' -and
        $null -ne $key.PSObject.Properties['DefaultUserName'] -and $key.DefaultUserName -ieq 'jnpt-dienst' -and
        $null -ne $key.PSObject.Properties['DefaultDomainName'] -and $key.DefaultDomainName -ieq $env:COMPUTERNAME)
}

function Enable-DienstAutologon {
    param([string]$Binary, [Security.SecureString]$Password)
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    $previousPreference = $ErrorActionPreference
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        # Sysinternals requires a plaintext process argument. It is transient,
        # visible to privileged process inspection, and never logged here.
        try {
            # PS 5.1 turns redirected native stderr into ErrorRecords. Do not
            # let such records echo the secret or bypass the exit-code check.
            $ErrorActionPreference = 'Continue'
            & $Binary /accepteula 'jnpt-dienst' $env:COMPUTERNAME $plain *> $null
            $ErrorActionPreference = $previousPreference
            if ($LASTEXITCODE -ne 0) { throw 'Autologon fehlgeschlagen.' }
        } catch { throw 'Autologon fehlgeschlagen; Kennwort wird nicht ausgegeben.' }
    } finally {
        $ErrorActionPreference = $previousPreference
        $plain = $null
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    if (-not (Test-DienstAutologon)) { throw 'Autologon konnte nicht bestaetigt werden.' }
}

function Register-DienstTasks {
    $account = $env:COMPUTERNAME + '\jnpt-dienst'
    $principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $account
    $lock = New-ScheduledTaskAction -Execute ($env:SystemRoot + '\System32\rundll32.exe') -Argument 'user32.dll,LockWorkStation'
    Register-ScheduledTask -TaskName 'JanuaPort Sperren bei Anmeldung' -Action $lock -Trigger $logon -Principal $principal -Settings $settings -Force | Out-Null
    $ps = $env:SystemRoot + '\System32\WindowsPowerShell\v1.0\powershell.exe'
    $install = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $DienstDirectory -Argument ('-NoProfile -ExecutionPolicy Bypass -File "' + $DienstDirectory + '\einrichten.ps1"')
    # On demand only: the operator supplies the image tag in the initial
    # interactive commissioning session. Later runs reuse the existing .env.
    Register-ScheduledTask -TaskName 'JanuaPort Anlage starten' -Action $install -Principal $principal -Settings $settings -Force | Out-Null
    # EncodedCommand preserves roots ending in backslash and paths containing
    # apostrophes without Windows argv quoting changing the target.
    $backupCommand = "& '" + $DienstDirectory + "\jnpt-backup.ps1' -Target '" + $BackupTarget.Replace("'", "''") + "'"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($backupCommand))
    $backup = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $DienstDirectory -Argument ('-NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + $encoded)
    $daily = New-ScheduledTaskTrigger -Daily -At '20:00'
    Register-ScheduledTask -TaskName 'JanuaPort Sicherung' -Action $backup -Trigger $daily -Principal $principal -Settings $settings -Force | Out-Null
}

function Initialize-Dienst {
    Assert-Administrator
    if ($BackupTarget -match '["\r\n]' -or
        $BackupTarget -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$))') { throw 'Absolutes Sicherungsziel ohne Anfuehrungszeichen erforderlich.' }
    Test-ProfileFiles $PSScriptRoot
    $user = Get-LocalUser -Name 'jnpt-dienst' -ErrorAction SilentlyContinue
    $password = $null
    try {
        # Verify even on repeat runs. No other binary/fallback is accepted.
        $binary = Get-AutologonBinary $PSScriptRoot
        if ($null -eq $user) {
            $password = New-DienstPassword
            $user = New-LocalUser -Name 'jnpt-dienst' -Password $password -PasswordNeverExpires -AccountNeverExpires -Description 'JanuaPort Dienstbetrieb'
        } elseif ($KennwortNeu) {
            $password = New-DienstPassword
            Set-LocalUser -Name 'jnpt-dienst' -Password $password
        }
        $admins = Get-LocalGroup -SID 'S-1-5-32-544'
        if (@(Get-LocalGroupMember -Group $admins.Name | Where-Object { [string]$_.SID -eq [string]$user.SID }).Count -ne 0) {
            throw 'jnpt-dienst muss Standardbenutzer sein.'
        }
        if (-not $user.Enabled) { throw 'jnpt-dienst ist deaktiviert.' }
        # New-LocalUser alone need not grant interactive logon membership.
        # Resolve the built-in Users group by SID, independent of Windows locale.
        foreach ($group in @((Get-LocalGroup -SID 'S-1-5-32-545'), (Get-LocalGroup -Name 'docker-users'))) {
            if (@(Get-LocalGroupMember -Group $group.Name | Where-Object { [string]$_.SID -eq [string]$user.SID }).Count -eq 0) {
                Add-LocalGroupMember -Group $group.Name -Member $user
            }
        }
        $profilePath = Get-DienstProfilePath $user
        Protect-DienstRoot $user.SID
        $upgrade = Test-LegacyProfile $DienstDirectory
        New-Item -ItemType Directory -Path $DienstDirectory -Force | Out-Null
        Protect-DienstDirectory $DienstDirectory $user.SID
        foreach ($name in (@('SHA256SUMS') + $ProfileFiles)) {
            $destination = Join-Path $DienstDirectory $name
            $source = Join-Path $PSScriptRoot $name
            if (-not $upgrade -and (Test-Path -LiteralPath $destination) -and
                (Get-FileHash -LiteralPath $destination).Hash -cne (Get-FileHash -LiteralPath $source).Hash) {
                throw 'Vorhandenes Profil weicht ab; geprueftes Update erforderlich.'
            }
            if ($upgrade -or -not (Test-Path -LiteralPath $destination)) { Copy-Item -LiteralPath $source -Destination $destination }
        }
        Set-DienstScreenLock $profilePath $user.SID
        $wsl = Join-Path $profilePath '.wslconfig'
        $wslText = "[wsl2]`nmemory=4GB`n"
        if ((Test-Path -LiteralPath $wsl) -and [IO.File]::ReadAllText($wsl).Replace("`r`n","`n") -cne $wslText) {
            throw 'Vorhandene .wslconfig manuell mit Speichergrenze 4GB abstimmen.'
        }
        [IO.File]::WriteAllText($wsl, $wslText, (New-Object Text.UTF8Encoding($false)))
        foreach ($arguments in @(@('/hibernate','off'), @('/change','standby-timeout-ac','0'), @('/change','standby-timeout-dc','0'))) {
            & powercfg.exe @arguments *> $null
            if ($LASTEXITCODE -ne 0) { throw 'powercfg fehlgeschlagen.' }
        }
        Register-DienstTasks
        if ($null -ne $password) { Enable-DienstAutologon $binary $password }
        elseif (-not (Test-DienstAutologon)) { throw 'Autologon fehlt: bewusst mit -KennwortNeu erneut einrichten.' }
        Test-DockerDesktopSettings $profilePath
    } finally { if ($null -ne $password) { $password.Dispose() } }
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Initialize-Dienst; exit 0 } catch {
        [Console]::Error.WriteLine(('Diensteinrichtung fehlgeschlagen: ' + $_.Exception.Message))
        exit 1
    }
}
