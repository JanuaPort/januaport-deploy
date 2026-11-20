"""SEC H1: remove the hardlink guard in an isolated copy, keep originals intact."""
from mutations import mutant


def main():
    mutant('H1 hardlink guard removed', 'dienst-einrichten.ps1',
           "if ((Get-DienstFileLinkCount $Path) -gt 1)", 'if ($false)',
           command=['-m', 'unittest', 'test_hardlinks.Hardlinks.test_real_hardlink_rejected_before_file_security_write', '-v'])
    print('H1: 1 mutation killed; original bytes unchanged.', flush=True)


if __name__ == '__main__':
    main()
