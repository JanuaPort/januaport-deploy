package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func bootstrapDir(t *testing.T) string {
	t.Helper()
	dir := "/etc/jnpt-bootstrap"
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Fatal("Test verlangt einen frischen Container")
	}
	if err := os.Mkdir(dir, 0700); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	return dir
}

func TestDokumentierterDateiwegOhneGeheimnisargumente(t *testing.T) {
	adapterTests(t)
	dir := bootstrapDir(t)
	doc, err := os.ReadFile("README.md")
	if err != nil {
		t.Fatal(err)
	}
	const canary = "KANARIE_STDIN_1497"
	count := 0
	for _, line := range strings.Split(strings.ReplaceAll(string(doc), "\r\n", "\n"), "\n") {
		prefix := "ssh root@<server-ip> '"
		end := strings.LastIndex(line, "' < /sicher/")
		if !strings.HasPrefix(line, prefix) || end < 0 {
			continue
		}
		name := line[end+len("' < /sicher/"):]
		t.Run(name, func(t *testing.T) {
			// Exakter dokumentierter Remote-Shell-Body, lokal im Testcontainer.
			// Keine SSH-Verbindung. strace erfasst die echten execve-Argumente
			// von Shell, cat, chown, chmod und mv; der Inhalt kommt über stdin.
			trace := filepath.Join(t.TempDir(), "execve.log")
			cmd := exec.Command("strace", "-f", "-s", "4096", "-e", "trace=execve", "-o", trace, "sh", "-c", line[len(prefix):end])
			cmd.Stdin = strings.NewReader(canary + "\n")
			if out, err := cmd.CombinedOutput(); err != nil {
				t.Fatalf("Dateiablage fehlgeschlagen: %v %s", err, out)
			}
			contents, err := os.ReadFile(filepath.Join(dir, name))
			if err != nil || string(contents) != canary+"\n" {
				t.Fatal("stdin-Inhalt nicht unverändert abgelegt")
			}
			stat := command(t, "stat", "-c", "%u:%g:%a", filepath.Join(dir, name))
			if strings.TrimSpace(stat) != "0:0:600" {
				t.Fatal("Zieldatei nicht root:root/0600")
			}
			args, err := os.ReadFile(trace)
			if err != nil {
				t.Fatal(err)
			}
			if strings.Contains(string(args), canary) {
				t.Fatal("Geheimnis in execve-Argumenten des dokumentierten Dateiwegs")
			}
		})
		count++
	}
	if count != 4 {
		t.Fatalf("vier dokumentierte Ablagebefehle erwartet, gefunden: %d", count)
	}
}

func TestGitAskpassOhneGeheimnisargumente(t *testing.T) {
	adapterTests(t)
	dir := bootstrapDir(t)
	const canary = "KANARIE_GIT_1497"
	if err := os.WriteFile(filepath.Join(dir, "git_token"), []byte(canary+"\n"), 0600); err != nil {
		t.Fatal(err)
	}
	_, cfg := render(t, nil)
	askpass := script(t, cfg, "/opt/jnpt/askpass.sh")
	trace := filepath.Join(t.TempDir(), "execve.log")
	// Echte Git-Credential-Schnittstelle und produktiver Askpass-Helfer;
	// credential fill löst die Passwortabfrage aus, baut keine Netzverbindung auf.
	cmd := exec.Command("strace", "-f", "-s", "4096", "-e", "trace=execve", "-o", trace, "git", "-c", "credential.helper=", "credential", "fill")
	// Die Windows-Worktree-Verknüpfung des Quell-Repos ist im Linux-Container
	// kein Git-Pfad; Credential-Abfragen benötigen ohnehin kein Repository.
	cmd.Dir = t.TempDir()
	cmd.Env = append(os.Environ(), "GIT_ASKPASS="+askpass, "GIT_TERMINAL_PROMPT=0", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null")
	cmd.Stdin = strings.NewReader("protocol=https\nhost=example.invalid\n\n")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("Git-Credential-Adapter fehlgeschlagen: %v %s", err, strings.ReplaceAll(string(out), canary, "[KANARIE]"))
	}
	if !strings.Contains(string(out), "username=x-access-token\n") || !strings.Contains(string(out), "password="+canary+"\n") {
		t.Fatal("Git erhält das Credential nicht über Askpass")
	}
	args, err := os.ReadFile(trace)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(args), canary) {
		t.Fatal("Git-Token steht in execve-Argumenten")
	}
}
