# Confluence pages published 2026-08-21

Confluence is the **source of record** for these. This directory deliberately does not
duplicate their bodies — the Book Intelligence area's governance rule is *"one live copy of
any spec, ever. A spec that exists in both places is a spec that will disagree with itself."*
Only `01-13tac-4.2.md` is kept locally, as the working transcription that produced the
statutory-reference page.

| Page | ID | Location | Status |
|---|---|---|---|
| Texas 13 TAC §4.2 — School Library Collection Development Standards (adopted) | `205193248` | Compliance Hub (CH) | REFERENCE, provenance-labeled |
| Evidence Severity and the "Not a Rating System" Boundary | `205520897` | PROD → 1 · Doctrine | DRAFT — awaiting CEO approval |
| Book Intelligence — Statutory Evidence Model | `205553665` | PROD → 1 · Doctrine | DRAFT — awaiting CEO approval |
| Book Intelligence — Documentation Cleanup Register | `205357059` | PROD → under BI Canonical Source of Truth | OPEN REGISTER |
| Accuracy Gate — Statutory Evidence Model, First Result | `205750273` | PROD → 4 · Evidence Quality and Measurement | DRAFT — awaiting CEO approval |

## What changed and why

Book Intelligence output is now organized around **the statutory questions a Texas district
must answer about a book** rather than around content categories. Categories are inputs; the
questions are the output. For each question the system reports what the evidence supports,
what it does not, and where the gap is — it never answers the question, and never states that
a book complies with or violates a statute or a district policy.

Three findings drove the restructure:

1. **13 TAC §4.2(d) prescribes an evidentiary method** requiring at least two of five listed
   evaluation methods. Prong 5 names professional review journals — already our top admissible
   source tier. Prongs 1, 2, 4 and 5 need no access to the book's text, which narrows the
   "we can't read the manuscript" limitation considerably.
2. **HB 900's vendor-rating machinery is enjoined**, yet both district policy binders still
   carry the vendor-rating prohibition. The statute points at a rating no vendor must produce.
   Texas has no functioning content-rating mechanism and districts must act as if one exists.
3. **Prevalence is per-question, not global.** "As a whole" is statutory for harmful material
   and obscenity, arrives via *Parent v. Lovejoy* for pervasively vulgar / educationally
   unsuitable, and is absent for indecent and profane content.

## Gate before any customer-facing compliance claim

CEO decision, 2026-08-21: no compliance-grade claim reaches a customer before a measured
precision figure exists, published **per question** (a blended number would hide the
prevalence asymmetry that matters most).

**Result: the gate cannot be satisfied as specified.** The reference gold-standard harness
grades whether a citation substantiates a ban or challenge *event*. It has no content-type
axis and no passage-level citations, so it scores the known-list flag layer but cannot score
the per-statutory-question content evidence — the half that makes a claim about what is
inside a book, and the half that most needs gating. Full result, including the one real
defect it did surface and what building the missing ground truth requires:
`../accuracy-gate-2026-08-21.md` and page `205750273`.
