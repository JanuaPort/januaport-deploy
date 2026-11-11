"""Exercise the real Windows PowerShell 5.1 filesystem/hash adapter."""
from pathlib import Path
import os
import hashlib
import shutil
import tempfile
import unittest
import json
import zipfile
import base64

from test_profile import PROFILE_FILES, ROOT, run


def ps(script, source=ROOT / "einrichten.ps1", extra_env=None):
    # Passed as an argument, without an intervening shell.
    env = dict(os.environ)
    # PowerShell 7's inherited PSModulePath hides the standard 5.1 cmdlets.
    env = {key: value for key, value in env.items() if key.lower() != 'psmodulepath'}
    env.update(extra_env or {})
    return run("powershell", "-NoProfile", "-Command",
               "$ErrorActionPreference='Stop'; . '" + str(source) + "'; " + script,
               check=False, env=env)


class Installer(unittest.TestCase):
    def test_manifest_shape_and_allowed_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            for name in ('SHA256SUMS', '.env.example', *PROFILE_FILES):
                shutil.copyfile(ROOT / name, target / name)
            original = (target / 'SHA256SUMS').read_text()
            rows = original.splitlines()
            extra = hashlib.sha256((target / '.env.example').read_bytes()).hexdigest() + '  .env.example'
            cases = [(original + '../outside\n', 'Ungueltige'),
                     ('\n'.join([rows[0], rows[1], extra]) + '\n', 'Unerwarteter'),
                     (original + rows[0] + '\n', 'Unerwarteter'),
                     ('\n'.join(rows[:2]) + '\n', 'Unvollstaendige')]
            for manifest, message in cases:
                (target / 'SHA256SUMS').write_text(manifest)
                result = ps("Test-ProfileFiles '" + str(target) + "'")
                self.assertNotEqual(result.returncode, 0, manifest)
                self.assertIn(message, result.stderr)

    def test_real_checksum_adapter_rejects_corruption(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "test") as tmp:
            target = Path(tmp)
            for name in ('SHA256SUMS', *PROFILE_FILES):
                shutil.copyfile(ROOT / name, target / name)
            command = "Test-ProfileFiles '" + str(target) + "'"
            clean = ps(command)
            self.assertEqual(clean.returncode, 0, clean.stderr)
            for name in PROFILE_FILES:
                original = (target / name).read_bytes()
                (target / name).write_bytes(original + b"# corrupted\n")
                result = ps(command)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("SHA-256-Pruefung fehlgeschlagen", result.stderr)
                (target / name).write_bytes(original)

    def test_invalid_image_input_rejected(self):
        for value in ["", "sha256:bad", "sha256:" + "A" * 64,
                      "other.example/core:1", "x;exit 0", "$(exit 0)", "tag`nINJECTED=value"]:
            result = ps("Resolve-CoreImage '" + value + "'")
            self.assertNotEqual(result.returncode, 0, value)
            self.assertIn("Image-Tag oder sha256:", result.stderr)

    def test_existing_installation_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "test") as tmp:
            marker = Path(tmp) / ".env"
            marker.write_bytes(b"existing\n")
            result = ps("function Get-CurrentAccount {$env:COMPUTERNAME+'\\jnpt-dienst'}; $Directory='" + tmp + "'; Install-Profile")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Ziel existiert bereits", result.stderr)
            self.assertEqual(marker.read_bytes(), b"existing\n")


