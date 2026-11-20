"""F5/B-7 mutations: descriptor flags, extra grant, two writes and idempotence."""
from mutations import mutant

CASES = [
    ('F5 inheritance protection missing',
     '$sec.SetAccessRuleProtection($true, $false)', '$sec.SetAccessRuleProtection($false, $false)',
     'test_upgrade.ParentAcl'),
    ('F5 fourth principal',
     "$principals = @([string]$SID, 'S-1-5-32-544', 'S-1-5-18')",
     "$principals = @([string]$SID, 'S-1-5-32-544', 'S-1-5-18', 'S-1-5-11')",
     'test_upgrade.ParentAcl.test_b7_one_atomic_write_exact_three_rules_and_owner_on_every_run'),
    ('F5 empty DACL before final write',
     '    [IO.Directory]::SetAccessControl($Path, $sec)',
     '    [IO.Directory]::SetAccessControl($Path, (New-Object Security.AccessControl.DirectorySecurity))\n'
     '    [IO.Directory]::SetAccessControl($Path, $sec)',
     'test_acl_f5.AtomicAcl.test_no_intermediate_empty_dacl_or_legacy_adapter_pattern'),
    ('F5 BA ownership omitted',
     "    $sec.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))\n    if (-not $exact)",
     '    if (-not $exact)',
     'test_audit_owner.Owner.test_foreign_owner_replaced_even_when_dacl_already_matches'),
    ('F5 previous explicit grants preserved',
     '$sec = if ($exact) { $current } else { New-Object Security.AccessControl.DirectorySecurity }',
     '$sec = $current',
     'test_acl_f5.AtomicAcl.test_extra_users_read_ace_requires_rewrite'),
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
