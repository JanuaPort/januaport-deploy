package hetzner_test

import (
	"encoding/pem"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"

	"github.com/hashicorp/hcl/v2"
	"github.com/hashicorp/hcl/v2/ext/tryfunc"
	"github.com/hashicorp/hcl/v2/hclsyntax"
	"github.com/zclconf/go-cty/cty"
	"github.com/zclconf/go-cty/cty/function"
	"github.com/zclconf/go-cty/cty/function/stdlib"
)

func TestAptPinAmEchtenGPGAdapter(t *testing.T) {
	_, cfg := render(t, nil)
	helper := script(t, cfg, "/opt/jnpt/apt-schluessel.sh")
	dir := t.TempDir()
	command(t, "gpg", "--homedir", dir, "--batch", "--passphrase", "", "--quick-gen-key", "Audit <apt@example.org>", "ed25519", "sign", "0")
	key := command(t, "gpg", "--homedir", dir, "--armor", "--export")
	colons := command(t, "gpg", "--homedir", dir, "--with-colons", "--list-keys")
	var fingerprint string
	for _, line := range strings.Split(colons, "\n") {
		if strings.HasPrefix(line, "fpr:") {
			fingerprint = strings.Split(line, ":")[9]
			break
		}
	}
	if fingerprint == "" {
		t.Fatal("kein Test-Fingerabdruck")
	}
	command(t, "gpg", "--homedir", dir, "--batch", "--passphrase", "", "--quick-gen-key", "Zweiter Audit <apt2@example.org>", "ed25519", "sign", "0")
	multiple := command(t, "gpg", "--homedir", dir, "--armor", "--export")
	body := key
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(body)) }))
	defer srv.Close()
	ca := filepath.Join(t.TempDir(), "ca.pem")
	os.WriteFile(ca, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: srv.Certificate().Raw}), 0600)
	t.Setenv("CURL_CA_BUNDLE", ca)
	for _, tc := range []struct {
		name, data, pin string
		accepted        bool
	}{
		{"passend", key, fingerprint, true},
		{"fremder_Schluessel", key, "9DC858229FC7DD38854AE2D88D81803C0EBFCD88", false},
		{"kaputt", "keine Schluesseldaten", fingerprint, false},
		{"zwei_Hauptschluessel", multiple, fingerprint, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			body = tc.data
			target := filepath.Join(t.TempDir(), "docker.asc")
			out, err := exec.Command("sh", helper, srv.URL, tc.pin, target).CombinedOutput()
			if (err == nil) != tc.accepted {
				t.Fatalf("APT-Abweisung falsch: %v %s", err, out)
			}
			_, statErr := os.Stat(target)
			if (statErr == nil) != tc.accepted {
				t.Fatal("unvertrauter Schluessel installiert oder gueltiger fehlt")
			}
		})
	}
	// Echter runcmd-Aufruf: falscher Download muss auch den Quelleintrag verhindern.
	var boot string
	for _, line := range cfg.Run {
		if strings.Contains(line, "/opt/jnpt/apt-schluessel.sh ") {
			boot = line
			break
		}
	}
	if !strings.Contains(boot, "9DC858229FC7DD38854AE2D88D81803C0EBFCD88") || !strings.Contains(boot, "&&") {
		t.Fatal("Docker-Pin/bedingter Quelleintrag fehlt")
	}
	keyPath, sourcePath := filepath.Join(t.TempDir(), "docker.asc"), filepath.Join(t.TempDir(), "docker.list")
	boot = strings.NewReplacer("/opt/jnpt/apt-schluessel.sh", helper, "https://download.docker.com/linux/ubuntu/gpg", srv.URL, "/etc/apt/keyrings/docker.asc", keyPath, "/etc/apt/sources.list.d/docker.list", sourcePath).Replace(boot)
	body = key
	if out, err := exec.Command("sh", "-c", boot).CombinedOutput(); err == nil {
		t.Fatalf("fremder APT-Schluessel akzeptiert: %s", out)
	}
	for _, path := range []string{keyPath, sourcePath} {
		if _, err := os.Stat(path); !os.IsNotExist(err) {
			t.Fatalf("Vertrauensdatei trotz Abweisung: %s", path)
		}
	}
}

