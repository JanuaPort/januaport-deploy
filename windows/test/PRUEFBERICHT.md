# #1246 Paket A: Prüfbericht

## Stand und Entscheidungen

Test zuerst: Commit `d51e71b` enthält nur die roten Profilprüfungen. Drei Tests
scheiterten an fehlenden Profildateien. Die Implementierung folgt in einem
separaten Commit; dessen Hash steht im Übergabebericht.

Die Arbeitskopie enthält keine CLAUDE.md, auch nicht unter `windows/`; die
Referenz-Repositories wurden nur gelesen. `compose/` bleibt bytegleich.
Die beiden Haupt-READMEs verlinken Windows; das neue Profil ist deutsch und
englisch dokumentiert. Die LF-Regel unter `windows/` verhindert, dass ein
Windows-Checkout die gegen Git-Raw-Downloads berechneten Summen verändert.

**W6:** Ohne Sandbox statt eines erfundenen Abschaltparameters. Der echte
Vermittler v0.3.1 liefert Desktop-Pakete unabhängig von der Sandbox. Der lokale
Laufpfad und der Zeitplanpfad hängen dagegen an einer gültigen Sandbox-Isolation.
In diesem Profil gibt es keinen Sandbox-Dienst und kein optionales Profil
dafür. `tools/list` zeigt den lokalen Pin als `pending`; ein gültiges
`tools/call` liefert `refused/state`, `isolation=invalid`. Der Original-
Healthcheck meldet folgerichtig 503/unhealthy; er wird nicht grün umetikettiert.
Die Desktop-Paketprobe bleibt HTTP 200. Die Gegenprobe startet den echten Guard
mit dem Original-Seccomp-Profil und führt das synthetische Skript erfolgreich
aus (`end=ok`, Ausgabe `probe-executed`); dadurch wird der Abweisungstest rot.

Die zusätzlichen Plugin-Verzeichnisse entstehen einmalig über `plugin-init`
in einem benannten Volume statt durch Windows-Bind-Mounts oder systemd.
Der Elternordner bleibt root:0755, die Kinder gehören 65532 mit Modus 0750.
Vermittler und Fetcher erhalten jeweils nur ihren eigenen Schlüssel-Unterordner
read-only; der Kern erhält den Eltern-Mount zum atomaren Schreiben.

Der Registry-Tag `ghcr.io/januaport/januaport:v0.87.1` existierte bei der Probe
nicht. Der verfügbare Tag heißt `0.87.1`; sein Digest ist in `.env.example`
festgehalten. Der Skript-Läufer entspricht `script-runner-v0.3.1`, Image-Tag
`0.3.1`; Caddy entspricht `2.10.2-alpine`. Sämtliche laufenden Images sind per
Registry-Digest gebunden. Für den Kern erzwingt Compose zusätzlich zur
Repository-/Tag-Variablen einen eigenen Pflicht-Digest.

## Verifikation

Lokal mit Docker Desktop 4.82.0, Linux/amd64, PowerShell 5.1 und PowerShell 7:

| Prüfung | Ergebnis |
|---|---|
| `python -B -m unittest discover -s windows/test -v` | 8 Tests grün, kein Skip |
| `docker compose --env-file windows/.env.example -f windows/docker-compose.yml config --quiet` | Exit 0 |
| `caddy adapt` im gepinnten Container | Exit 0; danach echte HTTPS-Negativanfragen |
| PowerShell-Parser `ParseFile` unter `pwsh -NoProfile` | leere Fehlerliste |
| PowerShell 5.1: Tagauflösung über echten Docker-Pull/Inspect | `0.87.1` ergibt den erwarteten Digest |
| `python -B windows/test/live.py` | vollständiger Compose-Rundlauf grün |
| HTTPS `/api/device/v1/`, ohne Token | 401, Antwort der Geräte-API |
| HTTPS `/`, `/admin/mcp`, `/api/admin/tokens`, `/mcp`, `/mcp/x` | jeweils 404 |
| HTTP `127.0.0.1:8484/healthz` | 200 |
| POST `pair` mit Vertrag 1 und `{}` über HTTPS | 400, Eingabeprüfung nach bestandenem Transport-Riegel |
| derselbe POST direkt über HTTP/NAT | 401, Transport-Riegel |
| PowerShell-Leaf-Fingerprint gegen echtes TLS-DER | bytegenau gleich |
| Zugriff auf Admin-Port über eigene LAN-Schnittstelle | Verbindung scheitert |
| Tatsächliche Docker-Portbindung und Namespace | 8484 nur 127.0.0.1; Caddy `container:<jnpt-ID>` |
| Bereinigung | `down -v --remove-orphans`, keine Testcontainer/-volumes übrig |
| `git diff --check`, unverändertes `compose/` | grün |
| Namens-/Netz-Grep in neuen Dateien | keine konkreten Personen-, Kunden-, Orts- oder Betreiber-Netzwerte |

Die HTTPS-Routenprobe löst GET und POST für GUI, Admin-MCP, Admin-API, MCP,
Metrics, falsche Pfadgrenzen, Punktpfad-Traversal und kodiertes Traversal aus.
Auch Caddys Admin-Socket wird tatsächlich angesprochen und muss unerreichbar
sein. Der echte Container-Zertifikatsspeicher enthält keine importierte
Caddy-CA. Beschädigte Compose-, Caddy- und Skriptdateien werden sowohl durch
die Python-Prüfung als auch den echten PowerShell/.NET-Hashadapter abgewiesen.

