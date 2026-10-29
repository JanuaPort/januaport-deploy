# Windows: Docker Compose with TLS on the LAN

**English** · [Deutsch](README.md)

Package A (#1246), tested locally with Docker Desktop. Requires Windows 10/11
Pro (amd64), WSL2 Linux containers, Docker Desktop **≥ 4.44.3**
(CVE-2025-9074), Compose ≥ 2.35 and PowerShell ≥ 5.1. Keep **“Expose daemon on
tcp://localhost:2375” disabled**; approve automatic updates only after review.
TCP ports 443 and 8484 must be available. Registry/GitHub access is required.

## Two commands

The publisher must first publish the immutable **profile release tag**
`windows-v0.1.0` at the reviewed commit. The following URL works only after
publication. `<tag>` in distribution instructions means this profile release,
not the core image tag or `main`. The installer downloads the profile and its
checksum manifest from this fixed tag. New profile releases must update the
embedded reference and checksums together. The initial script download trusts
HTTPS/GitHub; the checksums are not an independent publisher signature.

```powershell
curl.exe -fLo e.ps1 https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.1.0/windows/einrichten.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1
```

Enter only a core image tag (e.g. `0.87.1`) or `sha256:<64 lowercase hex digits>`.
Docker resolves tags to registry digests. The installer creates
`%LOCALAPPDATA%\JanuaPort\windows\.env` with `JANUAPORT_IMAGE` (repository/tag)
and mandatory `JANUAPORT_IMAGE_DIGEST`; Compose combines them into a digest
reference. Caddy, OpenSSL and script-runner images are already pinned. A complete
existing profile is verified and started again, preserving its files, `.env`,
certificate and key, without downloading files or prompting for an image again.
Other existing or incomplete target directories are rejected. Use
`-Directory C:\JanuaPort\windows` for another directory.

The script creates a self-signed ECDSA P-256 **leaf** once, valid for ten years
(3653 days), using a digest-pinned OpenSSL container. SANs include `127.0.0.1`,
`localhost`, the computer name and all current host IPv4 addresses. Certificate
and key live in the dedicated `tls-leaf` volume (default name
`jnpt-windows_tls-leaf`), mounted read-only by Caddy. There is no automatic
renewal or local CA. An incomplete existing certificate/key pair is rejected
without overwriting it. The script starts Compose, waits for `/healthz` and
checks that Caddy serves this exact certificate. The printed SHA-256 fingerprint
is computed from that PEM certificate in the volume.

The GUI output is exactly `Admin-GUI: http://127.0.0.1:8484`. Follow the product's
`docs/inbetriebnahme.md`: secure the master key, set the admin password and
create the first admin token.

## Pair a desktop runner

Verify the signed Windows executable using `desktop-runner/README.md` in
`JanuaPort/januaport-plugins`. Create a Windows device and a one-time pairing
code in the local admin GUI. Transfer the locally displayed fingerprint over a
trusted channel; retrieving a certificate from another LAN machine does not
establish its identity.

```powershell
.\desktop-runner.exe pair --url https://<server-LAN-IP> --code <PAIRING-CODE> --fingerprint <64-hex-digits>
.\desktop-runner.exe run
```

On the server use `https://127.0.0.1`. **Never import a CA into any certificate
store (SEC W10).** Do not use `--ca` or disable TLS validation in the runner.
Caddy loads only `/certs/cert.pem` and `/certs/key.pem`.

The reviewed desktop runner (`desktop-runner/internal/client/http.go`,
`NewAPI`/`VerifyConnection`) checks only the exact DER leaf's SHA-256 in fingerprint
mode. It does not check hostname/IP SANs, the CA chain or validity dates.
A new DHCP IP therefore does not require a new certificate, but the saved server
URL must remain reachable. Pair again with the new `--url` and the same
fingerprint when changing addresses. Prefer a fixed IP, DHCP reservation or
a reliably resolvable computer name.

**Explicit certificate replacement**, for example after a compromise or before
the ten-year validity ends:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\JanuaPort\windows\einrichten.ps1" -NeuesZertifikat
```

Add `-Directory <profile-directory>` for a custom installation. This explicit
command stops Caddy, replaces the certificate/key with current SANs and starts
it again. **Pair every runner again with a new code and the new fingerprint.**
Normal setup reruns and Caddy restarts preserve the certificate. Keep the TLS
volume: losing it and generating another certificate also changes the pin.

For desktop packages, configure `plugin-script-runner` (runtime key) and
`plugin-script-runner-git` (read-only deploy key) in basic setup, then set the
repository and desktop pin with full commit, path and target device under the
script-runner settings. Named volumes provide the plugin directories; the core
atomically writes keys and pins. Compose manages the sidecar directly, without
a host actuator; leave its catalog selection unmanaged. The fetcher checks
commits against the repository default branch. Verify package readiness and a
completed job separately from pairing.

## Security defaults and firewall

- **W6:** `runc`, no sandbox service or optional sandbox profile. Valid local
  pin calls return `refused/state`, `isolation=invalid`; local schedules have no
  execution slot. Desktop packages work independently. The original sandbox
  healthcheck honestly remains **unhealthy/503**; avoid `up --wait`.
- **W8:** Only TCP 443 is published to the LAN. Caddy shares `jnpt`'s network
  namespace and forwards to real loopback `http://127.0.0.1:8484`. This satisfies
  the device pairing check under Docker Desktop NAT. Only `/api/device/v1/*`
  and exact `/healthz` are forwarded. Everything else returns 404, including
  the GUI, `/admin/mcp`, `/api/admin/*`, `/metrics` and `/mcp`. Port 8484 binds
  to `127.0.0.1` only; Caddy's admin API is disabled. Enable the commented exact
  `/mcp` block only when a LAN AI client needs it and after reviewing permissions
  and route tests again.
- **W9:** Example in an administrative PowerShell:

  ```powershell
  New-NetFirewallRule -DisplayName 'JanuaPort HTTPS LAN' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 443 -RemoteAddress LocalSubnet -Profile Private
  ```

  Use a private network and keep the default inbound firewall policy at Block.
  Restrict broader Docker/WSL allow rules; adding a narrow rule does not revoke
  broad rules. Test 443 from the local subnet and rejection from outside it;
  verify that 8484 cannot be reached from the LAN. Do not forward 443 at the
  router. The installer does not change the host firewall.
- **Caddy and the firewall are the edge (SEC K1/K2):** Caddy forwards from inside
  the `jnpt` network namespace, so the core sees every request as loopback. The
  core's checks for local senders (pairing without HTTPS, local devices only)
  therefore do not apply in this profile. The boundary is Caddy alone (TLS on 443
  only, no plaintext listener, covered by a test) plus the Windows firewall (W9).
  Before production data, the acceptance report lists `Get-NetFirewallRule` for 443
  and for the Docker processes. No rule may allow "Any" as remote address. Where
  possible, add a negative probe from a foreign subnet.

An internal Docker network alone does not isolate all Windows/WSL host services.
The Linux iptables guidance in `compose/README.md` is not Windows verification;
check host/WSL firewall policies with the operator. The fetcher has a separate
egress network and only sees the Git key; the mediator sees the runtime key.
Containers receive no Docker socket.

## Checks, updates and limits

From the installed profile directory:

```powershell
docker compose config --quiet
curl.exe -fsS http://127.0.0.1:8484/healthz
curl.exe -k -i https://127.0.0.1/api/device/v1/
curl.exe -k -i https://127.0.0.1/
```

Expect 200, device API JSON/401 without a token, and 404 respectively. `-k` is
for these manual diagnostics only; runners use the fingerprint. Health does not
prove package delivery or job completion.

Repository checks: `python -B -m unittest discover -s windows/test -v`
(Python standard library and Docker). See [test/README.md](test/README.md) for
live checks and mutations. `.gitattributes` preserves the LF bytes covered by
SHA256SUMS in both Windows checkouts and raw downloads.

Updates, backup and autologon are package B. Docker Desktop must already be
running; unattended startup without a user session is unverified. Tailscale
is outside package A.

## Remote maintenance

Through the customer's remote-support tool. The customer accepts every session.
