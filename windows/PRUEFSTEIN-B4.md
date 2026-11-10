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
2. **W4/W5, B-3, Neustart:** `dienst-einrichten.ps1` auf dem Testrechner als
   Admin einrichten, Docker-Einstellungen in `jnpt-dienst` von Hand prüfen,
   erneut prüfen lassen. Neustarten. Foto des erreichten Sperrbildschirms
   aufnehmen (ohne personenbezogene Inhalte). Sperre bei Anmeldung und nach
   einer Minute Inaktivität einschließlich Kennwortpflicht tatsächlich testen.
   Prüfen, dass Docker Desktop und Anlage trotz gesperrter Sitzung laufen.
   `docker-users` ist praktisch Admin und keine Schutzgrenze. Das Wartungskonto
   löst ausschließlich die Aufgaben aus, z. B. `schtasks /run /tn "JanuaPort
   Sicherung"`; keine Anmeldung/Arbeit des Dienstleisters als `jnpt-dienst`.
3. **USB-Sicherung:** Separaten USB-Datenträger mit `.jnpt-backup-ziel`
   vorbereiten. Tägliche Aufgabe und manuellen Aufgabenstart prüfen. Ergebnis
   `LastTaskResult = 0`, genau eine Sicherungsdatei pro Lauf, keine `.teil`,
   keine Key-Datei. Fehlenden Marker, abgezogenen USB-Datenträger, Schreibfehler
   und gestoppten Container prüfen: Aufgabe jeweils fehlgeschlagen. Container-
   Kopie nach erfolgreichem Hashvergleich entfernt. Alte Zieldateien bleiben.
4. **B-1, Kennwort zurücksetzen:** Vorher synthetische Anlage, Admin-Anmeldung,
   Mailversand und Sicherung grün belegen. Lokales Kennwort von `jnpt-dienst`
   als Admin zurücksetzen, danach `dienst-einrichten.ps1 -KennwortNeu
   -BackupTarget <USB-Ziel>` aus dem geprüften Profil ausführen. Es erzeugt ein
   weiteres Zufallskennwort und setzt Autologon neu; es zeigt das Kennwort nicht
   an. Neustarten, Sperrbildschirm prüfen. Anlage, Admin-Anmeldung, Mailversand
   und Sicherung müssen wieder grün sein. Master-Key, Admin-Kennwort und
   SMTP-/Graph-Secret hängen an Dateien/Volume, nicht an DPAPI/cmdkey/EFS.
   Bei optionalem SMB die ausschließlich dafür bestimmten Zugangsdaten durch
   den Betreiber erneut unter `jnpt-dienst` eingeben und Sicherung prüfen.
5. **B-4, getrennte Rücksicherung:** Sicherungsdatei auf einen separaten
   Testrechner übertragen, den getrennt verwahrten Master-Key separat zuführen.
   Nach der Wiederherstellungsanleitung der eingesetzten Kern-Version
   zurücksichern. Synthetische Daten, Admin-Anmeldung und erneute Sicherung
   prüfen. Nachweisen, dass am Sicherungsziel nur die Sicherungsdatei liegt und
   die Key-Datei nicht mitkopiert wurde. Ohne `JNPT_MASTER_KEY_FILE` liegt der
   Key neben der DB in `/data`; deshalb wird niemals ganz `/data` kopiert.
6. **Wartung und Fernzugang:** TeamViewer auf Annahme gemäß AVV Anlage 3:
   ein Mensch beim Betreiber nimmt jede Sitzung an. Kein unbeaufsichtigter
   Fernzugriff, kein festes Fernwartungskennwort. Sperrbildschirm entsperrt der
   Betreiber vor Ort. Wartungskonto startet nur Aufgaben. B5-Update-Aufgabe
   bleibt bis zu deren eigenem Paket offen. Docker-Desktop-Lizenz und
   unterstütztes Windows/ESU separat bestätigen.

Abnahmestatus: **offen**. Auf dem Entwicklungsrechner wird keiner dieser
Systemeingriffe ausgeführt.
