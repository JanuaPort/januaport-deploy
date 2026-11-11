"""SEC acceptance recipes execute with read-only firewall boundary fakes."""
import json
import unittest

from test_install import ps
from test_profile import ROOT
from test_operator_docs import recipe


class SecDocs(unittest.TestCase):
    def assert_contains(self, member, container, msg=None):
        # Avoid dumping complete operator documents on assertion failure.
        self.assertTrue(member in container, msg or ('missing text: ' + member))

    def test_restore_archive_warning_in_all_four_documents(self):
        for name in ['README.md','README.en.md','RUNBOOK.md','PRUEFSTEIN-B4.md']:
            with self.subTest(file=name):
                text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
                if name.endswith('.en.md'):
                    self.assert_contains('Delete `/data/beiseite-<zeitstempel>` only after verifying the restore (healthz, login, read access).', text)
                    self.assert_contains('Applying the block to an existing installation otherwise loses its previous state.', text)
                else:
                    self.assert_contains('Den Ordner `/data/beiseite-<zeitstempel>` erst löschen, wenn die Rücksicherung geprüft ist (healthz, Anmeldung, Lesezugriff).', text)
                    self.assert_contains('Wer den Block auf eine nicht frische Anlage anwendet, verliert sonst den alten Stand.', text)

    def test_service_risk_and_measurement_placeholder_in_both_readmes(self):
        for name in ['README.md','README.en.md']:
            with self.subTest(file=name):
                text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
                # Gemessen in B4 (BOX c-6775695532): Sperre 12,6 s nach Start, Desktop höchstens rund 7 s sichtbar.
                self.assertNotIn('<SEKUNDEN>', text)
                if name == 'README.md':
                    self.assert_contains('höchstens rund 7 Sekunden', text)
                    self.assert_contains('12,6 Sekunden nach dem Start', text)
                else:
                    self.assert_contains('at most about 7 seconds', text)
                    self.assert_contains('12.6 seconds after start', text)
                if name == 'README.md':
                    self.assert_contains('`docker-users` ist praktisch Admin des Rechners. Schutz der Konsole sind Sperre und Raumzutritt beim Betreiber.', text)
                    self.assertNotIn('Für wenige Sekunden', text)
                else:
                    self.assert_contains('`docker-users` effectively grants administrator control of the computer.', text)
                    self.assert_contains("Console protection relies on locking and controlled access to the operator's room.", text)
                    self.assertNotIn('For a few seconds', text)

    def test_firewall_dialog_evidence_and_operator_check_documented(self):
        for name in ['README.md','README.en.md','RUNBOOK.md','PRUEFSTEIN-B4.md']:
            with self.subTest(file=name):
                text = ' '.join((ROOT / name).read_text(encoding='utf-8').split())
                if name.endswith('.en.md'):
                    self.assert_contains('Do not answer the Docker Desktop firewall dialog with “Allow” for public networks.', text)
                    self.assert_contains('The effect of choosing “Allow” was not measured.', text)
                else:
                    self.assert_contains('Den Firewall-Dialog von Docker Desktop nicht mit ‚Zulassen‘ für öffentliche Netze beantworten.', text)
                    self.assert_contains('Was bei „Zulassen“ entsteht, ist nicht gemessen.', text)
                self.assert_contains('LocalSubnet', text)
                self.assert_contains('JanuaPort 443 LAN', text)

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
        @('irrelevant','Other unrelated port','Any','445','Any'),
        # N8 (B4): Diese Regeln öffnen 443 nicht für den Docker-Listener und sollen nicht erscheinen.
        @('foreign-program','Teams all ports','C:\Teams\teams.exe','Any','Any'),
        @('app-package','Store app all ports','Any','Any','Any','S-1-15-2-1'),
        @('udp-any','UDP all ports','Any','Any','Any','','UDP')
    )) {
        $package = if ($row.Count -gt 5) { $row[5] } else { '' }
        $protocol = if ($row.Count -gt 6) { $row[6] } else { 'TCP' }
        [pscustomobject]@{Name=$row[0];DisplayName=$row[1];Profile='Private';Program=$row[2];LocalPort=$row[3];RemoteAddress=$row[4];Package=$package;Protocol=$protocol}
    }
}
function Get-NetFirewallApplicationFilter {param([Parameter(ValueFromPipeline=$true)]$InputObject)
    process {[pscustomobject]@{Program=$InputObject.Program;Package=$InputObject.Package}}
}
function Get-NetFirewallPortFilter {param([Parameter(ValueFromPipeline=$true)]$InputObject)
    process {[pscustomobject]@{Protocol=$InputObject.Protocol;LocalPort=$InputObject.LocalPort}}
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
