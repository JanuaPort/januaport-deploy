package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestAuditMutationen(t *testing.T) {
	for _, m := range []struct{ name, file, old, replacement, test string }{
		{"APT_Pin_entfernt", "cloud-init.yaml.tftpl", `if [ "$ist" != "$soll" ]; then`, "if false; then", "TestAptPinAmEchtenGPGAdapter"},
		{"SSH_Allnetzsperre_entfernt", "variables.tf", `!contains(var.ssh_allowed_cidr, "0.0.0.0/0") && !contains(var.ssh_allowed_cidr, "::/0")`, "true", "TestSSHAllnetzeMitEchtemHCLAusdruck"},
		{"Checkout_Pin_entfernt", "../.github/workflows/secret-scan.yml", "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5", "actions/checkout@v4", "TestCheckoutMitCommitPin"},
		{"Konfig_Dateipruefung_entfernt", "cloud-init.yaml.tftpl", `[ -f "$pruef/$datei" ] || fail`, `true || fail`, "TestKonfigMitEchtemGit"},
	} {
		t.Run(m.name, func(t *testing.T) {
			root := t.TempDir()
			dir := filepath.Join(root, "hetzner")
			os.MkdirAll(dir, 0755)
			for _, name := range []string{"cloud-init.yaml.tftpl", "variables.tf", "../.github/workflows/secret-scan.yml"} {
				b, err := os.ReadFile(name)
				if err != nil {
					t.Fatal(err)
				}
				if name == m.file {
					if !strings.Contains(string(b), m.old) {
						t.Fatalf("Mutationsziel fehlt: %s", m.old)
					}
					b = []byte(strings.ReplaceAll(string(b), m.old, m.replacement))
				}
				p := filepath.Join(dir, name)
				os.MkdirAll(filepath.Dir(p), 0755)
				os.WriteFile(p, b, 0600)
			}
			cmd := exec.Command(os.Args[0], "-test.v", "-test.run=^"+m.test+"$")
			cmd.Dir = dir
			out, err := cmd.CombinedOutput()
			if err == nil || !strings.Contains(string(out), "--- FAIL: "+m.test) {
				t.Fatalf("Mutant nicht rot: %v %s", err, out)
			}
			t.Logf("Rot belegt: %s\n%s", m.test, out)
		})
	}
}
