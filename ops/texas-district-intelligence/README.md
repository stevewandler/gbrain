# Texas District Intelligence — contact layer + TBTC sweep

Working package for making `texas-esc-districts` (Supabase `fdnncloyxjsxwdhpfkjj`)
the central source for current Texas district contacts, and for completing the
Take Back the Classroom (TBTC) campus-level scrape.

**Status 2026-08-27:** the district-level contact load is **COMPLETE**. All
35,043 district-scope AskTED personnel rows (elected trustees + district-office
staff) are live in `district_contacts` against `fdnncloyxjsxwdhpfkjj`, zero
rejects. Campus principals (9,461 rows) and ESC staff (2,576 rows) are
deliberately not loaded yet — see "Import scope" below. Findings from the real
artifacts are in [FINDINGS.md](FINDINGS.md); how the bulk load actually moved
data is in "How the 2026-08-27 load actually moved data" below.

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

### What was needed to load (resolved 2026-08-27)

All three blockers below were resolved — kept here as a record, since the
next person to touch this package may hit "the file is missing" doubt again
and shouldn't have to re-derive that it was already found:

- **The export file.** Was reachable all along at
  `~/Documents/askted-import/` on the brain owner's machine, once Laptop
  Bridge could reach it (earlier timeouts were the laptop asleep, not the
  file being gone).
- **`BookmarkED-Corp/bookmarked-district-intelligence`** — still not reachable
  from this session (cross-owner `add_repo` still refused in v1), but turned
  out not to matter: this package's own `loader/` scripts were sufficient.
- **Network egress** still blocks `tea.texas.gov` and `takebacktheclassroom.org`
  from this environment. Irrelevant to this load, since it used the existing
  2026-08-19 export rather than re-pulling — still the blocker for any future
  re-pull or for the TBTC sweep in section 2 below.

### Load runbook (as originally planned)

The generic version of the plan, for the next person doing a fresh load rather
than a refresh. What was *actually* run for the 2026-08-27 district-scope load
— including the transport dead ends and fix — is in "How the 2026-08-27 load
actually moved data" and "Pre-import validation" below; this is the more
general shape:

1. Checksum the artifact; open a `source_runs` row with `source_date` from the
   export itself, not today's date.
2. Map columns to `district_contacts`. Confirm role-title → `role_code`
   coverage; anything unmapped lands as `other` and appears in a review query.
3. Resolve org: TEA district ID for district rows, region for ESC rows. The
   audit flagged three IDs present only in the frozen snapshot (`130-801`,
   `220-814`, `246-802`, combined enrollment 659) — absence from one export
   does not establish closure, so do not drop them.
4. Load in a transaction. Upsert on `natural_key`.
5. Gate on: superintendent coverage, zero-contact districts, unmapped role
   codes, `row_count_loaded` vs `row_count_raw`.
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
| `001_contact_layer.sql` | Core contact-layer migration. **Applied.** |
| `001b_staging_table.sql` | `district_contacts_staging` DDL + RLS. **Applied** 2026-08-27 (was applied ahead of being committed — see its header comment). |
| `002_role_taxonomy_seed.sql` | 20 role codes + 137 AskTED-role → role_code mappings. **Applied.** |
| `003_promote_staging.sql` | Staging → `district_contacts` promote, reject report, reconcile. **Run**, zero rejects. |
| `FINDINGS.md` | Source-data findings from the real AskTED artifacts (header SHA verification, no-district-library-role, duplicate rows, nameless rows). |
| `loader/` | CSV emission + FK pre-check scripts (`askted_emit_csv.py`, `askted_check_fk.py`, `askted_role_map.json`) run on the machine holding the source export. |
| `README.md` | This document. |

## Open decisions

1. ~~Approve applying `001_contact_layer.sql`~~ — **done**, applied and approved
   2026-08-26.
2. ~~Load the existing export, or re-pull fresh~~ — **decided**: loaded the
   existing 2026-08-19 export as-is, no re-pull (this environment cannot reach
   `tea.texas.gov` anyway).
3. Where does this package finally live? `BookmarkED-Corp/bookmarked-district-intelligence`
   is the architecturally correct home; it is staged here because that repo is
   not reachable from this session.


---

## Applied state (2026-08-27)

