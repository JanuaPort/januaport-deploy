//go:build ignore

// Aufruf nur zur bewussten Herkunfts-Aktualisierung, siehe README.
// Neue/veraenderte Ausnahmen bekommen KEINEN automatischen Freibrief:
// ihr Grund muss vor dem Commit geprueft werden.
package main

import (
	"crypto/sha256"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/hashicorp/hcl/v2"
	"github.com/hashicorp/hcl/v2/hclsyntax"
	"github.com/zclconf/go-cty/cty"
	"gopkg.in/yaml.v3"
)

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func sections(src []byte) map[string]string {
	vars := map[string]cty.Value{"script_runner_enabled": cty.False}
	for k, v := range map[string]string{
		"domain": "mcp.example.com", "acme_email": "admin@example.org", "ts_hostname": "jnpt",
		"image_ref": "ghcr.io/januaport/januaport:0.106.0", "git_repo": "https://github.com/JanuaPort/januaport.git", "git_ref": "v0.106.0",
		"update_manifest_url": "", "update_plugins_url": "", "update_public_keys": "", "updater_image_repo": "ghcr.io/januaport/januaport",
		"volume_device": "/dev/disk/by-id/scsi-0HC_Volume_123",
	} {
		vars[k] = cty.StringVal(v)
	}
	e, d := hclsyntax.ParseTemplate(src, "cloud-init.yaml.tftpl", hcl.InitialPos)
	if d.HasErrors() {
		panic(d.Error())
	}
	v, d := e.Value(&hcl.EvalContext{Variables: vars})
	if d.HasErrors() {
		panic(d.Error())
	}
	var root map[string]interface{}
	must(yaml.Unmarshal([]byte(v.AsString()), &root))
	values := map[string]interface{}{}
	for name, value := range root {
		if name != "write_files" {
			values[name] = value
			continue
		}
		for _, file := range value.([]interface{}) {
			f := file.(map[string]interface{})
			values["write_files:"+f["path"].(string)] = f
		}
	}
	hashes := map[string]string{}
	for name, value := range values {
		b, err := json.Marshal(value)
		must(err)
		hashes[name] = fmt.Sprintf("%x", sha256.Sum256(b))
	}
	return hashes
}

func main() {
	corePath := flag.String("core", "", "Export der Kern-Vorlage")
	commit := flag.String("commit", "", "40-stelliger Herkunfts-Commit")
	flag.Parse()
	if len(*commit) != 40 || *corePath == "" {
		panic("-core und -commit erforderlich")
	}
	core, err := os.ReadFile(*corePath)
	must(err)
	local, err := os.ReadFile("cloud-init.yaml.tftpl")
	must(err)
	type exception struct{ Core, Deploy, Reason string }
	type manifest struct {
		SourceCommit, CoreTemplateSHA256 string
		CoreSections                     map[string]string
		Exceptions                       map[string]exception
	}
	m := manifest{SourceCommit: *commit, CoreTemplateSHA256: fmt.Sprintf("%x", sha256.Sum256(core)), CoreSections: sections(core), Exceptions: map[string]exception{}}
	oldBytes, err := os.ReadFile("testdata/core-drift.json")
	var old manifest
	if err == nil {
		must(json.Unmarshal(oldBytes, &old))
	}
	deploy := sections(local)
	names := map[string]bool{}
	for n := range m.CoreSections {
		names[n] = true
	}
	for n := range deploy {
		names[n] = true
	}
	for name := range names {
		c, l := m.CoreSections[name], deploy[name]
		if c == l {
			continue
		}
		reason := old.Exceptions[name].Reason
		if reason == "" {
			reason = "PRUEFEN: Unterschied begruenden"
		}
		m.Exceptions[name] = exception{c, l, reason}
	}
	b, err := json.MarshalIndent(m, "", "  ")
	must(err)
	must(os.MkdirAll("testdata", 0755))
	must(os.WriteFile("testdata/core-drift.json", append(b, '\n'), 0644))
}
