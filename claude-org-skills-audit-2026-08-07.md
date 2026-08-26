# Claude Org Skill Library — Audit & Disposition
**Date:** 2026-08-07 · **Org:** Bookmarked (Team plan) · **Library size:** 21 org skills
**Decision status:** AUDIT ONLY — nothing deleted. Dispositions below are recommendations for Steve.
**Backups:** Feb-2026 originals preserved in G-Brain as Drive-ingested pages (`drive/bookmarked-api/f-*`, title `SKILL.md`) + Google Drive folder. Console export of `sales-executive-strategy` at `claude-org-skills-backup-2026-08-07/`.

---

## 1. The diagnosis

All 21 skills were added **Feb 2026** and **none has been updated since**. In that time G-Brain matured into the retrieval layer, Confluence became the contract layer, the brand canon was rewritten to v4.0.0, and the CEO Foundation Document was marked stale. The library did not move.

**Nothing in the working setup references any of them.** Grepped global `CLAUDE.md`, all 19 local `~/.claude/skills/`, and the memory routing index: zero references. They fire only by accidental description-match — which is worse than not existing, because the match is silent and the content is wrong.

### The governing principle for the rebuild

> **Skills carry METHOD. G-Brain and Confluence carry FACTS.**

Every skill with facts baked inline is a staleness bomb. The failures below are all the same failure.

---

## 2. Verified drift (evidence, not inference)

| # | Finding | Evidence |
|---|---|---|
| D1 | **`company-context` routes to a page you fenced off.** It loads Confluence **58851341** (CEO Foundation Document) as "canonical source of truth." | That page was marked **"OPERATIONALLY STALE — RECONCILE BEFORE USE"** on **2026-08-03**, with the rule *"do not cite this page for current cash, runway, roster, partner stage, board authority, or sprint priorities."* Successor: **BSH-2026 — Strategic Home Sprint (187760767)**. |
| D2 | **`company-context` contains a banned phrase.** Its Framework 2 states *"Manual review costs $135 per book."* | Brand canon (Confluence **174981121**, CEO-locked) lists **"$135 per book"** under **Never say**. |
| D3 | **`company-context` makes banned multi-state claims.** *"26 states passed legislation"* / *"Texas model ports to 26 states."* | Canon: **Never say** — *"multi-state claims (Texas-only branding)."* |
| D4 | **Brand skills carry the retired palette + font.** `bookmarked-brand-standards` and `brand-messaging-intelligence` predate v4.0.0. | Canon: current palette is `#15B79E / #0E766A / #44C5B1 / #111928 / #F9FAFB / #FF692E`. **`#12A38C`, `#107569`, `#0D5A52`, `#101828`, `#2563EB` are retired — "flag on sight."** **"Urbanist is retired"** — system font stack now. |
| D5 | **Three competing brand authorities.** `bookmarked-brand-standards` calls itself "authoritative source"; `brand-messaging-intelligence` calls itself "the upstream source." | Canon is neither. It is Confluence 174981121, CEO-locked, *"only Steve changes this page."* |
| D6 | **`context-memory` collides with G-Brain.** Self-describes as *"Bookmarked's second brain… stores in organized Confluence pages,"* owns `/capture` and `/context`. | G-Brain is the brain now. Also collides with local `where-was-i` and the transcript-sync pipeline. Whichever loads first wins, silently. |
| D7 | **Expired goal frame.** `sales-executive-strategy` grounds on *"$2.5M by August 2026"* — expiring this month — and `cro-strategy` hard-codes the $60M/Dec-2027 frame. | Live milestone dates belong in the operating sprint, not in a skill body. |
| D8 | **Duplicate authority pairs.** `strategic-advisor` ↔ `bookmarked-strategy-rev2` (both "the first filter"); `jira-operating-model` ↔ `jira-ticket-standards` (create vs. QA the same object). | Both pairs trigger on overlapping language. |
| D9 | **Audience mismatch.** 21 C-suite skills for a 5-person org where 3 of 5 members are ops/finance/CS. | Every skill body is written in second-person-to-Steve voice ("when Steve is talking to a superintendent…"). |

