"""#1512: every removed guard must yield assertion failures in real adapters."""
from mutations import mutant


def main():
    cases = [
        ('operator signature removed', 'dienst-einrichten.ps1',
         "$signature.Status -ne 'Valid' -or", "$false -or",
         'test_rest.Autologon.test_operator_path_rejects_signature_publisher_and_missing_file'),
        ('operator publisher removed', 'dienst-einrichten.ps1',
         "$signature.SignerCertificate.Subject -notmatch '(?:^|,\\s*)O=Microsoft Corporation(?:,|$)'", '$false',
         'test_rest.Autologon.test_operator_path_rejects_signature_publisher_and_missing_file'),
        ('plugin validation removed', 'einrichten.ps1',
         "        throw 'Plugin-Netz: privates Subnetz, passende Range und freie feste IP erforderlich.'", '        return',
         'test_rest.PluginNetwork.test_inconsistent_public_and_overlapping_values_rejected'),
        ('installer network validation call removed', 'einrichten.ps1',
         '        Assert-PluginNetwork (ConvertFrom-Json -InputObject ((Invoke-Docker @(\'compose\', \'config\', \'--format\', \'json\')) -join "`n"))\n', '',
         'test_rest.PluginNetwork.test_real_installer_rejects_invalid_resolved_network_before_start'),
        ('running digest comparison removed', 'jnpt-update.ps1',
         'if (@($digests) -cnotcontains ($UpdateRepository + \'@\' + $Digest))', 'if ($false)',
         'test_rest.RunningDigest.test_wrong_missing_or_failed_running_digest_records_health_failure'),
        ('retention filename filter removed', 'jnpt-backup.ps1',
         '$_.Name -cmatch $BackupNamePattern -and', '$true -and',
         'test_rest.Retention.test_only_expired_generated_names_deleted_foreign_and_newest_kept'),
        ('retention newest protection removed', 'jnpt-backup.ps1',
         '$file.FullName -cne $newest.FullName -and', '$true -and',
         'test_rest.Retention.test_only_expired_generated_names_deleted_foreign_and_newest_kept'),
        ('retention minimum removed', 'jnpt-backup.ps1',
         "if ($RetentionDays -lt 1) { throw 'Aufbewahrung muss mindestens einen Tag betragen.' }", '',
         'test_rest.Retention.test_custom_retention_and_invalid_days'),
        ('verified backup removed on retention failure', 'jnpt-backup.ps1',
         '        $success = $true\n        Clear-ExpiredBackups', '        Clear-ExpiredBackups\n        $success = $true',
         'test_rest.Retention.test_retention_failure_preserves_verified_new_backup'),
        ('digest inspect allowlist removed', 'jnpt-update.ps1', 'if (-not $allowed)', 'if ($false)',
         'test_rest.RunningDigest.test_inspect_adapter_rejects_other_formats_and_injected_ids'),
    ]
    for label, file, old, new, selected in cases:
        mutant(label, file, old, new, command=['-m','unittest',selected,'-v'])


if __name__ == '__main__':
    main()
