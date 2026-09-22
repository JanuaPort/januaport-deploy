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
