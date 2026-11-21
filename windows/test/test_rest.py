"""#1512: real PS 5.1 adapters with local files and native Docker shims."""
import hashlib
import json
from pathlib import Path
import tempfile
import os
import unittest

from test_install import ps
import test_install
from test_profile import ROOT, config
import test_update


class Autologon(unittest.TestCase):
    def probe(self, status='Valid', publisher='Microsoft Corporation', missing=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'operator.exe'
            binary.write_bytes(b'operator supplied synthetic executable')
            code = r'''
function Invoke-WebRequest {throw 'DOWNLOAD FORBIDDEN'}
function Get-AuthenticodeSignature {param($FilePath)
    [pscustomobject]@{Status=$env:PROBE_STATUS;SignerCertificate=[pscustomobject]@{Subject=('CN=fixture, O='+$env:PROBE_PUBLISHER+', C=US')}}
}
Get-AutologonBinary -ManifestDirectory $env:PROBE_ROOT -AutologonPfad (Join-Path $env:PROBE_ROOT $env:PROBE_FILE)
'''
            result = ps(code, ROOT / 'dienst-einrichten.ps1', dict(PROBE_ROOT=tmp,
                        PROBE_STATUS=status, PROBE_PUBLISHER=publisher,
                        PROBE_FILE='missing.exe' if missing else 'operator.exe'))
            copied = (root / 'Autologon64.exe').read_bytes() if (root / 'Autologon64.exe').exists() else None
            return result, copied, hashlib.sha256(binary.read_bytes()).hexdigest()

    def test_operator_path_valid_signature_and_hash_logged_without_download(self):
        result, copied, digest = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(copied, b'operator supplied synthetic executable')
        self.assertIn(digest, result.stdout)

    def test_operator_path_rejects_signature_publisher_and_missing_file(self):
        for status, publisher, missing in [('NotSigned','Microsoft Corporation',False),
                ('HashMismatch','Microsoft Corporation',False), ('Valid','Other',False),
                ('Valid','Microsoft Corporation Evil',False), ('Valid','Microsoft Corporation',True)]:
            with self.subTest(status=status, publisher=publisher, missing=missing):
                result, copied, _ = self.probe(status, publisher, missing)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(copied)

    def test_pin_failure_explains_operator_parameter(self):
        result = test_install.Dienst().binary_probe(wrong_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('-AutologonPfad <datei>', result.stderr)

    def test_entry_passes_optional_parameter(self):
        result, _, _ = test_install.Dienst().fake_setup(repeat=False, extra=r'''
$AutologonPfad='operator.exe'
function Get-AutologonBinary {param($ManifestDirectory,$AutologonPfad)
    if ($AutologonPfad -cne 'operator.exe') {throw 'operator path lost'}
    'synthetic.exe'
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)


class PluginNetwork(unittest.TestCase):
    def probe(self, subnet='172.21.0.0/16', ip='172.21.0.2', dynamic='172.21.128.0/17', empty=False):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / '.env'
            env.write_text('' if empty else f'JNPT_PLUGIN_SUBNET={subnet}\nJNPT_PLUGIN_IP={ip}\nJNPT_PLUGIN_RANGE={dynamic}\n')
            rendered = config(env_file=env)
            result = ps("Assert-PluginNetwork (ConvertFrom-Json -InputObject @'\n" + rendered.stdout + "\n'@)")
            return result, json.loads(rendered.stdout)

    def test_defaults_existing_dotenv_and_custom_private_networks(self):
        for subnet, ip, dynamic, empty in [('172.21.0.0/16','172.21.0.2','172.21.128.0/17',True),
                ('10.77.0.0/16','10.77.0.2','10.77.128.0/17',False),
                ('192.168.55.0/24','192.168.55.2','192.168.55.128/25',False)]:
            result, cfg = self.probe(subnet, ip, dynamic, empty)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(cfg['services']['jnpt']['networks']['plugins']['ipv4_address'], ip)
            self.assertEqual(cfg['networks']['plugins']['ipam']['config'][0], {'subnet':subnet,'ip_range':dynamic})

    def test_inconsistent_public_and_overlapping_values_rejected(self):
        for subnet, ip, dynamic in [('172.21.0.0/16','172.22.0.2','172.21.128.0/17'),
                ('172.21.0.0/16','172.21.0.2','172.22.128.0/17'),
                ('8.8.0.0/16','8.8.0.2','8.8.128.0/17'),
                ('172.0.0.0/8','172.21.0.2','172.21.128.0/17'),
                ('172.21.0.0/16','172.21.128.2','172.21.128.0/17'),
                ('172.21.0.0/16','172.21.0.0','172.21.128.0/17'),
                ('172.21.0.0/16','172.21.255.255','172.21.128.0/17')]:
            with self.subTest(subnet=subnet, ip=ip, dynamic=dynamic):
                result, _ = self.probe(subnet, ip, dynamic)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Plugin-Netz', result.stderr)


class RunningDigest(unittest.TestCase):
    invoke = test_update.Update.invoke
    records = staticmethod(test_update.Update.records)

    def test_wrong_missing_or_failed_running_digest_records_health_failure(self):
        for mode in ['digest-mismatch','digest-missing','digest-error','container-stopped','container-ambiguous']:
            with self.subTest(mode=mode):
                result, trace = self.invoke(mode=mode)
                self.assertEqual(result.returncode, 6, result.stderr)
                self.assertEqual(len(self.records(trace)), 1)
                self.assertIn('--result=failed', self.records(trace)[0])
                self.assertIn('RUNBOOK.md: Rueckweg von Hand; exit=6', self.log)

    def test_exact_running_image_checked_before_installed(self):
        result, trace = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['compose','ps','--status','running','-q','jnpt'], trace)
        inspect = ['image','inspect','--format','{{json .RepoDigests}}','sha256:'+'d'*64]
        self.assertIn(inspect, trace)
        self.assertLess(trace.index(inspect), trace.index(self.records(trace)[0]))

    def test_digest_queries_have_30_second_deadline(self):
        result = ps(r'''
function Invoke-UpdateProcess {param($Command,$TimeoutSeconds); $TimeoutSeconds}
Invoke-UpdateDocker @('compose','ps','--status','running','-q','jnpt')
Invoke-UpdateDocker @('inspect','--type','container','--format','{{.Image}}',('c'*64))
Invoke-UpdateDocker @('image','inspect','--format','{{json .RepoDigests}}',('sha256:'+('d'*64)))
''', ROOT/'jnpt-update.ps1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ['30','30','30'])

    def test_inspect_adapter_rejects_other_formats_and_injected_ids(self):
        for args in ["@('inspect','--type','container','--format','{{.Config.Env}}',('c'*64))",
                     "@('inspect','--type','container','--format','{{.Image}}','evil;whoami')",
                     "@('image','inspect','--format','{{json .RepoDigests}}','latest')"]:
            result, trace = self.invoke(extra='Invoke-UpdateDocker '+args+'; exit 99')
            self.assertNotIn(result.returncode, [0,99])
            self.assertEqual(trace, [])


class Retention(unittest.TestCase):
    def probe(self, days=30, only_old=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = ['jnpt-20000101T000000000Z-'+'a'*32+'.jnpt-backup',
                     'jnpt-20010101T000000000Z-'+'b'*32+'.jnpt-backup',
                     'foreign.jnpt-backup', 'jnpt-20000101T000000000Z-'+'a'*32+'.jnpt-backup.extra',
                     '.jnpt-backup-ziel']
            if not only_old: names += ['jnpt-20990101T000000000Z-'+'c'*32+'.jnpt-backup']
            for name in names:
                (root/name).write_bytes(b'retained contents')
                if '2099' not in name: os.utime(root/name, (946684800,946684800))
            result = ps("$Target='"+tmp+"'; $RetentionDays="+str(days)+"; Clear-ExpiredBackups", ROOT/'jnpt-backup.ps1')
            return result, set(p.name for p in root.iterdir()), names

    def test_only_expired_generated_names_deleted_foreign_and_newest_kept(self):
        for only_old in [False, True]:
            result, remaining, names = self.probe(only_old=only_old)
            self.assertEqual(result.returncode, 0, result.stderr)
            removed = set(names[:1] if only_old else names[:2])
            self.assertEqual(remaining, set(names)-removed)

    def test_custom_retention_and_invalid_days(self):
        result, remaining, names = self.probe(days=20000)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(remaining, set(names))
        result, remaining, names = self.probe(days=0)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(remaining, set(names))

    def test_default_and_successful_backup_invoke_retention(self):
        from test_backup import Backup
        result, _, _ = Backup().invoke(extra=r'''
if ($RetentionDays -ne 30) {throw 'default must be 30'}
function Clear-ExpiredBackups {Write-Host 'RETENTION-CALLED'}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('RETENTION-CALLED', result.stdout)


class Workflow(unittest.TestCase):
    def test_windows_workflow_pins_paths_permissions_and_fake_suite(self):
        # The workflow is outside copied mutation profiles.
        root = Path(__file__).resolve().parents[2]
        path = root/'.github/workflows/windows-tests.yml'
        self.assertTrue(path.is_file(), 'Windows CI workflow missing')
        text = path.read_text()
        for fragment in ['windows-latest','windows/**','workflow_dispatch:', 'main',
                'contents: read','fetch-depth: 0','fetch-tags: true','timeout-minutes: 30',
                'actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5',
                'python -B windows/test/run_fake_tests.py', 'verify_sums']:
            self.assertIn(fragment, text)
        self.assertRegex(text, r'actions/setup-python@[a-f0-9]{40}')
        self.assertNotIn('secrets.', text)
