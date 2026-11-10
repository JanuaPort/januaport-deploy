"""Opt-in F4 live test: real pinned distroless core, isolated Compose project."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import uuid

from test_install import ps
from test_profile import ROOT, PROFILE_FILES, config, run


class BackupLive(unittest.TestCase):
    def test_real_core_backup_host_hash_and_cleanup(self):
        project = 'jnpt-backup-live-' + uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp); profile = root / 'profile'; profile.mkdir()
            for name in PROFILE_FILES: shutil.copyfile(ROOT / name, profile / name)
            (profile / '.env').write_text('')
            (profile / 'backups').mkdir()
            (profile / 'secrets').mkdir()
            for name in ['smtp_password', 'graph_client_secret']: (profile / 'secrets' / name).write_bytes(b'')
            cfg = json.loads(config().stdout)
            core = cfg['services']['jnpt']
            # Keep the real core image/env/mount contract. No public test ports,
            # sidecars or persistent deployment objects are needed for backup.
            core.pop('depends_on', None)
            core['ports'] = []
            core.pop('networks', None)
            core['network_mode'] = 'none'
            core['restart'] = 'no'
            for mount in core['volumes']:
                if mount['type'] == 'bind' and mount['target'] == '/backups': mount['source'] = str(profile / 'backups')
            self.assertTrue(any(m['target'] == '/backups' for m in core['volumes']))
            manifest = dict(name=project, services={'jnpt': core},
                            volumes={name: {} for name in ['jnpt-data', 'plugin-keys']},
                            secrets={name: dict(file=str(profile / 'secrets' / name)) for name in ['smtp_password','graph_client_secret']},
                            )
            (profile / 'docker-compose.yml').write_text(json.dumps(manifest))
            compose = ('docker', 'compose', '-p', project, '-f', str(profile / 'docker-compose.yml'))
            target = root / 'usb'; target.mkdir()
            (target / '.jnpt-backup-ziel').write_text('synthetic live target')
            try:
                up = run(*compose, 'up', '-d', check=False)
                if up.returncode and '524' in up.stderr:
                    self.skipTest('LIVE blocked by seccomp errno 524; BOX must run B4 F4')
                self.assertEqual(up.returncode, 0, up.stderr)
                time.sleep(3)
                cid = run(*compose, 'ps', '-a', '-q', 'jnpt').stdout.strip()
                state = json.loads(run('docker','inspect',cid).stdout)[0]['State']
                if not state['Running']:
                    # Never print core logs: they may contain the initial key.
                    logs = run(*compose, 'logs', 'jnpt', check=False).stdout
                    if '524' in logs: self.skipTest('LIVE blocked by seccomp errno 524; BOX must run B4 F4')
                self.assertTrue(state['Running'], 'real core did not remain running; inspect locally without publishing logs')
                command = r'''
function Get-CurrentAccount {$env:COMPUTERNAME+'\jnpt-dienst'}
function Get-FileHash {param($LiteralPath,$Algorithm)
    $hash=Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $LiteralPath -Algorithm $Algorithm
    if ((Split-Path $LiteralPath -Parent) -eq (Join-Path $ProfileDirectory 'backups')) {
        [IO.File]::WriteAllText($env:PROBE_DIGEST,$hash.Hash)
    }
    $hash
}
Invoke-JnptBackup
'''
                result = ps("$ProfileDirectory='" + str(profile) + "'; $Target='" + str(target) + "'; " + command,
                            ROOT / 'jnpt-backup.ps1', dict(COMPOSE_PROJECT_NAME=project, PROBE_DIGEST=str(root / 'digest')))
                self.assertEqual(result.returncode, 0, result.stderr)
                backups = [p for p in target.iterdir() if p.name != '.jnpt-backup-ziel']
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].suffix, '.jnpt-backup')
                self.assertEqual(hashlib.sha256(backups[0].read_bytes()).hexdigest(), (root / 'digest').read_text().lower())
                self.assertEqual(list((profile / 'backups').iterdir()), [])
            finally:
                run(*compose, 'down', '-v', '--remove-orphans', check=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
