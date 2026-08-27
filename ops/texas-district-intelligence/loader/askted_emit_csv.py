#!/usr/bin/env python3
"""Emit the FULL AskTED contact set as CSVs for bulk import into Supabase.

Usage: askted_emit_csv.py [max_rows_per_file] [out_dir]

Writes district_contacts_staging-shaped CSVs (all text, header row) importable
through the Supabase dashboard Table Editor — no credential, no agent round-trip.
Promote afterwards with ../003_promote_staging.sql, which does the FK check, the
dedupe and the upsert, and reports rejects.

Everything is precomputed here because a CSV import cannot run SQL:
  role_code    from askted_role_map.json (mirrors public.askted_role_map)
  natural_key  sha256 of district_id|campus_id|region|role_title|lower(full_name)
               — the SAME tuple the batch loader hashes in SQL, so the two paths
               agree and re-importing already-loaded rows is idempotent.

Normalization reuses the REVIEWED helpers from ingest_askted.py rather than
reimplementing them. Rows with no name in any name field are skipped, not
invented. Exact duplicate source rows are collapsed, keeping the richer record.

Measured 2026-08-26 (org_level=ALL): 47,070 rows out, 0 unmapped roles, 128
duplicates collapsed, 11,114 nameless rows skipped.

Measured 2026-08-27 (org_level=district, the scope actually loaded into
district_contacts — see ../README.md): 35,043 rows out, 0 unmapped roles.
Campus (9,461) and ESC (2,576) rows are excluded from that scope, not dropped
from the pipeline — rerun with ALL to pick them up later.

The dashboard-import path above is one option; the 2026-08-27 load actually
went through an HTTPS relay instead (a temporary Edge Function) because the
direct psql paths were blocked on that machine's network — see ../README.md
"How the 2026-08-27 load actually moved data" before assuming either path
will work unmodified for the next refresh.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

WORK = Path("/Users/stevewandler/Documents/Codex/2026-08-19/texas-district-data-intelligence/work")
PLANNER = WORK.parent / "scripts" / "ingest_askted.py"
ROLE_MAP = json.loads((Path(__file__).parent / "askted_role_map.json").read_text())

FILES = {
    "district": WORK / "askted_personnel_principals_superintendents_all_district_staff_2026-08-19.csv",
    "esc": WORK / "askted_personnel_all_esc_staff_2026-08-19.csv",
}
COLS = ["org_level", "district_id", "region_number", "campus_id", "campus_name",
        "full_name", "first_name", "last_name", "role_title", "role_code",
        "email", "phone", "natural_key", "source_scope"]


def load_planner():
    spec = importlib.util.spec_from_file_location("ingest_askted", PLANNER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ingest_askted"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    max_rows = int(sys.argv[1]) if len(sys.argv) > 1 else 25000
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "/Users/stevewandler/Documents/askted-import")
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("askted_contacts_*.csv"):
        stale.unlink()

    p = load_planner()
    collapse, strip, norm_id = p.collapse_whitespace, p.strip_tea_marker, p.normalize_tea_identifier

    rows, seen = [], {}
    stats, role_code_counts, unmapped = Counter(), Counter(), Counter()

    for scope in ("district", "esc"):
        smap = ROLE_MAP[scope]
        with FILES[scope].open(newline="", encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                stats[f"{scope}_seen"] += 1
                role = collapse(r.get("Role"))
                code = smap.get(role)
                if code is None:
                    unmapped[f"{scope}:{role}"] += 1
                    code = "other"

                full = collapse(r.get("Full Name"))
                first, last = collapse(r.get("First Name")), collapse(r.get("Last Name"))
                if not full:
                    full = (first + " " + last).strip()
                if not full:
                    stats[f"{scope}_skipped_no_name"] += 1
                    continue

                org_type = collapse(r.get("Organization Type"))
                org_num = strip(r.get("Organization Number"))
                region = strip(r.get("Region Number"))
                region_s = (region.lstrip("0") or None) if region.isdigit() else None

                if scope == "esc":
                    if region_s is None:
                        stats["esc_skipped_no_region"] += 1
                        continue
                    org_level, district_id, campus_id, campus_name = "esc", None, None, None
                else:
                    try:
                        district_id = norm_id(strip(r.get("District Number")))
                    except Exception:  # noqa: BLE001
                        stats["district_skipped_bad_id"] += 1
                        continue
                    if org_type == "school" and len(org_num) == 9:
                        org_level = "campus"
                        campus_id = org_num[:3] + "-" + org_num[3:6] + "-" + org_num[6:]
                        campus_name = collapse(r.get("Organization Name")) or None
                    else:
                        org_level, campus_id, campus_name = "district", None, None

                email = collapse(r.get("Email Address")) or None
                phone = collapse(r.get("Phone")) or None
                nk = hashlib.sha256("|".join([
                    district_id or "", campus_id or "", region_s or "", role, full.lower(),
                ]).encode("utf-8")).hexdigest()

                if nk in seen:
                    stats["duplicate_source_rows"] += 1
                    cur = rows[seen[nk]]
                    if not cur[10] and email:
                        cur[10] = email
                    if not cur[11] and phone:
                        cur[11] = phone
                    continue

                seen[nk] = len(rows)
                rows.append([org_level, district_id or "", region_s or "", campus_id or "",
                             campus_name or "", full, first or "", last or "", role, code,
                             email or "", phone or "", nk, scope])
                stats[f"{scope}_emitted"] += 1
                role_code_counts[code] += 1

    files = []
    for n, start in enumerate(range(0, len(rows), max_rows), 1):
        fp = out_dir / f"askted_contacts_{n:02d}.csv"
        with fp.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLS)
            w.writerows(rows[start:start + max_rows])
        files.append({"file": str(fp), "rows": min(max_rows, len(rows) - start),
                      "mb": round(fp.stat().st_size / 1_048_576, 2)})

    print(json.dumps({"total_rows": len(rows), "stats": dict(stats),
                      "role_code_counts": dict(role_code_counts.most_common()),
                      "unmapped_roles": dict(unmapped), "files": files,
                      "out_dir": str(out_dir)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
