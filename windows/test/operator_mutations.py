"""Mutate operator recipes; exercise their real helper adapter on test volumes."""
from mutations import mutant


def main():
    for label, old, new in [
        ('N4 preserve previous database and key', 'mv /data/$f $d/', 'rm /data/$f'),
        ('N4 nonroot key owner', 'chown 65532:65532 /data /data/jnpt.key', 'chown 0:0 /data /data/jnpt.key'),
        ('N4 private key permissions', 'chmod 600 /data/jnpt.key', 'chmod 644 /data/jnpt.key'),
    ]:
        mutant(label, 'README.md', old, new, command=['-m', 'unittest',
            'test_operator_docs.RecoveryDocs.test_n4_helper_preserves_files_and_nonroot_key', '-v'])
    for label, file, old, new, test in [
        ('N5 Any remote address', 'README.md', '-RemoteAddress LocalSubnet', '-RemoteAddress Any',
         'test_n5_recipe_is_manual_private_domain_and_local_subnet_only'),
        ('N5 public firewall profile', 'README.en.md', '-Profile Private,Domain', '-Profile Any',
         'test_n5_recipe_is_manual_private_domain_and_local_subnet_only'),
        ('N5 network profile check omitted', 'RUNBOOK.md', 'Get-NetConnectionProfile\n', '',
         'test_n5_recipe_is_manual_private_domain_and_local_subnet_only'),
        ('N5 automatic firewall change', 'einrichten.ps1', '    Assert-DienstSession\n',
         "    Assert-DienstSession\n    New-NetFirewallRule -DisplayName 'forbidden automatic change'\n",
         'test_installer_never_changes_firewall'),
    ]:
        mutant(label, file, old, new, command=['-m', 'unittest', 'test_operator_docs.FirewallDocs.' + test, '-v'])
    print('Operator recipes: 7 mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
