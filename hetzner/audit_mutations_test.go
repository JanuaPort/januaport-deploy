package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"
)

func TestAuditMutationen(t *testing.T) {
	for _, m := range []struct{ name, file, old, replacement, test string }{
		{"APT_Pin_entfernt", "cloud-init.yaml.tftpl", `if [ "$ist" != "$soll" ]; then`, "if false; then", "TestAptPinAmEchtenGPGAdapter"},
		{"SSH_Allnetzsperre_entfernt", "variables.tf", `!contains(var.ssh_allowed_cidr, "0.0.0.0/0") && !contains(var.ssh_allowed_cidr, "::/0")`, "true", "TestSSHAllnetzeMitEchtemHCLAusdruck"},
		{"Checkout_Pin_entfernt", "../.github/workflows/secret-scan.yml", "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5", "actions/checkout@v4", "TestCheckoutMitCommitPin"},
		{"Konfig_Dateipruefung_entfernt", "cloud-init.yaml.tftpl", `[ -f "$pruef/$datei" ] || fail`, `true || fail`, "TestKonfigMitEchtemGit"},
		{"Privater_Default_ohne_Token", "cloud-init.yaml.tftpl", `[ -f /etc/jnpt-bootstrap/git_token ] || fail`, `true || fail`, "TestKonfigMitEchtemGit"},
	} {
		t.Run(m.name, func(t *testing.T) {
			if runtime.GOOS == "windows" && (m.test == "TestAptPinAmEchtenGPGAdapter" || m.test == "TestKonfigMitEchtemGit") {
				t.Skip("Mutation braucht den Linux-GPG-/Shell-Adapter ihres Zieltests")
			}
			root := t.TempDir()
			dir := filepath.Join(root, "hetzner")
			os.MkdirAll(dir, 0755)
			for _, name := range []string{"cloud-init.yaml.tftpl", "variables.tf", "../.github/workflows/secret-scan.yml"} {
				b, err := os.ReadFile(name)
				if err != nil {
					t.Fatal(err)
				}
				if name == m.file {
					if m.name == "SSH_Allnetzsperre_entfernt" {
						re := regexp.MustCompile(`(?s)(variable "ssh_allowed_cidr".*?validation \{\s*condition\s*=\s*)(.*?)(\s+error_message)`)
						if !re.Match(b) {
							t.Fatal("CIDR-Mutationsziel fehlt")
						}
						b = re.ReplaceAll(b, []byte("${1}true${3}"))
					} else {
						if !strings.Contains(string(b), m.old) {
							t.Fatalf("Mutationsziel fehlt: %s", m.old)
						}
						b = []byte(strings.ReplaceAll(string(b), m.old, m.replacement))
					}
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

func TestPluginRechteMutation(t *testing.T) {
	adapterTests(t)
	dir := t.TempDir()
	b, err := os.ReadFile("cloud-init.yaml.tftpl")
	if err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(dir, "cloud-init.yaml.tftpl"), []byte(strings.ReplaceAll(string(b), "d /run/jnpt/plugins 0755 root root -", "d /run/jnpt/plugins 0755 65532 65532 -")), 0600)
	cmd := exec.Command(os.Args[0], "-test.run=^TestPluginRechteAmEchtenTmpfilesAdapter$", "-test.v")
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), "Kern kann fremde Plugin-Stelle anlegen") {
		t.Fatalf("Plugin-Mutant nicht gezielt rot: %v %s", err, out)
	}
	t.Logf("Rot belegt: %s", out)
}
