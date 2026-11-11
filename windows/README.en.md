# Windows: Docker Compose with TLS on the LAN

**English** · [Deutsch](README.md)

Package A with B1 mail forwarding, B2 service operation, B3 backups and B5 updates (#1246), tested locally with Docker Desktop. Requires Windows 10/11
Pro (amd64), WSL2 Linux containers, Docker Desktop **≥ 4.44.3**
(CVE-2025-9074), Compose ≥ 2.35 and PowerShell ≥ 5.1. Keep **“Expose daemon on
tcp://localhost:2375” disabled**, AutoStart enabled, automatic downloads/updates disabled. Review updates manually.
TCP ports 443 and 8484 must be available. Registry/GitHub access is required.

### LAN access during setup (N5)

B4 found no Docker allow rule. Docker Desktop had created only two block rules
for the Public profile because the firewall dialog was left unanswered.
The effect of choosing “Allow” was not measured.
Do not answer the Docker Desktop firewall dialog with “Allow” for public networks.
At every real acceptance, list Docker application filters and all port filters
opening 443 using [RUNBOOK, N5-1](RUNBOOK.md). Apart from “JanuaPort 443 LAN”,
no allow rule may open 443; disable additional rules or restrict them to
`LocalSubnet`. For LAN desktop runners, the operator or their IT checks the network
profile in an administrative PowerShell: it must be **Private** or **Domain**.
Have IT verify trust before reclassifying a public network as private. Then
allow TCP 443 only from `LocalSubnet` on `Private,Domain` profiles:

<!-- N5 -->
```powershell
Get-NetConnectionProfile
New-NetFirewallRule -DisplayName 'JanuaPort 443 LAN' -Direction Inbound -Protocol TCP -LocalPort 443 -RemoteAddress LocalSubnet -Action Allow -Profile Private,Domain
```

Do not use `Any` for remote addresses. This is a manual operator step;
`einrichten.ps1` changes neither firewall nor network profile. Verify HTTPS
from a workstation in the local subnet afterwards. Admin port 8484 stays on loopback.


## Two commands

The publisher must first publish the immutable **profile release tag**
`windows-v0.3.0` at the reviewed commit. The following URL works only after
publication. `<tag>` in distribution instructions means this profile release,
not the core image tag or `main`. The installer downloads the profile and its
checksum manifest from this fixed tag. New profile releases must update the
embedded reference and checksums together. The initial script download trusts
HTTPS/GitHub; the checksums are not an independent publisher signature.

After [service setup](#service-operation-b2), the operator commissions the system
in the `jnpt-dienst` session. The maintenance account only triggers tasks.

```powershell
curl.exe -fLo e.ps1 https://raw.githubusercontent.com/JanuaPort/januaport-deploy/windows-v0.3.0/windows/einrichten.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1
```

Enter only a core image tag (e.g. `0.87.1`) or `sha256:<64 lowercase hex digits>`.
Docker resolves tags to registry digests. The installer creates
`C:\JanuaPort\windows\.env` with `JANUAPORT_IMAGE` (repository/tag)
and mandatory `JANUAPORT_IMAGE_DIGEST`; Compose combines them into a digest
reference. Caddy, OpenSSL and script-runner images are already pinned. A complete
existing profile is verified and started again, preserving its files, `.env`,
certificate and key, without downloading files or prompting for an image again.
Unmodified 0.1.0 and 0.2.0 profiles use the [upgrade path](#from-010-or-020-to-030); other
incomplete target directories are still rejected. Use
`-Directory <profile-directory>` for another directory; service tasks always
use `C:\JanuaPort\windows`.

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

## From 0.1.0 or 0.2.0 to 0.3.0

After GATE publishes the tag, download the **new** `einrichten.ps1` (see “Two
commands”) and run it in `jnpt-dienst` with the existing profile directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\e.ps1 -Directory '<existing profile directory>'
```

The script recognizes the three unchanged original `windows-v0.1.0` files
(`docker-compose.yml`, `Caddyfile`, `einrichten.ps1`) by their fixed SHA-256 hashes.
For `windows-v0.2.0`, all eleven release-managed original files must be
present unchanged; their published hashes are also embedded in the installer.
Any changed file blocks automatic upgrade.
`.env` must exist; the old `SHA256SUMS` may be present or absent. It downloads the
complete profile and manifest only from `windows-v0.3.0` into a temporary directory
and verifies everything before writing to the target. It then replaces the
release-managed files and adds the missing READMEs, `.gitignore`, runbook, B2/B3
scripts including `jnpt-sperren.ps1`, `jnpt-update.ps1` and both acceptance checklists. Setup and upgrade
also create the local `backups\` directory under the B-7 ACL; this runtime directory
is excluded from SHA256SUMS. Locally changed legacy files require manual
reconciliation and abort before downloading. Download or checksum failure leaves
existing files unchanged. A second successful run downloads nothing.

**`.env` and all existing contents under `secrets/` are preserved byte for byte.**
Missing mail secret files are created empty as before. There is no image prompt
or change to the saved core image. Without `-NeuesZertifikat`, the certificate
and key remain unchanged. Local staging by `dienst-einrichten.ps1` recognizes
the same 0.1.0 or 0.2.0 original files and uses its verified release directory.
After the 0.2.0 → 0.3.0 file upgrade, rerun `dienst-einrichten.ps1` as
administrator from the verified 0.3.0 release with the previous `-BackupTarget`
to register “JanuaPort Update”. This file upgrade preserves the core image.
Acceptance is covered by [B5](PRUEFSTEIN-B5.md).

This file upgrade moves neither the profile directory nor engines or volumes
between Windows accounts. Service operation still uses `C:\JanuaPort\windows`;
`%LOCALAPPDATA%\JanuaPort\windows` is a legacy location, not the new default.
Identify the account holding the existing engine/data before changing deployment
and exercise the upgrade on the test machine under [B4](PRUEFSTEIN-B4.md).
The script does not automatically migrate another Windows account's data.

**In-place upgrade only under `jnpt-dienst`:** The script requires the
`jnpt-dienst` session. If 0.1.0 ran under a personal account, there is no
in-place upgrade, only the following path.

**Data from another Windows account:** Docker Desktop keeps containers, images and,
as far as we know, volumes per Windows account. If 0.1.0 ran under a personal account,
the installation's data lives there and not with `jnpt-dienst`. The file upgrade does
not move it. Run `jnpt backup` in the old account first and keep the master key
separately, then set up again under `jnpt-dienst` and restore the backup. Only once the installation
runs under `jnpt-dienst` and the restore is checked, run `docker compose down -v`
in the old profile folder under the old account. Otherwise a complete installation
with vault and master key stays there, and Docker Desktop may start it again at
sign-in. Afterwards `docker volume ls` in the old account shows no
`jnpt-windows_*` volume. This path is a step of the B4 checkpoint.

The TLS certificate belongs to the old engine's `tls-leaf` volume. Switching
accounts creates a new certificate with a new fingerprint under `jnpt-dienst`.
After B4 step 2a, pair every previously paired desktop runner again with a new
pairing code and the new fingerprint transferred through a trusted local channel.

## Service operation (B2)

On the intended deployment machine, use an administrative PowerShell in the
`windows` directory of the complete, verified `windows-v0.3.0` release:
`.\dienst-einrichten.ps1 -BackupTarget 'E:\JanuaPort-Backup'`. GATE publishes
the tag after review. The script verifies `SHA256SUMS`, creates `jnpt-dienst`,
adds it to `docker-users`. **B-7/F5:** For both `C:\JanuaPort` and
`C:\JanuaPort\windows`, setup prepares a complete protected DACL with exactly
three explicit Allow rules: `jnpt-dienst`, Administrators and SYSTEM receive
FullControl with ContainerInherit and ObjectInherit. R4 also requires
Propagation None: no InheritOnly or NoPropagate and no additional ACEs,
whether Allow or Deny, explicit or inherited. One
`Directory.SetAccessControl` call replaces only the Access section, without
clearing it first. Additional grants and inheritance from the parent are
removed together; owner, group and audit remain unchanged. An already matching
protected DACL is not written again, preserving access to inherited files on
repeat runs. Profile files are staged afterwards. For installations already
affected by F5, see the [manual RUNBOOK repair](RUNBOOK.md#f5-reparatur-nach-entzogenen-dateirechten).
Different existing files are rejected outside the
verified upgrades from 0.1.0 or 0.2.0; `.env` and secrets are preserved. Initial
installation adds `.env` to a verified B2 profile that does not yet have one.

A random password is never displayed or saved to a password file. Repeated runs
keep it; `-KennwortNeu` deliberately resets it and reconfigures autologon,
including after an administrator reset. After invoking Autologon64, setup checks
the Winlogon values every 500 ms for up to 10 seconds before reporting a missing
confirmation. Master key, admin password and SMTP/Graph
secrets live in profile files or volumes, never in Credential Manager or EFS;
they do not depend on this account's DPAPI secrets. Sysinternals autologon uses
an LSA secret readable by administrators. Its CLI briefly needs a plaintext
process argument, visible to privileged process inspection; the script does
not log it.

The exact `Autologon64.exe` is downloaded only from
`https://download.sysinternals.com/files/AutoLogon.zip`, checked against its
SHA-256 in `SHA256SUMS`, then checked for a valid Microsoft Authenticode
signature. A mismatch aborts without a fallback. The licensed binary is local
only and excluded from the public repository. Changed upstream bytes require a
reviewed pin update.

“JanuaPort Sperren bei Anmeldung” starts the fixed
`C:\JanuaPort\windows\jnpt-sperren.ps1` with hidden PowerShell immediately at
logon, without a fixed delay. The B-7 ACL protects that path. The script checks
once per second for `explorer.exe` in its own session, calls `LockWorkStation`, and
verifies the lock through `WTSQuerySessionInformation` /
`WTSSessionInfoEx.SessionFlags`. Without confirmation it retries every second.
Readiness and locking share a 120-second deadline. Failure returns a nonzero
exit code visible in Task Scheduler; there is no logoff or shutdown fallback.
Exactly one line per logon in `C:\JanuaPort\windows\log\sperren.log` records the
ISO start time, ISO confirmed-lock time or `nicht_gesperrt`, attempt count and
exit code. It contains no usernames or window contents and retains the last
100 lines. Setup creates the directory under the B-7 ACL. A log failure also
returns a nonzero exit code.
After reboot, the `jnpt-dienst` desktop is visible and unlocked for at most about 7 seconds
until locking is confirmed (measured in checkpoint B4: lock 12.6 seconds after start, about
6 seconds of which are conhost and PowerShell start-up). Protection during this interval depends on controlling
access to the operator's room. A password-protected screen saver also locks after
60 seconds. `powercfg` disables AC/battery standby and
hibernation. The account's `.wslconfig` sets `[wsl2]` / `memory=4GB`; conflicting
existing settings require manual reconciliation. The script does not restart
Docker or WSL; the limit takes effect at the next WSL start.

Docker Desktop settings are only checked: AutoStart on, TCP 2375 off, automatic
downloads/updates off. The required keys are `autoStart=true`,
`exposeDockerAPIOnTCP2375=false`, `autoDownloadUpdates=false`, `disableUpdate=true`
and `silentModulesUpdate=false`, including component updates ([Docker reference](https://docs.docker.com/enterprise/security/hardened-desktop/settings-management/settings-reference/)).
Missing, unknown or different values cause failure.
**Start Docker Desktop once as `jnpt-dienst` before `dienst-einrichten.ps1`,**
accept its license and set these options. Setup reads that account's
`%APPDATA%\Docker\settings-store.json`, falling back to `settings.json`.
If both are absent, it fails with the fixed message:
“Docker Desktop einmal in jnpt-dienst starten und die Einstellungen pruefen (AutoStart an, 2375 aus, Auto-Update aus)”.
If the account does not yet exist, an initial preparation run creates the
account, lock and autologon and stops at this message. The operator then
temporarily resets `jnpt-dienst` to a personally entered password
as local administrator, signs in, configures Docker Desktop and accepts its
license. Afterwards, the operator reruns setup as administrator
with `-KennwortNeu` and reboots to restore the random password, matching autologon
and lock. This is local commissioning before any production data. The operator performs initial commissioning and answers
the image prompt there. The service provider never works in this session.
“JanuaPort Anlage starten” is an on-demand task; “JanuaPort Sicherung” runs
daily at 20:00. “JanuaPort Update” also has no trigger. All three use the account's interactive token without a stored task
password. The maintenance account only triggers tasks:

```powershell
schtasks /run /tn "JanuaPort Anlage starten"
schtasks /run /tn "JanuaPort Sicherung"
schtasks /run /tn "JanuaPort Update"
```

`docker-users` effectively grants administrator control of the computer.
Console protection relies on locking and controlled access to the operator's room.
Members can bind-mount `C:\` into containers. “Standard user” is an
organizational choice. [B4](PRUEFSTEIN-B4.md) requires a photo and the earliest password prompt
while pressing a key every 5 seconds from the first image after reboot,
together with task result and log time; a photo alone does not prove locking.
acceptance remains open.

[Docker's Windows installation documentation](https://docs.docker.com/desktop/setup/install/windows-install/)
says containers and images cannot be shared across accounts with the WSL 2
backend. That passage does not explicitly name volumes. The full “engine and
volumes per Windows user” finding still needs B4 verification; it is not a
blanket claim about other backends. Installation, updates (B5) and
backups all run in `jnpt-dienst`.

Docker Desktop is free for businesses with **fewer than 250 employees AND less
than USD 10 million annual revenue**. Other professional use generally needs a
paid subscription, as do government entities; consult the [license terms](https://docs.docker.com/subscription/desktop-license/).
Windows 10 regular support ended on 14 October 2025. Continued use requires a
separate ESU assessment, which does not establish Docker Desktop support.
Check the current support matrix; prefer a supported Windows 11 Pro version.

## Backups (B3)

v1 uses **USB**, preferably rotating drives. The operator creates the target
folder (for example `E:\JanuaPort-Backup`) and `.jnpt-backup-ziel` marker on each
drive, granting `jnpt-dienst` write access. The script creates neither target
nor marker and never falls back to another target. Run in `jnpt-dienst` or
trigger the task:

```powershell
powershell -NoProfile -File C:\JanuaPort\windows\jnpt-backup.ps1 -Target 'E:\JanuaPort-Backup'
```

Compose binds the relative profile directory `./backups` to `/backups`. Setup
creates `C:\JanuaPort\windows\backups` under the B-7 ACL. The only container
command is `docker compose exec -T jnpt /jnpt backup --output /backups/<name>`.
The core writes atomically using a temporary file and rename. The distroless
image has no file utilities; the script reads size and SHA-256 on the host,
copies exactly that file to `.teil` at the destination, verifies size/hash,
renames it and verifies again. It then removes the local staging file.
Every error returns nonzero and removes the run's own destination file.
A staging removal failure also invalidates the run and removes its destination.
Staging cleanup only deletes names matching `jnpt-<UTC-time>-<GUID>.jnpt-backup`,
including leftovers from earlier runs; foreign files remain untouched.
The exact pattern is `^jnpt-[0-9]{8}T[0-9]{9}Z-[a-f0-9]{32}\.jnpt-backup$`.
Older external backups are not automatically deleted. Monitor free space and
`LastTaskResult`.

**B4/F4 still requires deployment evidence:** the nonroot core must be able to
write and atomically rename on the Docker Desktop bind mount. Run
`python -B windows/test/backup_live.py` against the real pinned core in its own
project. A locally blocked live test is not success; BOX must rerun it.
The backup path has no helper-container fallback.
Inventory leftovers from earlier broken runs in the volume's `/data/backups`
separately with LEAD/BOX; this host workflow only cleans `backups\`.

**Keep the master key separately from backups.** The script never copies the
key file or all of `/data`. Without `JNPT_MASTER_KEY_FILE`, the key is beside
the database at `/data/jnpt.key`. Restoring on a separate test machine with a separately
provided key is required in [B4](PRUEFSTEIN-B4.md).

Optional SMB requires a dedicated backup account and share with write access
only there. Credentials exist only under `jnpt-dienst`; the operator re-enters
them after an administrator password reset. These scripts create no `cmdkey`
entries. A destination writable by the ZBOX does not protect against an attacker
on that ZBOX. A rotating, unplugged USB drive does. The operator chooses;
TeamViewer and the maintenance account do not receive these credentials.


### Restore into a fresh installation (N4)

Prepare the verified profile including `.env` and secret files. Supply the
separately stored key before the first `docker compose up`. `einrichten.ps1`
already starts the installation; if it has run, use `down` and move its generated
database and key aside as below. Keep the gateway stopped until restore finishes.
The target database must be empty: restore does not overwrite a database.
Use the same master key as the backup.

Compose sets neither `JNPT_DB_PATH` nor `JNPT_MASTER_KEY_FILE`. The image defaults
to `/data/jnpt.db` and its adjacent key `/data/jnpt.key`. Project name
`jnpt-windows` gives volume `jnpt-windows_jnpt-data`. For a deliberately different
configuration, place the key where `JNPT_MASTER_KEY_FILE` expects it before the
first start. The commands below apply to the shipped profile and use a pinned
one-time helper. They also assign a fresh volume to UID/GID 65532. Key mode is
600; BOX must confirm nonroot core readability and permissions in B4.

Adjust the USB key directory, backup directory and backup filename. The
separately stored file in the key directory must be called `jnpt.key`.
Existing database files and any key generated on first start are moved aside,
not deleted. Run the move-aside step even for a fresh installation:

<!-- N4 -->
```powershell
Set-Location C:\JanuaPort\windows
$HelperImage = 'busybox@sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec'
docker compose down
docker run --rm -v jnpt-windows_jnpt-data:/data $HelperImage sh -ec 'd=/data/beiseite-$(date -u +%Y%m%dT%H%M%SZ) && mkdir $d && for f in jnpt.db jnpt.db-wal jnpt.db-shm jnpt.key; do [ ! -e /data/$f ] || mv /data/$f $d/; done'
$KeyDirectory = 'E:\JanuaPort-Key'
docker run --rm -v jnpt-windows_jnpt-data:/data -v "${KeyDirectory}:/in:ro" $HelperImage sh -ec 'cp /in/jnpt.key /data/jnpt.key && chown 65532:65532 /data /data/jnpt.key && chmod 600 /data/jnpt.key'
$BackupDirectory = 'E:\JanuaPort-Backup'
$BackupFile = 'sicherung.jnpt-backup'
docker compose run --rm --no-deps -v "${BackupDirectory}:/in:ro" jnpt restore "/in/$BackupFile"
docker compose up -d
curl.exe --fail http://127.0.0.1:8484/healthz
```

Then verify an admin login: health must return 200 and the expected data must
be available.
Delete `/data/beiseite-<zeitstempel>` only after verifying the restore (healthz, login, read access).
Applying the block to an existing installation otherwise loses its previous state.
Unplug the USB drive afterwards. If a key copy was placed on the
computer, remove that copy after verification; retain the separately stored
original. See the deployed core version's `docs/disaster-recovery.md` for further
verification.

## Mail

`einrichten.ps1` still prompts only for the image tag. Before starting Compose,
it creates empty `secrets/smtp_password` and `secrets/graph_client_secret` files
in the profile directory, preserving existing contents. The profile starts as
before without mail settings.
**The operator attribute (Betreiber-Merkmal), network gate (Netztür), construction
phase (Bauphase) and case token (Fall-Token) require deliverable mail.**
Verify sending and actual receipt before using them.

Configure mail manually afterwards in the installed profile directory (by default
`C:\JanuaPort\windows`). Add these optional settings to `.env`;
missing or empty values remain empty in the container:

| Variable | Meaning |
|---|---|
| `JNPT_SMTP_HOST` | SMTP server, e.g. `smtp.example.org` |
| `JNPT_SMTP_PORT` | SMTP server port |
| `JNPT_SMTP_TLS` | TLS setting as defined by the core configuration |
| `JNPT_SMTP_FROM` | Sender, e.g. `sender@example.org` |
| `JNPT_SMTP_TO` | Recipient, e.g. `recipient@example.org` |
| `JNPT_SMTP_USERNAME` | SMTP username |
| `JNPT_NOTIFY_STATE` | Optional notification state path inside the container |
| `JNPT_NOTIFY_TRANSPORT` | Mail transport as defined by the core configuration |
| `JNPT_NOTIFY_GRAPH_TENANT_ID` | Graph tenant ID |
| `JNPT_NOTIFY_GRAPH_CLIENT_ID` | Client ID of the Graph application |
| `JNPT_NOTIFY_GRAPH_SENDER` | Graph sender, e.g. `sender@example.org` |
| `JNPT_NOTIFY_GRAPH_CLIENT_SECRET_EXPIRES` | Client-secret expiry as defined by the core configuration |
| `JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE` | For Graph only: `/run/secrets/graph_client_secret`; otherwise leave empty |

**The SMTP password must never appear in `.env` or the container environment.**
Store it only as the contents of the local `secrets/smtp_password` file (UTF-8
without BOM). The `secrets/` directory is gitignored; secret files are neither
distributed nor included in `SHA256SUMS`. Restrict local file access to the
responsible users and Docker Desktop. Compose mounts it as a secret at
`/run/secrets/smtp_password`. `JNPT_SMTP_PASSWORD_FILE` is fixed to this container
path; `JNPT_SMTP_PASSWORD` is not forwarded. Neither variable belongs in `.env`.

For Graph, set `JNPT_NOTIFY_TRANSPORT=graph` and the Graph settings in `.env`.
Also add this line to `.env`:

```dotenv
JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE=/run/secrets/graph_client_secret
```

**The Graph client secret must also never appear in `.env` or the container
environment.** Store it only in `secrets/graph_client_secret` (UTF-8 without BOM).
Compose mounts it at `/run/secrets/graph_client_secret`;
no other path is intended. Without a value set in `.env`,
`JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE` remains empty in the container.
`JNPT_NOTIFY_GRAPH_CLIENT_SECRET` is not forwarded and does not belong in `.env`.
**Graph v1 supports client-secret authentication only.**
`JNPT_NOTIFY_GRAPH_CERT_FILE` and `JNPT_NOTIFY_GRAPH_KEY_FILE` are not forwarded;
certificate authentication will follow if needed.

For SMTP, leave all `JNPT_NOTIFY_GRAPH_*` settings empty or absent in `.env`,
including `JNPT_NOTIFY_GRAPH_CLIENT_SECRET_FILE`. This avoids the core's warning
about ignored Graph settings. The secret mount with its empty file remains present.

`JNPT_ADMIN_URL` is fixed to `http://127.0.0.1:8484` (SEC W8): admin links are
accessible only on the machine running the installation.

Keep both secret files even without mail settings. `docker compose config` does
not check whether they exist. With a missing file, Compose may fail at startup
or mount a directory instead of a readable file. Before starting manually,
prepare the profile with `einrichten.ps1`. After changing `.env` or a secret
file, run these commands in the profile directory:

```powershell
docker compose config --quiet
docker compose up -d --force-recreate jnpt
```

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
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\JanuaPort\windows\einrichten.ps1" -NeuesZertifikat
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
- **W9:** Manually follow [LAN access during setup](#lan-access-during-setup-n5):
  Private or Domain profile, rule “JanuaPort 443 LAN”, TCP 443 from
  `LocalSubnet` only. Keep the default inbound firewall policy at Block.
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

On the internal `plugins` network, `jnpt` uses the fixed address `172.21.0.2`
in subnet `172.21.0.0/16`; sidecars receive addresses exclusively from the dynamic
pool `172.21.128.0/17`, keeping the gateway address free during restarts (#1355).
All long-running services use `restart: unless-stopped`; init services use `restart: "no"`.
When updating an existing profile, run `docker compose down` followed by
`docker compose up -d` once in the profile directory to recreate the network
with the new IPAM configuration; retain the named volumes.

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
live checks and mutations. SHA256SUMS covers Compose, Caddyfile, all five scripts
(`einrichten.ps1`, `dienst-einrichten.ps1`, `jnpt-sperren.ps1`, `jnpt-backup.ps1`, `jnpt-update.ps1`),
`.gitignore`, both READMEs, the runbook, B4/B5 checklists and the external autologon pin. `.gitattributes` preserves the LF bytes covered by
SHA256SUMS in both Windows checkouts and raw downloads.

## Updates (B5)

`jnpt-update.ps1` executes the core's plan. “JanuaPort Update” runs under
`jnpt-dienst`, Interactive/Limited with `IgnoreNew`, without a trigger.
Approve in the local admin GUI, then use the maintenance account:

```powershell
schtasks /run /tn "JanuaPort Update"
Get-ScheduledTaskInfo -TaskName 'JanuaPort Update' | Select-Object LastRunTime,LastTaskResult
Get-Content C:\JanuaPort\windows\log\update.log -Tail 100
```

The `jnpt` service receives `JNPT_UPDATE_MANIFEST_URL` and
`JNPT_UPDATE_PUBLIC_KEYS` from `.env`. Missing or empty means offline-first;
the core returns `action=none`. After changing feed settings, run
`docker compose up -d --force-recreate jnpt` in the profile folder as
`jnpt-dienst`. Only the core evaluates signatures, versions, migrations and
approval. The host script derives no policy from `current`, `latest`,
`on_failure` or `reason` and performs no restore or automatic reversal.

Sequence: plan → verified backup in a child process → pull
`ghcr.io/januaport/januaport@<digest>` → log the two old image lines →
atomically replace only those two `.env` lines (UTF-8 without BOM) → `up -d`
→ host health and TLS fingerprint → record the result.
Neither `latest` nor `reason` supplies an image reference. The digest must
be exactly `sha256:` followed by 64 lowercase hex digits; uppercase, newlines
and extra reference components are rejected. The core container runs only
`/jnpt`; OpenSSL only reads the certificate in `cert-init`. Replacement keeps
the `.env` DACL; the script writes no ACL.

| Exit | Meaning |
|---|---|
| 0 | `none` or healthy update (`installed`) |
| 1 | Wrong session or incomplete profile |
| 2 | Plan is not exactly one JSON line, Docker not ready, invalid digest or `rollback` (RUNBOOK) |
| 3 | Backup, pull or file replacement failed; backup/pull failure preserves `.env` |
| 6 | Start, host health or TLS failed; `failed` with digest, new state remains for diagnosis |

An unbookable result is logged only; the update's exit code is preserved.
Check `LastTaskResult=0` together with the log and GUI. Native output and raw
exception messages stay off the console and log. `log\update.log` retains
at most 100 lines without usernames. It records the old two image values
before replacement; retain them locally before a later run for manual recovery.
Each Docker call is bounded to 30 seconds, backup to 600 seconds. If Docker
is not ready after reboot, the plan attempt ends with a fixed error message
and exit 2; trigger again once ready. Host health has at most 90 attempts,
with a 3-second request timeout and 2-second pause; TLS has at most 30 attempts
with a 2-second pause, as in setup.

Manual recovery and concurrent daily backups: [RUNBOOK](RUNBOOK.md#7-update-b5).
BOX must complete [B5](PRUEFSTEIN-B5.md) on VM `jnpt-b4` before tagging
`windows-v0.3.0`. Docker Desktop continues to run in the logged-in, locked
`jnpt-dienst` session. Tailscale is outside this package.


## Remote maintenance

TeamViewer on acceptance under AVV Annex 3: a person at the operator accepts
every session. No unattended remote access or fixed remote-support password.
Local Windows autologon is separate. The service provider uses the maintenance
account and only triggers tasks.
