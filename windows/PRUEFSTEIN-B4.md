# Prüfstein B4: Dienstbetrieb und Wiederherstellung

Offene Abnahme auf einem eigenen Testrechner mit ausschließlich synthetischen
Daten. Die Python-Fakes ersetzen diesen Nachweis nicht. Ergebnis, Windows- und
Docker-Version, Backend, Uhrzeit und Nachweis je Schritt im Abnahmeprotokoll
festhalten; keine Geheimnisse oder Daten des Betreibers aufnehmen.

1. **Engine und Volumes je Benutzer (Hauptfund):** Docker Desktop mit WSL 2
   in `jnpt-dienst` starten. Mit `docker context show`, `docker info --format
   '{{.ID}}'` und `docker volume ls` Engine und synthetisches Test-Volume
   identifizieren. Unter einem zweiten lokalen Konto separat prüfen, ob dieselbe
   Engine und dasselbe Volume sichtbar sind. Nicht gleichzeitig konkurrierende
   Docker-Desktop-Instanzen starten. Beide Ergebnisse dokumentieren. Die
   [Docker-Doku](https://docs.docker.com/desktop/setup/install/windows-install/)
   sagt ausdrücklich, dass Container und Images mit dem WSL-2-Backend nicht
   zwischen Konten geteilt werden können; Volumes benennt diese Passage nicht.
   Andere Backends dürfen aus diesem Befund nicht abgeleitet werden.
2. **Upgrade 0.1.0 → 0.2.0 am Testrechner einmal gehen.** Von den drei
   Originaldateien plus `.env` ausgehen (alte Summenliste optional), neues
   Einrichtungsskript verwenden. Vollständiges 0.2.0-Profil, unveränderte `.env`
   und Secrets, bisheriges Kern-Image und Zertifikat prüfen; zweiter Lauf ohne
   Download. Profilpfad und Windows-Konto separat prüfen: keine automatische
   Migration einer Engine oder ihrer Volumes zwischen Konten.
3. **B-7, Ordnerrechte:** Nach Diensteinrichtung `icacls C:\JanuaPort` und
   `icacls C:\JanuaPort\windows` prüfen. Nur `jnpt-dienst`, Administratoren und
   SYSTEM dürfen eingetragen sein. Keine Rechte für Benutzer oder
   Authentifizierte Benutzer. Mit einem anderen Standardkonto den Lesezugriff
   auf `secrets/smtp_password` und den Schreibzugriff auf `docker-compose.yml`
   tatsächlich versuchen: beide müssen scheitern. Erst dann weiterarbeiten.
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
5. **USB-Sicherung:** Separaten USB-Datenträger mit `.jnpt-backup-ziel`
   vorbereiten. Tägliche Aufgabe und manuellen Aufgabenstart prüfen. Ergebnis
   `LastTaskResult = 0`, genau eine Sicherungsdatei pro Lauf, keine `.teil`,
   keine Key-Datei. Fehlenden Marker, abgezogenen USB-Datenträger, Schreibfehler
   und gestoppten Container prüfen: Aufgabe jeweils fehlgeschlagen. Container-
   Kopie nach erfolgreichem Hashvergleich entfernt. Alte Zieldateien bleiben.
6. **B-1, Kennwort zurücksetzen:** Vorher synthetische Anlage, Admin-Anmeldung,
   Mailversand und Sicherung grün belegen. Lokales Kennwort von `jnpt-dienst`
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
   USB anschließend abziehen bzw. lokale Key-Kopie entfernen.
8. **Wartung und Fernzugang:** TeamViewer auf Annahme gemäß AVV Anlage 3:
   ein Mensch beim Betreiber nimmt jede Sitzung an. Kein unbeaufsichtigter
   Fernzugriff, kein festes Fernwartungskennwort. Sperrbildschirm entsperrt der
   Betreiber vor Ort. Wartungskonto startet nur Aufgaben. B5-Update-Aufgabe
   bleibt bis zu deren eigenem Paket offen. Docker-Desktop-Lizenz und
   unterstütztes Windows/ESU separat bestätigen.
2a. **Kontowechsel der Daten:** Eine 0.1.0-Anlage, die unter einem persönlichen Konto lief, per `jnpt backup` sichern, unter `jnpt-dienst` neu einrichten und mit dem getrennt verwahrten Master-Key gemäß README zurückspielen. Das TLS-Zertifikat hängt am Volume `tls-leaf` der alten Engine; unter `jnpt-dienst` entsteht ein neues mit neuem Fingerprint. Alle gekoppelten Desktop-Läufer nach 2a mit neuem Code und neuem, lokal vertrauenswürdig übermitteltem Fingerprint erneut koppeln und prüfen. Danach Anmeldung und ein Lesewerkzeug grün. Dann im alten Konto `docker compose down -v`; `docker volume ls` im alten Konto zeigt kein `jnpt-windows_*`-Volume mehr (SEC E1).

Abnahmestatus: **offen**. Auf dem Entwicklungsrechner wird keiner dieser
Systemeingriffe ausgeführt.
