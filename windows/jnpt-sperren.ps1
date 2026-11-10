#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$SessionLockLogPath = 'C:\JanuaPort\windows\log\sperren.log'

function Initialize-SessionLockNative {
    if ('Jnpt.SessionLock' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace Jnpt {
    public static class SessionLock {
        [DllImport("user32.dll", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool LockWorkStation();
        [DllImport("wtsapi32.dll", EntryPoint="WTSQuerySessionInformationW", SetLastError=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool WTSQuerySessionInformation(IntPtr server, int session, int info, out IntPtr buffer, out int bytes);
        [DllImport("wtsapi32.dll")]
        private static extern void WTSFreeMemory(IntPtr buffer);

        public static bool Lock() { return LockWorkStation(); }

        public static bool IsLocked() {
            const int WTS_CURRENT_SESSION = -1;
            const int WTSSessionInfoEx = 26;
            // Windows 10/11: LOCK=0, UNLOCK=1 (not the inverted Win7 values).
            const int WTS_SESSIONSTATE_LOCK = 0;
            IntPtr buffer = IntPtr.Zero;
            int bytes;
            try {
                bool queried = WTSQuerySessionInformation(IntPtr.Zero, WTS_CURRENT_SESSION,
                    WTSSessionInfoEx, out buffer, out bytes);
                // WTSINFOEXW: DWORD Level, 8-byte aligned Data union;
                // LEVEL1 starts with SessionId, SessionState, SessionFlags.
                // Only read this fixed prefix, identically laid out on x86/x64.
                return queried && buffer != IntPtr.Zero && bytes >= 20 &&
                    Marshal.ReadInt32(buffer, 0) == 1 &&
                    Marshal.ReadInt32(buffer, 16) == WTS_SESSIONSTATE_LOCK;
            } finally {
                if (buffer != IntPtr.Zero) { WTSFreeMemory(buffer); }
            }
        }
    }
}
'@ | Out-Null
}

function Get-SessionLockElapsedSeconds {
    param($Timer)
    return $Timer.Elapsed.TotalSeconds
}

function Invoke-SessionLock {
    param($Result)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $sessionId = (Get-Process -Id $PID).SessionId
    # One deadline covers readiness and locking. No fixed logon delay.
    while ((Get-SessionLockElapsedSeconds $timer) -lt 120) {
        $explorer = @(Get-Process -Name explorer -ErrorAction SilentlyContinue |
            Where-Object { $_.SessionId -eq $sessionId })
        if ($explorer.Count -gt 0) {
            Initialize-SessionLockNative
            $Result.Attempts++
            # Neither API return value nor a LogonUI process proves locking.
            [Jnpt.SessionLock]::Lock() | Out-Null
            if ([Jnpt.SessionLock]::IsLocked()) {
                $Result.LockedAt = [DateTime]::UtcNow.ToString('o')
                $Result.ExitCode = 0
                return
            }
        }
        Start-Sleep -Milliseconds 1000
    }
    # Timeout leaves result failed.
}

function Write-SessionLockResult {
    param([DateTime]$Started, $Result)
    $line = "{0}`t{1}`tattempts={2}`texit={3}" -f $Started.ToString('o'), $Result.LockedAt, $Result.Attempts, $Result.ExitCode
    $lines = @()
    if (Test-Path -LiteralPath $SessionLockLogPath -PathType Leaf) {
        $lines = @(Get-Content -LiteralPath $SessionLockLogPath -Tail 99)
    }
    $lines += $line
    [IO.File]::WriteAllLines($SessionLockLogPath, [string[]]$lines, (New-Object Text.UTF8Encoding($false)))
}

if ($MyInvocation.InvocationName -ne '.') {
    $started = [DateTime]::UtcNow
    $result = @{LockedAt='nicht_gesperrt'; Attempts=0; ExitCode=1}
    try { Invoke-SessionLock $result } catch { }
    # One bounded audit line, no identity or exception text. No alternative action.
    try { Write-SessionLockResult $started $result } catch { exit 1 }
    exit $result.ExitCode
}
