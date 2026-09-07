# Loader scripts

These run on the machine holding the AskTED CSVs (they import the reviewed
normalization helpers from that machine's `ingest_askted.py` by path). They are
checked in here so the logic is versioned and reviewable; the copies that actually
ran live under `~/.claude/scripts/` on that machine.

| Script | What it does |
|---|---|
| `askted_profile.py` | Read-only. Verifies each file's header SHA against the reviewed pinned signature, counts rows, roles, org types, nameless rows, and identifier shapes. |
| `askted_roles.py` | Read-only. Dumps the FULL role inventory with named-vs-total counts, plus the distinct district-id set. This is what proved AskTED has no district library role. |
| `askted_emit_sql.py` | Emits idempotent upsert batches. Dedupes on the same tuple the DB hashes into `natural_key`. |
| `askted_role_map.json` | Mirror of `public.askted_role_map`, used only to filter which rows to emit. The authoritative role_code still comes from the DB join. |

Run order: profile → roles → emit.

`askted_emit_sql.py <scope> <role_codes|ALL> [batch_size] [out_dir]`

`scope` is `district` or `esc`. Batch size 300 keeps each file near 43 KB, which
is what the agent transport can carry in one hop; a direct database connection
does not need the batching at all.

## Validation scripts

| Script | Purpose |
|---|---|
| `askted_validate_csv.py` | Structural validation of the generated CSV: field counts, `natural_key` shape + uniqueness, `org_level` and `role_code` domains, TEA id format, region range, empty required fields. Exits non-zero on any problem. |
| `askted_check_fk.py` | Confirms every `district_id` in the CSV exists in `districts`, so the promote's FK filter cannot silently drop a district's staff. Needs `districts_snapshot.txt`. |

Run both before any import. Both are read-only.
