package hetzner_test

import (
	"os"
	"regexp"
	"strings"
	"testing"
)

func TestCheckoutMitCommitPin(t *testing.T) {
	b, err := os.ReadFile("../.github/workflows/secret-scan.yml")
	if err != nil {
		t.Fatal(err)
	}
	if !regexp.MustCompile(`uses: actions/checkout@[0-9a-f]{40} # v4\.`).Match(b) || strings.Contains(string(b), "actions/checkout@v4\n") {
		t.Fatal("Checkout ohne dokumentierten SHA-Pin")
	}
}

func TestDokumentationAufReleaseStand(t *testing.T) {
	for _, path := range []string{"../README.md", "../README.de.md", "../windows/README.md", "../windows/README.en.md", "../windows/RUNBOOK.md"} {
		b, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		for _, stale := range []string{"A + B1–B3", "in B4 offen", "remain open in B4", "Bis dahin ist die URL", "publisher must first publish", "Vor dem Tag `windows-v0.3.0`", "before tagging\n`windows-v0.3.0`", "bevor `windows-v0.3.0` getaggt wird"} {
			if strings.Contains(string(b), stale) {
				t.Errorf("%s: ueberholter Stand %q", path, stale)
			}
		}
	}
	for _, path := range []string{"../compose/.env.example", "../compose/docker-compose.yml", "terraform.tfvars.example", "variables.tf", "../aws/cloud-init.yaml", "../azure/cloud-init.yaml"} {
		b, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if strings.Contains(string(b), "0.59.0") {
			t.Errorf("%s: veraltetes Beispiel-Image", path)
		}
	}
}
