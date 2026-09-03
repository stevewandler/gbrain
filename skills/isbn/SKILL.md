---
name: isbn
version: 1.0.0
description: |
  ISBN and ISO 2108 identifier expertise for book records. Use when a question involves an
  ISBN, ISBN-10 vs ISBN-13, check digits, a 978 or 979 prefix, an SBN, whether a change
  requires a new ISBN, ISBN assignment for a set or multi-volume work, ebook and EPUB
  format ISBNs, DRM variants, translations, imprint or publisher changes, trim size changes,
  an EAN-13 barcode, ONIX metadata feeds, BISG title rules, or triaging dirty ISBN data
  (placeholder prefixes, concatenated values, failed check digits). Also use before writing
  any ISBN to a durable store. Does NOT own MARC record structure (use marc-records).
triggers:
  - "isbn"
  - "isbn-10"
  - "isbn-13"
  - "check digit"
  - "does this need a new isbn"
  - "set isbn"
  - "ebook isbn"
  - "onix"
  - "ean-13 barcode"
  - "is this a valid isbn"
  - "why did this isbn fail"
tools:
  - shell
mutating: false
---

# ISBN — identifier logistics

**This is a mirror.** It carries the ISO 2108 standards only. An upstream canonical copy is
maintained by the publisher alongside their own data mapping and incident history; changes
start there, not here.

## Contract

This skill guarantees:

- **No inferred identifier rules.** If a rule is not stated here, the answer is *"I don't
  know — this needs checking against <named authority>"*. An honest gap is the correct
  answer; a confident wrong answer about an identifier is a permanent data defect.
- **Nothing ISBN-shaped is ever minted.** Not a placeholder, not a synthetic, not a
  temporary one. An empty ISBN field is honest; a fabricated one can generate a real
  purchase order for a book that does not exist.
- **Check-digit validation before any write**, via `isbn-tools.ts` rather than by eye — and
  with the explicit understanding that a passing check digit is a floor, not proof.
- **Impossible conversions fail loudly.** A `979`-prefixed ISBN has no 10-digit form; the
  converter raises rather than returning a plausible wrong answer.

## Core axioms

- **An ISBN is a commercial supply-chain tool.** Not a copyright registration, not proof of
  authorship, not a quality signal. It exists so a specific product can be listed, ordered,
  inventoried, and discovered.
- **The Manifestation Rule.** An ISBN identifies a specific *format and edition*, not the
  work as an abstract thing. One text as hardcover, paperback, EPUB, PDF and audiobook needs
  five distinct ISBNs.
- **Permanence and non-reusability.** Once registered, permanently tied to its metadata
  record — that is what preserves library holdings files and historical commerce data. It can
  never be edited, recycled, or reassigned, even if the book is cancelled.
- **No expiration.** Unassigned ISBNs in a publisher's block stay valid indefinitely.
- **ISBN is a weak identifier for retrieval.** It is edition-grain, and effectively nothing
  published before ~1970 has one. Treat it as the first rung of an identifier cascade
  (ISBN → OCLC → LCCN → work-level id → normalised title+author+year), never as the answer.

## Anatomy

```
978-0-306-40615-7
[Prefix 978][Group 0][Registrant 306][Publication 40615][Check 7]
```

| Segment | Length | What it is |
|---|---|---|
| Prefix (GS1) | always 3 | `978` or `979` — designates a book within GS1 |
| Registration group | 1–5 | country, region, or language territory |
| Registrant | up to 7 | publisher or imprint. Larger publishers get *shorter* registrant elements. |
| Publication | up to 6 | the specific title/format/edition |
| Check digit | 1 | validates the preceding 12 |

**Segment lengths are variable and cannot be inferred from the string.** Splitting an ISBN
into segments requires the official range file. If a task needs that, say so.

Under prefix `979`, registration group `0` is reserved for ISMNs — out of scope for books.

### Check digits

**ISBN-13 (Modulus-10):** weight the first 12 digits alternately 1, 3 starting at 1; sum;
take mod 10; the check digit is `0` if the remainder is 0, else `10 − remainder`.

**ISBN-10 (Modulus-11):** weight the 9 digits 10 down to 2; sum; check digit is
`(11 − (sum mod 11)) mod 11`, with the value 10 written as `X`.

### ⚠️ The Modulus-10 transposition blind spot

**A passing Mod-10 check does not mean the ISBN is correct.** If two adjacent digits are
transposed and their difference is exactly **5** (6↔1, 3↔8, 7↔2, 9↔4, 5↔0), the checksum is
unchanged and the error is invisible. A structurally valid ISBN can belong to an entirely
different book. Modulus-11 (ISBN-10) does not have this weakness.

### ⚠️ The 979 conversion block

