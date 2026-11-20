# Prüfstein B5: Update unter Windows

**Abnahmestatus: GRÜN @`a87f571` — BOX auf VM `jnpt-b4`, Protokoll
`c-6796028725` auf #1246.** Der Tag `windows-v0.3.0` ist veröffentlicht. Die folgende Checkliste gilt
auch für weitere Abnahmen des Profils.
**Audit-Nachzug, SEC B1:** #1498 ist **gebaut, nicht an NTFS belegt**;
für #1499 ist die **Abnahme mit echtem Docker Desktop offen**. Die frühere
grüne B5-Abnahme gilt für den veröffentlichten Stand, nicht für diese Fixes.
Kein neuer `windows-v*`-Tag, bevor der Fremdbesitzer-NTFS-Prüfstein aus B4
(Ordner und Datei → BA; fremdes `icacls /grant` scheitert) und der langsame
Pull-/Start- und Zertifikatsabfrage-Prüfstein für #1499 unten auf der Test-VM grün sind.
Nur synthetische Daten. Feed: VENDOR-Feed oder ein öffentlich erreichbarer
Test-Feed; private Ziele (auch host.docker.internal) sperrt der SSRF-Schutz des Kerns.
Keine Geheimnisse,
Benutzernamen oder Daten des Betreibers im Bericht. Zeitpunkt, Windows-/Docker-
Version, Backend, Profil-Commit und Nachweis je Schritt lokal festhalten.
Die Adaptertests ersetzen diese Abnahme nicht. B4 gilt ergänzend weiter.

- [ ] **Profil-Upgrade:** Mit den unveränderten veröffentlichten Profilen
  `windows-v0.2.0` (elf Profil-Dateien) und `windows-v0.3.0` (13 Profil-Dateien)
  getrennt beginnen, jeweils mit gefüllten synthetischen `.env`-/Secret-Dateien.
  Neues `einrichten.ps1` in `jnpt-dienst` ausführen; vollständiges Zielprofil
  des geprüften Release, unveränderte `.env` und Secrets, altes Kern-Image und Zertifikat
  belegen. Zweiter Lauf ohne Download. Eine geänderte Originaldatei muss das
  automatische Upgrade sperren. `dienst-einrichten.ps1` aus dem geprüften
  Zielrelease als Admin mit bisherigem `-BackupTarget` wiederholen.
  „JanuaPort Update“ hat `jnpt-dienst`, Interactive/Limited, `IgnoreNew`,
  keinen Auslöser und ein `EncodedCommand` mit genau diesem Sicherungsziel.
- [ ] **Feed und Freigabe:** Zunächst leere/fehlende Werte für
  `JNPT_UPDATE_MANIFEST_URL` und `JNPT_UPDATE_PUBLIC_KEYS`: Plan `none`, nur
  `record none`, keine Sicherung und kein Pull. Anschließend die vorgesehene
  Feed-URL und öffentliche Schlüssel gemäß Kernformat in `.env` setzen und in `jnpt-dienst` mit
  `docker compose up -d --force-recreate jnpt` übernehmen. In der lokalen
  Admin-GUI das Test-Update freigeben. Signatur, Version und Freigabe bleiben
  Kernaufgabe; das Host-Skript trifft keine eigene Entscheidung.
- [ ] **Anstoß aus dem Wartungskonto:** Vorher `icacls
  C:\JanuaPort\windows\.env` lokal festhalten. Die tägliche Sicherung um
  20:00 muss beendet sein (Abstimmung nach RUNBOOK, keine neue technische Sperre).
  `schtasks /run /tn "JanuaPort Update"` ausführen. Abschluss abwarten:
  `Get-ScheduledTaskInfo -TaskName 'JanuaPort Update'` zeigt `LastTaskResult=0`.
  LastTaskResult entspricht dem Exit-Code des Skripts; das auch für die
  Aufgabe „JanuaPort Sicherung“ prüfen.
  `log\update.log` lesen, Admin-GUI zeigt „installiert“.
- [ ] **Sicherung und unveränderliche Referenz:** Neue, geprüfte Sicherung
  von vor dem Wechsel am markierten USB-Ziel; keine `.teil` und keine Key-Kopie.
  Reihenfolge Plan → Sicherung → Pull → alte zwei Image-Zeilen im Log →
  Austausch → `up -d` → Host-Health/TLS → `record installed` belegen. Image
  ausschließlich `ghcr.io/januaport/januaport@sha256:<64 kleine Hex-Zeichen>`.
  `.env` enthält nur die zwei geänderten Image-Zeilen, UTF-8 ohne BOM;
  `icacls .env` ist vor/nach dem Austausch gleich. Host-Health 200 und derselbe
  eingerichtete TLS-Fingerprint. Das neue Image in der gemeinsamen Engine
  nachweisen. Es gibt eine Engine; wer in `docker-users` ist, erreicht die
  Container. Nur `jnpt-dienst` gehört in diese Gruppe. Das Wartungskonto stößt
  nur Aufgaben mit `schtasks /run` an und ruft nie selbst `docker` auf;
  das ist eine Betriebsregel, keine technische Trennung. Jedes lokale
  Admin-Konto erreicht Container, Datenvolume, Master-Key und `.env`.
  Nachweis: `Get-LocalGroupMember Administrators` und `docker-users`
  protokollieren; das Betreiber-Konto ist Standardbenutzer und steht nicht in
  `docker-users`.
