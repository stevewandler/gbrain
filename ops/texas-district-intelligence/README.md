# Texas District Intelligence — contact layer + TBTC sweep

Working package for making `texas-esc-districts` (Supabase `fdnncloyxjsxwdhpfkjj`)
the central source for current Texas district contacts, and for completing the
Take Back the Classroom (TBTC) campus-level scrape.

**Status 2026-08-26:** the migration is **APPLIED** to `fdnncloyxjsxwdhpfkjj`
(approved by the brain owner). The contact load is **partial** — see
"Completing the load" below. Findings from the real artifacts are in
[FINDINGS.md](FINDINGS.md).

---

## Why this package exists

As of 2026-08-26 the database holds a good identity/enrollment spine and **no
contact layer at all**:

| Layer | State |
|---|---|
| `districts` | 1,219 rows, 20 ESC regions, enrollment Oct 2025 complete, snapshot `data_last_verified = 2026-06-26` |
| Contact fields on `districts` (`phone`, `email`, `mailing_address`, `web_address`, `nces_district_id`) | columns exist, **0 of 1,219 populated** |
| Superintendent / assistant superintendent / campus staff | **absent — no table** |

The AskTED personnel export itself is not missing. The 2026-08-21 audit
(G-Brain `projects/texas-district-intelligence/audit-and-architecture-2026-08-21`)
records it as **55,493 district/school rows + 2,819 ESC rows = 58,312 combined**,
with post-normalization gaps of five NCES values, three websites, and six
superintendents. It was analyzed and never loaded.

The governed evidence-first architecture designed to hold it is at
**DO NOT APPLY** — three independent reviews returned FAIL on six engineering
blockers (blocker 1 passed; 2 and 5 awaiting review; 3, 4, 6 queued). This
package is the deliberately narrow alternative so the revenue team gets the
list now. It is **additive only** and the governed model can absorb it later.

---

## 1. Contact layer — `001_contact_layer.sql`

Three tables, three views, no changes to anything that already exists.

- **`source_runs`** — one row per ingest occurrence: source date (what the
  source claims, distinct from fetch time), `artifact_sha256` pinning the exact
  bytes parsed, parser version, raw vs loaded row counts.
- **`district_contacts`** — the flat table the team queries. One row per
  person-role-org observation, scoped `district` / `campus` / `esc`, keyed for
  idempotent upsert on `natural_key`.
- **`role_code_ref`** — role normalization as a *table*, so new AskTED title
  strings get mapped without a migration. Priority roles flagged:
  superintendent, assistant superintendent, curriculum director, library
  director, technology director, principal, librarian.
- **Views** — `v_current_superintendents` (one row per district, the immediate
  ask), `v_district_contact_coverage` (the gap list), `v_latest_run`.

### Two design rules carried from the audit

**"Missing is not zero, closed, vacant, or ended."** A person who stops
appearing in a newer export gets a stale `last_seen_run_id` — never a
fabricated end date, never a delete. `v_current_superintendents.in_latest_run`
surfaces it as `false` so it reads as *investigate this*, not *the seat is
vacant*.

**`role_title` is stored verbatim.** Normalization lives in `role_code`, so the
original AskTED string is always recoverable.

### Verification actually performed

Run against a throwaway PostgreSQL 16 cluster with the live schema mirrored
(`districts`, `escs`) and Supabase's `anon` / `authenticated` / `service_role`
roles created:

| Check | Result |
|---|---|
| Applies clean on a fresh cluster | pass |
| Idempotent — 3 consecutive re-runs | pass, 0 errors |
| Upsert on `natural_key` re-observes instead of duplicating | pass (3 rows, not 4; email updated to newer value) |
| Person absent from newer run → `in_latest_run = false`, row retained | pass |
| `org_level='esc'` with null `region_number` rejected | pass (check constraint fires) |
| Unmapped role title loads as `other` without aborting the run | pass (`NOT VALID` FK) |
| `anon` SELECT on contacts | **denied** |
| `authenticated` SELECT | permitted |
| `authenticated` INSERT | **denied** |

Two real bugs were found and fixed by this testing:

1. **Not idempotent.** `ADD CONSTRAINT` and three `CREATE POLICY` statements
   had no existence guard, so run 2 failed. Now guarded.
