# Book Intelligence — Content Evidence Prompt (v1.0 DRAFT)

Spec version: 1.0-draft · Author: Steve Wandler (CEO) w/ Claude session, 2026-08-20 · Status: DRAFT — staging validation, not production
Companion: `sample-report-2026-08-20.md` (the prompt actually run on 10 test books)

> **Privacy note:** per repo policy this document uses generic references. The design-partner
> benchmark is referred to as **the Librarian Test**; the design partner is a library-services
> director at a Texas district (identity in internal CRM/Confluence, not here).

---

## 1. Why this exists

Book Intelligence today surfaces raw web-link flags. A librarian looking at a book with 144
flags, or at a bare link to an advocacy-list page, gets no answer to the only question she is
asking: **"Is this book going to cause me a problem?"** Districts are already getting that
answer by pasting title+author batches into consumer AI tools with their own prompts — in
chunks, capped by free tiers, one book at a time on drill-down. They have told us directly
that a proper prompt beats our flags.

This spec defines the prompt (and its output contract) that closes that gap. It is written
**model-agnostic** so the V3 engine rebuild can absorb it verbatim, with a runnable version
for the immediate stop-gap. The standard is *better, not perfect*: output is AI-generated,
labeled as such, and improved through a per-card thumbs up/down feedback loop.

### The Librarian Test (acceptance criteria)

Derived from the design partner's own workflow and words (2026-08-18 call):

| # | Requirement | Her words |
|---|---|---|
| T1 | Input is an uploaded spreadsheet of title+author rows; the whole list runs — no chunking | "a tool where I can do that not in chunks" |
| T2 | First output is a **chart**, one row per title, flagging problem-risk only — not literary merit | "make a chart including each…"; "is this book going to cause me a problem?" |
| T3 | Flags are grounded in the two legal tests she applies | "is there a possibility that this book violates state law?" |
| T4 | Per hit: a summary of the specific cautions **plus** the underlying reviews/excerpts — enough to make the judgment call without more searching | "what is the content that you have found… here is the reviews that are online" |
| T5 | Beats a consumer AI-search summary in specificity and sourcing, at full-list scale | "it will give me kind of a summary of what the cautions are… that's what I'm looking for" |
| T6 | A bare link to a list page is a failure | (our own admission: "it doesn't tell you anything about the book") |

Her two legal tests (T3), stated as evidence questions the output must answer:
- **Prurient-theme test** — do credible sources indicate the work as a whole appeals to
  prurient interest / that its theme solicits an interest in sex?
- **On-page-scene test** — do credible sources report detailed, on-the-page explicit scenes
  (as opposed to referenced/implied/"fade to black" content)?

The output surfaces *evidence* for both. The legal determination is the district's.
**Bookmarked does not rate books. Bookmarked surfaces evidence.**

---

## 2. Workflow (product-level)

Two lanes, one prompt:

**Lane A — bulk pass over known lists (job number one).**
Run the prompt over every title on the known lists we hold (PEN America index, Take Back the
Classroom, Moms for Liberty, Moms for America, ALA OIF, state removal lists). ~2–5K titles.
These books arrive pre-flagged (Channel 1 below) AND get content evidence (Channel 2). Results
are cached per work; refresh on a 6–12 month cycle, not the legacy 21-day cycle.

**Lane B — on-demand: "Generate Book Intelligence."**
A customer uploads/creates a book list. Books already covered (Lane A or a prior run) show
stored results instantly. For uncovered books, the customer hits **Generate Book
Intelligence** → the prompt runs in the backend, asynchronously. v1 delivery: "we'll email
you when the report's done" (nightly batch acceptable). Per-run book-count guardrails are an
engineering decision; the workflow just requires that a cap, if any, is visible in the UI
before the run starts.

Per-book processing = two channels:

- **Channel 1 — known-list flags (data lookup, NO LLM).** Match title+author (fuzzy; a customer
  typo caused a catastrophic false negative in a prior audit) against the ingested known lists.
  Each hit emits a distinct, year-attributed flag — e.g. "PEN America Index, 2023–24" — phrased
  as *"appeared on [source] as of [date/scope]"*, never "is banned." Hits are never folded into
  a generic count.
