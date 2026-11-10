#requires -Version 5.1
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

function Invoke-SessionLock {
    $sessionId = (Get-Process -Id $PID).SessionId
    # Bounded readiness wait; an explorer in another session is insufficient.
    for ($elapsed = 0; $elapsed -le 120; $elapsed++) {
        $explorer = @(Get-Process -Name explorer -ErrorAction SilentlyContinue |
            Where-Object { $_.SessionId -eq $sessionId })
        if ($explorer.Count -gt 0) { break }
        if ($elapsed -eq 120) { return 1 }
        Start-Sleep -Seconds 1
    }
    Initialize-SessionLockNative
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        # Neither the API return value nor a LogonUI process proves locking.
        # Verify WTS state even if LockWorkStation returns false.
        [Jnpt.SessionLock]::Lock() | Out-Null
        if ([Jnpt.SessionLock]::IsLocked()) { return 0 }
        if ($attempt -lt 12) { Start-Sleep -Seconds 5 }
    }
    return 1
}

if ($MyInvocation.InvocationName -ne '.') {
    # No log, user data or alternative action: Task Scheduler sees the failure.
    try { exit (Invoke-SessionLock) } catch { exit 1 }
}
