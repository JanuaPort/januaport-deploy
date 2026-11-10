# Prüfungen für das Windows-Profil (Paket A und B1–B4)

Vom Repo-Root unter Windows: Python-Standardbibliothek, Windows PowerShell 5.1
und Docker Desktop (Linux/amd64). Kein Python-Paket und kein PowerShell-Modul
muss installiert werden. Die beiden Image-Digests der Beisteller werden aus
dem echten `docker compose config` gelesen. Fehlendes Docker ist ein Fehler.

```powershell
python -B -m unittest discover -s windows/test -v
python -B windows/test/live.py
python -B windows/test/mutations.py
python -B windows/test/dienst_mutations.py
python -B windows/test/b4_mutations.py
python -B windows/test/f4_mutations.py
```

B2/B3 nur in einer **nicht erhöhten** Testsitzung ausführen. Für die neuen
Skripte werden weder Konto, Autologon, Energieoptionen noch Aufgaben oder echte
Docker-Desktop-Einstellungen geändert. `dienst_fakes.ps1` ersetzt die
Systemadapter; `test_install.py` führt die echte PS-5.1-Steuerung aus. Ein
Kanarienwert prüft stdout/stderr einschließlich eines echten `.cmd`-Kindprozesses,
der seine Argumente ausgibt und mit Fehler endet. Der echte Windows-Token muss
an der Admin-Sperre scheitern. Nur in einem temporären Testordner werden echte
Datei-ACLs gesetzt und geprüft; die Registry-Adapter bleiben Fakes. Die echten
JSON-Dateiadapter prüfen AutoStart, TCP 2375, `autoDownloadUpdates`,
`disableUpdate` und `silentModulesUpdate` ohne Schreibzugriff.

`test_backup.py` startet den echten PS-5.1-Einstieg `Start-JnptBackup` mit einem
Docker-Shim auf `PATH`. Der Shim implementiert ausschließlich
`exec -T jnpt /jnpt backup --output /backups/<name>`; alle anderen Programme
werden wie beim distroless-Image abgewiesen. Backup-Dateien, Host-Kopie,
`.teil`, Umbenennen und Hash-Rücklesen sind echte
Dateioperationen im temporären Ordner. Fehlender Marker, falsches Konto,
relatives Ziel mit vorhandenem Marker, unvollständiges Profil, jeder native
Docker-Fehler, leere/fehlende Staging-Datei, Größen-/Hashfehler, Fehler nach Umbenennung
und Host-Aufräumfehler müssen Exit ungleich 0 und keine neue Zieldatei
liefern. Alte Sicherungen bleiben erhalten. Bei Erfolg gibt es genau eine
Sicherungsdatei und keine Key-Datei; die Staging-Kopie ist entfernt.
Liegengebliebene Dateien nach dem exakten Namensmuster werden entfernt; fremde
Dateien und Pfade außerhalb von `backups\` bleiben erhalten. Der native
Docker-Adapter weist `stat`, `sha256sum`, `rm` und `sh` vor dem Aufruf ab.
Beide Installer müssen `backups\` anlegen. Compose wird mit dem echten Adapter
auf den relativen Bind-Mount und den Git-Ausschluss geprüft.

Der zusätzliche Live-Test ist bewusst außerhalb der Standardsuite:
`python -B windows/test/backup_live.py`. Er startet nur den echten gepinnten
Kern aus der Compose-Konfiguration in einem eigenen zufälligen Projekt ohne
Netzzugang oder veröffentlichte Ports und führt das echte Backup-Skript aus
(nur Kontoidentität ersetzt). Host-Quellhash und Zielhash stimmen überein,
genau eine Sicherung und keine Key-Datei liegen am Ziel, Staging ist leer.
Seccomp errno 524 wird als blockierter Live-Test markiert, den BOX in B4
ausführen muss; andere Fehler bleiben Fehler. Kern-Logs werden nicht ausgegeben.

Die Windows-Adapterprüfungen (F4 enthält auch `docker compose config`):

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_install test_backup -v
python -B windows/test/dienst_mutations.py
```

`dienst_mutations.py` verwendet isolierte Profilkopien und verlangt echte
Assertion-Fehler. Unter anderem werden Hash-Pin bei gültiger Signatur,
Microsoft-Herausgeber, Admin-/Kontosperren, bestehende Dateien, Docker-Einstellungen,
Kennwort-Ausgabesperre, cmdkey-Verbot, ACLs und Sperrbildschirmrichtlinien entfernt.
Die B-4-Mutation kopiert zusätzlich eine synthetische Key-Datei aus dem
Staging ins Ziel: die Erfolgsprüfung muss rot werden. F4-Mutationen erlauben
`stat` im nativen Container-Adapter, entfernen den Löschwächter, versuchen
fremde Dateien zu löschen oder lassen alte/neue Sicherungsdateien im Staging.
Weitere Mutationen entfernen Exit ungleich 0, Marker-, Größen- und Hashprüfung,
Rücklesen nach Umbenennung und beide Aufräumwege. Originale werden bytegenau
verglichen. Mutationen und Standardsuite nacheinander ausführen; die
Originalprüfung darf keine parallel angelegten temporären Testdateien sehen.

Die `Autologon64.exe`-Zeile in `SHA256SUMS` ist ein externer Pin, keine Datei im
Repo oder Profil-Download. Die echte Binärprüfung lädt ausschließlich die feste
Sysinternals-URL und prüft Hash vor Authenticode. Die Tests nutzen ein lokales
ZIP-Fixture und eine gültige Fake-Signatur, führen niemals das echte Binary aus.
Der externe Pin wird von Manifestprüfungen separat von den Profilbytes geprüft.
Der Live-Rundlauf ersetzt ausschließlich die Kontoidentität; alle Container und
Volumes darin bleiben wie bisher temporäre Testobjekte. Kein Dienstskript wird
auf diesem Rechner mit echten Systemadaptern ausgeführt.

