# Eingabevariablen für das Hetzner-Single-Node-Deployment (JanuaPort/januaport#776,
# generisch abgeleitet aus deploy/hetzner/ im Produkt-Repo, #107).
#
# Secrets sind als `sensitive = true` markiert (kein Klartext im Plan/Output).
# Echte Werte gehören in eine *.tfvars-Datei (gitignored) oder in
# TF_VAR_*-Umgebungsvariablen — NIE in dieses Repo. Vorlage:
# terraform.tfvars.example.

# ── Secrets ──────────────────────────────────────────────────────────────────

variable "hcloud_token" {
  description = "Hetzner-Cloud-API-Token (Projekt → Security → API-Tokens, Read & Write)."
  type        = string
  sensitive   = true
}

variable "tailscale_authkey" {
  description = <<-EOT
    Tailscale-Auth-Key (Tailscale-Admin-Konsole → Settings → Keys).
    Empfehlung: ephemeral=false (persistenter Knoten), reusable nach Bedarf,
    ein passendes ACL-Tag. Wird per cloud-init als Docker-Secret abgelegt.
  EOT
  type        = string
  sensitive   = true
}

variable "jnpt_master_key" {
  description = <<-EOT
    JanuaPort-Vault-Master-Key als 64 Hex-Zeichen (= 32 Byte). Erzeugen mit
    `openssl rand -hex 32`. Wird per cloud-init als Docker-Secret abgelegt
    (JNPT_MASTER_KEY_FILE). ACHTUNG: Verlust = die verschlüsselten Credentials
    sind unwiederbringlich. GETRENNT vom Server sichern.
  EOT
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9a-fA-F]{64}$", var.jnpt_master_key))
    error_message = "jnpt_master_key muss exakt 64 Hex-Zeichen sein (openssl rand -hex 32)."
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

# WARNUNG (wie bei git_*): Eine Änderung von image_ref/registry_token ändert die
# cloud-init/user_data der VM. Ein `terraform apply` gegen eine BESTEHENDE VM
# triggert bei hcloud deshalb ein VM-REPLACEMENT (die user_data ist Teil des
# Server-Ressourcen-Fingerprints) — der neue Wert greift erst beim nächsten
# bewussten Neuaufbau. Für ein reines Image-Update auf der laufenden VM NICHT
# `apply`, sondern das Update-Runbook des Produkts fahren: JANUAPORT_IMAGE in
# der .env auf den neuen Tag setzen, `docker compose pull && up -d`.
variable "image_ref" {
  description = <<-EOT
    Gepinnter Image-Tag, den die VM aus der Registry zieht, z. B.
    ghcr.io/januaport/januaport:0.1.2. PFLICHT (kein Default): bewusst KEIN
    `latest`, damit der Deploy reproduzierbar auf einem festen Tag steht.
    cloud-init schreibt den Wert als JANUAPORT_IMAGE in die .env neben der
    Prod-Compose; `docker compose pull` holt das Image.
  EOT
  type        = string
}

variable "registry_token" {
  description = <<-EOT
    OPTIONAL: GitHub-PAT für `docker login ghcr.io`, um das Image aus einem
    PRIVATEN GHCR-Package zu ziehen. WICHTIG: GHCR akzeptiert an der Container-
    Registry NUR classic PATs mit der EINEN Berechtigung `read:packages` —
    fein-granulare PATs funktionieren dort NICHT. Leer lassen, sobald das
    Package public ist (dann ist kein Login nötig).

    Sicherheit/Trade-off (ehrlich): Der Token landet — wie die anderen Secrets —
    im Terraform-State und in der cloud-init-user_data im KLARTEXT (State ist
    deshalb gitignored, lokal halten). Auf der VM reicht cloud-init ihn NUR über
    `docker login --password-stdin` (nie in der Prozessliste/im Log/in einer
    URL). Dass `docker login` die Auth danach in /root/.docker/config.json
    persistiert, ist akzeptiert. Verlust unkritisch: read-only, package-scoped,
    jederzeit in GitHub rotierbar.
  EOT
  type        = string
  sensitive   = true
  default     = ""
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
    Terraform-State. Ohne ihn ist der Aktuator inert, und genau das ist der
    gewollte Zustand direkt nach der Provisionierung.
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
    Git-Repository (HTTPS), das cloud-init auf der VM klont — NUR für die
    Konfig-Dateien (docker/docker-compose.prod.yml, docker/Caddyfile,
    docker/tailscale-serve.json aus dem JanuaPort-Produkt-Repo). Das Image wird
    NICHT on-VM gebaut, sondern als Prebuilt-Image aus der Registry gezogen
    (siehe `image_ref`). Für ein PRIVATES Repo zusätzlich `git_token` setzen
    (authentifizierter Klon — der Token wird NICHT in die URL geschrieben).
  EOT
  type        = string
  default     = "https://github.com/JanuaPort/januaport.git"
}

variable "git_ref" {
  description = "Branch/Tag/Commit, der auf der VM ausgecheckt wird."
  type        = string
  default     = "main"
}

variable "git_token" {
  description = <<-EOT
    OPTIONAL: GitHub-PAT für den authentifizierten Klon eines PRIVATEN Repos —
    NUR für die Konfig-Dateien (die VM baut nichts, sie zieht das Prebuilt-Image
    via `image_ref`/`registry_token`). Leer lassen für ein öffentliches Repo
    (anonymer HTTPS-Klon).

    Zweck: cloud-init klont `git_repo` damit über HTTPS. Empfehlung:
    fein-granularer, READ-ONLY PAT mit Geltung NUR für dieses eine Repo und
    NUR der Berechtigung "Contents: read-only". Mehr braucht der Klon nicht.
    (Hinweis: für das GHCR-Image-Pull braucht es dagegen ein classic PAT
    `read:packages` — `registry_token` —, GHCR unterstützt keine
    fein-granularen PATs dafür.)

    Sicherheit/Trade-off (ehrlich): Der Token landet — wie die anderen Secrets
    — im Terraform-State und in der cloud-init-user_data im KLARTEXT (State ist
    deshalb gitignored, lokal halten). Auf der VM wird der Token NICHT
    persistiert: kein Eintrag in der `git remote`-URL bzw. `.git/config`, kein
    Logging; cloud-init reicht ihn nur kurzlebig per GIT_ASKPASS an `git clone`
    und scrubbt ihn danach. Verlust ist unkritisch: read-only, repo-scoped,
    jederzeit in GitHub rotierbar.
  EOT
  type        = string
  sensitive   = true
  default     = ""
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
    ["203.0.113.4/32"]). Bewusst NICHT 0.0.0.0/0. Wer wirklich kein SSH von
    außen will, trägt explizit eine leere Liste `[]` ein.
    Hinweis: Verwaltung läuft ohnehin primär über das Tailnet.
  EOT
  type        = list(string)
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
