"""Disposable full core round trip; ports 443 and 8484 must be free."""
import hashlib
import http.client
import json
import socket
import ssl
import time
import unittest
import uuid

from test_install import ps
from test_profile import ROOT, run


class Live(unittest.TestCase):
    def test_core_tls_loopback_and_fingerprint(self):
        name = 'jnpt-windows-live-' + uuid.uuid4().hex[:10]
        compose = ('docker', 'compose', '--env-file', str(ROOT / '.env.example'),
                   '-p', name, '-f', str(ROOT / 'docker-compose.yml'))
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
            result = run(*compose, 'up', '-d', check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
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
            fingerprint = ps('Get-LeafFingerprint')
            self.assertEqual(fingerprint.returncode, 0, fingerprint.stderr)
            self.assertEqual(fingerprint.stdout.strip(), expected)
        finally:
            result = run(*compose, 'down', '-v', '--remove-orphans', check=False)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
