"""F5/B-7 mutations: descriptor flags, extra grant, two writes and idempotence."""
from mutations import mutant

CASES = [
    ('F5 inheritance protection missing',
     '$sec.SetAccessRuleProtection($true, $false)', '$sec.SetAccessRuleProtection($false, $false)',
     'test_upgrade.ParentAcl'),
    ('F5 fourth principal',
     "$principals = @([string]$SID, 'S-1-5-32-544', 'S-1-5-18')",
     "$principals = @([string]$SID, 'S-1-5-32-544', 'S-1-5-18', 'S-1-5-11')",
     'test_upgrade.ParentAcl.test_b7_one_atomic_write_exact_three_rules_and_second_run_no_write'),
    ('F5 empty DACL before final write',
     '    [IO.Directory]::SetAccessControl($Path, $sec)',
     '    [IO.Directory]::SetAccessControl($Path, (New-Object Security.AccessControl.DirectorySecurity))\n'
     '    [IO.Directory]::SetAccessControl($Path, $sec)',
     'test_acl_f5.AtomicAcl.test_no_intermediate_empty_dacl_or_legacy_adapter_pattern'),
    ('F5 second identical run writes again',
     'if ($exact) { return }', 'if ($false) { return }',
     'test_upgrade.ParentAcl.test_b7_one_atomic_write_exact_three_rules_and_second_run_no_write'),
    ('F5 previous explicit grants preserved',
     '$sec = New-Object Security.AccessControl.DirectorySecurity',
     '$sec = [IO.Directory]::GetAccessControl($Path, [Security.AccessControl.AccessControlSections]::Access)',
     'test_upgrade.ParentAcl.test_b7_real_temp_parent_removes_inherited_and_explicit_other_principals'),
    ('F5 native ACL write error ignored',
     '    [IO.Directory]::SetAccessControl($Path, $sec)',
     '    try { [IO.Directory]::SetAccessControl($Path, $sec) } catch { }',
     'test_upgrade.ParentAcl.test_b7_acl_write_error_aborts'),
]


def main():
    for label, old, new, selected in CASES:
        mutant(label, 'dienst-einrichten.ps1', old, new, command=['-m','unittest',selected,'-v'])
    print('F5: 6 mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
