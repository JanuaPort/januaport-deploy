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
Docker-Shim auf `PATH`. Der Shim implementiert `exec`, `stat`, `sha256sum`, `cp`
und `rm`. Backup-Dateien, `.teil`, Umbenennen und Hash-Rücklesen sind echte
Dateioperationen im temporären Ordner. Fehlender Marker, falsches Konto,
relatives Ziel mit vorhandenem Marker, unvollständiges Profil, jeder native
Docker-Fehler, ungültige Metadaten, Größen-/Hashfehler, Fehler nach Umbenennung
und Container-Aufräumfehler müssen Exit ungleich 0 und keine neue Zieldatei
liefern. Alte Sicherungen bleiben erhalten. Bei Erfolg gibt es genau eine
Sicherungsdatei und keine Key-Datei; die Container-Kopie ist entfernt.

Nur die neuen Prüfungen ohne laufenden Docker-Daemon:

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_install test_backup -v
python -B windows/test/dienst_mutations.py
```

`dienst_mutations.py` verwendet isolierte Profilkopien und verlangt echte
Assertion-Fehler. Unter anderem werden Hash-Pin bei gültiger Signatur,
Microsoft-Herausgeber, Admin-/Kontosperren, bestehende Dateien, Docker-Einstellungen,
Kennwort-Ausgabesperre, cmdkey-Verbot, ACLs und Sperrbildschirmrichtlinien entfernt.
Die B-4-Mutation kopiert zusätzlich ganz `/data`: der Shim legt dabei tatsächlich
eine synthetische Key-Datei am Ziel ab, die Erfolgsprüfung muss rot werden.
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

`test_b4.py` pr�ft den sofortigen Anmeldeausl�ser ohne festen Delay und den
festen Aufruf von `C:\JanuaPort\windows\jnpt-sperren.ps1`. Der echte PS-5.1-
Einstieg l�uft mit verwaltetem Ersatz f�r user32/WTS und virtuellem Sekundentakt.
Nur Explorer derselben Sitzung z�hlt; Bereitschaft und Sperre teilen sich ein
120-Sekunden-Limit. Erste/dritte best�tigte Sperre, nie gesperrte Sitzung und
sp�ter Explorer werden gepr�ft. Das echte Dateiadapter-Protokoll enth�lt genau
eine Zeile (ISO-Start, ISO-Sperre oder `nicht_gesperrt`, Versuche, Exit), ohne
Benutzernamen; maximal 100 Zeilen. Ein Schreibfehler ergibt Exit ungleich 0.
Die Einrichtung muss den B-7-gesch�tzten Logordner vor der Aufgabe anlegen.
Der C#-WTS-Decoder l�uft mit ausschlie�lich ersetzten P/Invoke-Deklarationen:
aktuelle Sitzung, Klasse 26, LOCK/UNLOCK/UNKNOWN, kurze/falsche/fehlgeschlagene
Antwort und Speicherfreigabe. Keine echte native Sperre oder WTS-Abfrage.
Autologon nutzt einen lokalen `.cmd`-Ersatz und virtuellen Takt (Best�tigung
nach 2 Sekunden oder Fehler nach 10 Sekunden). Beide JSON-Dateivarianten und
die feste Meldung bei fehlenden Docker-Einstellungen verwenden echte Dateien.

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_b4 -v
python -B windows/test/b4_mutations.py
```

Die 15 SEC-Mutationen f�hren Delay, zu langsamen Takt, ersten Abbruch,
fehlende/personenbezogene/unbegrenzte Protokollierung, fehlende Sperrpr�fung,
fremde Sitzung, falschen Erfolgs-Exit und unerlaubte Fehlerausgabe ein.
Au�erdem werden Autologon-Nachfragen und die feste N2-Meldung entfernt.
Abmelden/Herunterfahren werden an protokollierenden Fehlerfallen tats�chlich
versucht. Jede isolierte Kopie muss an einer Assertion scheitern; die
Originalbytes bleiben erhalten.

`test_operator_docs.py` f�hrt die gepinnten N4-Hilfscontainer-Befehle aus den
READMEs gegen ein eigenes zuf�lliges Test-Volume und synthetische Key-Dateien
aus: bisherige DB/Key-Dateien bleiben beiseitegelegt erhalten, der neue Key
ist als UID 65532 mit Modus 600 lesbar. `operator_mutations.py` muss L�schen
statt Verschieben sowie falschen Eigent�mer und Modus am echten Adapter erkennen.

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
