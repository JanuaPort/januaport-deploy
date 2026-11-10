"""CreateProfile verlangt einen Puffer von hoechstens MAX_PATH (260) Zeichen.

Befund B4/F1 (JanuaPort/januaport#1246): Mit 1024 antwortet Windows 0x800706F7
und dienst-einrichten.ps1 bricht auf jedem frischen Rechner ab.
"""
import pathlib
import re
import unittest

SKRIPT = pathlib.Path(__file__).resolve().parent.parent / "dienst-einrichten.ps1"


class CreateProfilePuffer(unittest.TestCase):
    def setUp(self):
        self.text = SKRIPT.read_text(encoding="utf-8")

    def test_puffer_und_groesse_sind_max_path(self):
        self.assertRegex(self.text, r"New-Object Text\.StringBuilder 260\b")
        aufruf = re.search(r"::CreateProfile\(([^)]*)\)", self.text)
        self.assertIsNotNone(aufruf)
        self.assertEqual(aufruf.group(1).split(",")[-1].strip(), "260")

    def test_kein_groesserer_puffer(self):
        for zahl in re.findall(r"StringBuilder (\d+)", self.text):
            self.assertLessEqual(int(zahl), 260)


if __name__ == "__main__":
    unittest.main()
