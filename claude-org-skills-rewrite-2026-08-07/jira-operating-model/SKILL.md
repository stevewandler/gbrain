---
name: jira-operating-model
description: Converts requirements, ideas, or raw requests into properly structured JIRA work, and enforces the quality gate before anything reaches engineering. Activates when creating Epics, Stories, or Tasks, breaking down a spec into executable tickets, reviewing or validating existing tickets, discussing what engineering should work on next, or when someone says "create a ticket," "add this to JIRA," "break this down," or references the BOOK project. Forces structure through clarifying questions and blocks incomplete tickets.
---

# JIRA Operating Model

## SOURCES OF TRUTH — read before writing a ticket

| Need | Go to |
|---|---|
| Product context, prior decisions, why something exists | G-Brain (`Bookmarked GBrain` connector) |
| Live ticket, sprint, and board state | Atlassian connector |
| Current priorities and sequencing | Confluence **187760767** — BSH-2026 Strategic Home Sprint |

**Do not invent product behavior.** If a requirement is ambiguous, ask — do not resolve it by writing a plausible acceptance criterion. This skill carries method, not product decisions.

## WHY THIS SKILL EXISTS

Tickets arrive as ideas, not requirements. This skill compensates for missing spec discipline by forcing structure at intake — and by refusing to pass work forward that engineering cannot act on. Both halves matter: creating well and blocking badly-formed work are the same job.

---

## PART 1 — INTAKE

### The clarifying questions (ask before writing, not after)

1. **Who is this for, and what can they not do today?**
2. **What does "done" look like from the user's side?** — behavior, not implementation.
3. **What is explicitly out of scope?** — the single most-skipped question, and the most common source of rework.
4. **What breaks if we ship this wrong?**
5. **Is this one ticket or several?** If the answer to #2 has an "and," it is several.

If you cannot answer 1, 2, and 3 from what you were given, **stop and ask.** Writing the ticket anyway just moves the ambiguity downstream where it costs more.

### Structure

| Level | Use when |
|---|---|
| **Epic** | A body of work spanning multiple sprints with a shared user outcome |
| **Story** | A single user-visible change, deliverable in one sprint |
| **Task** | Work with no direct user-visible outcome (migration, infra, spike) |

Write the Story title as the user outcome, not the implementation. "Librarian can filter the review queue by status" — not "Add status dropdown to queue component."

---

## PART 2 — THE QUALITY GATE

Run this before any ticket reaches engineering. **Any unchecked box blocks the ticket.**

- [ ] Title states a user outcome, not a solution
- [ ] Description says what problem this solves and for whom
- [ ] Acceptance criteria are testable — someone can determine pass/fail without asking the author
- [ ] Out-of-scope is stated explicitly
- [ ] Dependencies named, or explicitly "none"
- [ ] No unresolved "TBD," "we think," or "something like"
- [ ] Sized, or flagged as needing a spike first
- [ ] If it touches district or student-adjacent data, the privacy implication is named

### How to block

Return the ticket with the specific failing items and a concrete rewrite suggestion for each. Do not return a generic "needs more detail" — that produces a second bad ticket.

If work is genuinely urgent and underspecified, say so plainly and write it as a **spike** with a timebox and a question to answer. That is the honest form of "we don't know yet."

## WHAT THIS SKILL DOES NOT DO

- Decide priority or sequencing.
- Estimate on engineering's behalf.
- Transition tickets through workflow states without being asked.
