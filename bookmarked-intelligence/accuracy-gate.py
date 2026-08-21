#!/usr/bin/env python3
"""Accuracy gate: score the sample run's known-list flags against the reference
district flag audit's failure taxonomy.

Scope note, load-bearing. The reference audit (Confluence 181403776) grades
whether a citation substantiates a ban/challenge EVENT. It has no content-type
axis and no passage-level citations, so it cannot score the per-statutory-
question content evidence the model now produces. This script therefore
measures Channel 1 (known-list flags) only. Channel 2 (content evidence per
statutory question) has no ground truth; see the companion write-up.

Every check here is mechanical — derived from the emitted URL and claim text,
never from opening the cited page. The reference audit graded the same way
(its own gap note (b)), so the comparison is apples-to-apples. Neither run
has an aboutness measurement.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from citation_stability import is_unstable

HERE = Path(__file__).parent

# --- reference-audit baseline (Confluence 181403776, 109 flags on 126 titles) ---
BASELINE = {
    "known_a": (6, 109),      # ALA award / booklist / ethics page as ban evidence
    "known_b": (7, 109),      # live / rotating URL cited for a dated claim
    "junk_tier": (55, 109),   # New-1/2/6 junk, retail, tertiary-only
    "new_3": (None, 109),      # display / LibGuide / catalog genre misread (folded into ~55 above)
    "texas": (3, 109),        # carries Texas-specific evidence (audit: 2-3, ~3%)
}

# --- mechanical checks ---
ROTATING = re.compile(r"/(top10|topten|top-10|frequentlychallengedbooks/?$|banned-?books-?week/?$)", re.I)
YEAR_ANCHOR = re.compile(r"(19|20)\d\d|decade|archive|web\.archive\.org")
AWARD = re.compile(r"(newbery|caldecott|printz|award|notable|best-?books|yalsa|alsc|ethics|press-?release)", re.I)
JUNK = re.compile(
    r"(wikipedia|britannica|grokipedia|enotes|sparknotes|studylib|scribd|quora|reddit"
    r"|instagram|facebook|tiktok|x\.com|twitter|goodreads|storygraph|amazon|barnesandnoble"
    r"|abebooks|thriftbooks|blogspot|wordpress\.com|substack|medium\.com|commonsensemedia)", re.I)
NEW_3 = re.compile(r"(libguides?|libguide|/catalog/|banned-?books-?week)", re.I)
# Advocacy rating sites. The reference rubric caps these at a low authority tier;
# the spec admits them as labelled advocacy artifacts because they are the lists
# districts are actually handed. Reported as a divergence in standard, not a fail.
ADVOCACY = re.compile(r"(booklooks|ratedbooks|momsforliberty|momsforamerica|takebacktheclassroom)", re.I)
DATE = re.compile(r"\b(19|20)\d\d\b")
PLACE = re.compile(r"\b(national|statewide|county|district|ISD|Florida|Texas|Utah|South Carolina|U\.S\.)\b", re.I)
TEXAS = re.compile(r"\btexas\b|\bISD\b", re.I)

# Titles present in BOTH the sample run and the reference audit, with the audit's
# verdict on the DISTRICT'S PRODUCTION flag for that title (not on ours).
OVERLAP = {
    "Because of Winn-Dixie": ("CONFIRMED FALSE POSITIVE",
        "production flag cited an ALA Newbery Honor award page as ban evidence (Known-A)"),
    "To Kill a Mockingbird": ("LEGITIMATE — citation repair needed",
        "claim iron-clad; production flag cited the live rotating top-10 URL (Known-B)"),
    "The Hunger Games": ("LEGITIMATE — minor repair",
        "ALA Top 10 2010/2011/2013 documented; upgrade citation to the static decade list"),
    "The Perks of Being a Wallflower": ("LEGITIMATE — under-cited",
        "verified #2 on the ALA 2025 list; production flag cited less than the record supports"),
    "The Absolutely True Diary of a Part-Time Indian": ("CATASTROPHIC SILENT FALSE NEGATIVE",
        "customer typo defeated exact-match lookup; the most ban-relevant title on the list returned no data"),
}


def load_flags():
    out = []
    for f in sorted((HERE / "sample-results").glob("*.json")):
        b = json.loads(f.read_text())
        for k in b["known_list_flags"]:
            path = urlparse(k["url"]).path
            text = f"{k['scope']} {k['claim']}"
            out.append({
                "title": b["book"]["title"],
                "list": k["list"],
                "url": k["url"],
                "scope": k["scope"],
                "claim": k["claim"],
                "known_a": bool(AWARD.search(path)),
                "known_b": is_unstable(k["url"], k["claim"]),
                "junk_tier": bool(JUNK.search(k["url"])),
                "new_3": bool(NEW_3.search(k["url"])),
                "advocacy": bool(ADVOCACY.search(k["url"])),
                "has_date": bool(DATE.search(text)),
                "has_place": bool(PLACE.search(k["scope"])),
                "texas": bool(TEXAS.search(text)),
            })
    return out


def rate(n, total):
    return f"{n}/{total} ({100 * n / total:.1f}%)" if total else "n/a"


def main():
    flags = load_flags()
    titles = sorted({f["title"] for f in flags})
    n = len(flags)
    hits = {k: sum(f[k] for f in flags) for k in
            ("known_a", "known_b", "junk_tier", "new_3", "advocacy",
             "has_date", "has_place", "texas")}

    print("=" * 74)
    print("CHANNEL 1 — known-list flag citation quality")
    sampled = len(list((HERE / "sample-results").glob("*.json")))
    print(f"{n} flags; {len(titles)} of {sampled} sampled titles carry at least one flag")
    print("=" * 74)
    rows = [
        ("Known-A  award/booklist/ethics page as ban evidence", "known_a", "lower is better"),
        ("Known-B  live/rotating URL cited for a dated claim ", "known_b", "lower is better"),
        ("New-1/2/6  junk-tier / retail / tertiary-only      ", "junk_tier", "lower is better"),
        ("New-3    display / LibGuide / catalog genre       ", "new_3", "lower is better"),
    ]
    print(f"{'check':<52}{'this run':>14}{'baseline':>16}")
    for label, key, _ in rows:
        b_n, b_d = BASELINE[key]
        base = rate(b_n, b_d) if b_n is not None else "folded into ^"
        print(f"{label:<52}{rate(hits[key], n):>14}{base:>16}")
    print()
    print(f"{'Claim carries a date':<52}{rate(hits['has_date'], n):>14}{'not measured':>16}")
    print(f"{'Claim carries a jurisdiction / place':<52}{rate(hits['has_place'], n):>14}{'not measured':>16}")
    b_n, b_d = BASELINE["texas"]
    print(f"{'Carries Texas-specific evidence':<52}{rate(hits['texas'], n):>14}{rate(b_n, b_d):>16}")

    print()
    print(f"{'Advocacy rating site (labelled, not a fail)':<52}"
          f"{rate(hits['advocacy'], n):>14}{'tier-capped':>16}")

    # The same defect in the content-evidence layer. Not part of the Channel 1
    # rate above (different denominator) but part of the honest total.
    cat_unstable = []
    for path in sorted((HERE / "sample-results").glob("*.json")):
        d = json.loads(path.read_text())
        for cat, c in d["categories"].items():
            for src in c.get("sources", []):
                if is_unstable(src.get("url", ""), src.get("date_or_year", "")):
                    cat_unstable.append((d["book"]["title"], cat, src["url"]))

    fails = [f for f in flags
             if f["known_b"] or f["known_a"] or f["junk_tier"] or f["new_3"]]
    print()
    print("-" * 74)
    print(f"FLAGS FAILING A MECHANICAL CHECK: {len(fails)}")
    print("-" * 74)
    for f in fails:
        which = ", ".join(k for k in ("known_a", "known_b", "junk_tier", "new_3") if f[k])
        print(f"  [{which}] {f['title']}")
        print(f"    {f['url']}")
        print(f"    claim: {f['claim'][:120]}")

    print()
    print("-" * 74)
    print(f"SAME DEFECT IN THE CONTENT-EVIDENCE LAYER: {len(cat_unstable)} sources")
    print("-" * 74)
    for title, cat, url in cat_unstable:
        print(f"  {title} / {cat}")
        print(f"    {url}")

    print()
    print("-" * 74)
    print("OVERLAP WITH THE REFERENCE AUDIT")
    print("-" * 74)
    present = [t for t in titles if t in OVERLAP]
    print(f"  {len(present)} of {len(titles)} sampled titles appear in the audited set\n")
    for t in present:
        verdict, why = OVERLAP[t]
        ours = [f for f in flags if f["title"] == t]
        bad = [f for f in ours
               if f["known_a"] or f["known_b"] or f["junk_tier"] or f["new_3"]]
        print(f"  {t}")
        print(f"    audit verdict on the production flag: {verdict}")
        print(f"      {why}")
        print(f"    this run: {len(ours)} flag(s), {len(bad)} failing a mechanical check")
    absent = [t for t in titles if t not in OVERLAP]
    print(f"\n  Not in the audited set ({len(absent)}): {', '.join(absent)}")

    print()
    print("=" * 74)
    print("CHANNEL 2 — content evidence per statutory question")
    print("=" * 74)
    print("  NOT MEASURABLE. The reference audit's 126 verdicts all answer")
    print("  'does this citation substantiate a ban/challenge event.' None answers")
    print("  'does this book contain indecent content under TEC 33.020(2).'")
    print("  No ground truth exists for Q1-Q7. See the write-up for what building")
    print("  one requires.")
    print()
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
