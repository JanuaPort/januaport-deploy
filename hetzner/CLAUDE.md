# Hetzner-Modul

## Geheimnisgrenze (#1497)

`user_data` und die Argumente von `templatefile` enthalten ausschließlich
öffentliche Konfiguration. Hetzners Metadaten-Dienst
`http://169.254.169.254/hetzner/v1/userdata` liefert die vollständige cloud-config
ohne Anmeldung an Prozesse der VM, auch über Container-Ausgang/SSRF. Die lokale
root-Kopie unter `/var/lib/cloud/instances/` und das Scrubben von Staging-Dateien
schützen diesen Netzweg nicht.

Master-Key, Tailscale-Authkey, Git- und Registry-Token werden nach `apply` vom
Betreiber unter `/etc/jnpt-bootstrap/` abgelegt (root:root/0600, Verzeichnis
0700), wie der separate Prüf-Token unter `/etc/jnpt-updater.token`. SSH-stdin-
Befehle und Start mit `/usr/local/sbin/jnpt-start` stehen in [README.md](README.md#geheimnisse-ablegen-und-starten-1497).
cloud-init installiert nur Infrastruktur und Starthelfer. Der ausdrückliche
Betreiberstart vermeidet Boot-Warteschleifen und erlaubt private Repo-Klone
erst nach Token-Ablage. Der Helfer prüft Dateien vor Klon/Pull/Start.

Compose-file-Secrets brauchen für den nonroot-Kern eine abgeleitete Lesekopie
des Master-Keys mit 0400 und UID/GID 65532; die Betreiber-Quelldatei bleibt
root:root/0600. Bei Rotation Quelle und Lesekopie synchron halten. Git-/Registry-
Quelldateien werden nach erfolgreichem Start entfernt, Docker-Auth bleibt
unter `/root/.docker/config.json`. Alle diese Dateien liegen außerhalb von /data.

Die vier alten Terraform-Variablen bleiben ausschließlich Migrationssperren:
Default leer, gesetzte Werte mit `validation` und #1497-Hinweis abweisen.
So werden vorhandene tfvars nicht still ignoriert. Nur der Hetzner-API-Token
bleibt eine sensitive Provider-Eingabe; State und tfvars weiterhin schützen.

## Zweite Linie: Metadaten-Guard

`jnpt-metadata-guard.service` setzt `DOCKER-USER -d 169.254.0.0/16 -j DROP`
an Position 1 vor jedes ACCEPT. `After`, `Requires`, `PartOf=docker.service`,
`RemainAfterExit=yes` und `WantedBy=multi-user.target docker.service` erhalten
die Sperre bei Host-/Docker-Neustart. Der Starthelfer fordert den Guard vor
Compose an. Ein bloßes `iptables -C` genügt nicht: DROP hinter ACCEPT ist wirkungslos.
Die Kette erfasst weitergeleiteten Bridge-Verkehr, keine Host-Prozesse oder
Host-Netzwerk-Container; deshalb Geheimnisse unabhängig davon aus user_data halten.

Bestehende Anlagen: Regel sofort nachrüsten und dauerhaft installieren, danach
Gegenprobe aus jedem Container (nur Zähler, keine Antwortinhalte festhalten).
Bei zuvor erreichbarem Metadaten-Dienst gemäß SEC #1497 alle vier Werte rotieren;
Master-Key über #1466, frisches Backup und Wiederherstellungstest. Alte user_data
bleibt bis zum VM-Ersatz erhalten. Details, bedingte Rotation und Betreiberbefehle
stehen im [Upgrade-Abschnitt](README.md#bestehende-anlagen-nachrüsten-1497).
V4/CRA und externe Betreiberkommunikation entscheidet der PO.

## Prüfungen

`cloudinit_render_test.go`: echte HCL-Renderung mit vier Kanarienwerten, Terraform-
Kompositionsweg, Unit/Regel/Startreihenfolge und Altvariablenvalidierungen.
`cloudinit_waechter_test.go`: echter Starthelfer und echtes iptables/HTTP in
isolierten Netzwerk-Namespaces; optionaler Terraform-CLI-Test nur in dafür
freigegebener Umgebung. `secret_transport_test.go` prüft Dateiweg/Git-Askpass
mit echten execve-Traces; `mutations_test.go` entfernt Sperren in Wegwerfkopien.
Aufrufe siehe README. Bei Änderungen an einer Sperre
auch das Verbotene auslösen und die Mutationsprobe mit entfernter Sperre prüfen.

## Audit-Nachzug (#1500, #1501, #1512 Punkte 2/10)

Docker-APT: unveränderter Kern-Helfer apt-schluessel.sh mit Pin
9DC858229FC7DD38854AE2D88D81803C0EBFCD88; Quelle nur hinter erfolgreichem `&&`.
Plugin-tmpfiles vor Handstart und bei Boot; Eltern root:root/0755,
tunnel-admin 65532:65532/0750. Plugin-Feed als öffentliche Variable bis `.env`.

Das private Default-Repo braucht vor dem Klon die Git-Token-Datei. Der separate
config-holen.sh akzeptiert Branch/Tag/Commit-SHA, prüft Stack-/Aktuator-Dateien
und übernimmt erst den vollständigen Klon. Default-Ref v0.87.1 zum Beispiel-Image
0.87.1. Startfehler und ungestartete Anlage erscheinen in Ausgabe/MOTD.
SSH-Eingabe weist IPv4-Präfixe kürzer als /8 und IPv6-Präfixe kürzer als /16
einschließlich 0.0.0.0/0 und ::/0 ab; [] bleibt bewusst möglich.

Der Drift-Wächter friert alle gerenderten Felder mit benannten Ausnahmen samt
Grund und beidseitigem Hash ein. Jeder Kern-Nachzug verlangt zusätzlich den
frischen Export via JNPT_CORE_TEMPLATE; dessen kompletter Hash erfasst auch
optionale Skript-Läufer-Blöcke. Baseline/Update-Anleitung: README.
Audit-Tests/Mutanten verwenden echte GPG-, Git-, HCL-, tmpfiles- und
Dateisystemadapter im Wegwerfcontainer; audit-test.Dockerfile braucht kein Terraform.
