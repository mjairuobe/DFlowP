---
name: ci-performance-metrik
description: >-
  Analysiert die Laufzeiten von Jenkins-Pipeline-Stages anhand des Build-Logs
  (Timestamps) und liefert pro Stage/Teilaufgabe Zeiten, Engpässe und
  Optimierungsvorschläge. Nutze bei Jenkins-Jobs, Jenkinsfiles, CI-Dauer, Build-
  Performance, „letzter grüner Build“, Log mit Zeitstempeln, oder wenn der Nutzer
  CI-Metriken, Stage-Dauer oder Pipeline-Beschleunigung wünscht.
---

# CI-Performance-Metrik (Jenkins)

## Ziel

Für einen **Jenkins-Job** (bzw. die zugehörige **Pipeline-Definition** / `Jenkinsfile`) die **Dauer** von **Stages** und sinnvollen **Teilaufgaben** aus dem **Konsolenlog** ableiten, den letzten **vollständigen, erfolgreichen** Lauf finden, und **Performance-Probleme** plus **konkrete Verbesserungsideen** nennen.

Gilt **generisch** für beliebige Declarative/Scripted Pipelines, nicht nur ein Projekt.

## Eingrenzung (vor Analyse)

1. **Job identifizieren**  
   `jobName` aus Nutzer-Angabe, Repo-Kontext oder `Jenkinsfile.*` → in Jenkins auffindbarer Name.

2. **Optional:** **Commit / Revision** beachten, wenn der Nutzer einen Branch oder Build-Nummer nennt; sonst die Revision des **zu analysierenden Builds** verwenden.

3. **Jenkinsfile / Stages einlesen (zu dieser Revision)**  
   - Aus dem Build-Artefakt/Checkout (falls zugänglich) oder per **Repository**-Checkout mit der **Revision des Builds** (`git fetch` + `git show <rev>:Jenkinsfile.api` o. ä.).  
   - **Declarative Pipeline:** `stage('…') { … }` notieren, **Reihenfolge** und **Namen**; bei verschachtelten `parallel`-Blöcken Unterteilungen merken.  
   - **Teilaufgaben:** große `sh`-Befehlsserien, `docker build`, `docker compose`, Prüfungen, Push — logisch trennen, wenn im Log sichtbar (eigene Log-Zeilen/Blöcke).  

4. **Welcher Build?** (Standard)  
   - **Nicht** blind `lastSuccessfulBuild` nehmen, wenn „vollständig“ wichtig ist.  
   - Suche: **letzter Build mit `result: SUCCESS`**, der **subjektiv alle relevanten Stages** durchlaufen hat (z. B. **kein** reiner Skip von Image-Builds, wenn der Nutzer genau so einen Full-Build will).  
   - Heuristik: Log durchsehen (oder `get_pipeline_stages` / Blue Ocean API falls verfügbar) auf: „Skipping“, „not built“, „when { … }”-Sprünge, abgebrochene Stages.  
   - Wenn unklar: **verfügbare Builds rückwärts** (SUCCESS) prüfen, bis ein **voller** Lauf klar erkennbar ist; andernfalls den **jüngsten SUCCESS** wählen und im Report **Einschränkungen** schreiben (z. B. „möglicherweise übersprungene Stage“).  
   - Abweichung: Nutzer nennt **Build-Nummer** / „vorletzter Build“ → exakt so verwenden.

## Log holen (mit Timestamps)

- **Erforderlich:** Konsolenausgabe mit **Zeitstempeln** pro Zeile (z. B. **Timestamper-Plugin** oder Jenkins-eigene `timestamps { … }` in der Pipeline).  
- Quellen: **Jenkins MCP** `get_console_log` (Snippet + ggf. voll), **HTTP** `.../job/<name>/<n>/consoleText` (ggf. mit Auth + Crumb), oder **vom Nutzer eingefügtes Log** (dann prüfen, ob Timestamps vorhanden sind; wenn nicht: Limitierung ausweisen, keine Dauer-„Summe“ fälschen).  
- Wenn nötig, **vollständiges Log** für die Analyse nutzen, nicht nur die letzten hundert Zeilen.

