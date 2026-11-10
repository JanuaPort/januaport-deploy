"""F5: real security descriptors, fake native boundary, and real temporary NTFS."""
import json
from pathlib import Path
import re
import tempfile
import unittest

from test_install import ps
from test_profile import ROOT


def root_probe(fail=False, repair=''):
    command = r'''
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Security.AccessControl;
public static class F5AclBoundary {
    public static DirectorySecurity Current = new DirectorySecurity();
    public static int Writes;
    public static List<string> Paths = new List<string>();
    public static DirectorySecurity GetAccessControl(string path, AccessControlSections sections) {
        if (path != @"C:\JanuaPort" || sections != AccessControlSections.Access) throw new Exception("wrong ACL read");
        return Current;
    }
    public static void SetAccessControl(string path, DirectorySecurity security) {
        if (path != @"C:\JanuaPort") throw new Exception("wrong ACL write");
        if (Environment.GetEnvironmentVariable("PROBE_FAIL") == "1") throw new UnauthorizedAccessException("DACL write failed");
        Writes++; Paths.Add(path); Current = security;
    }
}
'@
# Replace only Directory's native boundary, retaining the production algorithm
# and the real DirectorySecurity/FileSystemAccessRule implementations.
$body=(Get-Command Protect-DienstDirectory).ScriptBlock.ToString().Replace('[IO.Directory]', '[F5AclBoundary]')
Set-Item Function:\Protect-DienstDirectory ([scriptblock]::Create($body))
function Clear-DienstExplicitAccess {throw 'FORBIDDEN intermediate ACL clearing'}
function icacls.exe {throw 'FORBIDDEN legacy icacls adapter'}
function New-Item {param($Path,$ItemType,[switch]$Force)
    if ($Path -cne 'C:\JanuaPort') {throw 'unexpected real root creation'}
}
$DienstDirectory='C:\JanuaPort\windows'
Protect-DienstRoot 'S-1-5-21-100-100-100-1001'
$acl=[F5AclBoundary]::Current
if ($env:PROBE_REPAIR -eq 'unprotected') { $acl.SetAccessRuleProtection($false,$false) }
elseif ($env:PROBE_REPAIR -eq 'fourth') {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule('S-1-5-11','Read','ContainerInherit,ObjectInherit','None','Allow')))
} elseif ($env:PROBE_REPAIR) {
    $rule=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))[0]
    $acl.RemoveAccessRuleSpecific($rule)
    $rights='FullControl'; $inherit='ContainerInherit,ObjectInherit'; $propagate='None'; $allow='Allow'
    switch ($env:PROBE_REPAIR) {
        'rights' {$rights='ReadAndExecute'}
        'inheritance' {$inherit='ObjectInherit'}
        'propagation' {$propagate='InheritOnly'}
        'deny' {$allow='Deny'}
    }
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule($rule.IdentityReference,$rights,$inherit,$propagate,$allow)))
}
Protect-DienstRoot 'S-1-5-21-100-100-100-1001'
$acl=[F5AclBoundary]::Current
$rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
    [pscustomobject]@{SID=$_.IdentityReference.Value;Rights=[int]$_.FileSystemRights;
        Inheritance=[int]$_.InheritanceFlags;Propagation=[int]$_.PropagationFlags;
        Type=[int]$_.AccessControlType;Inherited=$_.IsInherited}
})
[pscustomobject]@{Writes=[F5AclBoundary]::Writes;Paths=@([F5AclBoundary]::Paths);
    Protected=$acl.AreAccessRulesProtected;Rules=$rules;Owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]);
    Group=$acl.GetGroup([Security.Principal.SecurityIdentifier])} | ConvertTo-Json -Depth 5 -Compress
'''
    return ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_FAIL='1' if fail else '0', PROBE_REPAIR=repair))


def assert_exact_rules(case, state, writes):
    case.assertEqual(state['Writes'], writes)
    case.assertTrue(state['Protected'])
    case.assertEqual(state['Paths'], ['C:\\JanuaPort'] * writes)
    case.assertIsNone(state['Owner'])
    case.assertIsNone(state['Group'])
    rules = state['Rules']
    case.assertEqual(len(rules), 3)
    case.assertEqual({r['SID'] for r in rules}, {'S-1-5-21-100-100-100-1001','S-1-5-32-544','S-1-5-18'})
    for rule in rules:
        case.assertEqual((rule['Rights'],rule['Inheritance'],rule['Propagation'],rule['Type'],rule['Inherited']),
                         (2032127,3,0,0,False))


