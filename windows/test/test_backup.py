"""Real PS 5.1 backup entry/filesystem with a Docker executable shim on PATH."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from test_profile import ROOT, run

SHIM = r'''
import hashlib,json,os,pathlib,sys
a=sys.argv[1:]; root=pathlib.Path(os.environ['PROBE_ROOT']); mode=os.environ.get('PROBE_FAIL','')
with (root/'docker.jsonl').open('a') as f: f.write(json.dumps(a)+'\n')
if a[:1] != ['compose']: sys.exit(91)
a=a[1:]
data=b'synthetic backup contents\n'
if a[:4]==['exec','-T','jnpt','/jnpt']:
    assert a[4:6]==['backup','--output'] and len(a)==7
    assert a[6].startswith('/data/backups/') and '..' not in a[6]
    if mode=='backup': sys.exit(11)
elif a[:4]==['exec','-T','jnpt','stat']:
    if mode=='stat': sys.exit(12)
    print('invalid' if mode=='stat-format' else len(data)+(1 if mode=='size' else 0))
elif a[:4]==['exec','-T','jnpt','sha256sum']:
    if mode=='sha': sys.exit(13)
    print('invalid' if mode=='sha-format' else (('0'*64 if mode=='hash' else hashlib.sha256(data).hexdigest())+'  '+a[4]))
elif a[:1]==['cp']:
    dst=pathlib.Path(a[2])
    if a[1].endswith(':/data') or a[1].endswith(':/data/'):
        # A broad directory copy really brings a synthetic key to the target.
        dst.mkdir(exist_ok=True); (dst/'master.key').write_text('synthetic key probe')
    else:
        assert a[1].startswith('jnpt:/data/backups/')
        dst.write_bytes(b'' if mode=='empty' else data)
    if mode=='cp': sys.exit(14)
elif a[:4]==['exec','-T','jnpt','rm']:
    assert a[4]=='--' and a[5].startswith('/data/backups/') and len(a)==6
    if mode=='cleanup': sys.exit(15)
else: sys.exit(92)
'''


class Backup(unittest.TestCase):
    def invoke(self, mode='', marker=True, identity=True, extra=''):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            root = Path(tmp)
            target = root / 'usb'
            target.mkdir()
            if marker:
                (target / '.jnpt-backup-ziel').write_text('JanuaPort backup v1\n')
            profile = root / 'profile'
            profile.mkdir()
            (profile / 'docker-compose.yml').write_text('synthetic profile')
            (profile / '.env').write_text('synthetic env')
            (root / 'docker_shim.py').write_text(SHIM)
            (root / 'docker.cmd').write_text('@echo off\n"' + sys.executable + '" "' +
                                            str(root / 'docker_shim.py') + '" %*\n')
            driver = root / 'driver.ps1'
            driver.write_text("$ErrorActionPreference='Stop'\n. '" + str(ROOT / 'jnpt-backup.ps1') +
                              "' -ProfileDirectory '" + str(profile) + "' -Target '" + str(target) + "'\n" +
                              ("function Get-CurrentAccount { $env:COMPUTERNAME + '\\jnpt-dienst' }\n" if identity else '') +
                              extra + '\nStart-JnptBackup\n')
            env = {k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}
            env.update(PROBE_ROOT=tmp, PROBE_FAIL=mode, PATH=tmp + os.pathsep + env['PATH'])
            result = run('powershell.exe', '-NoProfile', '-File', str(driver), check=False, env=env)
            files = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
            calls = [json.loads(line) for line in (root / 'docker.jsonl').read_text().splitlines()] if (root / 'docker.jsonl').exists() else []
            return result, files, calls

    def test_success_renames_part_checks_hash_and_removes_container_copy(self):
        result, files, calls = self.invoke()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        backups = [name for name in files if name != '.jnpt-backup-ziel']
        self.assertEqual(len(backups), 1, files)  # B-4: exactly one file, no key
        self.assertTrue(backups[0].endswith('.jnpt-backup'))
        self.assertEqual(files[backups[0]], b'synthetic backup contents\n')
        cp = [a for a in calls if a[1] == 'cp']
        self.assertEqual(len(cp), 1)
        self.assertTrue(cp[0][-1].endswith('.teil'))
        self.assertEqual(calls[-1][1:5], ['exec', '-T', 'jnpt', 'rm'])
        self.assertNotIn('master.key', files)

    def test_every_docker_and_verification_error_is_nonzero_without_target_file(self):
        for mode in ['backup', 'stat', 'stat-format', 'sha', 'sha-format', 'size',
                     'hash', 'cp', 'empty', 'cleanup']:
            with self.subTest(mode=mode):
                result, files, calls = self.invoke(mode)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(set(files), {'.jnpt-backup-ziel'}, (mode, files))
                if mode != 'cleanup':
                    self.assertFalse(any(a[1:5] == ['exec','-T','jnpt','rm'] for a in calls))

    def test_missing_marker_aborts_before_docker(self):
        result, files, calls = self.invoke(marker=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(files, {})
        self.assertEqual(calls, [])

    def test_other_account_rejected_at_real_identity_adapter(self):
        result, files, calls = self.invoke(identity=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('jnpt-dienst', result.stderr)
        self.assertEqual(set(files), {'.jnpt-backup-ziel'})
        self.assertEqual(calls, [])

    def test_real_filesystem_rename_and_hash_errors_leave_no_backup(self):
        for extra in ["function Move-Item { throw 'rename probe' }",
                      "function Get-FileHash { throw 'hash read probe' }"]:
            with self.subTest(extra=extra):
                result, files, _ = self.invoke(extra=extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(set(files), {'.jnpt-backup-ziel'})


if __name__ == '__main__':
    unittest.main()
