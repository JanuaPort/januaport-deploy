# azure/ — minimaler Startpunkt für Microsoft Azure

**Community-Vorlage, von JanuaPort GmbH nicht betrieben, ungetestet.** Kein
IaC-Modul (kein Terraform/Bicep) — ein cloud-init-Skript + eine VM, die Sie
selbst anlegen. Fehler, Lücken und Azure-Besonderheiten bitte als Issue
melden (`CONTRIBUTING.md`).

## Voraussetzungen

- Azure-Abonnement + Azure CLI (`az login`).
- Eine Resource Group in der gewünschten Region.

## Schritte (Beispiel, ungetestet — vor dem produktiven Einsatz selbst prüfen)

```bash
az group create --name jnpt-rg --location westeurope

# NSG mit restriktiver SSH-Regel VORHER anlegen (az vm create öffnet sonst
# per Default 22/tcp für 0.0.0.0/0 — das NICHT so stehen lassen):
az network nsg create --resource-group jnpt-rg --name jnpt-nsg
az network nsg rule create \
  --resource-group jnpt-rg --nsg-name jnpt-nsg \
  --name allow-ssh-own-ip --priority 100 \
  --access Allow --direction Inbound --protocol Tcp \
  --destination-port-ranges 22 \
  --source-address-prefixes "<ihre-oeffentliche-ip>/32"

az vm create \
  --resource-group jnpt-rg \
  --name jnpt-vm \
  --image Ubuntu2404 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --nsg jnpt-nsg \
  --custom-data cloud-init.yaml
```

Nach dem ersten Boot (Docker-Installation braucht etwas Zeit — Fortschritt via
`ssh azureuser@<vm-ip> "cloud-init status --wait"`):

```bash
ssh azureuser@<vm-ip>
sudo nano /opt/jnpt/.env   # JANUAPORT_IMAGE + weitere Werte eintragen
cd /opt/jnpt && sudo docker compose --env-file .env up -d
```

## Prüfen

Wie im generischen Compose-Stack — `/healthz` + echter MCP-Rundlauf
(`initialize` + `tools/list`), siehe [`../compose/README.md`](../compose/README.md#prüfen).
Port 8484 ist hier ebenfalls nur an Loopback gebunden — für den Zugriff von
außerhalb der VM einen SSH-Tunnel nutzen (`ssh -L 8484:localhost:8484 …`) oder
einen eigenen Reverse-Proxy ergänzen.

## Update

```bash
cd /opt/jnpt && sudo docker compose --env-file .env pull && sudo docker compose --env-file .env up -d
```

## Sicherheits-Defaults

- Die NSG-Regel oben öffnet **nur SSH von der eigenen IP** — kein `0.0.0.0/0`.
- Port 8484 ist nur an Loopback gebunden, nicht öffentlich erreichbar.
- Wer eine öffentliche Fläche braucht: eigenen Reverse-Proxy mit TLS ergänzen
  und **nur** selektiv weiterleiten (`/mcp` exakt, `/healthz`, OAuth-Discovery)
  — die Admin-Fläche gehört nie ins offene Internet. Das gehärtete
  Referenzmuster (Caddy-Whitelist + Tailscale-Sidecar) steht in
  [`../hetzner/`](../hetzner/); es ist 1:1 auf Azure übertragbar, aber nicht
  Teil dieser minimalen Vorlage.
- Secrets kommen ausschließlich aus `/opt/jnpt/.env` — nie in die
  `docker-compose.yml`, nie ins Repo.
