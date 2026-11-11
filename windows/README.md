# Windows: Docker Compose mit TLS im LAN

[English](README.en.md) · **Deutsch**

Paket A mit B1-Mail sowie B2-Dienstbetrieb und B3-Sicherung (#1246): Windows 10/11 Pro, Docker Desktop mit WSL2 und Linux-Containern
(amd64). Gebaut und mit Docker Desktop lokal geprüft; kein Nachweis eines
unbeaufsichtigten Dauerbetriebs. Die Oberfläche bleibt am Gerät, Desktop-Läufer
im LAN und am selben Rechner sprechen HTTPS mit Zertifikatbindung.

Den Ablauf vor Ort und bei Fernwartung (wer wann was tut) beschreibt das [Runbook](RUNBOOK.md).

## Voraussetzungen

- Docker Desktop **≥ 4.44.3** (Behebung von CVE-2025-9074), laufende WSL2-Engine,
  Compose ≥ 2.35 (Volume-Subpaths) und PowerShell 5.1 oder neuer.
- Docker Desktop: **„Expose daemon on tcp://localhost:2375“ aus**. AutoStart **an**, automatische Downloads/Updates **aus**; Updates
  nur nach Prüfung freigeben; dieses Profil installiert keine Updates.
- Die TCP-Ports 443 und 8484 sind frei. Kein Router-Portforwarding für 443.
- Zugang zur öffentlichen Image-Registry und zu GitHub. Für Desktop-Pins später
  ein eigenes Skript-Repository und dessen Nur-Lese-Deploy-Key.

### LAN-Freigabe bei der Einrichtung (N5)

In B4 fand sich keine Allow-Regel für Docker. Docker Desktop hatte nur zwei
Block-Regeln für das Profil „Öffentlich“ angelegt, weil der Firewall-Dialog
unbeantwortet blieb. Was bei „Zulassen“ entsteht, ist nicht gemessen.
Den Firewall-Dialog von Docker Desktop nicht mit ‚Zulassen‘ für öffentliche Netze beantworten.
Bei jeder echten Abnahme Docker-Anwendungsfilter und alle Portfilter, die 443
öffnen, gemäß [RUNBOOK, N5-1](RUNBOOK.md) auflisten. Außer „JanuaPort 443 LAN“
darf keine Allow-Regel 443 öffnen; weitere Regeln deaktivieren oder auf
`LocalSubnet` einengen. Für Desktop-Läufer im LAN prüft der Betreiber bzw. seine IT
in einer administrativen PowerShell das Netzprofil: Es muss **Privat** oder
**Domäne** sein. Ein öffentliches Netz erst nach Prüfung durch die IT als
vertrauenswürdiges privates Netz einordnen. Dann TCP 443 ausschließlich für
`LocalSubnet` und die Profile `Private,Domain` freigeben:

<!-- N5 -->
```powershell
Get-NetConnectionProfile
New-NetFirewallRule -DisplayName 'JanuaPort 443 LAN' -Direction Inbound -Protocol TCP -LocalPort 443 -RemoteAddress LocalSubnet -Action Allow -Profile Private,Domain
```

Kein `Any` bei den Gegenstellen. Die Freigabe ist ein menschlicher Schritt;
`einrichten.ps1` ändert weder Firewall noch Netzprofil. Danach HTTPS von einem
Arbeitsplatz im lokalen Subnetz prüfen. Der Admin-Port 8484 bleibt auf Loopback.


## Zwei Befehle

Der Herausgeber muss zuerst den unveränderlichen Profil-Tag `windows-v0.2.0`
auf dem geprüften Commit dieses Repos veröffentlichen. **Bis dahin ist die URL
noch nicht nutzbar.** `<tag>` in eigenen Verteilanweisungen steht für diesen
Profil-Release, nicht für einen JanuaPort-Image-Tag und nicht für `main`.
Das Skript lädt alle Dateien und `SHA256SUMS` genau von diesem festen Tag.
Bei einem neuen Profil-Release werden Skript-Referenz und Summen gemeinsam
erneuert. Der erste Skript-Download vertraut HTTPS/GitHub; die Summen erkennen
Dateifehler, sind keine davon unabhängige Herausgebersignatur.

Ersteinrichtung durch den Betreiber in der Sitzung von `jnpt-dienst`, nach der
[Diensteinrichtung](#dienstbetrieb-b2). Das Wartungskonto startet nur Aufgaben.
In einer normalen PowerShell von `jnpt-dienst` im gewünschten Downloadordner:

```powershell
curl.exe -fLo e.ps1 https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.2.0/windows/einrichten.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1
```

Nur den Kern-Image-Tag, z. B. `0.87.1`, oder `sha256:<64 kleine Hex-Zeichen>`
eingeben. Ein Tag wird mit Docker auf seinen Registry-Digest aufgelöst. In
`C:\JanuaPort\windows\.env` stehen Repository/Tag als `JANUAPORT_IMAGE`
und der zwingende `JANUAPORT_IMAGE_DIGEST`; Compose kombiniert beide zu einer
Digest-Referenz. Caddy und Skript-Läufer sind bereits per Digest festgelegt.
Ein vollständiges vorhandenes Profil wird erneut geprüft und gestartet; seine
Dateien, `.env`, Zertifikat und Schlüssel bleiben erhalten. Dabei gibt es
keinen Download und keine erneute Image-Abfrage. Für unveränderte Profile aus
0.1.0 gilt der [Upgrade-Weg](#von-010-auf-020); andere unvollständige Zielordner
werden weiterhin abgewiesen. Für ein anderes Ziel gibt es
`-Directory <Profilordner>`; der Dienstbetrieb und seine Aufgaben verwenden immer
`C:\JanuaPort\windows`.

Nach Prüfung der Summen erzeugt das Skript einmalig ein selbstsigniertes
ECDSA-P-256-Leaf für zehn Jahre (3653 Tage) in einem per Digest gepinnten
OpenSSL-Container. SANs: `127.0.0.1`, `localhost`, Rechnername und aktuelle
IPv4-Adressen des Hosts. Zertifikat und Schlüssel liegen im eigenen Docker-
Volume `tls-leaf` (standardmäßig `jnpt-windows_tls-leaf`), für Caddy nur lesbar.
Es gibt keine automatische Zertifikatserneuerung und keine lokale CA.
Auch ein unvollständiges Zertifikat-/Schlüsselpaar wird nicht überschrieben.

Danach startet `docker compose up -d`; das Skript wartet auf `/healthz` und
prüft, dass Caddy genau das eingerichtete Zertifikat ausliefert. Der ausgegebene
SHA-256-Fingerprint stammt aus genau diesem PEM-Zertifikat im Volume.
Die GUI-Ausgabe lautet wörtlich `Admin-GUI: http://127.0.0.1:8484`. Weiter mit
`docs/inbetriebnahme.md` im Produkt-Repo `JanuaPort/januaport`: Master-Schlüssel
sichern, Admin-Passwort setzen, ersten Admin-Token erzeugen.

## Von 0.1.0 auf 0.2.0

Nach Veröffentlichung des Tags durch GATE das **neue** `einrichten.ps1` laden
(siehe „Zwei Befehle“) und in `jnpt-dienst` mit dem bisherigen Profilordner starten:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1 -Directory '<bisheriger Profilordner>'
```

Das Skript erkennt die drei unveränderten Originaldateien aus `windows-v0.1.0`
(`docker-compose.yml`, `Caddyfile`, `einrichten.ps1`) an ihren festen SHA-256-Werten.
`.env` muss vorhanden sein; eine alte `SHA256SUMS` darf vorhanden sein oder fehlen.
Es lädt sämtliche Dateien und die Summenliste ausschließlich von `windows-v0.2.0`
in einen temporären Ordner und prüft sie vollständig, bevor es im Ziel schreibt.
Danach ersetzt es die releaseverwalteten Dateien und ergänzt die bisher fehlenden
READMEs, `.gitignore`, das Runbook sowie B2/B3-Skripte einschließlich
`jnpt-sperren.ps1` und Prüfstein.
Der lokale Ordner `backups\` wird bei der Einrichtung und beim Upgrade angelegt;
er erbt die B-7-ACL und ist kein Bestandteil von SHA256SUMS.
Änderungen an den drei alten Originaldateien erfordern eine manuelle Abstimmung und führen
zum Abbruch vor dem Download. Bei Download- oder Prüfsummenfehlern bleiben die
vorhandenen Dateien unverändert. Nach einem erfolgreichen Upgrade lädt der
zweite Lauf nichts mehr nach.

**`.env` und alle vorhandenen Inhalte unter `secrets/` bleiben bytegenau erhalten.**
Die beiden fehlenden Mail-Secret-Dateien werden wie bisher nur bei Bedarf leer
angelegt. Es gibt keine Image-Abfrage und keinen Wechsel des gespeicherten
Kern-Images. Ohne `-NeuesZertifikat` bleiben Zertifikat und Schlüssel erhalten.
Die lokale Bereitstellung durch `dienst-einrichten.ps1` erkennt dieselben
0.1.0-Dateien und verwendet dafür den bereits geprüften Release-Ordner.

Diese Dateimigration verschiebt weder den Profilordner noch Engine oder Volumes
zwischen Windows-Konten. Für den Dienstbetrieb bleibt das Ziel
`C:\JanuaPort\windows`; eine frühere Ablage unter `%LOCALAPPDATA%\JanuaPort\windows`
ist ein Altpfad, kein neuer Standard. Vor dem Übergang die vorhandene Engine und
Daten dem richtigen Konto zuordnen und den Ablauf auf dem Testrechner gemäß
[Prüfstein B4](PRUEFSTEIN-B4.md) gehen. Das Skript migriert keine Daten eines
anderen Windows-Kontos automatisch.

**Upgrade an Ort und Stelle nur unter `jnpt-dienst`:** Das Skript verlangt die
Sitzung von `jnpt-dienst`. Lief 0.1.0 unter einem persönlichen Konto, gibt es
kein Upgrade an Ort und Stelle, nur den folgenden Weg.

**Daten aus einem anderen Windows-Konto:** Docker Desktop hält Container, Images und
nach unserem Stand auch Volumes je Windows-Konto. Lief 0.1.0 unter einem persönlichen
Konto, liegen die Daten der Anlage dort und nicht bei `jnpt-dienst`. Das Upgrade der
Dateien zieht sie nicht um. Vorher im alten Konto `jnpt backup` ausführen und den
Master-Key getrennt verwahren, dann unter `jnpt-dienst` neu einrichten und die
Sicherung zurückspielen. Erst wenn die Anlage unter `jnpt-dienst` läuft und die
Rücksicherung geprüft ist, im alten Konto im alten Profilordner
`docker compose down -v` ausführen. Sonst liegt dort weiter eine vollständige
Anlage mit Tresor und Master-Key, und Docker Desktop startet sie beim Anmelden
vielleicht wieder. Danach zeigt `docker volume ls` im alten Konto kein
`jnpt-windows_*`-Volume mehr. Dieser Weg ist ein Schritt im Prüfstein B4.

Das TLS-Zertifikat liegt im Volume `tls-leaf` der alten Engine. Beim
Kontowechsel entsteht unter `jnpt-dienst` ein neues Zertifikat mit neuem
Fingerprint. Nach B4-Schritt 2a müssen alle gekoppelten Desktop-Läufer mit
neuem Kopplungscode und dem neuen, lokal vertrauenswürdig übermittelten
Fingerprint erneut koppeln.

## Dienstbetrieb (B2)

Admin-PowerShell, nur auf dem vorgesehenen Betriebsrechner: den vollständigen,
geprüften Release `windows-v0.2.0` bereitstellen, im enthaltenen Ordner `windows`
`dienst-einrichten.ps1 -BackupTarget 'E:\JanuaPort-Backup'` ausführen. GATE
veröffentlicht den Tag erst nach Prüfung; dieses Paket erzeugt keinen Tag.
Das Skript prüft zuerst `SHA256SUMS`, legt `jnpt-dienst` an, nimmt ihn in
`docker-users` auf. **B-7/F5:** Für den Elternordner `C:\JanuaPort` und
`C:\JanuaPort\windows` wird jeweils eine vollständige geschützte DACL mit genau
drei expliziten Allow-Regeln vorbereitet: `jnpt-dienst`, Administratoren und
SYSTEM erhalten FullControl mit ContainerInherit und ObjectInherit.
R4 verlangt außerdem Propagation None: kein InheritOnly oder NoPropagate,
keine weiteren ACEs, weder Allow noch Deny, weder explizit noch geerbt.
Ein einzelner `Directory.SetAccessControl`-Aufruf ersetzt nur den Access-Abschnitt,
ohne vorheriges Leeren. Vorherige zusätzliche Freigaben und die Vererbung vom
Elternordner entfallen zusammen; Besitzer, Gruppe und Audit bleiben erhalten.
Stimmt die geschützte DACL bereits genau überein, schreibt der erneute Lauf
nichts. Erbende Dateien bleiben dadurch auch beim Wiederholen zugänglich.
Erst danach werden Profildateien bereitgestellt. Für bereits von F5 betroffene
Installationen beschreibt das [RUNBOOK](RUNBOOK.md#f5-reparatur-nach-entzogenen-dateirechten)
die manuelle Reparatur.
Vorhandene abweichende Dateien werden außerhalb des geprüften 0.1.0-Upgrades
abgewiesen; `.env` und Secrets bleiben erhalten. Ein von B2
bereitgestelltes Profil ohne `.env` wird bei der ersten Installation ergänzt.

Das Konto erhält ein Zufallskennwort, das nicht angezeigt oder in Dateien
abgelegt wird. Bei Wiederholung bleibt es erhalten. `-KennwortNeu` erzeugt
bewusst ein neues und richtet Autologon neu ein (auch nach einem Admin-Reset).
Nach dem Aufruf von Autologon64 prüft das Skript die Winlogon-Werte alle
500 ms für höchstens 10 Sekunden; erst dann meldet es eine fehlende Bestätigung.
Master-Key, Admin-Kennwort und SMTP-/Graph-Secret liegen in Dateien im
Profilordner bzw. im Volume, nie in der Anmeldeinformationsverwaltung und nicht
EFS-verschlüsselt. Diese Geheimnisse hängen nicht an DPAPI von `jnpt-dienst`.
Sysinternals speichert das Autologon-Kennwort als LSA-Secret; Administratoren
können es auslesen. Die CLI benötigt es kurz als Prozessargument, das für
privilegierte Prozessinspektion sichtbar ist. Das Skript protokolliert es nicht.

`Autologon64.exe` wird ausschließlich aus
`https://download.sysinternals.com/files/AutoLogon.zip` geladen. Der exakte
SHA-256 steht in `SHA256SUMS`; erst danach wird eine gültige Microsoft-
Authenticode-Signatur verlangt. Hashabweichung bedeutet Abbruch, ohne
Ausweichquelle. Das lizenzierte Binary liegt nur lokal, nicht im öffentlichen
Repo. Ein neuer Upstream-Download erfordert ggf. einen überprüften neuen Pin.

„JanuaPort Sperren bei Anmeldung“ startet sofort bei der Anmeldung das feste
`C:\JanuaPort\windows\jnpt-sperren.ps1` verborgen
mit PowerShell. Der Pfad ist durch die B-7-ACL geschützt. Das Skript wartet
im Sekundentakt auf `explorer.exe` in seiner eigenen Sitzung, ruft
`LockWorkStation` auf und bestätigt die Sperre anhand von
`WTSQuerySessionInformation` / `WTSSessionInfoEx.SessionFlags`.
Ohne Bestätigung wiederholt es den Aufruf nach jeweils einer Sekunde. Für
Bereitschaft und Sperre gilt zusammen ein Limit von 120 Sekunden. Scheitert
die Sperre, zeigt die Aufgabenplanung einen Exit-Code ungleich 0; es gibt
kein Abmelden oder Herunterfahren als Ersatz. Genau eine Zeile je Anmeldung
in `C:\JanuaPort\windows\log\sperren.log` enthält ISO-Startzeit, ISO-Zeit der
belegten Sperre oder `nicht_gesperrt`, Versuchszahl und Exit-Code. Sie enthält
keine Benutzernamen oder Fensterinhalte; erhalten bleiben die letzten 100 Zeilen.
Die Einrichtung legt den Ordner unter der B-7-ACL an. Ein Protokollfehler
liefert ebenfalls Exit ungleich 0.
Nach dem Neustart ist der Desktop von `jnpt-dienst` bis zur belegten Sperre
höchstens rund 7 Sekunden sichtbar und ungesperrt (gemessen im Prüfstein B4: Sperre
12,6 Sekunden nach dem Start, davon rund 6 Sekunden Start von conhost und PowerShell).
Schutz in dieser Zeit ist der Zutritt zum Raum beim Betreiber.
Zusätzlich sperrt ein kennwortgeschützter Bildschirmschoner nach 60 Sekunden.
`powercfg` deaktiviert Standby an Netz
und Akku sowie den Ruhezustand. Im Windows-Profil von `jnpt-dienst` wird
`.wslconfig` mit `[wsl2]` und `memory=4GB` angelegt; abweichende vorhandene
Konfiguration erfordert eine manuelle Abstimmung. Kein Docker-/WSL-Neustart
im Skript; die Speichergrenze greift beim nächsten WSL-Start.

Docker Desktop wird nicht konfiguriert: AutoStart **an**, 2375 **aus** und
Auto-Download/Auto-Update **aus** werden nur gelesen und geprüft. Fehlende,
unbekannte oder abweichende Einstellungen führen zum Fehler. Geprüft werden
`autoStart=true`, `exposeDockerAPIOnTCP2375=false`, `autoDownloadUpdates=false`,
`disableUpdate=true` und `silentModulesUpdate=false`; auch Komponentenupdates
müssen aus sein ([Docker-Referenz](https://docs.docker.com/enterprise/security/hardened-desktop/settings-management/settings-reference/)).
**Vor `dienst-einrichten.ps1` Docker Desktop einmal als `jnpt-dienst` starten,**
die Lizenz annehmen und diese Einstellungen setzen. Geprüft wird
`%APPDATA%\Docker\settings-store.json`, alternativ `settings.json` dieses Kontos.
Fehlen beide, endet das Skript mit Fehler und der festen Meldung:
„Docker Desktop einmal in jnpt-dienst starten und die Einstellungen pruefen (AutoStart an, 2375 aus, Auto-Update aus)“.
Falls das Konto noch fehlt, legt ein erster Vorbereitungslauf Konto, Sperre und
Autologon an und endet bei dieser Meldung. Der Betreiber setzt dann als lokaler
Admin vorübergehend ein eigenes Kennwort für
`jnpt-dienst` (sichere Eingabe), meldet sich damit an, konfiguriert Docker Desktop
und stimmt der Lizenz zu. Anschließend führt er als Admin das
Skript mit `-KennwortNeu` erneut aus und startet neu. Damit sind Zufallskennwort,
Autologon und Sperre wieder gemeinsam eingerichtet. Dies gehört zur lokalen
Erstinbetriebnahme vor produktiven Daten. Die Ersteinrichtung und
Image-Abfrage führt der Betreiber in dieser Sitzung durch. Der Dienstleister
arbeitet dort nicht. Danach ist „JanuaPort Anlage starten“ ohne Trigger für
manuelle Starts vorhanden; die tägliche Sicherung läuft um 20:00 Uhr. Beide
Aufgaben verwenden das interaktive Token von `jnpt-dienst`, ohne gespeichertes
Aufgabenkennwort. Das Wartungskonto stößt nur an:

```powershell
schtasks /run /tn "JanuaPort Anlage starten"
schtasks /run /tn "JanuaPort Sicherung"
```

`docker-users` ist praktisch Admin des Rechners. Schutz der Konsole sind Sperre und Raumzutritt beim Betreiber.
Mitglieder können Container mit Bind-Mount auf `C:\` starten. „Standardbenutzer“
beschreibt nur die Ordnung. Der [Prüfstein B4](PRUEFSTEIN-B4.md) verlangt ein Foto des
Sperrbildschirms nach Neustart und die früheste Kennwortabfrage bei Tastendruck
alle 5 Sekunden ab dem ersten Bild. Aufgabenresultat und Protokollzeit gehören
zum Nachweis; ein Foto allein genügt nicht. Dieser Nachweis steht noch aus.

Für das WSL-2-Backend bestätigt die [Docker-Doku zur Windows-Installation](https://docs.docker.com/desktop/setup/install/windows-install/),
dass Container und Images nicht zwischen Konten geteilt werden können. Volumes
werden dort nicht ausdrücklich benannt. „Engine und Volumes je Windows-Benutzer“
ist deshalb als vollständiger Befund noch auf B4 zu prüfen; für andere Backends
gilt diese Behauptung nicht pauschal. Installation, spätere Updates (B5) und
Sicherung laufen durchgehend in `jnpt-dienst`.

Docker Desktop ist für Unternehmen mit **weniger als 250 Mitarbeitern UND
weniger als 10 Mio. USD Jahresumsatz** kostenlos, sonst ist für geschäftliche
Nutzung in der Regel ein kostenpflichtiges Abonnement nötig; staatliche Stellen
benötigen ebenfalls eines. Maßgeblich sind die [Docker-Lizenzbedingungen](https://docs.docker.com/subscription/desktop-license/).
Windows 10 hat seit 14.10.2025 keinen regulären Support mehr. ESU muss bei
weiterem Einsatz gesondert abgesichert werden und belegt keine Docker-Desktop-
Unterstützung. Vor Betrieb die aktuelle Windows-/Docker-Supportmatrix prüfen;
bevorzugt ein unterstütztes Windows 11 Pro einsetzen.

## Sicherung (B3)

v1 verwendet **USB**, vorzugsweise wechselnde Datenträger. Der Betreiber legt
auf jedem vorgesehenen Zielordner (z. B. `E:\JanuaPort-Backup`) die Markerdatei
`.jnpt-backup-ziel` an und gewährt `jnpt-dienst` Schreibrecht. Der Lauf erzeugt
weder Zielordner noch Marker und verwendet kein anderes Ziel bei Fehlern.
Manuell in `jnpt-dienst`, sonst über die Aufgabe:

```powershell
powershell -NoProfile -File C:\JanuaPort\windows\jnpt-backup.ps1 -Target 'E:\JanuaPort-Backup'
```

Compose bindet den relativen Profilordner `./backups` nach `/backups` ein.
Die Einrichtung legt `C:\JanuaPort\windows\backups` unter der B-7-ACL an;
der Lauf ruft ausschließlich `docker compose exec -T jnpt /jnpt backup --output
/backups/<name>` auf. Der Kern schreibt atomar über Temp-Datei und Rename.
Das distroless-Image enthält keine Dateiverwaltungswerkzeuge; Größe und
SHA-256 liest das Skript auf dem Host aus genau dieser Datei. Es kopiert sie
auf das Sicherungsziel unter `.teil`, prüft Größe und Hash, benennt um und
prüft erneut. Anschließend löscht es die Datei im lokalen Staging.
Jeder Fehler liefert Exit ungleich 0 und räumt die eigene Zieldatei auf.
Auch ein Löschfehler macht den Lauf ungültig und entfernt seine Zieldatei.
Nur Namen nach `jnpt-<UTC-Zeit>-<GUID>.jnpt-backup` werden im Staging gelöscht,
auch beim Aufräumen liegengebliebener Läufe. Fremde Dateien bleiben erhalten.
Das exakte Muster ist `^jnpt-[0-9]{8}T[0-9]{9}Z-[a-f0-9]{32}\.jnpt-backup$`.
Ältere Sicherungen am externen Ziel werden nicht automatisch gelöscht.
Freien Speicher und `LastTaskResult` regelmäßig prüfen.

**B4/F4 bleibt am Betriebsmodell zu belegen:** Der nonroot-Kern muss auf dem
Bind-Mount unter Docker Desktop schreiben können; das atomare Rename muss
funktionieren. Der Live-Test `python -B windows/test/backup_live.py` prüft das
echte gepinnte Kern-Image in einem eigenen Projekt. Ein hier blockierter
Live-Test ist kein Erfolgsbeleg; BOX fährt ihn erneut. Es gibt keinen
Hilfscontainer als Ersatz im Sicherungsablauf.
Altlasten aus früheren fehlerhaften Läufen unter `/data/backups` im Volume
separat mit LEAD/BOX erfassen; dieser Host-Ablauf bereinigt nur `backups\`.

**Master-Key getrennt von den Sicherungen verwahren.** Das Skript kopiert keine
Key-Datei und niemals ganz `/data`. Ohne `JNPT_MASTER_KEY_FILE` liegt der Key
neben der DB unter `/data/jnpt.key`. Rücksicherung auf einem Testrechner mit separat
zugeführtem Key ist Pflicht in [B4](PRUEFSTEIN-B4.md).

Optional ist eine SMB-Freigabe nur mit eigenem Sicherungsbenutzer und eigener
Freigabe zulässig, Schreibrecht ausschließlich dort. Zugangsdaten liegen nur
bei `jnpt-dienst`; nach einem Admin-Kennwortreset gibt der Betreiber sie dort
neu ein. Die Skripte legen keine `cmdkey`-Einträge an. Ein Ziel, auf das die
ZBOX schreiben kann, schützt nicht gegen einen Angreifer auf der ZBOX. Ein
wechselnder, abgezogener USB-Datenträger schützt dagegen. Die Wahl trifft der
Betreiber; TeamViewer und das Wartungskonto erhalten diese Zugangsdaten nicht.


### Rücksicherung in eine frische Installation (N4)

Das geprüfte Profil einschließlich `.env` und Secret-Dateien vorbereiten. Vor
seinem ersten `docker compose up` den getrennt verwahrten Key einlegen.
`einrichten.ps1` startet die Anlage bereits; wurde es ausgeführt, zuerst
`down` und die dabei erzeugte DB samt Key wie unten beiseitelegen. Der Gateway
bleibt bis nach `restore` gestoppt; die Ziel-DB muss leer sein, denn Restore
überschreibt keine DB. Der Key muss derselbe wie beim Backup sein.

Compose setzt weder `JNPT_DB_PATH` noch `JNPT_MASTER_KEY_FILE`; der Image-Default
verwendet `/data/jnpt.db` und den benachbarten Key `/data/jnpt.key`. Der feste
Projektname `jnpt-windows` ergibt das Volume `jnpt-windows_jnpt-data`.
Bei einer bewusst abweichenden Konfiguration den Key vor dem ersten Start an
den von `JNPT_MASTER_KEY_FILE` erwarteten Ort legen. Die folgende Folge gilt
für das ausgelieferte Profil und verwendet einen einmaligen, gepinnten
Hilfscontainer. Bei frischem Volume setzt sie auch dessen Eigentümer auf
UID/GID 65532. Die Key-Datei erhält Modus 600; BOX bestätigt Lesbarkeit durch
den nonroot-Kern und die Rechte bei der B4-Abnahme.

Key-Ordner und Sicherungsordner auf dem USB-Datenträger sowie den Dateinamen
anpassen. Im Key-Ordner heißt die separat verwahrte Datei `jnpt.key`.
Vorhandene DB-Dateien und der beim Erststart erzeugte Key werden verschoben,
nicht gelöscht. Das Beiseitelege-Muster auch bei frischer Installation ausführen:

<!-- N4 -->
```powershell
Set-Location C:\JanuaPort\windows
$HelperImage = 'busybox@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec'
docker compose down
docker run --rm -v jnpt-windows_jnpt-data:/data $HelperImage sh -ec 'd=/data/beiseite-$(date -u +%Y%m%dT%H%M%SZ) && mkdir $d && for f in jnpt.db jnpt.db-wal jnpt.db-shm jnpt.key; do [ ! -e /data/$f ] || mv /data/$f $d/; done'
$KeyDirectory = 'E:\JanuaPort-Key'
docker run --rm -v jnpt-windows_jnpt-data:/data -v "${KeyDirectory}:/in:ro" $HelperImage sh -ec 'cp /in/jnpt.key /data/jnpt.key && chown 65532:65532 /data /data/jnpt.key && chmod 600 /data/jnpt.key'
$BackupDirectory = 'E:\JanuaPort-Backup'
$BackupFile = 'sicherung.jnpt-backup'
docker compose run --rm --no-deps -v "${BackupDirectory}:/in:ro" jnpt restore "/in/$BackupFile"
docker compose up -d
curl.exe --fail http://127.0.0.1:8484/healthz
```

Danach eine Admin-Anmeldung prüfen: Health muss 200 liefern und die erwarteten
Daten müssen verfügbar sein.
Den Ordner `/data/beiseite-<zeitstempel>` erst löschen, wenn die Rücksicherung geprüft ist (healthz, Anmeldung, Lesezugriff).
Wer den Block auf eine nicht frische Anlage anwendet, verliert sonst den alten Stand.
USB-Datenträger anschließend abziehen. Lag eine
Key-Kopie auf dem Rechner, diese nach der Prüfung wieder entfernen; der
getrennt verwahrte Original-Key bleibt erhalten. `docs/disaster-recovery.md`
der eingesetzten Kern-Version beschreibt die weitere Prüfung.

## Mail

`einrichten.ps1` fragt weiterhin nur nach dem Image-Tag. Es legt vor dem Start
die leeren Dateien `secrets/smtp_password` und `secrets/graph_client_secret` im
Profilordner an und erhält vorhandene Inhalte. Ohne Mail-Konfiguration startet
das Profil wie bisher.
**Betreiber-Merkmal, Netztür, Bauphase und Fall-Token benötigen zustellbare Mail.**
Vor ihrer Nutzung den Versand und den tatsächlichen Empfang prüfen.

Die Mail-Einrichtung erfolgt danach von Hand im installierten Profilordner
(standardmäßig `C:\JanuaPort\windows`). Die folgenden optionalen
Werte in `.env` ergänzen; fehlende oder leere Werte bleiben im Container leer:

| Variable | Bedeutung |
|---|---|
| `JNPT_SMTP_HOST` | SMTP-Server, z. B. `smtp.example.org` |
| `JNPT_SMTP_PORT` | Port des SMTP-Servers |
| `JNPT_SMTP_TLS` | TLS-Einstellung gemäß der Kern-Konfiguration |
| `JNPT_SMTP_FROM` | Absender, z. B. `sender@example.org` |
| `JNPT_SMTP_TO` | Empfänger, z. B. `recipient@example.org` |
| `JNPT_SMTP_USERNAME` | SMTP-Benutzername |
| `JNPT_NOTIFY_STATE` | Optionaler Pfad des Benachrichtigungszustands im Container |
| `JNPT_NOTIFY_TRANSPORT` | Mail-Transport gemäß der Kern-Konfiguration |
| `JNPT_NOTIFY_GRAPH_TENANT_ID` | Tenant-ID für Graph |
| `JNPT_NOTIFY_GRAPH_CLIENT_ID` | Client-ID der Graph-Anwendung |
| `JNPT_NOTIFY_GRAPH_SENDER` | Graph-Absender, z. B. `sender@example.org` |
| `JNPT_NOTIFY_GRAPH_CLIENT_SECRET_EXPIRES` | Ablaufzeitpunkt des Client-Secrets gemäß der Kern-Konfiguration |
| `JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE` | Nur für Graph: `/run/secrets/graph_client_secret`, sonst leer lassen |

**Das SMTP-Passwort steht nie in `.env` und nie in der Container-Umgebung.**
Es ausschließlich als Inhalt der lokalen Datei `secrets/smtp_password` speichern
(UTF-8 ohne BOM). Der Ordner `secrets/` ist gitignored; die Secret-Dateien werden
weder ausgeliefert noch in `SHA256SUMS` aufgenommen. Den Dateizugriff auf dem
Rechner auf die zuständigen Benutzer und Docker Desktop beschränken.
Compose bindet sie als Secret unter `/run/secrets/smtp_password` ein.
`JNPT_SMTP_PASSWORD_FILE` ist fest auf diesen Containerpfad gesetzt;
`JNPT_SMTP_PASSWORD` wird nicht durchgereicht. Beide Variablen gehören nicht
in `.env`.

Für Graph `JNPT_NOTIFY_TRANSPORT=graph` und die Graph-Werte in `.env` setzen.
In `.env` zusätzlich diese Zeile eintragen:

```dotenv
JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE=/run/secrets/graph_client_secret
```

**Das Graph-Client-Secret steht ebenfalls nie in `.env` oder im Container-Env.**
Es ausschließlich in `secrets/graph_client_secret` speichern (UTF-8 ohne BOM).
Compose bindet die Datei unter `/run/secrets/graph_client_secret` ein;
ein anderer Pfad ist nicht vorgesehen. Ohne gesetzten `.env`-Wert bleibt
`JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE` im Container leer.
`JNPT_NOTIFY_GRAPH_CLIENT_SECRET` wird nicht durchgereicht und gehört nicht
in `.env`. **Graph unterstützt in v1 ausschließlich Client-Secret.**
`JNPT_NOTIFY_GRAPH_CERT_FILE` und `JNPT_NOTIFY_GRAPH_KEY_FILE` werden nicht
durchgereicht; Zertifikatsauthentifizierung folgt bei Bedarf.

Bei SMTP alle `JNPT_NOTIFY_GRAPH_*`-Werte in `.env` leer lassen oder weglassen,
auch `JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE`. So meldet der Kern keine ignorierte
Graph-Konfiguration. Der Secret-Mount mit der leeren Datei bleibt vorhanden.

`JNPT_ADMIN_URL` ist fest `http://127.0.0.1:8484` (SEC W8):
Admin-Links sind ausschließlich am Rechner der Anlage erreichbar.

Beide Secret-Dateien auch ohne Mail-Konfiguration erhalten. `docker compose config`
prüft ihre Existenz nicht. Bei fehlender Datei kann Compose beim Start
scheitern oder einen Verzeichnispfad statt einer lesbaren Datei einbinden.
Für einen manuellen Start das Profil deshalb zuerst mit `einrichten.ps1`
vorbereiten. Nach Änderungen an `.env` oder einer Secret-Datei im Profilordner
ausführen:

```powershell
docker compose config --quiet
docker compose up -d --force-recreate jnpt
```

## Desktop-Läufer koppeln

Die signierte Windows-EXE aus `JanuaPort/januaport-plugins` gemäß dessen
`desktop-runner/README.md` prüfen und im Benutzerprofil ablegen. In der lokalen
Admin-GUI ein Windows-Gerät anlegen und einen einmaligen Kopplungscode erzeugen.
Den lokal ausgegebenen Fingerprint über einen vertrauenswürdigen Weg an den
Läufer übertragen; auf einem fremden LAN-Gerät einfach ein Zertifikat abzuholen
belegt dessen Identität nicht.

```powershell
.\desktop-runner.exe pair --url https://<LAN-IP-des-Servers> --code <KOPPLUNGSCODE> --fingerprint <64-Hex-Zeichen>
.\desktop-runner.exe run
```

Am Server selbst `--url https://127.0.0.1` verwenden. **Eine CA nie in einen
Windows- oder anderen Zertifikatsspeicher importieren (SEC W10).** Kein `--ca`
und kein Abschalten der TLS-Prüfung am Läufer. `--fingerprint` bindet genau
dieses Leaf; Caddy lädt ausschließlich `/certs/cert.pem` und `/certs/key.pem`.

Im geprüften Desktop-Läufer (`desktop-runner/internal/client/http.go`,
`NewAPI`/`VerifyConnection`) vergleicht der Fingerprint-Modus ausschließlich
SHA-256 des DER-Leafs. Hostname/IP-SAN, CA-Kette und Gültigkeitszeit werden
dabei nicht geprüft. Eine neue DHCP-IP erfordert daher kein neues Zertifikat.
Die im Läufer gespeicherte Server-URL muss aber weiter erreichbar sein; bei
geänderter Adresse mit angepasstem `--url` erneut koppeln, mit demselben
Fingerprint. Empfehlung: feste IP oder DHCP-Reservierung bzw. ein stabil
auflösbarer Rechnername.

**Zertifikat bewusst ersetzen:** beispielsweise nach einer Kompromittierung
oder vor Ablauf der zehn Jahre im installierten Profil:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\JanuaPort\windows\einrichten.ps1" -NeuesZertifikat
```

Bei einem eigenen Ziel `-Directory <Profilordner>` ergänzen. Dieser ausdrückliche
Aufruf stoppt Caddy, ersetzt Zertifikat und Schlüssel, nimmt die aktuellen SANs
auf und startet wieder. **Danach alle Läufer mit neuem Kopplungscode und dem
neuen Fingerprint erneut koppeln.** Ein normaler Einrichtungslauf und ein
Caddy-Neustart behalten das Zertifikat unverändert. Das TLS-Volume erhalten;
sein Verlust und anschließende Neuerzeugung bedeuten ebenfalls einen neuen Pin.

Für Skriptpakete in der Basis-Einrichtung die Stellen `plugin-script-runner`
(Laufzeitschlüssel) und `plugin-script-runner-git` (Nur-Lese-Deploy-Key) belegen.
Unter Einstellungen › Plugins › Skript-Läufer Repository-URL und Desktop-Pin
mit vollem Commit, Pfad und Zielgerät setzen. Die benannten Volumes stellen
die Plugin-Ordner bereit; der Kern schreibt Schlüssel und Pins atomar hinein.
Die Compose verwaltet den Beisteller direkt; ein Host-Aktuator gehört nicht
zu diesem Profil. Die Katalogauswahl dafür unverwaltet lassen. Desktop-Pakete
werden vom echten Fetcher gegen den Standard-Zweig geprüft; `ready` und ein
erfolgreicher Auftragslauf sind zusätzlich zur Kopplung zu prüfen.

## Sicherheits-Defaults

- **SEC W6:** Runtime `runc`; lokale Skript-Pins sind aus. Es existiert kein
  Sandbox-Dienst, auch kein zuschaltbares Sandbox-Profil. Ein lokales
  `tools/call` für einen gültigen Pin endet mit `refused/state`,
  `isolation=invalid`. Zeitpläne erhalten ebenfalls keinen lokalen Laufplatz.
  Desktop-Pins und deren Paketabruf benötigen die Sandbox nicht.
  Der originale Sandbox-Healthcheck bleibt deshalb **unhealthy/503**. Das ist
  kein Desktop-Paketfehler; `docker compose up --wait` eignet sich hier nicht.
- **SEC W8:** Nur TCP 443 geht ins LAN. Caddy teilt `jnpt`'s Netz-Namensraum
  und spricht `http://127.0.0.1:8484` mit echtem Loopback-Absender an. Das
  ermöglicht die Geräte-Kopplung trotz Docker-Desktop-NAT. Weitergeleitet werden
  ausschließlich `/api/device/v1/*` und exakt `/healthz`; alles andere ist 404,
  darunter GUI, `/admin/mcp`, `/api/admin/*`, `/metrics` und `/mcp`.
  Port 8484 bindet ausschließlich an `127.0.0.1`. Caddys Admin-API ist aus.
  Der auskommentierte `/mcp`-Block ist erst bei Bedarf eines KI-Clients im LAN
  und nach erneuter Berechtigungs- und Pfadprüfung zu aktivieren.
- **SEC W9:** Die [LAN-Freigabe bei der Einrichtung](#lan-freigabe-bei-der-einrichtung-n5)
  manuell ausführen: Privat oder Domäne, Regel „JanuaPort 443 LAN“, TCP 443
  ausschließlich aus `LocalSubnet`. Windows-Firewall eingehend auf
  Standard „Blockieren“ belassen. Vorhandene breitere Docker-/WSL-Freigaben
  prüfen und einschränken; eine zusätzliche enge Allow-Regel hebt breite
  Regeln nicht auf. Von einem Gerät im lokalen Subnetz 443 prüfen, von außerhalb
  des Subnetzes muss der Zugriff scheitern. 8484 auch im LAN negativ prüfen.
  Das Skript ändert die Host-Firewall nicht.
- **Caddy und Firewall sind die Kante (SEC K1/K2):** Weil Caddy im Netz-Namensraum
  von `jnpt` weiterleitet, sieht der Kern jeden Aufruf als Loopback. Die Prüfungen
  des Kerns auf lokale Absender (Kopplung ohne HTTPS, nur lokale Geräte) greifen in
  diesem Profil deshalb nicht. Die Grenze bilden allein Caddy (nur TLS auf 443, kein
  Klartext-Listener, durch einen Test belegt) und die Windows-Firewall (W9). Vor
  produktiven Daten gehören `Get-NetFirewallRule` für 443 und für die Docker-Prozesse
  in den Abnahmebericht. Eine Freigabe mit „Beliebig“ als Remoteadresse darf es nicht
  geben. Wo möglich, kommt eine Gegenprobe aus einem fremden Subnetz dazu.

Im internen Plugin-Netz `plugins` ist `jnpt` fest auf `172.21.0.2` im Subnetz
`172.21.0.0/16` gesetzt; Beisteller erhalten Adressen ausschließlich dynamisch
aus `172.21.128.0/17`, damit sie beim Neustart den Gateway-Platz freihalten (#1355).
Alle Dauerdienste verwenden `restart: unless-stopped`, Init-Dienste `restart: "no"`.
Beim Umstellen eines bestehenden Profils im Profilordner einmal
`docker compose down` und danach `docker compose up -d` ausführen, damit das
Netz mit der neuen IPAM-Konfiguration entsteht; die benannten Volumes erhalten.

Das interne Plugin-Netz begrenzt den Ausgang, sperrt aber nicht von selbst
jeden Dienst des Windows-/WSL-Hosts. Die Linux-iptables-Anleitung in
`compose/README.md` ist kein Windows-Nachweis. Host-/WSL-Firewall nach den
Vorgaben des Betreibers prüfen. Der Fetcher besitzt ein separates Ausgangsnetz
und sieht nur den Git-Schlüssel; der Vermittler sieht den Laufzeitschlüssel.
Kein Docker-Socket wird in Container eingehängt.

## Prüfen

Im installierten Profilordner:

```powershell
docker compose config --quiet
curl.exe -fsS http://127.0.0.1:8484/healthz
curl.exe -k -i https://127.0.0.1/api/device/v1/
curl.exe -k -i https://127.0.0.1/
```

Erwartet: Health 200; Geräte-API ohne Token 401 mit JSON; Root 404.
`-k` dient ausschließlich diesen manuellen Diagnoseaufrufen. Kopplung und
Läuferbetrieb verwenden den Fingerprint. Ein Health-Erfolg belegt weder einen
Desktop-Paketabruf noch einen erfolgreichen Auftrag.

Repository-Prüfungen (Python-Standardbibliothek, Docker erforderlich):
`python -B -m unittest discover -s windows/test -v`.
Zusätzlicher Rundlauf und Mutationen sind in [test/README.md](test/README.md)
beschrieben. SHA256SUMS enthält Compose, Caddyfile, alle vier Skripte
(`einrichten.ps1`, `dienst-einrichten.ps1`, `jnpt-sperren.ps1`, `jnpt-backup.ps1`), `.gitignore`,
beide READMEs, Runbook und B4-Prüfstein sowie den externen Autologon-Pin; `.gitattributes`
hält dafür auch im Windows-Checkout dieselben LF-Bytes wie im Download fest.

## Update und Grenzen

B2 richtet Autologon und Dienstaufgaben ein, B3 die tägliche Sicherung. Das
B5-Update-Skript folgt als eigenes Paket; kein automatisches Update. Docker
Desktop läuft in der angemeldeten, gesperrten Sitzung von `jnpt-dienst`. Der
Neustartnachweis ist im [Prüfstein B4](PRUEFSTEIN-B4.md) offen. Tailscale gehört
nicht zu diesem Paket.

## Fernwartung

TeamViewer auf Annahme gemäß AVV Anlage 3: Ein Mensch beim Betreiber nimmt
jede Sitzung an. Kein unbeaufsichtigter Fernzugriff und kein festes
Fernwartungskennwort; Autologon ist ausschließlich die lokale Windows-Anmeldung.
Der Dienstleister arbeitet im Wartungskonto und stößt nur Aufgaben an.
