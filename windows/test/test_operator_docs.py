"""Operator recipes: test their contract and execute helper shell on own volumes."""
import re
import tempfile
from pathlib import Path
import unittest
import uuid

from test_profile import ROOT, run


def recipe(file, marker):
    text = (ROOT / file).read_text(encoding='utf-8')
    match = re.search(r'<!-- ' + marker + r' -->\s*```powershell\n(.*?)```', text, re.S)
    if not match:
        raise AssertionError(file + ': missing recipe ' + marker)
    return match.group(1)


class RecoveryDocs(unittest.TestCase):
    def test_n4_recipe_is_identical_pinned_and_preserves_old_database_and_key(self):
        code = recipe('README.md', 'N4')
        self.assertEqual(code, recipe('README.en.md', 'N4'))
        self.assertIn('jnpt-windows_jnpt-data:/data', code)
        self.assertIn('jnpt.db jnpt.db-wal jnpt.db-shm jnpt.key', code)
        self.assertIn('cp /in/jnpt.key /data/jnpt.key', code)
        self.assertIn('chown 65532:65532', code)
        self.assertIn('chmod 600 /data/jnpt.key', code)
        self.assertIn('jnpt restore "/in/$BackupFile"', code)
        self.assertLess(code.index('docker compose down'), code.index('cp /in/jnpt.key'))
        self.assertLess(code.index('jnpt restore'), code.index('docker compose up -d'))
        self.assertNotRegex(code, r'\brm\b|down -v|JNPT_MASTER_KEY=')
        helper = re.search(r"\$HelperImage = '(busybox@sha256:[a-f0-9]{64})'", code)
        self.assertIsNotNone(helper)
        scripts = re.findall(r"sh -ec '([^']+)'", code)
        self.assertEqual(len(scripts), 2)
        volume = 'jnpt-recovery-test-' + uuid.uuid4().hex
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            key = Path(tmp) / 'jnpt.key'
            key.write_bytes(b'synthetic separate fixture')
            args = ['docker', 'run', '--rm', '-v', volume + ':/data', '-v', tmp + ':/in:ro', helper.group(1)]
            try:
                run(*args, 'sh', '-ec', 'for f in jnpt.db jnpt.db-wal jnpt.db-shm jnpt.key; do echo old > /data/$f; done')
                run(*args, 'sh', '-ec', scripts[0])
                preserved = run(*args, 'sh', '-ec', 'find /data/beiseite-* -type f').stdout.splitlines()
                self.assertEqual(len(preserved), 4)
                run(*args, 'sh', '-ec', scripts[1])
                self.assertEqual(run(*args, 'cat', '/data/jnpt.key').stdout, key.read_text())
                self.assertEqual(run(*args, 'stat', '-c', '%u:%g:%a', '/data/jnpt.key').stdout.strip(), '65532:65532:600')
                run('docker', 'run', '--rm', '--user', '65532:65532', '-v', volume + ':/data',
                    helper.group(1), 'sh', '-ec', 'test -r /data/jnpt.key && touch /data/new-db-probe')
            finally:
                run('docker', 'volume', 'rm', volume, check=False)
