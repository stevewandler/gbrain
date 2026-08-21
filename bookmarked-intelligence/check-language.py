#!/usr/bin/env python3
"""Language-rule check for district-facing output.

Enforces the no-conclusion rule from the Statutory Evidence Model (Confluence
205553665) and the severity doctrine note (205520897): output may characterize
EVIDENCE, but must never assert that a book complies with or violates a statute
or policy, must never recommend keeping/removing, and must never render an
absence of evidence as safe/clean/clear/low-risk.

Assertive patterns only. A disclaimer that DENIES making a determination
("does not determine whether a book complies with...") is correct usage and
must not trip the check — the earlier naive grep flagged exactly that.

Scope limit, stated so nobody mistakes this for a proof: it is a drift guard,
not a verifier. It catches the phrasings we know go wrong. A determined writer
can still smuggle a conclusion past it, and a contrived negation ("we can't
stress enough that the book violates...") reads as a disclaimer to it. Human
review of customer-facing copy is still the control; this is the backstop that
keeps the common failures from surviving to a report.
"""
import re
import sys
from pathlib import Path

# Assertive conclusion: a subject followed by a verdict verb, not negated.
ASSERTIVE = [
    (r"\b(?:this |the )?book (?:complies with|violates|is in violation of)\b",
     "asserts a compliance conclusion about a book"),
    (r"\b(?:we|bookmarked) (?:recommend|advise) (?:removing|removal|keeping|retaining|restricting)\b",
     "renders a keep/remove recommendation"),
    (r"\b(?:should be|must be) (?:removed|banned|restricted|pulled)\b",
     "renders a removal recommendation"),
    (r"\b(?:this book is|the book is|title is) (?:safe|clean|clear|appropriate|unobjectionable)\b",
     "renders absence of evidence as a safety judgment"),
    (r"\blow[- ]risk\b(?!.*never)", "uses risk-rating language"),
    (r"\brisk (?:score|rating|level)\b", "uses rating language for evidence"),
]
# Contexts where the words legitimately appear because they are being disclaimed.
# Contractions are included deliberately: a disclaimer written naturally ("we
# can't tell you a book violates the law") is still a disclaimer, and excluding
# them made the guard fire on correct copy. [’'] covers both apostrophe forms —
# markdown authored in an editor gets the typographic one.
NEGATING = re.compile(
    r"("
    r"does not|do not|never|not a|cannot|must not|does no|is not|"
    r"can[’']t|won[’']t|don[’']t|doesn[’']t|isn[’']t|aren[’']t|"
    r"couldn[’']t|wouldn[’']t|shouldn[’']t|nobody|no one"
    r")\b[^.]{0,120}$",
    re.I,
)

def check(path: Path):
    findings = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        for pat, why in ASSERTIVE:
            for m in re.finditer(pat, line, re.I):
                before = line[: m.start()]
                if NEGATING.search(before):
                    continue  # the phrase is being disclaimed, not asserted
                findings.append((i, why, line.strip()[:130]))
    return findings

def main():
    targets = sys.argv[1:] or [
        str(p) for p in (Path(__file__).parent).glob("district-view-*.md")
    ]
    total = 0
    for t in targets:
        p = Path(t)
        if not p.exists():
            continue
        fs = check(p)
        print(f"{p.name}: {'CLEAN' if not fs else str(len(fs)) + ' violation(s)'}")
        for ln, why, txt in fs:
            print(f"  ✗ line {ln}: {why}\n    {txt}")
        total += len(fs)
    print(f"\ntotal violations: {total}")
    sys.exit(1 if total else 0)

if __name__ == "__main__":
    main()
