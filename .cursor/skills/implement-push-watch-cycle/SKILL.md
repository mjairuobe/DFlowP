---
name: implement-push-watch-cycle
description: >-
  Führt eine enge Schleife aus: Jenkins-Build-Logs (oder anderes Ziel) auswerten,
  minimal fixen, committen, pushen, erneut bauen/beobachten, bis das Ziel grün ist.
  Nutzen, wenn CI/Jenkins nach Codeänderungen grün werden soll oder der Nutzer
  „implement, push, watch, repeat“ / Grinding / „until pass“ für Pipeline-Builds verlangt.
---

# Implement → Push → Watch Cycle (Grinding)

Kombiniert das Muster **Grind until pass** (fix → verifizieren → wiederholen) mit **externer CI**: typischerweise Jenkins-Konsole, optional lokaler Check davor.

## Zieldefinition

1. **Erfolgskriterium** explizit setzen, z. B.:
   - Jenkins-Job `DFlowP-stack` (Multibranch-Branch) endet mit `result: SUCCESS`, oder
   - lokaler Befehl zuerst (`pytest`, `npm test`, …), dann Jenkins.
2. **Nicht** mehrere unabhängige Ziele in einer Schleife vermischen.

## Schleife (pro Iteration)

1. **Logs / Status holen**  
   - Letzter Build: `lastBuild` bzw. `lastCompletedBuild` per API oder Konsole (`consoleText` Ende lesen).  
   - Ersten konkreten Fehler identifizieren (Root Cause), nicht raten.

2. **Minimal fixen**  
   - Nur das Nötige am Code/Konfiguration; kein Refactoring „nebenbei“.  
   - Keine Secrets aus Logs in Commits oder Antworten übernehmen.

3. **Commit & Push**  
   - Sinnvolle Commit-Message; Branch-Workflow des Repos beachten (kein direkter Commit auf `main`, sofern Regeln das vorgeben).

4. **Watch**  
   - Build triggern (Webhook nach Push oder `build`-POST mit Crumb) und **pollen**, bis `building: false`.  
   - Bei langen Läufen Intervall 40–60 s, Timeout sinnvoll setzen.

5. **Entscheidung**  
   - Ziel erreicht → stoppen, kurz berichten (Was war kaputt, was wurde geändert, wie viele Iterationen).  
   - Noch rot → mit Schritt 1 weitermachen.

## Grenzen („Grinding“-Regeln)

- **Maximal 10 Iterationen.** Danach stoppen, Blocker und letzte Log-Ausschnitte schildern; menschliche Entscheidung einholen.
- **Pro Iteration idealerweise eine Ursache** beheben; wenn ein Fix mehrere Fehler beseitigt, ist das ok.
- **Tests nicht löschen**, um grün zu werden; Fehler im Produktionscode oder in der Pipeline beheben.
- **Fehler nicht wegdiskutieren** (`@ts-ignore`, blindes `|| true`), außer der Nutzer will bewusst nur Diagnose.

## Jenkins (DFlowP, Orientierung)

- Multibranch-URL enthält oft `job/<Projekt>/job/<branch-encoded>/`.  
- API-Aufrufe: ggf. `-g` bei `curl` (keine Globbing-Probleme mit `[…]` in URLs), bei Basic-Auth **keine** Tokens in Chat/Logs zitieren.  
- Häufige Stolperer: Redirects, `lastSuccessfulBuild` fehlt (404), leeres Pipeline-`changeSet` (dafür `changeSets` / `BuildData` nutzen, falls Gate-Code betroffen).

## Wenn kein Jenkins erreichbar ist

- Lokalen **Surrogat-Befehl** definieren (z. B. `docker compose …` / Tests), bis Netz/Credentials da sind; dann Watch auf Jenkins nachziehen.

## Kurz-Checkliste

```text
[ ] Zielbefehl / Job eindeutig
[ ] Log gelesen, Ursache benannt
[ ] Minimaler Fix
[ ] Commit + Push
[ ] Neuer Build beobachtet
[ ] Iterationszähler ≤ 10
```
