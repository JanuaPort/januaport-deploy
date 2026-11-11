"""B5: PS 5.1 entry point, native Docker shim, backup child and real NTFS."""
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

from test_profile import ROOT, run

REPOSITORY = 'ghcr.io/januaport/januaport'
DIGEST = 'sha256:' + 'b' * 64
OLD = (b'# retained JANUAPORT_IMAGE=ghcr.io/januaport/januaport:old\r\nJANUAPORT_IMAGE=ghcr.io/januaport/januaport:old\r\n'
       b'JNPT_SMTP_HOST=smtp.example.org\nJANUAPORT_IMAGE_DIGEST=' + b'a' * 64 + b'\r\nKEEP=Gr\xc3\xbc\xc3\x9fe')
NEW = OLD.replace(b'\r\nJANUAPORT_IMAGE=ghcr.io/januaport/januaport:old', b'\r\nJANUAPORT_IMAGE='+REPOSITORY.encode()).replace(b'a' * 64, b'b' * 64)
SHIM = r'''
import json,os,pathlib,sys
r=pathlib.Path(os.environ['PROBE_ROOT']); a=sys.argv[1:]
if a==['compose','up','-d']:
    with (r/'trace').open('a') as f: f.write(json.dumps(['env',(r/'p'/'.env').read_text()])+'\n')
with (r/'trace').open('a') as f: f.write(json.dumps(a)+'\n')
mode=os.environ.get('PROBE_FAIL','')
if a==['compose','exec','-T','jnpt','/jnpt','update','plan','--json']:
    if mode=='plan-stderr': print('PRIVATE NATIVE OUTPUT',file=sys.stderr)
    if mode=='offline': sys.exit(25)
    sys.stdout.write((r/'plan').read_text()); sys.exit(0)
if a[:7]==['compose','exec','-T','jnpt','/jnpt','update','record']:
    print('PRIVATE NATIVE OUTPUT'); print('PRIVATE NATIVE OUTPUT',file=sys.stderr)
    sys.exit(19 if mode=='record' else 0)
if a[:1]==['pull']:
    print('PRIVATE NATIVE OUTPUT'); print('PRIVATE NATIVE OUTPUT',file=sys.stderr)
    sys.exit(17 if mode=='pull' else 0)
if a==['compose','up','-d']:
    sys.exit(18 if mode=='up' else 0)
if a==['compose','run','--rm','--no-deps','--entrypoint','openssl','cert-init','x509','-in','/certs/cert.pem','-noout','-fingerprint','-sha256']:
    print('sha256 Fingerprint='+':'.join(['AB']*32)); sys.exit(0)
sys.exit(92)
'''


