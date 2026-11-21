package hetzner_test

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/zclconf/go-cty/cty"
)

func TestVolumeFailClosedRenderUndShell(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("echter Linux-Shelladapter")
	}
	for _, mode := range []string{"missing", "mount-failed", "unmounted", "ready"} {
		t.Run(mode, func(t *testing.T) {
			dir := t.TempDir()
			device := filepath.Join(dir, "device")
			if mode != "missing" {
				command(t, "mknod", device, "b", "7", "200")
			}
			_, cfg := render(t, map[string]cty.Value{"volume_device": cty.StringVal(device)})
			start := -1
			for i, line := range cfg.Run {
				if strings.Contains(line, "seq 1 60") {
					start = i
					break
				}
			}
			if start < 0 {
				t.Fatal("gerenderte Volume-Testzeile fehlt")
			}
			body := strings.Join(cfg.Run[start:], "\n")
			body = strings.ReplaceAll(body, "/etc/motd", filepath.Join(dir, "motd"))
			body = strings.ReplaceAll(body, "/etc/fstab", filepath.Join(dir, "fstab"))
			body = strings.ReplaceAll(body, "/mnt/jnpt-data", filepath.Join(dir, "data"))
			os.WriteFile(filepath.Join(dir, "fstab"), nil, 0600)
			for _, name := range []string{"sleep", "blkid", "mkfs.ext4", "mount", "mountpoint", "docker", "systemd-tmpfiles"} {
				shim := "#!/bin/sh\necho " + name + " >> \"$TRACE\"\n"
				if name == "mount" && mode == "mount-failed" || name == "mountpoint" && mode == "unmounted" {
					shim += "exit 1\n"
				}
				os.WriteFile(filepath.Join(dir, name), []byte(shim), 0700)
			}
			cmd := exec.Command("sh", "-c", body)
			cmd.Env = append(os.Environ(), "PATH="+dir+":"+os.Getenv("PATH"), "TRACE="+filepath.Join(dir, "trace"))
			out, err := cmd.CombinedOutput()
			trace, _ := os.ReadFile(filepath.Join(dir, "trace"))
			motd, _ := os.ReadFile(filepath.Join(dir, "motd"))
			if mode == "ready" {
				if err != nil || strings.Count(string(trace), "docker\n") != 4 {
					t.Fatalf("Erfolgsweg: %v %s %s", err, out, trace)
				}
			} else {
				if err == nil {
					t.Fatalf("Volume-Fehler muss Einrichtung abbrechen: %s", trace)
				}
				if strings.Contains(string(trace), "docker") {
					t.Fatalf("Docker darf keine Root-Platten-Volumes anlegen: %s", trace)
				}
				if _, err := os.Stat(filepath.Join(dir, "data", "jnpt-data")); !os.IsNotExist(err) {
					t.Fatal("Anlagedaten auf Root-Platte angelegt")
				}
				if !strings.Contains(string(out), "Keine Anlage gestartet") || !strings.Contains(string(motd), "Keine Anlage gestartet") {
					t.Fatalf("Fehler fehlt in Ausgabe/MOTD: %s / %s", out, motd)
				}
				if mode == "missing" && strings.Count(string(trace), "sleep\n") != 60 {
					t.Fatalf("Wartefrist nicht 60 x 5 s: %s", trace)
				}
			}
		})
	}
}

func TestVolumeAbbruchMutation(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("echter Linux-Shelladapter")
	}
	dir := t.TempDir()
	b, err := os.ReadFile("cloud-init.yaml.tftpl")
	if err != nil {
		t.Fatal(err)
	}
	old := `[ -b ${volume_device} ] || fail 'Keine Anlage gestartet: Volume nach 5 Minuten nicht verfuegbar.'`
	if !strings.Contains(string(b), old) {
		t.Fatal("Mutationsanker fehlt")
	}
	os.WriteFile(filepath.Join(dir, "cloud-init.yaml.tftpl"), []byte(strings.Replace(string(b), old, ": # Abbruch entfernt", 1)), 0600)
	cmd := exec.Command(os.Args[0], "-test.v", "-test.run=^TestVolumeFailClosedRenderUndShell$/missing$")
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), "Volume-Fehler muss Einrichtung abbrechen") || !strings.Contains(string(out), "docker") {
		t.Fatalf("Mutant nicht gezielt rot: %v %s", err, out)
	}
	t.Logf("Rot belegt: %s", out)
}