- **Channel 2 — content evidence (THE PROMPT, §3).** Runs regardless of Channel 1 result for
  any book in a Lane A or Lane B run: a list hit tells you a book was challenged somewhere;
  it does not tell you what is in the book. Channel 2 answers T4/T6.

---

## 3. The prompt

### 3.1 System prompt (verbatim — this is the artifact engineering ingests)

```text
You are a content-evidence researcher for a school library compliance platform. School
districts must review library books under state library-material standards. Your job is to
research ONE book using credible public sources and report EVIDENCE about the book's content.
You never judge whether a book is good, bad, appropriate, or should be removed. You never
recommend keeping or removing a book. The district makes every judgment call; you make sure
they don't have to go searching for the evidence themselves.

## What you report on — the seven content categories

For each category below, you determine whether credible sources describe such content IN THIS
BOOK, and you report exactly what they describe:

1. sexually_explicit — descriptions or depictions of sexual conduct. Distinguish carefully
   between (a) detailed on-the-page scenes, (b) referenced/implied/"fade-to-black" content,
   and (c) educational or clinical references.
2. sustained_nudity — nudity that is depicted or described at length or repeatedly
   (most relevant for illustrated works and graphic novels).
3. extreme_violence — graphic, gratuitous, or glorified violence, torture, or gore beyond
   plot-necessary conflict. Report what sources actually describe, including who it happens
   to and how it is rendered.
4. profane_content — profanity and obscene language. Report severity and frequency as sources
   describe them (e.g., "frequent use of f---" vs "occasional mild profanity").
5. indecent_content — indecent descriptions or depictions of sexual or excretory acts or
   organs, in the statutory sense, that are not already captured under sexually_explicit.
6. patently_vulgar — content sources describe as patently offensive or vulgar by
   contemporary community standards.
7. prohibited_website_referral — the book directs readers to websites, hotlines, or online
   communities that sources report contain explicit or otherwise prohibited material.

## Verdict per category

- RED — credible sources describe SPECIFIC instances of this content in this book
  (a scene, a passage, a depiction, a count).
- YELLOW — evidence is partial: implied, brief, disputed between sources, secondhand,
  or described only in general terms.
- NO_EVIDENCE_FOUND — nothing admissible found. Render EXACTLY:
  "No content evidence found in sources reviewed as of {run_date}."
  NEVER say "safe," "clean," "clear," "low risk," "appropriate," or any equivalent. Absence
  of evidence is not a rating.

## The two legal lenses

After the categories, answer two evidence questions (evidence only — the legal determination
belongs to the district):
- prurient_theme: Do credible sources indicate the work AS A WHOLE appeals to prurient
  interest, or that its theme solicits an interest in sex? (Isolated passages do not, by
  themselves, establish this — say so when that is the case.)
- onpage_explicit_scenes: Do credible sources report detailed, on-the-page explicit scenes?
  Name the scenes/passages sources cite.

## Source rules — HARD CONSTRAINTS

ADMISSIBLE sources (use these):
- Professional review journals: Kirkus, School Library Journal, Booklist, Publishers Weekly,
  The Horn Book — best source of specific content descriptions.
- State government records: state education agency removal/objection lists, school board
  minutes and reconsideration decisions, court records.
- Authoritative index/advocacy rationale documents: PEN America, ALA OIF, Moms for Liberty
  chapter reports, Take Back the Classroom, Moms for America, NCAC — usable BOTH as
  challenge records AND for the specific content rationale they document. Report their
  claims as attributed claims, not established fact.
- Major and regional news organizations (staff-reported articles).
- Publisher and author official descriptions — for baseline context (plot, audience) only,
  never as caution evidence.

NEVER use or cite (inadmissible — a finding supported only by these is NO_EVIDENCE_FOUND):
- User-generated content: Facebook, Reddit, Quora, X/Twitter, Instagram, TikTok, Medium,
  Change.org, YouTube, Goodreads/StoryGraph reviews, fan wikis, personal blogs.
- Retail or resale listings: Amazon, Barnes & Noble, AbeBooks, eBay, PangoBooks, or any
  store page. A resale listing is not evidence of anything.
- Study-guide mills, AI-generated encyclopedias/aggregators, and content farms.
- Common Sense Media — the product displays CSM data separately under its own attribution;
  you must not scrape, quote, or cite it.

Claim discipline:
- Every cited source must EXPLICITLY name this book (exact title AND author — beware
  same-title different-author collisions and adaptations). A page that lists many books
  proves nothing about any one of them unless it names this one in the claimed context.
- Label every finding's claim_type: "content_description" (source describes what is in the
  book) or "challenge_record" (source documents that someone objected/challenged/removed).
  A challenge is NOT confirmation of content — keep the two distinct.
- Phrase list appearances as "appeared on [source] as of [year/scope]," never
  "is on [source]" or "is banned."
- Independence: PEN America, EveryLibrary, and indexes derived from them share a research
  lineage — cite at most one of them per claim and treat them as ONE witness. PEN America
  and Moms for Liberty are genuinely independent; agreement between them IS corroboration.
  Syndicated copies of the same article are one source.
- Never fabricate a source, quote, page number, or count. Never infer content from genre,
  audience, cover, author reputation, or the book's presence on any list. If you cannot
  verify, downgrade the verdict or report NO_EVIDENCE_FOUND.

## Output

Return ONLY a JSON object conforming to the provided schema. The synopsis field is 3–6 plain
sentences answering "what is this evidence telling me?" — written for a librarian skimming a
long report. Set review_priority to LOOK_CLOSER only when specific evidence was found
(any RED, or YELLOW on sexually_explicit / sustained_nudity / indecent_content, or either
legal lens true); otherwise NO_ACTION_INDICATED. This reflects evidence volume and
specificity only — it is not a rating of the book.
```

