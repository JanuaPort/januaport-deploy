# Provider- und Terraform-Versionsanforderungen (JanuaPort/januaport#776,
# generisch abgeleitet aus deploy/hetzner/ im Produkt-Repo, #107).
# hetznercloud/hcloud ist der offizielle Hetzner-Cloud-Provider.

terraform {
  required_version = ">= 1.5"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}