Baseline before apply: 6 tables, 1 view, 6 policies, districts 1,219,
tbtc_districts 848, tbtc_school_books 457.

After `001` + `002` + `001b`: **11 tables, 4 views, 16 policies** (verified live,
not computed by hand), `role_code_ref` 20 rows, `askted_role_map` 137 rows.
Pre-existing data unchanged. `anon` holds **zero** grants on any new table —
verified in production, not assumed.

Two `source_runs` rows are registered, each pinned to its artifact SHA-256:

| source_name | artifact | row_count_raw | row_count_loaded |
|---|---|---|---|
| `askted_personnel` | district+school personnel, 2026-08-19 | 55,493 | 35,043 |
| `askted_personnel_esc` | ESC personnel, 2026-08-19 | 2,819 | 0 (deferred) |

`district_contacts` holds **35,043 rows** across **1,216** distinct
districts/charter operators (verified live) — every district-scope AskTED
personnel row: elected trustees, superintendents, assistant superintendents,
and all other district-office roles. **0** landed as the unmapped `other`
role_code, **31,483** have an email, **32,267** have a phone (all verified live
against the final table, matching the pre-import CSV check exactly — zero
drift between predicted and landed). The 300 leadership-tier rows loaded first
(2026-08-26) collapsed into this set on `natural_key`: same people, same hash,
no duplicates. `district_contacts_staging` is empty (truncated after promote)
and stays in the schema for the next refresh.

## How the 2026-08-27 load actually moved data

The plan going into this load was a scoped, temporary Postgres role driven by
`psql \copy` straight from the machine holding the CSV — no CSV data round-
tripping through the agent's context, no dashboard CSV import (ruled out: the
file already existed, so a manual re-upload step would have just been the
agent handing back work it should do itself). That plan hit two dead ends
specific to this project's network path, both worth recording so the next
monthly refresh doesn't re-discover them the slow way:

1. **The direct connection host (`db.<ref>.supabase.co:5432`) is IPv6-only**,
   and the machine's network cannot resolve IPv6 at all — confirmed by testing
   DNS resolution against a known-good IPv6 hostname on the same network, which
   failed identically. Not a Supabase misconfiguration; a local network limit.
2. **The Supavisor connection pooler rejects a role created by raw SQL.** A
   role made with plain `CREATE ROLE ... LOGIN` is invisible to the pooler's
   own tenant/user cache — it returned `tenant/user ... not found` even though
   the role existed and worked fine for direct SQL access via the Supabase
   MCP connection. The pooler only recognizes roles provisioned through
   Supabase's own control plane, not ones created ad hoc in a session.

With both `psql` paths blocked, the load instead went over HTTPS, which was
already reachable:

1. A temporary Supabase Edge Function (`askted-staging-loader`) accepted a
   batch of rows over POST, checked a disposable bearer token, whitelisted the
   exact 14 staging columns (no dynamic SQL, no arbitrary table), and inserted
   into `district_contacts_staging` using the service-role key **held
   server-side inside the function** — never exposed to the machine or the
   network.
2. A small script on the machine holding the CSV read it in 1,000-row batches
   and POSTed each batch to the function, authenticated with the project's
   public anon key plus the disposable token. All 36 batches (35,043 rows)
   succeeded on the first attempt, zero retries needed.
3. After the promote step below verified clean, the function was redeployed
   as a dead stub (always returns HTTP 410) since there's no delete-function
   tool available, the disposable token was discarded, and the one-off scripts
   holding it were deleted from the machine.

Net effect: the same zero-agent-context, zero-standing-credential properties
the `psql` plan was designed for, reached by a different transport. For the
next refresh, either retry the scoped-role approach (it may work fine from a
network with IPv6 egress) or reuse this Edge Function pattern — the function
code is in this commit's history if it needs to be redeployed.

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

## Follow-ups

- Load the organization file (`askted_school_district_2026-08-19.csv`, 9,726 rows)
  to backfill the `districts` contact columns that are still 0-of-1,219 populated
  (phone, email, mailing address, website, NCES id).
- No campus table yet: `district_contacts.campus_id` / `campus_name` carry campus
  identity inline for the 9,896 principal rows. A real `campuses` table is the
  right home once the organization file lands.
- 36 TBTC districts still have no `tea_district_id`.