### 3.2 Per-book user message (template)

```text
Research this book and return the content-evidence JSON.

title: {title}
author: {author}
isbn: {isbn | "unknown"}
audience_shelf: {elementary | middle | high | unknown}
run_date: {YYYY-MM-DD}

Existing flags held by the platform for this book (may be empty; treat as leads to verify
against the source rules, NOT as established findings — many legacy flags are junk):
{surviving_flags_json | "none"}

Known-list matches from Channel 1 (already verified; include in known_list_flags verbatim):
{channel1_flags_json | "none"}
```

The `surviving_flags_json` block implements the two-pass mechanic: read what we already
hold (post-cleanup — UGC already stripped), synopsize what survives, then search for more.
In the stop-gap (no cleaned flag store yet) it is passed as "none" and the prompt works
search-only.

### 3.3 Output JSON schema

```json
{
  "book": { "title": "", "author": "", "isbn": "", "publication_year": 0, "audience_reported": "" },
  "known_list_flags": [
    { "list": "", "scope": "", "claim": "appeared on … as of …", "url": "", "independence_group": "" }
  ],
  "categories": {
    "sexually_explicit":            { "verdict": "RED | YELLOW | NO_EVIDENCE_FOUND", "findings": "", "claim_types": ["content_description | challenge_record"], "sources": [ { "name": "", "url": "", "type": "professional_review | state_record | advocacy_rationale | news | publisher", "date_or_year": "", "quote": "", "independence_group": "" } ] },
    "sustained_nudity":             { "...": "same shape" },
    "extreme_violence":             { "...": "same shape" },
    "profane_content":              { "...": "same shape" },
    "indecent_content":             { "...": "same shape" },
    "patently_vulgar":              { "...": "same shape" },
    "prohibited_website_referral":  { "...": "same shape" }
  },
  "legal_lenses": {
    "prurient_theme":         { "evidence_found": false, "basis": "" },
    "onpage_explicit_scenes": { "evidence_found": false, "basis": "" }
  },
  "synopsis": "",
  "review_priority": "LOOK_CLOSER | NO_ACTION_INDICATED",
  "provenance": {
    "model": "", "prompt_version": "1.0", "run_date": "",
    "sources_reviewed_count": 0,
    "disclaimer": "This summary is AI generated and unverified. Confirm findings against the cited sources before acting."
  },
  "feedback": { "thumbs": null, "note": null }
}
```

Notes for engineering:
- `feedback` is a placeholder the UI writes to (thumbs up/down per card is the quality
  loop; down-voted cards are triage input, not auto-deleted).
- `provenance` closes the standing AI-provenance gap: model id, prompt version, run date
  persist with every record.
- On Bedrock/Nova, enforce the schema with tool-use constrained decoding (greedy) — do not
  rely on freeform JSON.

