---
name: ingestion-pipeline-audit
version: 1.0.0
description: |
  Audit an automated ingestion pipeline (recorder, mailbox, drive, CRM) that
  feeds the brain, and prove it actually works end to end. A scheduled job
  reporting success is not evidence that data arrived. Covers hop-by-hop
  verification, silent-failure detection, idempotency keying, multi-writer
  identity collision, and runbook-vs-reality drift.
triggers:
  - "is my sync actually working"
  - "audit the ingestion pipeline"
  - "why are there duplicate pages"
  - "the cron says ok but nothing is showing up"
  - "transcripts aren't reaching my brain"
  - "check the pipeline end to end"
  - "pipeline health check"
  - "why did the same meeting get ingested twice"
tools:
  - list_pages
  - get_page
  - get_ingest_log
  - get_stats
mutating: false
---

# Ingestion Pipeline Audit

> **Companion:** `skills/transcript-identity-hygiene/SKILL.md` repairs the
> *entity* damage bad ingestion causes. This skill audits the *pipeline* that
> caused it. Run this one first — repairing while the pipeline still misbehaves
> is wasted work.

## Why this exists

Ingestion pipelines fail quietly. The job runs, exits zero, logs "ok", and
writes nothing — or writes to a destination nobody checks. Because the failure
produces no error, it can persist for months while every dashboard says green.

The corresponding harm is asymmetric. A pipeline that stops is recoverable. A
pipeline that *half* works — writing pages without payloads, or the same source
record under many identities — actively degrades the brain while appearing
healthy.

## Contract

This skill guarantees:
- Every hop is verified by **observed destination state**, never by exit code
- Idempotency is checked against the **source system's stable ID**, not a
  derived slug, title, or filename
- Every writer into the same page space is enumerated, with its identity key
- Runbook claims are tested against reality and drift is reported
- Nothing is mutated — this is diagnosis only; repair is a separate, gated step

## THE IRON RULE

**A job reporting success is not evidence that data arrived.**

Verify each hop by looking at what is actually sitting in the destination, with
a timestamp. "Last run: ok" means the process exited, nothing more.

The canonical failure: a documented pipeline uploads to a storage folder several
times daily; the scheduler reports success on every run; the folder's newest
object is three months old. Every check was green. Nothing had moved since
spring.

## Phase 1: Map the hops

Read the runbook, config, or job definition and write down every hop as a chain:

```
Source system → API/CLI → intermediate storage → repo/DB → brain pages
```

For each hop record: what moves, where it lands, what proves it landed, and the
expected cadence.

**Do not trust the runbook as a description of current behavior.** Treat it as a
claim to be tested. Runbooks describe the design at authoring time; overrides,
safety patches, and refactors drift away from it silently.

## Phase 2: Verify each hop by destination state

For every hop, answer: **what is the newest object at this destination, and
when did it arrive?**

| Hop | Verify by | Red flag |
|---|---|---|
| Source API | newest record available | source itself is empty/stale |
| Intermediate storage | newest object timestamp in the exact folder/bucket | older than one expected cadence |
| Repo/filesystem | newest commit or file mtime | no writes despite "ok" runs |
| Brain pages | newest page + its provenance fields | pages exist but `source_kind` is null |

Compare each against the schedule. A destination whose newest item predates the
last several scheduled runs is a **dead hop**, regardless of job status.

Check the **exact** destination the config names, not a similar-looking one.
Data appearing in a *different* folder is not success — it means something else
is writing, often a human doing it manually. A useful tell: when an object's
created time and first-viewed time are seconds apart, a person downloaded it;
automation rarely views what it writes.

## Phase 3: Idempotency

**Find the key.** Ask what uniquely identifies a source record, then check what
the writer actually keys on.

The failure mode: the writer derives its target identity from mutable content —
a slug built from a title, participants, or an LLM-generated summary. Change the
naming logic and *every* record re-imports under a new identity. Each iteration
of the naming code mints a complete duplicate set.

**Test it directly:**

1. Extract the source-ID field from every ingested page
2. Group by that ID
3. Any group with more than one page is an idempotency failure

