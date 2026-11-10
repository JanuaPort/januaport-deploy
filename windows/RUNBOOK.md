# Runbook: JanuaPort auf Windows mit Docker Desktop — vor Ort und per Fernsitzung

Dieses Runbook beschreibt den **Ablauf eines Termins** beim Kunden. Was installiert wird und wie,
steht im [README](README.md) dieses Profils. Hier steht, wer wann was tut, was vorher geklärt sein
muss und was nach einem Neustart passiert.

Begriffe: **Kunde** ist die Organisation, in deren Räumen der Rechner steht. Sie ist Betreiber der Anlage
und Verantwortlicher im Sinne des Datenschutzes. **Dienstleister** ist, wer die Anlage für den Kunden
einrichtet und wartet. „Betreiber“ meint in diesem Runbook und im Produkt immer den Kunden.

## 1. Grundregeln

- **Der Rechner ist nur für JanuaPort da.** Er ist kein Arbeitsplatz und hält keine Daten des Kunden.
- **Fernzugang nur auf Annahme.** TeamViewer auf Annahme gemäß AVV Anlage 3: Ein Mensch beim Kunden
  nimmt jede Sitzung an, startet sie selbst und nennt Kennung und
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
- **Kein KI-Werkzeug sieht echte Daten des Kunden.** Gilt bei Kunden mit Berufsgeheimnis, etwa Praxen.
  - Skripte bauen und testen mit KI nur gegen eine Schulungs- oder Testinstanz des Fachsystems mit eigener
    Datenbank. Tests mit echten Daten macht ein Mensch, ohne KI.
  - Der Kunde bestätigt in Textform, dass diese Instanz nur Testdaten enthält und keine Kopie der echten
    Datenbank ist. Sie läuft auf einem eigenen Rechner oder in einer VM, nicht auf einem Arbeitsplatz, an dem
    auch die echte Fachanwendung offen ist. Ein Bildschirmfoto zeigt sonst beides.
  - Zeigt ein Bildschirm echte Daten, etwa die Fachanwendung oder eine Fernsitzung auf einen Arbeitsplatz,
    ist am Zugriffsgerät kein KI-Werkzeug mit Bildschirmzugriff aktiv. Dazu zählen Computer-Use, eine
    Desktop-App mit Bildschirmfreigabe und Screenshot-Synchronisierung. Das ist ein Prüfpunkt im
    Sitzungsprotokoll (Abschnitt 4).
  - Kein KI-Werkzeug des Dienstleisters hat Datei-, Datenbank- oder Werkzeugzugriff (MCP) auf echte Daten
    des Kunden, auch nicht per Shell auf dem Rechner (Datenbank, Export, Log). KI-Clients des Dienstleisters
    sind nur mit der Schulungs- oder Testinstanz verbunden. Was der Kunde mit seiner eigenen KI tut, ist
    seine Verarbeitung und nicht Teil dieser Regel.
  - Keine Screenshots und keine Logs mit Daten des Kunden in Tickets, Chats oder Notizen bei Dritt-Diensten.
    Gespeichert wird nur auf eigenen, verschlüsselten Geräten des Dienstleisters, nie in Cloud-Ablagen.

## 2. Vor dem Termin klären

