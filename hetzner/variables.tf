# Eingabevariablen für das Hetzner-Single-Node-Deployment (JanuaPort/januaport#776,
# generisch abgeleitet aus deploy/hetzner/ im Produkt-Repo, #107).
#
# Der API-Token bleibt sensitive und außerhalb des Repos. Laufzeitgeheimnisse
# werden nach apply als Dateien abgelegt; die vier alten Eingaben unten sind
# ausschließlich Migrationssperren (#1497), keine verwendeten Konfigurationen.

# ── Secrets ──────────────────────────────────────────────────────────────────

variable "hcloud_token" {
  description = "Hetzner-Cloud-API-Token (Projekt → Security → API-Tokens, Read & Write)."
  type        = string
  sensitive   = true
}

variable "tailscale_authkey" {
  description = "NICHT MEHR VERWENDET (#1497): nach apply als root:root/0600-Datei /etc/jnpt-bootstrap/tailscale_authkey ablegen (README)."
  type        = string
  sensitive   = true
  default     = ""
  nullable    = false

  validation {
    condition     = var.tailscale_authkey == ""
    error_message = "tailscale_authkey wird seit #1497 nicht mehr über Terraform verwendet. Eintrag aus tfvars/TF_VAR entfernen; nach apply als 0600-Datei auf der VM ablegen, siehe hetzner/README.md."
  }
}

variable "jnpt_master_key" {
  description = "NICHT MEHR VERWENDET (#1497): nach apply als root:root/0600-Datei /etc/jnpt-bootstrap/jnpt_master_key ablegen (README)."
  type        = string
  sensitive   = true
  default     = ""
  nullable    = false

  validation {
    condition     = var.jnpt_master_key == ""
    error_message = "jnpt_master_key wird seit #1497 nicht mehr über Terraform verwendet. Eintrag aus tfvars/TF_VAR entfernen; nach apply als 0600-Datei auf der VM ablegen, siehe hetzner/README.md."
  }
}

# ── Domain / DNS ─────────────────────────────────────────────────────────────

