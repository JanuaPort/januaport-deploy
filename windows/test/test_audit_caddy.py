"""#1503: no unsupported switch; real optional native Caddy HTTPS adapter."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest

from test_install import ps
from test_profile import ROOT, PROFILE_FILES


class CaddyMaintenance(unittest.TestCase):
    def test_no_documented_switch_can_invalidate_managed_caddyfile(self):
        caddy = (ROOT / 'Caddyfile').read_text()
        self.assertNotRegex(caddy, r'(?m)^\s*#\s*handle /mcp\s*\{')
        for name in ['README.md', 'README.en.md']:
            self.assertNotRegex((ROOT / name).read_text(encoding='utf-8'), r'(?is)(?:auskommentierte|uncomment).*?/mcp.*?(?:aktivier|needs it)')

    def test_manual_mcp_route_still_rejected_by_real_hash_adapter(self):
        import shutil
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ['SHA256SUMS', *PROFILE_FILES]:
                shutil.copyfile(ROOT / name, root / name)
            with (root / 'Caddyfile').open('a') as file:
                file.write('\n# manual route change\nhandle /mcp {\n reverse_proxy http://127.0.0.1:8484\n}\n')
            result = ps("Test-ProfileFiles '" + tmp + "'")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('SHA-256-Pruefung fehlgeschlagen: Caddyfile', result.stderr)

    @unittest.skipUnless(os.environ.get('JNPT_CADDY_EXE'), 'JNPT_CADDY_EXE fuer nativen HTTPS-Adapter erforderlich')
    def test_real_https_rejects_mcp_and_foreign_routes(self):
        class Backend(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'upstream')
            do_POST = do_GET
            def log_message(self, *args):
                pass

        with tempfile.TemporaryDirectory() as tmp, ThreadingHTTPServer(('127.0.0.1', 0), Backend) as backend:
            root = Path(tmp)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            (root / 'openssl.cnf').write_text('[req]\ndistinguished_name=dn\n[dn]\n')
            subprocess.run(['openssl', 'req', '-config', str(root / 'openssl.cnf'), '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(root / 'key.pem'), '-out', str(root / 'cert.pem'),
                            '-days', '1', '-subj', '/CN=localhost'], check=True, capture_output=True)
            text = (ROOT / 'Caddyfile').read_text().replace(
                'https://localhost, https:// {', 'https://127.0.0.1:' + str(port) + ' {\n bind 127.0.0.1')
            text = text.replace('/certs/cert.pem', (root / 'cert.pem').as_posix()).replace('/certs/key.pem', (root / 'key.pem').as_posix())
            text = text.replace('127.0.0.1:8484', '127.0.0.1:' + str(backend.server_port))
            config = root / 'Caddyfile'
            config.write_text(text)
            env = dict(os.environ, XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'))
            log = (root / 'caddy.log').open('wb')
            process = subprocess.Popen([os.environ['JNPT_CADDY_EXE'], 'run', '--config', str(config), '--adapter', 'caddyfile'],
                                       env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            thread = threading.Thread(target=backend.serve_forever, daemon=True)
            thread.start()
            def request(path, method='GET'):
                conn = http.client.HTTPSConnection('127.0.0.1', port, context=ssl._create_unverified_context(), timeout=2)
                try:
                    conn.request(method, path)
                    res = conn.getresponse()
                    return res.status, res.read()
                finally:
                    conn.close()
            try:
                for _ in range(80):
                    if process.poll() is not None:
                        raise RuntimeError('Caddy test adapter exited: ' + (root / 'caddy.log').read_text())
                    try:
                        if request('/healthz') == (200, b'upstream'):
                            break
                    except OSError:
                        pass
                    time.sleep(.1)
                self.assertEqual(request('/api/device/v1/pair', 'POST'), (200, b'upstream'))
                for path in ['/', '/mcp', '/mcp/x', '/admin/mcp', '/api/admin/tokens', '/metrics', '/healthz/']:
                    for method in ['GET', 'POST']:
                        self.assertEqual(request(path, method)[0], 404, (method, path))
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.close()
                backend.shutdown()
                thread.join(timeout=5)
