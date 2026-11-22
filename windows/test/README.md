# Prüfungen für das Windows-Profil (Paket A und B1–B5)

## Auswahl ohne laufende Container (#1512, auch CI)

```powershell
python -B windows/test/run_fake_tests.py
$env:PYTHONPATH = 'windows/test'
python -B -c "from test_profile import ROOT, verify_sums; verify_sums(ROOT)"
python -B windows/test/rest_mutations.py
python -B windows/test/mutations.py --fakes
python -B windows/test/operator_mutations.py --fakes
```

Diese Auswahl führt die PS-5.1-Adapter mit Fakes, echten TEMP-Dateien,
nativen Docker-Shims und `docker compose config` aus. Keine Docker-Engine,
kein Docker Desktop, keine GUI, Dienste oder echten Downloads nötig.
Die fünf vorhandenen Linux-Container-Integrationstests (Mail-Mount, TLS-Leaf,
Caddy-Container, N4-Helfer, Skript-Läufer) gehören weiter zur vollständigen
Adapterauswahl unten. Die vier NTFS-VM-Prüfungen bleiben ohne `JNPT_OWNER_VM`
übersprungen; der native Caddy-HTTPS-Test bleibt ohne `JNPT_CADDY_EXE` ebenfalls
sichtbar übersprungen. Die echte Admin-Sperre wird mit einem eingeschränkten
Duplikat des Windows-Tokens geprüft, auch auf dem erhöhten GitHub-Runner;
keine Kontoanlage oder Änderung am Prozess-/Benutzertoken.
`windows-tests.yml` nutzt diese Auswahl und prüft SHA256SUMS separat.

`test_rest.py` prüft den expliziten lokalen Autologon-Dateiweg (Signatur,
Microsoft-Herausgeber, fehlende Datei, Hashprotokoll, Parameterdurchleitung,
Download-Pin-Hinweis), die tatsächlich aufgelösten privaten Plugin-Netze samt
Bestandsdefaults und ungültigen Kombinationen, den laufenden Image-Digest vor
`installed` samt 30-Sekunden-Abfragen sowie die 30-Tage-Aufbewahrung am echten
Fake-Ziel. Abgewiesene Inspect-Aufrufe erreichen den nativen Shim nicht.
Aufbewahrungstests bieten überfällige fremde Dateien und die jüngste eigene
Sicherung wirklich zum Löschen an; beide müssen erhalten bleiben.
Reparse-Metadaten werden am Leseübergang ersetzt (lokal fehlt das
Symlink-Privileg); der Löschversuch gegen die fremde TEMP-Datei verwendet den
echten `Remove-Item`-Adapter. Ungültige IPv4-/CIDR-Werte und mehrere Pools
werden zusätzlich direkt an der produktiven Netzprüfung angeboten.
`rest_mutations.py` entfernt die Sperren in isolierten Profilkopien; Assertions
müssen rot werden. Originalbytes und Summen bleiben unverändert.
`--fakes` lässt in den beiden älteren Mutationsskripten die ausdrücklich als
`NOT RUN` gemeldeten Linux-Engine-/Live-/Download-Fälle aus. Es ersetzt deren
vollständige Mutationsabnahme nicht; ohne Schalter bleibt sie unverändert.

Vom Repo-Root unter Windows: Python-Standardbibliothek, Windows PowerShell 5.1
und Docker Desktop (Linux/amd64). Kein Python-Paket und kein PowerShell-Modul
muss installiert werden. Die beiden Image-Digests der Beisteller werden aus
dem echten `docker compose config` gelesen. Fehlendes Docker ist ein Fehler.

`go test ./...` überspringt unter Windows gezielt Linux-GPG-/Shell-/POSIX-Adapter
und ihre Mutationen mit `runtime.GOOS == "windows"`; HCL-, Drift- und Doku-Tests
bleiben aktiv. Vollständiger Linux-Lauf: Testcontainer aus `hetzner/audit-test.Dockerfile`.

