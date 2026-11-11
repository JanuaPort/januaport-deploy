"""Run from the repository root: python -B -m unittest discover -s windows/test -v.

Docker is required: the configuration adapters and HTTPS router are real binaries.
Only disposable containers/volumes belonging to this test are used.
"""
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import ssl
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(os.environ.get('JNPT_PROFILE_ROOT', Path(__file__).resolve().parents[1]))
EXAMPLE = {"JANUAPORT_IMAGE": "ghcr.io/januaport/januaport:0.87.1",
           "JANUAPORT_IMAGE_DIGEST": "81b25ca65d1cf3ff9c0bbf4d3b14fb5362debac9ed120db73cf5e2c5e18a4bfd"}
MAIL_VALUES = {
    'JNPT_SMTP_HOST': 'smtp.example.org',
    'JNPT_SMTP_PORT': '587',
    'JNPT_SMTP_TLS': 'starttls',
    'JNPT_SMTP_FROM': 'sender@example.org',
    'JNPT_SMTP_TO': 'recipient@example.org',
    'JNPT_SMTP_USERNAME': 'sender@example.org',
    'JNPT_NOTIFY_STATE': '/data/notify-state.json',
    'JNPT_NOTIFY_TRANSPORT': 'smtp',
    'JNPT_NOTIFY_GRAPH_TENANT_ID': 'example-tenant',
    'JNPT_NOTIFY_GRAPH_CLIENT_ID': 'example-client',
    'JNPT_NOTIFY_GRAPH_SENDER': 'sender@example.org',
    'JNPT_NOTIFY_GRAPH_CLIENT_SECRET_EXPIRES': '2030-01-01T00:00:00Z',
}
PROFILE_FILES = ('docker-compose.yml', 'Caddyfile', 'einrichten.ps1', '.gitignore',
                 'README.md', 'README.en.md', 'RUNBOOK.md', 'dienst-einrichten.ps1',
                 'jnpt-backup.ps1', 'jnpt-sperren.ps1', 'PRUEFSTEIN-B4.md',
                 'jnpt-update.ps1', 'PRUEFSTEIN-B5.md')
AUTOLOGON_SHA256 = '5d96bbc4e5b726d87c7cf547f5fe98f8f05434ec2130bd60cbf5671fd3a7381b'


def run(*args, input=None, check=True, env=None):
    return subprocess.run(args, input=input, text=True, capture_output=True,
                          check=check, env=env, timeout=120)


def config(directory=ROOT, extra_env=None, check=True, env_file=None):
    # Mail tests must not inherit an operator's settings or credentials.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('JNPT_SMTP_', 'JNPT_NOTIFY_', 'JNPT_UPDATE_')) and key != 'JNPT_ADMIN_URL'}
    env.update(EXAMPLE)
    env.update(extra_env or {})
    return run("docker", "compose", "--env-file", str(env_file or os.devnull), "-f",
               str(directory / "docker-compose.yml"), "config", "--format", "json",
               env=env, check=check)


def verify_sums(directory):
    rows = (directory / "SHA256SUMS").read_text().splitlines()
    expected = set(PROFILE_FILES) | {'Autologon64.exe'}
    found = set()
    for row in rows:
        digest, name = row.split("  ")
        if name not in expected or name in found:
            raise ValueError("unexpected checksum entry")
        found.add(name)
        if name == 'Autologon64.exe':
            if digest != AUTOLOGON_SHA256:
                raise ValueError('checksum mismatch: Autologon pin')
            continue
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest:
            raise ValueError("checksum mismatch: " + name)
    if found != expected:
        raise ValueError("incomplete checksum manifest")


def create_leaf(cfg, volume, san='DNS:localhost,IP:127.0.0.1'):
    service = cfg['services']['cert-init']
    # Compose config escapes dollars again in serialized output.
    script = service['command'][0].replace('$$', '$')
    return run('docker', 'run', '--rm', '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '-v', volume + ':/certs', '-e', 'CERT_SAN=' + san,
               '--entrypoint', '/bin/sh', service['image'], '-ec', script)