**Parallel context:** G-Brain page `ops/2026-08-07-system-optimization-session` records a skills cleanup that ran **today** — 113 active / 47 archived, curator enabled, 5 trigger-overlap clusters fixed. That was the **Hermes agent fleet**. This claude.ai org library was untouched by it. Same disease, different surface.

---

## 3. Disposition — per skill

### DELETE (10) — superseded, duplicated, or actively wrong

| Skill | Rationale |
|---|---|
| `context-memory` | D6. G-Brain owns this role. Direct `/capture` `/context` collision. |
| `company-context` | D1 + D2 + D3. Routes to a stale page and carries two banned phrases. Replace with a thin router, not a repair. |
| `bookmarked-brand-standards` | D4 + D5. Retired palette and font; falsely claims authority. |
| `brand-messaging-intelligence` | D4 + D5. Third competing brand authority. |
| `bookmarked-strategy-rev2` | D8. Frameworks (Dunford / Balfour / Skok) are generic and already in-model. |
| `strategic-advisor` | D8. Steve-only priority filter; duplicate of the above. |
| `context-handoff` | Obsoleted by G-Brain, Projects, and current context windows. |
| `jira-ticket-standards` | D8. Merge the quality gate into `jira-operating-model`. |
| `market-research-analyst` | Research is a web-search + G-Brain job now. Its TX figures are 6 months stale. |
| `chief-strategy-implementer` | Steve-only operating-cadence skill. Not team-facing. |

### DEMOTE to Steve's personal skills (5) — useful to one person, clutter for four

`cro-strategy` · `chief-financial-officer` · `chief-product-officer` · `skill-factory` · `marketing-coordinator`

These are CEO-shaped. Keeping them org-published means four people carry their metadata in every conversation for zero benefit.

### KEEP + REPOINT (6) — durable method, real users

| Skill | Who uses it | What the rewrite changes |
|---|---|---|
| `compliance-advisor` | Sales, CS, Steve | Keep the conversational framework. Facts already read from Confluence **62652425** — preserve that; strip inline statute detail. |
| `chief-hubspot-officer` | Patrick, ops | **Highest-value skill in the library.** The Renewed-stage quirk (`1008389048`), pipeline IDs, and the `hs_arr`/`hs_mrr` unreliability warning are load-bearing and correct. Keep verbatim; add a G-Brain pointer. |
| `qbo-bookkeeper` | Michelle | Keep. Remove routing to `chief-financial-officer` (demoted). |
| `jira-operating-model` | Eng, product | Absorb `jira-ticket-standards` as a quality-gate section. |
| `collateral-creator` | Marketing, sales | Repoint every brand reference to Confluence **174981121**. Delete inline color/font values. |
| `sales-executive-strategy` | Sales, Steve | Keep Challenger/Dunford method. Strip the expired goal frame (D7) and the `company-context` dependency. |

**Net: 21 → 6 org skills.**

---

## 4. Recommended rewrite pattern

Every kept skill gets this header block, replacing all inline facts:

```
## SOURCES OF TRUTH — read before answering
- Company/product facts, people, history  → G-Brain (`Bookmarked GBrain` connector)
- Brand, voice, palette, say/never-say     → Confluence 174981121 (CEO-locked)
- Current operating state, cash, roster    → Confluence 187760767 (BSH-2026)
- Regulatory/statute detail                → Confluence 62652425
Do NOT answer from memory baked into this file. If a fact is not in a source
above, say so and name the gap. This skill carries method, not facts.
```

---

## 5. Two adjacent issues found while auditing

1. **The org `Bookmarked GBrain` connector points at `https://mcp.bookmarked-staging.net/mcp`** — a *staging* host — and exposes **95 tools** with no permission ceiling set. If the team is meant to rely on G-Brain as the fact layer, it should not be pointed at staging, and 95 unrestricted tools is a large token and blast-radius surface.
2. **The Google MCP bridge token is broken** — `invalid_scope: Bad Request` against `~/.hermes/google_token.json`, bridge restart required. Drive/Gmail/Tasks tooling is down until it's re-authed.

---

## 6. What happens next

- **This document is decision input.** No skill has been deleted.
- The 6 keepers have been rewritten to the pattern above and are staged for upload.
- On your go-ahead, the 10 deletions and 5 demotions take about 15 minutes in the console.
