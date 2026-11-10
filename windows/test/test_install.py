"""Exercise the real Windows PowerShell 5.1 filesystem/hash adapter."""
from pathlib import Path
import os
import hashlib
import shutil
import tempfile
import unittest
import json
import zipfile

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
            result = ps("$Directory='" + tmp + "'; Install-Profile")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Ziel existiert bereits", result.stderr)
            self.assertEqual(marker.read_bytes(), b"existing\n")


class Dienst(unittest.TestCase):
    def fake_setup(self, mode='', repeat=True, extra=''):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            (target / 'user').mkdir()
            source = ROOT / 'dienst-einrichten.ps1'
            command = ". '" + str(Path(__file__).with_name('dienst_fakes.ps1')) + "'; "
            command += "$DienstDirectory='" + str(target / 'profile') + "'; $BackupTarget='E:\\Backup'; "
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
        self.assertEqual(events.count('autologon'), 1)
        self.assertEqual(len(tasks), 6)
        self.assertIn('memory=4GB', wsl)
        self.assertIn('screen:60', events)
        self.assertIn('power:/hibernate off', events)
        self.assertIn('power:/change standby-timeout-ac 0', events)
        self.assertIn('power:/change standby-timeout-dc 0', events)
        for task in tasks:
            self.assertEqual(task['Principal']['LogonType'], 'Interactive')
            self.assertEqual(task['Principal']['RunLevel'], 'Limited')
            self.assertTrue(task['Principal']['UserId'].endswith('\\jnpt-dienst'))
        actions = ' '.join(t['Action']['Argument'] or '' for t in tasks)
        self.assertIn('LockWorkStation', actions)
        self.assertIn('jnpt-backup.ps1', actions)
        self.assertIn('einrichten.ps1', actions)
        # cmdkey.exe is a trap in the fake: every credential write would fail.
        self.assertNotIn('FORBIDDEN', result.stderr)

    def test_setup_failure_never_prints_password(self):
        for mode in ['admin', 'privileged', 'power', 'task']:
            with self.subTest(mode=mode):
                extra = '$script:exists=$true' if mode == 'privileged' else '$null=$null'
                result, _, _ = self.fake_setup(mode, repeat=False, extra=extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('KANARIE-NICHT-ECHT', result.stdout + result.stderr)

    def test_wrong_hash_with_valid_signature_aborts_before_autologon(self):
        result = self.binary_probe(wrong_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SHA-256', result.stderr)
        self.assertNotIn('SIGNATURE-CHECKED', result.stdout)
        self.assertNotIn('AUTOLOGON-CALLED', result.stdout)

    def binary_probe(self, wrong_hash=False, signature='Valid', publisher='Microsoft Corporation'):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            data = b'synthetic binary fixture'
            with zipfile.ZipFile(target / 'fixture.zip', 'w') as z:
                z.writestr('Autologon64.exe', data)
            digest = '0' * 64 if wrong_hash else hashlib.sha256(data).hexdigest()
            (target / 'SHA256SUMS').write_text(digest + '  Autologon64.exe\n')
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

    def test_docker_settings_are_read_only_and_fail_closed(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp) / 'AppData' / 'Roaming' / 'Docker'
            target.mkdir(parents=True)
            file = target / 'settings-store.json'
            good = dict(autoStart=True, exposeDockerAPIOnTCP2375=False, autoDownloadUpdates=False)
            for settings in [good, {}, dict(good, autoStart=False),
                             dict(good, exposeDockerAPIOnTCP2375=True), dict(good, autoDownloadUpdates=True)]:
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


if __name__ == "__main__":
    unittest.main()
