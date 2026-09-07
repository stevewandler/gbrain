#!/usr/bin/env python3
"""Confirm every district_id in the import CSV exists in Supabase `districts`.

Read-only. The promote statement FILTERS unmatched rows rather than aborting, so
without this check a whole district's staff could be silently dropped. Run it
BEFORE importing.

`districts_snapshot.txt` is a comma-separated snapshot of district_id pulled from
the live table; refresh it whenever `districts` changes.

Measured 2026-08-26: 1,216 CSV districts all resolve against 1,219 live; zero
rows at risk. The 3 live districts with no AskTED personnel are 130-801, 220-814
and 246-802 — the same frozen-only ids the 2026-08-21 audit named.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

CSV_PATH = Path(sys.argv[1] if len(sys.argv) > 1
                else "/Users/stevewandler/Documents/askted-import/askted_contacts_01.csv")
IDS_PATH = Path(__file__).parent / "districts_snapshot.txt"


def main() -> int:
    live = {x.strip() for x in IDS_PATH.read_text().split(",") if x.strip()}
    in_csv, rows_by_district = set(), {}
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        for d in csv.DictReader(fh):
            did = d["district_id"].strip()
            if did:
                in_csv.add(did)
                rows_by_district[did] = rows_by_district.get(did, 0) + 1

    missing = sorted(in_csv - live)
    print(json.dumps({
        "live_districts": len(live),
        "districts_in_csv": len(in_csv),
        "csv_ids_missing_from_districts": missing,
        "rows_that_would_be_rejected": sum(rows_by_district.get(d, 0) for d in missing),
        "districts_with_no_askted_personnel": sorted(live - in_csv),
        "VERDICT": "PASS — every CSV district resolves" if not missing
                   else "FAIL — rows would be rejected",
    }, indent=1))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
