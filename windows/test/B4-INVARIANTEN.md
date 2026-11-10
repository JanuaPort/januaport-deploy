# B4 F2/F3/N2/N3: Invarianten-Audit (#1246)

Repo-weite Suche nach dem Auftragstext und den weiteren Adaptern/Kompositionsstellen.
Die folgende Liste nennt alle Treffer als Datei:Zeile, ohne vorhandene Inhalte
oder Secret-Beispiele aus anderen Profilen zu duplizieren. Diese Auditdatei
selbst ist aus der Suche ausgenommen und wird nicht ausgeliefert.

Suchmuster:

```text
Sperren bei Anmeldung|LockWorkStation|Autologon|settings\.json|Fingerprint|Master-Key|master key|master_key|rundll32|AtLogOn|WTSSessionInfoEx|WTS_SESSIONSTATE_LOCK|settings-store\.json|AutoAdminLogon|DefaultUserName|tls-leaf|jnpt-data:/data|\$ProfileFiles|PROFILE_FILES
```

Geprüfte Verbindungen:

- Anmeldung: `Register-DienstTasks` baut Trigger und festen PowerShell-Aufruf;
  `jnpt-sperren.ps1` wartet auf die eigene Sitzung und prüft WTS nach jedem Aufruf.
  Der separate Bildschirmschoner bleibt bei 60 Sekunden. B-7 schützt denselben Pfad.
- Autologon: nativer Aufruf in `Enable-DienstAutologon`, Prüfung durch
  `Test-DienstAutologon`; nach Neueinrichtung/Reset 21 Prüfungen mit 20 Pausen
  zu je 500 ms, unveränderter Bestandskonto-Pfad ohne Kennwortreset.
- Docker-Einstellungen: settings-store.json, dann settings.json; beide fehlend
  ergibt die feste Meldung. Vorhandene Einstellungen werden weiterhin gelesen.
- Verteilung: `$ProfileFiles` speist Download, Staging, Upgrade und lokale
  Diensteinrichtung. Die Python-Liste `PROFILE_FILES` speist die Upgrade-Tests,
  Summenprüfungen, Live-Fixtures und Mutationskopien. `jnpt-sperren.ps1` ist
  in beiden Listen und im Manifest enthalten; die drei Legacy-Dateien bleiben
  der unveränderte Erkennungsanker für windows-v0.1.0.
- TLS: Compose mountet `tls-leaf` für Initialisierung und Caddy. Derselbe
  Engine-Bestand behält sein Zertifikat; beim Kontowechsel entsteht ein neues.
  Beide READMEs, Runbook und B4-Schritt 2a verlangen erneutes Koppeln.
- Key: Compose mountet `jnpt-data:/data`. Ein Dateiname oder
  `JNPT_MASTER_KEY_FILE` ist dort nicht definiert. Die genaue N4-Befehlsfolge
  benötigt deshalb die Pfadangabe der eingesetzten Kern-Version.
- Treffer außerhalb von windows gehören zu eigenständigen Deployment-Profilen
  oder allgemeinen Verweisen; sie enthalten keinen zweiten Windows-Aufgaben-
  oder Verteilungsweg und bleiben gemäß Scope unverändert.

Negativproben: zwölf erfolglose Sperrversuche, nur fremder Explorer,
WTS UNLOCK/UNKNOWN/kurze/falsche/fehlgeschlagene Antwort, native Ausnahme,
ausbleibende Winlogon-Werte und fehlende JSON-Dateien. Der echte PS-5.1-Ablauf
und der echte C#-WTS-Decoder laufen mit ausschließlich ersetzten Systemgrenzen.
Zehn isolierte Mutationen müssen Assertion-Fehler ergeben, einschließlich
versuchter Abmelde-/Herunterfahradapter und unerlaubter Fehlerausgabe.
Die Originalbytes werden nach jeder Mutation verglichen.

## Treffer

