package hetzner_test

import (
	"bufio"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestStartWeistFehlendeUndUnsichereDateienAb(t *testing.T) {
	adapterTests(t)
	_, cfg := render(t, nil)
	start := script(t, cfg, "/usr/local/sbin/jnpt-start")
	// Feste Produktionspfade, ausschließlich im wegwerfbaren Testcontainer.
	dir := "/etc/jnpt-bootstrap"
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Fatal("Test verlangt einen frischen Container")
	}
	if err := os.Mkdir(dir, 0700); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	key := filepath.Join(dir, "jnpt_master_key")
	tail := filepath.Join(dir, "tailscale_authkey")
	put := func(path, value string, mode os.FileMode) {
		t.Helper()
		os.Remove(path)
		if err := os.WriteFile(path, []byte(value+"\n"), mode); err != nil {
			t.Fatal(err)
		}
	}
	check := func(wantError bool, message string) {
		t.Helper()
		calls := [][]string{{start, "--check"}}
		if wantError {
			calls = append(calls, []string{start})
		}
		for _, args := range calls {
			out, err := exec.Command("sh", args...).CombinedOutput()
			if (err != nil) != wantError || (wantError && !strings.Contains(string(out), message)) {
				t.Fatalf("Ablegeprüfung: err=%v Ausgabe=%s, erwartet Fehler=%t/%s", err, out, wantError, message)
			}
			if strings.Contains(string(out), "KANARIE_") || strings.Contains(string(out), strings.Repeat("a", 64)) {
				t.Fatal("Startprüfung gibt Geheimnis aus")
			}
		}
	}
	check(true, "jnpt_master_key")
	put(key, strings.Repeat("a", 64), 0600)
	check(true, "tailscale_authkey")
	put(tail, "KANARIE_TAILSCALE", 0600)
	check(false, "")
	for _, name := range []string{"jnpt_master_key", "tailscale_authkey", "git_token", "registry_token"} {
		t.Run(name, func(t *testing.T) {
			path := filepath.Join(dir, name)
			value := "KANARIE_TOKEN"
			if name == "jnpt_master_key" {
				value = strings.Repeat("a", 64)
			}
			put(path, value, 0644)
			check(true, name)
			put(path, value, 0600)
			if err := os.Chown(path, 65532, 65532); err != nil {
				t.Fatal(err)
			}
			check(true, name)
			put(path, "", 0600)
			check(true, name)
			put(path, value+"\nzweite-zeile", 0600)
			check(true, name)
			put(path, value, 0600)
			check(false, "")
			target := filepath.Join(t.TempDir(), "token")
			put(target, value, 0600)
			os.Remove(path)
			if err := os.Symlink(target, path); err != nil {
				t.Fatal(err)
			}
			check(true, name)
			put(path, value, 0600)
		})
	}
	put(key, "kein-hex-key", 0600)
	check(true, "64 Hex")
	put(key, strings.Repeat("a", 64), 0600)
	put(tail, "erste\nzweite", 0600)
	check(true, "tailscale_authkey")
	put(tail, "KANARIE_TAILSCALE", 0600)
	// Auch die root- und Parallelstartsperren am echten Shell-/flock-Adapter.
	cmd := exec.Command("setpriv", "--reuid=65532", "--regid=65532", "--clear-groups", "sh", "-s", "--", "--check")
	cmd.Stdin = strings.NewReader(fileContent(t, cfg, "/usr/local/sbin/jnpt-start"))
	if out, err := cmd.CombinedOutput(); err == nil || !strings.Contains(string(out), "als root") {
		t.Fatalf("Nicht-root-Start nicht abgewiesen: %v %s", err, out)
	}
	lock := exec.Command("flock", "-x", "/run/lock/jnpt-start.lock", "cat")
	in, err := lock.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	out, err := lock.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := lock.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { in.Close(); lock.Wait() })
	if _, err := in.Write([]byte("bereit\n")); err != nil {
		t.Fatal(err)
	}
	if line, err := bufio.NewReader(out).ReadString('\n'); err != nil || line != "bereit\n" {
		t.Fatalf("flock nicht bereit: %q %v", line, err)
	}
	if out, err := exec.Command("sh", start).CombinedOutput(); err == nil || !strings.Contains(string(out), "laeuft bereits") {
		t.Fatalf("Parallelstart nicht abgewiesen: %v %s", err, out)
	}
}

func TestAlteTerraformGeheimnisseWerdenAbgewiesen(t *testing.T) {
	adapterTests(t)
	if os.Getenv("JNPT_TERRAFORM_TESTS") != "1" {
		t.Skip("Terraform-CLI separat freigeben (lokale SEC-R2-Sperre #1055)")
	}
	dir := t.TempDir()
	src, err := os.ReadFile("variables.tf")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "variables.tf"), src, 0600); err != nil {
		t.Fatal(err)
	}
	cmd := exec.Command("terraform", "-chdir="+dir, "init", "-backend=false", "-input=false")
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("init: %v %s", err, out)
	}
	base := []string{"-chdir=" + dir, "plan", "-input=false", "-lock=false", "-refresh=false", "-no-color",
		"-var=hcloud_token=KANARIE_API", "-var=domain=mcp.example.com", "-var=acme_email=admin@example.com",
		"-var=ssh_public_key=TEST", "-var=ssh_allowed_cidr=[]", "-var=image_ref=example:1"}
	if out, err := exec.Command("terraform", base...).CombinedOutput(); err != nil {
		t.Fatalf("leere Altvariablen: %v %s", err, out)
	}
	for _, name := range []string{"jnpt_master_key", "tailscale_authkey", "git_token", "registry_token"} {
		t.Run(name, func(t *testing.T) {
			value := "KANARIE_1497"
			if name == "jnpt_master_key" {
				value = strings.Repeat("a", 64)
			}
			out, err := exec.Command("terraform", append(append([]string{}, base...), "-var="+name+"="+value)...).CombinedOutput()
			if err == nil || !strings.Contains(string(out), "#1497") || !strings.Contains(string(out), name) {
				t.Fatalf("Altvariable %s nicht mit Migrationshinweis abgewiesen: %v\n%s", name, err, out)
			}
			if strings.Contains(string(out), value) {
				t.Fatal("Migrationsfehler gibt den Wert aus")
			}
		})
	}
}

