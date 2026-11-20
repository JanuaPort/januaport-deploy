package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/hashicorp/hcl/v2"
	"github.com/hashicorp/hcl/v2/hclsyntax"
	"github.com/zclconf/go-cty/cty"
	"gopkg.in/yaml.v3"
)

type cloudConfig struct {
	Files []struct {
		Path        string `yaml:"path"`
		Content     string `yaml:"content"`
		Permissions string `yaml:"permissions"`
		Owner       string `yaml:"owner"`
	} `yaml:"write_files"`
	Run []string `yaml:"runcmd"`
}

func render(t *testing.T, extra map[string]cty.Value) (string, cloudConfig) {
	t.Helper()
	vars := map[string]cty.Value{}
	for k, v := range map[string]string{
		"domain": "mcp.example.com", "acme_email": "admin@example.com", "ts_hostname": "jnpt",
		"image_ref": "ghcr.io/januaport/januaport:0.59.0", "git_repo": "https://github.com/JanuaPort/januaport.git", "git_ref": "main",
		"update_manifest_url": "", "update_public_keys": "", "updater_image_repo": "ghcr.io/januaport/januaport",
		"volume_device": "/dev/disk/by-id/scsi-0HC_Volume_123", "master_key": "", "tailscale_authkey": "", "git_token": "", "registry_token": "",
	} {
		vars[k] = cty.StringVal(v)
	}
	for k, v := range extra {
		vars[k] = v
	}
	src, err := os.ReadFile("cloud-init.yaml.tftpl")
	if err != nil {
		t.Fatal(err)
	}
	expr, diags := hclsyntax.ParseTemplate(src, "cloud-init.yaml.tftpl", hcl.InitialPos)
	if diags.HasErrors() {
		t.Fatal(diags.Error())
	}
	value, diags := expr.Value(&hcl.EvalContext{Variables: vars})
	if diags.HasErrors() {
		t.Fatal(diags.Error())
	}
	result := value.AsString()
	var cfg cloudConfig
	if err := yaml.Unmarshal([]byte(result), &cfg); err != nil {
		t.Fatal(err)
	}
	return result, cfg
}

func fileContent(t *testing.T, cfg cloudConfig, path string) string {
	t.Helper()
	for _, f := range cfg.Files {
		if f.Path == path {
			return f.Content
		}
	}
	t.Fatalf("gerenderte Datei fehlt: %s", path)
	return ""
}

func script(t *testing.T, cfg cloudConfig, name string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), filepath.Base(name))
	if err := os.WriteFile(path, []byte(fileContent(t, cfg, name)), 0700); err != nil {
		t.Fatal(err)
	}
	return path
}

func command(t *testing.T, name string, args ...string) string {
	t.Helper()
	out, err := exec.Command(name, args...).CombinedOutput()
	if err != nil {
		t.Fatalf("%s %v: %v\n%s", name, args, err, out)
	}
	return string(out)
}

func TestUserDataOhneGeheimnisse(t *testing.T) {
	canaries := map[string]cty.Value{
		"master_key":        cty.StringVal(strings.Repeat("a1497bcd", 8)),
		"tailscale_authkey": cty.StringVal("KANARIE_1497_TAILSCALE"),
		"git_token":         cty.StringVal("KANARIE_1497_GIT"),
		"registry_token":    cty.StringVal("KANARIE_1497_REGISTRY"),
	}
	rendered, _ := render(t, canaries)
	for name, value := range canaries {
		if strings.Contains(rendered, value.AsString()) {
			t.Errorf("Geheimnis %s steht in user_data", name)
		}
	}
	// Auch der Kompositionsweg muss geschlossen sein, nicht nur die Vorlage.
	src, err := os.ReadFile("main.tf")
	if err != nil {
		t.Fatal(err)
	}
	f, diags := hclsyntax.ParseConfig(src, "main.tf", hcl.InitialPos)
	if diags.HasErrors() {
		t.Fatal(diags.Error())
	}
	for _, block := range f.Body.(*hclsyntax.Body).Blocks {
		if block.Type != "resource" {
			continue
		}
		attr := block.Body.Attributes["user_data"]
		if attr == nil {
			continue
		}
		for _, traversal := range attr.Expr.Variables() {
			for _, step := range traversal {
				if a, ok := step.(hcl.TraverseAttr); ok {
					for _, name := range []string{"jnpt_master_key", "tailscale_authkey", "git_token", "registry_token"} {
						if a.Name == name {
							t.Errorf("user_data verwendet var.%s", name)
						}
					}
				}
			}
		}
	}
}

func TestMetadatenUnitUndStartreihenfolge(t *testing.T) {
	_, cfg := render(t, nil)
	unit := fileContent(t, cfg, "/etc/systemd/system/jnpt-metadata-guard.service")
	for _, line := range []string{"After=docker.service", "Requires=docker.service", "PartOf=docker.service", "Type=oneshot", "RemainAfterExit=yes", "ExecStart=/usr/local/sbin/jnpt-metadata-guard.sh", "WantedBy=multi-user.target docker.service"} {
		if !strings.Contains(unit, line) {
			t.Errorf("Unit fehlt %s", line)
		}
	}
	guard := fileContent(t, cfg, "/usr/local/sbin/jnpt-metadata-guard.sh")
	if !strings.Contains(guard, "-I DOCKER-USER 1 -d 169.254.0.0/16 -j DROP") {
		t.Error("Link-Local-DROP muss an Position 1 stehen")
	}
	boot := strings.Join(cfg.Run, "\n")
	if !strings.Contains(boot, "systemctl enable --now jnpt-metadata-guard.service") {
		t.Error("Guard wird nicht aktiviert")
	}
	if strings.Contains(boot, "compose") || strings.Contains(boot, "git clone") {
		t.Error("cloud-init darf den Stack nicht vor der manuellen Ablage starten/klonen")
	}
	start := fileContent(t, cfg, "/usr/local/sbin/jnpt-start")
	guardAt, upAt := strings.Index(start, "systemctl restart jnpt-metadata-guard.service"), strings.Index(start, " up -d")
	if guardAt < 0 || upAt < guardAt {
		t.Error("Guard muss vor dem Stack-Start laufen")
	}
}

func adapterTests(t *testing.T) {
	t.Helper()
	if os.Getenv("JNPT_ADAPTER_TESTS") != "1" {
		t.Skip("echte Adapter: hetzner/test.Dockerfile, isolierter privilegierter Testcontainer")
	}
}