**An ISBN beginning `979` has no 10-digit equivalent.** The conversion is mathematically
impossible — the `979` registrant space was never allocated in the 10-digit scheme. Any code
path that "converts back to 10 digits for lookup" needs a `979` branch that skips it.

### SBN zero-padding (pre-1974)

A 9-digit Standard Book Number from an English-speaking territory (US, UK, Canada, Australia,
New Zealand, South Africa, Zimbabwe) becomes a valid ISBN-10 by **prepending a single leading
zero**: SBN `688054552` → `0688054552`. SBNs from other territories do **not** take the zero.

## New ISBN or same ISBN

**The Customer Expectation Test:** if a reader who ordered the original received this version,
would they feel they got a different product? Yes → new ISBN.

**NEW ISBN is mandatory for:** significant content revision (chapters added or removed, new
foreword, extensive appendices, rewrites beyond ~10% of the manuscript) · format change
(paperback ↔ hardcover, print ↔ ebook, audiobook) · **trim size change** (warehouse systems
allocate shelving and shipping weight from trim dimensions) · any title or subtitle change,
even one word · publisher or imprint change (the registrant element is bound to a publisher
prefix) · translation · grayscale vs colour interior · a different DRM/usage-rights profile
on the same file.

**SAME ISBN is retained for:** typo fixes that do not change page flow · unchanged reprints ·
retail price changes · cover art redesign · **device display variation** (the same EPUB
rendering in colour on a tablet and grayscale on e-ink is hardware, not a product variant —
contrast with a deliberately produced grayscale edition, which does need its own ISBN).

If the matrix does not settle a case, **say so** rather than extending it by analogy.

## Titles, ebooks, sets, linked media

**Title integrity (BISG).** Title and subtitle metadata must match the physical title page
**exactly**. Strip promotional terms, keyword stuffing, and sales pitches that are not on the
title page — they belong in ONIX marketing description tags, never the title block.

**Format-neutral ebooks.** Do not assign an ISBN to a format-neutral EPUB or master XML file
unless it is sold directly to the public as a standalone product. If a publisher ships such a
file to a distributor who converts it to proprietary DRM-locked formats without supplying
per-version ISBNs, the converting intermediary may assign their own.

**Linked media — use ISLI, not a new ISBN.** When external audio, video, or digital assets are
linked to an existing printed book, use the International Standard Link Identifier
(ISO 17316): the book is the stable *Source* (its print ISBN), the assets are *Targets*
(ISRC, ISAN, URI). The media can then change without touching the book's ISBN.

**Sets.** If volumes are sold separately, each needs its own ISBN *and* the set gets a
separate Set ISBN. Even when volumes are not sold separately, per-volume ISBNs are strongly
recommended so a single damaged volume can be returned. Every volume's copyright page lists
all ISBNs, qualified:

```text
ISBN 978-1-4249-6171-9 (set)
ISBN 978-1-4249-6172-6 (v. 1)
ISBN 978-1-4249-6173-7 (v. 2)
```

**Co-publication.** Both publishers may print their ISBNs on the copyright page, but **only
one can be encoded in the EAN-13 barcode** — the one belonging to whoever manages inventory
and fulfilment. Encoding two breaks automated retail scanning.

## ONIX for Books 3.0 / 3.1

- Multi-component set: `<ProductComposition>` (`<x313>`) = **`10`**
- Each child volume is a `<ProductPart>` carrying `<ProductIDType>` (`<b221>`) = **`03`**
  (GTIN-13/ISBN-13), `<IDValue>` (`<b244>`) = the ISBN, and `<ProductForm>` (`<b012>`) =
  the physical form (`BB` hardback, `BC` paperback).

**Code List 51 — product relations**, inside `<RelatedMaterial>`:

| Code | Meaning |
|---|---|
| `03` | Replaces (this is a new edition of the linked ISBN) |
| `05` | Replaced by — redirects search traffic and merges review history onto the active listing |
| `06` | Alternative format — same text, different format |
| `11` | Is other-language version of |
| `13` | Based on print product — needed for print-equivalent page numbering |
| `16` | POD replacement for |
| `28` | Enhanced version available as |

Codes outside this list exist. Do not guess one — the complete list is at EDITEUR.

## Dirty data — the classes that occur in real catalogs

