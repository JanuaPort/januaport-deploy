"""Disposable full core round trip; ports 443 and 8484 must be free."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import time
import tempfile
import unittest
import uuid

from test_install import ps
from test_profile import ROOT, run


class Live(unittest.TestCase):
    def test_core_tls_loopback_and_fingerprint(self):
        name = 'jnpt-windows-live-' + uuid.uuid4().hex[:10]
        compose = ('docker', 'compose', '--env-file', str(ROOT / '.env.example'),
                   '-p', name, '-f', str(ROOT / 'docker-compose.yml'))
        installation = tempfile.TemporaryDirectory(prefix='install-', dir=ROOT / 'test')
        target = Path(installation.name)
        for file in ['Caddyfile', 'docker-compose.yml', 'einrichten.ps1', 'SHA256SUMS']:
            shutil.copyfile(ROOT / file, target / file)
        shutil.copyfile(ROOT / '.env.example', target / '.env')
        env_bytes = (target / '.env').read_bytes()
        install_env = {key: value for key, value in os.environ.items() if key.lower() != 'psmodulepath'}
        install_env['COMPOSE_PROJECT_NAME'] = name
        def install(rotate=False):
            return run('powershell', '-NoProfile', '-File', str(target / 'einrichten.ps1'),
                       '-Directory', str(target), *(['-NeuesZertifikat'] if rotate else []),
                       env=install_env, check=False)
        def request(path, tls=False, method='GET', body=None, headers=None):
            if tls:
                conn = http.client.HTTPSConnection('127.0.0.1', 443, timeout=4,
                                                   context=ssl._create_unverified_context())
            else:
                conn = http.client.HTTPConnection('127.0.0.1', 8484, timeout=4)
            try:
                conn.request(method, path, body=body, headers=headers or {})
                response = conn.getresponse()
                return response.status, response.read()
            finally:
                conn.close()
        try:
            result = install()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Admin-GUI: http://127.0.0.1:8484', result.stdout)
            for attempt in range(60):
                try:
                    if request('/healthz', tls=True)[0] == 200:
                        break
                except (OSError, ssl.SSLError):
                    pass
                time.sleep(1)
            self.assertEqual(request('/healthz')[0], 200)
            self.assertEqual(request('/api/device/v1/', tls=True)[0], 401)
            for path in ['/', '/admin/mcp', '/api/admin/tokens', '/mcp', '/mcp/x']:
                self.assertEqual(request(path, tls=True)[0], 404, path)
            headers = {'X-Jnpt-Desktop-Contract': '1', 'Content-Type': 'application/json'}
            # {} passes the transport guard but fails required input fields.
            # HTTP through Docker NAT is refused earlier, at the transport guard.
            self.assertEqual(request('/api/device/v1/pair', True, 'POST', '{}', headers)[0], 400)
            self.assertEqual(request('/api/device/v1/pair', False, 'POST', '{}', headers)[0], 401)
            # The actual Windows LAN interface must not reach the admin listener.
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                probe.connect(('192.0.2.1', 9))
                host_ip = probe.getsockname()[0]
            finally:
                probe.close()
            with self.assertRaises(OSError):
                with socket.create_connection((host_ip, 8484), timeout=2):
                    pass
            cid = run(*compose, 'ps', '-q', 'jnpt').stdout.strip()
            inspect = json.loads(run('docker', 'inspect', cid).stdout)[0]
            bindings = inspect['HostConfig']['PortBindings']
            self.assertEqual(bindings['8484/tcp'], [{'HostIp': '127.0.0.1', 'HostPort': '8484'}])
            self.assertEqual(set(bindings), {'443/tcp', '8484/tcp'})
            caddy = run(*compose, 'ps', '-q', 'caddy').stdout.strip()
            shared = json.loads(run('docker', 'inspect', caddy).stdout)[0]
            self.assertEqual(shared['HostConfig']['NetworkMode'], 'container:' + cid)
            with socket.create_connection(('127.0.0.1', 443), timeout=3) as raw:
                with ssl._create_unverified_context().wrap_socket(raw, server_hostname=None) as secure:
                    expected = hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest()
            fingerprint = ps("Push-Location '" + str(target) + "'; Get-LeafFingerprint", extra_env={'COMPOSE_PROJECT_NAME': name})
            self.assertEqual(fingerprint.returncode, 0, fingerprint.stderr)
            self.assertEqual(fingerprint.stdout.strip(), expected)
            # The setup path includes the real machine name and all current IPv4 SANs.
            sans = ps('Get-CertificateSAN')
            self.assertEqual(sans.returncode, 0, sans.stderr)
            expected_sans = {'DNS:localhost', 'IP:127.0.0.1', 'DNS:' + socket.gethostname()}
            expected_sans.update('IP:' + address[4][0] for address in
                                 socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
            self.assertTrue(expected_sans.issubset(set(sans.stdout.strip().split(','))))
            cert = run(*compose, 'run', '--rm', '--no-deps', '--entrypoint', 'openssl',
                       'cert-init', 'x509', '-in', '/certs/cert.pem', '-noout', '-text').stdout
            for san in sans.stdout.strip().split(','):
                self.assertIn(san.replace('IP:', 'IP Address:'), cert)
            # Execute the entire setup script again, preserving operator values and leaf.
            again = install()
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn(expected, again.stdout)
            self.assertEqual((target / '.env').read_bytes(), env_bytes)
            run(*compose, 'restart', 'caddy')
            for attempt in range(30):
                try:
                    with socket.create_connection(('127.0.0.1', 443), timeout=3) as raw:
                        with ssl._create_unverified_context().wrap_socket(raw, server_hostname=None) as secure:
                            restarted = hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest()
                    break
                except (OSError, ssl.SSLError):
                    time.sleep(.25)
            self.assertEqual(restarted, expected)
            rotated = install(rotate=True)
            self.assertEqual(rotated.returncode, 0, rotated.stderr)
            new_pin = ps("Push-Location '" + str(target) + "'; Get-LeafFingerprint",
                         extra_env={'COMPOSE_PROJECT_NAME': name})
            self.assertEqual(new_pin.returncode, 0, new_pin.stderr)
            self.assertNotEqual(new_pin.stdout.strip(), expected)
            self.assertIn(new_pin.stdout.strip(), rotated.stdout)
        finally:
            result = run(*compose, 'down', '-v', '--remove-orphans', check=False)
            installation.cleanup()
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
