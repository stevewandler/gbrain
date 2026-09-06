---
name: marc-records
version: 1.0.0
description: |
  MARC 21 and RDA bibliographic record expertise. Use when a question involves a MARC record,
  a MARC tag or field number (010, 020, 035, 100, 245, 250, 260, 264, 300, 490, 520, 650,
  700), indicators, subfields or delimiters, the Leader, the Directory, the 008 fixed-length
  field, authority control or established name forms, LCSH or Sears subject headings, LCCN or
  OCLC numbers, an ILS or library catalog export, a MARC21 or MARCXML file, or converting a
  catalog card into a machine-readable record. Also use when an ISBN needs to be placed into
  a bibliographic record correctly. Does NOT own ISBN assignment or validation (use isbn).
triggers:
  - "marc record"
  - "marc 21"
  - "marc tag"
  - "what does field 245 mean"
  - "indicators"
  - "subfield"
  - "the leader"
  - "008 field"
  - "marcxml"
  - "lccn"
  - "oclc number"
  - "authority control"
  - "established heading"
  - "lcsh"
  - "sears"
  - "catalog card to marc"
  - "ils export"
tools:
  - shell
mutating: false
---

# MARC 21 — bibliographic record architecture

**This is a mirror.** It carries the MARC 21 / RDA standards only. An upstream canonical copy
is maintained by the publisher alongside their own data mapping; changes start there, not here.

## Contract

This skill guarantees:

- **No invented content designators.** A tag, indicator value, or subfield code that is not
  stated here is a lookup, never an inference. MARC's meanings are defined, not derivable.
- **No invented authority headings.** Access points (1XX, 6XX, 7XX, 8XX) must match an
  established form. A guessed heading is one no other library shares, which is precisely the
  failure authority control exists to prevent.
- **No assertions about a vendor's API.** Whether a given ILS exposes a given field over its
  API is verified-or-not, never reasoned.
- **Field emission through `marc-tools.ts`**, not hand-assembled strings — the Field 020
  punctuation rules alone are enough to get wrong.

## Core axioms

- **Machine-readable means a computer can find the parts.** A flat catalog card gives a
  computer no way to know where a title ends and a statement of responsibility begins. MARC
  puts numeric **content designators** — signposts — before each element.
- **Variable fields, variable lengths.** Titles, physical descriptions and series statements
  vary enormously; MARC is built for unlimited fields of unlimited length.
- **"MARCese".** Compact numeric shorthand instead of wordy labels — `264` rather than "place
  of publication", `$c` rather than "physical size".
- **The standard is the point.** MARC 21 is what prevents duplicate cataloging, lets libraries
  share records, and keeps data portable across ILS migrations.

## Record anatomy

### The Leader — the first 24 characters (0–23)

| Position | Element |
|---|---|
| 5 | Record status — new, corrected, deleted, encoding level increased |
| 6 | Type of record — language material, printed music, non-projected graphic, audiovisual |
| 7 | Bibliographic level — monograph, serial, collection |
| 9 | Character coding scheme — UTF-8 or MARC-8 |
| 10 | Indicator count — **always `2`** in MARC 21 |
| 11 | Subfield code length — **always `2`** (delimiter + letter) |
| 12–16 | Base address of data — where Leader + Directory end |

### The Directory — the record's table of contents

Built automatically, immediately after the Leader. Repeatable **12-character blocks**:
tag (3) + field length (4) + starting character position (5). Because fields do not start at
fixed positions, the computer queries the Directory to locate a tag. **Any edit rebuilds the
Directory entirely** — which is why hand-editing a raw communications record is a mistake, and
why tools emit fields and let the software assemble.

### Variable control fields 001–009

No indicators, no subfields — data sits directly after the tag.

### The 008 — exactly 40 characters (0–39)

