"""SEC H1: real TEMP hardlinks and metadata adapter, no ownership changes."""
import json
from pathlib import Path
import tempfile
import unittest

from test_install import ps
from test_profile import ROOT


class Hardlinks(unittest.TestCase):
    def test_real_link_count_single_multiple_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ps(r'''
$file=Join-Path $env:PROBE_ROOT 'single'
$alias=Join-Path $env:PROBE_ROOT 'alias'
[IO.File]::WriteAllText($file,'synthetic fixture')
$single=Get-DienstFileLinkCount $file
New-Item -ItemType HardLink -Path $alias -Target $file | Out-Null
$multiple=Get-DienstFileLinkCount $alias
$missingRejected=$false
try { Get-DienstFileLinkCount (Join-Path $env:PROBE_ROOT 'missing') | Out-Null }
catch { $missingRejected=$true }
@{Single=$single;Multiple=$multiple;MissingRejected=$missingRejected} | ConvertTo-Json -Compress
''', ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), dict(Single=1, Multiple=2, MissingRejected=True))

    def test_real_hardlink_rejected_before_file_security_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'protected').mkdir()
            (root / 'outside').write_text('synthetic external fixture')
            result = ps(r'''
$outside=Join-Path $env:PROBE_ROOT 'outside'
$tree=Join-Path $env:PROBE_ROOT 'protected'
$alias=Join-Path $tree 'jnpt-backup.ps1'
New-Item -ItemType HardLink -Path $alias -Target $outside | Out-Null
$before=(Get-Acl -LiteralPath $outside).Sddl
Add-Type -TypeDefinition @'
using System.Security.AccessControl;
public static class H1FileBoundary {
    public static int Writes;
    public static void SetAccessControl(string path, FileSecurity security) { Writes++; }
}
'@
# Only ACL writes are faked; real tree, guard and kernel metadata remain intact.
$body=(Get-Command Protect-DienstFile).ScriptBlock.ToString().Replace('[IO.File]', '[H1FileBoundary]')
Set-Item Function:\Protect-DienstFile ([scriptblock]::Create($body))
$script:directoryWrites=0
function Protect-DienstDirectory {param($Path,$SID) $script:directoryWrites++}
$rejected=$false
try { Protect-DienstTree $tree 'S-1-5-21-100-100-100-1001' }
catch {
    if ($_.Exception.Message -cne 'Mehrere Hardlinks im Dienstprofil nicht erlaubt.') {throw}
    $rejected=$true
}
@{Rejected=$rejected;Writes=[H1FileBoundary]::Writes;DirectoryWrites=$script:directoryWrites;SameAcl=($before -ceq (Get-Acl -LiteralPath $outside).Sddl)} | ConvertTo-Json -Compress
''', ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), dict(Rejected=True, Writes=0, DirectoryWrites=0, SameAcl=True))
            self.assertEqual((root / 'outside').read_text(), 'synthetic external fixture')
