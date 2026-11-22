# hetzner/ — Terraform-Vorlage für Hetzner Cloud

**Status: von JanuaPort GmbH betrieben (Showcase-Muster).** Dieses Modul ist
generisch aus dem Terraform-Modul abgeleitet, das unseren eigenen
Showcase trägt — ohne unsere konkreten Werte (Domain,
Tailnet-Name, Kontoname, Tokens, IPs). Es provisioniert eine
**Single-Node**-VM (kein k8s, kein Postgres — ein Server). Nach der manuellen
Geheimnisablage startet der Betreiber den gehärteten Drei-Container-Stack aus
dem Produkt-Repo (`jnpt` + `caddy` + `tailscale`-Sidecar).

**Terraform-Hinweis (JanuaPort/januaport#776):** Ist Terraform in der eigenen
Umgebung verfügbar, vor dem `apply` zusätzlich `terraform fmt -check -recursive`
und `terraform validate` fahren. Ist es nicht verfügbar, gilt: Prüfung durch
Lesen statt Behauptung.

## Voraussetzungen

- Terraform ≥ 1.5, Provider `hetznercloud/hcloud` (`terraform init` lädt ihn).
- Ein Hetzner-Cloud-Projekt + API-Token (Read & Write).
- Ein Tailscale-Konto + Auth-Key für den Drei-Container-Stack und die
  Admin-Fläche im Tailnet (siehe „Sicherheits-Defaults").
- Eine eigene Domain mit Zugriff auf die DNS-Zone (A-Record nach `apply`).
- Ein gepinnter JanuaPort-Image-Tag aus der Registry.
- Zugriff auf das **private** Produkt-Repo `JanuaPort/januaport` für Compose,
  Caddy/Tailscale-Konfiguration und Host-Aktuator. Beim Default ist die Datei
  `/etc/jnpt-bootstrap/git_token` mit `Contents: read-only` Pflicht; ein
  öffentliches Image ersetzt diesen Repo-Zugriff nicht. Ohne Datei bricht
  der Konfig-Helfer vor dem Klon mit einer Fehlermeldung ab.
- SSH-Zugang nach `apply` für die Dateiablage; `ssh_allowed_cidr` muss den
  Betreiber erreichen lassen (bei leerer Liste einen eigenen sicheren Zugang
  vorher herstellen). Tailscale läuft zu diesem Zeitpunkt noch nicht.

## Schritte

1. `terraform.tfvars.example` nach `terraform.tfvars` kopieren, echte Werte
   eintragen (`terraform.tfvars` ist gitignored). Nur der Hetzner-API-Token
   gehört hierher; die vier Laufzeitgeheimnisse folgen als Dateien.
2. ```bash
   terraform init
   terraform plan
   terraform apply
   ```
3. DNS: A-Record `domain` → `server_ipv4` (Output nach `apply`) setzen. Caddy
   stellt das TLS-Zertifikat erst danach aus (ACME-Challenge).
4. [Geheimnisse ablegen und starten](#geheimnisse-ablegen-und-starten-1497).
5. Weiter mit der Inbetriebnahme-Doku des Produkts (`docs/inbetriebnahme.md`
   im Produkt-Repo `JanuaPort/januaport`).

## Geheimnisse ablegen und starten (#1497)

`cloud-init` beendet die Infrastrukturvorbereitung **ohne Klon, Image-Pull und
Gateway-Start**. Danach startet der Betreiber ausdrücklich. Das vermeidet
Warteschleifen beim Boot und funktioniert auch mit einem privaten Konfig-Repo,
für dessen Klon der Git-Token erst bereitgestellt werden muss.

Alle Quelldateien liegen außerhalb von Repo und Datenvolume in
`/etc/jnpt-bootstrap/` (Verzeichnis root:root/0700, Dateien root:root/0600).
Jede Datei enthält genau eine nichtleere Zeile, einen abschließenden Zeilenumbruch
optional. `jnpt-start` prüft Existenz, Eigentümer, Modus, reguläre Datei statt
Symlink sowie das 64-Hex-Format des Master-Keys, bevor es klont oder startet.

| Datei | Inhalt / Verwendung |
|---|---|
| `jnpt_master_key` | Pflicht: 64 Hex-Zeichen (32 Byte), GETRENNT vom Server sichern; Verlust bedeutet Verlust der verschlüsselten Credentials |
| `tailscale_authkey` | Pflicht für diesen Drei-Container-Stack: Auth-Key für den Tailnet-Beitritt (passendes ACL-Tag, persistent, Wiederverwendbarkeit bewusst wählen) |
| `git_token` | Pflicht beim privaten Default-Produkt-Repo: fein-granularer PAT, nur dieses Repo und `Contents: read-only`; bei öffentlichem Repo Datei weglassen |
| `registry_token` | Optional für privates GHCR-Package: classic PAT mit `read:packages` (GHCR unterstützt hierfür keine fein-granularen PATs); bei öffentlichem Package Datei weglassen |

Nur bei einer **Neuanlage mit leerer DB** den Master-Key in einer sicheren
lokalen Datei erzeugen, z. B. `umask 077; openssl rand -hex 32 > /sicher/jnpt_master_key`.
Bei Wiederverwendung eines Datenvolumes dessen vorhandenen Master-Key verwenden.
Die übrigen Werte ebenfalls über einen sicheren Editor/Secret-Manager als lokale
Dateien bereitstellen, außerhalb dieses Worktrees. Kein Geheimnis als Shell-Argument
eingeben. Die folgenden Bash-Befehle übertragen den Inhalt über SSH-stdin;
in den Argumenten stehen nur Dateinamen. Ausführen auf dem Betreiberrechner,
`<server-ip>` und die lokalen Pfade ersetzen:

```bash
ssh root@<server-ip> 'cloud-init status --wait'

# Beispiel für den Master-Key; die drei weiteren Dateien genauso übertragen:
ssh root@<server-ip> 'set -eu; umask 077; cat > /etc/jnpt-bootstrap/jnpt_master_key.new; chown root:root /etc/jnpt-bootstrap/jnpt_master_key.new; chmod 0600 /etc/jnpt-bootstrap/jnpt_master_key.new; mv -f /etc/jnpt-bootstrap/jnpt_master_key.new /etc/jnpt-bootstrap/jnpt_master_key' < /sicher/jnpt_master_key
ssh root@<server-ip> 'set -eu; umask 077; cat > /etc/jnpt-bootstrap/tailscale_authkey.new; chown root:root /etc/jnpt-bootstrap/tailscale_authkey.new; chmod 0600 /etc/jnpt-bootstrap/tailscale_authkey.new; mv -f /etc/jnpt-bootstrap/tailscale_authkey.new /etc/jnpt-bootstrap/tailscale_authkey' < /sicher/tailscale_authkey

# git_token beim privaten Default-Repo; registry_token nur bei privatem Package:
ssh root@<server-ip> 'set -eu; umask 077; cat > /etc/jnpt-bootstrap/git_token.new; chown root:root /etc/jnpt-bootstrap/git_token.new; chmod 0600 /etc/jnpt-bootstrap/git_token.new; mv -f /etc/jnpt-bootstrap/git_token.new /etc/jnpt-bootstrap/git_token' < /sicher/git_token
ssh root@<server-ip> 'set -eu; umask 077; cat > /etc/jnpt-bootstrap/registry_token.new; chown root:root /etc/jnpt-bootstrap/registry_token.new; chmod 0600 /etc/jnpt-bootstrap/registry_token.new; mv -f /etc/jnpt-bootstrap/registry_token.new /etc/jnpt-bootstrap/registry_token' < /sicher/registry_token

ssh root@<server-ip> '/usr/local/sbin/jnpt-start --check'
ssh root@<server-ip> '/usr/local/sbin/jnpt-start'
```

Der Master-Key erhält für Compose zusätzlich eine Lesekopie unter
`/opt/jnpt/repo/deploy/hetzner/secrets/jnpt_master_key`, **0400, UID/GID 65532**:
der Kern läuft nonroot, und Compose-file-Secrets übernehmen die Host-Rechte
(Swarm-`uid`/`mode` helfen hier nicht). Die Tailscale-Lesekopie daneben bleibt
root:root/0600; die Quelldateien bleiben root:root/0600. Nach einer legitimen
Key-Rotation die Quelldatei auf den neuen Key aktualisieren, bevor `jnpt-start`
erneut aufgerufen wird. Für ein gewöhnliches Image-Update das Update-Runbook
verwenden, statt die Provisionierung erneut auszuführen.

Git erhält den Token per `GIT_ASKPASS`, mit deaktiviertem Credential-Helper;
GHCR erhält ihn per `docker login --password-stdin`. Nach erfolgreichem Start
werden die beiden PAT-Quelldateien gelöscht; bei Fehlern bleiben sie für einen
erneuten Startversuch erhalten. Docker persistiert Registry-Auth in
`/root/.docker/config.json` — diese Datei ebenfalls als Geheimnis behandeln.

Der Prüf-Token des Host-Aktuators folgt demselben Ablagemuster, aber separat
unter `/etc/jnpt-updater.token` (root:root/0600). Zum Übertragen obiges
SSH-stdin-Muster mit diesem Zielpfad verwenden. Ohne ihn bleibt der Aktuator
inert. Nach dem Stack-Start dessen Dienst mit `systemctl start jnpt-updater.service`
auslösen; Inhalt und Einrichtung gemäß Produkt-Inbetriebnahme.

Die Altvariablen `jnpt_master_key`, `tailscale_authkey`, `git_token` und
`registry_token` sind **nicht mehr verwendete Terraform-Eingaben**. Sie bleiben
mit leerem Default und `validation` erhalten: ein gesetzter Altwert in tfvars
oder `TF_VAR_*` bricht den Plan mit einer Migrationsmeldung ab. Das verhindert
stilles Ignorieren vorhandener Betreiberdateien; Einträge entfernen und die
Werte über den Dateiweg bereitstellen. `sensitive` allein hätte weder State
noch Metadaten geschützt.

## Variablen (Auswahl, vollständig in `variables.tf`)

`git_ref` akzeptiert Branch, Tag und vollständigen Commit-SHA. Der Default
`v0.101.0` passt zum Beispiel-Image `0.101.0`; bei einem anderen Image auch die
Konfig-Version bewusst wählen. `config-holen.sh` verwendet `git init`,
`fetch --depth 1 origin <ref>` und `checkout --detach FETCH_HEAD`. Ein fehlender
Ref oder eine fehlende Compose-/Caddy-/Tailscale-/Aktuator-Datei beendet den
Start. Der geprüfte Klon wird erst danach nach `/opt/jnpt/repo` verschoben;
Fehlversuche hinterlassen dort keine teilweise ausgecheckte Arbeitskopie.
Ein erneuter Start erhält eine vorhandene Arbeitskopie und deren `.env`, prüft
aber die benötigten Dateien erneut. Änderungen von `git_ref` in Terraform
ersetzen die VM; laufende Anlagen nach dem Produkt-Update-Runbook aktualisieren.

Nach cloud-init zeigt `/etc/motd` ausdrücklich **„Keine Anlage gestartet“**.
Bei Startfehlern bleibt eine Meldung in der Ausgabe und der MOTD erhalten;
nach abgeschlossenem Compose-Start fordert die MOTD zur Health-/MCP-Prüfung auf.
Ein erfolgreiches `terraform apply` allein bedeutet weiterhin keine gestartete Anlage.

| Variable | sensitive | Default | Zweck |
|---|---|---|---|
| `hcloud_token` | ✅ | — | Hetzner-Cloud-API-Token |
| `domain` | — | — | öffentliche Domain (TLS); validiert |
| `acme_email` | — | — | Let's-Encrypt-Kontakt |
| `ts_hostname` | — | `jnpt` | Tailnet-Hostname (Admin-URL) |
| `server_type` / `location` | — | `cpx22` / `nbg1` | Server-Typ/Standort (Verfügbarkeit vor `apply` prüfen) |
| `ssh_public_key` | — | — | Admin-SSH-Key |
| `ssh_allowed_cidr` | — | **Pflicht, kein Default** | SSH-Quellen; IPv4 ab `/8`, IPv6 ab `/16`; breitere Netze einschließlich `0.0.0.0/0` und `::/0` werden abgewiesen; `[]` bleibt möglich |
| `public_web_enabled` | — | `false` | öffnet 80/443 in der Firewall |
| `image_ref` | — | Pflicht | gepinnter Registry-Tag, den die VM zieht |
| `git_repo` / `git_ref` | — | privates Produkt-Repo / `v0.101.0` | Konfiguration und Aktuator; Default braucht `git_token`-Datei; Branch/Tag/Commit-SHA |
| `update_manifest_url` / `update_public_keys` | — | `""` | optionaler Versions-Check (offline-first) |
| `update_plugins_url` | — | `""` | signierter Plugin-Katalog (`JNPT_UPDATE_PLUGINS_URL`); leer = kein Katalog, offline-first; gleicher Client und Schlüsselring wie Manifest |
| `updater_image_repo` | — | Produkt-Registry | Allowlist des Host-Aktuators |

**Abweichung vom Herkunfts-Modul:** `ssh_allowed_cidr` ist hier **Pflicht ohne
Default** (im Produkt-Repo-Modul hat sie `default = []`) — wer dieses Modul
für die eigene Infrastruktur anwendet, soll die SSH-Quelle bewusst entscheiden
statt sich auf einen stillen Default zu verlassen.

## Dateien

- `versions.tf` — Provider-Anforderung.
- `variables.tf` — Eingaben.
- `main.tf` — SSH-Key, Firewall (deny-by-default), Volume, Server.
- `outputs.tf` — Server-IPs, DNS-Hinweis, Admin-Zugangs-Hinweis.
- `cloud-init.yaml.tftpl` — First-Boot: Docker, Datenvolume, öffentliche `.env`,
  dauerhafter Metadaten-Guard; installiert `jnpt-start` für Klon/Pull/Start
  und Aktuator-Einrichtung nach der manuellen Dateiablage.
- `terraform.tfvars.example` — Platzhalter-Vorlage.

## Sicherheits-Defaults

- Docker-APT-Schlüssel vor Installation und Quelleintrag auf
  `9DC858229FC7DD38854AE2D88D81803C0EBFCD88` prüfen. Helfer und Pin sind
  unverändert aus dem Kern-Herkunftsmodul übernommen (#928 SEC E10, #1500).
  Ein fremder, ungültiger oder aus mehreren Hauptschlüsseln bestehender
  Download wird abgewiesen; `signed-by` bindet den Schlüssel an Docker.
- `/etc/tmpfiles.d/jnpt-plugins.conf` legt bei jedem Boot und vor dem Handstart
  `/run/jnpt/plugins` als root:root/0755 und `tunnel-admin` als 65532:65532/0750
  an. Der nonroot-Kern kann nur die beanspruchte Plugin-Stelle beschreiben.

- Firewall ist **deny-by-default**: SSH nur aus `ssh_allowed_cidr`, die
  öffentliche Web-Fläche (80/443) nur bei `public_web_enabled = true`.
- **Kein Port 8484 in der Firewall** — JanuaPort ist von außen nie direkt
  erreichbar, nur über `caddy` (öffentliche Whitelist) oder `tailscale`
  (Admin-Fläche, nur im Tailnet).
- Der Hetzner-API-Token bleibt eine sensitive Provider-Eingabe. tfvars und State
  weiterhin schützen (gitignored; für Teams verschlüsseltes Backend erwägen).
- Master-Key, Tailscale-Authkey sowie Git-/Registry-Token kommen seit #1497
  ausschließlich nach `apply` als Dateien auf die VM, nach dem Muster des
  Aktuator-Prüf-Tokens. Sie werden nicht mehr an `templatefile` übergeben.
- **Netzweg:** `http://169.254.169.254/hetzner/v1/userdata` liefert die vollständige
  `user_data` ohne Anmeldung an Prozesse der VM. Codeausführung oder SSRF in
  einem Container mit Ausgang kann diesen Weg nutzen; root-Rechte zum Lesen
  lokaler cloud-init-Dateien sind dafür unnötig. Das Löschen von Staging-Dateien
  entfernt keine Daten aus dem Metadaten-Dienst.
- Zweite Linie: `jnpt-metadata-guard.service` setzt den DROP für das ganze
  `169.254.0.0/16` an Position 1 in `DOCKER-USER`, vor jedes ACCEPT. Die Unit läuft
  nach Docker, bei Docker-Neustart erneut und vor dem manuellen Stack-Start.
  Dies schützt weitergeleiteten Docker-Bridge-Verkehr; Host-Prozesse und
  Container mit Host-Netzwerk unterliegen dieser Kette nicht. Deshalb bleibt
  die geheimnisfreie `user_data` die erste Linie.

## Bestehende Anlagen nachrüsten (#1497)

Ein normales `apply` aktualisiert keine laufende cloud-init-Konfiguration:
geänderte `user_data` führt bei diesem Provider zum VM-Ersatz. Für die
Sofortmaßnahme **keinen Neuaufbau** auslösen. Als Betreiber auf der VM zunächst:

```sh
sudo iptables -I DOCKER-USER 1 -d 169.254.0.0/16 -j DROP
```

Für die dauerhafte Sperre die folgenden Inhalte als
`/usr/local/sbin/jnpt-metadata-guard.sh` (root:root/0755) und
`/etc/systemd/system/jnpt-metadata-guard.service` (root:root/0644) ablegen.
Sie entsprechen den `write_files` der Vorlage:

```sh
#!/bin/sh
set -eu
# Nicht nur -C: Ein vorhandener DROP hinter ACCEPT wäre wirkungslos.
first=$(iptables -w -S DOCKER-USER | sed -n '2p')
if [ "$first" != '-A DOCKER-USER -d 169.254.0.0/16 -j DROP' ]; then
  iptables -w -I DOCKER-USER 1 -d 169.254.0.0/16 -j DROP
fi
```

```ini
[Unit]
Description=JanuaPort: Container-Zugriff auf Link-Local/Metadaten sperren (#1497)
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/jnpt-metadata-guard.sh

[Install]
WantedBy=multi-user.target docker.service
```

Danach `sudo systemctl daemon-reload` und
`sudo systemctl enable --now jnpt-metadata-guard.service` ausführen.
Nach Installation und jedem Host-/Docker-Neustart aus **jedem laufenden
Container einschließlich Kern, Caddy, Tailscale und Beistellern** prüfen:
Metadaten-HTTP muss unerreichbar sein. Nur Erfolgs-/Fehlerzähler festhalten;
Antwortinhalt verwerfen, keine `user_data` in Logs oder Tickets kopieren.

Alte `user_data` bleibt für die Lebenszeit der VM am Metadaten-Dienst vorhanden.
War der Container-Zugriff vor der Sperre möglich, nach SEC-Entscheid #1497
**alle vier Werte rotieren**: Master-Key über `key rotate` gemäß #1466
(TTY-Gate, 0600-Datei), anschließend frisches Backup und Wiederherstellungstest;
Tailscale-Authkey widerrufen (Knoten läuft weiter), Git-/Registry-PAT widerrufen
und neu ausstellen. Neue Werte ausschließlich manuell ablegen, aus den alten
tfvars entfernen. Bei nachweislich bereits gesperrtem Zugriff entfällt laut
SEC diese bedingte Rotation. Unklaren Altzugriff mit dem Sicherheitsverantwortlichen
klären. Ältere Backups mit möglicherweise offengelegtem Key gesondert bewerten;
eine Löschung entscheidet der Betreiber/PO. Sicherheitshinweis und CRA-Bewertung
(V4) liegen beim PO. Diese Vorlage führt weder Live-Probe noch Rotation aus.

## Lokale Tests

### Datenvolume: Abbruch statt Root-Platte (#1512)

cloud-init wartet höchstens 5 Minuten (60 × 5 Sekunden) auf das Blockgerät.
Fehlt es danach oder scheitert das Einhängen, bricht der gemeinsame
Volume-/Docker-Shellblock vor den Datenordnern und `docker volume create` ab.
Ausgabe und MOTD melden „Keine Anlage gestartet“. Auch `jnpt-start` verlangt
einen bestehenden Mount, insbesondere nach einem Neustart mit `nofail`.
Erst Volume-Attachment und cloud-init-Ausgabe prüfen, dann die fehlgeschlagene
Einrichtung wiederholen; ohne Mount keine Anlage starten.
`TestVolumeFailClosedRenderUndShell` führt die gerenderte Testzeile aus
(fehlendes Blockgerät, Mountfehler, fehlender Mount, Erfolg). Die drei
Volume-Mutanten entfernen Timeout-Abbruch bzw. die beiden Mount-Sperren und
müssen den jeweiligen echten Shell-Test rot machen.

```powershell
$env:MSYS_NO_PATHCONV='1'
docker run --rm -v "${PWD}:/src" -w /src golang:1.26.11 go test -v ./hetzner/...
docker build -f hetzner/test.Dockerfile -t jnpt-1497-tests .
docker run --rm --privileged -v "${PWD}:/src" -w /src jnpt-1497-tests
docker run --rm --privileged -e JNPT_MUTATIONS=1 -v "${PWD}:/src" -w /src jnpt-1497-tests
```

Aus dem Repo-Root ausführen. Der zweite Lauf braucht einen isolierten
privilegierten Wegwerfcontainer für echte Netzwerk-Namespaces/iptables;
kein Host-Netzwerk, kein Docker-Socket, keine VM. Er prüft auch den echten
Starthelfer mit fehlenden/unsicheren Dateien sowie den dokumentierten
Dateiweg und Git-Askpass am echten Shell-/Git-Adapter. `strace` erfasst die
execve-Argumente, die keine Kanarienwerte enthalten dürfen. Der letzte Aufruf
prüft die Sperren mit absichtlich verwundbaren Wegwerfkopien; jede Mutation
muss den passenden Test rot machen. Die HCL-Ausdrücke der
Altvariablenvalidierung werden im normalen Lauf ausgewertet. Der zusätzliche
Terraform-CLI-Adaptertest erfordert explizit `-e JNPT_TERRAFORM_TESTS=1` und
eine Umgebung, in der die Terraform-CLI erlaubt ist (lokale SEC-R2-Sperre #1055
beachten); ohne Freigabe bleibt er sichtbar übersprungen.

## Host-Firewall für das Plugin-Netz (Beisteller, JanuaPort/januaport#1040, #1194)

Wer Beisteller betreibt (Skript-Läufer, agent-runner, google-reporting), braucht auf dem Host eine Regel. Sie verhindert, dass ein Container am Plugin-Netz `jnpt_plugins` über das Bridge-Gateway Dienste des Hosts erreicht, zum Beispiel sshd oder einen lokalen Modell-Server. `internal: true` sperrt nur den Weg nach außen, den Host selbst sperrt es nicht. Gemessen wurde das auf der Showcase am 26.10.2026.

1. **Bridge-Namen pinnen**, damit die Regel an einem festen Namen hängt und nicht am Subnetz:
   ```yaml
   services:
     jnpt:
       restart: unless-stopped
       networks:
         default: {}
         plugins:
           ipv4_address: 172.21.0.2
   networks:
     plugins:
       name: jnpt_plugins
       internal: true
       ipam:
         config:
           - subnet: 172.21.0.0/16
             ip_range: 172.21.128.0/17
       driver_opts:
         com.docker.network.bridge.name: jnpt-plugins
   ```
   Das Beispiel ergänzt die bestehende Gateway-Dienstdefinition. `jnpt` hat im Subnetz `172.21.0.0/16` den festen Platz `172.21.0.2` außerhalb der dynamischen Spanne `172.21.128.0/17`; sonst kann ein Beisteller beim Neustart die Adresse des Gateways belegen (JanuaPort/januaport#1355). Beisteller beziehen ihre Adressen ausschließlich dynamisch aus dieser Spanne. Dieses Muster gilt für jedes gemeinsame Netz von `jnpt` und Beistellern; alle Dauerdienste verwenden `restart: unless-stopped`, Init-Dienste behalten `restart: "no"`.

   ⚠️ Bridge-Name und IPAM-Konfiguration lassen sich nur beim Anlegen des Netzes setzen. Bei einer bestehenden Anlage nimmst du deshalb zuerst alle Plugin-Stacks herunter, danach den Kern, und startest dann in umgekehrter Reihenfolge. Plugin-Stacks laufen je mit `-f docker-compose.yml` im eigenen Ordner. Den Kern startest du mit **allen** seinen Dateien, also mit `-f` je Datei oder mit `COMPOSE_FILE=… docker compose …` nur als Präfix dieses einen Aufrufs. `COMPOSE_FILE` darf **nie** exportiert sein, sonst trifft ein `down` das falsche Projekt.
2. **Regel**, idempotent, für IPv4 und IPv6. Sie greift auch, bevor Docker die Bridge anlegt:
   ```sh
   # /usr/local/sbin/jnpt-plugin-net-guard.sh
   for IF in jnpt-plugins; do
     iptables  -C INPUT -i "$IF" -j DROP 2>/dev/null || iptables  -I INPUT 1 -i "$IF" -j DROP
     ip6tables -C INPUT -i "$IF" -j DROP 2>/dev/null || ip6tables -I INPUT 1 -i "$IF" -j DROP
   done
   ```
   Hat ein Beisteller ein eigenes Ausgangsnetz mit gepinnter Bridge, etwa google-reporting mit `jnpt-gr-egress`, gehört dessen Name mit in die Liste.
3. **Dauerhaft** über eine systemd-Unit `jnpt-plugin-net-guard.service` mit `Type=oneshot`, `RemainAfterExit=yes`, `ExecStart=/usr/local/sbin/jnpt-plugin-net-guard.sh`, `After=`, `Requires=` und `PartOf=docker.service`, `WantedBy=multi-user.target docker.service`. Ohne `RemainAfterExit=yes` greifen `PartOf` und `Requires` bei oneshot nicht richtig.
4. **Prüfen**, auch nach jedem Neustart des Hosts: Aus jedem Container am Plugin-Netz darf **kein** lauschender Host-Port (`ss -lnt`) über das Bridge-Gateway erreichbar sein. `jnpt:8484` muss erreichbar bleiben.

Die Box bringt mit `scripts/hardening.sh` eine input-Kette mit `policy drop` mit. Ob sie das Plugin-Netz vollständig erfasst, wird in JanuaPort/januaport#1194 geprüft.

## Linux-Audit-Adapter und Herkunfts-Drift (#1500)

Für echte GPG-/Git-/Dateirechte- und tmpfiles-Prüfungen gibt es ein Testimage
**ohne Terraform**. Es führt auch die AWS-/Azure-Tests aus:

```powershell
docker build -f hetzner/audit-test.Dockerfile -t jnpt-deploy-audit-tests .
docker run --rm --privileged -v "${PWD}:/src" -w /src jnpt-deploy-audit-tests
```

Die neuen Mutationen laufen automatisch in Wegwerfkopien; tmpfiles verlangt
das Testimage. Der vorhandene Netz-Adapter aus #1497 braucht weiterhin den
isolierten privilegierten Container, ohne Host-Netzwerk oder Docker-Socket.

`TestHerkunftsDrift` vergleicht alle gerenderten YAML-Felder einschließlich
Dateipfad, Eigentümer, Modus und Inhalt gegen die Hash-Baseline in
`testdata/core-drift.json`. Herkunft: Produkt-Repo `origin/main` bei
`ceba172a54bd01fa4f8200daba06823232f5d3c7`, `deploy/hetzner/cloud-init.yaml.tftpl`.
Die normale Vorlage entspricht dem Kern mit `script_runner_enabled=false`.
Das optionale gVisor-/Skript-Läufer-Provisioning ist kein Bestandteil dieser
generischen Vorlage. Der SHA-256 der **gesamten** Kern-Vorlage erfasst auch
Änderungen in diesen optionalen Blöcken.

Die Ausnahmeliste nennt je Feld einen Grund und die festen Hashes **beider**
Seiten. Eine Ausnahme ignoriert keine künftige Änderung. Unterschiede sind
der bestehende #1497-Starthelfer/Guard unter anderen Pfaden, strengere lokale
Dateiprüfungen, die #1501-Klonprüfung und #1512: fail-closed bei Volume-Timeout,
Mount-Prüfung vor Docker-Volumes sowie vor jedem Handstart. Die Herkunft
`ceba172a54bd01fa4f8200daba06823232f5d3c7` bleibt unverändert; für #1512 wurde
die Baseline mit dem Export genau dieses Commits regeneriert. Die APT-Härtung
hat keine Ausnahme.

Im öffentlichen Repo läuft der Vergleich offline gegen die bekannte Herkunft.
Für jeden Nachzug aus dem privaten Kern muss der Lead zusätzlich einen
**frischen Export aus dessen origin/main** einhängen; ein veränderter Export
macht den Test rot und verlangt die Sichtung aller neuen SEC-Härtungen:

```powershell
# $coreExport bezeichnet die exportierte deploy/hetzner/cloud-init.yaml.tftpl.
$env:MSYS_NO_PATHCONV='1'
docker run --rm -e JNPT_CORE_TEMPLATE=/core/cloud-init.yaml.tftpl -v "${PWD}:/src" -v "${coreExport}:/core/cloud-init.yaml.tftpl:ro" -w /src golang:1.26.11 go test -v ./hetzner/... -run 'TestHerkunftsDrift|TestDrift'
```

Nach Prüfung beider Vorlagen aktualisiert der Lead die Baseline bewusst mit
`go run drift-baseline.go -core <export> -commit <voller-kern-commit>` im Ordner
`hetzner` (ebenfalls im Go-Container möglich). Neue Ausnahmen tragen zunächst
`PRUEFEN:` und lassen den Test scheitern, bis ein konkreter Grund eingetragen
ist. Geänderte bestehende Ausnahmen und ihre Gründe im Diff erneut prüfen;
keine SEC-Härtung pauschal ausnehmen. Danach den vollständigen Testlauf starten.
