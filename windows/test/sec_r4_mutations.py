"""R4 exact DACL and N5 acceptance-recipe mutations in isolated copies."""
from mutations import mutant


def main():
    cases = [
        ('R4 contains three instead of exactly three', 'dienst-einrichten.ps1',
         '$exact = $current.AreAccessRulesProtected -and $rules.Count -eq 3 -and $rawRules.Count -eq 3',
         '$exact = $current.AreAccessRulesProtected',
         'test_acl_f5.AtomicAcl.test_extra_users_read_ace_requires_rewrite'),
        ('R4 conditional callback accepted as plain Allow', 'dienst-einrichten.ps1',
         '$ace.AceType -ne [Security.AccessControl.AceType]::AccessAllowed', '$false',
         'test_acl_f5.AtomicAcl.test_callback_instead_of_plain_allow_requires_rewrite'),
        ('N5-1 broad Any port omitted', 'RUNBOOK.md', "$_ -eq 'Any'", '$false',
         'test_sec_r4_docs.SecDocs.test_firewall_audit_finds_docker_and_every_443_allow_rule'),
        ('N5-1 Docker application filter omitted', 'PRUEFSTEIN-B4.md',
         "$isDocker = @($applications | Where-Object { $_.Program -match 'docker' }).Count -gt 0",
         '$isDocker = $false',
         'test_sec_r4_docs.SecDocs.test_firewall_audit_finds_docker_and_every_443_allow_rule'),
        ('N5-1 port range omitted', 'RUNBOOK.md', "$_ -match '^([0-9]+)-([0-9]+)$'", '$false',
         'test_sec_r4_docs.SecDocs.test_firewall_audit_finds_docker_and_every_443_allow_rule'),
    ]
    for label, file, old, new, selected in cases:
        mutant(label, file, old, new, command=['-m','unittest',selected,'-v'])
    print('R4/SEC: 5 mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
