---
name: transcript-identity-hygiene
version: 1.0.0
description: |
  Prevent and repair entity corruption caused by mis-transcribed names.
  Speech-to-text turns names into entities; a wrong name becomes a wrong
  person page, a split relationship, or an entirely fabricated contact.
  Covers the full loop: upstream recorder hygiene (custom vocabulary,
  speaker library), detection of corrupted entities, and the three repair
  patterns — move, retire, merge.
triggers:
  - "duplicate person pages"
  - "merge duplicate pages"
  - "this person doesn't exist"
  - "fix duplicate people"
  - "why are there two pages for"
  - "clean up transcript names"
  - "speaker names are wrong"
  - "entity cleanup"
  - "the name is misspelled in my brain"
tools:
  - search
  - query
  - get_page
  - put_page
  - delete_page
  - get_backlinks
  - get_links
  - list_pages
mutating: true
writes_pages: true
writes_to:
  - people/
  - companies/
---

# Transcript Identity Hygiene

> **Filing rule:** Read `skills/_brain-filing-rules.md` before creating any new page.
> **Convention:** See `skills/conventions/quality.md` for Iron Law back-linking.

## Why this exists

A brain fed by meeting transcripts inherits its recorder's spelling. Entity
extraction does not know that `alice-exmaple` and `alice-example` are the same
person, so it creates both. Worse, it does not know that a mis-heard syllable
is not a person at all — given a few mentions, it will build a complete page
with a role, an employer, and open threads for someone who has never existed.

That failure mode is more damaging than a gap. A missing page is visibly
missing. A fabricated page is confidently wrong, and it silently degrades
trust in every other answer the brain gives.

## Contract

This skill guarantees:
- No canonical page is chosen without first checking inbound link direction
- Every merge preserves the union of content, never the intersection
- Every retired slug leaves either a working basename resolution or an
  explicit alias-redirect — never a dangling reference
- Every repair is reversible for the soft-delete recovery window
- Known-bad spellings are never taught back to the upstream recorder

## THE IRON RULE

**Never assume the correctly-spelled slug is the canonical page.**

The single most expensive mistake in this work is assuming the tidy-looking
slug holds the real content. It frequently does not. A common pattern:

- The rich, human-maintained page lives at the **misspelled** slug, because
  that is what the first transcript produced.
- An automated pass (dream cycle, nightly enrichment) later creates a thin
  stub at the **correct** spelling.
- All new inbound links resolve to the *correct* slug — the stub.

Deleting "the misspelled duplicate" in that situation destroys the real page
and keeps a three-sentence stub. **Check inbound links before deciding
anything.**

## Phase 1: Detect

Run these four sweeps. Each finds a different corruption class.

### 1a. Near-collision slugs

List all pages of type `person` and `company`, then group by normalized
basename (lowercase, strip `dr-`/`mr-` prefixes, collapse punctuation).
Any group with more than one member is a candidate.

Also compare with edit distance ≤ 2 on the basename — this catches
`alice-example` / `alice-exmaple` / `alise-example`.

### 1b. Slug/title disagreement

A page whose slug and `title` disagree on spelling is a strong signal that a
rename was half-done:

```
slug: alice-exmaple      title: "Alice Example"     ← rich page, bad slug
slug: alice-example      title: "Alice Example"     ← stub, good slug
```

### 1c. Self-hedging pages

Grep page bodies for hedge language the enrichment pass emits when it cannot
resolve an identity:

- "may be a transcription artifact"
- "surname spelling unverified"
- "spelling from transcript — verify"
- "disambiguation"
- "single-mention"

**These are the fabricated-entity candidates.** A page that doubts its own
subject usually should not exist as a person.

### 1d. Malformed titles

Titles where entity extraction fused two things:

- `Alice Acme Corp` — person name welded to employer
- `Alice Example Isd` — lost intercapitalization on an acronym
- `Alice Mcexample` — lost intercap on a surname

The body `# H1` is usually correct in these cases; only the title metadata is
wrong. That makes it a safe, link-free fix.

## Phase 2: Classify

For each candidate pair, pull inbound links for **both** sides before acting.
Then classify into exactly one of three cases.

| Case | Signature | Repair |
|---|---|---|
| **A — Wrong basename** | Basenames differ. Rich content at the wrong one, links at the right one. | **Move** content to the correct slug, retire the wrong one. |
| **B — Redundant stub** | Basenames match. One side is a thin auto-generated stub. | **Retire** the stub. Wikilinks self-heal by basename. |
| **C — Complementary** | Basenames match. Both sides rich, covering different ground. | **Merge** the union into the newer/richer slug. |

### Why the basename question decides everything

Link resolution has two channels:

- `[[alice-example]]` — resolves by **basename**, so it self-heals if a page
  with that basename survives anywhere.
- `[wiki/people/alice-example]` — an explicit path, which **dangles** if that
  exact slug disappears.
- Auto-derived `mentions` links — resolve by **title**, and regenerate on
  reindex.

So in **Case B**, deleting the stub is safe: `[[alice-example]]` finds the
survivor. In **Case A**, deleting either side orphans real links, because the
basenames differ — the content must physically move.

**Count both sides before choosing.** In practice, a heavily-linked stub and a
zero-inbound rich page is the most common and most dangerous shape.

## Phase 3: Repair

### Case A — Move

1. Read the rich page in full. Read the stub for anything unique.
2. `put_page` the **union** at the correctly-named slug. Preserve every
   section; fold the stub's unique facts in.
