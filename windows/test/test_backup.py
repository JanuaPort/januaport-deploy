"""Real PS 5.1 backup entry/filesystem with a Docker executable shim on PATH."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from test_profile import ROOT, run, config
from test_install import ps

PATTERN = r'^jnpt-\d{8}T\d{9}Z-[a-f0-9]{32}\.jnpt-backup$'
OLD = 'jnpt-20000101T000000000Z-' + 'a' * 32 + '.jnpt-backup'
FOREIGN = {'jnpt.key': b'synthetic foreign fixture', 'foreign.jnpt-backup': b'foreign',
           OLD + '.extra': b'not an exact backup name'}

SHIM = r'''
import hashlib,json,os,pathlib,sys
a=sys.argv[1:]; root=pathlib.Path(os.environ['PROBE_ROOT']); mode=os.environ.get('PROBE_FAIL','')
with (root/'docker.jsonl').open('a') as f: f.write(json.dumps(a)+'\n')
if a[:1] != ['compose']: sys.exit(91)
a=a[1:]
# No shell, stat, sha256sum, rm or compose cp in this distroless boundary.
if a[:4]!=['exec','-T','jnpt','/jnpt']: sys.exit(92)
assert a[4:6]==['backup','--output'] and len(a)==7
assert a[6].startswith('/backups/') and '..' not in a[6]
if mode=='backup': sys.exit(11)
if mode!='source-missing':
    dst=root/'profile'/'backups'/pathlib.PurePosixPath(a[6]).name
    dst.write_bytes(b'' if mode=='empty' else b'synthetic backup contents\n')
'''


class Backup(unittest.TestCase):
    def invoke(self, mode='', marker=True, identity=True, extra='', existing=False, target_value=None, profile_complete=True):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            target = root / 'usb'
            target.mkdir()
            if marker:
                (target / '.jnpt-backup-ziel').write_text('JanuaPort backup v1\n')
            if existing:
                (target / 'old.jnpt-backup').write_bytes(b'old synthetic backup')
            profile = root / 'profile'
            profile.mkdir()
            (profile / 'docker-compose.yml').write_text('synthetic profile')
            if profile_complete:
                (profile / '.env').write_text('synthetic env')
            staging = profile / 'backups'
            staging.mkdir()
            for name, contents in FOREIGN.items(): (staging / name).write_bytes(contents)
            (staging / OLD).write_bytes(b'abandoned previous run')
            outside = root / OLD
            outside.write_bytes(b'outside staging')
            (root / 'docker_shim.py').write_text(SHIM)
            (root / 'docker.cmd').write_text('@echo off\n"' + sys.executable + '" "' +
                                            str(root / 'docker_shim.py') + '" %*\n')
            driver = root / 'driver.ps1'
            if target_value == '__relative_existing__':
                target_value = os.path.relpath(target, Path.cwd())
            elif target_value == '__root_relative_existing__':
                target_value = str(target)[2:]
            elif target_value == '__drive_relative_existing__':
                target_value = target.drive + os.path.relpath(target, Path.cwd())
            adapters = r'''
function Copy-Item { param($LiteralPath,$Destination,[switch]$Force)
    Add-Content (Join-Path $env:PROBE_ROOT 'copies.txt') $Destination
    Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Force:$Force
    if ($env:PROBE_FAIL -eq 'copy') {throw 'copy probe'}
    if ($env:PROBE_FAIL -eq 'size') {[IO.File]::AppendAllText($Destination,'extra')}
    if ($env:PROBE_FAIL -eq 'hash') {
        $bytes=[IO.File]::ReadAllBytes($Destination); $bytes[0]=0; [IO.File]::WriteAllBytes($Destination,$bytes)
    }
}
function Remove-Item { param($LiteralPath,[switch]$Force)
    if ($env:PROBE_FAIL -eq 'cleanup' -and $LiteralPath -like '*\backups\*' -and $LiteralPath -notlike '*20000101*') {throw 'cleanup probe'}
    Microsoft.PowerShell.Management\Remove-Item -LiteralPath $LiteralPath -Force:$Force
}
'''
            driver.write_text("$ErrorActionPreference='Stop'\n. '" + str(ROOT / 'jnpt-backup.ps1') +
                              "' -ProfileDirectory '" + str(profile) + "' -Target '" + (str(target) if target_value is None else target_value) + "'\n" +
                              ("function Get-CurrentAccount { $env:COMPUTERNAME + '\\jnpt-dienst' }\n" if identity else '') +
                              adapters + '\n' + extra + '\nStart-JnptBackup\n')
            env = {k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}
            env.update(PROBE_ROOT=tmp, PROBE_FAIL=mode, PATH=tmp + os.pathsep + env['PATH'])
            result = run('powershell.exe', '-NoProfile', '-File', str(driver), check=False, env=env)
            files = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
            self.staged = {p.name: p.read_bytes() for p in staging.iterdir() if p.is_file()}
            self.copies = (root / 'copies.txt').read_text().splitlines() if (root / 'copies.txt').exists() else []
            self.assertTrue(outside.is_file(), 'cleanup deleted a file outside staging')
            self.assertEqual(outside.read_bytes(), b'outside staging')
            calls = [json.loads(line) for line in (root / 'docker.jsonl').read_text().splitlines()] if (root / 'docker.jsonl').exists() else []
            return result, files, calls

    def test_success_renames_part_checks_hash_and_removes_container_copy(self):
        result, files, calls = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backups = [name for name in files if name != '.jnpt-backup-ziel']
        self.assertEqual(len(backups), 1, files)  # B-4: exactly one file, no key
        self.assertRegex(backups[0], PATTERN)
        self.assertEqual(files[backups[0]], b'synthetic backup contents\n')
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0][:7], ['compose','exec','-T','jnpt','/jnpt','backup','--output'])
        self.assertEqual(calls[0][7], '/backups/' + backups[0])
        self.assertEqual(self.staged, FOREIGN)
        self.assertEqual(len(self.copies), 1)
        self.assertTrue(self.copies[0].endswith('.teil'), self.copies)
        self.assertFalse(any(n.endswith('.teil') for n in files))
        self.assertNotIn('jnpt.key', files)

    def test_every_docker_and_verification_error_is_nonzero_without_target_file(self):
        for mode in ['backup', 'source-missing', 'empty', 'size', 'hash', 'copy', 'cleanup']:
            with self.subTest(mode=mode):
                result, files, calls = self.invoke(mode)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(set(files), {'.jnpt-backup-ziel'}, (mode, files))
                self.assertEqual(len(calls), 1, calls)
                self.assertTrue(all(self.staged.get(n) == b for n,b in FOREIGN.items()))
                if mode != 'cleanup': self.assertEqual(self.staged, FOREIGN)

    def test_host_size_gate_at_real_file_adapter(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            path = Path(tmp) / 'probe'
            path.write_bytes(b'synthetic size probe')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = ps("Assert-BackupCopy '" + str(path) + "' " + str(path.stat().st_size + 1) + " '" + digest + "'", ROOT / 'jnpt-backup.ps1')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Sicherungsgroesse', result.stderr)

    def test_native_docker_error_at_real_adapter(self):
        result, _, calls = self.invoke(mode='backup', extra="Invoke-BackupDocker @('exec','-T','jnpt','/jnpt','backup','--output','/backups/probe'); exit 0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)

    def test_exec_guard_rejects_non_jnpt_program_before_native_docker(self):
        for program in ['stat', 'sha256sum', 'rm', 'sh']:
            with self.subTest(program=program):
                result, _, calls = self.invoke(extra="Invoke-BackupDocker @('exec','-T','jnpt','" + program + "')")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])

    def test_cleanup_guard_rejects_foreign_filename_and_file_outside_staging(self):
        for path in ["(Join-Path $ProfileDirectory 'backups\\jnpt.key')", "(Join-Path $env:PROBE_ROOT '" + OLD + "')"]:
            with self.subTest(path=path):
                result, _, calls = self.invoke(extra='Remove-StagedBackup ' + path)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(calls, [])
                self.assertTrue(all(self.staged.get(n) == b for n,b in FOREIGN.items()))

    def test_compose_mount_is_relative_fixed_and_runtime_directory_ignored(self):
        self.assertIn('      - ./backups:/backups', (ROOT / 'docker-compose.yml').read_text())
        cfg = json.loads(config().stdout)
        mounts = [m for m in cfg['services']['jnpt']['volumes'] if m['target'] == '/backups']
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0]['type'], 'bind')
        self.assertEqual(Path(mounts[0]['source']), ROOT.resolve() / 'backups')
        self.assertFalse(mounts[0].get('read_only', False))
        self.assertEqual(run('git','-C',str(ROOT),'check-ignore','--no-index','backups/probe.jnpt-backup',check=False).returncode, 0)
        self.assertNotIn('  backups', (ROOT / 'SHA256SUMS').read_text())

    def test_both_installers_create_staging_directory(self):
        from test_install import Dienst
        result, _, _ = Dienst().fake_setup(repeat=False, extra=r'''
function Register-DienstTasks {
    if (-not (Test-Path -LiteralPath (Join-Path $DienstDirectory 'backups') -PathType Container)) {throw 'staging missing'}
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            from test_profile import PROFILE_FILES
            target = Path(tmp)
            for name in ('SHA256SUMS', *PROFILE_FILES): shutil.copyfile(ROOT / name, target / name)
            (target / '.env').write_text('synthetic env')
            script = r'''
function Get-CurrentAccount {$env:COMPUTERNAME+'\jnpt-dienst'}
function Invoke-Docker {param($Arguments)}
function Get-LeafFingerprint {'synthetic fingerprint'}
function Get-ServedLeafFingerprint {'synthetic fingerprint'}
function Invoke-WebRequest {[pscustomobject]@{StatusCode=200}}
Install-Profile
'''
            result = ps("$Directory='" + tmp + "'; " + script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / 'backups').is_dir())

    def test_missing_marker_aborts_before_docker(self):
        result, files, calls = self.invoke(marker=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(files, {})
        self.assertEqual(calls, [])

    def test_other_account_rejected_at_real_identity_adapter(self):
        result, files, calls = self.invoke(identity=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('jnpt-dienst', result.stderr)
        self.assertEqual(set(files), {'.jnpt-backup-ziel'})
        self.assertEqual(calls, [])

    def test_real_filesystem_rename_and_hash_errors_leave_no_backup(self):
        for extra in ["function Move-Item { throw 'rename probe' }",
                      "function Get-FileHash { throw 'hash read probe' }"]:
            with self.subTest(extra=extra):
                result, files, _ = self.invoke(extra=extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(set(files), {'.jnpt-backup-ziel'})
                self.assertEqual(self.staged, FOREIGN)

    def test_readback_detects_corruption_after_real_rename(self):
        extra = r'''
function Move-Item { param($LiteralPath,$Destination)
    Microsoft.PowerShell.Management\Move-Item -LiteralPath $LiteralPath -Destination $Destination
    [IO.File]::WriteAllText($Destination, 'corrupted synthetic backup')
}
'''
        result, files, calls = self.invoke(extra=extra)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(set(files), {'.jnpt-backup-ziel'})
        self.assertFalse(any('rm' in a for a in calls))
        self.assertEqual(self.staged, FOREIGN)

    def test_previous_backups_are_retained(self):
        result, files, _ = self.invoke(existing=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('old.jnpt-backup', files)
        self.assertEqual(files['old.jnpt-backup'], b'old synthetic backup')
        self.assertEqual(len(files), 3)

    def test_relative_or_empty_target_is_rejected(self):
        for target in ['', '__relative_existing__', '__root_relative_existing__', '__drive_relative_existing__']:
            with self.subTest(target=target):
                result, files, calls = self.invoke(target_value=target)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(set(files), {'.jnpt-backup-ziel'})
                self.assertEqual(calls, [])

    def test_incomplete_profile_rejected_before_docker(self):
        result, files, calls = self.invoke(profile_complete=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(set(files), {'.jnpt-backup-ziel'})
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
