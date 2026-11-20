package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
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
		"domain": "mcp.example.com", "acme_email": "admin@example.org", "ts_hostname": "jnpt",
		"image_ref": "ghcr.io/januaport/januaport:0.87.1", "git_repo": "https://github.com/JanuaPort/januaport.git", "git_ref": "v0.87.1",
		"update_manifest_url": "", "update_plugins_url": "", "update_public_keys": "", "updater_image_repo": "ghcr.io/januaport/januaport",
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
	t.Run("ShellSyntax", func(t *testing.T) {
		if runtime.GOOS == "windows" {
			t.Skip("Linux-Shell-Syntaxpruefung; Unit- und Startreihenfolge bleiben unter Windows aktiv")
		}
		for _, f := range cfg.Files {
			if strings.HasPrefix(f.Content, "#!/bin/sh\n") {
				cmd := exec.Command("sh", "-n")
				cmd.Stdin = strings.NewReader(f.Content)
				if out, err := cmd.CombinedOutput(); err != nil {
					t.Fatalf("Shell-Syntax %s: %v %s", f.Path, err, out)
				}
			}
		}
	})
	unit := fileContent(t, cfg, "/etc/systemd/system/jnpt-metadata-guard.service")
	for _, line := range []string{"After=docker.service", "Requires=docker.service", "PartOf=docker.service", "Type=oneshot", "RemainAfterExit=yes", "ExecStart=/usr/local/sbin/jnpt-metadata-guard.sh", "WantedBy=multi-user.target docker.service"} {
		if !strings.Contains(unit, line) {
			t.Errorf("Unit fehlt %s", line)
		}
	}
	guard := fileContent(t, cfg, "/usr/local/sbin/jnpt-metadata-guard.sh")
	readme, err := os.ReadFile("README.md")
	if err != nil {
		t.Fatal(err)
	}
	doc := strings.ReplaceAll(string(readme), "\r\n", "\n")
	for lang, content := range map[string]string{"sh": guard, "ini": unit} {
		if !strings.Contains(doc, "```"+lang+"\n"+strings.TrimSpace(content)+"\n```") {
			t.Errorf("Upgrade-Anleitung weicht von gerendertem %s ab", lang)
		}
	}
	if !strings.Contains(guard, "-I DOCKER-USER 1 -d 169.254.0.0/16 -j DROP") {
		t.Error("Link-Local-DROP muss an Position 1 stehen")
	}
	boot := strings.Join(cfg.Run, "\n")
	if !strings.Contains(boot, "systemctl enable --now jnpt-metadata-guard.service") {
		t.Error("Guard wird nicht aktiviert")
	}
	if strings.Contains(boot, "docker compose ") || strings.Contains(boot, "git clone ") {
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
	if runtime.GOOS == "windows" {
		t.Skip("Linux-Adapter mit systemd-tmpfiles, strace und Netzwerk-Namespaces erforderlich; isolierten Testcontainer verwenden")
	}
	if os.Getenv("JNPT_ADAPTER_TESTS") != "1" {
		t.Skip("echte Adapter: hetzner/test.Dockerfile, isolierter privilegierter Testcontainer")
	}
}

func TestAltvariablenValidierungenMitEchtenHCLAusdruecken(t *testing.T) {
	src, err := os.ReadFile("variables.tf")
	if err != nil {
		t.Fatal(err)
	}
	f, diags := hclsyntax.ParseConfig(src, "variables.tf", hcl.InitialPos)
	if diags.HasErrors() {
		t.Fatal(diags.Error())
	}
	for _, name := range []string{"jnpt_master_key", "tailscale_authkey", "git_token", "registry_token"} {
		t.Run(name, func(t *testing.T) {
			found := false
			for _, block := range f.Body.(*hclsyntax.Body).Blocks {
				if block.Type != "variable" || block.Labels[0] != name {
					continue
				}
				for _, validation := range block.Body.Blocks {
					if validation.Type != "validation" {
						continue
					}
					found = true
					for _, value := range []string{"", "KANARIE_1497", strings.Repeat("a", 64)} {
						ctx := &hcl.EvalContext{Variables: map[string]cty.Value{"var": cty.ObjectVal(map[string]cty.Value{name: cty.StringVal(value)})}}
						got, diags := validation.Body.Attributes["condition"].Expr.Value(ctx)
						if diags.HasErrors() || got.Type() != cty.Bool || got.True() != (value == "") {
							t.Fatalf("Altwert nicht abgewiesen: %s / %s", got.GoString(), diags.Error())
						}
					}
					message, diags := validation.Body.Attributes["error_message"].Expr.Value(nil)
					if diags.HasErrors() || !strings.Contains(message.AsString(), name) || !strings.Contains(message.AsString(), "#1497") {
						t.Fatal("Migrationsmeldung fehlt")
					}
				}
			}
			if !found {
				t.Fatal("Migrationssperre fehlt")
			}
		})
	}
}
