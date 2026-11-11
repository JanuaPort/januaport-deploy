# Prüfstein B5: Update unter Windows

**Abnahmestatus: offen — BOX auf VM `jnpt-b4`, vor dem Tag `windows-v0.3.0`.**
Nur synthetische Daten und ein kontrollierter Test-Feed. Keine Geheimnisse,
Benutzernamen oder Daten des Betreibers im Bericht. Zeitpunkt, Windows-/Docker-
Version, Backend, Profil-Commit und Nachweis je Schritt lokal festhalten.
Die Adaptertests ersetzen diese Abnahme nicht. B4 gilt ergänzend weiter.

- [ ] **Profil 0.2.0 → 0.3.0:** Mit dem unveränderten veröffentlichten
  `windows-v0.2.0`-Profil und gefüllten synthetischen `.env`-/Secret-Dateien
  beginnen. Neues `einrichten.ps1` in `jnpt-dienst` ausführen; vollständiges
  0.3.0-Profil, unveränderte `.env` und Secrets, altes Kern-Image und Zertifikat
  belegen. Zweiter Lauf ohne Download. Eine geänderte Originaldatei muss das
  automatische Upgrade sperren. `dienst-einrichten.ps1` aus dem geprüften
  0.3.0-Release als Admin mit bisherigem `-BackupTarget` wiederholen.
  „JanuaPort Update“ hat `jnpt-dienst`, Interactive/Limited, `IgnoreNew`,
  keinen Auslöser und ein `EncodedCommand` mit genau diesem Sicherungsziel.
- [ ] **Feed und Freigabe:** Zunächst leere/fehlende Werte für
  `JNPT_UPDATE_MANIFEST_URL` und `JNPT_UPDATE_PUBLIC_KEYS`: Plan `none`, nur
  `record none`, keine Sicherung und kein Pull. Dann Test-Feed und öffentliche
  Schlüssel gemäß Kernformat in `.env` setzen und in `jnpt-dienst` mit
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
  eingerichtete TLS-Fingerprint. Image nur in der Engine von `jnpt-dienst`
  nachweisen; im Wartungskonto keine zweite Installation starten.
- [ ] **USB weg → Exit 3:** USB abziehen und ein weiteres freigegebenes
  Test-Update anstoßen. `LastTaskResult=3`, `.env` bytegleich, kein Pull und
  kein `up -d`. Log meldet Sicherungsfehler; es wird kein anderes Ziel verwendet.
  USB wieder anstecken, Marker und vorhandene Sicherungen prüfen.
- [ ] **Erzwungen rot → Exit 6 und Rückweg:** Mit kontrolliertem Test-Image
  Health 503 bzw. falschen TLS-Fingerprint hervorrufen. Genau ein `up -d`,
  `record failed` mit Digest, `LastTaskResult=6`; neuer Stand bleibt erhalten.
  Alte zwei Zeilen stehen im Log. Nach [RUNBOOK, Update](RUNBOOK.md#7-update-b5)
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
  fester Fehlermeldung, Log und `LastTaskResult=2`; Docker-Aufruf höchstens
  30 Sekunden. Kein endloses Warten und keine Änderung an `.env`. Nach
  Bereitschaft erneut anstoßen und erfolgreichen Lauf belegen. B4-Sperre bleibt
  wirksam. Laufprotokoll höchstens 100 Zeilen ohne Benutzernamen, keine nativen
  Ausgaben und keine Secrets. Die alten zwei Zeilen für den Rückweg vor einem
  späteren Lauf separat lokal festhalten.

Ergebnis und offene Abweichungen an GATE geben. Erst nach vollständiger Abnahme
kann der Auftraggeber den Profil-Tag veröffentlichen. Dieses Paket erzeugt
keinen Tag und führt auf dem Entwicklungsrechner keine dieser Systemänderungen aus.
