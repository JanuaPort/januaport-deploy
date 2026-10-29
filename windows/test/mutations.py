"""Remove one guard at a time in isolated copies; require a failing real-adapter test.

Run after the green tests: python -B windows/test/mutations.py
The W6 mutation downloads the exact upstream seccomp fixture and checks its hash.
"""
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

from test_profile import ROOT, run

TESTS = ROOT / 'test'
HTTPS = ['-m', 'unittest', 'test_profile.Profile.test_caddy_adapter_and_https_rejections', '-v']
COMPOSE = ['-m', 'unittest', 'test_profile.Profile.test_compose', '-v']
CHECKSUM = ['-m', 'unittest', 'test_install.Installer.test_real_checksum_adapter_rejects_corruption', '-v']


def mutant(label, file=None, old=None, new=None, command=None, extra_env=None):
    originals = {path: path.read_bytes() for path in ROOT.rglob('*') if path.is_file()}
    with tempfile.TemporaryDirectory(prefix='mutation-', dir=TESTS) as tmp:
        target = Path(tmp)
        for name in ['Caddyfile', 'docker-compose.yml', 'SHA256SUMS', 'einrichten.ps1', '.env.example']:
            shutil.copyfile(ROOT / name, target / name)
        (target / 'test').mkdir()
        shutil.copyfile(TESTS / 'seed_runner.py', target / 'test' / 'seed_runner.py')
        if file:
            path = target / file
            original = path.read_text()
            if original.count(old) != 1:
                raise RuntimeError('mutation anchor is not unique: ' + label)
            path.write_text(original.replace(old, new), newline='\n')
        # Keep the fixture internally consistent: a mutant must be killed by
        # its own negative test, not an unrelated stale checksum.
        (target / 'SHA256SUMS').write_text(''.join(
            hashlib.sha256((target / name).read_bytes()).hexdigest() + '  ' + name + '\n'
            for name in ['docker-compose.yml', 'Caddyfile', 'einrichten.ps1']), newline='\n')
        env = dict(os.environ, JNPT_PROFILE_ROOT=str(target), PYTHONPATH=str(TESTS))
        env.update(extra_env or {})
        result = run(sys.executable, '-B', *(command or HTTPS), env=env, check=False)
        if result.returncode == 0:
            raise AssertionError('SURVIVED: ' + label + '\n' + result.stdout + result.stderr)
        # Failures must be assertion failures, not broken adapters or missing files.
        if 'FAIL:' not in result.stderr or 'FAILED (failures=' not in result.stderr or 'errors=' in result.stderr:
            raise AssertionError('invalid mutation result: ' + label + '\n' + result.stdout + result.stderr)
        if label.startswith('W6') and ("'end': 'ok'" not in result.stderr or 'probe-executed' not in result.stderr):
            raise AssertionError('W6 mutation did not execute the real script:\n' + result.stderr)
        print('KILLED: ' + label, flush=True)
    for path, data in originals.items():
        if path.read_bytes() != data:
            raise AssertionError('original changed: ' + str(path.relative_to(ROOT)))


