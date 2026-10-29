"""Run from the repository root: python -B -m unittest discover -s windows/test -v.

Docker is required: the configuration adapters and HTTPS router are real binaries.
Only disposable containers/volumes belonging to this test are used.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(os.environ.get('JNPT_PROFILE_ROOT', Path(__file__).resolve().parents[1]))
EXAMPLE = {"JANUAPORT_IMAGE": "ghcr.io/januaport/januaport:0.87.1",
           "JANUAPORT_IMAGE_DIGEST": "81b25ca65d1cf3ff9c0bbf4d3b14fb5362debac9ed120db73cf5e2c5e18a4bfd"}


def run(*args, input=None, check=True, env=None):
    return subprocess.run(args, input=input, text=True, capture_output=True,
                          check=check, env=env, timeout=120)


def config(directory=ROOT, extra_env=None, check=True):
    env = dict(os.environ, **EXAMPLE)
    env.update(extra_env or {})
    return run("docker", "compose", "--env-file", os.devnull, "-f",
               str(directory / "docker-compose.yml"), "config", "--format", "json",
               env=env, check=check)


def verify_sums(directory):
    rows = (directory / "SHA256SUMS").read_text().splitlines()
    expected = {"docker-compose.yml", "Caddyfile", "einrichten.ps1"}
    found = set()
    for row in rows:
        digest, name = row.split("  ")
        if name not in expected or name in found:
            raise ValueError("unexpected checksum entry")
        found.add(name)
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError("checksum mismatch: " + name)
    if found != expected:
        raise ValueError("incomplete checksum manifest")


class Profile(unittest.TestCase):
    def test_static_leaf_configuration(self):
        caddyfile = (ROOT / 'Caddyfile').read_text()
        self.assertNotIn('tls internal', caddyfile)
        self.assertIn('tls /certs/cert.pem /certs/key.pem', caddyfile)
        cfg = json.loads(config().stdout)
        mounts = cfg['services']['caddy']['volumes']
        leaf = [mount for mount in mounts if mount['target'] == '/certs']
        self.assertEqual(len(leaf), 1)
        self.assertTrue(leaf[0]['read_only'])

    def test_sums_and_tampering(self):
        verify_sums(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "test") as tmp:
            dst = Path(tmp)
            for name in ["SHA256SUMS", "Caddyfile", "docker-compose.yml", "einrichten.ps1"]:
                (dst / name).write_bytes((ROOT / name).read_bytes())
            for name in ["Caddyfile", "docker-compose.yml", "einrichten.ps1"]:
                original = (dst / name).read_bytes()
                (dst / name).write_bytes(original + b"# tampered\n")
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    verify_sums(dst)
                (dst / name).write_bytes(original)

    def test_compose(self):
        cfg = json.loads(config().stdout)
        services = cfg["services"]
        self.assertEqual(services["caddy"]["network_mode"], "service:jnpt")
        self.assertNotIn("ports", services["caddy"])
        self.assertNotIn("script-runner-sandbox", services)
        for name, service in services.items():
            self.assertRegex(service["image"], r"@sha256:[a-f0-9]{64}$", name)
            for port in service.get("ports", []):
                self.assertEqual(name, "jnpt")
                if port["target"] != 443:
                    self.assertEqual(port["host_ip"], "127.0.0.1")
                    self.assertEqual(port["target"], 8484)
            if name.startswith("script-runner"):
                self.assertEqual(service["runtime"], "runc")
        self.assertNotEqual(config(extra_env={"JANUAPORT_IMAGE_DIGEST": ""}, check=False).returncode, 0)
        self.assertNotEqual(config(extra_env={"JANUAPORT_IMAGE": ""}, check=False).returncode, 0)
        self.assertTrue(cfg["networks"]["plugins"]["internal"])

    def test_caddy_adapter_and_https_rejections(self):
        cfg = json.loads(config().stdout)
        image = cfg["services"]["caddy"]["image"]
        adapted = json.loads(run("docker", "run", "--rm", "-i", image, "caddy", "adapt",
                                 "--config", "/dev/stdin", "--adapter", "caddyfile",
                                 input=(ROOT / "Caddyfile").read_text()).stdout)
        ident = "jnpt-windows-test-" + uuid.uuid4().hex[:10]
        # A real HTTP backend proves that allowed requests reach reverse_proxy.
        backend = cfg["services"]["script-runner"]["image"]
        try:
            run("docker", "run", "-d", "--name", ident, "-p", "127.0.0.1::443",
                "--entrypoint", "python3", backend, "-c",
                "from http.server import HTTPServer,BaseHTTPRequestHandler\n"
                "class H(BaseHTTPRequestHandler):\n"
                " def do_GET(self):\n"
                "  self.send_response(200); self.end_headers(); self.wfile.write(b'upstream')\n"
                " do_POST=do_GET\n"
                "HTTPServer(('127.0.0.1',8484),H).serve_forever()")
            run("docker", "run", "-d", "--name", ident + "-caddy", "--network", "container:" + ident,
                "-v", str(ROOT / "Caddyfile") + ":/etc/caddy/Caddyfile:ro", image)
            port = int(run("docker", "port", ident, "443/tcp").stdout.strip().rsplit(":", 1)[1])
            def request(path, method="GET"):
                conn = http.client.HTTPSConnection("127.0.0.1", port, context=ssl._create_unverified_context(), timeout=3)
                conn.request(method, path)
                res = conn.getresponse()
                result = res.status, res.read()
                conn.close()
                return result
            for attempt in range(40):
                try:
                    if request("/healthz") == (200, b"upstream"):
                        break
                except (OSError, ssl.SSLError):
                    pass
                time.sleep(.25)
            self.assertEqual(request("/api/device/v1/pair", "POST"), (200, b"upstream"))
            # Probe Caddy's actual admin socket from the shared namespace.
            admin_probe = run('docker', 'exec', ident, 'python3', '-I', '-c',
                              "import socket; s=socket.create_connection(('127.0.0.1',2019),timeout=2)", check=False)
            self.assertNotEqual(admin_probe.returncode, 0, 'Caddy admin socket exposed')
            # Check the real container trust-store directory, as well as the adapter setting.
            store = run('docker', 'exec', ident + '-caddy', 'ls', '/usr/local/share/ca-certificates').stdout
            self.assertNotIn('Caddy', store)
            self.assertFalse(adapted['apps']['pki']['certificate_authorities']['local']['install_trust'])
            for path in ["/", "/admin/mcp", "/admin/mcp/", "/api/admin/tokens", "/mcp", "/mcp/x",
                         "/metrics", "/healthz/", "/api/device/v1", "/api/device/v10/pair",
                         "/api/device/v1/../../../admin/mcp", "/api/device/v1/%2e%2e/%2e%2e/%2e%2e/admin/mcp"]:
                for method in ["GET", "POST"]:
                    self.assertEqual(request(path, method)[0], 404, (method, path))
        finally:
            run("docker", "rm", "-f", "-v", ident + "-caddy", ident, check=False)


if __name__ == "__main__":
    unittest.main()