`test_upgrade.py` liest die drei Originaldateien aus dem lokalen Git-Tag
`windows-v0.1.0` (Git und dieses Tag sind Voraussetzung; das alte Skript wird
nicht ausgeführt). Der echte PS-5.1-Installer aktualisiert den temporären Ordner
mit und ohne alte Summenliste, erhält `.env` sowie alle Secret-Inhalte und lädt
beim zweiten Lauf nichts nach. Download/HTTP und Docker sind Fakes; Datei- und
Summenadapter sind echt. Download- und Hashfehler dürfen vor der ersten
Ersetzung keine vorhandene Datei ändern. Geänderte/unvollständige Altprofile
werden vor dem Download abgewiesen. Die lokale Bereitstellung über B2 wird
ebenfalls geprüft. Ein Test hält `$ProfileRef` auf `windows-v0.2.0` fest.

B-7 prüft den exakten `icacls`-Aufruf am festen Elternordner mit
`/inheritance:r` und ausschließlich den SIDs von `jnpt-dienst`, Administratoren
und SYSTEM. Im Fake wird an `C:\JanuaPort` nichts angelegt. Zusätzlich erhält
ein echter temporärer Eltern-/Kindordner absichtlich breite Rechte für
Authentifizierte Benutzer; der echte `icacls`-Adapter muss diese entfernen.
Aufrufreihenfolge und native Fehler werden geprüft. Die Mutation ohne
`/inheritance:r` muss sowohl die Argumentprüfung als auch den echten ACL-Test
rot machen; weitere Mutationen entfernen die Elternordnersperre, das Entfernen
alter expliziter Rechte, die Upgrade-Summenprüfung oder den Erhalt von `.env`
und Secrets. Diese Proben sind in `dienst_mutations.py` enthalten.

`test_b4.py` prüft den sofortigen Anmeldeauslöser ohne festen Delay und den
festen Aufruf von `C:\JanuaPort\windows\jnpt-sperren.ps1`. Der echte PS-5.1-
Einstieg läuft mit verwaltetem Ersatz für user32/WTS und virtuellem Sekundentakt.
Nur Explorer derselben Sitzung zählt; Bereitschaft und Sperre teilen sich ein
120-Sekunden-Limit. Erste/dritte bestätigte Sperre, nie gesperrte Sitzung und
später Explorer werden geprüft. Das echte Dateiadapter-Protokoll enthält genau
eine Zeile (ISO-Start, ISO-Sperre oder `nicht_gesperrt`, Versuche, Exit), ohne
Benutzernamen; maximal 100 Zeilen. Ein Schreibfehler ergibt Exit ungleich 0.
Die Einrichtung muss den B-7-geschützten Logordner vor der Aufgabe anlegen.
Der C#-WTS-Decoder läuft mit ausschließlich ersetzten P/Invoke-Deklarationen:
aktuelle Sitzung, Klasse 26, LOCK/UNLOCK/UNKNOWN, kurze/falsche/fehlgeschlagene
Antwort und Speicherfreigabe. Keine echte native Sperre oder WTS-Abfrage.
Autologon nutzt einen lokalen `.cmd`-Ersatz und virtuellen Takt (Bestätigung
nach 2 Sekunden oder Fehler nach 10 Sekunden). Beide JSON-Dateivarianten und
die feste Meldung bei fehlenden Docker-Einstellungen verwenden echte Dateien.

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_b4 -v
python -B windows/test/b4_mutations.py
```

Die 15 SEC-Mutationen führen Delay, zu langsamen Takt, ersten Abbruch,
fehlende/personenbezogene/unbegrenzte Protokollierung, fehlende Sperrprüfung,
fremde Sitzung, falschen Erfolgs-Exit und unerlaubte Fehlerausgabe ein.
Außerdem werden Autologon-Nachfragen und die feste N2-Meldung entfernt.
Abmelden/Herunterfahren werden an protokollierenden Fehlerfallen tatsächlich
versucht. Jede isolierte Kopie muss an einer Assertion scheitern; die
Originalbytes bleiben erhalten.

`test_operator_docs.py` führt die gepinnten N4-Hilfscontainer-Befehle aus den
READMEs gegen ein eigenes zufälliges Test-Volume und synthetische Key-Dateien
aus: bisherige DB/Key-Dateien bleiben beiseitegelegt erhalten, der neue Key
ist als UID 65532 mit Modus 600 lesbar. `operator_mutations.py` muss Löschen
statt Verschieben sowie falschen Eigentümer und Modus am echten Adapter erkennen.
N5 führt die drei Dokumentationsrezepte in PS 5.1 mit einem aufzeichnenden
Firewall-Adapter aus: Netzprofil zuerst, TCP 443 eingehend, `LocalSubnet`,
Profile `Private,Domain`. Die echte Firewall wird nicht verändert. Der echte
Installer läuft mit Fehlerfallen an allen Firewall-/Netzprofil-Schreibadaptern.
Weitere Mutationen ersetzen `LocalSubnet` durch `Any`, erlauben öffentliche
Profile, entfernen die Profilprüfung oder bauen eine automatische Regel ein.

```powershell
python -B windows/test/operator_mutations.py
```

Die manuelle B4-Abnahme steht in [PRUEFSTEIN-B4.md](../PRUEFSTEIN-B4.md):
DPAPI-unabhängige Wiederherstellung nach Kennwortreset, Sperrbildschirmfoto nach
Neustart, Engine-/Volume-Vergleich je Benutzer und Rücksicherung mit getrenntem
Master-Key. Das ist kein Ergebnis der Fakes und bleibt auf dem Testrechner offen.

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
