#!/usr/bin/env python3
"""Render the statutory model's evidence as a specific district's requested view.

Demonstrates the projection principle from the Statutory Evidence Model spec
(Confluence 205553665): the evidence layer is shared; the *view* is per-district.
This renders the state-floor profile in the four categories one design-partner
district asked for, drawn from the same underlying evidence records.

Her four asks map onto the model like this:
  "sexually explicit content"  -> Q1 harmful material + Q2 indecent content (sexual)
  "obscenity"                  -> Q2 indecent + Q3 profane + Q4 patently vulgar
  "nudity"                     -> DISTRICT dimension (no Texas statutory hook)
  "extreme violence"           -> DISTRICT dimension (no Texas statutory hook)

The last two are labeled as district criteria, not statutory gates, because
neither term appears in Texas statute, the Education Code, or 13 TAC 4.2.
"""
import json
from pathlib import Path

from citation_stability import annotate

SRC = Path(__file__).parent / "sample-results"
RUN_DATE = "2026-08-20"

# her category -> (source fields in the evidence record, layer)
VIEW = [
    ("Sexually explicit", ["sexually_explicit"], "statutory"),
    ("Obscenity", ["indecent_content", "profane_content", "patently_vulgar"], "statutory"),
    ("Nudity", ["sustained_nudity"], "district"),
    ("Extreme violence", ["extreme_violence"], "district"),
]
RANK = {"RED": 3, "YELLOW": 2, "NO_EVIDENCE_FOUND": 1}
GLYPH = {"RED": "●", "YELLOW": "◐", "NO_EVIDENCE_FOUND": "—"}


def roll_up(book, fields):
    """Worst-case across the contributing fields, with the contributors named."""
    best, contributors = "NO_EVIDENCE_FOUND", []
    for f in fields:
        c = book["categories"].get(f)
        if not c:
            continue
        if RANK[c["verdict"]] > RANK[best]:
            best = c["verdict"]
        if c["verdict"] != "NO_EVIDENCE_FOUND":
            contributors.append((f, c))
    return best, contributors


def main():
    books = [json.loads(f.read_text()) for f in sorted(SRC.glob("*.json"))]
    rows, detail = [], []

    for b in books:
        cells, any_evidence = [], False
        for label, fields, layer in VIEW:
            verdict, contributors = roll_up(b, fields)
            cells.append(GLYPH[verdict])
            if contributors:
                any_evidence = True
                for fname, c in contributors:
                    srcs = "; ".join(
                        f"[{s['name']}]({s['url']})"
                        f"{annotate(s['url'], s.get('date_or_year', ''))}"
                        for s in c.get("sources", [])[:3]
                    )
                    detail.append(
                        f"- **{b['book']['title']}** · {label} "
                        f"({'statutory gate' if layer == 'statutory' else 'district criterion'}) "
                        f"— {GLYPH[c['verdict']]} {c['verdict']}\n"
                        f"  {c['findings'][:400]}\n"
                        f"  Sources: {srcs or 'see full record'}"
                    )
        nflags = len(b["known_list_flags"])
        rows.append(
            "| "
            + " | ".join(
                [
                    f"**{b['book']['title']}**",
                    b["book"]["author"],
                    *cells,
                    f"{nflags}" if nflags else "—",
                    "Look closer" if any_evidence else "No evidence found",
                ]
            )
            + " |"
        )

    hdr = ["Title", "Author"] + [v[0] for v in VIEW] + ["Known lists", "Priority"]
    out = [
        "# Book list evidence review — district view",
        "",
        "**AI generated and unverified.** Confirm findings against the cited sources "
        "before acting. This report surfaces evidence; it does not determine whether a "
        "book complies with, or violates, any statute or district policy — that "
        "determination belongs to the district.",
        "",
        f"Run date: {RUN_DATE} · {len(books)} titles · full list, no batching",
        "",
        "Legend: ● evidence found · ◐ partial or implied · — no content evidence found "
        f"in sources reviewed as of {RUN_DATE}. An em dash is a statement about the "
        "sources reviewed, not a rating of the book.",
        "",
        "**Sexually explicit** and **Obscenity** are Texas statutory gates. "
        "**Nudity** and **Extreme violence** are district criteria — neither term "
        "appears in Texas statute, the Education Code, or 13 TAC §4.2, so they are "
        "reported as this district's own criteria rather than as state requirements.",
        "",
        "## What this chart is measured to support",
        "",
        "Calibrated to the accuracy gate run on 2026-08-21 "
        "(`accuracy-gate-2026-08-21.md`), so the chart carries only claims that "
        "have a measurement behind them.",
        "",
        "**Measured.** The known-list layer — whether a flag's citation holds up. "
        "On the sample set, scored against an independent citation-credibility "
        "rubric: zero award or booklist pages cited as ban evidence, zero "
        "junk-tier or retail sources, a date on 91% of flags and a jurisdiction "
        "on 51%. Ten titles and 35 flags, so those are proportions of a small "
        "sample, not rates.",
        "",
        "**Not measured.** The accuracy of the content evidence itself, per "
        "statutory question. No adjudicated ground truth for that exists yet, so "
        "no accuracy claim is made about the ● ◐ — marks in the four columns "
        "above. Read them as what the cited sources say, and check the sources.",
        "",
        "**Known defect, marked inline.** Some citations point at a rotating "
        f"index whose contents are replaced each cycle, so a claim about a "
        "specific past year may land on a page that no longer shows it. Those "
        "carry a repointing note beside the link. The claims are documented "
        "elsewhere; the citations need repointing to dated or archived pages "
        "before this chart goes to a board.",
        "",
        "| " + " | ".join(hdr) + " |",
        "|" + "---|" * len(hdr),
        *rows,
        "",
        "## What the evidence says",
        "",
        *detail,
    ]
    dest = Path(__file__).parent / f"district-view-{RUN_DATE}.md"
    dest.write_text("\n".join(out) + "\n")
    print(f"wrote {dest} ({len(books)} titles, {len(detail)} evidence findings)")


if __name__ == "__main__":
    main()