## Auswertung

1. **Timestamps parsen**  
   Häufige Formate: `[HH:MM:SS]`, ISO-Zeit, ms-seit-Start. Pro Zeile **Absolute Zeit** oder **Differenzen** bilden.  
2. **Stages im Log finden**  
   Typische Muster: `Stage "Name"`, `— Name —`, `Entering stage`, auffällige Abschnittsüberschriften in der Konsolenausgabe, Plugin-Zeilen. Stages dem **Jenkinsfile** zuordnen.  
3. **Teilaufgaben** (innerhalb einer Stage)  
   - Zeitblöcke zwischen auffälligen Log-Einschnitten: Start/Ende von `+ docker`, `+ npm test`, Wiederholungsschleifen.  
   - Wenn im Log **nicht** trennbar: eine Zeile pro Stage, Teilaufgaben als „(nicht im Log trennbar)“ kennzeichnen.  
4. **Dauern bilden**  
   Pro Stage/Teilaufgabe: **Differenz (Ende − Start)** in Sekunden/Minuten; runden sinnvoll; **Gesamtlauf** optional.

## Ausgabeformat (Vorlage)

Kurzbericht, orientiert an:

```text
[Build] Job: <name> | #<n> | Revision: <sha> | Ergebnis: SUCCESS
[Jenkinsfile] <pfad> (Stages laut Quelle: …)

Stage 1 „<Name>“ (~Xs gesamt):
  - <Teilaufgabe 1>: ~Xs
  - <Teilaufgabe 2>: ~Xs
  …

Stage 2 „<Name>“ …

Anteil am Gesamtbuild (Top 3 Stages / Teilaufgaben):
  …
```

- Zeiten **tatsächlich aus Log** ableiten, keine Plausibilität erfinden.  
- Unsicherheiten: „ca.“, „~“, oder Bereich, wenn Pausen/Sprünge im Log sind.

## Performance-Analyse (Pflichtteil)

- **Auffällig:** Stages/Teilaufgaben mit **hohem Anteil** an der Gesamtzeit, **Wartezeiten** (keine sichtbaren Schritte), **Wiederholungen** (Retry), fehlendes Caching, sequenzielle `docker build` statt paralleler Schritte (wenn Log das nahelegt).  
- **Unnötig / prüfenswert:** doppelte `npm install`/`pip install` ohne Cache, lange leere Pausen, `sleep`, redundante `git fetch`, Push bei unverändertem Image (wenn aus Log/Stage klar), Tests ohne Parallelisierung.  
- **Verbesserungsvorschläge** (konkret, kurz), z. B.:  
  - **Cache:** Docker BuildKit, layer cache, dependencies cache in Jenkins.  
  - **Parallel:** `parallel`-Stages, getrennte Matrix nur wenn sinnvoll.  
  - **Bedingt:** Pipelines, die früh abbrechen, wenn unverändert (bereits in DFlowP-Jenkinsfiles teils vorgesehen — hier nur falls passend).  
  - **Ressourcen:** Agent, Netz, Registry-Latenz — nur ansprechen, wenn Log/Stages das stützen.

## Werkzeuge

- **Jenkins MCP** (wenn angebunden): `get_build_status`, `get_console_log`, ggf. `get_pipeline_stages` falls Plugin vorhanden.  
- **Git:** exakte `Jenkinsfile`-Revision des Builds.  
- **Ohne API:** Nutzer-Log in Chat einfügen lassen, dann trotzdem Stages-Struktur aus Jenkinsfile im Repo (passender Branch/Tag) beziehen.

## Grenzen ehrlich nennen

- Kein Timestamps im Log → **keine** präzisen Dauern, nur qualitatives Ratenzitat.  
- `SUCCESS` trotz übersprungener wichtiger Stages (Log-„Skips“) → im Text flaggen.  
- Sehr lange Logs: auf **kritische Stages** fokussieren, aber im Abschnitt „Methodik“ sagen, ob trunciert.
