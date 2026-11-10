"""SEC acceptance recipes execute with read-only firewall boundary fakes."""
import json
import unittest

from test_install import ps
from test_profile import ROOT
from test_operator_docs import recipe


class SecDocs(unittest.TestCase):
    def assertIn(self, member, container, msg=None):
        # Avoid dumping complete operator documents on assertion failure.
        self.assertTrue(member in container, msg or ('missing text: ' + member))

    def test_restore_archive_warning_in_all_four_documents(self):
        for name in ['README.md','README.en.md','RUNBOOK.md','PRUEFSTEIN-B4.md']:
            with self.subTest(file=name):
                text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
                if name.endswith('.en.md'):
                    self.assertIn('Delete `/data/beiseite-<zeitstempel>` only after verifying the restore (healthz, login, read access).', text)
                    self.assertIn('Applying the block to an existing installation otherwise loses its previous state.', text)
                else:
                    self.assertIn('Den Ordner `/data/beiseite-<zeitstempel>` erst löschen, wenn die Rücksicherung geprüft ist (healthz, Anmeldung, Lesezugriff).', text)
                    self.assertIn('Wer den Block auf eine nicht frische Anlage anwendet, verliert sonst den alten Stand.', text)

    def test_service_risk_and_measurement_placeholder_in_both_readmes(self):
        for name in ['README.md','README.en.md']:
            with self.subTest(file=name):
                text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
                self.assertEqual(text.count('<SEKUNDEN>'), 1)
                if name == 'README.md':
                    self.assertIn('`docker-users` ist praktisch Admin des Rechners. Schutz der Konsole sind Sperre und Raumzutritt beim Betreiber.', text)
                    self.assertNotIn('Für wenige Sekunden', text)
                else:
                    self.assertIn('`docker-users` effectively grants administrator control of the computer.', text)
                    self.assertIn("Console protection relies on locking and controlled access to the operator's room.", text)
                    self.assertNotIn('For a few seconds', text)

    def test_firewall_dialog_evidence_and_operator_check_documented(self):
        for name in ['README.md','README.en.md','RUNBOOK.md','PRUEFSTEIN-B4.md']:
            with self.subTest(file=name):
                text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
                if name.endswith('.en.md'):
                    self.assertIn('Do not answer the Docker Desktop firewall dialog with “Allow” for public networks.', text)
                    self.assertIn('The effect of choosing “Allow” was not measured.', text)
                else:
                    self.assertIn('Den Firewall-Dialog von Docker Desktop nicht mit ‚Zulassen‘ für öffentliche Netze beantworten.', text)
                    self.assertIn('Was bei „Zulassen“ entsteht, ist nicht gemessen.', text)
                self.assertIn('LocalSubnet', text)
                self.assertIn('JanuaPort 443 LAN', text)

    def test_firewall_audit_finds_docker_and_every_443_allow_rule(self):
        for name in ['RUNBOOK.md','PRUEFSTEIN-B4.md']:
            with self.subTest(file=name):
                code = recipe(name, 'N5-1')
                command = r'''
function Get-NetFirewallRule {param($Enabled,$Direction,$Action)
    if ($Enabled -ne 'True' -or $Direction -ne 'Inbound' -or $Action -ne 'Allow') {throw 'wrong selection'}
    foreach ($row in @(
        @('canonical','JanuaPort 443 LAN','Any','443','LocalSubnet'),
        @('docker-wide','Docker Backend','C:\Docker\docker.exe','Any','Any'),
        @('docker-other-port','Docker Service','C:\Docker\docker-service.exe','8080','Any'),
        @('foreign-any','Other all ports','Any','Any','Any'),
        @('foreign-range','Other port range','Any','400-500','Any'),
        @('foreign-list','Other port list','Any','80,443,8443','Any'),
        @('irrelevant','Other unrelated port','Any','445','Any')
    )) {
        [pscustomobject]@{Name=$row[0];DisplayName=$row[1];Profile='Private';Program=$row[2];LocalPort=$row[3];RemoteAddress=$row[4]}
    }
}
function Get-NetFirewallApplicationFilter {param([Parameter(ValueFromPipeline=$true)]$InputObject)
    process {[pscustomobject]@{Program=$InputObject.Program}}
}
function Get-NetFirewallPortFilter {param([Parameter(ValueFromPipeline=$true)]$InputObject)
    process {[pscustomobject]@{Protocol='TCP';LocalPort=$InputObject.LocalPort}}
}
function Get-NetFirewallAddressFilter {param([Parameter(ValueFromPipeline=$true)]$InputObject)
    process {[pscustomobject]@{RemoteAddress=$InputObject.RemoteAddress}}
}
function Set-NetFirewallRule {throw 'FORBIDDEN firewall mutation'}
function Disable-NetFirewallRule {throw 'FORBIDDEN firewall mutation'}
'''
                result = ps(command + '\n$rows=@(& {\n' + code + '\n}); $rows | ConvertTo-Json -Compress')
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = json.loads(result.stdout)
                self.assertEqual({r['Name'] for r in rows}, {'canonical','docker-wide','docker-other-port','foreign-any','foreign-range','foreign-list'})
                for row in rows:
                    self.assertTrue({'DisplayName','Profile','Program','Protocol','LocalPort','RemoteAddress'} <= set(row))
                self.assertEqual(next(r for r in rows if r['Name']=='canonical')['RemoteAddress'], 'LocalSubnet')
