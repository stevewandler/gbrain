#!/usr/bin/env python3
"""Compliance sweep for content-evidence sample results (spec §5).

Checks every JSON in sample-results/:
  1. No blocklisted (UGC/retailer/CSM) domain appears in any cited source URL.
  2. Every NO_EVIDENCE_FOUND category carries the exact no-evidence string.
  3. Verdicts are valid enum values; review_priority valid.
  4. Provenance block present with exact disclaimer.
  5. Advisory: rating-language words (safe/clean/low risk) in findings/synopsis.
  6. Advisory: RED verdicts on sexually_explicit with <2 admissible sources.
  7. Citation stability: a flag asserting a dated appearance may not cite a
     live rotating index. Admissibility asks whether a source is a credible
     kind of source; stability asks whether the cited page will still contain
     the claim tomorrow. A rotating "current top ten" index passes the first
     and fails the second — the claim stays true while the citation goes false,
     which is the worst failure mode for a citation read aloud at a board
     meeting. Added 2026-08-21 after the accuracy gate found three such flags
     in the sample set; see accuracy-gate-2026-08-21.md.
"""
import json, re, sys
from pathlib import Path

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
# Rotating indexes: pages whose contents are replaced each cycle.
ROTATING_INDEX = re.compile(
    r"/(top10|topten|top-10|frequentlychallengedbooks/?$|banned-?books-?week/?$)", re.I)
# Anchors that pin a page to a fixed edition: an explicit year, a decade
# retrospective, or an archive snapshot.
STABLE_ANCHOR = re.compile(r"(19|20)\d\d|decade|web\.archive\.org", re.I)
DATED_CLAIM = re.compile(r"\b(19|20)\d\d\b")

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
        u = k.get("url", "")
        path = u.split("://", 1)[-1].split("/", 1)[-1] if "://" in u else u
        if (ROTATING_INDEX.search(u) and not STABLE_ANCHOR.search(path)
                and DATED_CLAIM.search(k.get("claim", ""))):
            fails.append(
                f"{name}: UNSTABLE CITATION — dated claim cites a rotating index: {u}")
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