func TestMetadatenSperreAmEchtenNetz(t *testing.T) {
	adapterTests(t)
	_, cfg := render(t, nil)
	guard := script(t, cfg, "/usr/local/sbin/jnpt-metadata-guard.sh")
	// Zwei Namespaces: Container -> Host-FORWARD/DOCKER-USER -> Metadaten.
	// Alle Adressen gehören ausschließlich diesem isolierten Testnetz.
	for _, ns := range []string{"jnpt-client", "jnpt-metadata"} {
		command(t, "ip", "netns", "add", ns)
		t.Cleanup(func() { exec.Command("ip", "netns", "del", ns).Run() })
	}
	command(t, "ip", "link", "add", "jnpt-in", "type", "veth", "peer", "name", "client0")
	command(t, "ip", "link", "set", "client0", "netns", "jnpt-client")
	command(t, "ip", "addr", "add", "192.0.2.1/24", "dev", "jnpt-in")
	command(t, "ip", "link", "set", "jnpt-in", "up")
	command(t, "ip", "-n", "jnpt-client", "addr", "add", "192.0.2.2/24", "dev", "client0")
	command(t, "ip", "-n", "jnpt-client", "link", "set", "client0", "up")
	command(t, "ip", "-n", "jnpt-client", "route", "add", "default", "via", "192.0.2.1")
	command(t, "ip", "link", "add", "jnpt-out", "type", "veth", "peer", "name", "metadata0")
	command(t, "ip", "link", "set", "metadata0", "netns", "jnpt-metadata")
	command(t, "ip", "addr", "add", "198.51.100.1/24", "dev", "jnpt-out")
	command(t, "ip", "link", "set", "jnpt-out", "up")
	command(t, "ip", "-n", "jnpt-metadata", "addr", "add", "198.51.100.2/24", "dev", "metadata0")
	command(t, "ip", "-n", "jnpt-metadata", "addr", "add", "169.254.169.254/32", "dev", "metadata0")
	command(t, "ip", "-n", "jnpt-metadata", "addr", "add", "169.254.42.42/32", "dev", "metadata0")
	command(t, "ip", "-n", "jnpt-metadata", "link", "set", "metadata0", "up")
	command(t, "ip", "-n", "jnpt-metadata", "route", "add", "default", "via", "198.51.100.1")
	command(t, "ip", "route", "add", "169.254.0.0/16", "via", "198.51.100.2")
	command(t, "sysctl", "-w", "net.ipv4.ip_forward=1")
	command(t, "iptables", "-N", "DOCKER-USER")
	command(t, "iptables", "-A", "FORWARD", "-j", "DOCKER-USER")
	command(t, "iptables", "-A", "DOCKER-USER", "-j", "ACCEPT")
	// HTTP über TCP, ohne curl/ping-Abhängigkeit; nutzt das Go-Testbinary im Namespace.
	server := exec.Command("ip", "netns", "exec", "jnpt-metadata", os.Args[0], "-test.run=^TestMetadataHTTPHelper$")
	server.Env = append(os.Environ(), "JNPT_HTTP_HELPER=serve")
	if err := server.Start(); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { server.Process.Kill(); server.Wait() })
	probe := func(ip string, reachable bool) {
		t.Helper()
		cmd := exec.Command("ip", "netns", "exec", "jnpt-client", os.Args[0], "-test.run=^TestMetadataHTTPHelper$")
		cmd.Env = append(os.Environ(), "JNPT_HTTP_HELPER="+ip)
		out, err := cmd.CombinedOutput()
		if (err == nil) != reachable {
			t.Fatalf("HTTP %s erreichbar=%t: %v %s", ip, reachable, err, out)
		}
	}
	probe("169.254.169.254", true)
	probe("169.254.42.42", true)
	command(t, "sh", guard)
	for _, ip := range []string{"169.254.169.254", "169.254.42.42"} {
		probe(ip, false)
	}
	probe("198.51.100.2", true)
	command(t, "sh", guard)
	rules := command(t, "iptables", "-S", "DOCKER-USER")
	if strings.Count(rules, "-j DROP") != 1 || strings.Index(rules, "-j DROP") > strings.Index(rules, "-j ACCEPT") {
		t.Fatalf("Reihenfolge/Idempotenz: %s", rules)
	}
	// Ein nachträglich vorgeschobenes ACCEPT darf den erneuten Guard-Lauf nicht umgehen.
	command(t, "iptables", "-I", "DOCKER-USER", "1", "-j", "ACCEPT")
	command(t, "sh", guard)
	probe("169.254.169.254", false)
	// Docker-Neustart: Kette geleert; derselbe ExecStart muss erneut sperren.
	command(t, "iptables", "-F", "DOCKER-USER")
	command(t, "iptables", "-A", "DOCKER-USER", "-j", "ACCEPT")
	command(t, "sh", guard)
	probe("169.254.169.254", false)
}
