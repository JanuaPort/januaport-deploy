# januaport-deploy

[English](README.md) · **Deutsch**

Betrieb für JanuaPort: Vorlagen und Anleitungen, um JanuaPort in einer bestimmten Umgebung zu betreiben.

JanuaPort ist ein self-hosted MCP-Gateway. Es verbindet KI-Assistenten fein berechtigt mit den
bestehenden Systemen eines Unternehmens und protokolliert die Zugriffe in einem append-only Audit-Log. Der
Kern von JanuaPort ist proprietäre Software der JanuaPort GmbH und nicht Teil dieses Repositorys. Dieses
Repository ist einer der offenen Ränder darum herum.

- **Lizenz:** Apache License 2.0 ([`LICENSE`](LICENSE), [`NOTICE`](NOTICE))
- **Links:** [januaport.ai](https://januaport.ai) · [Sicherheitsrichtlinie](SECURITY.md) · [Beiträge](CONTRIBUTING.md)

Keine Kundendaten, keine Schlüssel, keine Betreiberwerte in diesem Repository.

---

## Umgebungen

Jede Anleitung folgt derselben Gliederung: Voraussetzungen · Schritte · Prüfen · Update ·
Sicherheits-Defaults.

Kennzeichnung: **Gebaut** · **Im Bau** · **Geplant**. Jeder Eintrag sagt, was genau belegt ist.

| Umgebung | Stand | Anleitung |
|---|---|---|
| Docker Compose (generisch, Selbst-Hoster) | **Gebaut.** Von der JanuaPort GmbH betrieben (Showcase-Muster). | [`compose/`](compose/) |
| Hetzner Cloud (Terraform) | **Gebaut.** Von der JanuaPort GmbH betrieben (Showcase-Muster). | [`hetzner/`](hetzner/) |
| Microsoft Azure | **Gebaut, ungetestet.** Community-Vorlage. | [`azure/`](azure/) |
| Amazon Web Services (AWS) | **Gebaut, ungetestet.** Community-Vorlage. | [`aws/`](aws/) |
| JanuaPort Box | **Geplant.** Kommt aus `JanuaPort/januaport-plugins`. | [`box/`](box/) |

„Von der JanuaPort GmbH betrieben (Showcase-Muster)“ heißt: Dieselbe Grundform läuft produktiv auf unserem
eigenen Showcase. Die Vorlage hier ist davon abgeleitet, aber ohne unsere konkreten Betreiberwerte
(Domain, Tailnet-Name, Konto, Tokens, IP-Adressen). „Community-Vorlage, ungetestet“ heißt: ein minimaler,
plausibler Startpunkt, den wir nicht selbst betreiben und nicht durchprobiert haben. Korrekturen sind als
Beiträge willkommen ([`CONTRIBUTING.md`](CONTRIBUTING.md)).

## Verhältnis zum Produkt

JanuaPort selbst bleibt self-hosted und läuft ohne Freischaltung durch uns. Dieses Repository liefert nur die
Deploy-Schicht (Compose-Vorlagen, Infrastruktur-Automatik). Alles **nach** „Container läuft“ (Erstzugang,
Master-Schlüssel, Admin-Passwort, erster Admin-Token, Teams, SSO, Integrationen) steht in der
Inbetriebnahme-Anleitung des Produkts (`docs/inbetriebnahme.md`, Produkt-Doku, nicht öffentlich). Jede
Anleitung hier verweist an der passenden Stelle dorthin.