| Was | Wer liefert | Warum |
|---|---|---|
| Der Vertrag mit dem Kunden erlaubt diesen Termin. Bei Kunden mit Berufsgeheimnis heißt das in der Regel: Auftragsverarbeitung und Verpflichtung zur Geheimhaltung sind unterschrieben, oder es ist schriftlich vereinbart, was vorher erlaubt ist. | Dienstleister und Kunde | Ohne Grundlage kein Zugriff |
| Der Kunde bestätigt in Textform, dass der Rechner keine Daten des Kunden hält: keine Netzlaufwerke, keine gespeicherten Zugangsdaten, keine Fachanwendung, keine Mitgliedschaft in der Domäne des Kunden. | Kunde | Nur so darf der Rechner vor der Anbindung von Fachsystemen bearbeitet werden |
| Eine Person beim Kunden, die jede Fernsitzung annimmt und nach einem Neustart die lokal automatisch angemeldete, gesperrte Sitzung vor Ort verwaltet. Am Rechner hängen Bildschirm und Tastatur. | Kunde | Ohne unbeaufsichtigten Zugriff bricht jede Sitzung beim Neustart ab |
| Ein Zeitfenster, in dem ein Neustart niemanden stört. | Kunde | Docker Desktop verlangt einen Neustart |
| Ein wechselnder USB-Datenträger als Sicherungsziel v1; optional eine eigene SMB-Freigabe mit eigenem Sicherungsbenutzer und Schreibrecht nur dort. | Kunde | Backup der Anlage |
| Eine feste Adresse des Rechners im lokalen Netz (DHCP-Reservierung oder statische IP). Nötig erst, wenn Läufer auf anderen Arbeitsplätzen koppeln. | Kunde (IT-Dienstleister) | Die Läufer speichern die Adresse aus `pair`. Der Fingerprint prüft nur das Zertifikat, nicht die Adresse. Ändert sich die Adresse, erreichen die Läufer die Anlage nicht mehr. |
| Freigabe für den Desktop-Läufer auf den Arbeitsplätzen, falls eine Richtlinie (etwa AppLocker) oder ein Virenscanner Programme aus dem Benutzerprofil sperrt. Die EXE des Läufers liegt an einem dauerhaften Ort im Benutzerprofil und ist von der JanuaPort GmbH signiert: Regel nach Herausgeber, nicht nach Pfad. Jeder Lauf startet zusätzlich `python.exe` aus `%LOCALAPPDATA%\JanuaPort\desktop-runner\envs\…`. Diese ist von der Python Software Foundation signiert und braucht eine eigene Regel nach Herausgeber für dieses Verzeichnis. Sind DLL-Regeln aktiv, gilt das auch für die Bibliotheken der Skripte. Mit AppLocker ist dieser Weg ungetestet. | Kunde (IT-Dienstleister) | Sonst startet der Läufer nicht, oder er startet und jeder Lauf scheitert |

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

- `net use` zeigt keine Laufwerke des Kunden, außer dem eigenen Sicherungsziel unter `jnpt-dienst`.
  `cmdkey /list` zeigt keine Zugangsdaten des Kunden, außer dem Sicherungsziel unter `jnpt-dienst`.
  `PartOfDomain` ist `False`. Sonst bricht der Dienstleister ab und klärt es mit dem Kunden.
  Der Betreiber prüft die Ausnahme selbst in `jnpt-dienst`; im Wartungskonto liegt kein Sicherungszugang.
  Master-Key, Admin-Kennwort und SMTP-/Graph-Secret gehören nie in cmdkey/DPAPI/EFS.
  SMB-Zugangsdaten werden nach einem Admin-Kennwortreset dort vom Betreiber neu eingegeben (B4).
- `Get-Tpm` und `winver` werden notiert. Ohne TPM gibt es keine BitLocker-Verschlüsselung mit TPM.
  Das ist vor der Anbindung von Fachsystemen zu klären.
- In TeamViewer prüfen: kein unbeaufsichtigter Zugriff, kein festes Kennwort. Gemeint ist
  TeamViewer auf Annahme gemäß AVV Anlage 3; ein Mensch beim Kunden nimmt jede Sitzung an.
  Das lokale Windows-Autologon ist kein unbeaufsichtigter Fernzugang.

