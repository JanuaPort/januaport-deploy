# Windows: Docker Compose mit TLS im LAN

[English](README.en.md) · **Deutsch**

Paket A (#1246): Windows 10/11 Pro, Docker Desktop mit WSL2 und Linux-Containern
(amd64). Gebaut und mit Docker Desktop lokal geprüft; kein Nachweis eines
unbeaufsichtigten Dauerbetriebs. Die Oberfläche bleibt am Gerät, Desktop-Läufer
im LAN und am selben Rechner sprechen HTTPS mit Zertifikatbindung.

Den Ablauf vor Ort und bei Fernwartung (wer wann was tut) beschreibt das [Runbook](RUNBOOK.md).

## Voraussetzungen

- Docker Desktop **≥ 4.44.3** (Behebung von CVE-2025-9074), laufende WSL2-Engine,
  Compose ≥ 2.35 (Volume-Subpaths) und PowerShell 5.1 oder neuer.
- Docker Desktop: **„Expose daemon on tcp://localhost:2375“ aus**. Auto-Updates
  nur nach Prüfung freigeben; dieses Profil installiert keine Updates.
- Die TCP-Ports 443 und 8484 sind frei. Kein Router-Portforwarding für 443.
- Zugang zur öffentlichen Image-Registry und zu GitHub. Für Desktop-Pins später
  ein eigenes Skript-Repository und dessen Nur-Lese-Deploy-Key.

## Zwei Befehle

Der Herausgeber muss zuerst den unveränderlichen Profil-Tag `windows-v0.1.0`
auf dem geprüften Commit dieses Repos veröffentlichen. **Bis dahin ist die URL
noch nicht nutzbar.** `<tag>` in eigenen Verteilanweisungen steht für diesen
Profil-Release, nicht für einen JanuaPort-Image-Tag und nicht für `main`.
Das Skript lädt alle Dateien und `SHA256SUMS` genau von diesem festen Tag.
Bei einem neuen Profil-Release werden Skript-Referenz und Summen gemeinsam
erneuert. Der erste Skript-Download vertraut HTTPS/GitHub; die Summen erkennen
Dateifehler, sind keine davon unabhängige Herausgebersignatur.

In einer normalen PowerShell im gewünschten Downloadordner:

```powershell
iwr https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.1.0/windows/einrichten.ps1 -OutFile e.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1
```

Nur den Kern-Image-Tag, z. B. `0.87.1`, oder `sha256:<64 kleine Hex-Zeichen>`
eingeben. Ein Tag wird mit Docker auf seinen Registry-Digest aufgelöst. In
`%LOCALAPPDATA%\JanuaPort\windows\.env` stehen Repository/Tag als `JANUAPORT_IMAGE`
und der zwingende `JANUAPORT_IMAGE_DIGEST`; Compose kombiniert beide zu einer
Digest-Referenz. Caddy und Skript-Läufer sind bereits per Digest festgelegt.
Ein vollständiges vorhandenes Profil wird erneut geprüft und gestartet; seine
Dateien, `.env`, Zertifikat und Schlüssel bleiben erhalten. Dabei gibt es
keinen Download und keine erneute Image-Abfrage. Andere vorhandene oder
unvollständige Zielordner werden abgewiesen. Für ein anderes Ziel gibt es
`-Directory C:\JanuaPort\windows`.

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
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\JanuaPort\windows\einrichten.ps1" -NeuesZertifikat
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
beschrieben. SHA256SUMS enthält die drei ausgeführten Profildateien; `.gitattributes`
hält dafür auch im Windows-Checkout dieselben LF-Bytes wie im Download fest.

## Update und Grenzen

Update, Backup und Autologon folgen mit Paket B. Dieses Profil enthält dafür
keine Automatik. Docker Desktop muss bereits laufen; ein Systemstart ohne
Benutzeranmeldung ist hier nicht belegt. Tailscale gehört nicht zu Paket A.

## Fernwartung

Über das Werkzeug des Betreibers, Sitzung nimmt der Kunde an.