| Pattern | What it means | What to do |
|---|---|---|
| **Placeholder prefixes** (a repeated-digit prefix used by bulk imports with no ISBN) | "no ISBN", not an identifier and not a barcode | Exclude from matching, enrichment, and dedup; fall back to title+author |
| **23-character values** | two ISBNs concatenated by an import that failed to split a separator — **both orders occur**, 13-then-10 and 10-then-13 | Split; do not discard. Never assume one order. |
| **`978` + a valid ISBN-10, failing validation** | someone prefixed `978` and kept the ISBN-10's Mod-11 check digit instead of recomputing | The correct ISBN-13 is derivable from the intact ISBN-10 — a conversion, not a mint. Make the repair opt-in. |
| **Failed check digit** | legacy data, or a path that bypassed validation | **Never write it.** In an append-only store it is permanent, and vendor APIs answer it with a permanent error, so the loop re-asks forever. |
| **One ISBN under many title+author keys** | overwhelmingly title-string variance (subtitle present/absent, series prefix, truncation) | Do not assume contamination. A genuinely wrong minority exists; if string heuristics cannot size it, **say so instead of quoting a number**. |
| **Many internal record ids for one title+author** | usually a scoping artifact of a migration, not drift | Match to any of them |
| **A local barcode** | one physical copy in one library — the same barcode is a different book elsewhere | Never an identifier. It is something you return, never match on. |

Two matching traps worth carrying:

- **Stripping a volume number destroys identity.** `Blue Period, Vol. 8` stripped to
  `Blue Period` matches volume 1 just as happily. Merging volumes of a series is worse than
  leaving them apart. Guard on the volume number and retry with the raw title.
- **A short title is contained in every longer title that includes it.** *The Giver* matches
  *The Giver of Stars*; a same-author sequel defeats the author check too. Cap confidence when
  a candidate adds two or more identifying words to a short title.

## Validators

`isbn-tools.ts` is the reference implementation. `classify()` returns exactly one of eight
classes — `valid_isbn13`, `valid_isbn10`, `sbn9`, `placeholder_888`, `concatenated_13_10`,
`naive_978_prefix`, `bad_check_digit`, `not_an_isbn`.

**`classify()` alone is enough to decide whether to write a value, and never enough to
decide to discard one.** Three classes are recoverable rather than junk:
`concatenated_13_10` (split it), `naive_978_prefix` (repairable), and `sbn9` (zero-pads).
Only `not_an_isbn` and `placeholder_888` mean there is no number here.

```ts
import { classify, normalize, isbn10ToIsbn13, splitConcatenated } from './isbn-tools.ts';
```

`splitConcatenated()` handles both storage orders and always returns `[isbn13, isbn10]`.
`naive978PrefixRepair()` handles both the bare and concatenated forms and is opt-in —
nothing in the module silently corrects a value.

## Anti-Patterns

- **Minting an ISBN-shaped placeholder** so a record can pass a not-null constraint. Fix the
  constraint; an empty field is honest.
- **Treating a passing check digit as proof the ISBN is right.** It rules out typos, not
  wrong books. See the transposition blind spot.
- **Converting a `979` ISBN to 10 digits** because the code path expects 10 digits.
- **Gating display on the presence of an ISBN.** Pre-1970 works, speeches, poems and
  scripture have none and never will; gating makes them structurally invisible. Carry an
  explicit status value (`has_isbn` / `none_exists` / `unresolved` / `not_a_book`) instead.
- **Stripping annotations, volume numbers, or subtitles to raise a match rate**, without a
  guard that rejects the merges this causes.
- **Concluding data cannot be matched before exhausting the matching code that already
  exists.** A low match rate is a claim about the instrument until proven otherwise.
- **Quoting a count that string heuristics cannot honestly support.**

## Output Format

- **A verdict question** ("does this need a new ISBN?") → the verdict, the trigger from the
  matrix that decides it, and the Customer Expectation Test reading. One short paragraph.
- **A validation question** → the class from `classify()`, plainly named, plus what to do with
  it. If the value is structurally valid, say so *and* say that this does not mean it belongs
  to the book claimed.
- **A triage over many values** → a table of class → count → action, with the excluded classes
  named explicitly rather than folded into "invalid".
- **Anything not covered** → *"I don't know — that's answered by <authority>"*, naming which
  one and what it would settle. Never a bare refusal, never a guess.
- ONIX and identifier examples in fenced blocks, using placeholder titles and publishers.

## Authorities

| Authority | URL | Answers |
|---|---|---|
| International ISBN Agency | `https://www.isbn-international.org/` | The Users' Manual, national registries, the range files defining segment boundaries |
| Global Register of Publishers | `https://www.isbn-international.org/content/global-register-publishers/49` | Publisher prefixes and registrant elements |
| US ISBN Agency (Bowker) | `https://www.myidentifiers.com/` | US block purchase and assignment |
| EDITEUR | `https://ns.editeur.org/` | The complete ONIX schema and every code list |
| BISG | `https://bisg.org/` | Title and subtitle misuse policy |
| Library of Congress | `https://www.loc.gov/marc/` | MARC 21, and a free unauthenticated path to full records |

Free: Library of Congress, OpenLibrary, Google Books (which also returns OCLC and LCCN).
Paid: the OCLC WorldCat Metadata API (the Entities API is free). **xISBN is retired** — any
document citing it is stale.
