"""Real v0.3.1 mediator: desktop package succeeds, valid local pin is refused."""
import json
import time
import unittest
import uuid

from test_profile import ROOT, config, run


class Runner(unittest.TestCase):
    def test_desktop_package_without_local_execution(self):
        cfg = json.loads(config().stdout)
        image = cfg['services']['script-runner']['image']
        name = 'jnpt-windows-runner-test-' + uuid.uuid4().hex[:10]
        try:
            run('docker', 'run', '-d', '--name', name, '-v', '/run/script-runner', '-v', '/libs',
                '--entrypoint', 'sleep', image, 'infinity')
            commit = run('docker', 'exec', '-i', name, 'python3', '-I', '-',
                         input=(ROOT / 'test' / 'seed_runner.py').read_text()).stdout.strip()
            run('docker', 'exec', '-d', '--user', '65532:65532', name, 'script-runner', 'mediator')
            def request(method, params=None):
                payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}})
                code = ("import json,urllib.request\n"
                        "req=urllib.request.Request('http://127.0.0.1:8090/mcp',data=" + repr(payload.encode()) + ",headers="
                        + repr({'Authorization': 'Bearer synthetic-runtime-key',
                                'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json',
                                'X-Jnpt-Run-Token': 'jnptrun_' + 'a' * 43,
                                'X-Jnpt-Run-Id': '0b1e4c8a-6f2d-4b7e-9a31-2c5d7e8f9a10',
                                'X-Jnpt-Pin-Commit': commit}) + ")\n"
                        "print(urllib.request.urlopen(req,timeout=10).read().decode())")
                return json.loads(run('docker', 'exec', name, 'python3', '-I', '-c', code).stdout)
            for attempt in range(30):
                try:
                    listed = request('tools/list')['result']
                    desktop = listed['_meta']['januaport.ai/runner']['desktop_pins']
                    if desktop and desktop[0]['state'] == 'ready':
                        break
                except Exception:
                    if attempt == 29:
                        raise
                time.sleep(.25)
            self.assertEqual(desktop[0]['state'], 'ready', listed)
            # The valid local fixture is reported pending while isolation is invalid.
            self.assertEqual(listed['_meta']['januaport.ai/runner']['pins'][0]['state'], 'pending')
            self.assertEqual(listed['tools'], [])
            code = ("import urllib.request\n"
                    "r=urllib.request.Request('http://127.0.0.1:8090/desktop/package?commit=" + commit + "&path=desk',"
                    "headers={'Authorization':'Bearer synthetic-runtime-key'})\n"
                    "s=urllib.request.urlopen(r); print(s.status,len(s.read()))")
            status, length = run('docker', 'exec', name, 'python3', '-I', '-c', code).stdout.split()
            self.assertEqual(status, '200')
            self.assertGreater(int(length), 0)
            if __import__('os').environ.get('JNPT_MUTATE_SANDBOX'):
                # Deliberately remove W6 by starting the real guard. Profile is
                # only a mutation fixture, never part of the shipped Compose.
                run('docker', 'run', '-d', '--name', name + '-guard', '--network', 'none',
                    '--volumes-from', name + ':ro', '--user', '65533:65533', '--read-only',
                    '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                    '--security-opt', 'seccomp=' + __import__('os').environ['JNPT_MUTATE_SANDBOX'],
                    '--tmpfs', '/work:uid=65533,gid=65533,mode=0700',
                    '--tmpfs', '/tmp:uid=65533,gid=65533,mode=0700', image, 'guard')
                time.sleep(2)
            result = request('tools/call', {'name': 'local', 'arguments': {}})['result']
            meta = result['_meta']['januaport.ai/run']
            self.assertEqual((meta['end'], meta.get('detail'), meta['isolation']),
                             ('refused', 'state', 'invalid'), result)
        finally:
            run('docker', 'rm', '-f', '-v', name + '-guard', name, check=False)


if __name__ == '__main__':
    unittest.main()