```powershell
python -B -m unittest discover -s windows/test -v
python -B windows/test/live.py
python -B windows/test/mutations.py
python -B windows/test/dienst_mutations.py
python -B windows/test/b4_mutations.py
python -B windows/test/f4_mutations.py
python -B windows/test/sec_r4_mutations.py
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
liefern. Fremde alte Sicherungen bleiben erhalten. Nach geprüftem Erfolg gilt
am Ziel 30 Tage Aufbewahrung (`-RetentionDays`); die jüngste eigene Sicherung
bleibt erhalten. Bei Erfolg gibt es genau eine neue
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
Repo oder Profil-Download. Der Standardweg lädt ausschließlich die feste
Sysinternals-URL und prüft Hash vor Authenticode; `-AutologonPfad` prüft die
explizite Betreiberdatei mit Authenticode und protokolliert ihren Hash.
Die Tests nutzen ein lokales
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
ebenfalls geprüft. Ein Test hält `$ProfileRef` auf `windows-v0.3.0` fest.

B-7/F5 prueft die vollstaendige geschuetzte DirectorySecurity mit genau drei
expliziten FullControl-Regeln (ContainerInherit, ObjectInherit, Propagation None,
Allow) fuer Dienst-SID, Administratoren und SYSTEM. Der Fake ersetzt nur die
nativen Directory-Lese-/Schreibgrenzen; die echten Security-Descriptor-Klassen
und der produktive Kontrollfluss bleiben erhalten. Der erste Lauf schreibt
einmal; jeder weitere Lauf schreibt erneut den erzwungenen BA-Besitzer. Fast passende DACLs mit vierter
Regel, fehlendem Schutz, anderen Rechten, Vererbungs-/Propagationsflags oder
Deny werden ersetzt. Native Schreibfehler muessen abbrechen.
R4 prueft jede Abweichung einzeln: zusaetzliches Users-Read-ACE,
fehlendes OI bzw. CI, fehlende SID, geringere Rechte, InheritOnly,
NoPropagate, fehlender Schutz, Deny sowie zusaetzliche geerbte ACEs.
Auch die binaere DACL wird geprueft: GetAccessRules kann opaque ACEs
auslassen oder Callback-ACEs als Allow darstellen. Beide Faelle muessen
neu geschrieben werden; gueltig sind nur genau drei gewoehnliche Allow-ACEs.

`test_acl_f5.py` enthaelt einen AST-Waechter gegen zwei Schreibschritte oder
alte Clear-/icacls-Adapter. Auf echtem NTFS unter dem Testordner werden nach
der ersten Absicherung erbende `.env`-, Secret- und Logdateien angelegt und
anschliessend manuell ein erbendes Users-Read-ACE hinzugefuegt und dann
Eltern-/Profilordner erneut geschuetzt: Das Users-ACE verschwindet,
Inhalt bleibt lesbar, alle Dateien tragen BA als Besitzer und die drei geerbten
ACEs. Diese NTFS-Besitzwechseltests laufen nur mit `JNPT_OWNER_VM=1` auf einer
eigens vorgesehenen Test-VM, niemals auf dem Entwicklungsrechner. Der zusätzliche
Test `test_audit_owner` prüft lokal mit echten Security-Deskriptoren den
BA-Besitzer auch bei passender DACL und die Dateivererbung; native Schreibgrenzen
sind ersetzt. Baumdurchlauf und Junction-Abweisung nutzen echte TEMP-Dateien.
Für den echten Fremdkonto-Test auf der VM sind zusätzlich `JNPT_FOREIGN_USER`
und `JNPT_FOREIGN_PASSWORD` eines vorhandenen Standard-Testkontos erforderlich.
Er erstellt unter dessen Token Ordner und Datei, prüft den fremden Vorbesitzer,
erzwingt BA und versucht `icacls /grant` erneut unter dem fremden Token:
beide Freigaben müssen scheitern. Keine Konten oder Dienste werden angelegt.
Für die Mutationsprobe auf derselben VM muss SetOwner für Ordner und Dateien
entfernt werden; der Fremdkonto-Test muss rot sein. Lokal bleibt dieser Nachweis offen.

**SEC H1:** `python -B -m unittest test_hardlinks -v` erstellt echte Hardlinks
unter TEMP und liest `nNumberOfLinks` über den produktiven Win32-Adapter ohne
Adminrechte. Nur ACL-Schreibgrenzen sind ersetzt. Der Negativfall muss den ganzen
Baum vor dem ersten Ordner- oder Datei-ACL-Schreiben abweisen; die außenliegende
Datei behält Inhalt und SDDL. Ein fehlender Pfad muss beim Metadatenlesen scheitern.
`python -B windows/test/h1_mutations.py` entfernt die Hardlink-Sperre in einer
Wegwerfkopie und verlangt einen Assertion-Fehler. Diese lokale H1-Prüfung ersetzt
die weiterhin offene #1498-Fremdbesitzer-Abnahme auf der Test-VM nicht; vor neuem
`windows-v*`-Tag müssen sie und die echte Docker-Desktop-Abnahme für #1499 grün sein.

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_acl_f5 test_upgrade.ParentAcl -v
python -B windows/test/f5_mutations.py
```

