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


if __name__ == '__main__':
    main()