class Update(unittest.TestCase):
    def invoke(self, action='approved', digest=DIGEST, mode='', identity=True,
               raw=None, extra='', incomplete=None, seed=False):
        source = ROOT / 'jnpt-update.ps1'
        self.assertTrue(source.is_file(), 'B5 script must be shipped')
        # Short paths also keep mutation runs below Win32 MAX_PATH.
        with tempfile.TemporaryDirectory(prefix='u-') as tmp:
            root = Path(tmp); profile = root / 'p'; profile.mkdir()
            for name in ('einrichten.ps1', 'docker-compose.yml', 'Caddyfile'):
                shutil.copyfile(ROOT / name, profile / name)
            (profile / 'log').mkdir(); (profile / 'backups').mkdir()
            (profile / '.env').write_bytes(OLD)
            # Actual separate powershell.exe invocation; never dot-sourced.
            (profile / 'jnpt-backup.ps1').write_text(r'''
param($ProfileDirectory,$Target)
Add-Content (Join-Path $env:PROBE_ROOT 'trace') ('["backup","'+$PID+'"]')
if ($ProfileDirectory -cne (Join-Path $env:PROBE_ROOT 'p') -or $Target -cne "E:\Back'up\") {exit 99}
Write-Output 'PRIVATE CHILD OUTPUT'
[Console]::Error.WriteLine('PRIVATE CHILD OUTPUT')
if ($env:PROBE_FAIL -eq 'backup') {exit 7}
exit 0
''')
            if incomplete:
                (profile / incomplete).unlink()
            (root / 'docker_shim.py').write_text(SHIM)
            (root / 'docker.cmd').write_text('@echo off\n"' + sys.executable + '" "' + str(root / 'docker_shim.py') + '" %*\n')
            plan = dict(current='opaque-current', latest='other.example/EVIL:latest', digest=digest,
                        action=action, on_failure='rollback', reason='other.example/EVIL:reason')
            (root / 'plan').write_text(json.dumps(plan) + '\n' if raw is None else raw)
            if seed:
                (profile / 'log' / 'update.log').write_text('synthetic previous entry\n' * 105)
            bootstrap = r'''
function Invoke-WebRequest {param($Uri,$TimeoutSec,[switch]$UseBasicParsing)
    if ($Uri -cne 'http://127.0.0.1:8484/healthz' -or $TimeoutSec -gt 3) {throw 'wrong host health adapter'}
    Add-Content (Join-Path $env:PROBE_ROOT 'trace') '["health"]'
    [pscustomobject]@{StatusCode=$(if ($env:PROBE_FAIL -eq 'health') {503} else {200})}
}
function Get-ServedLeafFingerprint {
    Add-Content (Join-Path $env:PROBE_ROOT 'trace') '["tls"]'
    if ($env:PROBE_FAIL -eq 'tls') {return ('c'*64)}
    'ab'*32
}
function Start-Sleep {param($Seconds,$Milliseconds)}
'''
            if identity:
                bootstrap += "\nfunction Get-CurrentAccount {$env:COMPUTERNAME+'\\jnpt-dienst'}\n"
            bootstrap += r"""
if (Test-Path -LiteralPath (Join-Path $ProfileDirectory '.env')) {
    [IO.File]::WriteAllText((Join-Path $env:PROBE_ROOT 'acl-before'), ((& icacls.exe (Join-Path $ProfileDirectory '.env')) -join "`n"))
}
""" + extra + '\n'
            text = source.read_text(encoding='utf-8-sig')
            anchor = "if ($MyInvocation.InvocationName -ne '.')"
            self.assertEqual(text.count(anchor), 1)
            script = profile / 'jnpt-update.ps1'
            script.write_text(text.replace(anchor, bootstrap + anchor), encoding='utf-8-sig')
            driver = root / 'driver.ps1'
            driver.write_text("try { & '" + str(script) + "' -ProfileDirectory '" + str(profile) + "' -Target 'E:\\Back''up\\'; $code=$LASTEXITCODE } catch {$code=1}\n" + r"""
+if (Test-Path -LiteralPath (Join-Path $env:PROBE_ROOT 'p/.env')) {
+    [IO.File]::WriteAllText((Join-Path $env:PROBE_ROOT 'acl-after'), ((& icacls.exe (Join-Path $env:PROBE_ROOT 'p/.env')) -join "`n"))
+}
+exit $code
+""".replace('\n+','\n'), encoding='utf-8-sig')
            env = {k:v for k,v in os.environ.items() if k.lower() != 'psmodulepath'}
            env.update(PROBE_ROOT=tmp, PROBE_FAIL=mode, PATH=tmp+os.pathsep+env['PATH'])
            result = run('powershell.exe','-NoProfile','-File',str(driver),check=False,env=env)
            trace = [json.loads(s) for s in (root/'trace').read_text().splitlines()] if (root/'trace').exists() else []
            self.env_after = (profile/'.env').read_bytes() if (profile/'.env').exists() else None
            self.log = (profile/'log'/'update.log').read_text(encoding='utf-8-sig') if (profile/'log'/'update.log').exists() else ''
            self.assertNotIn('PRIVATE', result.stdout + result.stderr + self.log)
            self.assertEqual(result.stdout, '')
            self.assertLessEqual(len(self.log.splitlines()), 100)
            for value in [os.environ.get('USERNAME',''), 'jnpt-dienst']:
                if value: self.assertNotIn(value, self.log)
            self.assertEqual(list(profile.glob('*.tmp')), [])
            if (root/'acl-before').exists():
                self.assertEqual((root/'acl-before').read_text().strip(), (root/'acl-after').read_text().strip())
            return result, trace

    @staticmethod
    def records(trace):
        return [a for a in trace if 'record' in a]

    def test_01_none_only_records_none(self):
        r,t = self.invoke('none', digest='')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(len(t),2,t)
        self.assertIn('--result=none',t[-1]); self.assertEqual(self.env_after,OLD)

    def success(self, action):
        r,t = self.invoke(action, seed=True)
        self.assertEqual(r.returncode,0,r.stderr)
        def index(word):
            matches=[i for i,a in enumerate(t) if word in a]
            self.assertTrue(matches, 'missing protocol event: '+word)
            return matches[0]
        self.assertLess(index('plan'),index('backup'))
        self.assertLess(index('backup'),index('pull'))
        self.assertLess(index('pull'),index('env'))
        self.assertLess(index('env'),index('up'))
        self.assertLess(index('env'),index('health'))
        self.assertLess(index('up'),index('health'))
        self.assertLess(index('health'),index('tls'))
        self.assertLess(index('tls'),index('record'))
        self.assertEqual(next(a for a in t if a[0]=='pull'),['pull',REPOSITORY+'@'+DIGEST])
        self.assertEqual(self.env_after,NEW)
        rec=self.records(t); self.assertEqual(len(rec),1)
        for arg in ['--result=installed','--from=opaque-current','--to=other.example/EVIL:latest','--digest='+DIGEST]: self.assertIn(arg,rec[0])
        self.assertFalse(any(a.startswith('--backup') for a in rec[0]))
        self.assertEqual(sum(a==['compose','up','-d'] for a in t),1)
        return t

    def test_02_approved_green(self): self.success('approved')
    def test_03_unattended_green(self): self.success('unattended')

    def test_04_invalid_digest_and_plan_rejected(self):
        for digest in ['', 'sha256:'+'B'*64, 'sha256:'+'b'*63, 'b'*64, DIGEST+'\n',DIGEST+'\nEVIL=1',REPOSITORY+'@'+DIGEST]:
            with self.subTest(digest=digest):
                r,t=self.invoke(digest=digest)
                self.assertEqual(r.returncode,2,r.stderr); self.assertEqual(self.env_after,OLD)
                self.assertEqual(len(t),1,t)
        good=json.dumps(dict(current='x',latest='y',digest=DIGEST,action='none',on_failure='',reason=''))
        for raw in ['', '{}\n{}\n', '\n'+good+'\n', good+'\n\n', '[{}]\n', '{\n"action":"none"\n}\n', '{}\n', good.replace('none','unknown')+'\n']:
            with self.subTest(raw=raw):
                r,t=self.invoke(raw=raw)
                self.assertEqual(r.returncode,2,r.stderr); self.assertEqual(len(t),1,t)

    def test_05_backup_or_pull_failure_preserves_env(self):
        for mode in ['backup','pull']:
            with self.subTest(mode=mode):
                r,t=self.invoke(mode=mode)
                self.assertEqual(r.returncode,3,r.stderr); self.assertEqual(self.env_after,OLD)
                self.assertFalse(any('up' in a for a in t)); self.assertEqual(self.records(t),[])
                if mode=='backup': self.assertFalse(any('pull' in a for a in t))

    def test_06_health_tls_or_up_failure_records_failed_without_reversal(self):
        for mode in ['health','tls','up']:
            with self.subTest(mode=mode):
                r,t=self.invoke(mode=mode)
                self.assertEqual(r.returncode,6,r.stderr); self.assertEqual(self.env_after,NEW)
                rec=self.records(t); self.assertEqual(len(rec),1)
                self.assertIn('--result=failed',rec[0]); self.assertIn('--digest='+DIGEST,rec[0])
                self.assertEqual(sum(a==['compose','up','-d'] for a in t),1)
                self.assertIn('JANUAPORT_IMAGE='+REPOSITORY+':old',self.log)
                self.assertIn('JANUAPORT_IMAGE_DIGEST='+'a'*64,self.log)

    def test_07_unbookable_result_only_logged_and_exit_preserved(self):
        for action,extra,expected in [('none','',0),('approved','',0),('approved',"function Get-ServedLeafFingerprint {'wrong'}",6)]:
            with self.subTest(action=action,expected=expected):
                r,t=self.invoke(action,mode='record',extra=extra)
                self.assertEqual(r.returncode,expected,r.stderr)
                self.assertEqual(r.stderr,'')
                self.assertIn('record',self.log); self.assertIn('failed',self.log)
                self.assertEqual(len(self.records(t)),1)

    def test_08_rollback_no_intervention_or_record(self):
        r,t=self.invoke('rollback')
        self.assertEqual(r.returncode,2); self.assertEqual(len(t),1,t)
        self.assertEqual(self.env_after,OLD); self.assertIn('RUNBOOK',self.log)

    def test_09_session_and_profile_rejected_before_docker(self):
        r,t=self.invoke(identity=False)
        self.assertEqual(r.returncode,1,r.stderr); self.assertEqual(t,[])
        for name in ['.env','docker-compose.yml','jnpt-backup.ps1','Caddyfile']:
            with self.subTest(missing=name):
                r,t=self.invoke(incomplete=name)
                self.assertEqual(r.returncode,1,r.stderr); self.assertEqual(t,[])

    def test_10_native_stderr_does_not_abort_and_offline_fails_loudly(self):
        r,t=self.invoke(mode='plan-stderr')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(self.records(t))
        r,t=self.invoke(mode='offline')
        self.assertEqual(r.returncode,2); self.assertTrue(r.stderr)
        self.assertEqual(len(t),1); self.assertEqual(self.env_after,OLD)

    def test_11_core_owns_policy_guard(self):
        # PS tokens remove comments (including block comments), preserving strings.
        from test_install import ps
        result=ps(r'''$tokens=$null; $errors=$null
[Management.Automation.Language.Parser]::ParseFile($env:PROBE_SOURCE,[ref]$tokens,[ref]$errors) | Out-Null
if ($errors.Count) {throw 'parse errors'}
($tokens | Where-Object {$_.Kind -ne 'Comment'} | ForEach-Object {$_.Text}) -join ' '
''',extra_env={'PROBE_SOURCE':str(ROOT/'jnpt-update.ps1')})
        self.assertEqual(result.returncode,0,result.stderr)
        code=result.stdout.lower()
        for word in ['action','digest','plan','record']: self.assertIn(word,code)
        for pattern in [r'\[version\]',r'has_migration',r'\bbump\b',r'min_version',r'sort-object',r'wartungsfenster',r'update\s+rollback',r"['\"]update['\"]\s*,\s*['\"]rollback",r'jnpt\s+restore',r"['\"]/jnpt['\"]\s*,\s*['\"]restore",r'get-filehash',r'cosign',r'setaccesscontrol',r'(?:(?:current|latest).{0,30}-(?:gt|lt|ge|le)|-(?:gt|lt|ge|le).{0,30}(?:current|latest))']:
            self.assertNotRegex(code,pattern)


