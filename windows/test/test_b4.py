"""B4: real PS 5.1 control flow and file adapters, only system calls faked."""
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from test_install import ps
from test_profile import ROOT, run

MESSAGE = ('Docker Desktop einmal in jnpt-dienst starten und die Einstellungen '
           'pruefen (AutoStart an, 2375 aus, Auto-Update aus)')

class B4(unittest.TestCase):
    def test_logon_task_has_no_delay_and_fixed_script(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            command = ". '" + str(Path(__file__).with_name('dienst_fakes.ps1')) + "'; "
            command += "$BackupTarget='E:\\Backup'; Register-DienstTasks"
            result = ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            tasks = [json.loads(line) for line in (Path(tmp) / 'tasks.jsonl').read_text().splitlines()]
            task = next(t for t in tasks if t['TaskName'] == 'JanuaPort Sperren bei Anmeldung')
            self.assertIn(task['Trigger'].get('Delay'), [None, '', 'PT0S'])
            self.assertTrue(task['Trigger']['Logon'])
            # N7 (B4): Windows Terminal ignoriert -WindowStyle Hidden; conhost --headless öffnet kein Fenster.
            self.assertEqual(task['Action']['Execute'].lower(),
                             (os.environ['SystemRoot'] + r'\System32\conhost.exe').lower())
            self.assertEqual(task['Action']['Argument'],
                             '--headless "' + os.environ['SystemRoot'] + r'\System32\WindowsPowerShell\v1.0\powershell.exe'
                             + '" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden '
                             '-File "C:\\JanuaPort\\windows\\jnpt-sperren.ps1"')

    def lock_probe(self, explorer_after=0, locked_after=1, native_error=False, seed_log=False, log_failure=False):
        source = ROOT / 'jnpt-sperren.ps1'
        self.assertTrue(source.is_file(), 'lock script must be shipped')
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            # Managed native-boundary fake; production user32/wtsapi32 never load.
            bootstrap = r'''
Add-Type -TypeDefinition @'
using System;
using System.IO;
namespace Jnpt {
    public static class SessionLock {
        static int calls;
        static void Trace(string s) { File.AppendAllText(Environment.GetEnvironmentVariable("PROBE_TRACE"), s + "\n"); }
        public static bool Lock() { calls++; Trace("lock"); return false; }
        public static bool IsLocked() {
            Trace("verify");
            if (Environment.GetEnvironmentVariable("PROBE_ERROR") == "yes") throw new Exception("private data must stay silent");
            return calls >= int.Parse(Environment.GetEnvironmentVariable("PROBE_LOCKED_AFTER"));
        }
    }
}
'@
$script:elapsed = 0
$SessionLockLogPath = $env:PROBE_LOG
function Get-SessionLockElapsedSeconds { param($Timer) $script:elapsed / 1000 }
function Add-Type { throw 'FORBIDDEN real native binding' }
function Start-Sleep { param($Seconds,$Milliseconds)
    $ms = if ($Milliseconds) {$Milliseconds} else {1000*$Seconds}
    $script:elapsed += $ms
    Add-Content $env:PROBE_TRACE ('sleep:'+$ms)
}
function Get-Process { param($Id,$Name,$ErrorAction)
    if ($PSBoundParameters.ContainsKey('Id')) { return [pscustomobject]@{SessionId=7} }
    if ($Name -ne 'explorer') { throw 'unexpected process query' }
    Add-Content $env:PROBE_TRACE ('explorer:'+$script:elapsed)
    [pscustomobject]@{SessionId=8}
    if ($script:elapsed -ge [int]$env:PROBE_EXPLORER_AFTER) { [pscustomobject]@{SessionId=7} }
}
function Stop-Computer { Add-Content $env:PROBE_TRACE 'FORBIDDEN shutdown'; throw 'FORBIDDEN shutdown' }
function Restart-Computer { Add-Content $env:PROBE_TRACE 'FORBIDDEN restart'; throw 'FORBIDDEN restart' }
function shutdown.exe { Add-Content $env:PROBE_TRACE 'FORBIDDEN shutdown'; throw 'FORBIDDEN shutdown' }
function logoff.exe { Add-Content $env:PROBE_TRACE 'FORBIDDEN logoff'; throw 'FORBIDDEN logoff' }
'''
            # Actual -File entry and exit handler; inject boundary fakes only.
            text = source.read_text(encoding='utf-8-sig')
            anchor = "if ($MyInvocation.InvocationName -ne '.')"
            self.assertIn(anchor, text)
            script = root / 'probe.ps1'
            script.write_text(text.replace(anchor, bootstrap + '\n' + anchor), encoding='utf-8-sig')
            env = {k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}
            log = root / ('missing/sperren.log' if log_failure else 'sperren.log')
            if seed_log:
                log.write_text('2000-01-01T00:00:00.0000000Z\tnicht_gesperrt\tattempts=0\texit=1\n' * 105)
            env.update(PROBE_TRACE=str(root / 'trace'), PROBE_LOG=str(log), PROBE_EXPLORER_AFTER=str(explorer_after),
                       PROBE_LOCKED_AFTER=str(locked_after), PROBE_ERROR='yes' if native_error else 'no')
            result = run('powershell', '-NoProfile', '-File', str(script), env=env, check=False)
            trace = (root / 'trace').read_text().splitlines()
            self.assertEqual(result.stdout + result.stderr, '', 'exit code is the only output')
            self.assertFalse(any(s.startswith('FORBIDDEN') for s in trace), trace)
            if log_failure:
                self.assertFalse(log.exists())
            else:
                self.assertTrue(log.is_file(), 'exactly one log entry per invocation is required')
                lines = log.read_text().splitlines()
                self.assertEqual(len(lines), 100 if seed_log else 1)
                timestamp = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{7}Z'
                self.assertRegex(lines[-1], '^' + timestamp + '\t(?:' + timestamp + r'|nicht_gesperrt)\tattempts=\d+\texit=[01]$')
                self.assertEqual(lines[-1].split('\t')[2:], ['attempts=' + str(trace.count('lock')), 'exit=' + str(result.returncode)])
                if not result.returncode:
                    self.assertNotIn('nicht_gesperrt', lines[-1])
                self.assertNotIn('jnpt-dienst', lines[-1])
                self.assertNotIn(os.environ.get('USERNAME', 'unused-user'), lines[-1])
            return result, trace

    def test_lock_own_explorer_then_first_verified_success(self):
        result, trace = self.lock_probe(explorer_after=2000)
        self.assertEqual(result.returncode, 0)
        self.assertIn('explorer:2000', trace)
        self.assertGreater(trace.index('lock'), trace.index('explorer:2000'))
        self.assertEqual(trace.count('lock'), 1)
        self.assertEqual(trace.count('verify'), 1)

    def test_lock_retries_until_verified(self):
        result, trace = self.lock_probe(locked_after=3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual([s for s in trace if s in ('lock', 'verify', 'sleep:1000')],
                         ['lock', 'verify', 'sleep:1000', 'lock', 'verify', 'sleep:1000', 'lock', 'verify'])
        self.assertFalse(any(s.startswith('sleep:') and s != 'sleep:1000' for s in trace))

    def test_unlocked_after_all_attempts_is_failure(self):
        result, trace = self.lock_probe(locked_after=999)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(trace.count('lock'), 120)
        self.assertEqual(trace.count('verify'), 120)
        self.assertEqual(trace.count('sleep:1000'), 120)

    def test_readiness_and_lock_share_one_120_second_budget(self):
        result, trace = self.lock_probe(explorer_after=118000, locked_after=999)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(trace.count('lock'), 2)
        self.assertEqual(trace.count('sleep:1000'), 120)

    def test_log_is_bounded_to_last_100_lines(self):
        result, _ = self.lock_probe(seed_log=True)
        self.assertEqual(result.returncode, 0)

    def test_log_failure_is_silent_and_nonzero(self):
        result, _ = self.lock_probe(log_failure=True)
        self.assertNotEqual(result.returncode, 0)

    def test_setup_creates_log_directory_before_registering_task(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            (root / 'user').mkdir()
            command = ". '" + str(Path(__file__).with_name('dienst_fakes.ps1')) + "'; "
            command += r'''
$DienstDirectory=Join-Path $env:PROBE_ROOT 'profile'
$BackupTarget='E:\Backup'
function Register-DienstTasks {
    if (-not (Test-Path -LiteralPath (Join-Path $DienstDirectory 'log') -PathType Container)) { throw 'log directory missing' }
}
Initialize-Dienst
'''
            result = ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp, PROBE_FAIL=''))
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_foreign_explorer_cannot_allow_lock_and_wait_is_bounded(self):
        result, trace = self.lock_probe(explorer_after=121000)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('lock', trace)
        self.assertEqual(sum(int(s.split(':')[1]) for s in trace if s.startswith('sleep:')), 120000)

    def test_native_failure_is_silent_and_nonzero(self):
        result, _ = self.lock_probe(native_error=True)
        self.assertNotEqual(result.returncode, 0)

    def test_wts_adapter_decodes_only_locked_current_session_and_frees_buffer(self):
        source = ROOT / 'jnpt-sperren.ps1'
        self.assertTrue(source.is_file(), 'lock script must be shipped')
        native = source.read_text().split("@'", 1)[1].split("'@", 1)[0]
        # Keep the production C# query, validation, decoding and finally block.
        # Replace P/Invoke declarations ONLY, before compilation. No native DLL.
        replacements = {
            'LockWorkStation': 'private static bool LockWorkStation() { throw new Exception("must not lock"); }',
            'WTSQuerySessionInformation': '''
private static bool WTSQuerySessionInformation(IntPtr server, int session, int info, out IntPtr buffer, out int bytes) {
    if (server != IntPtr.Zero || session != -1 || info != 26) throw new Exception("wrong WTS target");
    buffer = Marshal.AllocHGlobal(20); bytes = 20;
    Marshal.WriteInt32(buffer, 0, 1);
    Marshal.WriteInt32(buffer, 8, 7);
    Marshal.WriteInt32(buffer, 12, 0);
    Marshal.WriteInt32(buffer, 16, int.Parse(Environment.GetEnvironmentVariable("PROBE_FLAGS")));
    string mode = Environment.GetEnvironmentVariable("PROBE_WTS");
    if (mode == "short") bytes = 16;
    if (mode == "level") Marshal.WriteInt32(buffer, 0, 2);
    return mode != "failed";
}''',
            'WTSFreeMemory': '''private static void WTSFreeMemory(IntPtr buffer) {
    Marshal.FreeHGlobal(buffer); File.AppendAllText(Environment.GetEnvironmentVariable("PROBE_TRACE"), "free");
}''',
        }
        for name, replacement in replacements.items():
            pattern = r'\[DllImport\([^\]]+\)\]\s*(?:\[return:[^\]]+\]\s*)?private static extern [^;]+\b' + name + r'\([^;]+;'
            native, count = re.subn(pattern, lambda _: replacement, native)
            self.assertEqual(count, 1, name)
        native = 'using System.IO;\n' + native
        for flags, mode, expected in [(0, 'ok', True), (1, 'ok', False), (-1, 'ok', False),
                                      (0, 'short', False), (0, 'level', False), (0, 'failed', False)]:
            with self.subTest(flags=flags, mode=mode), tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
                trace = Path(tmp) / 'trace'
                command = "Add-Type -TypeDefinition @'\n" + native + "\n'@\n[Jnpt.SessionLock]::IsLocked()"
                result = ps(command, ROOT / 'dienst-einrichten.ps1',
                            dict(PROBE_FLAGS=str(flags), PROBE_WTS=mode, PROBE_TRACE=str(trace)))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(expected))
                self.assertEqual(trace.read_text(), 'free')

    def autologon_probe(self, ready_after):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            binary = Path(tmp) / 'autologon.cmd'
            binary.write_text('@echo off\nexit /b 0\n')
            command = r'''
$script:elapsed=0
$script:reads=0
function Start-Sleep { param($Milliseconds) $script:elapsed += $Milliseconds }
function Get-ItemProperty { param($LiteralPath)
    if ($LiteralPath -ne 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon') {throw 'wrong registry adapter'}
    $script:reads++
    if ($script:elapsed -ge [int]$env:PROBE_READY_AFTER) {
        [pscustomobject]@{AutoAdminLogon='1'; DefaultUserName='jnpt-dienst'; DefaultDomainName=$env:COMPUTERNAME}
    } else { [pscustomobject]@{AutoAdminLogon='0'; DefaultUserName='other'; DefaultDomainName=$env:COMPUTERNAME} }
}
try {
    Enable-DienstAutologon $env:PROBE_BINARY (ConvertTo-SecureString 'synthetic probe' -AsPlainText -Force)
    $ok=$true
} catch { $ok=$false }
@{ok=$ok; elapsed=$script:elapsed; reads=$script:reads} | ConvertTo-Json -Compress
'''
            result = ps(command, ROOT / 'dienst-einrichten.ps1',
                        dict(PROBE_BINARY=str(binary), PROBE_READY_AFTER=str(ready_after)))
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_autologon_delayed_registry_values_are_confirmed(self):
        state = self.autologon_probe(2000)
        self.assertTrue(state['ok'])
        self.assertEqual(state['elapsed'], 2000)
        self.assertEqual(state['reads'], 5)

    def test_autologon_missing_values_fail_within_ten_seconds(self):
        state = self.autologon_probe(11000)
        self.assertFalse(state['ok'])
        self.assertEqual(state['elapsed'], 10000)
        self.assertEqual(state['reads'], 21)

    def test_missing_settings_real_file_adapter_has_fixed_message_and_error_exit(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            result = ps("try { Test-DockerDesktopSettings '" + tmp +
                        "'; exit 0 } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }",
                        ROOT / 'dienst-einrichten.ps1')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stderr.strip(), MESSAGE)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_settings_store_and_legacy_settings_remain_readable(self):
        good = dict(autoStart=True, exposeDockerAPIOnTCP2375=False, autoDownloadUpdates=False,
                    disableUpdate=True, silentModulesUpdate=False)
        for name in ['settings-store.json', 'settings.json']:
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
                folder = Path(tmp) / 'AppData' / 'Roaming' / 'Docker'
                folder.mkdir(parents=True)
                file = folder / name
                file.write_text(json.dumps(good))
                before = file.read_bytes()
                result = ps("Test-DockerDesktopSettings '" + tmp + "'", ROOT / 'dienst-einrichten.ps1')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(file.read_bytes(), before)

if __name__ == '__main__':
    unittest.main()
