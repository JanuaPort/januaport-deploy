"""Exercise the real Windows PowerShell 5.1 filesystem/hash adapter."""
from pathlib import Path
import os
import hashlib
import shutil
import tempfile
import unittest

from test_profile import ROOT, run


def ps(script, source=ROOT / "einrichten.ps1"):
    # Passed as an argument, without an intervening shell.
    env = dict(os.environ)
    # PowerShell 7's inherited PSModulePath hides the standard 5.1 cmdlets.
    env = {key: value for key, value in env.items() if key.lower() != 'psmodulepath'}
    return run("powershell", "-NoProfile", "-Command",
               "$ErrorActionPreference='Stop'; . '" + str(source) + "'; " + script,
               check=False, env=env)


class Installer(unittest.TestCase):
    def test_manifest_shape_and_allowed_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'test') as tmp:
            target = Path(tmp)
            for name in ['SHA256SUMS', 'Caddyfile', 'docker-compose.yml', 'einrichten.ps1', '.env.example']:
                shutil.copyfile(ROOT / name, target / name)
            original = (target / 'SHA256SUMS').read_text()
            rows = original.splitlines()
            extra = hashlib.sha256((target / '.env.example').read_bytes()).hexdigest() + '  .env.example'
            cases = [(original + '../outside\n', 'Ungueltige'),
                     ('\n'.join([rows[0], rows[1], extra]) + '\n', 'Unerwarteter'),
                     (original + rows[0] + '\n', 'Unerwarteter'),
                     ('\n'.join(rows[:2]) + '\n', 'Unvollstaendige')]
            for manifest, message in cases:
                (target / 'SHA256SUMS').write_text(manifest)
                result = ps("Test-ProfileFiles '" + str(target) + "'")
                self.assertNotEqual(result.returncode, 0, manifest)
                self.assertIn(message, result.stderr)

    def test_real_checksum_adapter_rejects_corruption(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "test") as tmp:
            target = Path(tmp)
            for name in ["SHA256SUMS", "Caddyfile", "docker-compose.yml", "einrichten.ps1"]:
                shutil.copyfile(ROOT / name, target / name)
            command = "Test-ProfileFiles '" + str(target) + "'"
            clean = ps(command)
            self.assertEqual(clean.returncode, 0, clean.stderr)
            for name in ["Caddyfile", "docker-compose.yml", "einrichten.ps1"]:
                original = (target / name).read_bytes()
                (target / name).write_bytes(original + b"# corrupted\n")
                result = ps(command)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("SHA-256-Pruefung fehlgeschlagen", result.stderr)
                (target / name).write_bytes(original)

    def test_invalid_image_input_rejected(self):
        for value in ["", "sha256:bad", "sha256:" + "A" * 64,
                      "other.example/core:1", "x;exit 0", "$(exit 0)", "tag`nINJECTED=value"]:
            result = ps("Resolve-CoreImage '" + value + "'")
            self.assertNotEqual(result.returncode, 0, value)
            self.assertIn("Image-Tag oder sha256:", result.stderr)

    def test_existing_installation_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "test") as tmp:
            marker = Path(tmp) / ".env"
            marker.write_bytes(b"existing\n")
            result = ps("$Directory='" + tmp + "'; Install-Profile")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Ziel existiert bereits", result.stderr)
            self.assertEqual(marker.read_bytes(), b"existing\n")


if __name__ == "__main__":
    unittest.main()