| Positions | Element |
|---|---|
| 0–5 | Date entered on file (YYMMDD) |
| 6 | Type of date / publication status |
| 7–10 / 11–14 | Date 1 / Date 2 (four-digit years) |
| 15–17 | Place of publication (e.g. `nyu`) |
| 18–21 | Illustrations |
| 22 | Target audience |
| 23 | Form of item — large print, microform, electronic |
| 24–27 | Nature of contents — bibliography, dictionary, directory, index, thesis |
| 28 | Government publication |
| 29 | Conference publication (`1`/`0`) |
| 30 | Festschrift (`1`/`0`) |
| 34 | Biography |
| 35–37 | Language (e.g. `eng`, `spa`) |

**Positions 18–34 above are the BOOK definitions** (Leader/06 = language material). Other
material types redefine them entirely. If the record is not a book, this table does not apply
— say so rather than reading it anyway.

## Content designators

### Tags and the hundreds divisions

| Tag | Field |  | Block | Contents |
|---|---|---|---|---|
| **010** | LC Control Number (LCCN) |  | **0XX** | Control info, numbers, codes |
| **020** | ISBN |  | **1XX** | Main entry — primary creator |
| **035** | System control number (OCLC) |  | **2XX** | Titles, edition, imprint |
| **100** | Personal name main entry |  | **3XX** | Physical description |
| **245** | Title statement |  | **4XX** | Series statements as printed |
| **250** | Edition statement |  | **5XX** | Notes |
| **264** | Imprint (RDA) |  | **6XX** | Subject added entries |
| **300** | Physical description |  | **7XX** | Added entries other than subject/series |
| **490** | Series statement |  | **8XX** | Series added entries |
| **520** | Summary note |  | **9XX** | **Locally defined** — call numbers, barcodes, prices |
| **650** | Topical subject heading |  |  |  |
| **700** | Personal name added entry |  |  |  |

Within each block the `X9X` slot (090, 590, …) is also local — **except 490**, a real series
statement.

### Indicators

Two character positions after the tag. Blank/undefined is written `#`. Each holds a **single
digit 0–9**, and **they are never read as one two-digit number** — `14` is "first indicator 1,
second indicator 4", not fourteen. This is the most common misreading of a MARC string.

```text
245 14 $a The emperor's new clothes / $c Hans Christian Andersen...
```

First indicator `1` = create a searchable title added entry. Second indicator `4` = ignore the
first **4 characters** (`T`, `h`, `e`, space) when alphabetizing, so it files under **E** for
"Emperor", not **T**. Get that wrong and every title beginning "The" files together.

### Subfields

A delimiter (`$`, `ǂ`, or `_`) plus one lowercase letter or digit.

```text
300 ## $a 25 p. : $b col. ill. ; $c 26 cm.
```

`$a` extent · `$b` other physical details · `$c` dimensions. **Subfield codes are
field-specific** — `$c` is dimensions in `300`, date in `264`, and statement of responsibility
in `245`. Never carry a subfield's meaning across fields.

### Authority control

Access points must match an established form.

**The cats-vs-felines axiom.** If one cataloger files books about felines under FELINES and
another under CATS, a user searching either finds half the collection. An authority list
establishes one approved heading regardless of which synonym a book's own title uses.

Registries: the Library of Congress Name Authority File for personal, corporate and meeting
names; LCSH or the Sears List for subjects.

### The parallel content rule

**Last two digits = entity type. Hundreds digit = the role it plays.**

| Ending | Entity |
|---|---|
| X00 | Personal names |
| X10 | Corporate names |
| X11 | Meeting or conference names |
| X30 | Uniform titles |
| X40 | Bibliographic titles |
| X50 | Topical terms |
| X51 | Geographic names |

Person as creator → `100`. Corporation as creator → `110`. Person as *subject* → `600`. Topic
as subject → `650`. Place as subject → `651`. Co-author added entry → `700`.

This lets you derive a tag you have not memorised — but only inside the pattern. An entity
type not in the table is a lookup.

## Field 020 — the ISBN in a record

Both indicators are undefined and left blank (`##`).