func TestKonfigMitEchtemGit(t *testing.T) {
	_, cfg := render(t, nil)
	helper := script(t, cfg, "/opt/jnpt/config-holen.sh")
	repo := t.TempDir()
	git := func(args ...string) string {
		return strings.TrimSpace(command(t, "git", append([]string{"-C", repo}, args...)...))
	}
	git("init", "-b", "main")
	for _, name := range []string{"docker/docker-compose.prod.yml", "docker/Caddyfile", "docker/tailscale-serve.json", "deploy/updater/jnpt-updater.sh", "deploy/updater/jnpt-updater.service", "deploy/updater/jnpt-updater.timer"} {
		p := filepath.Join(repo, name)
		os.MkdirAll(filepath.Dir(p), 0755)
		os.WriteFile(p, []byte("Audit\n"), 0644)
	}
	git("add", ".")
	git("-c", "user.name=Audit", "-c", "user.email=audit@example.org", "commit", "-m", "Teststand")
	sha := git("rev-parse", "HEAD")
	git("tag", "v0.87.1")
	for _, ref := range []string{"main", "v0.87.1", sha} {
		dest := filepath.Join(t.TempDir(), "repo")
		command(t, "sh", helper, repo, ref, dest)
		if got := strings.TrimSpace(command(t, "git", "-C", dest, "rev-parse", "HEAD")); got != sha {
			t.Fatalf("falscher Stand: %s", got)
		}
		command(t, "sh", helper, repo, ref, dest) // Wiederholung
	}
	for _, missing := range []string{"docker/docker-compose.prod.yml", "docker/Caddyfile", "docker/tailscale-serve.json", "deploy/updater/jnpt-updater.sh", "deploy/updater/jnpt-updater.service", "deploy/updater/jnpt-updater.timer"} {
		t.Run("bestehender_Klon_ohne_"+missing, func(t *testing.T) {
			dest := filepath.Join(t.TempDir(), "repo")
			command(t, "sh", helper, repo, "v0.87.1", dest)
			if err := os.Remove(filepath.Join(dest, missing)); err != nil {
				t.Fatal(err)
			}
			if out, err := exec.Command("sh", helper, repo, "v0.87.1", dest).CombinedOutput(); err == nil || !strings.Contains(string(out), "Konfig-Datei fehlt: "+missing) {
				t.Fatalf("fehlende Konfig-Datei nicht abgewiesen: %v %s", err, out)
			}
		})
	}
	for _, tc := range []struct{ name, repo, ref string }{
		{"privat_ohne_Token", "https://github.com/JanuaPort/januaport.git", "v0.87.1"},
		{"Ref_fehlt", repo, "nicht-vorhanden"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			dest := filepath.Join(t.TempDir(), "repo")
			cmd := exec.Command("sh", helper, tc.repo, tc.ref, dest)
			// Falls die Tokensperre mutiert wird, bleibt auch der verbotene
			// Default-Klon lokal: echtes Git-URL-Rewriting, kein Netzwerk/Mock.
			cmd.Env = append(os.Environ(), "GIT_CONFIG_COUNT=1", "GIT_CONFIG_KEY_0=url."+repo+".insteadOf", "GIT_CONFIG_VALUE_0=https://github.com/JanuaPort/januaport.git")
			out, err := cmd.CombinedOutput()
			if err == nil || !strings.Contains(string(out), "Keine Anlage gestartet") {
				t.Fatalf("stiller/erfolgreicher Fehler: %v %s", err, out)
			}
			if _, err := os.Stat(dest); !os.IsNotExist(err) {
				t.Fatal("unvollstaendiger Klon bleibt stehen")
			}
		})
	}
	// Ein gueltiger Git-Stand ohne die benötigten Stack-Dateien muss scheitern.
	git("rm", "docker/docker-compose.prod.yml")
	git("-c", "user.name=Audit", "-c", "user.email=audit@example.org", "commit", "-m", "Compose fehlt")
	dest := filepath.Join(t.TempDir(), "repo")
	if out, err := exec.Command("sh", helper, repo, "main", dest).CombinedOutput(); err == nil || !strings.Contains(string(out), "Keine Anlage gestartet") {
		t.Fatalf("fehlende Compose nicht abgewiesen: %v %s", err, out)
	}
}

func TestPluginRechteAmEchtenTmpfilesAdapter(t *testing.T) {
	adapterTests(t)
	_, cfg := render(t, nil)
	root := t.TempDir()
	os.Chmod(root, 0755)
	os.Chmod(filepath.Dir(root), 0755)
	etc := filepath.Join(root, "etc")
	os.MkdirAll(filepath.Join(etc, "tmpfiles.d"), 0755)
	os.WriteFile(filepath.Join(etc, "passwd"), []byte("root:x:0:0:root:/root:/bin/sh\n"), 0644)
	os.WriteFile(filepath.Join(etc, "group"), []byte("root:x:0:\n"), 0644)
	os.WriteFile(filepath.Join(etc, "tmpfiles.d/jnpt-plugins.conf"), []byte(fileContent(t, cfg, "/etc/tmpfiles.d/jnpt-plugins.conf")), 0644)
	command(t, "systemd-tmpfiles", "--root="+root, "--create", filepath.Join(etc, "tmpfiles.d/jnpt-plugins.conf"))
	parent := filepath.Join(root, "run/jnpt/plugins")
	command(t, "setpriv", "--reuid=65532", "--regid=65532", "--clear-groups", "touch", filepath.Join(parent, "tunnel-admin/runtime-test"))
	if out, err := exec.Command("setpriv", "--reuid=65532", "--regid=65532", "--clear-groups", "mkdir", filepath.Join(parent, "unerlaubt")).CombinedOutput(); err == nil || !strings.Contains(string(out), "Permission denied") {
		t.Fatalf("Kern kann fremde Plugin-Stelle anlegen: %v %s", err, out)
	}
}

