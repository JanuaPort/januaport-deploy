# Only loaded by Python in a disposable directory. No system-changing adapter
# below calls its original. Missing/new adapters must be added here before use.
$script:events = New-Object 'Collections.Generic.List[string]'
$script:exists = $false
$script:member = $false
$script:autologon = $false
function Assert-Administrator { if ($env:PROBE_FAIL -eq 'admin') { throw 'admin' } }
function Get-LocalUser { param($Name) if ($script:exists) { [pscustomobject]@{Name=$Name; SID='S-1-5-21-100-100-100-1001'; Enabled=($env:PROBE_FAIL -ne 'disabled')} } }
function New-DienstPassword { ConvertTo-SecureString 'KANARIE-NICHT-ECHT' -AsPlainText -Force }
function New-LocalUser { param($Name,$Password,$Description,[switch]$PasswordNeverExpires,[switch]$AccountNeverExpires)
    $script:events.Add('new:'+$Name); $script:exists=$true; Get-LocalUser $Name }
function Set-LocalUser { param($Name,$Password) $script:events.Add('reset') }
function Get-LocalGroup { param($SID,$Name) [pscustomobject]@{Name=$(if ($SID -eq 'S-1-5-32-545') {'Users'} elseif ($SID) {'Administrators'} else {'docker-users'})} }
function Get-LocalGroupMember { param($Group)
    if (($Group -eq 'docker-users' -and $script:member) -or ($Group -eq 'Users' -and $script:usersMember) -or ($Group -eq 'Administrators' -and $env:PROBE_FAIL -eq 'privileged')) {
        [pscustomobject]@{SID='S-1-5-21-100-100-100-1001'}
    }
}
$script:usersMember = $false
function Add-LocalGroupMember { param($Group,$Member) $script:events.Add('group:'+$Group); if ($Group -eq 'Users') {$script:usersMember=$true} else {$script:member=$true} }
function Get-DienstProfilePath { param($User) Join-Path $env:PROBE_ROOT 'user' }
function Protect-DienstRoot { param($SID) $script:events.Add('root-acl'); if ($env:PROBE_FAIL -eq 'root-acl') {throw 'icacls failed'} }
function Protect-DienstDirectory { param($Path,$SID) $script:events.Add('acl') }
function Set-DienstScreenLock { param($ProfilePath,$SID) $script:events.Add('screen:60') }
function powercfg.exe { $script:events.Add('power:' + ($args -join ' ')); $global:LASTEXITCODE=0; if ($env:PROBE_FAIL -eq 'power') {$global:LASTEXITCODE=1} }
function Test-DockerDesktopSettings { param($ProfilePath) $script:events.Add('settings-read') }
function Get-AutologonBinary { $script:events.Add('binary-verified'); 'unused-test-binary' }
function Test-DienstAutologon { $script:autologon }
function Enable-DienstAutologon { param($Binary,$Password) $script:events.Add('autologon'); $script:autologon=$true }
function New-ScheduledTaskAction { param($Execute,$Argument,$WorkingDirectory) [pscustomobject]@{Execute=$Execute;Argument=$Argument;WorkingDirectory=$WorkingDirectory} }
function New-ScheduledTaskTrigger { param([switch]$AtLogOn,$User,[switch]$Daily,$At) [pscustomobject]@{Logon=[bool]$AtLogOn;User=$User;Daily=[bool]$Daily} }
function New-ScheduledTaskPrincipal { param($UserId,$LogonType,$RunLevel) [pscustomobject]@{UserId=$UserId;LogonType=$LogonType;RunLevel=$RunLevel} }
function New-ScheduledTaskSettingsSet { param([switch]$StartWhenAvailable,$MultipleInstances) 'settings' }
function Register-ScheduledTask { param($TaskName,$Action,$Trigger,$Principal,$Settings,[switch]$Force)
    $script:events.Add('task:'+$TaskName)
    if ($env:PROBE_FAIL -eq 'task') {throw 'task'}
    [pscustomobject]@{TaskName=$TaskName;Action=$Action;Trigger=$Trigger;Principal=$Principal} | ConvertTo-Json -Depth 6 -Compress | Add-Content (Join-Path $env:PROBE_ROOT 'tasks.jsonl')
}
function cmdkey.exe { throw 'FORBIDDEN cmdkey adapter called' }
function Start-Process { throw 'FORBIDDEN Start-Process adapter called' }
function reg.exe { throw 'FORBIDDEN real registry adapter called' }
function schtasks.exe { throw 'FORBIDDEN real task adapter called' }
