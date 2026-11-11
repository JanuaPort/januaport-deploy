"""F4 composition and provisioning mutations, isolated profile copies."""
from mutations import mutant


def main():
    test = 'test_backup.Backup.test_both_installers_create_staging_directory'
    for label, file, old, new, selected in [
        ('F4 relative backup bind removed', 'docker-compose.yml', '      - ./backups:/backups\n', '',
         'test_backup.Backup.test_compose_mount_is_relative_fixed_and_runtime_directory_ignored'),
        ('F4 interactive installer omits staging', 'einrichten.ps1',
         "    New-Item -ItemType Directory -Path (Join-Path $Directory 'backups') -Force | Out-Null\n", '', test),
        ('F4 service setup omits staging', 'dienst-einrichten.ps1',
         "        New-Item -ItemType Directory -Path (Join-Path $DienstDirectory 'backups') -Force | Out-Null\n", '', test),
        ('F4 stat substituted in real caller', 'jnpt-backup.ps1',
         "@('exec', '-T', 'jnpt', '/jnpt', 'backup', '--output', $remote)",
         "@('exec', '-T', 'jnpt', 'stat', '-c', '%s', $remote)",
         'test_backup.Backup.test_success_renames_part_checks_hash_and_removes_container_copy'),
    ]:
        mutant(label, file, old, new, command=['-m', 'unittest', selected, '-v'])
    print('F4 composition: 4 mutations killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