class UpdateAdapter(unittest.TestCase):
    def test_non_core_programs_and_other_docker_operations_rejected_at_native_adapter(self):
        probe=Update()
        for args in ["@('compose','exec','-T','jnpt','sh')", "@('compose','exec','-T','jnpt','stat')", "@('compose','cp','jnpt:/data','x')", "@('compose','exec','-T','jnpt','/jnpt','restore')", "@('compose','exec','-T','jnpt','/jnpt','healthz')", "@('pull','other.example/EVIL@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')", "@('compose','exec','-T','jnpt','/jnpt','update','rollback')"]:
            with self.subTest(args=args):
                r,t=probe.invoke(extra='Invoke-UpdateDocker '+args+' | Out-Null\nexit 99')
                self.assertNotEqual(r.returncode,99); self.assertNotEqual(r.returncode,0)
                self.assertEqual(t,[])

    def test_native_process_timeout_is_bounded_at_real_process_adapter(self):
        r,t=Update().invoke(extra="try {Invoke-UpdateProcess '[Threading.Thread]::Sleep(5000)' 1 | Out-Null; exit 99} catch {exit 12}")
        self.assertEqual(r.returncode,12,r.stderr)
        self.assertEqual(t,[])

    def test_log_escapes_untrusted_values_and_redacts_current_identity(self):
        from test_install import ps
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'log').mkdir()
            result=ps("$ProfileDirectory='"+tmp+"'; Write-UpdateLog ($env:USERNAME+\"`nEVIL=1\"+ 'jnpt-dienst')",ROOT/'jnpt-update.ps1')
            self.assertEqual(result.returncode,0,result.stderr)
            text=(root/'log'/'update.log').read_text()
            self.assertEqual(len(text.splitlines()),1)
            self.assertNotIn(os.environ['USERNAME'],text); self.assertNotIn('jnpt-dienst',text)
            self.assertIn(r'\nEVIL=1',text)

    def test_ambiguous_env_is_not_replaced(self):
        probe=Update()
        for line in ['JANUAPORT_IMAGE=duplicate', 'JANUAPORT_IMAGE_DIGEST=duplicate']:
            with self.subTest(line=line):
                r,t=probe.invoke(extra="[IO.File]::AppendAllText((Join-Path $ProfileDirectory '.env'), \"`n"+line+"`n\")")
                self.assertEqual(r.returncode,3,r.stderr)
                self.assertFalse(any('up' in a for a in t))


if __name__=='__main__': unittest.main()
