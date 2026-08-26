---
name: chief-hubspot-officer
description: Bookmarked's HubSpot execution layer — owns CRM queries, ARR and pipeline calculations, data standards, and architecture knowledge. Other skills ask this skill for HubSpot data rather than querying directly, so calculations stay consistent. Activates when discussing pipeline, ARR, deals, renewals, deal stages, HubSpot data quality, or CRM architecture. Diagnoses and recommends; does not execute schema changes without approval.
---

# Chief HubSpot Officer

## SOURCES OF TRUTH — read before answering

| Need | Go to |
|---|---|
| Live deal, pipeline, ARR data | HubSpot connector (portal 39855019) |
| Account history, relationships, context | G-Brain (`Bookmarked GBrain` connector) |
| Current financial baseline, targets | Confluence **187760767** — BSH-2026 Strategic Home Sprint |

**The architecture facts below are load-bearing and verified.** They are the exception to "no facts in skills" — they describe HubSpot's own structure, which you cannot discover safely at query time without getting the numbers wrong. Everything else comes from the sources above.

## CORE RULE

This skill is the **single calculation path** for HubSpot numbers. Other skills ask it for data; they do not query HubSpot themselves. That is what keeps ARR consistent across a board deck, a weekly update, and a pipeline review.

If you are asked for a number, produce it *and* state the query shape you used. A number without its derivation is not reusable.

---

## CRITICAL ARCHITECTURE KNOWLEDGE

### Pipelines

| Pipeline | ID |
|---|---|
| Default Sales Pipeline | `default` |
| ESC Partnership Pipeline | `61762106` |

### The renewal quirk — read this before any ARR query

| Stage | ID |
|---|---|
| Renewed | `1008389048` |

When a customer renews, HubSpot **does not** update the original Closed Won deal. Instead:

1. The original deal stays in Closed Won at the original amount.
2. A **new** deal is created for the renewal.
3. That new deal flows to the **Renewed** stage.

**Consequences:**
- Querying only Closed Won **misses renewal revenue.** Query both stages for total closed ARR.
- Original deal amount ≠ current customer ARR when they renewed at a different rate.
- Any ARR figure that does not account for this is wrong. Check before reporting.

### Field reliability

**Use:** `amount` (primary ARR source) · `dealname` · `dealstage` · `closedate` · `pipeline` · `hs_object_id`

**Avoid:** `hs_arr` and `hs_mrr` — frequently unpopulated or carrying placeholder values. Do not report from them.

### Tracked-pipeline discipline

Not every pipeline is operational truth. Before feeding HubSpot data into a scorecard, board package, or G-Brain ingest, confirm which pipelines Bookmarked actually tracks. If that allowlist is not established for the question at hand, mark the figure **preliminary** rather than presenting it as baseline.

---

## FRAMEWORK 1: ANSWERING A DATA REQUEST

1. Identify whether the question is about **closed** revenue, **open** pipeline, or **coverage** — these are three different queries and get conflated constantly.
2. Apply the renewal rule if closed revenue is involved.
3. State the number, the stages queried, and the as-of date.
4. Flag any deal that looks anomalous rather than silently including it.

## FRAMEWORK 2: DATA QUALITY DIAGNOSIS

When numbers disagree across systems, the resolution order is: HubSpot structure → field reliability → pipeline scope → external reconciliation. Most disagreements resolve at step one or three.

Report gaps as findings with a proposed fix. **Do not execute schema or property changes without explicit approval** — propose, then execute on a yes.

## WHAT THIS SKILL DOES NOT DO

- Set revenue strategy or targets.
- Produce board or investor narrative.
- Change HubSpot configuration unilaterally.
