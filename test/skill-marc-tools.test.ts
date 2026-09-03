/**
 * Tests for skills/marc-records/marc-tools.ts — the TypeScript twin of the upstream
 * canonical marc_tools.py. Same cases, so the two ports cannot drift silently.
 *
 * Worked examples come from the MARC 21 field manual (the Arnosky catalog card and its
 * record); the routing and refusal cases come from the skill's Field 020 rules.
 *
 * Hermetic: pure functions, no DB, no env mutation, no filesystem.
 */

import { describe, expect, test } from 'bun:test';
import {
  MarcError,
  emit020,
  emit264,
  parse008,
  parseLeader,
  routeIsbnSubfield,
  validateIndicators,
} from '../skills/marc-records/marc-tools.ts';

describe('emit020', () => {
  test('strips hyphens — 0-688-05455-2 becomes 0688054552 in $a', () => {
    expect(emit020('0-688-05455-2')).toBe('020 ## $a 0688054552');
  });

  test('accepts an X check digit', () => {
    expect(emit020('0-8044-2957-X')).toBe('020 ## $a 080442957X');
  });

  test('a single qualifier gets one set of parentheses', () => {
    expect(emit020('9781498721271', ['pbk.'])).toBe('020 ## $a 9781498721271 $q (pbk.)');
  });

  test('multiple qualifiers share one paren, separated by space-semicolon-space', () => {
    expect(emit020('9781498721271', ['pbk.', 'v. 1'])).toBe(
      '020 ## $a 9781498721271 $q (pbk. ; v. 1)',
    );
  });

  test('invalid routes to $z — the set-collapsing prevention case', () => {
    expect(emit020('9781498721288', ['two-volume set'], true)).toBe(
      '020 ## $z 9781498721288 $q (two-volume set)',
    );
  });

  test('adds no trailing terminal punctuation', () => {
    expect(emit020('9780306406157').endsWith('.')).toBe(false);
  });

  test('empty qualifiers emit no $q', () => {
    expect(emit020('9780306406157', [])).not.toContain('$q');
  });

  test('rejects a value with no ISBN characters', () => {
    expect(() => emit020('---')).toThrow(MarcError);
  });
});

describe('emit264', () => {
  test('the manual publication example', () => {
    expect(emit264('New York', 'Lothrop, Lee & Shepard Books', '1987')).toBe(
      '264 #1 $a New York : $b Lothrop, Lee & Shepard Books, $c 1987.',
    );
  });

  test('the manual copyright-notice example', () => {
    expect(emit264(null, null, 'c1987', '#', '4')).toBe('264 #4 $c c1987.');
  });

  test('does not double ISBD punctuation already present', () => {
    expect(emit264('New York :', 'Lothrop, Lee & Shepard Books,', '1987.')).toBe(
      '264 #1 $a New York : $b Lothrop, Lee & Shepard Books, $c 1987.',
    );
  });

  test('place alone gets no trailing colon', () => {
    expect(emit264('New York', null, null, '#', '1')).toBe('264 #1 $a New York');
  });

  test('rejects an empty field', () => {
    expect(() => emit264()).toThrow(MarcError);
  });

  test('rejects an out-of-range second indicator', () => {
    expect(() => emit264('New York', 'A Publisher', '1987', '#', '7')).toThrow(MarcError);
  });
});

describe('validateIndicators', () => {
  test('245 14 — first indicator 1, second indicator 4, not fourteen', () => {
    expect(validateIndicators('245', '1', '4')).toEqual(['1', '4']);
  });

  test('rejects a pair passed as one two-digit string', () => {
    expect(() => validateIndicators('245', '14')).toThrow(/two-digit number/);
  });

  test('the two blank forms are interchangeable', () => {
    expect(validateIndicators('020', '#', '#')).toEqual(validateIndicators('020', ' ', ' '));
  });

  test('refuses an undocumented tag rather than silently passing it', () => {
    expect(() => validateIndicators('856', '4', '0')).toThrow(/not documented/);
  });

  test('rejects an out-of-range value', () => {
    expect(() => validateIndicators('100', '7', '#')).toThrow(MarcError);
  });
});

describe('routeIsbnSubfield', () => {
  test.each([
    ['valid_isbn13', 'a'],
    ['valid_isbn10', 'a'],
    ['sbn9', 'a'],
    ['bad_check_digit', 'z'],
    ['naive_978_prefix', 'z'],
    ['placeholder_888', null],
    ['not_an_isbn', null],
    ['concatenated_13_10', null],
  ])('%p routes to %p', (cls, expected) => {
    expect(routeIsbnSubfield(cls)).toBe(expected as 'a' | 'z' | null);
  });

  test('a set ISBN on a volume record goes to $z', () => {
    expect(routeIsbnSubfield('valid_isbn13', true)).toBe('z');
  });

  test('a placeholder is omitted, not transcribed into $z', () => {
    expect(routeIsbnSubfield('placeholder_888')).toBeNull();
  });

  test('an unknown class defaults to omission, never to $a', () => {
    expect(routeIsbnSubfield('something_new')).toBeNull();
  });
});

describe('parseLeader', () => {
  const LEADER = '00714cam a2200205 a 4500';

  test('documented positions', () => {
    const out = parseLeader(LEADER);
    expect(out.record_status).toBe('c');
    expect(out.type_of_record).toBe('a');
    expect(out.bibliographic_level).toBe('m');
    expect(out.indicator_count).toBe('2');
    expect(out.subfield_code_length).toBe('2');
    expect(out.is_marc21).toBe(true);
  });

  test('base address is five characters', () => {
    expect(parseLeader(LEADER).base_address_of_data.length).toBe(5);
  });

  test('rejects wrong length', () => {
    expect(() => parseLeader('00714cam a22')).toThrow(/24 characters/);
  });
});

describe('parse008', () => {
  // 40 characters: entered 870108, single date 1987, nyu, illustrations, eng.
  const FIELD = '870108s1987    nyua   j      000 0 eng d';

  test('the fixture really is 40 characters', () => {
    expect(FIELD.length).toBe(40);
  });

  test('documented positions', () => {
    const out = parse008(FIELD);
    expect(out.date_entered).toBe('870108');
    expect(out.date_1).toBe('1987');
    expect(out.place_of_publication).toBe('nyu');
    expect(out.language).toBe('eng');
    expect(out.target_audience).toBe('j');
  });

  test('undocumented positions are returned raw, not given invented labels', () => {
    expect(Object.keys(parse008(FIELD).undocumented).sort()).toEqual(['31_33', '38_39']);
  });

  test('declares the book assumption — 18-34 are material-type specific', () => {
    expect(parse008(FIELD).material_type_assumed).toBe('book');
  });

  test('rejects wrong length', () => {
    expect(() => parse008('870108s1987')).toThrow(/40 characters/);
  });
});

describe('the module assembles no record', () => {
  test('exposes no communications-format record builder', async () => {
    // The Directory is rebuilt by the ILS on every edit, so hand-assembling a record is a
    // mistake. If a builder ever appears here, this is the test that should stop it.
    const mod = await import('../skills/marc-records/marc-tools.ts');
    const forbidden = Object.keys(mod).filter(n =>
      /^(buildRecord|assemble|serializeRecord)/.test(n),
    );
    expect(forbidden).toEqual([]);
  });
});