Die sechs F5-Mutationen entfernen den Schutz, ergaenzen eine vierte Regel,
schreiben erst eine leere DACL und dann die Ziel-DACL, entfernen SetOwner,
erhalten alte explizite Freigaben oder ignorieren einen Schreibfehler. Sie
sind auch in `dienst_mutations.py` integriert. Die manuelle Reparatur im
RUNBOOK wird nur als Anleitung geprueft; takeown und icacls /reset werden
im Test nicht ausgefuehrt.

`sec_r4_mutations.py` ersetzt "genau drei" durch "enthaelt die drei": Der
Users-Read-Negativfall muss rot werden. Eine zweite Mutation akzeptiert ein
Callback-ACE als gewoehnliches Allow. Drei weitere entfernen aus den echten
N5-1-Dokumentationsrezepten den Docker-Anwendungsfilter, Any-Port oder
Portbereiche. Alle fuenf muessen an Assertions scheitern; die Originalbytes
bleiben erhalten.

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
`test_sec_r4_docs.py` fuehrt die N5-1-Abnahmezeilen aus RUNBOOK und B4 mit
PS-5.1-Firewall-Fakes aus: Docker-Regeln auch auf anderen Ports sowie
443 als Einzelport, Liste, Bereich oder Any muessen sichtbar werden;
unbeteiligte Regeln bleiben herausgefiltert. Kein echter Firewall-Zugriff.
Die SEC-Texte zu Ruecksicherung, unbeantwortetem Docker-Dialog und
Konsolenschutz werden in allen geforderten Dokumenten geprueft.
Beide READMEs nennen das in B4 gemessene Restfenster (hoechstens rund 7 s sichtbar, Sperre 12,6 s nach Start); ein Platzhalter ist nicht mehr erlaubt. Die Firewall-Pruefzeile (N5-1/N8) zeigt nur Docker-Regeln und TCP-443-Regeln mit Programm Any ohne App-Paket.

```powershell
python -B windows/test/operator_mutations.py
```

Die manuelle B4-Abnahme steht in [PRUEFSTEIN-B4.md](../PRUEFSTEIN-B4.md):
DPAPI-unabhängige Wiederherstellung nach Kennwortreset, Sperrbildschirmfoto nach
Neustart und Rücksicherung mit getrenntem Master-Key. Die Engine-Frage wurde
in B5 auf VM `jnpt-b4` geklärt: eine gemeinsame Engine, keine technische
Kontentrennung. Das Wartungskonto startet nur Aufgaben; diese Betriebsregel
wird von den Fakes nicht als technische Zugriffssperre belegt.

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


