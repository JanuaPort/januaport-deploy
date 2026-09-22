# Ausgaben des Hetzner-Deployments (JanuaPort/januaport#776, generisch
# abgeleitet aus deploy/hetzner/ im Produkt-Repo, #107).

output "server_ipv4" {
  description = "Öffentliche IPv4-Adresse der VM."
  value       = hcloud_server.jnpt.ipv4_address
}

output "server_ipv6" {
  description = "Öffentliche IPv6-Adresse der VM."
  value       = hcloud_server.jnpt.ipv6_address
}

output "dns_hint" {
  description = "Nächster Schritt: DNS-A-Record setzen, damit Caddy ein TLS-Zertifikat ausstellen kann."
  value       = "DNS setzen: A-Record  ${var.domain}  ->  ${hcloud_server.jnpt.ipv4_address}  (und optional AAAA -> ${hcloud_server.jnpt.ipv6_address}). Danach holt Caddy automatisch das Let's-Encrypt-Zertifikat."
}

output "admin_access_hint" {
  description = "Wo die Admin-Fläche liegt (NICHT öffentlich)."
  value       = "Admin-Fläche (GUI, /admin/mcp, /api/admin, /metrics) ist NUR im Tailnet erreichbar: https://${var.ts_hostname}.<dein-tailnet>.ts.net  — öffentlich ist nur https://${var.domain}/mcp + /healthz + OAuth-Discovery."
}
