# januaport-deploy

**English** · [Deutsch](README.de.md)

Operations for JanuaPort: templates and guides for running JanuaPort in a given environment.

JanuaPort is a self-hosted MCP gateway. It connects AI assistants to a company's existing systems with
fine-grained permissions and records access in an append-only audit log. The core of JanuaPort is
proprietary software of JanuaPort GmbH and is not part of this repository. This repository is one of the
open edges around it.

- **License:** Apache License 2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE))
- **Links:** [januaport.ai](https://januaport.ai) · [Security policy](SECURITY.md) · [Contributing](CONTRIBUTING.md)
- **Language:** The guides in the subfolders are currently written in German.

No customer data, no keys, no operator values in this repository.

---

## Environments

Every guide follows the same structure: prerequisites · steps · checks · update · security defaults.

Status labels: **Built** · **In progress** · **Planned**. Each entry says what exactly has been verified.

| Environment | Status | Guide |
|---|---|---|
| Docker Compose (generic, self-hosting) | **Built.** Operated by JanuaPort GmbH (showcase pattern). | [`compose/`](compose/) |
| Hetzner Cloud (Terraform) | **Built.** Operated by JanuaPort GmbH (showcase pattern). | [`hetzner/`](hetzner/) |
| Microsoft Azure | **Built, untested.** Community template. | [`azure/`](azure/) |
| Amazon Web Services (AWS) | **Built, untested.** Community template. | [`aws/`](aws/) |
| JanuaPort Box | **Planned.** Will come from `JanuaPort/januaport-plugins`. | [`box/`](box/) |

"Operated by JanuaPort GmbH (showcase pattern)" means: the same basic setup runs productively on our own
showcase. The template here is derived from it, without our concrete operator values (domain, tailnet
name, account, tokens, IP addresses). "Community template, untested" means: a minimal, plausible
starting point that we do not operate ourselves and have not tried out. Corrections are welcome as
contributions ([`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Relationship to the product

JanuaPort itself stays self-hosted and runs without any activation by us. This repository only provides
the deployment layer (Compose templates, infrastructure automation). Everything **after** "the container
is running" (first access, master key, admin password, first admin token, teams, SSO, integrations) is
described in the setup guide of the product (`docs/inbetriebnahme.md`, product documentation, not
public). Every guide here points there at the right step.