## B5: Update und Profil 0.3.0

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_update test_upgrade.Upgrade -v
python -B -m unittest discover -s windows/test -v
```

`test_update.py` enthält die elf Auftragsfälle: `none`, `approved`,
`unattended`, ungültige Digests/JSON-Zeilen, Sicherungs-/Pullfehler, rote
Health/TLS/Start-/Digest-Prüfung, nicht buchbare Ergebnisse, `rollback`, Sitzung/Profil,
natives stderr/Docker noch nicht bereit sowie den kommentarlosen Wächter gegen
eigene Kernentscheidungen. PS 5.1 läuft wirklich; `docker.cmd` auf PATH zeichnet
die Argumente auf. Die Reihenfolge wird über Protokoll-Indizes geprüft. Das
Backup läuft in einem echten separaten PowerShell-Prozess mit einem synthetischen
Backup-Skript. Das ist kein Nachweis einer echten Sicherung; diese bleibt B3/B4
und BOX vorbehalten. Host-HTTP und TLS-Gegenstelle sind Adapter-Fakes, die
503 und abweichenden Fingerprint tatsächlich liefern. Die Gesundheit wird nicht
im Container geprüft. Die vorhandene Live-Prüfung belegt den echten
Fingerprint-Adapter gegen Caddy; B5 im Betriebsmodell bleibt BOX-Aufgabe.

Dateiaustausch, UTF-8-Bytes ohne BOM, erhaltene Kommentar-/Mail-Zeilen,
`icacls` vor/nach dem Austausch, Logdatei und Kindprozess-Zeitlimit sind echte
Windows-Adapter. Die Testordner liegen kurz unter dem System-Temp-Pfad.
Zusätzliche Adapterfälle versuchen `sh`, `stat`, `compose cp`, Restore,
Health im Container, `update rollback` und einen Pull aus einem fremden
Repository direkt am produktiven Docker-Adapter: Abweisung vor dem nativen
Aufruf. Doppelte Image-Zeilen werden vor dem Austausch abgewiesen.
Der Logtest bietet den aktuellen Benutzernamen und einen Zeilenumbruch
wirklich an und verlangt Redaktion bzw. Escaping. 105 vorgegebene Logzeilen
müssen nach einem Lauf auf höchstens 100 begrenzt sein. Der Prozessadapter
muss einen echten schlafenden Kindprozess am Zeitlimit beenden.

**#1499:** Drei echte Docker-Shim-Prozesse schlafen jeweils 32 Sekunden:
Pull/Start-Erfolg werden erst nach Prozessende als `installed` gebucht;
ein tatsächlicher Startfehler wird danach als `failed` gebucht. Ein weiterer
Test startet einen nativen Python-Nachfahren, belegt dessen Start und verlangt,
dass er nach Ablauf der Frist keine Abschlussdatei mehr schreiben kann.
Die Mutanten mit pauschalen 30 Sekunden und ohne `taskkill /T` müssen rot sein.
Die Fristauswahl am echten `Invoke-UpdateDocker`-Adapter mit ersetzter Prozessgrenze
verlangt für genau die OpenSSL-Zertifikatsabfrage 300 Sekunden (BOX: gemessen
37–48 Sekunden bei schlechter Leitung), für Plan/Ergebnisbuchung weiter 30 und
für Pull/Start 0 (ohne Frist). `pruefstein_mutations.py` setzt die Konstante auf
30 zurück und verlangt einen Assertion-Fehler.

**#1503:** Das Ticket erlaubt, den nicht unterstützten MCP-Schalter zu entfernen.
`test_audit_caddy` hält diese Variante fest und versucht am echten Hashadapter
eine manuelle MCP-Route. Der native HTTPS-Test startet ausschließlich einen
temporären Caddy-Prozess und synthetischen Upstream auf Loopback, ohne Dienst,
Container oder Truststore-Installation. Mit `JNPT_CADDY_EXE` auf ein vorhandenes
Caddy-Binary werden MCP und fremde Routen per GET/POST tatsächlich versucht
und müssen 404 liefern; ohne Binary wird dieser Test ausdrücklich übersprungen.
`audit_mutations.py` öffnet die Route und entfernt separat den Hashwächter;
beide Negativtests müssen rot werden. Die regulären Installer- und Upgrade-Tests
prüfen weiterhin alle Wartungswege mit unveränderter Caddyfile.

```powershell
$env:PYTHONPATH = 'windows/test'
$env:JNPT_CADDY_EXE = 'C:\Pfad\caddy.exe'
python -B -m unittest test_audit_owner test_audit_caddy test_update -v
python -B windows/test/audit_mutations.py
```

Lokal bleiben `JNPT_OWNER_VM` und die Fremdkonto-Variablen ungesetzt. Nur auf
der separaten NTFS-Test-VM wird der Fremdkonto-Test in einer administrativen
Testsitzung mit `JNPT_OWNER_VM=1` ausgeführt; die lokalen B2/B3-Tests laufen
weiterhin ohne Erhöhung. Das Mutationsskript nimmt dort automatisch auch den
echten Fremdkonto-Test ohne beide SetOwner-Aufrufe hinzu.

Die sieben Pflichtmutationen werden einzeln in isolierten Kopien ausgeführt
und nicht als veränderter Produktcode committed: Versionsvergleich einfügen,
`-cmatch` durch `-match` ersetzen, `\z` durch `$` ersetzen, Backup-Exit ignorieren,
Image aus `latest` bauen, `record installed` entfernen, `update rollback`
einfügen. Jede Probe muss an einer Assertion rot werden; Adapterfehler zählen
nicht. Weitere Proben entfernen jeweils native Sperre, Sitzungs-/Profilprüfung,
JSON-Zeilenprüfung, Eindeutigkeit der `.env`-Zeilen, Zeitlimit, Logbegrenzung,
Redaktion oder Ausgabeschutz. Originalbytes werden danach verglichen.
Die Ergebnisse gehören in den Arbeitsbericht; Mutanten werden nicht ausgeliefert.

`test_profile.py` prüft beide Feed-Werte über den echten Compose-Adapter aus
Prozessumgebung und `.env`, gesetzt/leer/fehlend und nur beim Dienst `jnpt`.
`test_install.py` prüft die Update-Aufgabe über die vorhandenen System-Fakes:
Interactive/Limited als `jnpt-dienst`, IgnoreNew, kein Auslöser, `EncodedCommand`
mit USB-Wurzel, Apostroph und SMB-Ziel. Beide Dateilisten und Summen enthalten
Update-Skript und B5-Prüfstein. `test_upgrade.py` liest zusätzlich die elf
veröffentlichten 0.2.0-Dateien aus dem lokalen Tag und führt 0.2.0 → 0.3.0 durch
beide Installer mit echten Datei-/Hashadaptern aus. `.env` und Secret-Inhalte
bleiben erhalten, der zweite Lauf lädt nichts. Zusätzlich erzeugt der Test den
exakten v0.3.0-Baum aus `git show windows-v0.3.0:windows/<Datei>`: Alle 13
Profil-Dateien werden durch beide Installer ersetzt. Die separat heruntergeladene
`Autologon64.exe` ist kein ProfileFile; Erfolg wird ohne und mit einer synthetischen
EXE geprüft (sie wird nie ausgeführt). Ein geändertes Byte in jeder der elf v0.2.0-
und 13 v0.3.0-Dateien sperrt beide Wege an echten Datei-/Hashadaptern.
Fehlende Altdateien sperren ebenfalls den Download. Der 0.1.0-Weg bleibt geprüft.
`ProfileSourceDrift` zählt mit `git tag -l 'windows-v*'` alle lokalen Tags auf und
prüft ihre Upgrade-Erkennung. Nur der neueste Tag darf fehlen, solange HEAD exakt
dessen Profilbytes und Manifest trägt. Ohne Git oder Tags wird mit klarer
Begründung übersprungen. `pruefstein_mutations.py` entfernt den v0.3.0-Eintrag
(Upgrade und Drift müssen rot sein) und die Hashsperre an beiden Installationswegen.
Eine passend gefälschte lokale Summenliste darf `Test-LegacyProfile` keine Quelle
hinzufügen; auch das wird am echten Hashadapter und per Mutation geprüft.

```powershell
$env:PYTHONPATH = 'windows/test'
python -B -m unittest test_update test_upgrade -v
python -B windows/test/pruefstein_mutations.py
```

[Prüfstein B5](../PRUEFSTEIN-B5.md) ist durch BOX auf VM `jnpt-b4` @`a87f571`
grün (Protokoll `c-6796028725`, #1246): Feed-Freigabe und GUI-Buchung, TaskResult,
USB-Sicherung, gemeinsame Engine, Rechtegleichheit, Exit 3/6, manueller Rückweg
und früher Anstoß nach Neustart. Der Hersteller-Feed oder ein öffentlich
erreichbarer Test-Feed ist nötig; private Ziele sperrt der Kern per SSRF-Schutz.
Das Wartungskonto ruft nach Betriebsregel kein `docker` auf. Die Standardsuite
belegt diese Windows-Betriebsabnahme nicht selbst.
