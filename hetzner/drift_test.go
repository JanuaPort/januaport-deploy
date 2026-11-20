package hetzner_test

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v3"
)

type driftException struct{ Core, Deploy, Reason string }
type driftManifest struct {
	SourceCommit       string
	CoreTemplateSHA256 string
	CoreSections       map[string]string
	Exceptions         map[string]driftException
}

// Jedes YAML-Feld wird erfasst, auch neue Sicherheitsdateien und neue Root-
// Felder. Ausnahmen frieren BEIDE Seiten ein, kein Pfad wird ignoriert.
func driftSections(t *testing.T, rendered string) map[string]string {
	t.Helper()
	var root map[string]interface{}
	if err := yaml.Unmarshal([]byte(rendered), &root); err != nil {
		t.Fatal(err)
	}
	sections := map[string]interface{}{}
	for name, value := range root {
		if name != "write_files" {
			sections[name] = value
			continue
		}
		for _, file := range value.([]interface{}) {
			f := file.(map[string]interface{})
			path := "write_files:" + f["path"].(string)
			if _, ok := sections[path]; ok {
				t.Fatalf("doppelter Dateipfad: %s", path)
			}
			sections[path] = f
		}
	}
	hashes := map[string]string{}
	for name, value := range sections {
		b, err := json.Marshal(value)
		if err != nil {
			t.Fatal(err)
		}
		hashes[name] = fmt.Sprintf("%x", sha256.Sum256(b))
	}
	return hashes
}

func checkDrift(m driftManifest, deploy map[string]string) error {
	names := map[string]bool{}
	for name := range m.CoreSections {
		names[name] = true
	}
	for name := range deploy {
		names[name] = true
	}
	for name := range m.Exceptions {
		if !names[name] {
			return fmt.Errorf("verwaiste Ausnahme %s", name)
		}
	}
	for name := range names {
		core, local := m.CoreSections[name], deploy[name]
		if e, ok := m.Exceptions[name]; ok {
			if e.Reason == "" || strings.Contains(e.Reason, "PRUEFEN:") || e.Core != core || e.Deploy != local || core == local {
				return fmt.Errorf("Ausnahme veraltet/unbegruendet: %s", name)
			}
		} else if core != local {
			return fmt.Errorf("unerklaerte Drift: %s", name)
		}
	}
	return nil
}

func TestDriftLehntVeraendertenKernExportAb(t *testing.T) {
	path := filepath.Join(t.TempDir(), "core.tftpl")
	os.WriteFile(path, []byte("# Neue SEC-Haertung in aktueller Kern-Vorlage\n"), 0600)
	cmd := exec.Command(os.Args[0], "-test.run=^TestHerkunftsDrift$", "-test.v")
	cmd.Env = append(os.Environ(), "JNPT_CORE_TEMPLATE="+path)
	out, err := cmd.CombinedOutput()
	if err == nil || !strings.Contains(string(out), "Kern-Vorlage geaendert") {
		t.Fatalf("aktuelle Herkunftsdrift nicht abgewiesen: %v %s", err, out)
	}
}

func TestHerkunftsDrift(t *testing.T) {
	b, err := os.ReadFile("testdata/core-drift.json")
	if err != nil {
		t.Fatal(err)
	}
	var m driftManifest
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatal(err)
	}
	if len(m.SourceCommit) != 40 || len(m.CoreTemplateSHA256) != 64 || len(m.CoreSections) == 0 {
		t.Fatal("Herkunft fehlt")
	}
	// Kein Zugriff auf das private Produkt-Repo im öffentlichen CI nötig.
	// Der Integrationslauf bekommt den aktuellen Kern-Export zwingend per Env.
	if path := os.Getenv("JNPT_CORE_TEMPLATE"); path != "" {
		core, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if fmt.Sprintf("%x", sha256.Sum256(core)) != m.CoreTemplateSHA256 {
			t.Fatal("Kern-Vorlage geaendert: neue SEC-Haertungen und Ausnahmen pruefen, Baseline nachziehen")
		}
	} else {
		t.Log("Offline-Baseline; aktueller Kern-Abgleich separat mit JNPT_CORE_TEMPLATE")
	}
	rendered, _ := render(t, nil)
	if err := checkDrift(m, driftSections(t, rendered)); err != nil {
		t.Fatal(err)
	}
}

func TestDriftWeistNeueHaertungUndAusnahmeAenderungAb(t *testing.T) {
	m := driftManifest{CoreSections: map[string]string{"security": "kern"}, Exceptions: map[string]driftException{"security": {Core: "kern", Deploy: "deploy", Reason: "anderer Pfad, separat geprueft"}}}
	if err := checkDrift(m, map[string]string{"security": "deploy"}); err != nil {
		t.Fatal(err)
	}
	m.CoreSections["neue_SEC_Datei"] = "neu"
	if err := checkDrift(m, map[string]string{"security": "deploy"}); err == nil {
		t.Fatal("neue Kern-Haertung still ignoriert")
	}
	delete(m.CoreSections, "neue_SEC_Datei")
	if err := checkDrift(m, map[string]string{"security": "unsicher"}); err == nil {
		t.Fatal("Ausnahme erlaubt beliebige lokale Aenderung")
	}
	m.CoreSections["security"] = "neuer Kern"
	if err := checkDrift(m, map[string]string{"security": "deploy"}); err == nil {
		t.Fatal("Ausnahme erlaubt beliebige Kern-Aenderung")
	}
}
