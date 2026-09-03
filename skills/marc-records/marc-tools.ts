/**
 * MARC 21 field emission and fixed-field parsing — TypeScript port.
 *
 * Behavioural twin of the upstream canonical marc_tools.py, tested against the same cases.
 *
 * This module deliberately does NOT assemble a full MARC communications record. The
 * Directory is rebuilt by cataloging software on every edit, so hand-assembling one is a
 * mistake; these functions emit fields and parse fixed-length blocks, and leave record
 * assembly to the ILS.
 */

/** How an undefined indicator position is written in documentation and display form. */
export const BLANK = '#';

/** Standard qualifier abbreviations for subfield $q. */
export const STANDARD_QUALIFIERS = ['pbk.', 'hbk.', 'ed.', 'v.', 'vol.', 'set'] as const;

export class MarcError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'MarcError';
  }
}

/**
 * Indicator definitions for the fields this skill documents. A field absent from this map
 * is not "anything goes" — it is unknown, and validateIndicators says so rather than
 * passing it.
 */
const INDICATOR_RULES: Record<string, [Set<string>, Set<string>]> = {
  '010': [new Set([' ', '#']), new Set([' ', '#'])],
  '020': [new Set([' ', '#']), new Set([' ', '#'])],
  '100': [new Set(['0', '1', '3']), new Set([' ', '#'])],
  '245': [new Set(['0', '1']), new Set('0123456789'.split(''))],
  '250': [new Set([' ', '#']), new Set([' ', '#'])],
  '260': [new Set([' ', '#', '2', '3']), new Set([' ', '#'])],
  '264': [new Set([' ', '#', '2', '3']), new Set(['0', '1', '2', '3', '4'])],
  '300': [new Set([' ', '#']), new Set([' ', '#'])],
  '520': [new Set([' ', '#', '0', '1', '2', '3', '4', '8']), new Set([' ', '#'])],
  '650': [new Set([' ', '#', '0', '1', '2']), new Set([...'01234567'.split(''), '8'])],
  '700': [new Set(['0', '1', '3']), new Set([' ', '#', '2'])],
};

function normIndicator(value: string | undefined | null): string {
  if (value === undefined || value === null || value === '') return ' ';
  const s = String(value);
  if (s.length !== 1) {
    throw new MarcError(
      `an indicator is one character, got ${JSON.stringify(value)} — indicators are never ` +
        `read as a two-digit number`,
    );
  }
  return s === '#' ? ' ' : s;
}

/**
 * Validate an indicator pair for a known tag; return the normalized pair.
 *
 * Rejects the classic error of passing an indicator pair as one two-digit string
 * (`validateIndicators('245', '14')`), and refuses to bless indicators for a tag this
 * skill does not document rather than silently allowing anything.
 */
export function validateIndicators(
  tag: string,
  ind1: string = '#',
  ind2: string = '#',
): [string, string] {
  const a = normIndicator(ind1);
  const b = normIndicator(ind2);
  const rules = INDICATOR_RULES[tag];
  if (!rules) {
    throw new MarcError(
      `indicator rules for tag ${tag} are not documented in this skill — check the LC ` +
        `MARC 21 format or OCLC BibFormats rather than guessing`,
    );
  }
  const [allowed1, allowed2] = rules;
  if (!allowed1.has(a)) {
    throw new MarcError(`${JSON.stringify(a)} is not a valid first indicator for tag ${tag}`);
  }
  if (!allowed2.has(b)) {
    throw new MarcError(`${JSON.stringify(b)} is not a valid second indicator for tag ${tag}`);
  }
  return [a, b];
}

/**
 * Return 'a', 'z', or null for a value, given its class from the isbn skill.
 *
 * null means the value does not belong in field 020 at all. A placeholder means "no ISBN",
 * and an unparseable value is not made to disappear by transcribing it into `$z`.
 */
export function routeIsbnSubfield(
  isbnClass: string,
  isSetIsbnOnVolumeRecord = false,
): 'a' | 'z' | null {
  if (isSetIsbnOnVolumeRecord) return 'z';
  const map: Record<string, 'a' | 'z' | null> = {
    valid_isbn13: 'a',
    valid_isbn10: 'a',
    // only after zero-padding, and only for English-speaking territories
    sbn9: 'a',
    bad_check_digit: 'z',
    placeholder_888: null,
    not_an_isbn: null,
    // split first, then route each half
    concatenated_13_10: null,
  };
  return isbnClass in map ? map[isbnClass] : null;
}

/** Build a $q value: one set of parentheses, ' ; ' between multiple qualifiers. */
function formatQualifiers(qualifiers: Iterable<string>): string {
  const items = [...qualifiers].map(q => (q ?? '').trim()).filter(q => q.length > 0);
  if (items.length === 0) return '';
  return '(' + items.join(' ; ') + ')';
}

