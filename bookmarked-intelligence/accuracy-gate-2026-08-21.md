# Accuracy Gate — Result (2026-08-21)

**Status: the gate cannot be satisfied as specified.** The reference gold-standard
harness measures the wrong thing for half of what needs gating. What it *can*
measure produced one real, actionable defect in the sample run.

Run artifacts: `accuracy-gate.py` (the checks), `accuracy-gate-2026-08-21.txt`
(raw output), `sample-results/*.json` (the run under test). The fix for the one
defect found is landed in `qc-sweep.py` as check 7, which now hard-fails the
three affected flags.

---

## The finding that changes the gate

The gate was specified as: run the statutory evidence model against the
reference district's verified per-title audit and publish per-question
precision and recall.

That audit is a **citation-credibility harness, not a content-accuracy
harness.** Every one of its 126 verdicts answers one question — *does this
citation substantiate a ban or challenge event?* Its failure taxonomy is
entirely about citation genre, source tier, URL stability, aboutness, and
jurisdiction. There is no content-type axis anywhere in it, and no
passage-level citation.

So it can score the **known-list flag layer**. It cannot score the
**per-statutory-question content evidence** — which is precisely the new
capability that most needs gating, because it is the half that makes a claim
about what is inside a book.

That gap is not an oversight in the harness. It follows from the product's own
doctrine: the system operates on publicly available information *about* books
and never reads book text. Nothing in the existing evidence base was ever
built to answer "does this book contain indecent content under Texas Education
Code §33.020(2)."

---

## Channel 1 — known-list flag citation quality (measured)

35 flags across the 10 sampled titles, scored against the reference audit's
own failure taxonomy. Baseline column is that audit's production numbers
(109 flags on 126 titles).

| Check | This run | Production baseline |
|---|---|---|
| **Known-A** — award / booklist / ethics page cited as ban evidence | 0/35 (0.0%) | 6/109 (5.5%) |
| **Known-B** — live/rotating URL cited for a dated claim | **3/35 (8.6%)** | 7/109 (6.4%) |
| **New-1/2/6** — junk-tier, retail/merchandising, tertiary-only | 0/35 (0.0%) | ~55/109 (~50%) |
| **New-3** — display / LibGuide / catalog genre | 1/35 (2.9%) | folded into the ~55 above |
| Claim carries a date | 32/35 (91.4%) | not measured |
| Claim carries a jurisdiction or place | 18/35 (51.4%) | not measured |
| Carries Texas-specific evidence | 3/35 (8.6%) | ~3/109 (~3%) |
| Advocacy rating site (labelled, see divergence below) | 2/35 (5.7%) | tier-capped by the rubric |

### The one real failure

Three flags cite the **live rotating ALA top-10 index** for appearances in
specific past years:

- *To Kill a Mockingbird* — claim asserts 2011, 2017, and the 2010–2019 decade list
- *Looking for Alaska* — claim asserts 2012, 2013, 2015
- *The Absolutely True Diary of a Part-Time Indian* — claim asserts 2010–2014, 2017, 2018, 2020, 2022

The reference audit independently verified that this page does **not** today
contain *To Kill a Mockingbird*. The underlying claims are well documented; the
**citations are false as of the run date**. A librarian who clicks through in
front of a board finds a page that does not mention the book.

This run therefore **reproduced the Known-B defect at a slightly higher rate
than production** (8.6% vs 6.4%), on a curated sample where it should have done
better.

**Root cause — a real spec gap.** Both v1.0 and the statutory evidence model
rule on *source admissibility* (which domains and genres are allowed). Neither
has a **citation-stability rule**. Admissibility asks "is this a credible kind
of source"; stability asks "will the cited page still contain this claim
tomorrow." A rotating index passes the first and fails the second.

**Fix (mechanically checkable, no judgment call).** Any flag asserting a dated
appearance must cite a page whose URL is anchored to that year or decade, or an
archive snapshot with a retrieval date. Add the check to `qc-sweep.py` so it
fails the sweep rather than surviving to a report. The reference audit reached
the same conclusion independently — its fix list item 5 is "archive-on-flag with
retrieval dates; live URLs repointed to dated archives."

### One divergence in standard, recorded not hidden

Two flags cite advocacy rating sites (a BookLooks-lineage page; an advocacy
chapter list). The reference rubric caps such sources at a low authority tier.
The spec admits them **as labelled advocacy artifacts**, because they are the
lists districts are actually handed and a district asking "why is this book on
the list someone gave me" needs to see the artifact itself. That is a
deliberate divergence, not a defect — but it is a divergence, and any number
computed against the rubric should say so.

### Overlap with the audited set

5 of the 10 sampled titles appear in the audited 126.

