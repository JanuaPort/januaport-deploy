"""B2/B3 guards: isolated profile copies, real PS 5.1 and filesystem/shim tests.

No account, autologon, power configuration, registry or scheduler changes.
"""
from mutations import mutant


def probe(label, file, old, new, test):
    mutant(label, file, old, new, command=['-m', 'unittest', test, '-v'])


def main():
    setup = 'test_install.Dienst.test_account_tasks_idempotence_password_and_no_dpapi'
    failed_setup = 'test_install.Dienst.test_setup_failure_never_prints_password'
    backup_ok = 'test_backup.Backup.test_success_renames_part_checks_hash_and_removes_container_copy'
    backup_errors = 'test_backup.Backup.test_every_docker_and_verification_error_is_nonzero_without_target_file'
    probe('B-2 hash before valid Authenticode', 'dienst-einrichten.ps1',
          'if ((Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected)',
          'if ($false)', 'test_install.Dienst.test_wrong_hash_with_valid_signature_aborts_before_autologon')
    probe('B2 Authenticode signature', 'dienst-einrichten.ps1', "$signature.Status -ne 'Valid'", '$false',
          'test_install.Dienst.test_authenticode_and_publisher_are_second_gate')
    probe('B2 Microsoft publisher', 'dienst-einrichten.ps1',
          "$signature.SignerCertificate.Subject -notmatch '(?:^|,\\s*)O=Microsoft Corporation(?:,|$)'", '$false',
          'test_install.Dienst.test_authenticode_and_publisher_are_second_gate')
    probe('B2 admin gate at actual Windows token', 'dienst-einrichten.ps1',
          'if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))',
          'if ($false)', 'test_install.Dienst.test_actual_nonadmin_session_rejected')
    probe('B2 standard user gate', 'dienst-einrichten.ps1',
          "throw 'jnpt-dienst muss Standardbenutzer sein.'", '$null=$null', failed_setup)
    probe('B2 disabled account gate', 'dienst-einrichten.ps1',
          "if (-not $user.Enabled)", 'if ($false)', failed_setup)
    probe('B2 native powercfg failure', 'dienst-einrichten.ps1',
          "if ($LASTEXITCODE -ne 0) { throw 'powercfg fehlgeschlagen.' }", '$null=$null', failed_setup)
    probe('B2 task target injection gate', 'dienst-einrichten.ps1',
          "throw 'Absolutes Sicherungsziel ohne Anfuehrungszeichen erforderlich.'", '$null=$null',
          'test_install.Dienst.test_unsafe_task_target_rejected_before_any_account_creation')
    probe('B2 existing wsl settings gate', 'dienst-einrichten.ps1',
          "throw 'Vorhandene .wslconfig manuell mit Speichergrenze 4GB abstimmen.'", '$null=$null',
          'test_install.Dienst.test_conflicting_wsl_and_profile_files_are_preserved')
    probe('B2 existing profile files gate', 'dienst-einrichten.ps1',
          "throw 'Vorhandenes Profil weicht ab; geprueftes Update erforderlich.'", '$null=$null',
          'test_install.Dienst.test_conflicting_wsl_and_profile_files_are_preserved')
    probe('B2 missing autologon needs explicit reset', 'dienst-einrichten.ps1',
          "throw 'Autologon fehlt: bewusst mit -KennwortNeu erneut einrichten.'", '$null=$null',
          'test_install.Dienst.test_existing_account_requires_explicit_password_reset_without_autologon')
    probe('B2 native password output suppressed', 'dienst-einrichten.ps1',
          "& $Binary /accepteula 'jnpt-dienst' $env:COMPUTERNAME $plain *> $null",
          "& $Binary /accepteula 'jnpt-dienst' $env:COMPUTERNAME $plain",
          'test_install.Dienst.test_actual_autologon_adapter_suppresses_native_password_output_and_failure')
    probe('B2 native autologon error rejected', 'dienst-einrichten.ps1',
          "if ($LASTEXITCODE -ne 0) { throw 'Autologon fehlgeschlagen.' }", '$null=$null',
          'test_install.Dienst.test_actual_autologon_adapter_suppresses_native_password_output_and_failure')
    probe('B-1 cmdkey write prohibited', 'dienst-einrichten.ps1',
          '    Assert-Administrator\n', '    Assert-Administrator\n    & cmdkey.exe /add:synthetic-master-key-probe\n', setup)
    probe('B2 private profile ACL', 'dienst-einrichten.ps1',
          '$acl.SetAccessRuleProtection($true, $false)', '$acl.SetAccessRuleProtection($false, $false)',
          'test_install.Dienst.test_real_filesystem_acl_is_limited_to_account_system_and_administrators')
    for old, new in [("@('ScreenSaveActive','1')", "@('ScreenSaveActive','0')"),
                     ("@('ScreenSaveTimeOut','60')", "@('ScreenSaveTimeOut','120')"),
                     ("@('ScreenSaverIsSecure','1')", "@('ScreenSaverIsSecure','0')")]:
        probe('B2 screen policy ' + old, 'dienst-einrichten.ps1', old, new,
              'test_install.Dienst.test_screen_lock_writes_secure_policy_and_hive_failures_abort')
    for key in ['autoStart', 'exposeDockerAPIOnTCP2375', 'autoDownloadUpdates', 'disableUpdate', 'silentModulesUpdate']:
        probe('B2 read-only Docker setting ' + key, 'dienst-einrichten.ps1',
              "throw ('Docker Desktop manuell in jnpt-dienst pruefen: ' + $requirement[0])",
              "if ($requirement[0] -ne '" + key + "') { throw 'other setting rejected' }",
              'test_install.Dienst.test_docker_settings_are_read_only_and_fail_closed')
    probe('B2 installer account gate', 'einrichten.ps1', '    Assert-DienstSession\n', '',
          'test_install.Dienst.test_installer_rejects_other_account_before_docker')
    probe('B-4 master key must stay separate', 'jnpt-backup.ps1',
          "        Invoke-BackupDocker @('cp', ('jnpt:' + $remote), $partial) | Out-Null",
          "        Invoke-BackupDocker @('cp', ('jnpt:' + $remote), $partial) | Out-Null\n"
          "        Invoke-BackupDocker @('cp', 'jnpt:/data', $Target) | Out-Null", backup_ok)
    probe('B3 nonzero error exit', 'jnpt-backup.ps1', '        exit 1', '        exit 0', backup_errors)
    probe('B3 marker gate', 'jnpt-backup.ps1',
          'if (-not (Test-Path -LiteralPath $marker -PathType Leaf))', 'if ($false)',
          'test_backup.Backup.test_missing_marker_aborts_before_docker')
    probe('B3 account gate', 'jnpt-backup.ps1',
          "if ((Get-CurrentAccount) -ine ($env:COMPUTERNAME + '\\jnpt-dienst'))", 'if ($false)',
          'test_backup.Backup.test_other_account_rejected_at_real_identity_adapter')
    probe('B3 absolute target gate', 'jnpt-backup.ps1',
          "if ([string]::IsNullOrWhiteSpace($Target) -or -not [IO.Path]::IsPathRooted($Target))", 'if ($false)',
          'test_backup.Backup.test_relative_or_empty_target_is_rejected')
    probe('B3 profile completeness', 'jnpt-backup.ps1',
          "throw 'Profil unvollstaendig.'", '$null=$null',
          'test_backup.Backup.test_incomplete_profile_rejected_before_docker')
    probe('B3 Docker exit code', 'jnpt-backup.ps1',
          "if ($LASTEXITCODE -ne 0) { throw 'Docker-Sicherung fehlgeschlagen.' }", '$null=$null', backup_errors)
    probe('B3 size comparison', 'jnpt-backup.ps1',
          "if ((Get-Item -LiteralPath $Path).Length -ne $Size)", 'if ($false)', backup_errors)
    probe('B3 hash comparison', 'jnpt-backup.ps1',
          'if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $Digest)',
          'if ($false)', backup_errors)
    probe('B3 final file readback', 'jnpt-backup.ps1',
          '        Assert-BackupCopy $final $size $digest\n', '',
          'test_backup.Backup.test_readback_detects_corruption_after_real_rename')
    probe('B3 partial filename', 'jnpt-backup.ps1', "$partial = $final + '.teil'", "$partial = $final + '.tmp'", backup_ok)
    probe('B3 failed final file cleanup', 'jnpt-backup.ps1',
          '-not $success -and $ownsFinal', '$false -and $ownsFinal', backup_errors)
    probe('B3 successful container cleanup', 'jnpt-backup.ps1',
          "        Invoke-BackupDocker @('exec', '-T', 'jnpt', 'rm', '--', $remote) | Out-Null\n", '', backup_ok)
    print('B2/B3 mutations: all killed; original profile bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
