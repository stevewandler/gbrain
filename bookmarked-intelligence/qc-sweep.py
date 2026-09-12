#!/usr/bin/env python3
"""Compliance sweep for content-evidence sample results (spec §5).

Checks every JSON in sample-results/:
  1. No blocklisted (UGC/retailer/CSM) domain appears in any cited source URL.
  2. Every NO_EVIDENCE_FOUND category carries the exact no-evidence string.
  3. Verdicts are valid enum values; review_priority valid.
  4. Provenance block present with exact disclaimer.
  5. Advisory: rating-language words (safe/clean/low risk) in findings/synopsis.
  6. Advisory: RED verdicts on sexually_explicit with <2 admissible sources.
  7. Citation stability: nothing asserting a dated appearance may cite a live
     rotating index — known-list flags and category sources alike.
     Rule lives in citation_stability.py; added 2026-08-21
     after the accuracy gate found three such flags in the sample set (see
     accuracy-gate-2026-08-21.md).
"""
import json, re, sys
from pathlib import Path

from citation_stability import is_unstable

BLOCKLIST = [
    "facebook.com", "reddit.com", "quora.com", "twitter.com", "/x.com", "instagram.com",
    "tiktok.com", "medium.com", "change.org", "youtube.com", "goodreads.com",
    "thestorygraph.com", "amazon.", "barnesandnoble.com", "abebooks.com", "ebay.",
    "pangobooks.com", "commonsensemedia.org", "grokipedia",
]
NO_EV = "No content evidence found in sources reviewed as of "
DISCLAIMER = "This summary is AI generated and unverified. Confirm findings against the cited sources before acting."
VERDICTS = {"RED", "YELLOW", "NO_EVIDENCE_FOUND"}
PRIORITIES = {"LOOK_CLOSER", "NO_ACTION_INDICATED"}
RATING_WORDS = re.compile(r"\b(safe|clean|low[- ]risk)\b", re.I)

fails, advisories = [], []
results_dir = Path(__file__).parent / "sample-results"
files = sorted(results_dir.glob("*.json"))
for f in files:
    d = json.loads(f.read_text())
    name = f.name
    urls = [s.get("url", "") for c in d["categories"].values() for s in c.get("sources", [])]
    urls += [k.get("url", "") for k in d.get("known_list_flags", [])]
    for u in urls:
        for b in BLOCKLIST:
            if b in u.lower():
                fails.append(f"{name}: BLOCKLISTED source URL ({b}): {u}")
    for cat, c in d["categories"].items():
        if c["verdict"] not in VERDICTS:
            fails.append(f"{name}: {cat} invalid verdict {c['verdict']}")
        if c["verdict"] == "NO_EVIDENCE_FOUND":
            if not c["findings"].startswith(NO_EV):
                fails.append(f"{name}: {cat} no-evidence string mismatch: {c['findings'][:60]!r}")
            if c.get("sources"):
                fails.append(f"{name}: {cat} NO_EVIDENCE_FOUND but has sources")
        if c["verdict"] in ("RED", "YELLOW") and not c.get("sources"):
            fails.append(f"{name}: {cat} {c['verdict']} with zero sources")
    for k in d.get("known_list_flags", []):
        if is_unstable(k.get("url", ""), k.get("claim", "")):
            fails.append(f"{name}: UNSTABLE CITATION (known-list flag) — dated "
                         f"claim cites a rotating index: {k.get('url', '')}")
    for cat, c in d["categories"].items():
        for s_ in c.get("sources", []):
            if is_unstable(s_.get("url", ""), s_.get("date_or_year", "")):
                fails.append(f"{name}: UNSTABLE CITATION ({cat}) — dated source "
                             f"cites a rotating index: {s_.get('url', '')}")
    if d.get("review_priority") not in PRIORITIES:
        fails.append(f"{name}: invalid review_priority {d.get('review_priority')}")
    if d.get("provenance", {}).get("disclaimer") != DISCLAIMER:
        fails.append(f"{name}: disclaimer mismatch")
    se = d["categories"]["sexually_explicit"]
    if se["verdict"] == "RED" and len(se.get("sources", [])) < 2:
        advisories.append(f"{name}: RED sexually_explicit with <2 sources")
    for field, text in [("synopsis", d.get("synopsis", ""))] + [
        (f"{cat}.findings", c.get("findings", "")) for cat, c in d["categories"].items()
    ]:
        for m in RATING_WORDS.finditer(text):
            advisories.append(f"{name}: rating-language {m.group(0)!r} in {field} (check context)")

print(f"files checked: {len(files)}")
print(f"HARD FAILS: {len(fails)}")
for x in fails: print("  ✗", x)
print(f"advisories: {len(advisories)}")
for x in advisories: print("  ⚠", x)
sys.exit(1 if fails else 0)
