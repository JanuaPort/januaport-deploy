"""0.1.0 -> 0.2.0 through real PS 5.1 file/hash adapters, with transport fakes."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_install import ps
from test_profile import PROFILE_FILES, ROOT, verify_sums

LEGACY_FILES = ('docker-compose.yml', 'Caddyfile', 'einrichten.ps1')


class Upgrade(unittest.TestCase):
    def exercise(self, mode='', manifest=False):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            target = root / 'profile'
            target.mkdir()
            # Read exact published bytes, never execute the old installer.
            for name in (*LEGACY_FILES, *(('SHA256SUMS',) if manifest else ())):
                (target / name).write_bytes(subprocess.check_output(
                    ['git', 'show', 'windows-v0.1.0:windows/' + name]))
            (target / '.env').write_bytes(b'# synthetic retained environment\r\nJANUAPORT_IMAGE=synthetic-image\r\n')
            (target / 'secrets').mkdir()
            for name in ('smtp_password', 'graph_client_secret', 'operator-file'):
                (target / 'secrets' / name).write_bytes(b'synthetic retained contents\r\n')
            if mode == 'missing-base':
                (target / 'Caddyfile').unlink()
            if mode == 'modified-base':
                with (target / 'docker-compose.yml').open('ab') as file:
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
        $base='https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.2.0/windows/'
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
            result = ps(command, extra_env=dict(PROBE_ROOT=tmp, PROBE_SOURCE=str(ROOT), PROBE_FAIL=mode))
            after = {p.relative_to(target).as_posix(): p.read_bytes()
                     for p in target.rglob('*') if p.is_file()}
            downloads = (root / 'downloads.txt').read_text().splitlines() if (root / 'downloads.txt').exists() else []
            docker = (root / 'docker.txt').read_text() if (root / 'docker.txt').exists() else ''
            if result.returncode == 0:
                verify_sums(target)
            return result, before, after, downloads, docker

    def test_release_ref_is_windows_v020(self):
        result = ps('Write-Output $ProfileRef; Write-Output $ProfileBase')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'windows-v0.2.0',
            'https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.2.0/windows'])

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
        command = r'''
$DienstDirectory='C:\JanuaPort\windows'
$script:calls=@()
function New-Item {param($Path,$ItemType,[switch]$Force)
    if ($Path -cne 'C:\JanuaPort') {throw 'unexpected real root creation'}
}
function Clear-DienstExplicitAccess {param($Path) if ($Path -cne 'C:\JanuaPort') {throw 'wrong ACL root'} }
function icacls.exe {
    $script:calls += ,@($args)
    $global:LASTEXITCODE=[int]$env:PROBE_FAIL
}
Protect-DienstRoot 'S-1-5-21-100-100-100-1001'
ConvertTo-Json -InputObject $script:calls -Compress
'''
        return ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_FAIL='1' if fail else '0'))

    def test_b7_icacls_fixed_parent_inheritance_and_exact_three_principals(self):
        result = self.root_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = json.loads(result.stdout)
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0][0], 'C:\\JanuaPort')
        self.assertEqual(calls[0][1:3], ['/inheritance:r', '/grant:r'])
        self.assertCountEqual(calls[0][3:], ['*S-1-5-21-100-100-100-1001:(OI)(CI)F',
                                           '*S-1-5-32-544:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'])

    def test_b7_native_icacls_error_aborts(self):
        result = self.root_probe(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('icacls', result.stderr)

    def test_b7_real_temp_parent_removes_inherited_and_explicit_other_principals(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            command = r'''
$parent=Join-Path $env:PROBE_ROOT 'JanuaPort'
$DienstDirectory=Join-Path $parent 'windows'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
New-Item -ItemType Directory $parent | Out-Null
$acl=[IO.Directory]::GetAccessControl($parent,[Security.AccessControl.AccessControlSections]::Access)
$other=New-Object Security.Principal.SecurityIdentifier('S-1-5-11')
$rule=New-Object Security.AccessControl.FileSystemAccessRule($other,'Modify','ContainerInherit,ObjectInherit','None','Allow')
$acl.AddAccessRule($rule)
[IO.Directory]::SetAccessControl($parent,$acl)
New-Item -ItemType Directory $DienstDirectory | Out-Null
if (-not ((Get-Acl $DienstDirectory).Access | Where-Object {$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -eq 'S-1-5-11'})) {throw 'fixture has no broad inherited access'}
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