### 3.2 Docker Desktop (ein Neustart)
Schritte im [README](README.md#voraussetzungen), Abschnitt „Voraussetzungen“. Vor dem Neustart dem Kunden sagen, dass gleich
eine neue Sitzung nötig ist.

### 3.3 Nach einem Neustart
1. Die Fernsitzung bricht ab. Der Dienstleister ruft beim Kunden an.
2. `jnpt-dienst` meldet sich lokal automatisch an. „JanuaPort Sperren bei Anmeldung“
   startet sofort das B-7-geschützte `C:\JanuaPort\windows\jnpt-sperren.ps1`.
   Es prüft Explorer derselben Sitzung und den WTS-Sperrstatus im Sekundentakt;
   für beides zusammen gelten 120 Sekunden. Fehler sind als `LastTaskResult`
   ungleich 0 sichtbar; kein Ersatz durch Abmelden oder Herunterfahren.
   `log\sperren.log` enthält eine Zeile je Anmeldung (Startzeit, Sperrzeit oder
   `nicht_gesperrt`, Versuche, Exit-Code), höchstens 100 Zeilen, ohne Benutzernamen.
   Der Betreiber drückt ab dem ersten Bild alle 5 Sekunden eine Taste und
   notiert die früheste Kennwortabfrage. Aufgabenresultat 0 und Protokollzeit
   kommen zusammen mit dem Foto in den Gate-Bericht. Bis der Desktop steht,
   schützt nur der kontrollierte Zutritt zum Raum die noch ungesperrte Sitzung.
3. Die Person beim Kunden startet/akzeptiert eine neue TeamViewer-Sitzung nach dem vereinbarten
   Verfahren. Der Dienstleister verwendet ausschließlich das Wartungskonto und arbeitet nie als
   `jnpt-dienst`. Das Wartungskonto stößt nur Aufgaben mit `schtasks /run` an.
4. Docker Desktop startet in `jnpt-dienst`; einige Minuten bis zur Bereitschaft berücksichtigen.
   Engine und Volumes nicht aus dem Wartungskonto beurteilen. Maßgeblich ist der Aufgabenstatus.

### 3.4 Anlage einrichten
Vor `dienst-einrichten.ps1` Docker Desktop einmal als `jnpt-dienst` starten,
Lizenz annehmen und AutoStart an, TCP 2375 aus sowie automatische Updates aus
setzen. Fehlt das Konto noch, legt ein erster B2-Vorbereitungslauf es an und
endet mit „Docker Desktop einmal in jnpt-dienst starten und die Einstellungen pruefen (AutoStart an, 2375 aus, Auto-Update aus)“.
Der Betreiber setzt dann lokal vorübergehend ein Kennwort, meldet sich als
`jnpt-dienst` an und startet Docker Desktop. Danach die administrative
[B2-Einrichtung](README.md#dienstbetrieb-b2) mit `-KennwortNeu` erneut ausführen;
Autologon wird alle 500 ms bis höchstens 10 Sekunden nachgeprüft. Neustarten.
B-7: `icacls C:\JanuaPort` und `icacls C:\JanuaPort\windows` zeigen ausschließlich
`jnpt-dienst`, Administratoren und SYSTEM. Vererbung vom Laufwerksstamm ist aus.
F5: Die Einrichtung ersetzt die vollständige DACL in einem einzigen
Access-Schreibaufruf. R4: Nur eine geschützte DACL mit genau drei expliziten
Allow-ACEs für die genannten SIDs, jeweils FullControl, ContainerInherit und
ObjectInherit, ohne InheritOnly oder NoPropagate und ohne weitere explizite
oder geerbte Allow-/Deny-ACEs bleibt ohne Schreibzugriff erhalten. Jede
Abweichung wird ersetzt. Besitzer und andere Sicherheitsabschnitte bleiben unverändert.
Bei einem Altprofil den [Upgrade-Weg 0.1.0 → 0.2.0](README.md#von-010-auf-020) und
die zusätzliche Abnahme in B4 verwenden. Die
Erstkonfiguration von Docker Desktop und die Schritte in [„Zwei Befehle“](README.md#zwei-befehle)
führt der Betreiber in `jnpt-dienst` aus. Danach startet das Wartungskonto nur Aufgaben.
Am Ende gibt `einrichten.ps1` den
Zertifikats-Fingerprint aus. Ihn abschreiben und beim Dienstleister ablegen, nicht beim Kunden aushängen.
Beim Kontowechsel verbleibt `tls-leaf` in der alten Engine. Nach B4-Schritt 2a
alle Desktop-Läufer mit neuem Code und dem neuen Fingerprint erneut koppeln.

Mail anschließend durch den Betreiber in `jnpt-dienst` gemäß [README, Abschnitt „Mail“](README.md#mail)
einrichten. USB-Ziel und Marker vorbereiten, Aufgabe „JanuaPort Sicherung“ prüfen.
Die Einrichtung legt `backups\` im B-7-geschützten Profilordner an. Der Kern
schreibt dort über den relativen Bind-Mount `/backups`; Größe, Hash, Zielkopie
und Aufräumen erfolgen auf dem Host. Schreibrecht und atomisches Rename durch
den nonroot-Kern sowie alle USB-Fehlerfälle in B4/F4 erneut belegen.
Master-Key getrennt von Sicherungen verwahren. Ein vom Rechner beschreibbares Ziel schützt nicht
gegen einen Angreifer auf dem Rechner; wechselndes, abgezogenes USB dagegen schon. Die Wahl
trifft der Betreiber. Wiederherstellung nach Kennwortreset und getrennte Rücksicherung gemäß
[Prüfstein B4](PRUEFSTEIN-B4.md) belegen.
Für eine frische Installation den getrennten Key vor dem ersten Start einlegen;
nach Erststart DB und erzeugten Key bei gestoppter Anlage beiseitelegen.
Die festen Befehle stehen unter [Rücksicherung (N4)](README.md#rücksicherung-in-eine-frische-installation-n4).
Nach der Rücksicherung healthz, Admin-Anmeldung und Lesezugriff prüfen.
Den Ordner `/data/beiseite-<zeitstempel>` erst löschen, wenn die Rücksicherung geprüft ist (healthz, Anmeldung, Lesezugriff).
Wer den Block auf eine nicht frische Anlage anwendet, verliert sonst den alten Stand.

**Das Admin-Passwort setzt der Kunde selbst am Rechner, nicht der Dienstleister.** Wer das Admin-Passwort
kennt, verwaltet die Anlage. Der Dienstleister beendet dafür die Fernsitzung. Der Kunde setzt das Passwort in
der Admin-Oberfläche (`http://127.0.0.1:8484`), sichert den Master-Schlüssel und startet danach eine neue
Sitzung. Hat doch der Dienstleister das Passwort gesetzt, setzt der Kunde es neu.

Den Master-Schlüssel der Anlage auf Papier sichern. Das Papier bleibt beim Kunden, an einem verschlossenen Ort.

#### F5-Reparatur nach entzogenen Dateirechten

Falls `978b7eb` oder `6bb0d8f` bereits gelaufen ist und Dateien wegen leerer
DACL unlesbar sind, im geprüften **F5-Releaseordner** als Administrator
`takeown`, dann `icacls /reset` und unmittelbar die neue Diensteinrichtung
ausführen; das Sicherungsziel anpassen. Die Reparatur ist ein manueller
Wartungsschritt. Auf deutschem Windows ist `/d j` richtig (lokal mit
`takeown /?` bestätigt), auf englischem Windows stattdessen `/d y` verwenden.
Danach ist der angemeldete Administrator Besitzer; das ist in Ordnung.
Die abschließende Diensteinrichtung setzt die B-7-DACL wieder auf genau die
drei Prinzipale. Anschließend Lesbarkeit von `.env`, `secrets\` und
`log\sperren.log`, Anlagenstart und Sicherung erneut prüfen.

<!-- F5 -->
```powershell
takeown /f C:\JanuaPort /r /d j
icacls C:\JanuaPort /reset /t
.\dienst-einrichten.ps1 -BackupTarget 'E:\JanuaPort-Backup'
```

### 3.5 LAN-Freigabe vor dem Koppeln (N5)

In B4 fand sich keine Allow-Regel für Docker. Docker Desktop hatte nur zwei
Block-Regeln für das Profil „Öffentlich“ angelegt, weil der Firewall-Dialog
unbeantwortet blieb. Was bei „Zulassen“ entsteht, ist nicht gemessen.
Den Firewall-Dialog von Docker Desktop nicht mit ‚Zulassen‘ für öffentliche Netze beantworten.
Der Betreiber bzw. seine IT prüft in einer administrativen PowerShell das
Netzprofil: **Privat** oder **Domäne**. Ein öffentliches Netz erst nach Prüfung
als vertrauenswürdiges privates Netz einordnen. Dann TCP 443 ausschließlich
für das lokale Subnetz freigeben:

<!-- N5 -->
```powershell
Get-NetConnectionProfile
New-NetFirewallRule -DisplayName 'JanuaPort 443 LAN' -Direction Inbound -Protocol TCP -LocalPort 443 -RemoteAddress LocalSubnet -Action Allow -Profile Private,Domain
```

Kein `Any` bei Gegenstellen. Die Regel gilt nur für `Private,Domain`.
`einrichten.ps1` ändert weder Firewall noch Netzprofil; dieser Schritt bleibt
beim Menschen. HTTPS anschließend von einem Arbeitsplatz im lokalen Subnetz
prüfen. Port 8484 bleibt am Server auf Loopback beschränkt.

#### N5-1: Firewall bei jeder echten Abnahme prüfen

In einer administrativen PowerShell alle aktiven eingehenden Allow-Regeln
mit Docker-Anwendungsfilter sowie alle Portfilter auflisten, die 443 öffnen
(auch `Any`, Portlisten und Bereiche). Die folgende Prüfung liest nur:

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

Ergebnis im Abnahmeprotokoll festhalten. Außer „JanuaPort 443 LAN“ darf keine
Allow-Regel 443 öffnen. Gibt es eine weitere, wird sie deaktiviert oder auf
`LocalSubnet` eingeengt. Auch die benannte Regel auf TCP 443, `LocalSubnet`
und `Private,Domain` prüfen. Danach HTTPS aus dem lokalen Subnetz und die
Abweisung von außerhalb sowie die Unerreichbarkeit von 8484 im LAN belegen.


### 3.6 Desktop-Läufer auf dem Rechner selbst
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

### 3.7 Erster Lauf
Ein harmloses Test-Skript ohne Bezug zum Kunden, etwa eines, das den Editor öffnet, belegt die Kette aus
Anlage, Skript-Läufer, Kopplung und Lauf. Den Zeitplan danach löschen.

## 4. Sitzungsprotokoll
Je Sitzung ein Eintrag beim Dienstleister: Datum, Uhrzeit, Person, Zweck. Keine Inhalte vom Bildschirm, keine
Daten des Kunden. Vor dem Start hakt die Person ab:

- [ ] Der Kunde hat die Sitzung angenommen.
- [ ] Am Zugriffsgerät ist kein KI-Werkzeug mit Bildschirmzugriff aktiv: kein Computer-Use, keine Desktop-App
      mit Bildschirmfreigabe, keine Screenshot-Synchronisierung.
- [ ] Kein KI-Werkzeug des Dienstleisters hat Datei-, Datenbank- oder Werkzeugzugriff (MCP) auf echte Daten;
      KI-Clients sind nur mit der Schulungs- oder Testinstanz verbunden.
- [ ] Zeigt die Sitzung echte Daten? Dann wird nur von Hand gearbeitet, ohne KI.

## 5. Nach dem Termin
- Offene Punkte gehen in das Ticket des Dienstleisters, ohne Namen und ohne Daten des Kunden.

## 6. Typische Fehlerbilder
| Bild | Ursache | Abhilfe |
|---|---|---|
| Nach dem Neustart keine Sitzung möglich | kein unbeaufsichtigter Zugriff (gewollt) | Mensch beim Kunden nimmt TeamViewer erneut an (3.3); Wartung nur über Wartungskonto |
| `docker version` zeigt keinen Server | Docker Desktop startet noch oder ist nicht angemeldet | einige Minuten warten; Docker Desktop startet nur in einer angemeldeten Sitzung |
| `pair` scheitert ohne TLS-Fehler | Kopplung über HTTP an einen Container | immer über `https://` mit Fingerprint koppeln |
| Läufer im Netz erreicht die Anlage nicht | Windows-Firewall oder falsche Adresse | Netzprofil Privat/Domäne und Regel „JanuaPort 443 LAN“ gemäß 3.5 prüfen (`LocalSubnet`, TCP 443) |