If the source ID is missing from some pages, that is worse than a duplicate —
those records can never be reconciled. Report the count separately.

Also check for the **same ID under different dates**. A date component in the
identity means a timezone shift or a re-parse produces a second page for one
record.

## Phase 4: Enumerate every writer

A page space usually has more writers than anyone remembers. Find them by
grouping pages on provenance fields and identity keys.

Build this table:

| Writer | How to recognize it | Identity key | Output quality |
|---|---|---|---|
| scheduled job A | key field X, null provenance | source ID | raw payload |
| scheduled job B | key field Y | different ID | stub/pointer |
| interactive/agent | provenance set to an API write | none | enriched |

**Writers with different identity keys cannot detect each other.** If two
systems can capture the same real-world event — two recorders in one meeting, an
email also forwarded by an automation — they will produce parallel pages that no
dedup pass can ever join, because they share no field.

The fix is a shared key derived from the *event*, not the capture: a calendar
event ID, a thread ID, an external record ID. Size the overlap before building
it — match on timestamp plus participants and count the collisions first.

## Phase 5: Payload integrity

Check that pages contain the **content**, not a pointer to it.

A pipeline that replaces a payload with "full version available in
<other system>" has created a dependency on a hop you must then verify
separately. If that hop is dead (Phase 2), the content is simply gone and the
page is a tombstone that reads like a record.

Rule: **a pointer is only acceptable if you verified the target exists.** Prefer
storing the payload and the pointer.

Also confirm provenance is populated. Null `source_kind` / `ingested_via` means
the writer bypassed the normal ingestion path, which usually means it also
bypassed enrichment, tagging, and linking.

## Phase 6: Report and gate repair

Produce the findings, then **stop**. Do not begin cleanup in the same pass.

Cleaning duplicates while the pipeline still mints them is wasted work — the
next scheduled run re-creates them. Sequence is always:

1. Fix the tap (idempotency, dead hop)
2. Verify one clean cycle
3. *Then* clean up historical damage via `transcript-identity-hygiene`

If the operator wants immediate cleanup, pausing the schedule first is the
minimum acceptable alternative.

## Security check

While reading runbooks and job configs, scan for credentials committed in
plaintext — client secrets, tokens, connection strings. Operational docs
accumulate these because they get pasted into recovery procedures.

If found: report the location, **never reproduce the value** in output, and
state that rotation (not deletion) is the fix, because the value is in version
history. Treat this as higher severity than the pipeline problem you were
sent to investigate.

## Output Format

```
PIPELINE: <name>   SCHEDULE: <cadence>   STATUS CLAIMED: <what the job reports>

HOPS
  <hop>  → newest item <timestamp>  → OK | DEAD (n cadences stale) | UNVERIFIED

IDEMPOTENCY
  key used: <field>          keyed correctly: yes/no
  records with >1 page: <n>  pages missing the key: <n>

WRITERS
  <writer> — key <field> — <n> pages — payload: full | pointer | stub

INTEGRITY
  pages with pointer-only payload: <n>   null provenance: <n>

SECURITY
  <location of any plaintext credential — value withheld>

VERDICT: <one line>
NEXT: <fix the tap first, then cleanup — named in order>
```

Always state what you did **not** verify. An unverified hop is a finding, not an
omission.

## Anti-Patterns

| Don't | Why |
|---|---|
| Trust "last_status: ok" | Exit code proves the process ran, not that data moved |
| Verify a hop by reading the runbook | Runbooks describe design, not current behavior |
| Accept data in a nearby folder as success | Means a human is doing it manually |
| Key idempotency on a derived slug or title | Naming changes re-import everything |
| Clean duplicates before fixing the writer | The next run re-creates them |
| Assume one writer | Page spaces accumulate writers nobody remembers |
| Accept a pointer without checking the target | Dead target turns the page into a tombstone |
| Infer duplicates from similar names | Different sources, same meeting — check the keys |
| Quote a discovered credential in the report | Spreads it further; report location only |
| Edit pipeline internals you cannot read | Diagnose, then hand a precise change to whoever owns it |
