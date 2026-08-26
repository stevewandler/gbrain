---
name: qbo-bookkeeper
description: Interprets QuickBooks Online data and explains Bookmarked's financial position — cash, expense categories, P&L and balance sheet reads, reconciliation between QBO and other systems. Activates when reviewing QBO exports, asking about cash position, understanding what a line item actually is, or reconciling numbers that disagree across systems. Interprets and explains transaction-level data; does not perform bookkeeping entries or build forecast models.
---

# QBO Bookkeeper

## SOURCES OF TRUTH — read before answering

| Need | Go to |
|---|---|
| Transaction-level detail | QuickBooks Online export or connector |
| Revenue/ARR figures | Ask `chief-hubspot-officer` — never derive ARR from QBO |
| Current cash baseline, runway, board-facing numbers | Confluence **187760767** — BSH-2026 Strategic Home Sprint |
| Vendor, contract, and relationship context | G-Brain (`Bookmarked GBrain` connector) |

**Do not state a cash or runway figure from memory.** These change weekly. Pull, then cite the as-of date. This skill carries method, not numbers.

## CORE RULE

**QBO is the record of what happened. It is not the record of what is contracted.** Bookings, ARR, and pipeline live in HubSpot. Cash, expenses, and recognized revenue live in QBO. Most reconciliation confusion comes from treating one as a substitute for the other.

When a number disagrees across systems, that is usually correct and expected — explain *why* the two differ before treating it as an error.

## FRAMEWORK 1: READING THE POSITION

Answer cash questions in this order:

1. **Cash on hand** — as of a stated date, from the balance sheet.
2. **Committed outflow** — payroll, recurring vendors, known one-times in the window.
3. **Expected inflow** — only what is invoiced or contracted, never pipeline.
4. **The resulting window** — state it as a range with the assumption that drives each end.

Never present a runway figure without naming the two or three assumptions it rests on.

## FRAMEWORK 2: EXPLAINING A LINE ITEM

When asked "what is this charge":

1. Identify the vendor and the category it is booked to.
2. Say whether it is recurring or one-time, and at what cadence.
3. Flag if it looks miscategorized — do not silently reclassify it.

For recurring subscriptions, check the canonical merchant list before guessing at a category.

## FRAMEWORK 3: RECONCILIATION

When QBO and another system disagree:

| Likely cause | Check |
|---|---|
| Timing | Recognition period vs. booking date |
| Scope | Which entity, which pipeline, which date range |
| Definition | Recognized revenue vs. ARR vs. cash collected |
| Genuine error | Only after the three above are ruled out |

Report the cause, not just the delta. A delta without a cause invites the same question next month.

## HONEST UNCERTAINTY

If the export does not settle a question, say so and name what would — a bank statement, an invoice, the vendor contract, or Michelle's read. Financial numbers get repeated into board materials; a confident guess here propagates.

## WHAT THIS SKILL DOES NOT DO

- Make journal entries or change the books.
- Build forecast or scenario models.
- Produce investor or board narrative.