func TestStartMeldetFehlerUndBootstatus(t *testing.T) {
	_, cfg := render(t, nil)
	start := fileContent(t, cfg, "/usr/local/sbin/jnpt-start")
	if !strings.Contains(start, "/opt/jnpt/config-holen.sh") || strings.Contains(start, "git -c credential.helper= clone") {
		t.Fatal("Start nutzt geprueften Konfig-Adapter nicht")
	}
	if !strings.Contains(strings.Join(cfg.Run, "\n"), "Keine Anlage gestartet") {
		t.Fatal("MOTD verschweigt fehlenden Stack")
	}
	cmd := exec.Command("sh", script(t, cfg, "/usr/local/sbin/jnpt-start"))
	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), "Keine Anlage gestartet") {
		t.Fatalf("Startfehler nicht laut: %v %s", err, out)
	}
}

func TestPluginVerzeichnisUndFeed(t *testing.T) {
	_, cfg := render(t, map[string]cty.Value{"update_plugins_url": cty.StringVal("https://updates.example.org/plugins.json")})
	rules := fileContent(t, cfg, "/etc/tmpfiles.d/jnpt-plugins.conf")
	if rules != "d /run/jnpt/plugins 0755 root root -\nd /run/jnpt/plugins/tunnel-admin 0750 65532 65532 -\n" {
		t.Fatalf("Plugin-Rechte weichen ab: %s", rules)
	}
	if !strings.Contains(fileContent(t, cfg, "/opt/jnpt/staging/.env"), "JNPT_UPDATE_PLUGINS_URL=https://updates.example.org/plugins.json\n") {
		t.Fatal("Plugin-Feed fehlt")
	}
	for _, content := range []string{strings.Join(cfg.Run, "\n"), fileContent(t, cfg, "/usr/local/sbin/jnpt-start")} {
		if !strings.Contains(content, "systemd-tmpfiles --create /etc/tmpfiles.d/jnpt-plugins.conf") {
			t.Fatal("Plugin-Regel wird nicht angewendet")
		}
	}
	main, _ := os.ReadFile("main.tf")
	if !regexp.MustCompile(`update_plugins_url\s*=\s*var\.update_plugins_url`).Match(main) {
		t.Fatal("Feed-Komposition fehlt")
	}
}

func TestSSHAllnetzeMitEchtemHCLAusdruck(t *testing.T) {
	src, err := os.ReadFile("variables.tf")
	if err != nil {
		t.Fatal(err)
	}
	f, diags := hclsyntax.ParseConfig(src, "variables.tf", hcl.InitialPos)
	if diags.HasErrors() {
		t.Fatal(diags.Error())
	}
	for _, b := range f.Body.(*hclsyntax.Body).Blocks {
		if b.Type != "variable" || b.Labels[0] != "ssh_allowed_cidr" {
			continue
		}
		for _, v := range b.Body.Blocks {
			if v.Type != "validation" {
				continue
			}
			for _, tc := range []struct {
				values   []string
				accepted bool
			}{
				{nil, true}, {[]string{"203.0.113.4/32", "2001:db8::/64"}, true},
				{[]string{"0.0.0.0/0"}, false}, {[]string{"::/0"}, false}, {[]string{"203.0.113.4/32", "::/0"}, false},
				{[]string{"10.0.0.0/7"}, false}, {[]string{"2000::/15"}, false},
				{[]string{"10.0.0.0/8", "2001::/16"}, true},
				{[]string{"203.0.113.4/32", "2000::/15"}, false},
				{[]string{"10.0.0.0/7", "2001:db8::/64"}, false},
				{[]string{"203.0.113.4/32", "2001:db8::1/128"}, true},
				{[]string{"203.0.113.4"}, false}, {[]string{"2001:db8::/ungueltig"}, false},
			} {
				values := []cty.Value{}
				for _, s := range tc.values {
					values = append(values, cty.StringVal(s))
				}
				list := cty.ListValEmpty(cty.String)
				if len(values) > 0 {
					list = cty.ListVal(values)
				}
				ctx := &hcl.EvalContext{Variables: map[string]cty.Value{"var": cty.ObjectVal(map[string]cty.Value{"ssh_allowed_cidr": list})}, Functions: map[string]function.Function{
					"contains": stdlib.ContainsFunc, "length": stdlib.LengthFunc, "split": stdlib.SplitFunc,
					"tonumber": stdlib.MakeToFunc(cty.Number), "regexall": stdlib.RegexAllFunc, "try": tryfunc.TryFunc,
				}}
				got, d := v.Body.Attributes["condition"].Expr.Value(ctx)
				if d.HasErrors() || got.Type() != cty.Bool || got.True() != tc.accepted {
					t.Errorf("CIDR %v: %s %s", tc.values, got.GoString(), d.Error())
				}
			}
			return
		}
	}
	t.Fatal("SSH-Allnetzsperre fehlt")
}