/**
 * Emit a MARC 020 field.
 *
 * `isbn` is recorded without spaces, hyphens or punctuation. `invalid: true` routes it to
 * `$z` — for cancelled ISBNs, values that fail check-digit validation, and a set ISBN on a
 * single-volume record (application-invalid there, and it would otherwise collapse a
 * search for the set into one volume).
 *
 * No trailing terminal punctuation is added: 020 ends only in an abbreviation period,
 * hyphen, or closing parenthesis that is already part of the data.
 */
export function emit020(
  isbn: string,
  qualifiers: Iterable<string> = [],
  invalid = false,
): string {
  const bare = String(isbn ?? '')
    .replace(/[^0-9Xx]/g, '')
    .toUpperCase();
  if (!bare) throw new MarcError(`no ISBN characters in ${JSON.stringify(isbn)}`);
  validateIndicators('020', '#', '#');
  const code = invalid ? 'z' : 'a';
  const parts = [`$${code} ${bare}`];
  const q = formatQualifiers(qualifiers);
  if (q) parts.push(`$q ${q}`);
  return `020 ${BLANK}${BLANK} ` + parts.join(' ');
}

/**
 * Emit a MARC 264 field (RDA imprint) with ISBD punctuation.
 *
 * Second indicator: 0 production, 1 publication (the default), 2 distribution,
 * 3 manufacture, 4 copyright notice. A copyright notice normally carries only `$c`.
 */
export function emit264(
  place?: string | null,
  publisher?: string | null,
  date?: string | null,
  ind1 = '#',
  ind2 = '1',
): string {
  const [a, b] = validateIndicators('264', ind1, ind2);
  if (!place && !publisher && !date) {
    throw new MarcError('264 needs at least one of place, publisher, date');
  }
  const parts: string[] = [];
  if (place) {
    const p = place.replace(/[\s:]+$/, '');
    parts.push(publisher ? `$a ${p} :` : `$a ${p}`);
  }
  if (publisher) {
    const pub = publisher.replace(/[\s,]+$/, '');
    parts.push(date ? `$b ${pub},` : `$b ${pub}`);
  }
  if (date) {
    const d = String(date).trim();
    parts.push(d.endsWith('.') || d.endsWith('-') ? `$c ${d}` : `$c ${d}.`);
  }
  const disp1 = a === ' ' ? BLANK : a;
  const disp2 = b === ' ' ? BLANK : b;
  return `264 ${disp1}${disp2} ` + parts.join(' ');
}

/**
 * Leader positions this skill documents. Positions not listed are returned raw rather than
 * given invented labels.
 */
const LEADER_POSITIONS: Record<number, string> = {
  5: 'record_status',
  6: 'type_of_record',
  7: 'bibliographic_level',
  9: 'character_coding_scheme',
  10: 'indicator_count',
  11: 'subfield_code_length',
};

export interface ParsedLeader {
  [key: string]: string | boolean;
  base_address_of_data: string;
  raw: string;
  is_marc21: boolean;
}

/** Parse the 24-character Leader into its documented coded positions. */
export function parseLeader(leader: string): ParsedLeader {
  const s = String(leader ?? '');
  if (s.length !== 24) {
    throw new MarcError(`the Leader is exactly 24 characters, got ${s.length}`);
  }
  const out: Record<string, string | boolean> = {};
  for (const [pos, name] of Object.entries(LEADER_POSITIONS)) out[name] = s[Number(pos)];
  out.base_address_of_data = s.slice(12, 17);
  out.raw = s;
  // Both are fixed by the standard; a different value means the record is not MARC 21.
  out.is_marc21 = out.indicator_count === '2' && out.subfield_code_length === '2';
  return out as ParsedLeader;
}

/**
 * 008 positions for BOOKS (Leader/06 = language material). Other material types redefine
 * 18-34 entirely.
 */
const SLICES_008: Record<string, [number, number]> = {
  date_entered: [0, 6],
  date_type: [6, 7],
  date_1: [7, 11],
  date_2: [11, 15],
  place_of_publication: [15, 18],
  illustrations: [18, 22],
  target_audience: [22, 23],
  form_of_item: [23, 24],
  nature_of_contents: [24, 28],
  government_publication: [28, 29],
  conference_publication: [29, 30],
  festschrift: [30, 31],
  biography: [34, 35],
  language: [35, 38],
};

export interface Parsed008 {
  [key: string]: string | Record<string, string>;
  undocumented: Record<string, string>;
  raw: string;
  material_type_assumed: string;
}

/**
 * Parse the 40-character 008 field, using the BOOK definitions of 18-34.
 *
 * Positions this skill does not document are returned under `undocumented` as raw
 * characters rather than being given invented names.
 */
export function parse008(field: string): Parsed008 {
  const s = String(field ?? '');
  if (s.length !== 40) {
    throw new MarcError(`the 008 field is exactly 40 characters, got ${s.length}`);
  }
  const out: Record<string, string | Record<string, string>> = {};
  for (const [name, [a, b]] of Object.entries(SLICES_008)) out[name] = s.slice(a, b);
  out.undocumented = { '31_33': s.slice(31, 34), '38_39': s.slice(38, 40) };
  out.raw = s;
  out.material_type_assumed = 'book';
  return out as Parsed008;
}