---

## 4. Rendering spec

**Report level (email + list view) — the chart (T2).** One row per title; seven columns.
Cell glyphs: ● RED · ◐ YELLOW · — no evidence found. Two extra columns: known-list flags
(each named + year, e.g. "PEN America 2023–24"), and review priority. Sorted LOOK_CLOSER
first. Header carries the AI-generated disclaimer and run date.

**Book level — the cards.** A new "AI-generated book summary" section:
- One card per category with evidence (RED/YELLOW): category name, verdict color, findings
  text, source links (name + year, click-through), thumbs up/down on the card.
- Categories with no evidence collapse into a single neutral line: *"No content evidence
  found in sources reviewed as of {date}: {category list}."* Rendered neutral/gray — never
  green, never "clear."
- Legal-lenses strip: the two lenses with evidence_found state and basis sentence.
- Rollup synopsis at the bottom (the "what are these flags telling me" paragraph).
- Known-list flags render as distinct named flags with year attribution, visually separate
  from the AI summary and never summed into a count.
- Footer on the whole section: "This is AI generated" + thumbs up/down + report date.
- Common Sense Media data, where shown, stays in its own visually distinct block with
  "Source: Common Sense Media" attribution — never mixed into this section.

---

## 5. Validation plan

**Known-answer set** (run in the companion sample report):

| Book | Expectation |
|---|---|
| *Because of Winn-Dixie* | All 7 categories NO_EVIDENCE_FOUND (current-system false positive: "1 ban 3 challenges") |
| *Diary of a Wimpy Kid #10 (Old School)* | No ban, no content evidence — pre-registered acceptance test (legacy flag traced to a resale listing) |
| *All Boys Aren't Blue* | RED sexually_explicit with ≥2 admissible sources naming specific passages (the 144-flag book — this is the usability fix) |
| *Gender Queer* | RED sexually_explicit + sustained_nudity (illustrated) with specific sources |
| *To Kill a Mockingbird* | Violence/profanity/racial-slur findings with sources; NO sexually_explicit false positive |
| *The Hunger Games* | extreme_violence findings; no sexual-content false positive |
| *The Perks of Being a Wallflower*, *Looking for Alaska*, *The Absolutely True Diary of a Part-Time Indian* | YELLOW/RED on sexual content & profanity with specific scene citations — the nuanced middle where specificity matters most |
| *Drama* (Telgemeier) | Challenge records exist (challenge_record), but content evidence near-empty — the discriminator between "challenged" and "contains" |

**Compliance sweep** on any run before it ships to a customer: zero inadmissible domains
cited; every source names the book; exact no-evidence string; every list claim year-attributed
and "as of"-phrased; disclaimer + provenance present on every record.

**Regression set (next step, not this session):** the 99-title gold-standard audit list —
run the prompt across it and diff against the manually verified findings.

**Fail conditions (any one fails the run):** a control book gets any RED/YELLOW; a known-red
book returns NO_EVIDENCE_FOUND on its established category; any cited source is on the
blocklist; any output says safe/clean/clear/low-risk.

---

## 6. Calibration against the design partner's own prompt

**PLACEHOLDER — her verbatim prompt text is pending** (she pasted it into a meeting chat;
CEO has it). When received:
1. Decompose her prompt into individual asks.
2. Map each ask to the section of this spec that covers it; extend the spec where uncovered.
3. Side-by-side run on 3 books (her prompt vs this spec) and record deltas here.

What we already know it must cover (from the call): chart across a batch (T2), the
"cause me a problem / violates state law" framing (T3), per-hit content drill-down with the
reviews behind it (T4).

---

## 7. Ownership & next steps

- This spec is the CEO-owned "what is the prompt" deliverable from the 2026-08-19 roadmap
  sync; destination of record is the Confluence Book Intelligence area (as an additive child
  page — locked pages untouched) so the V3 engine rebuild ingests it.
- Product lead owns: known-list ingestion + labeling tickets, legacy flag cleanup
  (UGC removal), Confluence documentation of this request for the rebuild.
- Note for the ingestion ticket: Take Back the Classroom is named as an admitted source but
  is not yet in the BI source registry (it exists only in the April source-registry page) —
  promote it.
- Staging first. UAT-eyeball the sample output, iterate the prompt, then production.
