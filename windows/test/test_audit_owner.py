"""#1498: real descriptors locally; foreign-owner NTFS proof explicitly VM-only."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from test_install import ps
from test_profile import ROOT
from test_acl_f5 import root_probe, assert_exact_rules


class Owner(unittest.TestCase):
    def test_foreign_owner_replaced_even_when_dacl_already_matches(self):
        result = root_probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        assert_exact_rules(self, json.loads(result.stdout), writes=3)

    def test_existing_tree_visits_hidden_files_and_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'windows' / 'secrets').mkdir(parents=True)
            for name in ['windows/jnpt-backup.ps1', 'windows/jnpt-sperren.ps1', 'windows/secrets/probe', '.env']:
                (root / name).write_text('synthetic fixture')
            result = ps(r'''
$script:seen=@()
function Protect-DienstDirectory {param($Path,$SID) $script:seen+=('directory:'+ $Path)}
function Protect-DienstFile {param($Path) $script:seen+=('file:'+ $Path)}
Protect-DienstTree $env:PROBE_ROOT 'S-1-5-21-100-100-100-1001'
ConvertTo-Json -InputObject $script:seen -Compress
''', ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            expected = ['directory:' + tmp] + [
                ('directory:' if p.is_dir() else 'file:') + str(p) for p in root.rglob('*')]
            self.assertCountEqual(json.loads(result.stdout), expected)

    @unittest.skipUnless(os.environ.get('JNPT_OWNER_VM') == '1', 'Fremdes Konto und Besitzwechsel nur auf NTFS-Test-VM')
    def test_foreign_ntfs_owner_cannot_grant_after_protection(self):
        # VM operator supplies an EXISTING unprivileged test account. No accounts,
        # tasks or services are created. Both child probes use that account's token.
        with tempfile.TemporaryDirectory() as tmp:
            result = ps(r'''
Assert-Administrator
$root=$env:PROBE_ROOT
$password=ConvertTo-SecureString $env:JNPT_FOREIGN_PASSWORD -AsPlainText -Force
$credential=New-Object Management.Automation.PSCredential($env:JNPT_FOREIGN_USER,$password)
$foreign=(New-Object Security.Principal.NTAccount($env:JNPT_FOREIGN_USER)).Translate([Security.Principal.SecurityIdentifier])
$acl=Get-Acl -LiteralPath $root
$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($foreign,'FullControl','ContainerInherit,ObjectInherit','None','Allow')))
Set-Acl -LiteralPath $root -AclObject $acl
function Invoke-ForeignProbe {param($Command)
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
    $child=Start-Process -FilePath ($env:SystemRoot+'\System32\WindowsPowerShell\v1.0\powershell.exe') -Credential $credential -WindowStyle Hidden -WorkingDirectory $root -ArgumentList ('-NoProfile -EncodedCommand '+$encoded) -PassThru -Wait
    return $child.ExitCode
}
$directory=Join-Path $root 'foreign'
$file=Join-Path $directory 'jnpt-backup.ps1'
$prepare="`$ErrorActionPreference='Stop'; New-Item -ItemType Directory '$directory' | Out-Null; [IO.File]::WriteAllText('$file','synthetic fixture'); exit 0"
if ((Invoke-ForeignProbe $prepare) -ne 0) {throw 'foreign fixture creation failed'}
foreach ($path in @($directory,$file)) {
    if ((Get-Acl -LiteralPath $path).GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $foreign.Value) {throw 'fixture must really have foreign owner'}
}
Protect-DienstTree $directory 'S-1-5-21-100-100-100-1001'
$owners=@($directory,$file | ForEach-Object {(Get-Acl -LiteralPath $_).GetOwner([Security.Principal.SecurityIdentifier]).Value})
$grants=@()
foreach ($path in @($directory,$file)) {
    $grants+=Invoke-ForeignProbe ("& icacls.exe '$path' /grant '*"+$foreign.Value+":F' *>`$null; exit `$LASTEXITCODE")
}
$rules=@((Get-Acl -LiteralPath $file).Access)
@{Owners=$owners;Grants=$grants;Inherited=@($rules | ForEach-Object {$_.IsInherited});Count=$rules.Count} | ConvertTo-Json -Compress
''', ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(result.stdout)
            self.assertEqual(state['Owners'], ['S-1-5-32-544'] * 2)
            self.assertTrue(all(code != 0 for code in state['Grants']), state)
            self.assertEqual(state['Count'], 3)
            self.assertEqual(state['Inherited'], [True] * 3)
