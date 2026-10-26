# hetzner/ — Terraform-Vorlage für Hetzner Cloud

**Status: von JanuaPort GmbH betrieben (Showcase-Muster).** Dieses Modul ist
generisch aus dem Terraform-Modul abgeleitet, das unseren öffentlichen
Showcase (`mcp.januaport.ai`) trägt — ohne unsere konkreten Werte (Domain,
Tailnet-Name, Kontoname, Tokens, IPs). Es provisioniert eine
**Single-Node**-VM (kein k8s, kein Postgres — ein Server) und rollt darauf den
gehärteten Drei-Container-Stack aus dem Produkt-Repo aus (`jnpt` + `caddy` +
`tailscale`-Sidecar).

**Terraform-Hinweis (JanuaPort/januaport#776):** Ist Terraform in der eigenen
Umgebung verfügbar, vor dem `apply` zusätzlich `terraform fmt -check -recursive`
und `terraform validate` fahren. Ist es nicht verfügbar, gilt: Prüfung durch
Lesen statt Behauptung.

## Voraussetzungen

- Terraform ≥ 1.5, Provider `hetznercloud/hcloud` (`terraform init` lädt ihn).
- Ein Hetzner-Cloud-Projekt + API-Token (Read & Write).
- Ein Tailscale-Konto + Auth-Key, falls die Admin-Fläche über das Tailnet
  erreichbar sein soll (empfohlen — siehe „Sicherheits-Defaults").
- Eine eigene Domain mit Zugriff auf die DNS-Zone (A-Record nach `apply`).
- Ein gepinnter JanuaPort-Image-Tag aus der Registry.

## Schritte

1. `terraform.tfvars.example` nach `terraform.tfvars` kopieren, echte Werte
   eintragen (`terraform.tfvars` ist gitignored — Secrets NIE committen).
2. ```bash
   terraform init
   terraform plan
   terraform apply
   ```
3. DNS: A-Record `domain` → `server_ipv4` (Output nach `apply`) setzen. Caddy
   stellt das TLS-Zertifikat erst danach aus (ACME-Challenge).
4. Weiter mit der Inbetriebnahme-Doku des Produkts (`docs/inbetriebnahme.md`
   im Produkt-Repo `JanuaPort/januaport`).

## Variablen (Auswahl, vollständig in `variables.tf`)

| Variable | sensitive | Default | Zweck |
|---|---|---|---|
| `hcloud_token` | ✅ | — | Hetzner-Cloud-API-Token |
| `tailscale_authkey` | ✅ | — | Tailnet-Beitritt des Sidecars |
| `jnpt_master_key` | ✅ | — | Vault-Master-Key (64 Hex, validiert) |
| `domain` | — | — | öffentliche Domain (TLS); validiert |
| `acme_email` | — | — | Let's-Encrypt-Kontakt |
| `ts_hostname` | — | `jnpt` | Tailnet-Hostname (Admin-URL) |
| `server_type` / `location` | — | `cpx22` / `nbg1` | Server-Typ/Standort (Verfügbarkeit vor `apply` prüfen) |
| `ssh_public_key` | — | — | Admin-SSH-Key |
| `ssh_allowed_cidr` | — | **Pflicht, kein Default** | SSH-Quellen — bewusste Entscheidung statt stiller Vorgabe |
| `public_web_enabled` | — | `false` | öffnet 80/443 in der Firewall |
| `image_ref` | — | Pflicht | gepinnter Registry-Tag, den die VM zieht |
| `registry_token` | ✅ | `""` | optional: PAT für privaten Registry-Pull |
| `git_repo` / `git_ref` | — | Produkt-Repo / `main` | Quelle der Konfig-Dateien (Compose/Caddyfile/tailscale-serve) |
| `git_token` | ✅ | `""` | optional: PAT für privaten Konfig-Klon |
| `update_manifest_url` / `update_public_keys` | — | `""` | optionaler Versions-Check (offline-first) |
| `updater_image_repo` | — | Produkt-Registry | Allowlist des Host-Aktuators |

**Abweichung vom Herkunfts-Modul:** `ssh_allowed_cidr` ist hier **Pflicht ohne
Default** (im Produkt-Repo-Modul hat sie `default = []`) — wer dieses Modul
für die eigene Infrastruktur anwendet, soll die SSH-Quelle bewusst entscheiden
statt sich auf einen stillen Default zu verlassen.

## Dateien

- `versions.tf` — Provider-Anforderung.
- `variables.tf` — Eingaben.
- `main.tf` — SSH-Key, Firewall (deny-by-default), Volume, Server.
- `outputs.tf` — Server-IPs, DNS-Hinweis, Admin-Zugangs-Hinweis.
- `cloud-init.yaml.tftpl` — First-Boot-Skript: Docker installieren, Volume
  mounten, Konfig-Dateien aus dem Produkt-Repo klonen, Secrets/`.env`
  schreiben, Image ziehen, Compose starten, Host-Aktuator einrichten.
- `terraform.tfvars.example` — Platzhalter-Vorlage.

## Sicherheits-Defaults

- Firewall ist **deny-by-default**: SSH nur aus `ssh_allowed_cidr`, die
  öffentliche Web-Fläche (80/443) nur bei `public_web_enabled = true`.
- **Kein Port 8484 in der Firewall** — JanuaPort ist von außen nie direkt
  erreichbar, nur über `caddy` (öffentliche Whitelist) oder `tailscale`
  (Admin-Fläche, nur im Tailnet).
- Secrets (Hetzner-Token, Tailscale-Authkey, Master-Key) landen nur in
  `terraform.tfvars` (gitignored) bzw. im Terraform-State (ebenfalls
  gitignored, lokal halten — für Team-Betrieb ein verschlüsseltes
  Remote-Backend erwägen).

## Host-Firewall für das Plugin-Netz (Beisteller, JanuaPort/januaport#1040, #1194)

Wer Beisteller betreibt (Skript-Läufer, agent-runner, google-reporting), braucht auf dem Host eine Regel. Sie verhindert, dass ein Container am Plugin-Netz `jnpt_plugins` über das Bridge-Gateway Dienste des Hosts erreicht, zum Beispiel sshd oder einen lokalen Modell-Server. `internal: true` sperrt nur den Weg nach außen, den Host selbst sperrt es nicht. Gemessen wurde das auf der Showcase am 26.10.2026.

1. **Bridge-Namen pinnen**, damit die Regel an einem festen Namen hängt und nicht am Subnetz:
   ```yaml
   networks:
     plugins:
       name: jnpt_plugins
       internal: true
       driver_opts:
         com.docker.network.bridge.name: jnpt-plugins
   ```
   ⚠️ Ein Bridge-Name lässt sich nur beim Anlegen des Netzes setzen. Bei einer bestehenden Anlage nimmst du deshalb zuerst alle Plugin-Stacks herunter, danach den Kern, und startest dann in umgekehrter Reihenfolge. Jeder Aufruf bekommt `-f` auf die eigene Datei, und `COMPOSE_FILE` darf **nicht** exportiert sein. Sonst trifft ein `down` das falsche Projekt.
2. **Regel**, idempotent, für IPv4 und IPv6. Sie greift auch, bevor Docker die Bridge anlegt:
   ```sh
   # /usr/local/sbin/jnpt-plugin-net-guard.sh
   for IF in jnpt-plugins; do
     iptables  -C INPUT -i "$IF" -j DROP 2>/dev/null || iptables  -I INPUT 1 -i "$IF" -j DROP
     ip6tables -C INPUT -i "$IF" -j DROP 2>/dev/null || ip6tables -I INPUT 1 -i "$IF" -j DROP
   done
   ```
   Hat ein Beisteller ein eigenes Ausgangsnetz mit gepinnter Bridge, etwa google-reporting mit `jnpt-gr-egress`, gehört dessen Name mit in die Liste.
3. **Dauerhaft** über eine systemd-Unit `jnpt-plugin-net-guard.service`: `Type=oneshot`, `After=`, `Requires=` und `PartOf=docker.service`, `WantedBy=multi-user.target docker.service`. Sie ruft das Skript auf.
4. **Prüfen**, auch nach jedem Neustart des Hosts: Aus jedem Container am Plugin-Netz darf **kein** lauschender Host-Port (`ss -lnt`) über das Bridge-Gateway erreichbar sein. `jnpt:8484` muss erreichbar bleiben.

Die Box bringt mit `scripts/hardening.sh` eine input-Kette mit `policy drop` mit. Ob sie das Plugin-Netz vollständig erfasst, wird in JanuaPort/januaport#1194 geprüft.