variable "domain" {
  description = <<-EOT
    Öffentliche Domain für die Tool-/SSO-Fläche (TLS via Caddy/ACME). Nach
    `apply` einen A-Record `domain` → Server-IPv4 setzen (siehe outputs.tf).
  EOT
  type        = string

  validation {
    condition     = can(regex("^[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.domain))
    error_message = "domain muss ein gültiger Hostname sein (z. B. jnpt.example.com)."
  }
}

variable "acme_email" {
  description = "Kontakt-E-Mail für Let's Encrypt (Ablauf-Benachrichtigungen)."
  type        = string
}

variable "ts_hostname" {
  description = "Tailnet-Hostname des Knotens (MagicDNS-Name; Admin-Fläche erreichbar als https://<ts_hostname>.<tailnet>.ts.net)."
  type        = string
  default     = "jnpt"
}

# ── Server / Standort ────────────────────────────────────────────────────────

variable "server_type" {
  description = <<-EOT
    Hetzner-Server-Typ. Default cpx22 (2 vCPU/4 GB) — günstig und für den
    Single-Node ausreichend. ACHTUNG: Server-Typen sind region-abhängig und
    ändern sich über die Zeit. Vor `apply` die echte Verfügbarkeit prüfen
    (GET /v1/datacenters → server_types.available × /v1/server_types) — der Typ
    muss zur gewählten `location` passen.
  EOT
  type        = string
  default     = "cpx22"
}

variable "location" {
  description = "Hetzner-Rechenzentrum (z. B. nbg1, fsn1, hel1). EU-Standort empfohlen (DSGVO)."
  type        = string
  default     = "nbg1"
}

variable "image" {
  description = "Betriebssystem-Image. Ubuntu LTS."
  type        = string
  default     = "ubuntu-24.04"
}

variable "volume_size" {
  description = "Größe des persistenten /data-Volumes in GB (SQLite-DB). Minimum bei Hetzner ist 10 GB."
  type        = number
  default     = 10

  validation {
    condition     = var.volume_size >= 10
    error_message = "Hetzner-Volumes sind mindestens 10 GB groß."
  }
}

variable "name" {
  description = "Namenspräfix für die angelegten Ressourcen (Server, Volume, Firewall, Key)."
  type        = string
  default     = "jnpt"
}

# ── Image-Quelle (Prebuilt-Image aus einer Container-Registry) ──────────────

# WARNUNG (wie bei git_*): Eine Änderung von image_ref ändert die
# cloud-init/user_data der VM. Ein `terraform apply` gegen eine BESTEHENDE VM
# triggert bei hcloud deshalb ein VM-REPLACEMENT (die user_data ist Teil des
# Server-Ressourcen-Fingerprints) — der neue Wert greift erst beim nächsten
# bewussten Neuaufbau. Für ein reines Image-Update auf der laufenden VM NICHT
# `apply`, sondern das Update-Runbook des Produkts fahren: JANUAPORT_IMAGE in
# der .env auf den neuen Tag setzen, `docker compose pull && up -d`.
variable "image_ref" {
  description = <<-EOT
    Gepinnter Image-Tag, den die VM aus der Registry zieht, z. B.
    ghcr.io/januaport/januaport:0.106.0. PFLICHT (kein Default): bewusst KEIN
    `latest`, damit der Deploy reproduzierbar auf einem festen Tag steht.
    cloud-init bereitet die öffentliche .env mit JANUAPORT_IMAGE vor;
    jnpt-start installiert sie nach der Dateiablage neben der Prod-Compose.
  EOT
  type        = string
}

variable "registry_token" {
  description = "NICHT MEHR VERWENDET (#1497): bei privatem GHCR nach apply als root:root/0600-Datei /etc/jnpt-bootstrap/registry_token ablegen (README)."
  type        = string
  sensitive   = true
  default     = ""
  nullable    = false

  validation {
    condition     = var.registry_token == ""
    error_message = "registry_token wird seit #1497 nicht mehr über Terraform verwendet. Eintrag aus tfvars/TF_VAR entfernen; nach apply als 0600-Datei auf der VM ablegen, siehe hetzner/README.md."
  }
}

# ── Versions-Check (optional, offline-first) ─────────────────────────────────

# WARNUNG (wie bei image_ref/git_*): Eine Änderung dieser Werte ändert die
# cloud-init/user_data der VM. Ein `terraform apply` gegen eine BESTEHENDE VM
# triggert bei hcloud deshalb ein VM-REPLACEMENT — der neue Wert greift erst
# beim nächsten bewussten Neuaufbau. Für eine Änderung auf der LAUFENDEN Anlage
# NICHT `apply`, sondern die zwei Zeilen in der .env neben der Prod-Compose
# setzen und `docker compose up -d` fahren.
variable "update_manifest_url" {
  description = <<-EOT
    OPTIONAL: URL des signierten Vendor-Manifests für den Versions-Check
    (JNPT_UPDATE_MANIFEST_URL in der .env neben der Prod-Compose). LEER
    (Default) = der Check bleibt AUS. Das ist offline-first und ausdrücklich
    KEIN Fehler: der Serverstart telefoniert nie nach Hause.

    NICHT `sensitive`: eine öffentliche Abruf-Adresse, kein Geheimnis.
  EOT
  type        = string
  default     = ""
}

variable "update_plugins_url" {
  description = "OPTIONAL: öffentliche URL des signierten Plugin-Katalogs (JNPT_UPDATE_PLUGINS_URL). Leer = kein Katalog, offline-first. Nutzt denselben Ticker, gehärteten Client und Schlüsselring wie das Manifest. Änderungen an user_data ersetzen die VM; auf laufenden Anlagen die .env gemäß README ändern."
  type        = string
  default     = ""
}

variable "update_public_keys" {
  description = <<-EOT
    OPTIONAL: vertrauenswürdige ECDSA-P256-PUBLIC-Keys, gegen die das Manifest
    geprüft wird (JNPT_UPDATE_PUBLIC_KEYS). Form
    `key_id=<base64(SPKI-DER)|hex>;key_id2=…`; sie ERGÄNZEN den im Binary
    eingebetteten Schlüsselring (Rotation „current + next"). LEER (Default) =
    kein Schlüssel, und ohne Schlüssel ist der Check fail-closed — es wird
    nichts Ungeprüftes akzeptiert.

    BEWUSST NICHT `sensitive`: Ein VERIFIKATIONS-Schlüssel ist per Definition
    öffentlich — ihn zu veröffentlichen IST sein Zweck. Der zugehörige PRIVATE
    Schlüssel liegt ausschließlich beim Vendor und taucht hier nie auf.
  EOT
  type        = string
  default     = ""
}

# ── Host-Aktuator ─────────────────────────────────────────────────────────────

variable "updater_image_repo" {
  description = <<-EOT
    Repository, aus dem der Host-Aktuator installieren darf — DIE ALLOWLIST der
    Vertrauensgrenze. Sie steht bewusst in der HOST-Konfiguration und nicht im
    Manifest: Aus dem signierten Plan kommt ausschließlich der Digest, und der
    Aktuator setzt `<updater_image_repo>@<digest>` selbst zusammen.

    NUR das Repository — KEIN Tag und KEIN `@digest` (der Aktuator weist beides
    ab). Default ist dasselbe Repository, aus dem `image_ref` zieht.

    NICHT `sensitive`: ein Repository-Name ist kein Geheimnis. Der Prüf-Token
    des Gesundheits-Rundlaufs ist dagegen eines — er wird deshalb NICHT über
    Terraform gesetzt, sondern von Hand auf der VM abgelegt
    (`/etc/jnpt-updater.token`, 0600). Über `user_data` läge er im
    Terraform-State und am Metadaten-Dienst. Ohne ihn ist der Aktuator inert;
    das ist der gewollte Zustand direkt nach der Provisionierung.
  EOT
  type        = string
  default     = "ghcr.io/januaport/januaport"
}

# ── Konfig-Quelle (Klon der Compose-/Caddy-/Tailscale-Configs) ──────────────

# WARNUNG: Eine Änderung dieses Werts ändert die cloud-init/user_data der VM.
# Ein `terraform apply` gegen eine BESTEHENDE VM triggert bei hcloud deshalb
# ein VM-REPLACEMENT (die user_data ist Teil des Server-Ressourcen-
# Fingerprints) — der neue Wert greift erst beim nächsten bewussten Neuaufbau.
variable "git_repo" {
  description = <<-EOT
    Git-Repository (HTTPS), das jnpt-start nach der Dateiablage klont — NUR für die
    Konfig-Dateien (docker/docker-compose.prod.yml, docker/Caddyfile,
    docker/tailscale-serve.json aus dem JanuaPort-Produkt-Repo). Das Image wird
    NICHT on-VM gebaut, sondern als Prebuilt-Image aus der Registry gezogen
    (siehe `image_ref`). Für ein PRIVATES Repo nach apply die Datei
    /etc/jnpt-bootstrap/git_token ablegen (README, #1497).
  EOT
  type        = string
  default     = "https://github.com/JanuaPort/januaport.git"
}

variable "git_ref" {
  description = "Branch/Tag/Commit-SHA der Konfig-Dateien. Default v0.106.0 passend zum Beispiel-Image; für reproduzierbare Deploys Release-Tag oder vollständigen Commit-SHA wählen. Bestehende Arbeitskopien bleiben bei erneutem Start erhalten."
  type        = string
  default     = "v0.106.0"
}

variable "git_token" {
  description = "NICHT MEHR VERWENDET (#1497): bei privatem Konfig-Repo nach apply als root:root/0600-Datei /etc/jnpt-bootstrap/git_token ablegen (README)."
  type        = string
  sensitive   = true
  default     = ""
  nullable    = false

  validation {
    condition     = var.git_token == ""
    error_message = "git_token wird seit #1497 nicht mehr über Terraform verwendet. Eintrag aus tfvars/TF_VAR entfernen; nach apply als 0600-Datei auf der VM ablegen, siehe hetzner/README.md."
  }
}

# ── SSH-Zugang ───────────────────────────────────────────────────────────────

variable "ssh_public_key" {
  description = "Öffentlicher SSH-Schlüssel (Inhalt, z. B. aus ~/.ssh/id_ed25519.pub) für den Admin-Zugang zur VM."
  type        = string
}

# PFLICHTVARIABLE, bewusst OHNE Default (Abweichung vom Produkt-Repo-Modul, das
# hier default = [] hat): Dieses Repo hat kein Team, das die Wahl "kein SSH"
# stillschweigend für jeden Nutzer treffen sollte — wer das Modul anwendet,
# muss die SSH-Quelle EXPLIZIT entscheiden (und kann sich bewusst für eine
# leere Liste `[]` entscheiden, wenn wirklich kein SSH gewünscht ist).
variable "ssh_allowed_cidr" {
  description = <<-EOT
    CIDR-Liste, die SSH (Port 22) erreichen darf. PFLICHT, kein Default — bewusst
    keine stille Vorgabe. Für den Zugang die eigene IP setzen (z. B.
    ["203.0.113.4/32"]). IPv4-Präfixe kürzer als /8 und IPv6-Präfixe kürzer
    als /16 werden abgewiesen, einschließlich 0.0.0.0/0 und ::/0. Wer wirklich
    kein SSH von außen will, trägt explizit eine leere Liste `[]` ein.
    Für die Dateiablage nach apply ist ein erreichbarer SSH-Zugang nötig;
    Tailscale startet erst danach (README, #1497).
  EOT
  type        = list(string)

  validation {
    condition = length([
      for cidr in var.ssh_allowed_cidr : cidr
      if !try(tonumber(split("/", cidr)[1]) >= (length(regexall(":", cidr)) > 0 ? 16 : 8), false)
    ]) == 0
    error_message = "ssh_allowed_cidr braucht IPv4-Präfixe ab /8 und IPv6-Präfixe ab /16; 0.0.0.0/0 und ::/0 sind damit ebenfalls ausgeschlossen. Eigene CIDRs oder bewusst [] wählen."
  }
}

# ── Öffentliche Web-Fläche ────────────────────────────────────────────────────

variable "public_web_enabled" {
  description = <<-EOT
    Öffnet die öffentlichen Web-Ports (80/tcp, 443/tcp, 443/udp) in der
    Firewall. Default FALSE: kein öffentlicher Endpunkt, Verwaltung/Zugriff nur
    über das Tailnet bzw. SSH. Ein Wieder-Öffnen ist ein bewusster Handgriff
    (diese Variable auf true), kein Code-Revert. ⚠️ Vor einem `true` die eigene
    Zertifikats-/Domain-Lage prüfen — die offene Fläche ist der Punkt mit dem
    größten Risiko in diesem Modul.
  EOT
  type        = bool
  default     = false
}
