# AskTED load — findings from the 2026-08-26 run

Facts established by running against the real artifacts, not inferred.

## The export was found and verified

| File | Rows | SHA-256 (first 16) |
|---|---|---|
| `askted_personnel_principals_superintendents_all_district_staff_2026-08-19.csv` | 55,493 | `cba86b97270f90cb` |
| `askted_personnel_all_esc_staff_2026-08-19.csv` | 2,819 | `3b3922b141282 3d2` |
| `askted_school_district_2026-08-19.csv` (organization) | 9,726 | not loaded |

55,493 + 2,819 = **58,312**, matching the 2026-08-21 audit exactly. Both personnel
files' header SHA-256 is `104ea18e890dd94683c7a67dcbd1d963029adc62b4e0fd6166928df966d1adde`,
which equals `CURRENT_PERSONNEL_HEADER_SIGNATURE` pinned in the reviewed
`ingest_askted.py` — so these are the audited artifacts, not a re-export.

## AskTED has no district-level library contact

Across all **43** district roles, zero contain LIBRAR or MEDIA. `LIBRARY` (22) and
`MEDIA` (22) exist only at **ESC** scope, in the 94-role ESC vocabulary.

This is a product-relevant limit, not a load bug: the buyer persona Bookmarked
sells to is not in this dataset. `role_code_ref.library_media` is still flagged
`is_priority`, and its table comment says an empty district set means the source
does not carry the contact — not that a district has no librarian.

## Source data quirks that would have broken a guessed loader

1. **Identifiers carry an Excel text-forcing apostrophe** — `'001902`. The reviewed
   `normalize_tea_identifier` strips it and reformats `001902` → `001-902`, which is
   what `districts.district_id` uses. A naive load would have matched nothing.
2. **Campus rows use 9-digit org numbers** (`'001902001` → `001-902-001`); district
   rows use 6. Org type splits 45,597 district / 9,896 school.
3. **Empty fields are a single space**, not empty — every value needs whitespace
   collapse before a NULL test. Name fields are also right-padded.
4. **11,114 rows carry no name in any name field** (10,871 district + 243 ESC).
   These are unfilled directory slots. They are skipped, not loaded with a
   placeholder. The gap is visible as `row_count_raw` vs `row_count_loaded`.
5. **Exact duplicate rows exist.** Celina ISD lists the same assistant
   superintendent twice, identically. Postgres rejects the entire batch with
   `21000 ON CONFLICT DO UPDATE command cannot affect row a second time`. The
   loader now collapses duplicates on the same tuple the database hashes into
   `natural_key`, keeps the richer of the two contact rows, and the SQL carries a
   `DISTINCT ON` safety net. The prior audit classed this as
   `duplicate_source_record_exact` (warning severity).
6. **1,216 distinct district IDs** in the export vs 1,219 in `districts`. The insert
   filters on an existence check against `districts` rather than risking an FK
   abort mid-batch.

## Role coverage

All 43 district roles and all 94 ESC roles are mapped explicitly in
`askted_role_map` — nothing falls through to `other` by accident. Verified: the
loaded rows show `role_code = 'other'` count of **0**.

Named-vs-total counts matter, because a role can exist with nobody in it:

| Role | Rows | Named |
|---|---|---|
| SUPERINTENDENT | 1,133 | **1,127** |
| PRINCIPAL | 9,896 | 9,461 |
| ASSISTANT SUPERINTENDENT | 581 | 581 |
| SCHOOL SOCIAL WORKER | 1,236 | **251** |
| WEB ER CONTACT | 1,236 | 545 |

1,127 named superintendents out of 1,133 rows — the **six missing superintendents**
the audit reported, confirmed independently by the loader's `skipped_no_name` count.

Named superintendent coverage: SUPERINTENDENT 1,127 + INTERIM 74 + ACTING 8 =
**1,209** across 1,216 districts.

## The transfer bottleneck (resolved 2026-08-27)

Originally: this session cannot reach `tea.texas.gov` or
`takebacktheclassroom.org` (egress policy), and the laptop held no Supabase
credential for this project — so rows had to pass through the agent's
context: read the batch off the laptop, then write it back out as a SQL
parameter. That cost roughly twice the payload per batch, capped a batch at
~300 rows (~43 KB) before the tool output limit, and — at real scale — hit the
org's monthly Anthropic spend cap partway through, independent of how many
parallel agents were thrown at it (the cap is account-wide, not per-agent).

Fixed by removing the agent from the data path entirely rather than working
around the cap: see README "How the 2026-08-27 load actually moved data" for
the mechanism (a temporary HTTPS relay after both direct-`psql` options turned
out to be blocked on that machine's network) and "Applied state" for the
verified result — all 35,043 district-scope rows loaded, zero rejects.