class AtomicAcl(unittest.TestCase):
    def test_no_intermediate_empty_dacl_or_legacy_adapter_pattern(self):
        command = r'''
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($env:PROBE_SOURCE,[ref]$tokens,[ref]$errors)
$fn=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Protect-DienstDirectory'},$true))[0]
$allWrites=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.InvokeMemberExpressionAst] -and $n.Member.Value -eq 'SetAccessControl'},$true))
$writes=@($fn.FindAll({param($n) $n -is [Management.Automation.Language.InvokeMemberExpressionAst] -and $n.Member.Value -eq 'SetAccessControl'},$true))
$legacy=@($ast.FindAll({param($n) ($n -is [Management.Automation.Language.CommandAst] -and $n.GetCommandName() -in @('icacls','icacls.exe','Clear-DienstExplicitAccess')) -or ($n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Clear-DienstExplicitAccess')},$true))
@{allWrites=$allWrites.Count;writes=$writes.Count;legacy=$legacy.Count;parseErrors=@($errors).Count} | ConvertTo-Json -Compress
'''
        result = ps(command, extra_env=dict(PROBE_SOURCE=str(ROOT / 'dienst-einrichten.ps1')))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), dict(allWrites=1,writes=1,legacy=0,parseErrors=0))

    def test_near_matching_dacls_are_replaced_instead_of_skipped(self):
        for repair in ['unprotected','fourth','rights','inheritance','propagation','deny']:
            with self.subTest(repair=repair):
                result = root_probe(repair=repair)
                self.assertEqual(result.returncode, 0, result.stderr)
                assert_exact_rules(self, json.loads(result.stdout), writes=2)

    def test_real_ntfs_second_run_keeps_inherited_files_readable_and_owner(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            command = r'''
$root=$env:PROBE_ROOT
if ((New-Object IO.DriveInfo([IO.Path]::GetPathRoot($root))).DriveFormat -ne 'NTFS') {throw 'NTFS required'}
$parent=Join-Path $root 'JanuaPort'
$DienstDirectory=Join-Path $parent 'windows'
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
New-Item -ItemType Directory -Path $DienstDirectory -Force | Out-Null
Protect-DienstRoot $sid
Protect-DienstDirectory $DienstDirectory $sid
$before=@{}
foreach ($relative in @('.env','secrets\fixture','log\sperren.log')) {
    $path=Join-Path $DienstDirectory $relative
    New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force | Out-Null
    [IO.File]::WriteAllText($path,'synthetic inherited fixture')
    $before[$relative]=(Get-Acl -LiteralPath $path).Sddl
}
$parentBefore=(Get-Acl -LiteralPath $parent).Sddl
$profileBefore=(Get-Acl -LiteralPath $DienstDirectory).Sddl
Protect-DienstRoot $sid
Protect-DienstDirectory $DienstDirectory $sid
$results=@()
foreach ($relative in $before.Keys) {
    $path=Join-Path $DienstDirectory $relative
    $acl=Get-Acl -LiteralPath $path
    $results += [pscustomobject]@{Readable=([IO.File]::ReadAllText($path) -eq 'synthetic inherited fixture');
        Same=($before[$relative] -ceq $acl.Sddl);Sddl=$acl.Sddl;Owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value;
        Rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {
            [pscustomobject]@{SID=$_.IdentityReference.Value;Inherited=$_.IsInherited;Rights=[int]$_.FileSystemRights;Type=[int]$_.AccessControlType}
        })}
}
@{ParentSame=($parentBefore -ceq (Get-Acl -LiteralPath $parent).Sddl);
    ProfileSame=($profileBefore -ceq (Get-Acl -LiteralPath $DienstDirectory).Sddl);
    User=$sid.Value;Files=$results} | ConvertTo-Json -Depth 6 -Compress
'''
            result = ps(command, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(result.stdout)
            self.assertTrue(state['ParentSame']); self.assertTrue(state['ProfileSame'])
            self.assertEqual(len(state['Files']), 3)
            for file in state['Files']:
                self.assertTrue(file['Readable']); self.assertTrue(file['Same'])
                self.assertNotEqual(file['Sddl'], 'D:AI')
                self.assertEqual(file['Owner'], state['User'])
                self.assertEqual(len(file['Rules']), 3)
                self.assertEqual({r['SID'] for r in file['Rules']}, {state['User'],'S-1-5-18','S-1-5-32-544'})
                for rule in file['Rules']:
                    self.assertEqual((rule['Inherited'],rule['Rights'],rule['Type']), (True,2032127,0))

    def test_runbook_has_manual_repair_with_localized_takeown_answer(self):
        text = (ROOT / 'RUNBOOK.md').read_text(encoding='utf-8')
        match = re.search(r'<!-- F5 -->\s*```powershell\n(.*?)```', text, re.S)
        self.assertIsNotNone(match, 'manual recovery recipe missing')
        code = match.group(1)
        self.assertIn('takeown /f C:\\JanuaPort /r /d j', code)
        self.assertIn('icacls C:\\JanuaPort /reset /t', code)
        self.assertIn('dienst-einrichten.ps1', code)
        self.assertLess(code.index('takeown'), code.index('icacls'))
        self.assertLess(code.index('icacls'), code.index('dienst-einrichten.ps1'))
        self.assertIn('/d y', text)
