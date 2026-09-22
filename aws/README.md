# aws/ — minimaler Startpunkt für Amazon Web Services

**Community-Vorlage, von JanuaPort GmbH nicht betrieben, ungetestet.** Kein
IaC-Modul (kein Terraform/CloudFormation) — ein cloud-init-Skript (EC2
User-Data) + eine Instanz, die Sie selbst anlegen. Fehler, Lücken und
AWS-Besonderheiten bitte als Issue melden (`CONTRIBUTING.md`).

## Voraussetzungen

- AWS-Konto + AWS CLI (konfigurierte Credentials/Profil).
- Ein SSH-Key-Pair in der Ziel-Region (`aws ec2 create-key-pair` oder Import).
- Eine Security Group in der Ziel-VPC.

## Schritte (Beispiel, ungetestet — vor dem produktiven Einsatz selbst prüfen)

```bash
# Security Group mit restriktiver SSH-Regel anlegen (KEIN 0.0.0.0/0):
aws ec2 create-security-group --group-name jnpt-sg --description "JanuaPort minimal"
aws ec2 authorize-security-group-ingress \
  --group-name jnpt-sg --protocol tcp --port 22 \
  --cidr "<ihre-oeffentliche-ip>/32"

# Aktuelles Ubuntu-24.04-AMI der eigenen Region ermitteln (Beispiel eu-central-1;
# AMI-IDs sind regionsspezifisch und ändern sich — Wert vorher selbst prüfen,
# z. B. über den offiziellen Ubuntu-AMI-Locator):
aws ec2 run-instances \
  --image-id <aktuelle-ubuntu-24.04-ami-id> \
  --instance-type t3.small \
  --key-name <ihr-key-pair> \
  --security-groups jnpt-sg \
  --user-data file://cloud-init.yaml \
  --count 1
```

Nach dem ersten Boot (Docker-Installation braucht etwas Zeit — Fortschritt via
`ssh ubuntu@<instanz-ip> "cloud-init status --wait"`):

```bash
ssh ubuntu@<instanz-ip>
sudo nano /opt/jnpt/.env   # JANUAPORT_IMAGE + weitere Werte eintragen
cd /opt/jnpt && sudo docker compose --env-file .env up -d
```

## Prüfen

Wie im generischen Compose-Stack — `/healthz` + echter MCP-Rundlauf
(`initialize` + `tools/list`), siehe [`../compose/README.md`](../compose/README.md#prüfen).
Port 8484 ist hier ebenfalls nur an Loopback gebunden — für den Zugriff von
außerhalb der Instanz einen SSH-Tunnel nutzen (`ssh -L 8484:localhost:8484 …`)
oder einen eigenen Reverse-Proxy ergänzen.

## Update

```bash
cd /opt/jnpt && sudo docker compose --env-file .env pull && sudo docker compose --env-file .env up -d
```

## Sicherheits-Defaults

- Die Security-Group-Regel oben öffnet **nur SSH von der eigenen IP** — kein
  `0.0.0.0/0`.
- Port 8484 ist nur an Loopback gebunden, nicht öffentlich erreichbar.
- Wer eine öffentliche Fläche braucht: eigenen Reverse-Proxy mit TLS ergänzen
  und **nur** selektiv weiterleiten (`/mcp` exakt, `/healthz`, OAuth-Discovery)
  — die Admin-Fläche gehört nie ins offene Internet. Das gehärtete
  Referenzmuster (Caddy-Whitelist + Tailscale-Sidecar) steht in
  [`../hetzner/`](../hetzner/); es ist 1:1 auf AWS übertragbar, aber nicht Teil
  dieser minimalen Vorlage.
- Secrets kommen ausschließlich aus `/opt/jnpt/.env` — nie in die
  `docker-compose.yml`, nie ins Repo.
