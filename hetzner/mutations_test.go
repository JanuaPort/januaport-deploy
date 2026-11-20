package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// Verändert ausschließlich Wegwerfkopien; jeder Kindprozess führt die echten
// Render-/Shell-/Paketfiltertests aus. Die Originaldateien bleiben unverändert.
func TestSicherheitsMutationen(t *testing.T) {
	adapterTests(t)
	if os.Getenv("JNPT_MUTATIONS") != "1" {
		t.Skip("Mutationslauf explizit mit JNPT_MUTATIONS=1")
	}
	type mutation struct{ name, file, old, replacement, test string }
	var mutations []mutation
	for _, name := range []string{"master_key", "tailscale_authkey", "git_token", "registry_token"} {
		mutations = append(mutations, mutation{"user_data_" + name, "cloud-init.yaml.tftpl", "write_files:\n", "write_files:\n  - path: /tmp/kanarie\n    content: ${" + name + "}\n", "TestUserDataOhneGeheimnisse"})
	}
	for _, name := range []string{"jnpt_master_key", "tailscale_authkey", "git_token", "registry_token"} {
		mutations = append(mutations,
			mutation{"templatefile_" + name, "main.tf", "user_data = templatefile(\"${path.module}/cloud-init.yaml.tftpl\", {", "user_data = templatefile(\"${path.module}/cloud-init.yaml.tftpl\", {\n    legacy = var." + name, "TestUserDataOhneGeheimnisse"},
			mutation{"altvariable_" + name, "variables.tf", "var." + name + " == \"\"", "true", "TestAltvariablenValidierungenMitEchtenHCLAusdruecken"})
	}
	for _, line := range []string{"After=docker.service", "Requires=docker.service", "PartOf=docker.service", "RemainAfterExit=yes", "WantedBy=multi-user.target docker.service"} {
		mutations = append(mutations, mutation{"unit_" + line, "cloud-init.yaml.tftpl", line, "# entfernt", "TestMetadatenUnitUndStartreihenfolge"})
	}
	mutations = append(mutations,
		mutation{"dateiweg_argv_leck", "README.md", "cat > /etc/jnpt-bootstrap/jnpt_master_key.new", "v=$(cat); sh -c : \"$v\"; printf \"%s\\n\" \"$v\" > /etc/jnpt-bootstrap/jnpt_master_key.new", "TestDokumentierterDateiwegOhneGeheimnisargumente"},
		mutation{"git_argv_leck", "cloud-init.yaml.tftpl", "*) cat /etc/jnpt-bootstrap/git_token ;;", "*) cat /etc/jnpt-bootstrap/git_token; sh -c : \"$(cat /etc/jnpt-bootstrap/git_token)\" ;;", "TestGitAskpassOhneGeheimnisargumente"},
		mutation{"metadaten_DROP_entfernt", "cloud-init.yaml.tftpl", "iptables -w -I DOCKER-USER 1 -d 169.254.0.0/16 -j DROP", ":", "TestMetadatenSperreAmEchtenNetz"},
		mutation{"metadaten_DROP_hinter_ACCEPT", "cloud-init.yaml.tftpl", "-I DOCKER-USER 1 -d", "-A DOCKER-USER -d", "TestMetadatenSperreAmEchtenNetz"},
		mutation{"metadaten_nur_eine_IP", "cloud-init.yaml.tftpl", "169.254.0.0/16", "169.254.169.254/32", "TestMetadatenSperreAmEchtenNetz"},
		mutation{"guard_beim_boot_entfernt", "cloud-init.yaml.tftpl", "systemctl enable --now jnpt-metadata-guard.service", "true", "TestMetadatenUnitUndStartreihenfolge"},
		mutation{"guard_vor_start_entfernt", "cloud-init.yaml.tftpl", "systemctl restart jnpt-metadata-guard.service", "true", "TestMetadatenUnitUndStartreihenfolge"},
		mutation{"automatischer_start", "cloud-init.yaml.tftpl", "runcmd:\n", "runcmd:\n  - docker compose up -d\n", "TestMetadatenUnitUndStartreihenfolge"},
		mutation{"dateimodus", "cloud-init.yaml.tftpl", "stat -L -c '%u:%g:%a' \"$path\")\" = '0:0:600'", "stat -L -c '%u:%g' \"$path\")\" = '0:0'", "TestStartWeistFehlendeUndUnsichereDateienAb"},
		mutation{"dateieigentuemer", "cloud-init.yaml.tftpl", "stat -L -c '%u:%g:%a' \"$path\")\" = '0:0:600'", "stat -L -c '%a' \"$path\")\" = '600'", "TestStartWeistFehlendeUndUnsichereDateienAb"},
		mutation{"symlink", "cloud-init.yaml.tftpl", "[ ! -L \"$path\" ] && ", "", "TestStartWeistFehlendeUndUnsichereDateienAb"},
		mutation{"leer_mehrzeilig", "cloud-init.yaml.tftpl", "LC_ALL=C awk 'NR != 1 || length($0) == 0 {bad=1} END {exit (NR != 1 || bad)}' \"$path\"", "true", "TestStartWeistFehlendeUndUnsichereDateienAb"},
		mutation{"master_key_format", "cloud-init.yaml.tftpl", "LC_ALL=C grep -Eq '^[0-9a-fA-F]{64}$' /etc/jnpt-bootstrap/jnpt_master_key", "true", "TestStartWeistFehlendeUndUnsichereDateienAb"},
		mutation{"root_start", "cloud-init.yaml.tftpl", "[ \"$(id -u)\" = 0 ]", "true", "TestStartWeistFehlendeUndUnsichereDateienAb"},
		mutation{"parallelstart", "cloud-init.yaml.tftpl", "flock -n 9", "true", "TestStartWeistFehlendeUndUnsichereDateienAb"},
	)
	for _, m := range mutations {
		t.Run(m.name, func(t *testing.T) {
			dir := t.TempDir()
			for _, name := range []string{"cloud-init.yaml.tftpl", "main.tf", "variables.tf", "README.md"} {
				src, err := os.ReadFile(name)
				if err != nil {
					t.Fatal(err)
				}
				if name == m.file {
					if !strings.Contains(string(src), m.old) {
						t.Fatalf("Mutationsziel fehlt: %q", m.old)
					}
					src = []byte(strings.ReplaceAll(string(src), m.old, m.replacement))
				}
				if err := os.WriteFile(filepath.Join(dir, name), src, 0600); err != nil {
					t.Fatal(err)
				}
			}
			// Eigener Netz-Namespace pro Kind, kein Einfluss auf andere Container.
			cmd := exec.Command("unshare", "-n", os.Args[0], "-test.v", "-test.run=^"+m.test+"$")
			cmd.Dir = dir
			out, err := cmd.CombinedOutput()
			if err == nil {
				t.Fatalf("Mutation überlebt: %s\n%s", m.name, out)
			}
			if !strings.Contains(string(out), "--- FAIL: "+m.test) {
				t.Fatalf("Kein belegter Testfehler: %v\n%s", err, out)
			}
			if m.name == "dateiweg_argv_leck" && !strings.Contains(string(out), "Geheimnis in execve-Argumenten") {
				t.Fatalf("Argumentleck nicht nachgewiesen: %s", out)
			}
			if m.name == "git_argv_leck" && !strings.Contains(string(out), "Git-Token steht in execve-Argumenten") {
				t.Fatalf("Git-Argumentleck nicht nachgewiesen: %s", out)
			}
			t.Log("Rot belegt: " + m.test)
		})
	}
}
