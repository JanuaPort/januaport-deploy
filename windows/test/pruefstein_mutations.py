"""#1499 BOX findings: isolated copies, real PS/file adapters, no Docker engine."""
from mutations import mutant


def main():
    for label, file, old, new, selected in [
        ('1499 leaf deadline restored to 30 seconds', 'jnpt-update.ps1',
         '-Name UpdateLeafTimeoutSeconds -Value 300', '-Name UpdateLeafTimeoutSeconds -Value 30',
         'test_update.UpdateAdapter.test_only_leaf_query_gets_300_seconds_plan_record_stay_at_30'),
        ('1499 v0.3.0 upgrade source removed', 'einrichten.ps1',
         '@($legacy, $b4, $v030)', '@($legacy, $b4)',
         'test_upgrade.Upgrade.test_v030_exact_profile_is_replaced_preserving_local_data'),
        ('1499 v0.3.0 source removed caught by tag drift', 'einrichten.ps1',
         '@($legacy, $b4, $v030)', '@($legacy, $b4)',
         'test_upgrade.ProfileSourceDrift.test_every_local_windows_tag_is_an_upgrade_source'),
        ('1499 changed v0.3.0 bytes accepted by download installer', 'einrichten.ps1',
         '(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $candidate[$name]',
         '$false', 'test_upgrade.Upgrade.test_modified_original_reports_exact_upgrade_block_without_file_contents'),
        ('1499 forged local manifest accepted', 'einrichten.ps1',
         '(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $candidate[$name]',
         '$false', 'test_upgrade.Upgrade.test_v030_forged_local_manifest_cannot_authorize_changed_bytes'),
        ('1499 changed v0.3.0 bytes accepted by service installer', 'einrichten.ps1',
         '(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -cne $candidate[$name]',
         '$false', 'test_upgrade.Upgrade.test_local_dienst_staging_also_upgrades_v030_and_rejects_every_changed_file'),
    ]:
        mutant(label, file, old, new, command=['-m', 'unittest', selected, '-v'])
    print('Pruefstein #1499: 6 mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
