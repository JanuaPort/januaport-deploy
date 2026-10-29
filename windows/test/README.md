# Prüfungen für Paket A

Vom Repo-Root unter Windows: Python-Standardbibliothek, Windows PowerShell 5.1
und Docker Desktop (Linux/amd64). Kein Python-Paket und kein PowerShell-Modul
muss installiert werden. Die beiden Image-Digests der Beisteller werden aus
dem echten `docker compose config` gelesen. Fehlendes Docker ist ein Fehler.

```powershell
python -B -m unittest discover -s windows/test -v
python -B windows/test/live.py
python -B windows/test/mutations.py
```

Die Standardtests prüfen Summen samt beschädigter Dateien, echte
PowerShell-Summenprüfung einschließlich Format-/Dateinamen-/Duplikat- und
Vollständigkeitssperren, Eingabe- und Zielverzeichnis-Abweisungen sowie den
Compose-Adapter. Für Caddy läuft ein echter HTTPS-Server im Netz-Namensraum
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
Admin-Ports über die eigene LAN-Schnittstelle und den PowerShell-Fingerprint
gegen das tatsächlich empfangene DER-Zertifikat. In `finally` folgt immer
`docker compose down -v --remove-orphans` nur für das eigene Zufallsprojekt.
Keine Kern-Logs ausgeben: Sie können den initialen Master-Schlüssel enthalten.

`mutations.py` entfernt jeweils eine Sperre in einer isolierten Profilkopie.
Die zugehörige Negativprüfung muss mit einer Assertion rot werden; ein
Adapterfehler zählt nicht. Die Summen der Mutantenkopie werden dabei erneuert,
damit kein zufälliger Summenfehler die eigentliche Probe verdeckt. Geprüft
werden LAN-Pfadfilter, Caddy-Admin-Socket, CA-Import, Loopback-Upstream,
Admin-Portbindung, Netz-Namensraum, Pflicht-Image und -Digest, Beisteller-Digest,
Download-Summen, Summenformat/Dateinamen/Duplikate/Vollständigkeit,
Image-Eingaben, vorhandenes Ziel und W6.

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