func TestHandstartOhneDatenMountAbgewiesen(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("echter Linux-Shelladapter")
	}
	dir := t.TempDir()
	_, cfg := render(t, nil)
	body := fileContent(t, cfg, "/usr/local/sbin/jnpt-start")
	body = strings.ReplaceAll(body, "/etc/jnpt-bootstrap", dir)
	body = strings.ReplaceAll(body, "/etc/motd", filepath.Join(dir, "motd"))
	body = strings.ReplaceAll(body, "/run/lock/jnpt-start.lock", filepath.Join(dir, "lock"))
	body = strings.ReplaceAll(body, "/mnt/jnpt-data", filepath.Join(dir, "not-mounted"))
	os.Mkdir(filepath.Join(dir, "not-mounted"), 0700)
	os.WriteFile(filepath.Join(dir, "jnpt_master_key"), []byte(strings.Repeat("a", 64)+"\n"), 0600)
	os.WriteFile(filepath.Join(dir, "tailscale_authkey"), []byte("synthetic\n"), 0600)
	os.WriteFile(filepath.Join(dir, "systemctl"), []byte("#!/bin/sh\necho forbidden-start > \"$TRACE\"\nexit 1\n"), 0700)
	cmd := exec.Command("sh", "-c", body)
	cmd.Env = append(os.Environ(), "PATH="+dir+":"+os.Getenv("PATH"), "TRACE="+filepath.Join(dir, "trace"))
	out, err := cmd.CombinedOutput()
	motd, _ := os.ReadFile(filepath.Join(dir, "motd"))
	if err == nil || !strings.Contains(string(out), "Datenvolume nicht eingehangen") || !strings.Contains(string(motd), "Keine Anlage gestartet") {
		t.Fatalf("Handstart ohne Mount nicht gezielt abgewiesen: %v %s %s", err, out, motd)
	}
	if _, err := os.Stat(filepath.Join(dir, "trace")); !os.IsNotExist(err) {
		t.Fatal("Handstart hat ohne Mount den naechsten Adapter erreicht")
	}
}

func TestWeitereVolumeMutationen(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("echter Linux-Shelladapter")
	}
	for _, m := range []struct{ old, test string }{
		{`    mountpoint -q /mnt/jnpt-data || fail 'Keine Anlage gestartet: Datenvolume nicht eingehangen.'`, "TestVolumeFailClosedRenderUndShell/unmounted"},
		{`      mountpoint -q /mnt/jnpt-data || fail 'Keine Anlage gestartet: Datenvolume nicht eingehangen; cloud-init und Volume pruefen.'`, "TestHandstartOhneDatenMountAbgewiesen"},
	} {
		dir := t.TempDir()
		b, err := os.ReadFile("cloud-init.yaml.tftpl")
		if err != nil {
			t.Fatal(err)
		}
		if !strings.Contains(string(b), m.old) {
			t.Fatal("Mutationsanker fehlt", m.old)
		}
		os.WriteFile(filepath.Join(dir, "cloud-init.yaml.tftpl"), []byte(strings.Replace(string(b), m.old, "", 1)), 0600)
		cmd := exec.Command(os.Args[0], "-test.v", "-test.run=^"+m.test+"$")
		cmd.Dir = dir
		out, err := cmd.CombinedOutput()
		if err == nil || !strings.Contains(string(out), "--- FAIL:") {
			t.Fatalf("Mutant nicht rot: %v %s", err, out)
		}
		t.Logf("Rot belegt: %s", out)
	}
}
