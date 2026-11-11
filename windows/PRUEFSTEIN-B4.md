# Prüfstein B4: Dienstbetrieb und Wiederherstellung

Offene Abnahme auf einem eigenen Testrechner mit ausschließlich synthetischen
Daten. Die Python-Fakes ersetzen diesen Nachweis nicht. Ergebnis, Windows- und
Docker-Version, Backend, Uhrzeit und Nachweis je Schritt im Abnahmeprotokoll
festhalten; keine Geheimnisse oder Daten des Betreibers aufnehmen.

1. **Gemeinsame Engine (N4, durch B5 korrigiert):** Es gibt eine Engine.
   BOX hat auf VM `jnpt-b4` belegt, dass `docker ps` im Wartungskonto dieselben
   `jnpt-windows-*`-Container zeigt (B5 @`a87f571`, Protokoll `c-6796028725`, #1246).
   Wer in `docker-users` ist, erreicht die Container. Das Wartungskonto stößt
   ausschließlich Aufgaben mit `schtasks /run` an und ruft nie selbst `docker`
   auf; das ist eine Betriebsregel, keine technische Trennung. Die IT prüft
   `docker-users` als Administrator gemäß README: hinein gehört nur `jnpt-dienst`.
   `dienst-einrichten.ps1` fügt nur dieses Konto hinzu, bereinigt aber keine
   vorhandenen weiteren Mitglieder. Die frühere Annahme getrennter Engines
   und Volumes nach Windows-Konto ist widerlegt.

2. **Upgrade 0.1.0 → 0.3.0 am Testrechner einmal gehen.** Von den drei
   Originaldateien plus `.env` ausgehen (alte Summenliste optional), neues
   Einrichtungsskript verwenden. Vollständiges 0.3.0-Profil, unveränderte `.env`
   und Secrets, bisheriges Kern-Image und Zertifikat prüfen; zweiter Lauf ohne
   Download. Profilpfad und ausführendes Windows-Konto separat prüfen;
   dieselbe Engine und dieselben Volumes werden weiterverwendet.
3. **B-7, Ordnerrechte:** Nach Diensteinrichtung `icacls C:\JanuaPort` und
   `icacls C:\JanuaPort\windows` prüfen, dazu `icacls C:\JanuaPort /t` für
   explizite Freigaben auf einzelnen Dateien darunter (SEC, nicht blockierend). Nur `jnpt-dienst`, Administratoren und
   SYSTEM dürfen eingetragen sein. Keine Rechte für Benutzer oder
   Authentifizierte Benutzer. Mit einem anderen Standardkonto den Lesezugriff
   auf `secrets/smtp_password` und den Schreibzugriff auf `docker-compose.yml`
   tatsächlich versuchen: beide müssen scheitern. Erst dann weiterarbeiten.
   **F5/B-1:** `.env`, eine synthetische Datei unter `secrets\` und
   `log\sperren.log` in der Sitzung von `jnpt-dienst` erzeugen und deren Besitzer
   und geerbte ACEs festhalten. Die neue Diensteinrichtung als Administrator
   erneut ausführen (auch mit `-KennwortNeu`). Danach sind alle drei Dateien
   weiterhin lesbar, tragen die drei geerbten FullControl-ACEs und niemals
   eine leere DACL wie `D:AI`; Anlagenstart und Sicherung müssen grün sein.
   Bei bereits korrekter Ordner-DACL bleibt der SDDL beim zweiten Lauf gleich.
   **R4:** Gültig ist ausschließlich eine geschützte DACL mit genau drei
   expliziten Allow-ACEs (SYSTEM, Administratoren, Dienst-SID), jeweils
   FullControl mit ContainerInherit und ObjectInherit, ohne InheritOnly oder
   NoPropagate und ohne weitere explizite oder geerbte Allow-/Deny-ACEs.
   Zusätzliches Benutzer-Read-ACE und eine ACE ohne ObjectInherit getrennt
   ausprobieren: erneute Einrichtung muss beide Abweichungen entfernen.
   Der Fall eines anderen Dateibesitzers ist im lokalen NTFS-Test nicht
   nachgestellt und bleibt ausdrücklich BOX-Abnahme.
4. **W4/W5, B-3, Neustart:** `dienst-einrichten.ps1` auf dem Testrechner als
   Admin vorbereiten, Docker Desktop vor dem abschließenden Lauf einmal in
   `jnpt-dienst` starten und Einstellungen von Hand prüfen, mit `-KennwortNeu`
   erneut prüfen lassen. Keinen festen Delay und den festen B-7-geschützten Pfad
   `C:\JanuaPort\windows\jnpt-sperren.ps1` in der Aufgabe kontrollieren.
   Das Skript prüft Explorer derselben Sitzung und WTS-Sperrstatus jede Sekunde,
   zusammen höchstens 120 Sekunden. Bei Fehler ist `LastTaskResult` ungleich 0,
   ohne Abmelden oder Herunterfahren als Ersatz. Der B-7-geschützte Ordner
   `C:\JanuaPort\windows\log` ist angelegt; `sperren.log` enthält pro Anmeldung
   genau eine Zeile mit ISO-Startzeit, ISO-Sperrzeit oder `nicht_gesperrt`,
   Versuchszahl und Exit-Code, ohne Benutzernamen, höchstens 100 Zeilen.
   Neustarten. Ab dem ersten Bild alle 5 Sekunden eine Taste drücken und den
   frühesten Zeitpunkt einer Kennwortabfrage notieren. Aufgabenresultat muss 0
   sein. Diesen Zeitpunkt und den Zeitpunkt aus `sperren.log` in den Gate-Bericht
   aufnehmen. Der Bildschirmschoner sperrt nach 60 Sekunden: eine spätere Probe
   allein belegt die Skriptwirkung nicht. Foto des erreichten Sperrbildschirms
   aufnehmen (ohne personenbezogene Inhalte). Sperre bei Anmeldung und nach
   einer Minute Inaktivität einschließlich Kennwortpflicht tatsächlich testen.
   Prüfen, dass Docker Desktop und Anlage trotz gesperrter Sitzung laufen.
   `docker-users` ist praktisch Admin und keine Schutzgrenze. Das Wartungskonto
   löst ausschließlich die Aufgaben aus, z. B. `schtasks /run /tn "JanuaPort
   Sicherung"`; keine Anmeldung/Arbeit des Dienstleisters als `jnpt-dienst`.
4a. **N5-1, Firewall bei jeder echten Abnahme:** In B4 fand sich keine
    Allow-Regel für Docker. Docker Desktop hatte nur zwei Block-Regeln für das
    Profil „Öffentlich“ angelegt, weil der Firewall-Dialog unbeantwortet blieb.
    Was bei „Zulassen“ entsteht, ist nicht gemessen.
    Den Firewall-Dialog von Docker Desktop nicht mit ‚Zulassen‘ für öffentliche Netze beantworten.
    In einer administrativen PowerShell die aktiven eingehenden Allow-Regeln
    mit Docker-Anwendungsfilter und alle Portfilter, die 443 öffnen, auflisten
    (auch `Any`, Portlisten und Bereiche). Diese Prüfung liest nur:

<!-- N5-1 -->
```powershell
$inboundAllow = @(Get-NetFirewallRule -Enabled True -Direction Inbound -Action Allow)
foreach ($rule in $inboundAllow) {
    $applications = @($rule | Get-NetFirewallApplicationFilter)
    $isDocker = @($applications | Where-Object { $_.Program -match 'docker' }).Count -gt 0
    foreach ($port in @($rule | Get-NetFirewallPortFilter)) {
        $opens443 = @($port.LocalPort -split ',' | Where-Object {
            $_ -eq 'Any' -or $_ -eq '443' -or
            ($_ -match '^([0-9]+)-([0-9]+)$' -and [int]$Matches[1] -le 443 -and [int]$Matches[2] -ge 443)
        }).Count -gt 0
        # N8: Nur Regeln, die den Docker-Listener auf TCP 443 öffnen könnten (Programm Any, kein App-Paket).
        $tcp = $port.Protocol -in @('TCP', 'Any')
        $anyProgram = @($applications | Where-Object { $_.Program -eq 'Any' }).Count -gt 0
        $package = @($applications | Where-Object { $_.Package }).Count -gt 0
        if ($isDocker -or ($opens443 -and $tcp -and $anyProgram -and -not $package)) {
            [pscustomobject]@{
                Name = $rule.Name; DisplayName = $rule.DisplayName; Profile = $rule.Profile
                Program = ($applications.Program -join ',')
                Protocol = $port.Protocol; LocalPort = ($port.LocalPort -join ',')
                RemoteAddress = (@($rule | Get-NetFirewallAddressFilter).RemoteAddress -join ',')
            }
        }
    }
}
```

    Ergebnis im Abnahmeprotokoll festhalten. Außer „JanuaPort 443 LAN“ darf
    keine Allow-Regel 443 öffnen. Gibt es eine weitere, wird sie deaktiviert
    oder auf `LocalSubnet` eingeengt. Die benannte Regel muss TCP 443,
    `LocalSubnet` und `Private,Domain` tragen. HTTPS aus dem lokalen Subnetz,
    Abweisung von außerhalb und Unerreichbarkeit von 8484 im LAN belegen.

5. **USB-Sicherung:** Separaten USB-Datenträger mit `.jnpt-backup-ziel`
   vorbereiten. Tägliche Aufgabe und manuellen Aufgabenstart prüfen. Ergebnis
   `LastTaskResult = 0`, genau eine Sicherungsdatei pro Lauf, keine `.teil`,
   keine Key-Datei. Fehlenden Marker, abgezogenen USB-Datenträger, Schreibfehler
   und gestoppten Container prüfen: Aufgabe jeweils fehlgeschlagen.
   Sicherung über `/jnpt backup --output /backups/<name>` im relativen
   Bind-Mount `./backups:/backups` prüfen. Der nonroot-Kern muss dort schreiben
   und atomar umbenennen können. Größen-/SHA-256-Prüfung und Löschen erfolgen
   auf dem Host. `backups\` danach ohne generierte Sicherungsdatei; eine dort
   absichtlich abgelegte fremde Datei bleibt erhalten. Auch Altlastenbereinigung
   darf nur das exakte Namensmuster treffen. Alte Zieldateien bleiben.
   `python -B windows/test/backup_live.py` mit dem echten gepinnten Kern-Image
   ausführen. Bei lokaler Blockade (z. B. seccomp errno 524) bleibt dies offen
   für BOX. Kann UID 65532 im Bind-Mount nicht schreiben/umbenennen, an LEAD
   melden; ein Hilfscontainer-Ersatz ist nicht Teil dieses Pakets.
6. **B-1, Kennwort zurücksetzen:** Vorher synthetische Anlage, Admin-Anmeldung,
   Mailversand und Sicherung nach F4 einschließlich Host-Hash und leerem Staging
   erneut grün belegen. Lokales Kennwort von `jnpt-dienst`
   als Admin zurücksetzen, danach `dienst-einrichten.ps1 -KennwortNeu
   -BackupTarget <USB-Ziel>` aus dem geprüften Profil ausführen. Es erzeugt ein
   weiteres Zufallskennwort und setzt Autologon neu; es zeigt das Kennwort nicht
   an. Neustarten, Sperrbildschirm prüfen. Anlage, Admin-Anmeldung, Mailversand
   und Sicherung müssen wieder grün sein. Master-Key, Admin-Kennwort und
   SMTP-/Graph-Secret hängen an Dateien/Volume, nicht an DPAPI/cmdkey/EFS.
   Bei optionalem SMB die ausschließlich dafür bestimmten Zugangsdaten durch
   den Betreiber erneut unter `jnpt-dienst` eingeben und Sicherung prüfen.
7. **B-4, getrennte Rücksicherung:** Sicherungsdatei auf einen separaten
   Testrechner übertragen, den getrennt verwahrten Master-Key separat nach
   [README, Sicherung/Rücksicherung](README.md#sicherung-b3) zuführen.
   Nach der Wiederherstellungsanleitung der eingesetzten Kern-Version
   zurücksichern. Synthetische Daten, Admin-Anmeldung und erneute Sicherung
   prüfen. Nachweisen, dass am Sicherungsziel nur die Sicherungsdatei liegt und
   die Key-Datei nicht mitkopiert wurde. Ohne `JNPT_MASTER_KEY_FILE` liegt der
   Key neben der DB unter `/data/jnpt.key`; deshalb wird niemals ganz `/data`
   kopiert. Bei frischem Volume sowie nach Erststart das Beiseitelege- und
   Key-Einlege-Muster aus N4 prüfen. Der Kern läuft als UID/GID 65532:
   Key mit Eigentümer 65532:65532 und Modus 600 muss lesbar sein, Restore muss
   bei leerer Ziel-DB erfolgreich sein. Health 200 und Admin-Anmeldung belegen.
   Den Ordner `/data/beiseite-<zeitstempel>` erst löschen, wenn die Rücksicherung geprüft ist (healthz, Anmeldung, Lesezugriff).
   Wer den Block auf eine nicht frische Anlage anwendet, verliert sonst den alten Stand.
   USB anschließend abziehen bzw. lokale Key-Kopie entfernen.
8. **Wartung und Fernzugang:** TeamViewer auf Annahme gemäß AVV Anlage 3:
   ein Mensch beim Betreiber nimmt jede Sitzung an. Kein unbeaufsichtigter
   Fernzugriff, kein festes Fernwartungskennwort. Sperrbildschirm entsperrt der
   Betreiber vor Ort. Wartungskonto startet nur Aufgaben. B5-Update-Aufgabe
   separat nach [PRUEFSTEIN-B5.md](PRUEFSTEIN-B5.md) abnehmen; sie ist ohne Auslöser. Docker-Desktop-Lizenz und
   unterstütztes Windows/ESU separat bestätigen.
2a. **Ausführendes Konto wechseln:** Vorher die bestehende Anlage sichern und
    den Master-Key getrennt verwahren. `jnpt-dienst` für das bestehende Profil
    mit demselben Compose-Projektnamen und denselben Volumes einrichten.
    Daten, Admin-Anmeldung und Lesezugriff sowie den unveränderten Fingerprint
    prüfen. `tls-leaf` bleibt in der gemeinsamen Engine erhalten. Ein reiner
    Kontowechsel erfordert weder Rücksicherung noch erneute Kopplung.
    `docker compose down -v` im früheren Konto würde dieselben Anlagenvolumes
    entfernen und ist kein Aufräumschritt für diesen Kontowechsel.
    Das Wartungskonto verwendet anschließend ausschließlich `schtasks /run`.


Abnahmestatus: **offen**. Auf dem Entwicklungsrechner wird keiner dieser
Systemeingriffe ausgeführt.
