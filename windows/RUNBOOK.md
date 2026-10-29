# Runbook: JanuaPort auf Windows mit Docker Desktop — vor Ort und per Fernsitzung

Dieses Runbook beschreibt den **Ablauf eines Termins** beim Kunden. Was installiert wird und wie,
steht im [README](README.md) dieses Profils. Hier steht, wer wann was tut, was vorher geklärt sein
muss und was nach einem Neustart passiert.

Begriffe: **Kunde** ist die Organisation, in deren Räumen der Rechner steht. Sie ist Betreiber der Anlage
und Verantwortlicher im Sinne des Datenschutzes. **Dienstleister** ist, wer die Anlage für den Kunden
einrichtet und wartet. „Betreiber“ meint in diesem Runbook und im Produkt immer den Kunden.

## 1. Grundregeln

- **Der Rechner ist nur für JanuaPort da.** Er ist kein Arbeitsplatz und hält keine Daten des Kunden.
- **Fernzugang nur auf Annahme.** Der Kunde startet jede Fernsitzung selbst und nennt Kennung und
  Einmal-Kennwort telefonisch. Es gibt kein festes Kennwort und keinen unbeaufsichtigten Zugriff.
  Ist eines davon eingerichtet, wird es abgeschaltet, nicht genutzt.
- **Keine Zwischenablage, keine Dateiübertragung, keine Aufzeichnung** in der Fernsitzung. Alle Befehle
  werden abgetippt. Deshalb sind sie hier kurz gehalten. Längere Dateien lädt der Rechner selbst aus
  diesem Repo, geprüft gegen eine SHA-256-Liste.
- **Keine KI mit Bildschirmzugriff während einer Fernsitzung**, auch wenn die Anlage noch leer ist.
  Werkzeuge mit Bildschirmzugriff sind auf dem Gerät des Dienstleisters abgeschaltet, solange die Sitzung
  offen ist.
- **Die Admin-Oberfläche ist nur am Rechner selbst erreichbar** (`http://127.0.0.1:8484`, im Browser
  des Rechners). Ins lokale Netz geht nur die Geräte-API für die Desktop-Läufer.
- **Kopiert wird nur lokal** auf dem Rechner, etwa ein Schlüssel vom Editor in die Admin-Oberfläche.
  Danach die Datei löschen und die Zwischenablage leeren.

## 2. Vor dem Termin klären

| Was | Wer liefert | Warum |
|---|---|---|
| Der Vertrag mit dem Kunden erlaubt diesen Termin. Bei Kunden mit Berufsgeheimnis heißt das in der Regel: Auftragsverarbeitung und Verpflichtung zur Geheimhaltung sind unterschrieben, oder es ist schriftlich vereinbart, was vorher erlaubt ist. | Dienstleister und Kunde | Ohne Grundlage kein Zugriff |
| Der Kunde bestätigt in Textform, dass der Rechner keine Daten des Kunden hält: keine Netzlaufwerke, keine gespeicherten Zugangsdaten, keine Fachanwendung, keine Mitgliedschaft in der Domäne des Kunden. | Kunde | Nur so darf der Rechner vor der Anbindung von Fachsystemen bearbeitet werden |
| Eine Person beim Kunden, die die Sitzung startet und nach einem Neustart am Rechner anmeldet. Am Rechner hängen Bildschirm und Tastatur. | Kunde | Ohne unbeaufsichtigten Zugriff bricht jede Sitzung beim Neustart ab |
| Ein Zeitfenster, in dem ein Neustart niemanden stört. | Kunde | Docker Desktop verlangt einen Neustart |
| Ein Sicherungsziel außerhalb des Rechners (NAS oder USB-Laufwerk). | Kunde | Backup der Anlage |
| Eine feste Adresse des Rechners im lokalen Netz (DHCP-Reservierung oder statische IP). Nötig erst, wenn Läufer auf anderen Arbeitsplätzen koppeln. | Kunde (IT-Dienstleister) | Die Läufer speichern die Adresse aus `pair`. Der Fingerprint prüft nur das Zertifikat, nicht die Adresse. Ändert sich die Adresse, erreichen die Läufer die Anlage nicht mehr. |

## 3. Ablauf am Termin

### 3.1 Prüfen, bevor etwas installiert wird
In einer Admin-PowerShell:

```powershell
net use
cmdkey /list
(Get-CimInstance Win32_ComputerSystem).PartOfDomain
Get-Tpm
winver
```