| Title | Audit verdict on the *production* flag | This run |
|---|---|---|
| *Because of Winn-Dixie* | **Confirmed false positive** — award page cited as ban evidence | 1 flag, 0 mechanical failures; cites a static decade-retrospective page |
| *To Kill a Mockingbird* | Legitimate, citation repair needed (rotating URL) | 2 flags, **1 mechanical failure — same defect**; adds a Texas district row |
| *The Hunger Games* | Legitimate, minor repair | 1 flag, 0 mechanical failures |
| *The Perks of Being a Wallflower* | Legitimate but under-cited | 7 flags, 0 mechanical failures; three jurisdiction-specific rows |
| *The Absolutely True Diary of a Part-Time Indian* | **Catastrophic silent false negative** (customer typo defeated exact match) | 2 flags found, **1 mechanical failure** |

---

## What could not be measured

**1. Aboutness — does the cited page actually name this title?** Network egress
to publisher and association domains is blocked from the run environment, so
not one cited page could be opened and read. The reference audit graded from
URL, domain, and path alone for the same reason and recorded it as its own gap
(note b). The comparison above is therefore apples-to-apples — and **neither
run has an aboutness measurement**. This matters: the audit's single most
instructive false positive was a right-domain, right-path, wrong-everything-else
citation that only an aboutness check catches.

**2. Content-evidence accuracy, Q1 through Q7.** No ground truth exists. This
is the gap that blocks the gate.

**3. Recall — false negatives.** This run found evidence for the title that was
the audit's catastrophic silent miss. **That is not a fix.** The run was handed
the correct title; the defect was entity resolution against a customer typo, and
nothing here exercises fuzzy matching. The audit's own honest note stands: the
rubric has no false-negative test.

### One caveat on the numbers that must travel with them

The spec's source-admissibility rules were themselves drawn in part from this
audit's failure classes, and `qc-sweep.py` enforces them. The 0.0% on Known-A
and on junk-tier sourcing is therefore best read as **confirmation that the rule
is enforced**, not as independent validation that the rule is correct. The
Known-B result is different in kind and is the load-bearing finding: it is a
mechanical property of the URL the run emitted, it was not a rule the spec had,
and it failed.

Sample size is 10 titles and 35 flags. Percentages are stated because the
denominators are stated; they are not rates.

---

## What building the missing ground truth requires

To produce a defensible per-question precision figure for Q1–Q7:

1. **Stratified sample** — known-challenged titles, award winners, ordinary
   midlist, picture books, and pre-publication titles. Tier 4 doctrine already
   calls for hundreds of titles, not dozens.
2. **Per-question labels**, not one blended verdict. Prevalence rules differ per
   question — "as a whole" is statutory for harmful and obscene, precedential for
   pervasively vulgar, and **absent** for indecent and profane content — so a
   blended number hides the asymmetry that matters most.
3. **Two independent adjudicators** per title-question with a documented
   disagreement-resolution rule, so the labels are not one person's reading.
4. **A held-out split** the fix process never sees.
5. **A recall check** against known most-challenged lists, closing the
   false-negative gap the rubric admits it has.

Without a source of book text, prongs answerable from professional reviews,
award lists, and district records are gradeable; anything requiring the
manuscript is not.

---

## Recommendation

**Scope the customer-facing claim to what is measured, and fix the citation-
stability gap before anything ships.** Concretely:

- **Landed.** `qc-sweep.py` check 7 now hard-fails a dated claim that cites a
  rotating index. The sweep consequently reports **3 hard fails on the committed
  sample set** — that is the gate working, not a regression. Repointing those
  three citations to year-anchored or archived pages needs a machine that can
  open the replacement page to confirm it carries the claim; egress is blocked
  here, so the repoint is a named open item rather than a guess.
- What can be said today, with receipts: the known-list layer cites zero award
  pages, zero junk-tier sources, carries a date on 91% of flags and a
  jurisdiction on 51%, and surfaces Texas-specific evidence at roughly three
  times the production rate on this sample.
- What cannot be said today: anything measured about the accuracy of the
  content evidence per statutory question. Under the standing decision that
  accuracy is measured before any compliance claim reaches a customer, that
  half stays unclaimed until the benchmark above exists.

This is narrower than it sounds. The product already never states a compliance
conclusion — there is no legal review, so it reports evidence against the
criteria a district itself defined and never says a book complies with or
violates anything. The claim that actually needs gating is not "compliant" but
**"the evidence we show you is accurately cited."** Channel 1 is now measured
against that standard. Channel 2 is not.

---

*Method: mechanical scoring of emitted URLs and claim text against the reference
audit's failure taxonomy (`accuracy-gate.py`); overlap cross-reference against
the audited per-title set. No cited page was opened — egress blocked. Reference
audit and its rubric are the independent standard: both were drafted before
contact with this run's output.*