2. **Depended on ambient role state.** The first draft leaned on Supabase's
   `ALTER DEFAULT PRIVILEGES` to grant `authenticated` its read. That is the
   same class of finding that blocked the earlier governed package ("green
   tests depend on ambient role state"). All grants are now explicit.

Also caught before apply: `pg_trgm` is **not installed** on the target project,
so the original `gin_trgm_ops` index on `full_name` would have failed. Replaced
with a btree on `lower(full_name)`.

### What is still needed to load

The loader is **not** written, because one input is unavailable from this
session: the exact column headers of the AskTED personnel export. Everything
else is ready. Blockers:

- **The export file.** Lives at `~/Documents/Codex/2026-08-19/...` per the audit.
  Laptop Bridge timed out three times (laptop asleep).
- **`BookmarkED-Corp/bookmarked-district-intelligence`** exists and holds the
  preserved evidence, but this session is scoped to `stevewandler/gbrain`;
  cross-owner `add_repo` is refused in v1.
- **Network egress** blocks `tea.texas.gov`, `tea4avholly.tea.state.tx.us`
  (AskTED), the TEA ArcGIS open-data host, and `takebacktheclassroom.org`. No
  re-pull from source is possible from this environment.

Any one of: wake the laptop, start a session against the district-intelligence
repo, or run from an environment whose network policy allows `tea.texas.gov`.

### Load runbook (once the file is reachable)

1. Checksum the artifact; open a `source_runs` row with `source_date` from the
   export itself, not today's date.
2. Map columns to `district_contacts`. Confirm role-title → `role_code`
   coverage; anything unmapped lands as `other` and appears in a review query.
3. Resolve org: TEA district ID for district rows, region for ESC rows. The
   audit flagged three IDs present only in the frozen snapshot (`130-801`,
   `220-814`, `246-802`, combined enrollment 659) — absence from one export
   does not establish closure, so do not drop them.
4. Load in a transaction. Upsert on `natural_key`.
5. Gate on: superintendent coverage (expect ~1,213 of 1,219 given six known
   gaps), zero-contact districts, unmapped role codes, `row_count_loaded` vs
   `row_count_raw`.
6. Set `row_count_loaded` and only then treat the run as authoritative.

### Refresh cadence — the part that makes it "central"

A one-time load decays. AskTED is the official dated directory baseline but is
**not automatically current on leadership**: the 2026-08-20 Region 16 dossier
found current public leadership that superseded both HubSpot titles and
required going to district/ESC sites to resolve. Recommend a monthly AskTED run
plus a conflict queue, and treat HubSpot as commercial authority to crosswalk
against — not to overwrite.

---

## 2. TBTC campus sweep — full sweep of all 848

Decision 2026-08-26: complete the sweep.

### The scrape is trustworthy — verified, not assumed

Reconciliation across all 7 already-scraped districts:

| District | Campuses expected | Campuses loaded | District `book_count` | Σ campus `book_count` | Delta |
|---|---|---|---|---|---|
| Canyon ISD | 19 | 19 | 242 | 242 | **0** |
| Canadian ISD | 4 | 4 | 127 | 127 | **0** |
| Spearman ISD | 3 | 3 | 79 | 79 | **0** |
| Pringle-Morse CISD | 1 | 1 | 9 | 9 | **0** |
| Vega ISD | 1 | 1 | 0 | 0 | **0** |
| Perryton ISD | 5 | 5 | 0 | 0 | **0** |
| Clarendon ISD | 1 | 1 | 0 | 0 | **0** |

Every district ties out exactly, and `campus_title_rows` equals `book_count` in
all 7 cases. Two consequences worth having:

1. District-level `book_count` **is** the count of campus-title placements, so
   the completed `tbtc_school_books` table lands at ~**134,943 rows** — a
   derived target, not a guess. Any district that fails to hit its own
   `book_count` after scraping is a real defect.
2. `school_count` is populated for all 848 and matched campuses-loaded exactly,
   so the sweep can be sized precisely rather than extrapolated.

### Exact sweep size

| Metric | Value |
|---|---|
| Districts remaining | **841** of 848 |
| Campus fetches remaining | **5,840** of 5,874 |
| Flagged placements to materialize | **134,486** |
| Districts with `book_count = 0` (still need a confirming fetch) | 182 |
| Largest single district | 126 campuses |
| `tbtc_schools` after sweep | 34 → **5,874** |
| `tbtc_school_books` after sweep | 457 → **~134,943** |

At a polite 1 request/second that is roughly **2 hours** of wall clock; at 2s,
under 4. This is a well-bounded job, not a platform project. The engineering
that matters is resumability and the reconciliation gate, not throughput.

### Controls the sweep needs

- **Checkpointing.** Bank progress per district so a kill resumes instead of
  restarting. This repo already documents the proven pattern — the append-only
  `op_checkpoint_paths` + lock-heartbeat design in `CLAUDE.md` under "Sync
  resumability". Reuse it rather than inventing one.
- **Rate limiting + backoff.** Fixed delay plus jitter; exponential backoff on
  429/5xx. TBTC is a small nonprofit site; do not hammer it.
- **Per-district reconciliation gate.** After each district, assert
  `Σ campus book_count == district book_count` and
  `campuses_loaded == school_count`. Both hold on all 7 today, so a mismatch is
  a real signal. Quarantine the district, do not abort the sweep.
- **No silent caps.** Log every district skipped or truncated. A partial sweep
  that reads as complete is worse than an obviously partial one.
- **Re-scrape cadence.** TBTC's flag list moves. Stamp `scraped_at` per campus
  (already in the schema) and re-sweep on a schedule.

### Two things to fix while sweeping

- **36 remaining districts have no `tea_district_id`.** 812 of 848 are matched
  (96%). The unmatched 36 need name resolution or an explicit
  "not a TEA district" disposition — the TEA join is what makes this dataset an
  asset, so leaving them unmatched quietly shrinks its value.
- **`tbtc_books` will grow well past 232 titles.** Dedupe on ISBN where
  present, and expect title/author variants that need normalization.

### Not runnable from here

`takebacktheclassroom.org` is blocked by this environment's network policy.
The sweep needs an environment with egress to it.

---

## Files

| File | What it is |
|---|---|
| `001_contact_layer.sql` | Contact-layer migration. Drafted, tested, **not applied**. |
| `README.md` | This document. |

## Open decisions

1. Approve applying `001_contact_layer.sql` to `fdnncloyxjsxwdhpfkjj` (needs a
   backup/PITR check first, per the earlier package's own release gates).
2. Load the existing 2026-08-21 export, or re-pull AskTED fresh and stamp a new
   run? Re-pull is cleaner if we are declaring this the canonical source.
3. Where does this package finally live? `BookmarkED-Corp/bookmarked-district-intelligence`
   is the architecturally correct home; it is staged here because that repo is
   not reachable from this session.


---

## Applied state (2026-08-26)

Baseline before apply: 6 tables, 1 view, 6 policies, districts 1,219,
tbtc_districts 848, tbtc_school_books 457.

After `001` + `002`: **10 tables, 4 views, 14 policies**, `role_code_ref` 20 rows,
`askted_role_map` 137 rows. Pre-existing data unchanged. `anon` holds **zero**
grants on any new table — verified in production, not assumed.

Two `source_runs` rows are registered, each pinned to its artifact SHA-256:

| source_name | artifact | row_count_raw |
|---|---|---|
| `askted_personnel` | district+school personnel, 2026-08-19 | 55,493 |
| `askted_personnel_esc` | ESC personnel, 2026-08-19 | 2,819 |

`district_contacts` currently holds **300 rows** across 177 districts (176
superintendents, 123 assistant superintendents, 1 executive director), 0 unmapped
roles, 299/300 with email. That is the first batch of the leadership tier — the
load is deliberately incomplete pending the mechanism decision below.

## Completing the load — bulk CSV via staging (recommended)

The remaining rows are **47,070** (the full named set; 300 are already in, and
re-importing them is a no-op because both paths hash the same `natural_key`).

The earlier blocker was transport: no Supabase credential on the machine holding
the CSVs meant every row round-tripped through the agent's context, capping
batches near 300 rows. The fix avoids the agent entirely and needs **no new
credential**:

1. **Generate the CSVs** — `loader/askted_emit_csv.py` writes
   `askted_contacts_01.csv` (25,000 rows, 4.8 MB) and `askted_contacts_02.csv`
   (22,070 rows, 4.2 MB). Every column is precomputed, including `role_code` and
   the `natural_key` hash, because a CSV import cannot run SQL.
2. **Import into `district_contacts_staging`** via the Supabase dashboard Table
   Editor. Staging is all-text with no constraints and no FK, so a type cast or an
   unknown district id cannot fail the import partway through.
3. **Promote** with `003_promote_staging.sql`: it casts, resolves the run id from
   `source_scope`, applies the district FK guard, collapses duplicate
   `natural_key`s, and upserts.
4. **Read the reject report** (step 2 of that file — expect zero rows),
   reconcile the counts, set `row_count_loaded`, then truncate staging.

Why staging rather than importing straight into `district_contacts`: a dashboard
CSV import does plain INSERTs, so it would collide with the 300 rows already
loaded and would hard-fail on any FK miss. Staging turns both into reportable
data instead of a failed import.

**Alternative — scoped loader role.** A dedicated Postgres role with
INSERT/SELECT/UPDATE on `district_contacts` only, driven from `psql` on the
machine holding the CSVs. Faster and scriptable, which is what the monthly
refresh will eventually want. It is a production credential, so it needs explicit
approval and should be created and stored by a human, not generated in an agent
transcript. Not needed for the one-time backfill.

## Import scope (decided 2026-08-26)

Load `org_level = 'district'` only — district-office staff **plus** elected
trustees. **35,043 rows.** Campus principals and ESC staff are deferred: not
dropped from the pipeline, just not in this import. Re-run the generator with
`ALL` to pick them up.

| In this import (`org_level = 'district'`) | Rows |
|---|---|
| **Elected board members + officers** | **7,958** |
| Student services / liaisons | 4,030 |
| Special education | 3,937 |
| Data / PEIMS / TREX reporting | 3,733 |
| Assessment & accountability | 2,462 |
| Technology & cybersecurity | 2,144 |
| Federal programs | 2,022 |
| Operations, transport, facilities | 1,528 |
| Safety, security, discipline | 1,382 |
| Business / finance | 1,233 |
| **Superintendents** | **1,209** |
| **Assistant / deputy / associate superintendents** | **873** |
| Human resources | 861 |
| Curriculum & instruction | 853 |
| Administrative support | 817 |
| Executive director | 1 |
| **Total** | **35,043** |

| Deferred — available, not loaded | Rows |
|---|---|
| Campus principals (`org_level = 'campus'`) | 9,461 |
| ESC staff (`org_level = 'esc'`) | 2,576 |

Board-member rows dropped from 8,177 to 7,958 when ESC scope was excluded: 219 of
them were ESC board members and governance staff, not district trustees.

Library/media disappears entirely from this scope, because all 38 of those rows
are ESC. AskTED has no district-level library role at all — see
[FINDINGS.md](FINDINGS.md).

## Pre-import validation (all PASS, 2026-08-26)

The promote path was exercised end to end against a throwaway PostgreSQL 16
cluster carrying the real migrations, with deliberately hostile staging rows:

| Case | Expected | Result |
|---|---|---|
| Valid rows promote | inserted | pass |
| Duplicate `natural_key` inside staging | collapse to one, keep the richer contact record | pass — no SQLSTATE 21000, email/phone taken from the populated copy |
| `district_id` not in `districts` | rejected and reported, promote still succeeds | pass |
| ESC row with no region | rejected by the org-ref check | pass |
| Unknown `role_code` | falls back to `other`, `role_title` preserved | pass |
| Promote run 2 and 3 | upsert, no growth, no error | pass — row count stable |
| Reject report | names exactly the bad rows | pass — 2 of 2 |

The 35,043-row file itself also validates clean: 35,043 distinct `natural_key`s
and **zero** duplicates, every `org_level` = `district`, every `district_id`
matching `NNN-NNN`, all 20 ESC regions present, 31,483 rows with email (89.8%)
and 32,267 with phone (92.1%), and no row missing a name or role title.

**FK pre-check: zero rows would be rejected.** All 1,216 districts in the CSV
exist in `districts`. The 3 live districts with no AskTED personnel are
`130-801`, `220-814`, `246-802` — the same three the 2026-08-21 audit identified
as frozen-only, confirmed independently here.

## The one remaining manual step

Supabase dashboard → Table Editor → `district_contacts_staging` → Import data
from CSV → `~/Documents/askted-import/askted_contacts_01.csv` (6.6 MB).

Then the promote in `003_promote_staging.sql` runs, the reject report is read
(expected: zero rows), `row_count_loaded` is recorded, and staging is truncated.

## Follow-ups

- Load the organization file (`askted_school_district_2026-08-19.csv`, 9,726 rows)
  to backfill the `districts` contact columns that are still 0-of-1,219 populated
  (phone, email, mailing address, website, NCES id).
- No campus table yet: `district_contacts.campus_id` / `campus_name` carry campus
  identity inline for the 9,896 principal rows. A real `campuses` table is the
  right home once the organization file lands.
- 36 TBTC districts still have no `tea_district_id`.