class Dienst(unittest.TestCase):
    def test_actual_nonadmin_session_rejected(self):
        # This test runner must be non-elevated. Never elevate it for B2/B3.
        result = ps('Assert-Administrator', ROOT / 'dienst-einrichten.ps1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Administrative PowerShell', result.stderr)

    def fake_setup(self, mode='', repeat=True, extra='', backup_target='E:\\Backup'):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            (target / 'user').mkdir()
            source = ROOT / 'dienst-einrichten.ps1'
            command = ". '" + str(Path(__file__).with_name('dienst_fakes.ps1')) + "'; "
            command += "$DienstDirectory='" + str(target / 'profile') + "'; $BackupTarget='" + backup_target.replace("'", "''") + "'; "
            command += extra + '; Initialize-Dienst; '
            if repeat:
                command += 'Initialize-Dienst; '
            command += "$script:events | ConvertTo-Json -Compress"
            result = ps(command, source, dict(PROBE_ROOT=tmp, PROBE_FAIL=mode))
            tasks = [json.loads(line) for line in (target / 'tasks.jsonl').read_text().splitlines()] if (target / 'tasks.jsonl').exists() else []
            wsl = (target / 'user' / '.wslconfig').read_text() if (target / 'user' / '.wslconfig').exists() else ''
            return result, tasks, wsl

    def test_account_tasks_idempotence_password_and_no_dpapi(self):
        result, tasks, wsl = self.fake_setup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('KANARIE-NICHT-ECHT', result.stdout + result.stderr)
        events = json.loads(result.stdout.strip())
        self.assertEqual(events.count('new:jnpt-dienst'), 1)
        self.assertEqual(events.count('group:docker-users'), 1)
        self.assertEqual(events.count('group:Users'), 1)
        self.assertEqual(events.count('autologon'), 1)
        self.assertEqual(len(tasks), 8)
        self.assertIn('memory=4GB', wsl)
        self.assertIn('screen:60', events)
        self.assertIn('power:/hibernate off', events)
        self.assertIn('power:/change standby-timeout-ac 0', events)
        self.assertIn('power:/change standby-timeout-dc 0', events)
        for task in tasks:
            self.assertEqual(task['Principal']['LogonType'], 'Interactive')
            self.assertEqual(task['Principal']['RunLevel'], 'Limited')
            self.assertTrue(task['Principal']['UserId'].endswith('\\jnpt-dienst'))
        actions = ' '.join(self.task_command(t) for t in tasks)
        self.assertIn('jnpt-sperren.ps1', actions)
        self.assertIn('jnpt-backup.ps1', actions)
        self.assertIn('jnpt-update.ps1', actions)
        self.assertIn('einrichten.ps1', actions)
        for task in tasks:
            if task['TaskName'] == 'JanuaPort Sperren bei Anmeldung':
                self.assertTrue(task['Trigger']['Logon'])
            elif task['TaskName'] == 'JanuaPort Sicherung':
                self.assertTrue(task['Trigger']['Daily'])
            else:
                self.assertIsNone(task['Trigger'])
        # cmdkey.exe is a trap in the fake: every credential write would fail.
        self.assertNotIn('FORBIDDEN', result.stderr)

    @staticmethod
    def task_command(task):
        argument = task['Action']['Argument'] or ''
        if '-EncodedCommand ' in argument:
            return base64.b64decode(argument.rsplit(' ', 1)[1]).decode('utf-16le')
        return argument

    def test_task_preserves_usb_root_apostrophe_and_dedicated_smb_target(self):
        for target in ['E:\\', "E:\\Back'up", r'\\backup-host\dedicated-share']:
            with self.subTest(target=target):
                result, tasks, _ = self.fake_setup(backup_target=target, repeat=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                backup = next(t for t in tasks if t['TaskName'] == 'JanuaPort Sicherung')
                self.assertTrue(self.task_command(backup).endswith("-Target '" + target.replace("'", "''") + "'; exit $LASTEXITCODE"))

    def test_update_task_is_on_demand_interactive_limited_ignore_new_and_encoded(self):
        for target in ['E:\\', "E:\\Back'up", r'\\backup-host\dedicated-share']:
            with self.subTest(target=target):
                result,tasks,_ = self.fake_setup(backup_target=target,repeat=False)
                self.assertEqual(result.returncode,0,result.stderr)
                update = [t for t in tasks if t['TaskName']=='JanuaPort Update']
                self.assertEqual(len(update),1)
                task=update[0]
                self.assertIsNone(task['Trigger'])
                self.assertEqual(task['Principal']['LogonType'],'Interactive')
                self.assertEqual(task['Principal']['RunLevel'],'Limited')
                self.assertTrue(task['Principal']['UserId'].endswith('\\jnpt-dienst'))
                self.assertEqual(task['Settings']['MultipleInstances'],'IgnoreNew')
                self.assertIn('-EncodedCommand ',task['Action']['Argument'])
                command=self.task_command(task)
                self.assertIn('jnpt-update.ps1',command)
                self.assertTrue(command.endswith("-Target '"+target.replace("'","''")+"'; exit $LASTEXITCODE"),command)
                self.assertTrue(task['Action']['WorkingDirectory'].endswith('profile'))

    def test_backup_and_update_encoded_commands_propagate_script_exit_codes(self):
        result,tasks,_ = self.fake_setup(repeat=False)
        self.assertEqual(result.returncode,0,result.stderr)
        for name in ['JanuaPort Sicherung', 'JanuaPort Update']:
            task = next(t for t in tasks if t['TaskName'] == name)
            command = self.task_command(task)
            with self.subTest(task=name):
                self.assertTrue(command.endswith('; exit $LASTEXITCODE'),command)
                # Execute the registered command with only its script path rebased
                # to an actual PS 5.1 child fixture; no real task is registered.
                with tempfile.TemporaryDirectory(prefix='task-') as tmp:
                    script_name = 'jnpt-backup.ps1' if name == 'JanuaPort Sicherung' else 'jnpt-update.ps1'
                    fixture = Path(tmp) / script_name
                    fixture.write_text('param($Target)\nexit ([int]$env:PROBE_EXIT)\n', encoding='utf-8')
                    original = str(Path(task['Action']['WorkingDirectory']) / script_name)
                    rebased = command.replace(original.replace("'", "''"), str(fixture).replace("'", "''"))
                    self.assertNotEqual(rebased,command)
                    encoded = base64.b64encode(rebased.encode('utf-16le')).decode('ascii')
                    for code in [0,2,3,6]:
                        with self.subTest(task=name,code=code):
                            env = {k:v for k,v in os.environ.items() if k.lower() != 'psmodulepath'}
                            env['PROBE_EXIT'] = str(code)
                            child = run('powershell.exe','-NoProfile','-EncodedCommand',encoded,env=env,check=False)
                            self.assertEqual(child.returncode,code,child.stdout+child.stderr)

    def test_setup_failure_never_prints_password(self):
        for mode in ['admin', 'privileged', 'disabled', 'root-acl', 'power', 'task']:
            with self.subTest(mode=mode):
                extra = '$script:exists=$true; $script:autologon=$true' if mode == 'privileged' else '$null=$null'
                result, _, _ = self.fake_setup(mode, repeat=False, extra=extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn({'admin': 'admin', 'privileged': 'Standardbenutzer',
                               'disabled': 'deaktiviert', 'root-acl': 'DACL', 'power': 'powercfg', 'task': 'task'}[mode], result.stderr)
                self.assertNotIn('KANARIE-NICHT-ECHT', result.stdout + result.stderr)

    def test_b7_root_is_protected_before_profile_files_and_tasks(self):
        result, _, _ = self.fake_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(result.stdout.strip())
        self.assertEqual(events.count('root-acl'), 2)
        self.assertLess(events.index('root-acl'), events.index('acl'))
        self.assertLess(events.index('root-acl'), next(i for i, event in enumerate(events) if event.startswith('task:')))

    def test_existing_account_requires_explicit_password_reset_without_autologon(self):
        result, _, _ = self.fake_setup(repeat=False, extra='$script:exists=$true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('KennwortNeu', result.stderr)
        result, _, _ = self.fake_setup(extra='$script:exists=$true; $KennwortNeu=$true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('reset', result.stdout)
        self.assertNotIn('KANARIE-NICHT-ECHT', result.stdout + result.stderr)

    def test_unsafe_task_target_rejected_before_any_account_creation(self):
        for value in ['', 'relative', 'C:relative', '\\relative', 'E:\\probe" -File other.ps1', 'E:\\probe\nextra']:
            with self.subTest(target=value):
                result, tasks, _ = self.fake_setup(backup_target=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(tasks, [])
                self.assertIn('Sicherungsziel', result.stderr)

    def test_conflicting_wsl_and_profile_files_are_preserved(self):
        for filename, prepare in [
            ('wsl', "Set-Content (Join-Path $env:PROBE_ROOT 'user\\.wslconfig') 'conflicting probe'"),
            ('profile', "New-Item -ItemType Directory $DienstDirectory | Out-Null; Set-Content (Join-Path $DienstDirectory 'README.md') 'conflicting probe'")]:
            with self.subTest(filename=filename):
                result, _, _ = self.fake_setup(repeat=False, extra=prepare)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Vorhanden', result.stderr)

    def test_actual_autologon_adapter_suppresses_native_password_output_and_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            binary = Path(tmp) / 'autologon.cmd'
            for code in [0, 12]:
                binary.write_text('@echo off\necho %*\necho %* 1>&2\nexit /b ' + str(code) + '\n')
                result = ps("function Test-DienstAutologon {$true}; Enable-DienstAutologon '" + str(binary) +
                            "' (ConvertTo-SecureString 'KANARIE-NICHT-ECHT' -AsPlainText -Force)", ROOT / 'dienst-einrichten.ps1')
                self.assertEqual(result.returncode == 0, code == 0, result.stderr)
                self.assertNotIn('KANARIE-NICHT-ECHT', result.stdout + result.stderr)

    def test_screen_lock_writes_secure_policy_and_hive_failures_abort(self):
        command = r'''
function Test-Path { $true }
function New-Item { }
function New-ItemProperty { param($LiteralPath,$Name,$Value,$PropertyType,[switch]$Force)
    Write-Output ($Name+'='+$Value)
    if ($LiteralPath -notlike '*\Software\Policies\Microsoft\Windows\Control Panel\Desktop') {throw 'wrong policy'}
}
function reg.exe {throw 'unexpected hive access'}
Set-DienstScreenLock 'unused' 'S-1-5-21-100-100-100-1001'
'''
        # Actual policy builder, with only registry adapters replaced. Its output
        # is suppressed by production, so capture writes in a fake side channel.
        command = command.replace("Write-Output ($Name+'='+$Value)", "$script:written += @($Name+'='+$Value)")
        result = ps("$script:written=@(); " + command + '; $script:written | ConvertTo-Json -Compress', ROOT / 'dienst-einrichten.ps1')
        self.assertEqual(result.returncode, 0, result.stderr)
        written = json.loads(result.stdout)
        for setting in ['ScreenSaveActive=1', 'ScreenSaveTimeOut=60', 'ScreenSaverIsSecure=1']:
            self.assertIn(setting, written)
        self.assertTrue(any(x.startswith('SCRNSAVE.EXE=') for x in written))
        result = ps("function Test-Path {$false}; function reg.exe {$global:LASTEXITCODE=1}; Set-DienstScreenLock 'unused' 'probe'", ROOT / 'dienst-einrichten.ps1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Hive', result.stderr)

    def test_real_filesystem_acl_is_limited_to_account_system_and_administrators(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            # TemporaryDirectory itself may already have a protected DACL.
            # Exercise an inheriting child so dropping access-rule protection is visible.
            target = Path(tmp) / 'inherited'
            target.mkdir()
            result = ps("$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User; " +
                        "if ((Get-Acl -LiteralPath '" + str(target) + "').AreAccessRulesProtected) {throw 'fixture must inherit'}; " +
                        "Protect-DienstDirectory '" + str(target) +
                        "' $sid; $acl=Get-Acl -LiteralPath '" + str(target) + "'; " +
                        "[pscustomobject]@{Protected=$acl.AreAccessRulesProtected; Entries=@($acl.Access | ForEach-Object {$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value}); User=$sid.Value} | ConvertTo-Json -Compress", ROOT / 'dienst-einrichten.ps1')
            self.assertEqual(result.returncode, 0, result.stderr)
            acl = json.loads(result.stdout)
            self.assertTrue(acl['Protected'])
            self.assertEqual(set(acl['Entries']), {'S-1-5-18', 'S-1-5-32-544', acl['User']})

    def test_wrong_hash_with_valid_signature_aborts_before_autologon(self):
        result = self.binary_probe(wrong_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA-256', result.stderr)
        self.assertNotIn('SIGNATURE-CHECKED', result.stdout)
        self.assertNotIn('AUTOLOGON-CALLED', result.stdout)

    def binary_probe(self, wrong_hash=False, signature='Valid', publisher='Microsoft Corporation', manifest='valid'):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            data = b'synthetic binary fixture'
            with zipfile.ZipFile(target / 'fixture.zip', 'w') as z:
                z.writestr('Autologon64.exe', data)
            digest = '0' * 64 if wrong_hash else hashlib.sha256(data).hexdigest()
            row = digest + '  Autologon64.exe\n'
            (target / 'SHA256SUMS').write_text('' if manifest == 'missing' else row * 2 if manifest == 'duplicate' else row)
            command = r'''
function Invoke-WebRequest { param($Uri,$OutFile,[switch]$UseBasicParsing)
    if ($Uri -cne 'https://download.sysinternals.com/files/AutoLogon.zip') {throw 'wrong URL'}
    Copy-Item (Join-Path $env:PROBE_ROOT 'fixture.zip') $OutFile
}
function Get-AuthenticodeSignature { param($FilePath)
    Write-Host 'SIGNATURE-CHECKED'
    [pscustomobject]@{Status=$env:PROBE_SIGNATURE;SignerCertificate=[pscustomobject]@{Subject=('CN=fixture, O='+$env:PROBE_PUBLISHER+', C=US')}}
}
function Enable-DienstAutologon { Write-Host 'AUTOLOGON-CALLED' }
$binary = Get-AutologonBinary $env:PROBE_ROOT
Enable-DienstAutologon $binary (ConvertTo-SecureString 'KANARIE-NICHT-ECHT' -AsPlainText -Force)
'''
            return ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp,
                      PROBE_SIGNATURE=signature, PROBE_PUBLISHER=publisher))

    def test_authenticode_and_publisher_are_second_gate(self):
        for status, publisher, good in [('Valid', 'Microsoft Corporation', True),
                                        ('NotSigned', 'Microsoft Corporation', False),
                                        ('Valid', 'Other Publisher', False)]:
            result = self.binary_probe(signature=status, publisher=publisher)
            self.assertEqual(result.returncode == 0, good, result.stderr)
            self.assertEqual('AUTOLOGON-CALLED' in result.stdout, good)

    def test_external_pin_missing_or_duplicate_aborts(self):
        for manifest in ['missing', 'duplicate']:
            result = self.binary_probe(manifest=manifest)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('SHA-256-Pin', result.stderr)
            self.assertNotIn('AUTOLOGON-CALLED', result.stdout)

    def test_docker_settings_are_read_only_and_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp) / 'AppData' / 'Roaming' / 'Docker'
            target.mkdir(parents=True)
            file = target / 'settings-store.json'
            good = dict(autoStart=True, exposeDockerAPIOnTCP2375=False, autoDownloadUpdates=False,
                        disableUpdate=True, silentModulesUpdate=False)
            for settings in [good, {}, dict(good, autoStart=False),
                             dict(good, exposeDockerAPIOnTCP2375=True), dict(good, autoDownloadUpdates=True),
                             dict(good, disableUpdate=False), dict(good, silentModulesUpdate=True),
                             dict(good, autoStart='true'), dict(good, autoStart=None)]:
                with self.subTest(settings=settings):
                    file.write_text(json.dumps(settings))
                    before = file.read_bytes()
                    result = ps("Test-DockerDesktopSettings '" + tmp + "'", ROOT / 'dienst-einrichten.ps1')
                    self.assertEqual(result.returncode == 0, settings == good, result.stderr)
                    self.assertEqual(file.read_bytes(), before)

    def test_installer_rejects_other_account_before_docker(self):
        result = ps("function docker {throw 'DOCKER-MUST-NOT-RUN'}; Install-Profile")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('jnpt-dienst', result.stderr)
        self.assertNotIn('DOCKER-MUST-NOT-RUN', result.stderr)

    def test_staged_profile_initializes_env_once_in_dienst_session(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            for name in ('SHA256SUMS', *PROFILE_FILES):
                shutil.copyfile(ROOT / name, target / name)
            command = r'''
function Get-CurrentAccount {$env:COMPUTERNAME+'\jnpt-dienst'}
function docker {throw 'unexpected native Docker'}
function Invoke-Docker {param($Arguments)}
function Read-Host {'synthetic-image'}
function Resolve-CoreImage { @('synthetic-image', ('1'*64)) }
function Get-LeafFingerprint { 'synthetic fingerprint' }
function Get-ServedLeafFingerprint { 'synthetic fingerprint' }
function Invoke-WebRequest { [pscustomobject]@{StatusCode=200} }
Install-Profile
function Read-Host {throw 'second prompt forbidden'}
Install-Profile
'''
            result = ps("$Directory='" + tmp + "'; " + command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((target / '.env').read_text(),
                             'JANUAPORT_IMAGE=synthetic-image\nJANUAPORT_IMAGE_DIGEST=' + '1' * 64 + '\n')


if __name__ == "__main__":
    unittest.main()
