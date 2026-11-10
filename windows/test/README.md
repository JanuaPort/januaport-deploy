# Prüfungen für das Windows-Profil (Paket A und B1)

Vom Repo-Root unter Windows: Python-Standardbibliothek, Windows PowerShell 5.1
und Docker Desktop (Linux/amd64). Kein Python-Paket und kein PowerShell-Modul
muss installiert werden. Die beiden Image-Digests der Beisteller werden aus
dem echten `docker compose config` gelesen. Fehlendes Docker ist ein Fehler.

```powershell
python -B -m unittest discover -s windows/test -v
python -B windows/test/live.py
python -B windows/test/mutations.py
```

Die Mail-Tests lesen die SMTP-/Notify-Umgebung aus echtem `docker compose config`:
gesetzte, fehlende und leere Werte, fester SMTP-Secret-Dateipfad und feste lokale
Admin-URL. Der Graph-Secret-Dateipfad ist standardmäßig leer; der vorgesehene
Wert `/run/secrets/graph_client_secret` wird aus einer echten `.env` übernommen.
Eine reine SMTP-`.env` muss alle `JNPT_NOTIFY_GRAPH_*`-Werte leer ergeben,
damit der Kern keine ignorierte Graph-Konfiguration meldet. Dies wird für
fehlenden, leeren und auf `smtp` gesetzten Transport am Compose-Adapter geprüft.
Prozessumgebung und eine echte temporäre `.env` versuchen ausdrücklich,
ein Klartext-SMTP-Passwort, ein Graph-Client-Secret sowie andere SMTP-/Admin-Pfade
einzuschleusen. Auch Graph-Zertifikat- und Schlüsselpfade werden angeboten und
nicht übernommen: v1 unterstützt ausschließlich Client-Secret. PowerShell 5.1
legt beide leeren Secret-Dateien an und erhält vorhandene Inhalte sowie `.env`.
Ein isolierter Compose-Aufruf mit dem vorhandenen Python-Beisteller prüft beide
leeren Dateien an den tatsächlichen Secret-Mounts; dafür ist kein SMTP-Server
oder Graph-Zugang erforderlich. Die Zustellung selbst
ist eine zusätzliche Betreiberprüfung gemäß [Mail](../README.md#mail).

Die Standardtests prüfen Summen samt beschädigter Dateien, echte
PowerShell-Summenprüfung einschließlich Format-/Dateinamen-/Duplikat- und
Vollständigkeitssperren, Eingabe- und Zielverzeichnis-Abweisungen sowie den
Compose-Adapter. Ein OpenSSL-Container erzeugt das echte P-256-Leaf: Laufzeit,
SANs und `CA:FALSE` werden geprüft, ein unvollständiges Paar wird abgewiesen.
Das Caddyfile muss feste PEM-Dateien statt eines internen Ausstellers laden.
Für Caddy läuft ein echter HTTPS-Server im Netz-Namensraum
eines synthetischen HTTP-Backends. Die Negativanfragen umfassen GET/POST,
GUI, Admin-MCP, Admin-API, MCP, Metrics, Pfadgrenzen und Traversal. Der Test
versucht auch Caddys Admin-Socket zu erreichen und prüft den tatsächlichen
Container-Zertifikatsspeicher auf importierte Caddy-CAs.

Der echte Skript-Läufer v0.3.1 erhält einen synthetischen lokalen Git-Store und
Freigabemarken. Desktop-Paketabruf muss HTTP 200 liefern; ein lokaler Aufruf
mit gültigem Lauf-Tokenformat, Commit und Manifest muss `refused/state` und
`isolation=invalid` liefern. Dies belegt den Vermittler-/Paketadapter, nicht
die SSH-Anmeldung oder die Remote-Standard-Zweig-Prüfung des Fetchers.

`live.py` benötigt freie Ports 443 und 8484. Es startet das vollständige Profil
mit dem in `.env.example` gepinnten Kern-Image. Es prüft Health, erlaubte und
gesperrte Routen, den Transport-Riegel für die Kopplung (HTTP direkt: 401;
HTTPS mit leerem Eingabeobjekt: 400 nach dem Transport-Riegel), die tatsächliche
Netz-Namensraumteilung, Docker-Portbindungen, die Unerreichbarkeit des
Admin-Ports über die eigene LAN-Schnittstelle und den Fingerprint aus dem
Zertifikats-Volume gegen das tatsächlich empfangene DER-Zertifikat. Das gesamte
Einrichtungsskript läuft zweimal gegen ein vorbereitetes, geprüftes Profil:
`.env`, beide gefüllten Secret-Dateien und Fingerprint bleiben gleich. Danach muss ein Caddy-Neustart ebenfalls
denselben Pin liefern; nur `-NeuesZertifikat` muss ihn ändern. Die Host-SANs
werden mit dem erzeugten Zertifikat verglichen. In `finally` folgt immer
`docker compose down -v --remove-orphans` nur für das eigene Zufallsprojekt.
Keine Kern-Logs ausgeben: Sie können den initialen Master-Schlüssel enthalten.

`mutations.py` entfernt jeweils eine Sperre in einer isolierten Profilkopie.
Die zugehörige Negativprüfung muss mit einer Assertion rot werden; ein
Adapterfehler zählt nicht. Die Summen der Mutantenkopie werden dabei erneuert,
damit kein zufälliger Summenfehler die eigentliche Probe verdeckt. Geprüft
werden LAN-Pfadfilter, Caddy-Admin-Socket, statisches Leaf, Zertifikatserhalt,
`CA:FALSE`, Loopback-Upstream,
Admin-Portbindung, Netz-Namensraum, Pflicht-Image und -Digest, Beisteller-Digest,
Download-Summen, Summenformat/Dateinamen/Duplikate/Vollständigkeit,
Image-Eingaben, vorhandenes Ziel und W6. Dazu kommen B1-Mutationen für ein
Klartext-SMTP-Passwort und Graph-Client-Secret im Container-Env, überschreibbare
SMTP-Secret-Pfad/Admin-URL, überschriebene oder fehlende Secret-Dateien und aufgehobenen
Git-Ausschluss. Je eine Mutation reicht den Graph-Zertifikat- bzw. Schlüsselpfad
durch und muss die zugehörige Negativprüfung rot machen.
Die frühere feste Graph-Secret-Dateipfad-Zeile macht die reine SMTP-Prüfung rot;
ein dauerhaft leerer Graph-Dateipfad macht die Prüfung des gesetzten Werts rot.

Die W6-Mutation startet absichtlich einen echten Guard im Testcontainer-Verbund
mit dem originalen Seccomp-Profil von `script-runner-v0.3.1`. Es wird über HTTPS
geladen und vor Nutzung gegen den festgehaltenen SHA-256 geprüft. Erst die
echte lokale Skriptausführung macht die bisherige Abweisungsprüfung rot. Die
ausgelieferte Compose bekommt dadurch keine Sandbox. Sämtliche ursprünglichen
Dateien werden danach zusätzlich bytegenau verglichen.

Container/Volumes haben zufällige Testnamen und werden aufgeräumt. Die Proben
verändern keine Host-Firewall, keinen Windows-Zertifikatsspeicher und keine
bestehende Anlage. Den Firewallzugriff von einem zweiten Gerät innerhalb und
außerhalb des lokalen Subnetzes muss der Betreiber separat prüfen. Ein
vollständiges Desktop-Pairing und ein produktiver Desktop-Auftrag sind weitere
Abnahmeschritte; die leere Kopplungsanfrage im Rundlauf ist kein solcher Beleg.
