package cloudinit_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v3"
)

func TestEnvModusUndMetadaten(t *testing.T) {
	path := "cloud-init.yaml"
	if p := os.Getenv("JNPT_TEST_TEMPLATE"); p != "" {
		path = p
	}
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var cfg struct {
		Files []struct{ Path, Content string } `yaml:"write_files"`
		Run   []string                         `yaml:"runcmd"`
	}
	if err := yaml.Unmarshal(b, &cfg); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	if err := os.Chmod(dir, 0755); err != nil {
		t.Fatal(err)
	}
	var install string
	for _, f := range cfg.Files {
		if f.Path == "/opt/jnpt/.env.example" {
			if !strings.Contains(f.Content, "JNPT_MASTER_KEY=\n") {
				t.Fatal("Geheimnis in Metadaten-Vorlage")
			}
			os.WriteFile(filepath.Join(dir, ".env.example"), []byte(f.Content), 0644)
		}
	}
	for _, line := range cfg.Run {
		if strings.Contains(line, "/opt/jnpt/.env.example /opt/jnpt/.env") {
			install = strings.ReplaceAll(line, "/opt/jnpt", dir)
		}
	}
	if install == "" {
		t.Fatal("Env-Anlage nicht gefunden")
	}
	// Vorhandene zu offene Datei muss beim Wiederholungslauf ebenfalls 0600 werden.
	target := filepath.Join(dir, ".env")
	os.WriteFile(target, []byte("KANARIE_AUDIT\n"), 0644)
	cmd := exec.Command("sh", "-c", "umask 022; "+install)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("Env-Anlage: %v %s", err, out)
	}
	info, err := os.Stat(target)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0600 {
		t.Fatalf(".env-Modus %04o statt 0600", info.Mode().Perm())
	}
	// Wirklicher Dateisystemzugriff eines unprivilegierten Kontos, kein Mock.
	if out, err := exec.Command("setpriv", "--reuid=65532", "--regid=65532", "--clear-groups", "cat", target).CombinedOutput(); err == nil || !strings.Contains(string(out), "Permission denied") {
		t.Fatalf("unprivilegiertes Lesen nicht abgewiesen: %v %s", err, out)
	}
}

func TestEnvModusMutation(t *testing.T) {
	b, err := os.ReadFile("cloud-init.yaml")
	if err != nil {
		t.Fatal(err)
	}
	old := "install -m 0600 /opt/jnpt/.env.example /opt/jnpt/.env"
	if !strings.Contains(string(b), old) {
		t.Fatal("Mutationsziel fehlt")
	}
	path := filepath.Join(t.TempDir(), "mutant.yaml")
	os.WriteFile(path, []byte(strings.ReplaceAll(string(b), old, "cp /opt/jnpt/.env.example /opt/jnpt/.env")), 0600)
	cmd := exec.Command(os.Args[0], "-test.run=^TestEnvModusUndMetadaten$", "-test.v")
	cmd.Env = append(os.Environ(), "JNPT_TEST_TEMPLATE="+path)
	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), ".env-Modus 0644 statt 0600") {
		t.Fatalf("Mutant nicht gezielt rot: %v %s", err, out)
	}
	t.Log("Rot belegt: .env-Modus 0644 statt 0600; Original unveraendert")
}