| Subfield | Repeatable | Rule |
|---|---|---|
| `$a` | **No** | Recorded **without spaces, hyphens, or punctuation**. Only a structurally valid, check-digit-verified number. |
| `$q` | Yes | Brief standardised qualification in parentheses: `pbk.` `hbk.` `ed.` `v.` `vol.` `set` |
| `$z` | Yes | Cancelled or invalid ISBN — including one that is invalid *for this record* |

**Punctuation.** One set of parentheses per field; multiple qualifiers separated by **space,
semicolon, space** inside that one set: `(pbk. ; v. 1)`. **No trailing terminal punctuation**
unless the field already ends in an abbreviation period, hyphen, or closing parenthesis.

**SBN zero-padding.** A 9-digit SBN from an English-speaking territory zero-pads into `$a`:
`SBN 688054552` → `020 ## $a 0688054552`. SBNs from other territories go to `$z`.

### ⚠️ Set-collapsing prevention

When cataloging **one volume of a set**, do not put both the volume's ISBN and the set's ISBN
in valid `$a` subfields. The set ISBN is **application-invalid** for a single-volume record:

```text
020 ## $a 9781498721271 $q (v. 1)
020 ## $z 9781498721288 $q (two-volume set)
```

Put the set ISBN in `$a` and a catalog search for the set collapses into volume 1 — the user
asks for the set and receives one book.

### ⚠️ OCLC automatic regeneration

If a record holds both the 10- and 13-digit forms of one ISBN and you delete only one, **the
OCLC cooperative regenerates the deleted form on the next sync**. To remove an ISBN you must
delete **both forms at once**. A "the deletion didn't stick" report is usually this, not a
failed write — and any bulk 020 edit must be planned in 10-and-13 pairs.

### Routing a value of unknown quality

| Class (from the `isbn` skill) | Goes to |
|---|---|
| valid ISBN-13 / ISBN-10 | `$a` |
| SBN, English-speaking territory | zero-pad, then `$a` |
| SBN, elsewhere | `$z` as transcribed |
| failed check digit | `$z` — never `$a` |
| `978` + a valid ISBN-10 with the wrong check digit | `$z` **as stored**. Accepting the derived correction is a separate, deliberate decision; the corrected value then goes to `$a` and the malformed one stays in `$z` as transcribed. |
| set ISBN on a volume record | `$z` with a `$q` qualifier |
| placeholder prefix | **neither** — it means "no ISBN". Omit the field. |
| a run of concatenated ISBNs | split the run first, then route each ISBN it yields |
| not an ISBN at all | **neither.** Do not transcribe junk into `$z` to make it disappear. |

## Imprint — Tag 264, not legacy 260

**Use `264`** (Production, Publication, Distribution, Manufacture, and Copyright Notice). Tag
`260` is the legacy AACR2 field. Records containing `260` are older, not wrong — do not
rewrite them purely to modernise, and do not create new ones.

**First indicator (sequence):** `#` not applicable · `2` interim · `3` current/latest.
**Second indicator (function):** `0` production (archival) · `1` **publication** · `2`
distribution · `3` manufacture · `4` copyright notice.

`$a` place · `$b` name · `$c` date.

```text
264 #1 $a New York : $b Lothrop, Lee & Shepard Books, $c 1987.
264 #4 $c c1987.
```

Two fields, two functions — which is the whole point of `264`. A `260` record collapsed both
dates into one `$c`.

## Worked conversion — catalog card to MARC

```text
599.74 ARN  Arnosky, Jim.
               Raccoons and ripe corn / Jim Arnosky. -- 1st ed. --
            New York : Lothrop, Lee & Shepard Books, c1987.
               25 p. : col. ill. ; 26 cm.
               Hungry raccoons feast at night in a field of ripe corn.
               ISBN 0-688-05455-2

            1. Raccoons.  I. Title.
```

