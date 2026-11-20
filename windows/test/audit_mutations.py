"""#1498/#1499/#1503: isolated copies, assertion failures, original bytes preserved."""
import os
from mutations import mutant


def main():
    cases = [
        ('1498 directory SetOwner removed', 'dienst-einrichten.ps1',
         "    $sec.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))\n    if (-not $exact)",
         '    if (-not $exact)',
         'test_audit_owner.Owner.test_foreign_owner_replaced_even_when_dacl_already_matches'),
        ('1498 file SetOwner removed', 'dienst-einrichten.ps1',
         "    $sec.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))\n    # A fresh",
         '    # A fresh', 'test_audit_owner.Owner.test_file_descriptor_forces_ba_and_inheritance'),
        ('1498 junction guard removed', 'dienst-einrichten.ps1',
         'if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)', 'if ($false)',
         'test_audit_owner.Owner.test_junction_is_rejected_before_touching_target'),
        ('1498 final staged tree protection removed', 'dienst-einrichten.ps1',
         '        Protect-DienstTree $DienstDirectory $user.SID\n', '',
         'test_install.Dienst.test_new_scripts_and_runtime_directories_are_present_at_final_protection'),
        ('1499 blanket 30 second deadline restored', 'jnpt-update.ps1',
         "$timeout = if ($Arguments[0] -ceq 'pull' -or $command -ceq 'compose up -d') { 0 } else { 30 }",
         '$timeout = 30', 'test_update.UpdateAdapter.test_slow_up_records_installed_after_completion'),
        ('1499 process tree kill removed', 'jnpt-update.ps1',
         "' /T /F'", "' /F'",
         'test_update.UpdateAdapter.test_timeout_reaps_native_descendant_before_returning_failure'),
        ('1499 Docker contract guard removed', 'jnpt-update.ps1',
         'if (-not $allowed)', 'if ($false)',
         'test_update.UpdateAdapter.test_non_core_programs_and_other_docker_operations_rejected_at_native_adapter'),
        ('1503 HTTPS route guard removed', 'Caddyfile',
         'respond 404', 'reverse_proxy http://127.0.0.1:8484',
         'test_audit_caddy.CaddyMaintenance.test_real_https_rejects_mcp_and_foreign_routes'),
        ('1503 managed Caddyfile hash guard removed', 'einrichten.ps1',
         'if ($actual -cne $digest)', 'if ($false)',
         'test_audit_caddy.CaddyMaintenance.test_manual_mcp_route_still_rejected_by_real_hash_adapter'),
    ]
    if not os.environ.get('JNPT_CADDY_EXE'):
        raise RuntimeError('JNPT_CADDY_EXE is required for the real HTTPS mutation')
    for label, file, old, new, selected in cases:
        mutant(label, file, old, new, command=['-m','unittest',selected,'-v'])
    if os.environ.get('JNPT_OWNER_VM') == '1':
        mutant('1498 foreign NTFS owner without both SetOwner calls', 'dienst-einrichten.ps1',
               "    $sec.SetOwner((New-Object Security.Principal.SecurityIdentifier('S-1-5-32-544')))\n", '',
               command=['-m','unittest','test_audit_owner.Owner.test_foreign_ntfs_owner_cannot_grant_after_protection','-v'],
               occurrences=2)
    else:
        print('NOT RUN: foreign-owner NTFS mutation requires explicit test VM.', flush=True)
    print('Audit: 9 local mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
