"""Synthetic approved Git store, executed only inside disposable test containers.

This tests the mediator/package adapter, not SSH credentials or remote approval.
"""
import json
import os
from pathlib import Path
import subprocess

work = Path('/var/lib/script-runner/work')
work.mkdir()
for name, manifest in [('local', 'jnpt-script.yaml'), ('desk', 'jnpt-desktop.yaml')]:
    folder = work / name
    folder.mkdir()
    text = (f'name: {name}\ndescription: Synthetic probe.\nentry: main.py\n'
            'input_schema: {type: object}\ntools: [kartei_find]\ntimeout_s: 5\n')
    if name == 'desk':
        text += 'python: python.zip\n'
        (folder / 'python.zip').write_bytes(b'synthetic-opaque-runtime')
    (folder / manifest).write_text(text)
    (folder / 'main.py').write_text("print('probe-executed')\n")


def git(*args):
    return subprocess.check_output(['git', '-C', str(work), *args], text=True).strip()


git('init', '-q')
git('config', 'user.name', 'Synthetic')
git('config', 'user.email', 'test@example.invalid')
git('add', 'local', 'desk')
git('commit', '-qm', 'synthetic probe')
commit = git('rev-parse', 'HEAD')
git('clone', '-q', '--bare', str(work), '/var/lib/script-runner/store.git')
repo = 'ssh://git@git.example.invalid/org/scripts.git'
approved = Path('/var/lib/script-runner/approved')
approved.mkdir()
(approved / commit).write_text(repo)
keys = Path('/run/jnpt/plugins/script-runner')
keys.mkdir(parents=True)
(keys / 'runtime-key').write_text('synthetic-runtime-key')
for file, name in [('pins.json', 'local'), ('desktop-pins.json', 'desk')]:
    row = {'name': name, 'path': name, 'commit': commit, 'algo': 'sha1'}
    if name == 'desk':
        row['target_device'] = '12345678-1234-4123-8123-123456789abc'
    (keys / file).write_text(json.dumps({'version': 1, 'repo_url': repo, 'pins': [row]}))
for parent in [Path('/var/lib/script-runner'), Path('/run/jnpt/plugins')]:
    for path in [parent, *parent.rglob('*')]:
        os.chown(path, 65532, 65532)
print(commit)