3. Record provenance in frontmatter:
   ```yaml
   merged_from: alice-exmaple
   merge_note: >-
     Canonical hub consolidated <date>. Rich synthesis previously lived at the
     misspelled slug while inbound links resolved here.
   ```
4. `delete_page` the old slug (soft-delete).
5. Verify with `list_pages` that the survivor is present and the old slug is gone.

### Case B — Retire

1. Confirm the stub is genuinely thin — auto-generated frontmatter
   (`dream_generated: true` or similar), a few sentences, no unique facts.
2. Extract any unique nugget and note it for the user; do not silently discard.
3. `delete_page` the stub.

Do **not** rewrite the surviving rich page just to add a minor nugget. The
transcription risk of retyping a large page exceeds the value of the detail.

### Case C — Merge

Same as Case A, but the union is the whole job — both sides carry content the
other lacks. Merge into the **newer** slug when recency matters (live threads,
current status) and note both sources.

### Fabricated entities — the fourth case

When Phase 1c turns up a page for someone who does not exist:

1. **Confirm with the user.** Never dissolve an identity on inference alone.
2. Move any genuinely real content (usually organizational context) to the
   correct entity — often a company or project page.
3. Convert the slug into an **alias-redirect** rather than deleting it, so
   future mentions of the bad spelling resolve instead of minting a new page:

```markdown
---
title: Alise (see Alice Example)
type: person
redirects_to: alice-example
tags: [alias-redirect, person]
---

# Alise → Alice Example

**Transcription error. "Alise" is not a name.** Every occurrence is
**Alice Example**.

**Canonical page:** [[alice-example]]

- Person context → [[alice-example]]
- Organizational context → [[acme-example]]

## Known variants
`Alise` · `Alise Acme` · `Alyce`
```

4. Add every variant to the canonical page's frontmatter `aliases`. **This is
   the step that prevents recurrence** — without it, extraction re-mints the
   bad page on the next transcript.

```yaml
aliases:
  - Alise
  - Alise Acme
  - Alyce
```

## Phase 4: Close the tap (upstream)

Repair without prevention guarantees a repeat. Two upstream controls exist on
most recorders:

### Custom vocabulary

Most transcription products accept a term list that biases recognition and
fixes output spelling. Generate it **from the brain** — the roster is already
there:

1. `list_pages` for types `person` and `company`
2. Strip honorifics and parenthetical qualifiers; normalize acronym casing
3. Drop bare common first names — they waste slots and transcribe fine anyway
4. Add domain vocabulary the brain does not store as entities (statute names,
   product terms, internal acronyms)
5. Refresh quarterly — the roster drifts

**Never add a known-bad spelling to the vocabulary.** Vocabulary teaches the
recorder what to *output*. Adding the error entrenches it permanently. When
building the list from brain pages, explicitly filter out any slug or title
you have identified as a mis-transcription.

### Speaker library

Recorders that learn voiceprints from user-applied labels turn every manual
correction into durable training data — but they equally learn *wrong* labels
and reapply them forever.

- Fix misspelled entries at the source; one bad label reproduces on every
  future recording of that person.
- Prefer **rename over delete** — renaming keeps the voiceprint and maps it to
  the correct name; deleting discards learned signal.
- Audit for single-token entries (`Chuck`, `Sarah`, `Derek`). These are
  fabricated-entity precursors: enough substance for extraction to build a
  person around, not enough to identify one.

## Phase 5: Verify

- `list_pages` sorted by `updated_desc` — confirm survivors present, retired
  slugs absent
- Spot-read one merged page end-to-end for truncation
- Confirm write-through landed if the brain mirrors to a repo
- **Tell the user the recovery deadline.** Soft-deletes purge after the
  recovery window; a spot-check before then is the last cheap chance to catch
  a bad merge.

## Output Format

Report the sweep, then the repairs, then the deadline.

```
Detected: {N} candidate pairs ({N} case A, {N} case B, {N} case C, {N} fabricated)
Repaired: {N} moved, {N} retired, {N} merged, {N} aliased
Titles fixed: {N}
Upstream: {N} vocabulary terms refreshed, {N} speaker entries corrected
Recoverable until: {timestamp} — spot-check merged pages before then
```

Always name the merged pages explicitly and list any content dropped from a
retired stub — never let a discard be silent. If a fabricated entity was
dissolved, say which page absorbed its real content.

## Anti-Patterns

| Don't | Why |
|---|---|
| Batch-delete "the misspelled one" | The rich page is often at the misspelled slug |
| Trust slug tidiness over link counts | Links are evidence; tidiness is aesthetics |
| Rewrite a large page to add one detail | Retyping risk exceeds the value |
| Add the misspelling to recorder vocabulary | Teaches the error permanently |
| Delete a speaker entry to fix its name | Discards the learned voiceprint |
| Dissolve an identity without confirming | You may be deleting a real person |
| Merge personal and work framings silently | Context bleed; flag it and let the user decide |

## Notes on scope

Speaker diarization is frequently wrong even when names are spelled right —
attribution can swap mid-transcript. Do not treat speaker labels as
authoritative for fact extraction. When a calendar or roster is available,
resolving speakers against a closed attendee set beats open-vocabulary
guessing.

Repairing the brain does not repair the recorder's existing exports. Most
recorders apply a corrected speaker name only to *future* recordings.
