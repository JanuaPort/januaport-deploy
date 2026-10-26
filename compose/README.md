# compose/ — generischer Docker-Compose-Stack

**Status: von JanuaPort GmbH betrieben (Showcase-Muster).** Dieselbe
jnpt-Dienstdefinition läuft produktiv auf unserem Showcase (dort zusätzlich
hinter einem Caddy/Tailscale-Sidecar-Paar, das showcase-spezifisch ist). Diese
Vorlage ist der eigenständige Selbst-Hoster-Pfad: ein Container, eigener
Reverse-Proxy nach Wahl.

## Voraussetzungen

- Docker Engine + Compose-Plugin (`docker compose version`, v2 oder neuer).
- Ein gepinnter JanuaPort-Image-Tag aus der Registry
  (`ghcr.io/januaport/januaport:<TAG>`).
- Falls die Anlage öffentlich erreichbar sein soll: ein eigener Reverse-Proxy
  mit TLS vor Port 8484 (siehe „Sicherheits-Defaults" unten) — dieses Repo
  bringt keinen mit.

## Schritte

1. `.env.example` nach `.env` kopieren, Werte eintragen (`JANUAPORT_IMAGE` ist
   Pflicht, alles andere optional — siehe Kommentare in `.env.example`).
2. Starten:
   ```bash
   docker compose --env-file .env up -d
   ```
3. Weiter mit der Inbetriebnahme-Doku des Produkts (Master-Schlüssel sichern,
   Admin-Passwort setzen, ersten Admin-Token erzeugen): `docs/inbetriebnahme.md`
   im Produkt-Repo `JanuaPort/januaport`.

## Prüfen

`/healthz` beweist nur, dass der Prozess läuft — nicht, dass ein Client
arbeiten kann. Beides prüfen:

```bash
# 1) Liveness (notwendig, nicht hinreichend):
curl -fsS http://localhost:8484/healthz

# 2) Echter MCP-Rundlauf mit einem gültigen Bearer-Token (z. B. der erste
#    Admin-Token aus der Inbetriebnahme, oder ein Team-Token):
TOK=<ihr-token>

curl -s -X POST http://localhost:8484/mcp \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{
       "protocolVersion":"2025-11-25","capabilities":{},
       "clientInfo":{"name":"deploy-check","version":"1"}}}'

curl -s -X POST http://localhost:8484/mcp \
  -H "Authorization: Bearer $TOK" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

Erwartung: `initialize` liefert `result.serverInfo` (Name/Version der Anlage);
`tools/list` nennt mindestens die strukturell immer vorhandenen Werkzeuge
(Katalog, Problem-Melden, Ping) — erst das ist der Beweis „der Kunde kann
arbeiten", nicht nur „der Prozess läuft".

## Update

```bash
docker compose --env-file .env pull
docker compose --env-file .env up -d
```

`/data` (Volume `jnpt-data`) bleibt beim Image-Tausch unberührt.

## Sicherheits-Defaults

- **Port 8484 ist nur an Loopback gebunden** (`127.0.0.1:8484:8484`).
  Öffentlich erreichbar wird die Anlage ausschließlich über einen eigenen
  Reverse-Proxy mit TLS, der **selektiv** weiterleitet (`/mcp` exakt, `/healthz`,
  OAuth-Discovery) — kein `/mcp/*`-Wildcard, sonst leakt die Admin-GUI.
- **Die Admin-Fläche gehört nie ins offene Internet**: GUI, `/admin/mcp`,
  `/api/admin/*`, `/metrics`. Zugriff nur über SSH-Tunnel, VPN/Tailnet oder ein
  internes Netz.
- **Secrets kommen ausschließlich aus der `.env`** bzw. später aus dem Vault
  der Anlage selbst — nie in `docker-compose.yml`, nie ins Repo.

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
