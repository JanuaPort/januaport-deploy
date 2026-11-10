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
keinen Download und keine erneute Image-Abfrage. Andere vorhandene oder
unvollständige Zielordner werden abgewiesen. Für ein anderes Ziel gibt es
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

## Dienstbetrieb (B2)

Admin-PowerShell, nur auf dem vorgesehenen Betriebsrechner: den vollständigen,
geprüften Release `windows-v0.2.0` bereitstellen, im enthaltenen Ordner `windows`
`dienst-einrichten.ps1 -BackupTarget 'E:\JanuaPort-Backup'` ausführen. GATE
veröffentlicht den Tag erst nach Prüfung; dieses Paket erzeugt keinen Tag.
Das Skript prüft zuerst `SHA256SUMS`, legt `jnpt-dienst` an, nimmt ihn in
`docker-users` auf und richtet `C:\JanuaPort\windows` mit Zugriff für dieses
Konto, SYSTEM und lokale Administratoren ein. Vorhandene Profil-Dateien werden
bei Abweichungen abgewiesen; `.env` und Secrets bleiben erhalten. Ein von B2
bereitgestelltes Profil ohne `.env` wird bei der ersten Installation ergänzt.

Das Konto erhält ein Zufallskennwort, das nicht angezeigt oder in Dateien
abgelegt wird. Bei Wiederholung bleibt es erhalten. `-KennwortNeu` erzeugt
bewusst ein neues und richtet Autologon neu ein (auch nach einem Admin-Reset).
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

Das Skript richtet „JanuaPort Sperren bei Anmeldung“ und einen kennwortgeschützten
Bildschirmschoner nach 60 Sekunden ein. `powercfg` deaktiviert Standby an Netz
und Akku sowie den Ruhezustand. Im Windows-Profil von `jnpt-dienst` wird
`.wslconfig` mit `[wsl2]` und `memory=4GB` angelegt; abweichende vorhandene
Konfiguration erfordert eine manuelle Abstimmung. Kein Docker-/WSL-Neustart
im Skript; die Speichergrenze greift beim nächsten WSL-Start.

Docker Desktop wird nicht konfiguriert: AutoStart **an**, 2375 **aus** und
Auto-Download/Auto-Update **aus** werden nur gelesen und geprüft. Fehlende,
unbekannte oder abweichende Einstellungen führen zum Fehler. Geprüft werden
`autoStart=true`, `exposeDockerAPIOnTCP2375=false`, `autoDownloadUpdates=false`,
`disableUpdate=true` und `silentModulesUpdate=false`; auch Komponentenupdates
müssen aus sein ([Docker-Referenz](https://docs.docker.com/enterprise/security/hardened-desktop/settings-management/settings-reference/)). Bei der ersten
Einrichtung kann dies nach Konto-, Sperr- und Autologon-Einrichtung geschehen:
der Betreiber setzt als lokaler Admin vorübergehend ein eigenes Kennwort für
`jnpt-dienst` (sichere Eingabe), meldet sich damit an, konfiguriert Docker Desktop
und stimmt der Lizenz zu. Nach der Erstinstallation führt er als Admin das
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

**`docker-users` ist keine Schutzgrenze:** Mitglieder können Container mit
Bind-Mount auf `C:\` starten und sind damit praktisch Admin. „Standardbenutzer“
beschreibt nur die Ordnung. Bei Autologon hängt der Konsolenschutz an der Sperre
bei Anmeldung. Der [Prüfstein B4](PRUEFSTEIN-B4.md) verlangt ein Foto des
Sperrbildschirms nach Neustart; dieser Nachweis steht noch aus.

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

Der Ablauf ist `/jnpt backup --output /data/backups/<name>` über
`docker compose exec -T jnpt`, dann Größen-/SHA-Abfrage im Container und
`docker compose cp` für genau diese Datei auf den Host. Kein Bind-Mount.
Geschrieben wird unter `.teil`, dann umbenannt, Größe und `Get-FileHash` werden
vor und nach dem Umbenennen gegen die Container-Werte gelesen. Jeder Fehler
liefert Exit ungleich 0 und räumt die eigene unfertige Zieldatei auf; es gibt
keinen Ausweichweg. Nach geprüftem Ziel-Hash wird genau die Container-Kopie
unter `/data/backups/` gelöscht. Schlägt das Löschen fehl, ist auch der Lauf
fehlgeschlagen und die Zieldatei wird entfernt. v1 löscht keine älteren Sicherungen
automatisch. Freien Speicher und `LastTaskResult` regelmäßig prüfen.

**Master-Key getrennt von den Sicherungen verwahren.** Das Skript kopiert keine
Key-Datei und niemals ganz `/data`. Ohne `JNPT_MASTER_KEY_FILE` liegt der Key
neben der DB in `/data`. Rücksicherung auf einem Testrechner mit separat
zugeführtem Key ist Pflicht in [B4](PRUEFSTEIN-B4.md).

Optional ist eine SMB-Freigabe nur mit eigenem Sicherungsbenutzer und eigener
Freigabe zulässig, Schreibrecht ausschließlich dort. Zugangsdaten liegen nur
bei `jnpt-dienst`; nach einem Admin-Kennwortreset gibt der Betreiber sie dort
neu ein. Die Skripte legen keine `cmdkey`-Einträge an. Ein Ziel, auf das die
ZBOX schreiben kann, schützt nicht gegen einen Angreifer auf der ZBOX. Ein
wechselnder, abgezogener USB-Datenträger schützt dagegen. Die Wahl trifft der
Betreiber; TeamViewer und das Wartungskonto erhalten diese Zugangsdaten nicht.

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
- **SEC W9:** In einer administrativen PowerShell beispielsweise:

  ```powershell
  New-NetFirewallRule -DisplayName 'JanuaPort HTTPS LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 -RemoteAddress LocalSubnet -Profile Private
  ```

  Das Netz muss als privat eingestuft sein. Windows-Firewall eingehend auf
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
beschrieben. SHA256SUMS enthält Compose, Caddyfile, alle drei Skripte, `.gitignore`,
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