- [ ] **USB weg → Exit 3:** USB abziehen und ein weiteres freigegebenes
  Test-Update anstoßen. `LastTaskResult=3`, `.env` bytegleich, kein Pull und
  kein `up -d`. Log meldet Sicherungsfehler; es wird kein anderes Ziel verwendet.
  USB wieder anstecken, Marker und vorhandene Sicherungen prüfen.
- [ ] **Erzwungen rot → Exit 6 und Rückweg:** Den ursprünglichen `key.pem`
  aus dem Volume `tls-leaf` lokal geschützt für den Rückweg sichern. Darin
  einen fremden, nicht zu `cert.pem` passenden `key.pem` hinterlegen und das
  freigegebene Update anstoßen. Caddy teilt das Netz mit `jnpt` und wird mit
  ihm neu erzeugt. Das getauschte Leaf allein erzwingt deshalb keinen roten
  Lauf; das unpassende Schlüsselpaar verhindert hier erfolgreiches TLS.
  Genau ein `up -d`,
  `record failed` mit Digest, `LastTaskResult=6`; neuer Stand bleibt erhalten.
  Alte zwei Zeilen stehen im Log. Den ursprünglichen `key.pem` wiederherstellen.
  Nach [RUNBOOK, Update](RUNBOOK.md#7-update-b5)
  von Hand zurückschreiben und `docker compose up -d`, Health, Fingerprint,
  Admin-Anmeldung und Daten prüfen. Bei einer Migration die Sicherung von
  vor dem Update mit dem alten Image und getrenntem Master-Key bei leerer
  Ziel-DB einspielen. Vorhandene DB/Key bei gestoppter Anlage beiseitelegen.
  Den Ordner `/data/beiseite-<zeitstempel>` erst löschen, wenn die Rücksicherung geprüft ist (healthz, Anmeldung, Lesezugriff).
  Wer den Block auf eine nicht frische Anlage anwendet, verliert sonst den alten Stand.
- [ ] **Nicht buchbares Ergebnis und `rollback`:** Kontrolliert die Buchung
  scheitern lassen. Nur Logeintrag, unveränderter Lauf-Exit (0 bzw. 6), keine
  native Ausgabe. Plan `rollback` liefert Exit 2 und RUNBOOK-Verweis, ohne
  Sicherung, Pull, `up`, Restore oder `record`. `approved` und `unattended`
  durchlaufen denselben technischen Ablauf. Ungültige Digests inklusive
  Großbuchstaben und abschließendem Zeilenumbruch ergeben Exit 2 vor Sicherung.
- [ ] **Neustart vor Docker-Bereitschaft:** Neu starten und die Aufgabe
  unmittelbar vor bereiter Engine anstoßen. Begrenzter, lauter Abbruch mit
  fester Fehlermeldung, Log und `LastTaskResult=2`; Plan-Aufruf höchstens
  30 Sekunden. Kein endloses Warten und keine Änderung an `.env`. Nach
  Bereitschaft erneut anstoßen und erfolgreichen Lauf belegen. B4-Sperre bleibt
  wirksam. Laufprotokoll höchstens 100 Zeilen ohne Benutzernamen, keine nativen
  Ausgaben und keine Secrets. Die alten zwei Zeilen für den Rückweg vor einem
  späteren Lauf separat lokal festhalten.
- [ ] **#1499, langsames Docker:** Pull und `compose up -d` getrennt mit mehr
  als 30 Sekunden Laufzeit nachstellen. Bis Prozessende keine Ergebnisbuchung;
  Erfolg erst nach Health/TLS als `installed`, echter Startfehler nach dessen
  Ende als `failed`. Bei einem befristeten Plan-Test muss auch der native
  Nachfahre beendet sein. Lokale Shim-Regression ersetzt diese Docker-Abnahme nicht.
- [ ] **#1499, langsame Zertifikatsabfrage:** Den exakten `compose run --rm
  --no-deps --entrypoint openssl cert-init x509 …`-Aufruf bei schlechter Leitung
  prüfen (BOX: 37–48 Sekunden, sonst rund 1 Sekunde). Seine Frist beträgt
  300 Sekunden; Plan und Ergebnisbuchung bleiben bei 30 Sekunden. Ein gesundes
  Update muss anschließend `installed` liefern. Bei Fristablauf muss der ganze
  Prozessbaum per `taskkill /T /F` beendet sein, bevor der Fehler gebucht wird.

Ergebnis und offene Abweichungen an GATE geben. Erst nach vollständiger Abnahme
kann der Auftraggeber den Profil-Tag veröffentlichen. Dieses Paket erzeugt
keinen Tag und führt auf dem Entwicklungsrechner keine dieser Systemänderungen aus.
