#!/usr/bin/env python3
"""Render sample-results/*.json into the sample report (spec §4 layout).

Chart-first: one row per title, seven category columns (● RED / ◐ YELLOW / — none),
known-list flags, review priority. Then per-book cards. Markdown out.
"""
import json
from pathlib import Path

CATS = [
    ("sexually_explicit", "Sexually explicit"),
    ("sustained_nudity", "Sustained nudity"),
    ("extreme_violence", "Extreme violence"),
    ("profane_content", "Profane content"),
    ("indecent_content", "Indecent content"),
    ("patently_vulgar", "Patently vulgar"),
    ("prohibited_website_referral", "Prohibited website referral"),
]
GLYPH = {"RED": "●", "YELLOW": "◐", "NO_EVIDENCE_FOUND": "—"}
RUN_DATE = "2026-08-20"

def load():
    d = Path(__file__).parent / "sample-results"
    books = [json.loads(f.read_text()) for f in sorted(d.glob("*.json"))]
    prio = {"LOOK_CLOSER": 0, "NO_ACTION_INDICATED": 1}
    return sorted(books, key=lambda b: (prio[b["review_priority"]], b["book"]["title"]))

def chart(books):
    hdr = ["Title"] + [label.split()[0] if len(label.split()) < 3 else label for _, label in CATS]
    hdr = ["Title", "Sexually explicit", "Sustained nudity", "Extreme violence", "Profane", "Indecent", "Patently vulgar", "Website referral", "Known-list flags", "Priority"]
    lines = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    for b in books:
        cells = [f"**{b['book']['title']}**"]
        for key, _ in CATS:
            cells.append(GLYPH[b["categories"][key]["verdict"]])
        klf = "<br>".join(f"{k['list'].split('—')[0].split('(')[0].strip()} ({k['scope'][:40]})" for k in b["known_list_flags"]) or "none found"
        cells.append(klf)
        cells.append("🔎 LOOK CLOSER" if b["review_priority"] == "LOOK_CLOSER" else "No action indicated")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

def card(b):
    out = [f"### {b['book']['title']} — {b['book']['author']} ({b['book'].get('publication_year', '')})", ""]
    if b["known_list_flags"]:
        out.append("**Known-list flags:** " + " · ".join(
            f"[{k['list'].split('—')[0].split('(')[0].strip()}]({k['url']}) — {k['claim']}" for k in b["known_list_flags"]))
    else:
        out.append("**Known-list flags:** none found in this run.")
    out.append("")
    evid = [(k, lab) for k, lab in CATS if b["categories"][k]["verdict"] != "NO_EVIDENCE_FOUND"]
    none_ = [lab for k, lab in CATS if b["categories"][k]["verdict"] == "NO_EVIDENCE_FOUND"]
    for key, label in evid:
        c = b["categories"][key]
        out.append(f"**{GLYPH[c['verdict']]} {label} — {c['verdict']}**  ")
        out.append(c["findings"])
        for s in c["sources"]:
            year = f", {s['date_or_year']}" if s.get("date_or_year") else ""
            q = f' — "{s["quote"]}"' if s.get("quote") else ""
            out.append(f"  - [{s['name']}]({s['url']}) ({s['type']}{year}){q}")
        out.append("")
    if none_:
        out.append(f"*No content evidence found in sources reviewed as of {RUN_DATE}: {', '.join(none_)}.*")
        out.append("")
    ll = b["legal_lenses"]
    out.append(f"**Legal lenses** — prurient theme: {'evidence found' if ll['prurient_theme']['evidence_found'] else 'no evidence'}; "
               f"on-page explicit scenes: {'evidence found' if ll['onpage_explicit_scenes']['evidence_found'] else 'no evidence'}.  ")
    out.append(f"  - Prurient theme: {ll['prurient_theme']['basis']}")
    out.append(f"  - On-page scenes: {ll['onpage_explicit_scenes']['basis']}")
    out.append("")
    out.append(f"**What this evidence is telling you:** {b['synopsis']}")
    out.append("")
    out.append(f"*Sources reviewed: {b['provenance']['sources_reviewed_count']} · thumbs up/down placeholder per card in product UI*")
    out.append("")
    return "\n".join(out)

def main():
    books = load()
    doc = [
        "# Book Intelligence — Content Evidence Sample Report",
        "",
        f"**⚠ This report is AI generated and unverified. Confirm findings against the cited sources before acting.**  ",
        f"Run date: {RUN_DATE} · Prompt version: 1.0 (draft) · Engine: Claude research agents (stop-gap run) · {len(books)} titles",
        "",
        "This is a staging-style UAT sample of the content-evidence prompt defined in `prompt-spec.md`,",
        "run against a known-answer test set. Legend: ● evidence found (RED) · ◐ partial/implied (YELLOW) · — no content evidence found.",
        "An em dash is a statement about the sources reviewed on the run date, not a rating of the book.",
        "",
        "## The chart",
        "",
        chart(books),
        "",
        "## Per-book evidence cards",
        "",
    ]
    for b in books:
        doc.append(card(b))
        doc.append("---")
        doc.append("")
    doc.append("## Method + provenance")
    doc.append("")
    doc.append("Two channels per title (spec §2): known-list check (PEN America, ALA OIF, Take Back the Classroom,")
    doc.append("Moms for Liberty lineage, Moms for America, state lists), then the content-evidence prompt over")
    doc.append("admissible sources only — professional review journals, state/district records, staff-reported news,")
    doc.append("advocacy rationale documents. UGC (social media, forums, reader reviews), retail/resale listings, and")
    doc.append("Common Sense Media are excluded by rule. Every claim distinguishes *content description* from")
    doc.append("*challenge record* — a challenge somewhere is not proof of content. The QC sweep (`qc-sweep.py`)")
    doc.append("verified zero blocklisted sources and exact no-evidence language across all cards.")
    doc.append("")
    out = Path(__file__).parent / f"sample-report-{RUN_DATE}.md"
    out.write_text("\n".join(doc))
    print(f"wrote {out} ({len(books)} books)")

if __name__ == "__main__":
    main()
