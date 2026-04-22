---
name: agent-kanban
description: Verbindet den Agenten mit Agent Kanban (https://agent-kanban.io) per REST-API und Bearer-Token. Nutze diese Skill, wenn Board-Tickets, Nudges, Ready-Queue, Claim/Review, Kommentare oder Polling-Workflows zu Agent Kanban anstehen; API-Key aus Umgebung AGENT_KANBAN_API_KEY.
---

# Agent Kanban (Cursor Skill)

## Authentifizierung

- **Base URL (Standard):** `https://agent-kanban.io` — optional überschreiben mit `KANBAN_API_URL`, falls anders.
- **API-Key:** Umgebungsvariable `AGENT_KANBAN_API_KEY` (Projekt-Convention). Laut Doku heißt die Variable oft `KANBAN_API_KEY` — beide akzeptieren, bevorzugt `AGENT_KANBAN_API_KEY` falls gesetzt.
- **Header:** `Authorization: Bearer <api_key>`

Niemals den Key in Chat, Commits oder Logs ausgeben. Bei 429: `retry-after` beachten, Pausen/Backoff, nicht spammen.

## Nur „für mich“ gedachte Aufgaben

- **Nudges** zuerst: betroffene Tickets bearbeiten, bevor neue Ready-Arbeit gegriffen wird.
- **Ready-Tickets** nur annehmen, wenn sie klar zulässig sind:
  - `assignee` leer: Ticket darf geclaimt werden (eigener Agent-Name wie in der Agent-Konfiguration in Agent Kanban).
  - `assignee` gesetzt: nur bearbeiten, wenn der Name exakt eurer registrierte Agent-Name in diesem Projekt ist (Referenz: `GET /api/projects/:slug/members` — gültige Namen inkl. Agenten).
- Keine fremden Tickets mitnehmen, keine Masse an parallel offenen In-Progress-Tickets erzeugen, wenn euer Prozess „ein Ticket“ vorsieht.

## Pflicht-Workflow (Schleife)

1. **Nudges:** `GET /api/nudges` — v. a. `unanswered_comment` zuerst beantworten (Kommentar), ggf. `POST /api/nudges/:ticketId/dismiss` nach Erledigung.
2. **Ready:** `GET /api/projects/:projectSlug/tickets/ready` (nur zulässige Tickets siehe oben).
3. **Claim:** `PATCH /api/projects/:slug/tickets/:number` mit `status: "in_progress"` und `assignee: "<euer-agent-name>"` (nur Name aus Members).
4. **Fortschritt:** während der Arbeit `POST /api/.../comments` mit sinnvollen Updates; optional `author` = Agent-Name.
5. **Review:** Wenn fertig, `PATCH` mit `status: "in_review"`.
6. **Warten:** Kein neues „Ready“ claimen, solange euer Ticket noch auf Review/Feedback wartet (Owner-Kommentare → wieder bei 1. einordnen, nicht parallel neu ziehen, wenn das euer Ablauf ist).
7. **Pause vor nächstem Zyklus:** **15 Sekunden** warten, dann wieder bei 1. (bei 429 länger warten).

> Hinweis: Viele Cursor-Sitzungen sind **kurz**; ein Endlos-Daemon in einer Session ist unüblich. Wenn **ein externes Skript** die Schleife fährt, gelten 15s + Respekt vor Rate-Limit (100 req/min pro IP laut Doku).

## Wichtigste Endpunkte (Kurz)

| Zweck | Methode & Pfad |
|-------|----------------|
| Nudges | `GET /api/nudges` |
| Nudge entfernen | `POST /api/nudges/:ticketId/dismiss` |
| Ready | `GET /api/projects/:slug/tickets/ready` |
| Ticket+Historie | `GET /api/projects/:slug/tickets/:number` |
| Ticket ändern (Claim, Review) | `PATCH /api/projects/:slug/tickets/:number` |
| Kommentar | `POST /api/projects/:slug/tickets/:number/comments` |
| Gültige Namen | `GET /api/projects/:slug/members` |
| Projekte listen | `GET /api/projects` |

Vollständige Spezifikation: [API Reference](https://agent-kanban.io/docs/api-reference), [Agent Integration](https://agent-kanban.io/docs/agent-integration), interaktiv: `https://agent-kanban.io/api/docs`

## Externe Alternativen (optional)

- **MCP:** [MCP Integration](https://agent-kanban.io/docs/mcp-integration) (falls eingerichtet) kann HTTP-curl ersetzen.
- **Claude Code /kanban-Befehl:** laut Doku; in Cursor ggf. irrelevant.

## Prüfliste pro Lauf

- [ ] Nudges abgearbeitet, bevor Ready gewählt wurde
- [ ] Nur berechtigte Ready-Tickets, Assignee-Regel eingehalten
- [ ] Claim → Arbeitskommentare → `in_review`
- [ ] Review-Phase beachtet, bevor neuer Zyklus
- [ ] 15s Pause; bei 429 Backoff
- [ ] API-Key nicht exponiert