class Profile(unittest.TestCase):
    def test_plugin_network_addresses(self):
        cfg = json.loads(config().stdout)
        services = cfg['services']
        gateway_networks = services['jnpt']['networks']
        shared = {
            network for name, service in services.items() if name != 'jnpt'
            for network in service.get('networks', {}) if network in gateway_networks
        }
        self.assertIn('plugins', shared)
        # Check every shared network, including future sidecar attachments.
        for network in sorted(shared):
            with self.subTest(network=network, invariant='IPAM'):
                pools = cfg['networks'][network].get('ipam', {}).get('config', [])
                self.assertEqual(len(pools), 1)
                pool = pools[0]
                self.assertEqual(pool.get('subnet'), '172.21.0.0/16')
                self.assertEqual(pool.get('ip_range'), '172.21.128.0/17')
                subnet = ipaddress.IPv4Network(pool['subnet'])
                dynamic = ipaddress.IPv4Network(pool['ip_range'])
                self.assertTrue(dynamic.subnet_of(subnet))
                address = (gateway_networks[network] or {}).get('ipv4_address')
                self.assertIsNotNone(address)
                address = ipaddress.IPv4Address(address)
                self.assertIn(address, subnet)
                self.assertNotIn(address, dynamic)
                self.assertEqual(str(address), '172.21.0.2')
            for name, service in services.items():
                if name != 'jnpt' and network in service.get('networks', {}):
                    with self.subTest(network=network, service=name, invariant='dynamic sidecar'):
                        attachment = service['networks'][network] or {}
                        self.assertNotIn('ipv4_address', attachment)
                        self.assertNotIn('ipv6_address', attachment)

    def test_restart_policies(self):
        services = json.loads(config().stdout)['services']
        init_services = {'cert-init', 'plugin-init', 'script-runner-init'}
        self.assertTrue(init_services.issubset(services))
        for name, service in services.items():
            with self.subTest(service=name):
                self.assertEqual(service.get('restart'),
                                 'no' if name in init_services else 'unless-stopped')
    def test_update_feed_from_dotenv_or_environment_and_empty_offline_default(self):
        values = {'JNPT_UPDATE_MANIFEST_URL': 'https://updates.example.org/manifest.json',
                  'JNPT_UPDATE_PUBLIC_KEYS': 'synthetic-public-key'}
        with tempfile.TemporaryDirectory() as tmp:
            dotenv = Path(tmp) / '.env'
            for supplied in [values, dict.fromkeys(values, ''), {}]:
                dotenv.write_text(''.join(k+'='+v+'\n' for k,v in supplied.items()))
                for source in ['dotenv', 'process']:
                    with self.subTest(supplied=supplied, source=source):
                        cfg = json.loads(config(extra_env=supplied if source=='process' else None,
                                                env_file=dotenv if source=='dotenv' else None).stdout)
                        for key in values:
                            self.assertEqual(cfg['services']['jnpt']['environment'].get(key), supplied.get(key,''))
                        for name,service in cfg['services'].items():
                            if name!='jnpt':
                                self.assertTrue(set(values).isdisjoint(service.get('environment',{})), name)

    def test_mail_environment(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            dotenv.write_text(''.join(name + '=' + value + '\n'
                                      for name, value in MAIL_VALUES.items()))
            for source in ['process', 'dotenv']:
                cfg = json.loads(config(
                    extra_env=MAIL_VALUES if source == 'process' else None,
                    env_file=dotenv if source == 'dotenv' else None).stdout)
                environment = cfg['services']['jnpt'].get('environment', {})
                for name, value in MAIL_VALUES.items():
                    with self.subTest(source=source, variable=name):
                        self.assertEqual(environment.get(name), value)
                self.assertEqual(set(environment), set(MAIL_VALUES) |
                                 {'JNPT_SMTP_PASSWORD_FILE', 'JNPT_ADMIN_URL',
                                  'JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE',
                                  'JNPT_UPDATE_MANIFEST_URL', 'JNPT_UPDATE_PUBLIC_KEYS'})

    def test_graph_client_secret_is_file_only(self):
        attempted = {'JNPT_NOTIFY_GRAPH_CLIENT_SECRET': 'synthetic graph probe'}
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            dotenv.write_text(''.join(name + '=' + value + '\n'
                                      for name, value in attempted.items()))
            for source in ['process', 'dotenv']:
                with self.subTest(source=source):
                    cfg = json.loads(config(
                        extra_env=attempted if source == 'process' else None,
                        env_file=dotenv if source == 'dotenv' else None).stdout)
                    for name, service in cfg['services'].items():
                        self.assertNotIn('JNPT_NOTIFY_GRAPH_CLIENT_SECRET',
                                         service.get('environment', {}), name)
                    service = cfg['services']['jnpt']
                    mounts = [item for item in service.get('secrets', [])
                              if item['source'] == 'graph_client_secret']
                    self.assertEqual(len(mounts), 1)
                    self.assertEqual(str(PurePosixPath('/run/secrets') / mounts[0]['target']),
                                     '/run/secrets/graph_client_secret')
                    self.assertEqual(Path(cfg['secrets']['graph_client_secret']['file']),
                                     ROOT.resolve() / 'secrets' / 'graph_client_secret')

    def test_graph_client_secret_file_path_is_optional(self):
        variable = 'JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE'
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            for value in [None, '', '/run/secrets/graph_client_secret']:
                dotenv.write_text('' if value is None else variable + '=' + value + '\n')
                for source in ['process', 'dotenv']:
                    with self.subTest(value=value, source=source):
                        cfg = json.loads(config(
                            extra_env={variable: value} if source == 'process' and value is not None else None,
                            env_file=dotenv if source == 'dotenv' else None).stdout)
                        self.assertEqual(cfg['services']['jnpt']['environment'].get(variable),
                                         value or '')

    def test_smtp_has_no_graph_values(self):
        smtp = {name: value for name, value in MAIL_VALUES.items()
                if not name.startswith('JNPT_NOTIFY_GRAPH_') and name != 'JNPT_NOTIFY_TRANSPORT'}
        graph_names = {name for name in MAIL_VALUES if name.startswith('JNPT_NOTIFY_GRAPH_')}
        graph_names.add('JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE')
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            for transport in [None, '', 'smtp']:
                with self.subTest(transport=transport):
                    settings = dict(smtp)
                    if transport is not None:
                        settings['JNPT_NOTIFY_TRANSPORT'] = transport
                    dotenv.write_text(''.join(name + '=' + value + '\n'
                                              for name, value in settings.items()))
                    cfg = json.loads(config(env_file=dotenv).stdout)
                    graph = {name: value for name, value in cfg['services']['jnpt']['environment'].items()
                             if name.startswith('JNPT_NOTIFY_GRAPH_')}
                    self.assertEqual(graph, dict.fromkeys(graph_names, ''))

    def test_graph_certificates_not_forwarded(self):
        attempted = {'JNPT_NOTIFY_GRAPH_CERT_FILE': '/tmp/incorrect-graph-cert',
                     'JNPT_NOTIFY_GRAPH_KEY_FILE': '/tmp/incorrect-graph-key'}
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            dotenv.write_text(''.join(name + '=' + value + '\n'
                                      for name, value in attempted.items()))
            for source in ['process', 'dotenv']:
                with self.subTest(source=source):
                    cfg = json.loads(config(
                        extra_env=attempted if source == 'process' else None,
                        env_file=dotenv if source == 'dotenv' else None).stdout)
                    for name, service in cfg['services'].items():
                        for variable in attempted:
                            self.assertNotIn(variable, service.get('environment', {}), name)

    def test_mail_password_is_file_only(self):
        # Try both actual Compose input adapters, including an explicitly supplied
        # plaintext password. Neither may put it in a container environment.
        attempted = {'JNPT_SMTP_PASSWORD': 'synthetic mail probe',
                     'JNPT_SMTP_PASSWORD_FILE': '/tmp/incorrect-password-file'}
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            dotenv.write_text(''.join(name + '=' + value + '\n'
                                      for name, value in attempted.items()))
            for source in ['process', 'dotenv']:
                with self.subTest(source=source):
                    cfg = json.loads(config(
                        extra_env=attempted if source == 'process' else None,
                        env_file=dotenv if source == 'dotenv' else None).stdout)
                    service = cfg['services']['jnpt']
                    environment = service.get('environment', {})
                    self.assertNotIn('JNPT_SMTP_PASSWORD', environment)
                    self.assertEqual(environment.get('JNPT_SMTP_PASSWORD_FILE'),
                                     '/run/secrets/smtp_password')
                    mounts = [item for item in service.get('secrets', [])
                              if item['source'] == 'smtp_password']
                    self.assertEqual(len(mounts), 1)
                    # Compose 2 emits a relative target, Compose 5 an absolute one.
                    self.assertEqual(str(PurePosixPath('/run/secrets') / mounts[0]['target']),
                                     '/run/secrets/smtp_password')
                    self.assertEqual(Path(cfg['secrets']['smtp_password']['file']),
                                     ROOT.resolve() / 'secrets' / 'smtp_password')

    def test_mail_admin_url_is_local(self):
        attempted = {'JNPT_ADMIN_URL': 'https://smtp.example.org'}
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            dotenv = Path(tmp) / '.env'
            dotenv.write_text('JNPT_ADMIN_URL=https://smtp.example.org\n')
            for source in ['process', 'dotenv']:
                with self.subTest(source=source):
                    cfg = json.loads(config(
                        extra_env=attempted if source == 'process' else None,
                        env_file=dotenv if source == 'dotenv' else None).stdout)
                    self.assertEqual(cfg['services']['jnpt'].get('environment', {}).get('JNPT_ADMIN_URL'),
                                     'http://127.0.0.1:8484')

    def test_mail_unconfigured(self):
        for values in [None, dict.fromkeys(MAIL_VALUES, '')]:
            with self.subTest(values=values):
                result = config(extra_env=values, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                cfg = json.loads(result.stdout)
                environment = cfg['services']['jnpt'].get('environment', {})
                for name in MAIL_VALUES:
                    self.assertEqual(environment.get(name), '', name)

    def test_mail_secret_initialization_preserves_operator_files(self):
        self.assert_secret_initialization('smtp_password', b'synthetic mail probe')

    def test_graph_secret_initialization_preserves_operator_files(self):
        self.assert_secret_initialization('graph_client_secret', b'synthetic graph probe')

    def assert_secret_initialization(self, name, contents):
        from test_install import ps
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            dotenv = target / '.env'
            dotenv.write_bytes(b'JNPT_SMTP_HOST=smtp.example.org\n')
            original_env = dotenv.read_bytes()
            command = "Initialize-MailSecret '" + str(target) + "'"
            result = ps(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            secret = target / 'secrets' / name
            self.assertTrue(secret.is_file())
            self.assertEqual(secret.read_bytes(), b'')
            secret.write_bytes(contents)
            result = ps(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(secret.read_bytes(), contents)
            self.assertEqual(dotenv.read_bytes(), original_env)
        ignored = run('git', '-C', str(ROOT), 'check-ignore', '--no-index',
                      'secrets/' + name, check=False)
        self.assertEqual(ignored.returncode, 0, ignored.stderr)

    def test_mail_empty_secret_compose_adapter(self):
        from test_install import ps
        cfg = json.loads(config().stdout)
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            initialized = ps("Initialize-MailSecret '" + str(target) + "'")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            # Use the profile's actual secret declaration with its source rebased
            # to the disposable installation, and its existing Python sidecar image.
            declarations = {}
            for name in ['smtp_password', 'graph_client_secret']:
                self.assertIn(name, cfg['secrets'])
                declarations[name] = dict(cfg['secrets'][name],
                                          file=str(target / 'secrets' / name))
            probe = {
                'services': {'probe': {
                    'image': cfg['services']['script-runner']['image'],
                    'network_mode': 'none',
                    'entrypoint': ['python3', '-I', '-c'],
                    'command': ["from pathlib import Path; "
                                "paths=[Path('/run/secrets')/name for name in "
                                "('smtp_password', 'graph_client_secret')]; "
                                "assert all(p.is_file() and p.read_bytes() == b'' for p in paths)"],
                    'secrets': cfg['services']['jnpt']['secrets'],
                }},
                'secrets': declarations,
            }
            manifest = target / 'probe.json'
            manifest.write_text(json.dumps(probe))
            args = ('docker', 'compose', '-p', 'jnpt-mail-test-' + uuid.uuid4().hex[:10],
                    '-f', str(manifest))
            try:
                result = run(*args, 'run', '--rm', '-T', '--no-deps', 'probe', check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
            finally:
                run(*args, 'down', '-v', '--remove-orphans')

    def test_static_leaf_configuration(self):
        caddyfile = (ROOT / 'Caddyfile').read_text()
        self.assertNotIn('tls internal', caddyfile)
        self.assertIn('tls /certs/cert.pem /certs/key.pem', caddyfile)
        cfg = json.loads(config().stdout)
        mounts = cfg['services']['caddy']['volumes']
        leaf = [mount for mount in mounts if mount['target'] == '/certs']
        self.assertEqual(len(leaf), 1)
        self.assertTrue(leaf[0]['read_only'])

    def test_leaf_properties_and_partial_pair_rejection(self):
        cfg = json.loads(config().stdout)
        volume = 'jnpt-windows-cert-test-' + uuid.uuid4().hex[:10]
        image = cfg['services']['cert-init']['image']
        try:
            create_leaf(cfg, volume, 'DNS:localhost,DNS:probe-host,IP:127.0.0.1,IP:192.0.2.10')
            text = run('docker', 'run', '--rm', '-v', volume + ':/certs:ro', image,
                       'x509', '-in', '/certs/cert.pem', '-noout', '-text').stdout
            for value in ['CA:FALSE', 'prime256v1', 'DNS:localhost', 'DNS:probe-host',
                          'IP Address:127.0.0.1', 'IP Address:192.0.2.10']:
                self.assertIn(value, text)
            # At least ten years, but not an accidentally indefinite certificate.
            for days, expected in [(3652, 0), (3654, 1)]:
                check = run('docker', 'run', '--rm', '-v', volume + ':/certs:ro', image,
                            'x509', '-in', '/certs/cert.pem', '-noout', '-checkend',
                            str(days * 86400), check=False)
                self.assertEqual(check.returncode, expected)
            def fingerprint():
                return run('docker', 'run', '--rm', '-v', volume + ':/certs:ro', image,
                           'x509', '-in', '/certs/cert.pem', '-noout', '-fingerprint', '-sha256').stdout
            original_pin = fingerprint()
            create_leaf(cfg, volume)
            self.assertEqual(fingerprint(), original_pin, 'initializer replaced an existing leaf')
            run('docker', 'run', '--rm', '-v', volume + ':/certs', '--entrypoint', '/bin/sh',
                image, '-ec', 'rm /certs/key.pem')
            # A partial existing pair is never silently replaced.
            with self.assertRaises(subprocess.CalledProcessError):
                create_leaf(cfg, volume)
        finally:
            run('docker', 'volume', 'rm', volume, check=False)

    def test_sums_and_tampering(self):
        verify_sums(ROOT)
        with tempfile.TemporaryDirectory(dir=ROOT / "test") as tmp:
            dst = Path(tmp)
            for name in ('SHA256SUMS', *PROFILE_FILES):
                (dst / name).write_bytes((ROOT / name).read_bytes())
            for name in PROFILE_FILES:
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
            create_leaf(cfg, ident + '-leaf')
            run("docker", "run", "-d", "--name", ident, "-p", "127.0.0.1::443",
                "--entrypoint", "python3", backend, "-c",
                "from http.server import HTTPServer,BaseHTTPRequestHandler\n"
                "class H(BaseHTTPRequestHandler):\n"
                " def do_GET(self):\n"
                "  self.send_response(200); self.end_headers(); self.wfile.write(b'upstream')\n"
                " do_POST=do_GET\n"
                "HTTPServer(('127.0.0.1',8484),H).serve_forever()")
            run("docker", "run", "-d", "--name", ident + "-caddy", "--network", "container:" + ident,
                "-v", str(ROOT / "Caddyfile") + ":/etc/caddy/Caddyfile:ro",
                '-v', ident + '-leaf:/certs:ro', image)
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
            loaded = adapted['apps']['tls']['certificates']['load_files']
            self.assertEqual(len(loaded), 1)
            self.assertEqual((loaded[0]['certificate'], loaded[0]['key']),
                             ('/certs/cert.pem', '/certs/key.pem'))
            # SEC K1: Caddy is the edge. Behind it every request reaches the core as
            # loopback, so there must be no plaintext listener and no plaintext path
            # to the upstream.
            servers = adapted['apps']['http']['servers']
            for name, server in servers.items():
                self.assertEqual(server.get('listen'), [':443'], name)
                self.assertIn('tls_connection_policies', server, name)
            plain = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            plain.request("GET", "/healthz")
            plain_res = plain.getresponse()
            self.assertNotEqual(plain_res.read(), b"upstream")
            self.assertNotEqual(plain_res.status, 200)
            plain.close()
            for path in ["/", "/admin/mcp", "/admin/mcp/", "/api/admin/tokens", "/mcp", "/mcp/x",
                         "/metrics", "/healthz/", "/api/device/v1", "/api/device/v10/pair",
                         "/api/device/v1/../../../admin/mcp", "/api/device/v1/%2e%2e/%2e%2e/%2e%2e/admin/mcp"]:
                for method in ["GET", "POST"]:
                    self.assertEqual(request(path, method)[0], 404, (method, path))
        finally:
            run("docker", "rm", "-f", "-v", ident + "-caddy", ident, check=False)
            run('docker', 'volume', 'rm', ident + '-leaf', check=False)


if __name__ == "__main__":
    unittest.main()
