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
iwr https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.1.0/windows/einrichten.ps1 -OutFile e.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1
```

Enter only a core image tag (e.g. `0.87.1`) or `sha256:<64 lowercase hex digits>`.
Docker resolves tags to registry digests. The installer creates
`%LOCALAPPDATA%\JanuaPort\windows\.env` with `JANUAPORT_IMAGE` (repository/tag)
and mandatory `JANUAPORT_IMAGE_DIGEST`; Compose combines them into a digest
reference. Caddy and script-runner images are already pinned. Existing target
directories are rejected. Use `-Directory C:\JanuaPort\windows` for another
new directory. The script verifies the downloaded files, starts Compose, waits
for `/healthz`, then prints the SHA-256 fingerprint of Caddy's DER **leaf**.

Open the admin GUI locally at <http://127.0.0.1:8484> and follow the product's
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

On the server use `https://127.0.0.1`. Use numeric IP addresses rather than
arbitrary DNS aliases: connections without SNI and `localhost` receive the same
certificate. **Never import the CA into any certificate store (SEC W10).**
Do not use `--ca` or disable TLS validation in the runner. Caddy's
`skip_install_trust` also prevents CA installation inside the container.

Caddy's internal leaves are valid for 12 hours by default and renew automatically.
A changed certificate invalidates the old pin. Dot-source the installed script
and call `Get-LeafFingerprint` locally; verify the new value and pair again with
a new code. This package does not distribute renewed fingerprints automatically;
long-term operation requires an operational solution for this.

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

Through the operator's tool; the customer accepts the session.
