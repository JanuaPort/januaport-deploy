package cloudinit_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/JanuaPort/januaport-deploy/internal/cloudinittest"
	"gopkg.in/yaml.v3"
)

func TestDockerAptPinGerendert(t *testing.T) {
	path := "cloud-init.yaml"
	if p := os.Getenv("JNPT_TEST_TEMPLATE"); p != "" {
		path = p
	}
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var cfg struct {
		Files []struct{ Path, Content, Permissions, Owner string } `yaml:"write_files"`
		Run   []string                                             `yaml:"runcmd"`
	}
	if err := yaml.Unmarshal(b, &cfg); err != nil {
		t.Fatal(err)
	}
	for _, f := range cfg.Files {
		if f.Path != "/opt/jnpt/apt-schluessel.sh" {
			continue
		}
		if f.Permissions != "0700" || f.Owner != "root:root" {
			t.Fatal("APT-Pruefhelfer nicht root:root/0700")
		}
		cloudinittest.AptPin(t, f.Content, cfg.Run)
		return
	}
	t.Fatal("APT-Pruefhelfer fehlt in gerenderter Vorlage")
}

func TestDockerAptPinMutation(t *testing.T) {
	b, err := os.ReadFile("cloud-init.yaml")
	if err != nil {
		t.Fatal(err)
	}
	old := `if [ "$ist" != "$soll" ]; then`
	if !strings.Contains(string(b), old) {
		t.Fatal("APT-Mutationsziel fehlt")
	}
	path := filepath.Join(t.TempDir(), "mutant.yaml")
	if err := os.WriteFile(path, []byte(strings.ReplaceAll(string(b), old, "if false; then")), 0600); err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command(os.Args[0], "-test.v", "-test.run=^TestDockerAptPinGerendert$")
	cmd.Env = append(os.Environ(), "JNPT_TEST_TEMPLATE="+path)
	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), "APT-Abweisung falsch") || !strings.Contains(string(out), "unvertrauter APT-Download akzeptiert") {
		t.Fatalf("Pin-Mutant nicht am echten Adapter rot: %v %s", err, out)
	}
	t.Logf("Pin entfernt -> rot, Original unveraendert:\n%s", out)
}
