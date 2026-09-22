# Hetzner-Single-Node-Deployment für JanuaPort (JanuaPort/januaport#776,
# generisch abgeleitet aus deploy/hetzner/ im Produkt-Repo, #107).
#
# Legt an: SSH-Key, Firewall (default NUR optionales SSH — s. u.), persistentes
# Volume für /data, und den Server mit cloud-init, das Docker installiert und
# die Prod-Compose (drei Container) hochbringt.
#
# WICHTIG: Es wird KEIN Port 8484 geöffnet — JanuaPort ist von außen nicht direkt
# erreichbar. Die öffentliche Web-Fläche (80/443) ist standardmäßig ZU
# (public_web_enabled = false): ohne sie ist die Anlage nur im Tailnet
# erreichbar. Tailscale braucht KEINE Inbound-Regel (NAT-Traversal/DERP über
# Outbound).

# SSH-Key für den Admin-Zugang zur VM.
resource "hcloud_ssh_key" "jnpt" {
  name       = "${var.name}-admin"
  public_key = var.ssh_public_key
}

# Firewall: deny-by-default. Die öffentliche Web-Fläche (80/443) entsteht nur
# bei public_web_enabled = true (bewusster, dokumentierter Handgriff; s.
# variables.tf). Bleibt: SSH (22) aus ssh_allowed_cidr (Pflichtvariable, s.
# variables.tf). Outbound bleibt offen (Tailscale/Docker-Pull).
resource "hcloud_firewall" "jnpt" {
  name = "${var.name}-fw"

  # Öffentliche Web-Ports NUR bei public_web_enabled = true.
  dynamic "rule" {
    for_each = var.public_web_enabled ? [1] : []
    content {
      description = "HTTP (ACME-Challenge + Redirect auf HTTPS)"
      direction   = "in"
      protocol    = "tcp"
      port        = "80"
      source_ips  = ["0.0.0.0/0", "::/0"]
    }
  }

  dynamic "rule" {
    for_each = var.public_web_enabled ? [1] : []
    content {
      description = "HTTPS (öffentliche Tool-/SSO-Fläche via Caddy)"
      direction   = "in"
      protocol    = "tcp"
      port        = "443"
      source_ips  = ["0.0.0.0/0", "::/0"]
    }
  }

  dynamic "rule" {
    for_each = var.public_web_enabled ? [1] : []
    content {
      description = "HTTP/3 (QUIC) — optional, gleiche Fläche wie 443"
      direction   = "in"
      protocol    = "udp"
      port        = "443"
      source_ips  = ["0.0.0.0/0", "::/0"]
    }
  }

  # SSH nur aus den erlaubten Quellen (ssh_allowed_cidr ist Pflicht — leere
  # Liste explizit eintragen, wenn kein SSH gewünscht ist).
  dynamic "rule" {
    for_each = length(var.ssh_allowed_cidr) > 0 ? [1] : []
    content {
      description = "SSH (nur aus ssh_allowed_cidr)"
      direction   = "in"
      protocol    = "tcp"
      port        = "22"
      source_ips  = var.ssh_allowed_cidr
    }
  }
}

# Persistentes Volume für /data (SQLite-DB). Überlebt einen Server-Neuaufbau.
resource "hcloud_volume" "data" {
  name     = "${var.name}-data"
  size     = var.volume_size
  location = var.location
  format   = "ext4"
}

# Volume an den Server hängen. automount=false → cloud-init formatiert/mountet
# selbst (idempotent, overwrite:false), damit ein Re-Deploy die bestehende DB
# nicht überschreibt.
resource "hcloud_volume_attachment" "data" {
  volume_id = hcloud_volume.data.id
  server_id = hcloud_server.jnpt.id
  automount = false
}

# Der Server. cloud-init (user_data) installiert Docker + Compose und bringt die
# Prod-Compose hoch. Das Volume wird automatisch attached; den stabilen
# Geräte-Pfad reichen wir ins Template (Hetzner: /dev/disk/by-id/scsi-0HC_Volume_<id>).
resource "hcloud_server" "jnpt" {
  name        = var.name
  server_type = var.server_type
  image       = var.image
  location    = var.location

  ssh_keys     = [hcloud_ssh_key.jnpt.id]
  firewall_ids = [hcloud_firewall.jnpt.id]

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    domain            = var.domain
    acme_email        = var.acme_email
    ts_hostname       = var.ts_hostname
    master_key        = var.jnpt_master_key
    tailscale_authkey = var.tailscale_authkey
    git_repo          = var.git_repo
    git_ref           = var.git_ref
    git_token         = var.git_token
    # Prebuilt-Image aus einer Container-Registry: gepinnter Tag + optionaler
    # read:packages-PAT für ein privates Package.
    image_ref      = var.image_ref
    registry_token = var.registry_token
    # Versions-Check (optional): beide leer = Check aus (offline-first). Der
    # Public Key ist kein Geheimnis (s. variables.tf).
    update_manifest_url = var.update_manifest_url
    update_public_keys  = var.update_public_keys
    # Host-Aktuator: die Repository-Allowlist der Vertrauensgrenze. Der
    # Prüf-Token wird NICHT hier gereicht — er käme sonst in den State.
    updater_image_repo = var.updater_image_repo
    # Stabiler Geräte-Pfad des attachten Volumes (Hetzner-Konvention).
    volume_device = "/dev/disk/by-id/scsi-0HC_Volume_${hcloud_volume.data.id}"
  })

  labels = {
    app = "jnpt"
  }
}
