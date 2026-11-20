package hetzner_test

import (
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"testing"
	"time"
)

// Nur Testprozess im isolierten Netzwerk-Namespace, niemals eine echte VM.
func TestMetadataHTTPHelper(t *testing.T) {
	mode := os.Getenv("JNPT_HTTP_HELPER")
	if mode == "" {
		t.Skip("Namespace-Hilfsprozess")
	}
	if mode == "serve" {
		listener, err := net.Listen("tcp", ":8080")
		if err != nil {
			t.Fatal(err)
		}
		http.Serve(listener, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "TEST_USERDATA") }))
		return
	}
	client := &http.Client{Timeout: 300 * time.Millisecond, Transport: &http.Transport{Proxy: nil}}
	var last error
	for i := 0; i < 5; i++ {
		resp, err := client.Get("http://" + mode + ":8080/hetzner/v1/userdata")
		if err == nil {
			body, err := io.ReadAll(resp.Body)
			resp.Body.Close()
			if err != nil || string(body) != "TEST_USERDATA" {
				t.Fatal("unerwartete Testantwort")
			}
			return
		}
		last = err
		time.Sleep(50 * time.Millisecond)
	}
	t.Fatal(last)
}