def main():
    mutant('W8 LAN route allowlist', 'Caddyfile', '@device path /api/device/v1/* /healthz', '@device path /*')
    mutant('Caddy admin socket off', 'Caddyfile', '\tadmin off\n', '')
    mutant('static leaf instead of internal issuer', 'Caddyfile',
           'tls /certs/cert.pem /certs/key.pem', 'tls internal',
           command=['-m', 'unittest', 'test_profile.Profile.test_static_leaf_configuration', '-v'])
    mutant('certificate retained on repeated setup', 'docker-compose.yml',
           'if [ -s /certs/cert.pem ] && [ -s /certs/key.pem ]; then\n          exit 0\n        fi',
           'rm -f /certs/cert.pem /certs/key.pem',
           command=['-m', 'unittest', 'test_profile.Profile.test_leaf_properties_and_partial_pair_rejection', '-v'])
    mutant('partial certificate pair preserved', 'docker-compose.yml',
           "if [ -e /certs/cert.pem ] || [ -e /certs/key.pem ]; then\n"
           "          echo 'Unvollstaendiges TLS-Paar; vorhandene Dateien bleiben erhalten.' >&2\n"
           "          exit 1\n        fi", ':',
           command=['-m', 'unittest', 'test_profile.Profile.test_leaf_properties_and_partial_pair_rejection', '-v'])
    mutant('leaf is not a CA', 'docker-compose.yml', 'basicConstraints=critical,CA:FALSE',
           'basicConstraints=critical,CA:TRUE',
           command=['-m', 'unittest', 'test_profile.Profile.test_leaf_properties_and_partial_pair_rejection', '-v'])
    mutant('rotation requires explicit flag', 'einrichten.ps1', 'if ($NeuesZertifikat)',
           'if ($true)', command=[str(TESTS / 'live.py')])
    mutant('W8 real loopback upstream', 'Caddyfile', 'reverse_proxy http://127.0.0.1:8484\n\t}',
           'reverse_proxy http://jnpt:8484\n\t}', command=[str(TESTS / 'live.py')])
    mutant('W8 admin port LAN rejection', 'docker-compose.yml', '127.0.0.1:8484:8484', '8484:8484',
           command=[str(TESTS / 'live.py')])
    mutant('Caddy namespace composition', 'docker-compose.yml', 'network_mode: "service:jnpt"',
           'network_mode: "service:script-runner"', command=COMPOSE)
    mutant('required core digest', 'docker-compose.yml', '${JANUAPORT_IMAGE_DIGEST:?SHA-256-Digest fehlt}',
           '${JANUAPORT_IMAGE_DIGEST:-' + 'a' * 64 + '}', command=COMPOSE)
    mutant('required core image', 'docker-compose.yml', '${JANUAPORT_IMAGE:?Image-Repository oder Tag fehlt}',
           '${JANUAPORT_IMAGE:-ghcr.io/januaport/januaport:0.87.1}', command=COMPOSE)
    mutant('sidecar digest pin', 'docker-compose.yml',
           'caddy@sha256:4c6e91c6ed0e2fa03efd5b44747b625fec79bc9cd06ac5235a779726618e530d',
           'caddy:2.10.2-alpine', command=COMPOSE)
    mutant('download checksum enforcement', 'einrichten.ps1', 'if ($actual -cne $digest)',
           'if ($false)', command=CHECKSUM)
    manifest_test = ['-m', 'unittest', 'test_install.Installer.test_manifest_shape_and_allowed_files', '-v']
    mutant('manifest line rejection', 'einrichten.ps1', "throw 'Ungueltige SHA256SUMS-Zeile.'", 'continue', command=manifest_test)
    mutant('manifest allowed filenames', 'einrichten.ps1',
           '$expected -cnotcontains $name -or $seen.ContainsKey($name)', '$seen.ContainsKey($name)', command=manifest_test)
    mutant('manifest duplicate rejection', 'einrichten.ps1',
           '$expected -cnotcontains $name -or $seen.ContainsKey($name)', '$expected -cnotcontains $name', command=manifest_test)
    mutant('manifest completeness', 'einrichten.ps1',
           'if ($seen.Count -ne $expected.Count)', 'if ($false)', command=manifest_test)
    mutant('invalid image input', 'einrichten.ps1',
           "throw 'Image-Tag oder sha256:<64 kleine Hex-Zeichen> erforderlich.'",
           "return @($Repository, ('a' * 64))",
           command=['-m', 'unittest', 'test_install.Installer.test_invalid_image_input_rejected', '-v'])
    mutant('existing installation refusal', 'einrichten.ps1',
           "throw 'Ziel existiert bereits und ist kein vollstaendiges Profil.'", 'return',
           command=['-m', 'unittest', 'test_install.Installer.test_existing_installation_preserved', '-v'])
    with tempfile.TemporaryDirectory(prefix='seccomp-', dir=TESTS) as tmp:
        # Upstream fixture, not a deployment asset. Never adds a sandbox to the profile.
        url = ('https://raw.githubusercontent.com/JanuaPort/januaport-plugins/'
               'script-runner-v0.3.1/script-runner/seccomp/jnpt-sandbox-seccomp.json')
        data = urllib.request.urlopen(url, timeout=30).read()
        if hashlib.sha256(data).hexdigest() != 'c76c13f6dfbc895e3dc01f4aea1611ccf475d898622e4af2e9ba158edc352b88':
            raise AssertionError('upstream seccomp fixture checksum mismatch')
        fixture = Path(tmp) / 'sandbox-seccomp.json'
        fixture.write_bytes(data)
        mutant('W6 no local sandbox execution',
               command=['-m', 'unittest', 'test_runner.Runner.test_desktop_package_without_local_execution', '-v'],
               extra_env={'JNPT_MUTATE_SANDBOX': str(fixture)})


if __name__ == '__main__':
    main()
