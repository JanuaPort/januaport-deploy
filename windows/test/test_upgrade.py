"""0.1.0/0.2.0 -> 0.3.0 through real PS 5.1 file/hash adapters, with transport fakes."""
import json
import base64
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_install import ps
from test_profile import PROFILE_FILES, ROOT, verify_sums

LEGACY_FILES = ('docker-compose.yml', 'Caddyfile', 'einrichten.ps1')
OLD_B4_FILES = tuple(row.split('  ')[1] for row in subprocess.check_output(['git','show','windows-v0.2.0:windows/SHA256SUMS'],text=True).splitlines() if not row.endswith('  Autologon64.exe'))
UPGRADE_BLOCKED = 'Upgrade gesperrt: eine Profildatei weicht vom ausgelieferten Stand ab (SHA256SUMS). Datei prüfen oder zurücksetzen.'


class Upgrade(unittest.TestCase):
    def exercise(self, mode='', manifest=False, release='windows-v0.1.0', altered='docker-compose.yml', capture_error=False):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            target = root / 'profile'
            target.mkdir()
            # Read exact published bytes, never execute the old installer.
            for name in (LEGACY_FILES if release=='windows-v0.1.0' else OLD_B4_FILES) + (('SHA256SUMS',) if manifest else ()):
                (target / name).write_bytes(subprocess.check_output(
                    ['git', 'show', release + ':windows/' + name]))
            (target / '.env').write_bytes(b'# synthetic retained environment\r\nJANUAPORT_IMAGE=synthetic-image\r\n')
            (target / 'secrets').mkdir()
            for name in ('smtp_password', 'graph_client_secret', 'operator-file'):
                (target / 'secrets' / name).write_bytes(b'synthetic retained contents\r\n')
            if mode == 'missing-base':
                (target / 'Caddyfile').unlink()
            if mode == 'modified-base':
                with (target / altered).open('ab') as file:
                    file.write(b'# synthetic local change\n')
            before = {p.relative_to(target).as_posix(): p.read_bytes()
                      for p in target.rglob('*') if p.is_file()}
            command = r'''
$Directory = Join-Path $env:PROBE_ROOT 'profile'
function Get-CurrentAccount {$env:COMPUTERNAME+'\jnpt-dienst'}
function docker {throw 'unexpected native Docker'}
function Invoke-Docker {param($Arguments)
    ($Arguments -join ' ') | Add-Content (Join-Path $env:PROBE_ROOT 'docker.txt')
}
function Read-Host {throw 'image prompt forbidden during upgrade'}
function Resolve-CoreImage {throw 'image resolution forbidden during upgrade'}
function Get-LeafFingerprint {'synthetic fingerprint'}
function Get-ServedLeafFingerprint {'synthetic fingerprint'}
function Invoke-WebRequest {param($Uri,$OutFile,[switch]$UseBasicParsing,$TimeoutSec)
    if ($OutFile) {
        $base='https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.3.0/windows/'
        if (-not $Uri.StartsWith($base, [StringComparison]::Ordinal)) {throw 'wrong release URL'}
        $name=$Uri.Substring($base.Length)
        $name | Add-Content (Join-Path $env:PROBE_ROOT 'downloads.txt')
        if ($env:PROBE_FAIL -eq 'download' -and $name -eq 'jnpt-backup.ps1') {throw 'synthetic download failure'}
        Copy-Item -LiteralPath (Join-Path $env:PROBE_SOURCE $name) -Destination $OutFile
        if ($env:PROBE_FAIL -eq 'corrupt' -and $name -eq 'README.md') {Add-Content $OutFile 'synthetic corruption'}
    } else { [pscustomobject]@{StatusCode=200} }
}
Install-Profile
Test-ProfileFiles $Directory
Install-Profile
'''
            if capture_error:
                # Read the exact .NET message without locale-dependent native
                # console decoding between PS 5.1 and Python.
                command = 'try {\n' + command + '\n} catch { [Console]::Error.WriteLine([Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($_.Exception.Message))); exit 1 }'
            result = ps(command, extra_env=dict(PROBE_ROOT=tmp, PROBE_SOURCE=str(ROOT), PROBE_FAIL=mode))
            if capture_error and result.returncode:
                result.stderr = base64.b64decode(result.stderr.strip()).decode('utf-16le') + '\n'
            after = {p.relative_to(target).as_posix(): p.read_bytes()
                     for p in target.rglob('*') if p.is_file()}
            downloads = (root / 'downloads.txt').read_text().splitlines() if (root / 'downloads.txt').exists() else []
            docker = (root / 'docker.txt').read_text() if (root / 'docker.txt').exists() else ''
            if result.returncode == 0:
                verify_sums(target)
            return result, before, after, downloads, docker

    def test_b4_published_profile_upgrades_to_b5_preserving_local_data(self):
        for manifest in [False,True]:
            with self.subTest(manifest=manifest):
                r,before,after,downloads,docker=self.exercise(manifest=manifest,release='windows-v0.2.0')
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertCountEqual(downloads,['SHA256SUMS',*PROFILE_FILES])
                self.assertEqual(docker.count('compose up -d'),2)
                for name in ('.env','secrets/smtp_password','secrets/graph_client_secret','secrets/operator-file'):
                    self.assertEqual(before[name],after[name])
                for name in ('SHA256SUMS',*PROFILE_FILES): self.assertEqual(after[name],(ROOT/name).read_bytes())

    def test_modified_or_incomplete_b4_profile_is_rejected_before_download(self):
        for mode in ['modified-base','missing-base']:
            r,before,after,downloads,docker=self.exercise(mode=mode,release='windows-v0.2.0')
            self.assertNotEqual(r.returncode,0)
            self.assertEqual(before,after); self.assertEqual(downloads,[])
            self.assertNotIn('compose up',docker)

    def test_modified_original_reports_exact_upgrade_block_without_file_contents(self):
        for release,files in [('windows-v0.1.0',LEGACY_FILES),('windows-v0.2.0',OLD_B4_FILES)]:
            for altered in files:
                with self.subTest(release=release,altered=altered):
                    r,before,after,downloads,docker=self.exercise(mode='modified-base',release=release,
                                                                altered=altered,capture_error=True)
                    self.assertNotEqual(r.returncode,0)
                    self.assertEqual(r.stderr.strip(),UPGRADE_BLOCKED)
                    self.assertEqual(before,after); self.assertEqual(downloads,[])
                    self.assertNotIn('compose up',docker)

    def test_missing_original_remains_a_separate_incomplete_profile_error(self):
        for release in ['windows-v0.1.0','windows-v0.2.0']:
            with self.subTest(release=release):
                r,before,after,downloads,docker=self.exercise(mode='missing-base',release=release,capture_error=True)
                self.assertNotEqual(r.returncode,0)
                self.assertEqual(r.stderr.strip(),'Ziel existiert bereits und ist kein vollstaendiges Profil.')
                self.assertEqual(before,after); self.assertEqual(downloads,[])

    def test_local_dienst_staging_also_upgrades_b4_and_rejects_every_changed_file(self):
        for altered in [None,*OLD_B4_FILES]:
            with self.subTest(altered=altered),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); target=root/'profile'; target.mkdir(); (root/'user').mkdir()
                for name in OLD_B4_FILES:
                    (target/name).write_bytes(subprocess.check_output(['git','show','windows-v0.2.0:windows/'+name]))
                (target/'.env').write_bytes(b'synthetic retained env\r\n')
                if altered: (target/altered).write_bytes((target/altered).read_bytes()+b'# changed\n')
                command=". '"+str(Path(__file__).with_name('dienst_fakes.ps1'))+"'; "
                command+="$DienstDirectory=Join-Path $env:PROBE_ROOT 'profile'; $BackupTarget='E:\\Backup'; Initialize-Dienst"
                result=ps(command,ROOT/'dienst-einrichten.ps1',dict(PROBE_ROOT=tmp,PROBE_FAIL=''))
                self.assertEqual(result.returncode==0,altered is None,result.stderr)
                self.assertEqual((target/'.env').read_bytes(),b'synthetic retained env\r\n')
                if altered: self.assertIn('Vorhandenes Profil weicht ab',result.stderr)
                else: verify_sums(target)

    def test_local_dienst_staging_also_upgrades_legacy_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            target = root / 'profile'
            target.mkdir()
            (root / 'user').mkdir()
            for name in LEGACY_FILES:
                (target / name).write_bytes(subprocess.check_output(['git', 'show', 'windows-v0.1.0:windows/' + name]))
            (target / '.env').write_bytes(b'synthetic environment\r\n')
            (target / 'secrets').mkdir()
            (target / 'secrets' / 'smtp_password').write_bytes(b'synthetic retained mail contents')
            command = ". '" + str(Path(__file__).with_name('dienst_fakes.ps1')) + "'; "
            command += "$DienstDirectory=Join-Path $env:PROBE_ROOT 'profile'; $BackupTarget='E:\\Backup'; Initialize-Dienst; Test-ProfileFiles $DienstDirectory"
            result = ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp, PROBE_FAIL=''))
            self.assertEqual(result.returncode, 0, result.stderr)
            verify_sums(target)
            self.assertEqual((target / '.env').read_bytes(), b'synthetic environment\r\n')
            self.assertEqual((target / 'secrets' / 'smtp_password').read_bytes(), b'synthetic retained mail contents')

    def test_release_ref_is_windows_v030(self):
        result = ps('Write-Output $ProfileRef; Write-Output $ProfileBase')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'windows-v0.3.0',
            'https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.3.0/windows'])

    def test_legacy_three_files_upgrade_and_second_run_preserve_env_and_secrets(self):
        for manifest in [False, True]:
            with self.subTest(old_manifest=manifest):
                result, before, after, downloads, docker = self.exercise(manifest=manifest)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for name in ('.env', 'secrets/smtp_password', 'secrets/graph_client_secret', 'secrets/operator-file'):
                    self.assertEqual(after.get(name), before[name], name)
                for name in ('SHA256SUMS', *PROFILE_FILES):
                    self.assertEqual(after.get(name), (ROOT / name).read_bytes(), name)
                self.assertCountEqual(downloads, ['SHA256SUMS', *PROFILE_FILES])
                self.assertEqual(docker.count('compose up -d'), 2)

    def test_download_or_hash_failure_cannot_replace_existing_files(self):
        for mode in ['download', 'corrupt']:
            with self.subTest(mode=mode):
                result, before, after, downloads, docker = self.exercise(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(downloads)
                self.assertEqual(after, before)
                self.assertNotIn('compose up', docker)
                self.assertIn('download failure' if mode == 'download' else 'SHA-256-Pruefung fehlgeschlagen', result.stderr)

    def test_modified_or_missing_legacy_file_is_rejected_before_download(self):
        for mode in ['missing-base', 'modified-base']:
            with self.subTest(mode=mode):
                result, before, after, downloads, docker = self.exercise(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(downloads, [])
                self.assertEqual(after, before)
                self.assertNotIn('compose up', docker)


class ParentAcl(unittest.TestCase):
    def root_probe(self, fail=False):
        from test_acl_f5 import root_probe
        return root_probe(fail=fail)

    def test_b7_one_atomic_write_exact_three_rules_and_second_run_no_write(self):
        from test_acl_f5 import assert_exact_rules
        result = self.root_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        assert_exact_rules(self, json.loads(result.stdout), writes=1)

    def test_b7_acl_write_error_aborts(self):
        result = self.root_probe(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DACL write failed', result.stderr)

    def test_b7_real_temp_parent_removes_inherited_and_explicit_other_principals(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            command = r'''
$broadSource=Join-Path $env:PROBE_ROOT 'broad-source'
$parent=Join-Path $broadSource 'JanuaPort'
$DienstDirectory=Join-Path $parent 'windows'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
New-Item -ItemType Directory $broadSource | Out-Null
$acl=[IO.Directory]::GetAccessControl($broadSource,[Security.AccessControl.AccessControlSections]::Access)
$other=New-Object Security.Principal.SecurityIdentifier('S-1-5-11')
$rule=New-Object Security.AccessControl.FileSystemAccessRule($other,'Modify','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($rule)
[IO.Directory]::SetAccessControl($broadSource,$acl)
New-Item -ItemType Directory $parent | Out-Null
$acl=[IO.Directory]::GetAccessControl($parent,[Security.AccessControl.AccessControlSections]::Access)
$everyone=New-Object Security.Principal.SecurityIdentifier('S-1-1-0')
$explicit=New-Object Security.AccessControl.FileSystemAccessRule($everyone,'Read','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($explicit)
[IO.Directory]::SetAccessControl($parent,$acl)
New-Item -ItemType Directory $DienstDirectory | Out-Null
foreach ($path in @($parent,$DienstDirectory)) {
    if (-not ((Get-Acl $path).Access | Where-Object {$_.IsInherited -and $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq 'S-1-5-11'})) {throw 'fixture has no broad inherited access'}
}
Protect-DienstRoot $sid
Protect-DienstDirectory $DienstDirectory $sid
$results=@()
foreach ($path in @($parent,$DienstDirectory)) {
    $acl=Get-Acl $path
    $results += [pscustomobject]@{Protected=$acl.AreAccessRulesProtected;Entries=@($acl.Access | ForEach-Object {$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value});User=$sid.Value}
}
ConvertTo-Json -InputObject $results -Compress
'''
            result = ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            results = json.loads(result.stdout)
            self.assertEqual(len(results), 2)
            for acl in results:
                self.assertTrue(acl['Protected'])
                self.assertEqual(set(acl['Entries']), {'S-1-5-18', 'S-1-5-32-544', acl['User']})


if __name__ == '__main__':
    unittest.main()
