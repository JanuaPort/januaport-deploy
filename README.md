# januaport-deploy

Deploy-Vorlagen und Anleitungen je Umgebung fuer JanuaPort: Compose, Hetzner, Azure, AWS (Apache 2.0)

**Status:** privat bis zum GoLive von JanuaPort (Flip in der GoLive-Checkliste JanuaPort/januaport#788). Teil des Open-Core-Pivots (JanuaPort/januaport#773).

**Lizenz:** Apache License 2.0 (`LICENSE`), Copyright 2026 JanuaPort GmbH (`NOTICE`). Beitraege: `CONTRIBUTING.md`.

**Zustaendig:** Lead (#776) — Ownership je Unterordner; Inhalte kommen mit den genannten Tickets.

Keine Kundendaten, keine Schluessel, keine Betreiberwerte in diesem Repository.

## Umgebungen

Jede Anleitung folgt derselben Gliederung: Voraussetzungen · Schritte ·
Prüfen · Update · Sicherheits-Defaults.

| Umgebung | Status | Anleitung |
|---|---|---|
| Docker Compose (generisch, Selbst-Hoster) | von JanuaPort GmbH betrieben (Showcase-Muster) | [`compose/`](compose/) |
| Hetzner Cloud (Terraform) | von JanuaPort GmbH betrieben (Showcase-Muster) | [`hetzner/`](hetzner/) |
| Microsoft Azure | Community-Vorlage, ungetestet | [`azure/`](azure/) |
| Amazon Web Services (AWS) | Community-Vorlage, ungetestet | [`aws/`](aws/) |
| JanuaPort Box | kommt aus `JanuaPort/januaport-plugins` (#781) | [`box/`](box/) |

„Von JanuaPort GmbH betrieben (Showcase-Muster)" heißt: dieselbe Grundform
läuft produktiv auf unserem eigenen Showcase — die Vorlage hier ist davon
abgeleitet, aber ohne unsere konkreten Betreiberwerte (Domain, Tailnet-Name,
Konto, Tokens, IPs). „Community-Vorlage, ungetestet" heißt: ein minimaler,
plausibler Startpunkt, den wir nicht selbst betreiben und nicht durchprobiert
haben — Korrekturen sind Beiträge (`CONTRIBUTING.md`).

## Verhältnis zum Produkt-Repo

JanuaPort selbst bleibt self-hosted und account-agnostisch; dieses Repo
liefert nur die Deploy-Schicht (Compose-Vorlagen, Infrastruktur-Automatik).
Die Inbetriebnahme **nach** „Container läuft" (Erstzugang, Master-Schlüssel,
Admin-Passwort, erster Admin-Token, Teams, SSO, Integrationen) steht in
`docs/inbetriebnahme.md` im Produkt-Repo `JanuaPort/januaport` — jede
Anleitung hier verweist an der passenden Stelle dorthin.