- `net use` zeigt keine Laufwerke des Kunden, `cmdkey /list` keine Zugangsdaten des Kunden, `PartOfDomain`
  ist `False`. Sonst bricht der Dienstleister ab und klärt es mit dem Kunden.
- `Get-Tpm` und `winver` werden notiert. Ohne TPM gibt es keine BitLocker-Verschlüsselung mit TPM.
  Das ist vor der Anbindung von Fachsystemen zu klären.
- In der Fernwartungssoftware prüfen: kein unbeaufsichtigter Zugriff, kein festes Kennwort.

### 3.2 Docker Desktop (ein Neustart)
Schritte im [README](README.md#voraussetzungen), Abschnitt „Voraussetzungen“. Vor dem Neustart dem Kunden sagen, dass gleich
eine neue Sitzung nötig ist.

### 3.3 Nach einem Neustart
1. Die Sitzung bricht ab. Der Dienstleister ruft beim Kunden an.
2. Die Person beim Kunden meldet sich am Rechner an, mit dem für die Wartung vereinbarten Konto.
3. Sie startet die Fernwartung und nennt Kennung und neues Einmal-Kennwort.
4. Docker Desktop braucht auf schwacher Hardware nach dem Start einige Minuten. Erst weiterarbeiten,
   wenn `docker version` einen Server zeigt.

### 3.4 Anlage einrichten
Schritte im [README](README.md#zwei-befehle), Abschnitt „Zwei Befehle“. Am Ende gibt `einrichten.ps1` den
Zertifikats-Fingerprint aus. Ihn abschreiben und beim Dienstleister ablegen, nicht beim Kunden aushängen.

**Das Admin-Passwort setzt der Kunde selbst am Rechner, nicht der Dienstleister.** Wer das Admin-Passwort
kennt, verwaltet die Anlage. Der Dienstleister beendet dafür die Fernsitzung. Der Kunde setzt das Passwort in
der Admin-Oberfläche (`http://127.0.0.1:8484`), sichert den Master-Schlüssel und startet danach eine neue
Sitzung. Hat doch der Dienstleister das Passwort gesetzt, setzt der Kunde es neu.

Den Master-Schlüssel der Anlage auf Papier sichern. Das Papier bleibt beim Kunden, an einem verschlossenen Ort.

### 3.5 Desktop-Läufer auf dem Rechner selbst
1. In der Admin-Oberfläche ein Gerät anlegen: Art `dedicated`, gerätebezogener Name wie `desktop-01`,
   kein Personenname. Kopplungscode holen (gilt 15 Minuten).
2. Läufer aus dem Release `desktop-runner-v*` laden und die Prüfsumme gegen `SHA256SUMS` prüfen.
   Dann ohne erhöhte Rechte:
   ```powershell
   .\desktop-runner.exe pair --url https://127.0.0.1 --fingerprint <fingerprint> --code '<Kopplungscode>'
   .\desktop-runner.exe install
   .\desktop-runner.exe status
   ```
3. Das Gerät steht in der Admin-Oberfläche auf grün.

Läufer auf Arbeitsplätzen im lokalen Netz koppeln mit `https://<Adresse des Rechners>` und demselben
Fingerprint. Die CA des Rechners kommt nie in den Zertifikatsspeicher der Arbeitsplätze.

### 3.6 Erster Lauf
Ein harmloses Test-Skript ohne Bezug zum Kunden, etwa eines, das den Editor öffnet, belegt die Kette aus
Anlage, Skript-Läufer, Kopplung und Lauf. Den Zeitplan danach löschen.

## 4. Nach dem Termin
- Den Termin dokumentieren: Datum, Uhrzeit, Person, Zweck. Keine Inhalte vom Bildschirm, keine Daten des Kunden.
- Offene Punkte gehen in das Ticket des Dienstleisters, ohne Namen und ohne Daten des Kunden.

## 5. Typische Fehlerbilder
| Bild | Ursache | Abhilfe |
|---|---|---|
| Nach dem Neustart keine Sitzung möglich | kein unbeaufsichtigter Zugriff (gewollt) | Kunde meldet sich an und startet eine neue Sitzung (3.3) |
| `docker version` zeigt keinen Server | Docker Desktop startet noch oder ist nicht angemeldet | einige Minuten warten; Docker Desktop startet nur in einer angemeldeten Sitzung |
| `pair` scheitert ohne TLS-Fehler | Kopplung über HTTP an einen Container | immer über `https://` mit Fingerprint koppeln |
| Läufer im Netz erreicht die Anlage nicht | Windows-Firewall oder falsche Adresse | Freigabe für 443 aus dem lokalen Netz prüfen |