| Tag | Ind | Subfields | Data | Why |
|---|---|---|---|---|
| 010 | `##` | `$a` | `87000123` | LC Control Number |
| 020 | `##` | `$a` | `0688054552` | ISBN, **no hyphens** |
| 100 | `1#` | `$a` | `Arnosky, Jim.` | Ind 1 `1` = single surname |
| 245 | `10` | `$a` `$c` | `Raccoons and ripe corn /` · `Jim Arnosky.` | Ind 1 `1` = title added entry; Ind 2 `0` = no filing characters skipped |
| 250 | `##` | `$a` | `1st ed.` | Edition |
| 264 | `#1` | `$a` `$b` `$c` | `New York :` · `Lothrop, Lee & Shepard Books,` · `1987.` | Ind 2 `1` = publication |
| 300 | `##` | `$a` `$b` `$c` | `25 p. :` · `col. ill. ;` · `26 cm.` | Extent / details / dimensions |
| 520 | `##` | `$a` | `Hungry raccoons feast at night...` | Summary |
| 650 | `#1` | `$a` | `Raccoons.` | Ind 2 `1` = LCSH for children's literature |
| 900 / 901 / 903 | `##` | `$a` | call number · barcode · price | Local (9XX) |

What to notice: the ISBN loses its hyphens; the two `0`/`1` second indicators mean unrelated
things because indicator values are defined per field; and the call number, barcode and price
are all 9XX because they are true for one library only.

## Validators

```ts
import { emit020, emit264, parseLeader, parse008, validateIndicators } from './marc-tools.ts';
```

`emit020` routes to `$a` or `$z` and builds `$q` with the correct separator and punctuation.
`validateIndicators` rejects an indicator pair passed as a two-digit string, and **refuses**
tags it does not document rather than silently passing them.

## Anti-Patterns

- **Reading an indicator pair as a two-digit number.**
- **Putting a set ISBN in `$a` on a single-volume record** — it collapses set searches.
- **Deleting one of a 10/13 ISBN pair** and reporting the record fixed.
- **Transcribing an unparseable value into `$z`** to make it disappear. `$z` is for cancelled
  and invalid ISBNs, not for junk.
- **Reading 008 positions 18–34 on a non-book record.** They are redefined per material type.
- **Inventing an authority heading** because the established form is inconvenient to look up.
- **Hand-assembling a communications-format record.** The Directory is rebuilt by the ILS on
  every edit; emit fields instead.
- **Asserting what a vendor's API returns.** That is a documentation or export question.
- **Treating a received MARC record as truth.** District cataloging quality varies; it is
  evidence, and needs the same provenance handling as anything else ingested.

## Output Format

- **"What does this field/indicator/subfield mean?"** → the meaning, the field it is scoped to,
  and the consequence of getting it wrong. Two or three sentences.
- **A record or card to convert** → a table of tag · indicators · subfields · data · why, in
  tag order, with local (9XX) fields marked as local.
- **A parsed Leader or 008** → named positions with their values in plain language, and an
  explicit note of which material type's definitions were used.
- **A field to emit** → the field in fenced `text`, punctuation included, exactly as it would
  appear.
- **Anything not covered** → *"I don't know — that's in <LC MARC 21 / OCLC BibFormats / the
  relevant authority file>"*, naming what it would settle. Never a guess.

## Authorities

| Authority | URL | Answers |
|---|---|---|
| LC MARC Standards | `https://www.loc.gov/marc/` | The primary specification — all official MARC 21 documentation |
| MARC 21 Concise Formats | LC Cataloging Distribution Service | Current editions plus the XML schemas |
| OCLC Bibliographic Formats and Standards | `https://www.oclc.org/bibformats/en.html` | Field-by-field input standards — indicators, repeatability, subfields |
| LC Name Authority File | `http://authorities.loc.gov/` | Established personal, corporate and meeting names |
| LCSH | LC Linked Data Service | Established topical and geographic headings |
| Sears List | commercial | The thesaurus many school and small public collections actually use |
| RDA Toolkit | `https://www.rdatoolkit.org/` | Subscription. The cataloging rules behind 264. |

The Library of Congress is entirely free and unauthenticated (SRU, full MARC). The OCLC
WorldCat **Metadata API needs paid membership**; its Entities API is free. Google Books and
OpenLibrary return LCCN and OCLC numbers free. **xISBN is retired.**