- `README.md`: `README.md:45`
- `aws/cloud-init.yaml`: `aws/cloud-init.yaml:40`, `aws/cloud-init.yaml:42`, `aws/cloud-init.yaml:55`
- `azure/cloud-init.yaml`: `azure/cloud-init.yaml:40`, `azure/cloud-init.yaml:42`, `azure/cloud-init.yaml:55`
- `compose/.env.example`: `compose/.env.example:26`
- `compose/docker-compose.yml`: `compose/docker-compose.yml:31`, `compose/docker-compose.yml:32`, `compose/docker-compose.yml:34`, `compose/docker-compose.yml:62`, `compose/docker-compose.yml:64`
- `hetzner/README.md`: `hetzner/README.md:45`, `hetzner/README.md:83`
- `hetzner/cloud-init.yaml.tftpl`: `hetzner/cloud-init.yaml.tftpl:87`, `hetzner/cloud-init.yaml.tftpl:88`, `hetzner/cloud-init.yaml.tftpl:91`, `hetzner/cloud-init.yaml.tftpl:190`, `hetzner/cloud-init.yaml.tftpl:191`, `hetzner/cloud-init.yaml.tftpl:198`
- `hetzner/main.tf`: `hetzner/main.tf:108`
- `hetzner/terraform.tfvars.example`: `hetzner/terraform.tfvars.example:16`, `hetzner/terraform.tfvars.example:18`
- `hetzner/variables.tf`: `hetzner/variables.tf:27`, `hetzner/variables.tf:29`, `hetzner/variables.tf:31`, `hetzner/variables.tf:38`, `hetzner/variables.tf:39`, `hetzner/variables.tf:117`, `hetzner/variables.tf:219`
- `windows/PRUEFSTEIN-B4.md`: `windows/PRUEFSTEIN-B4.md:56`, `windows/PRUEFSTEIN-B4.md:58`, `windows/PRUEFSTEIN-B4.md:63`, `windows/PRUEFSTEIN-B4.md:68`, `windows/PRUEFSTEIN-B4.md:76`
- `windows/README.en.md`: `windows/README.en.md:44`, `windows/README.en.md:45`, `windows/README.en.md:48`, `windows/README.en.md:52`, `windows/README.en.md:94`, `windows/README.en.md:98`, `windows/README.en.md:102`, `windows/README.en.md:103`, `windows/README.en.md:105`, `windows/README.en.md:122`, `windows/README.en.md:123`, `windows/README.en.md:125`, `windows/README.en.md:127`, `windows/README.en.md:132`, `windows/README.en.md:133`, `windows/README.en.md:139`, `windows/README.en.md:142`, `windows/README.en.md:144`, `windows/README.en.md:161`, `windows/README.en.md:165`, `windows/README.en.md:169`, `windows/README.en.md:183`, `windows/README.en.md:222`, `windows/README.en.md:223`, `windows/README.en.md:311`, `windows/README.en.md:316`, `windows/README.en.md:325`, `windows/README.en.md:329`, `windows/README.en.md:341`, `windows/README.en.md:406`, `windows/README.en.md:413`, `windows/README.en.md:416`, `windows/README.en.md:426`
- `windows/README.md`: `windows/README.md:59`, `windows/README.md:65`, `windows/README.md:115`, `windows/README.md:119`, `windows/README.md:123`, `windows/README.md:125`, `windows/README.md:127`, `windows/README.md:147`, `windows/README.md:148`, `windows/README.md:150`, `windows/README.md:153`, `windows/README.md:157`, `windows/README.md:158`, `windows/README.md:164`, `windows/README.md:168`, `windows/README.md:169`, `windows/README.md:190`, `windows/README.md:194`, `windows/README.md:199`, `windows/README.md:214`, `windows/README.md:257`, `windows/README.md:258`, `windows/README.md:350`, `windows/README.md:355`, `windows/README.md:361`, `windows/README.md:365`, `windows/README.md:370`, `windows/README.md:383`, `windows/README.md:455`, `windows/README.md:463`, `windows/README.md:468`, `windows/README.md:478`
- `windows/RUNBOOK.md`: `windows/RUNBOOK.md:54`, `windows/RUNBOOK.md:74`, `windows/RUNBOOK.md:80`, `windows/RUNBOOK.md:88`, `windows/RUNBOOK.md:110`, `windows/RUNBOOK.md:118`, `windows/RUNBOOK.md:119`, `windows/RUNBOOK.md:120`, `windows/RUNBOOK.md:124`, `windows/RUNBOOK.md:142`, `windows/RUNBOOK.md:149`, `windows/RUNBOOK.md:174`
- `windows/SHA256SUMS`: `windows/SHA256SUMS:12`
- `windows/dienst-einrichten.ps1`: `windows/dienst-einrichten.ps1:108`, `windows/dienst-einrichten.ps1:110`, `windows/dienst-einrichten.ps1:125`, `windows/dienst-einrichten.ps1:128`, `windows/dienst-einrichten.ps1:129`, `windows/dienst-einrichten.ps1:131`, `windows/dienst-einrichten.ps1:135`, `windows/dienst-einrichten.ps1:136`, `windows/dienst-einrichten.ps1:138`, `windows/dienst-einrichten.ps1:140`, `windows/dienst-einrichten.ps1:144`, `windows/dienst-einrichten.ps1:146`, `windows/dienst-einrichten.ps1:157`, `windows/dienst-einrichten.ps1:159`, `windows/dienst-einrichten.ps1:160`, `windows/dienst-einrichten.ps1:164`, `windows/dienst-einrichten.ps1:178`, `windows/dienst-einrichten.ps1:179`, `windows/dienst-einrichten.ps1:185`, `windows/dienst-einrichten.ps1:187`, `windows/dienst-einrichten.ps1:188`, `windows/dienst-einrichten.ps1:197`, `windows/dienst-einrichten.ps1:201`, `windows/dienst-einrichten.ps1:224`, `windows/dienst-einrichten.ps1:249`, `windows/dienst-einrichten.ps1:270`, `windows/dienst-einrichten.ps1:271`
- `windows/docker-compose.yml`: `windows/docker-compose.yml:45`, `windows/docker-compose.yml:62`, `windows/docker-compose.yml:102`, `windows/docker-compose.yml:206`
- `windows/einrichten.ps1`: `windows/einrichten.ps1:15`, `windows/einrichten.ps1:30`, `windows/einrichten.ps1:38`, `windows/einrichten.ps1:83`, `windows/einrichten.ps1:86`, `windows/einrichten.ps1:87`, `windows/einrichten.ps1:88`, `windows/einrichten.ps1:93`, `windows/einrichten.ps1:150`, `windows/einrichten.ps1:167`, `windows/einrichten.ps1:177`, `windows/einrichten.ps1:205`, `windows/einrichten.ps1:219`, `windows/einrichten.ps1:226`, `windows/einrichten.ps1:227`, `windows/einrichten.ps1:228`
- `windows/jnpt-backup.ps1`: `windows/jnpt-backup.ps1:66`
- `windows/jnpt-sperren.ps1`: `windows/jnpt-sperren.ps1:17`, `windows/jnpt-sperren.ps1:24`, `windows/jnpt-sperren.ps1:28`, `windows/jnpt-sperren.ps1:30`, `windows/jnpt-sperren.ps1:35`, `windows/jnpt-sperren.ps1:41`, `windows/jnpt-sperren.ps1:64`
- `windows/test/README.md`: `windows/test/README.md:17`, `windows/test/README.md:56`, `windows/test/README.md:96`, `windows/test/README.md:108`, `windows/test/README.md:116`, `windows/test/README.md:158`, `windows/test/README.md:161`
- `windows/test/b4_mutations.py`: `windows/test/b4_mutations.py:15`, `windows/test/b4_mutations.py:17`, `windows/test/b4_mutations.py:27`
- `windows/test/dienst_fakes.ps1`: `windows/test/dienst_fakes.ps1:6`, `windows/test/dienst_fakes.ps1:27`, `windows/test/dienst_fakes.ps1:28`, `windows/test/dienst_fakes.ps1:29`, `windows/test/dienst_fakes.ps1:31`
- `windows/test/dienst_mutations.py`: `windows/test/dienst_mutations.py:3`, `windows/test/dienst_mutations.py:22`, `windows/test/dienst_mutations.py:26`, `windows/test/dienst_mutations.py:45`, `windows/test/dienst_mutations.py:48`, `windows/test/dienst_mutations.py:49`, `windows/test/dienst_mutations.py:50`, `windows/test/dienst_mutations.py:51`, `windows/test/dienst_mutations.py:55`, `windows/test/dienst_mutations.py:56`, `windows/test/dienst_mutations.py:57`, `windows/test/dienst_mutations.py:58`, `windows/test/dienst_mutations.py:60`, `windows/test/dienst_mutations.py:71`, `windows/test/dienst_mutations.py:112`
- `windows/test/live.py`: `windows/test/live.py:16`, `windows/test/live.py:20`, `windows/test/live.py:26`, `windows/test/live.py:97`, `windows/test/live.py:98`, `windows/test/live.py:99`, `windows/test/live.py:132`
- `windows/test/mutations.py`: `windows/test/mutations.py:14`, `windows/test/mutations.py:26`, `windows/test/mutations.py:40`
- `windows/test/test_b4.py`: `windows/test/test_b4.py:22`, `windows/test/test_b4.py:126`, `windows/test/test_b4.py:160`, `windows/test/test_b4.py:162`, `windows/test/test_b4.py:172`, `windows/test/test_b4.py:173`, `windows/test/test_b4.py:176`, `windows/test/test_b4.py:186`, `windows/test/test_b4.py:187`, `windows/test/test_b4.py:192`, `windows/test/test_b4.py:193`, `windows/test/test_b4.py:210`
- `windows/test/test_install.py`: `windows/test/test_install.py:12`, `windows/test/test_install.py:30`, `windows/test/test_install.py:48`, `windows/test/test_install.py:53`, `windows/test/test_install.py:109`, `windows/test/test_install.py:125`, `windows/test/test_install.py:152`, `windows/test/test_install.py:159`, `windows/test/test_install.py:167`, `windows/test/test_install.py:184`, `windows/test/test_install.py:193`, `windows/test/test_install.py:195`, `windows/test/test_install.py:198`, `windows/test/test_install.py:243`, `windows/test/test_install.py:248`, `windows/test/test_install.py:255`, `windows/test/test_install.py:257`, `windows/test/test_install.py:261`, `windows/test/test_install.py:268`, `windows/test/test_install.py:269`, `windows/test/test_install.py:270`, `windows/test/test_install.py:281`, `windows/test/test_install.py:288`, `windows/test/test_install.py:294`, `windows/test/test_install.py:317`, `windows/test/test_install.py:325`, `windows/test/test_install.py:326`
- `windows/test/test_profile.py`: `windows/test/test_profile.py:35`, `windows/test/test_profile.py:38`, `windows/test/test_profile.py:59`, `windows/test/test_profile.py:66`, `windows/test/test_profile.py:67`, `windows/test/test_profile.py:68`, `windows/test/test_profile.py:318`, `windows/test/test_profile.py:320`, `windows/test/test_profile.py:321`, `windows/test/test_profile.py:323`, `windows/test/test_profile.py:336`, `windows/test/test_profile.py:338`
- `windows/test/test_upgrade.py`: `windows/test/test_upgrade.py:9`, `windows/test/test_upgrade.py:44`, `windows/test/test_upgrade.py:45`, `windows/test/test_upgrade.py:103`, `windows/test/test_upgrade.py:105`
