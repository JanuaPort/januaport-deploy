// Package cloudinittest enthaelt ausschliesslich gemeinsame Testadapter.
package cloudinittest

import (
	"encoding/pem"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func command(t *testing.T, name string, args ...string) string {
	t.Helper()
	out, err := exec.Command(name, args...).CombinedOutput()
	if err != nil {
		t.Fatalf("%s %v: %v\n%s", name, args, err, out)
	}
	return string(out)
}

// AptPin prueft den gerenderten Helfer und den runcmd-Aufruf mit echten Adaptern.
func AptPin(t *testing.T, content string, commands []string) {
	t.Helper()
	helper := filepath.Join(t.TempDir(), "apt-schluessel.sh")
	if err := os.WriteFile(helper, []byte(content), 0700); err != nil {
		t.Fatal(err)
	}
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
	for _, line := range commands {
		if strings.Contains(line, "/opt/jnpt/apt-schluessel.sh ") {
			boot = line
			break
		}
	}
	if !strings.Contains(boot, "9DC858229FC7DD38854AE2D88D81803C0EBFCD88") || !strings.Contains(boot, "&&") {
		t.Fatal("Docker-Pin/bedingter Quelleintrag fehlt")
	}
	for _, tc := range []struct{ name, data string }{
		{"fremder_Download", key}, {"ungueltiger_Download", "keine Schluesseldaten"}, {"mehrere_Hauptschluessel", multiple},
	} {
		t.Run("Quelleintrag_"+tc.name, func(t *testing.T) {
			keyPath, sourcePath := filepath.Join(t.TempDir(), "docker.asc"), filepath.Join(t.TempDir(), "docker.list")
			line := strings.NewReplacer("/opt/jnpt/apt-schluessel.sh", helper, "https://download.docker.com/linux/ubuntu/gpg", srv.URL, "/etc/apt/keyrings/docker.asc", keyPath, "/etc/apt/sources.list.d/docker.list", sourcePath).Replace(boot)
			body = tc.data
			if out, err := exec.Command("sh", "-c", line).CombinedOutput(); err == nil {
				t.Fatalf("unvertrauter APT-Download akzeptiert: %s", out)
			}
			for _, path := range []string{keyPath, sourcePath} {
				if _, err := os.Stat(path); !os.IsNotExist(err) {
					t.Fatalf("Vertrauensdatei trotz Abweisung: %s", path)
				}
			}
		})
	}
}