## Mutationsprobe

`python -B windows/test/mutations.py`: **17/17 Mutanten erkannt**, jeweils mit
Assertion-Fehler statt Adapter-/Infrastrukturfehler. Mutanten laufen in
isolierten Dateikopien an echten Adaptern. Ihre Summen werden konsistent neu
berechnet; die ursprünglichen Dateien bleiben nachweislich bytegleich.

| Entfernte Sperre | Negativtest wird rot an |
|---|---|
| LAN-Pfad-Allowlist | echtem Caddy-HTTPS, verbotener Pfad erreicht Backend |
| Caddy `admin off` | tatsächlich erreichbarem Admin-Socket |
| `skip_install_trust` | tatsächlich importierter CA im Testcontainer |
| Loopback-Upstream | echtem Kern, TLS-Pairingprobe erreicht Eingabeprüfung nicht |
| Loopback-Bindung des Admin-Ports | tatsächlich erreichbarer eigener LAN-Schnittstelle |
| Caddy-Netz-Namensraum | echtem Compose-Adapter, falsche Dienst-Komposition |
| Pflicht-Digest des Kerns | Compose akzeptiert fehlenden Pflichtwert |
| Pflicht-Image des Kerns | Compose akzeptiert fehlenden Pflichtwert |
| Caddy-Digest-Pin | Compose liefert ungepinnte Beisteller-Referenz |
| Download-SHA-Prüfung | PowerShell akzeptiert beschädigte Profildatei |
| Summen-Zeilenformat | PowerShell ignoriert ungültige Zusatzzeile |
| Dateinamen-Allowlist | PowerShell akzeptiert unerwartete Datei |
| Duplikat-Abweisung | PowerShell akzeptiert zusätzliche doppelte Zeile |
| Vollständigkeit | PowerShell akzeptiert fehlenden Eintrag |
| Image-Eingabeprüfung | PowerShell akzeptiert ungültige Eingabe |
| Abweisung eines vorhandenen Ziels | PowerShell meldet keine Abweisung mehr |
| W6, fehlende Sandbox | echter Guard führt lokalen Pin aus, statt ihn abzuweisen |

Die W6-Gegenprobe prüft zusätzlich ausdrücklich, dass `end=ok` und die
synthetische Skriptausgabe im Fehlerbeleg stehen; ein bloßer Guard-Startfehler
zählt nicht als erfolgreiche Mutationsprobe.

## Invarianten und alternative Wege

Die vollständigen repo-weiten Treffer einschließlich `Datei:Zeile` und
Suchmustern stehen in [INVARIANTEN.txt](INVARIANTEN.txt). Gesucht wurde sowohl
nach Zusagetexten als auch nach Ports, Upstreams, Netz-Komposition, Mounts,
Runtime-/Sandbox-Startwegen, MCP-Varianten, Pin-/CA-Optionen und Bootstrap-Quellen.
Die Bestandsprofile AWS, Azure, Hetzner und `compose/` sind eigenständige
Kompositionsstellen; sie wurden zur Abgrenzung mit erfasst, aber nicht verändert.
Ihre MCP-Freigaben erweitern das Windows-Profil nicht.

Die allgemeine Formulierung „dieses Repo bringt keinen [Reverse-Proxy] mit“
unter `compose/README.md` steht im Kontext des generischen Single-Container-
Profils. Windows dokumentiert ausdrücklich seinen eigenen Proxy. Die
Auftragsgrenze „keine Änderungen an compose/“ hat hier Vorrang vor einer
Umformulierung der bestehenden generischen Anleitung.

## Offene Abnahme und Annahmen

- Der Auftraggeber veröffentlicht nach Review den unveränderlichen Profil-Tag
  `windows-v0.1.0`. Ohne Push/Tag-Veröffentlichung ist der Zwei-Befehle-Download
  noch nicht von GitHub ausführbar. Kein Push, PR, Merge oder Dispatch wurde
  ausgeführt. Der komplette Erstinstallations-Download von diesem neuen Tag
  kann entsprechend erst danach durchlaufen werden.
- IP-basierte Geräte-URLs, kein beliebiger DNS-Alias: `default_sni localhost`
  liefert das gleiche Leaf für numerische LAN-Adressen und Loopback.
- Caddys Standard-Leaf-Laufzeit beträgt 12 Stunden. Nach Erneuerung muss der
  Betreiber den neuen Fingerprint lokal prüfen und erneut koppeln. Keine
  automatische Fingerprint-Verteilung in Paket A; Dauerbetrieb bleibt offen.
- Firewall-W9 von einem zweiten Gerät innerhalb und außerhalb des lokalen
  Subnetzes prüfen. Der Host wurde nicht umkonfiguriert. Interne Docker-Netze
  ersetzen keinen Windows-/WSL-Hostschutz; breite bestehende Allow-Regeln
  müssen separat geprüft werden.
- Die lokale Git-Fixture belegt echte Vermittler-/Paketadapter, nicht den
  SSH-/Remote-Fetcher mit einem Betreiber-Repository. Vollständige Desktop-
  Kopplung mit gültigem Code sowie ein bestätigter Desktop-Auftrag bleiben
  Abnahmeschritte. Die leere Pairingprobe behauptet keine erfolgreiche Kopplung.
- Windows 10/11 Pro, bereits laufendes Docker Desktop/WSL2 und freie Ports sind
  Voraussetzungen. Update, Backup, Autologon und Tailscale wurden nicht ergänzt.
