/**
 * Tests for skills/isbn/isbn-tools.ts — the TypeScript twin of the upstream canonical
 * isbn_tools.py. Same cases, so the two ports cannot drift silently.
 *
 * Hermetic: pure functions, no DB, no env mutation, no filesystem.
 */

import { describe, expect, test } from 'bun:test';
import {
  CLASSES,
  IsbnError,
  type IsbnClass,
  checkDigit10,
  checkDigit13,
  classify,
  isbn10ToIsbn13,
  isbn13ToIsbn10,
  naive978PrefixRepair,
  normalize,
  sbnToIsbn10,
  splitConcatenated,
  splitIsbnRun,
  transpositionRisk,
  validateIsbn10,
  validateIsbn13,
} from '../skills/isbn/isbn-tools.ts';

describe('normalize', () => {
  test.each([
    ['978-0-306-40615-7', '9780306406157'],
    ['978 0 306 40615 7', '9780306406157'],
    ['ISBN 978-0-306-40615-7', '9780306406157'],
    ['ISBN-13: 9780306406157', '9780306406157'],
    ['0-8044-2957-X', '080442957X'],
    ['080442957x', '080442957X'],
    ['SBN 688054552', '688054552'],
    ['', ''],
  ])('strips formatting from %p', (raw, expected) => {
    expect(normalize(raw)).toBe(expected);
  });

  test('null and undefined are empty', () => {
    expect(normalize(null)).toBe('');
    expect(normalize(undefined)).toBe('');
  });
});

describe('check digits', () => {
  test('the worked example 978-0-306-40615-7', () => {
    expect(checkDigit13('978030640615')).toBe('7');
  });

  test('ISBN-10 X check digit', () => {
    expect(checkDigit10('080442957')).toBe('X');
  });

  test('rejects wrong length', () => {
    expect(() => checkDigit13('97803064061')).toThrow(IsbnError);
    expect(() => checkDigit10('08044295')).toThrow(IsbnError);
  });
});

describe('validation', () => {
  test.each(['9780306406157', '978-0-306-40615-7', '9791234567896'])('valid 13: %p', v => {
    expect(validateIsbn13(v)).toBe(true);
  });

  test.each([
    '9780306406158', // wrong check digit
    '1234567890123', // not a bookland prefix
    '978030640615', // too short
    '97803064061579', // too long
  ])('invalid 13: %p', v => {
    expect(validateIsbn13(v)).toBe(false);
  });

  test.each(['0688054552', '080442957X', '0-8044-2957-X'])('valid 10: %p', v => {
    expect(validateIsbn10(v)).toBe(true);
  });

  test.each(['0688054553', '0804429570', '068805455'])('invalid 10: %p', v => {
    expect(validateIsbn10(v)).toBe(false);
  });
});

describe('conversion', () => {
  test('10 to 13 and back round-trips', () => {
    const thirteen = isbn10ToIsbn13('0688054552');
    expect(thirteen).toBe('9780688054557');
    expect(isbn13ToIsbn10(thirteen)).toBe('0688054552');
  });

  test('X check digit round-trips', () => {
    const thirteen = isbn10ToIsbn13('080442957X');
    expect(validateIsbn13(thirteen)).toBe(true);
    expect(isbn13ToIsbn10(thirteen)).toBe('080442957X');
  });

  test('979 has no ISBN-10 — impossible, not unsupported', () => {
    expect(() => isbn13ToIsbn10('9791234567896')).toThrow(/no ISBN-10/);
  });

  test('rejects invalid input rather than converting it', () => {
    expect(() => isbn10ToIsbn13('0688054553')).toThrow(IsbnError);
    expect(() => isbn13ToIsbn10('9780306406158')).toThrow(IsbnError);
  });
});

describe('SBN zero-padding', () => {
  test('the worked example SBN 688054552', () => {
    expect(sbnToIsbn10('688054552')).toBe('0688054552');
  });

  test('rejects wrong length', () => {
    expect(() => sbnToIsbn10('0688054552')).toThrow(IsbnError);
  });

  test('rejects a value that does not pad to a valid ISBN-10', () => {
    expect(() => sbnToIsbn10('123456780')).toThrow(IsbnError);
  });
});

describe('splitConcatenated', () => {
  test.each([
    ['97816819180991681918099', '9781681918099', '1681918099'],
    ['97813680035441368003540', '9781368003544', '1368003540'],
    ['97815992886661599288664', '9781599288666', '1599288664'],
  ])('13-then-10 order: %p', (glued, thirteen, ten) => {
    expect(splitConcatenated(glued)).toEqual([thirteen, ten]);
  });

  test.each([
    ['00624458209780062445827', '9780062445827', '0062445820'],
    ['11019471369781101947135', '9781101947135', '1101947136'],
  ])('10-then-13 order also splits: %p', (glued, thirteen, ten) => {
    expect(splitConcatenated(glued)).toEqual([thirteen, ten]);
  });

  test('both halves are the same book', () => {
    const [thirteen, ten] = splitConcatenated('97816819180991681918099');
    expect(isbn10ToIsbn13(ten)).toBe(thirteen);
  });

  test('always returns 13 first regardless of storage order', () => {
    const a = splitConcatenated('97816819180991681918099');
    const b = splitConcatenated('00624458209780062445827');
    expect(a[0].length).toBe(13);
    expect(b[0].length).toBe(13);
    expect(a[1].length).toBe(10);
    expect(b[1].length).toBe(10);
  });

  test('refuses a run that is not exactly one 13 and one 10', () => {
    // Four ISBNs, not a pair — splitIsbnRun handles it, splitConcatenated will not
    // pretend it is a pair.
    expect(() =>
      splitConcatenated('0525476881978052547688797801424107070142410705'),
    ).toThrow(IsbnError);
  });

  test('the naive-978-prefix form raises with the repair named', () => {
    expect(() => splitConcatenated('04522644649780452264464')).toThrow(/naive-978-prefix/);
  });

  test('rejects wrong length', () => {
    expect(() => splitConcatenated('9780306406157')).toThrow(IsbnError);
  });
});

describe('naive978PrefixRepair', () => {
  test.each([
    ['9780452264464', '9780452264465'],
    ['9780688170528', '9780688170523'],
  ])('%p repairs to %p', (broken, correct) => {
    expect(naive978PrefixRepair(broken)).toBe(correct);
  });

  test('a valid ISBN-13 needs no repair', () => {
    expect(naive978PrefixRepair('9780306406157')).toBeNull();
  });

  test('a wrong ISBN-13 with no recoverable ISBN-10 is not this defect', () => {
    expect(naive978PrefixRepair('9780306406158')).toBeNull();
  });

  test('repairs the concatenated form too', () => {
    expect(naive978PrefixRepair('04522644649780452264464')).toBe('9780452264465');
  });

  test('a clean concatenation is not this defect', () => {
    expect(naive978PrefixRepair('00624458209780062445827')).toBeNull();
  });

  test('979 is never this defect', () => {
    expect(naive978PrefixRepair('9791234567890')).toBeNull();
  });
});

describe('transpositionRisk', () => {
  test('flags an adjacent pair differing by five', () => {
    expect(transpositionRisk('9780306406157')).toBe(true);
  });

  test('no risk when no adjacent pair differs by five', () => {
    expect(transpositionRisk('9781111111113')).toBe(false);
  });

  test('a non-ISBN-13 is not flagged', () => {
    expect(transpositionRisk('0688054552')).toBe(false);
  });
});

describe('classify', () => {
  test.each<[string, IsbnClass]>([
    ['9780306406157', 'valid_isbn13'],
    ['978-0-306-40615-7', 'valid_isbn13'],
    ['0688054552', 'valid_isbn10'],
    ['080442957X', 'valid_isbn10'],
    ['688054552', 'sbn9'],
    ['9780306406158', 'bad_check_digit'],
    ['9780452264464', 'naive_978_prefix'],
    ['04522644649780452264464', 'naive_978_prefix'],
    ['0688054553', 'bad_check_digit'],
    ['97816819180991681918099', 'concatenated_isbns'],
    ['00624458209780062445827', 'concatenated_isbns'],
    ['', 'not_an_isbn'],
    ['not a number at all', 'not_an_isbn'],
    ['12345', 'not_an_isbn'],
    ['1234567890123', 'not_an_isbn'],
  ])('%p is %p', (value, expected) => {
    expect(classify(value)).toBe(expected);
  });

  test.each(['8881234567890', '8881234567'])(
    'a placeholder prefix beats check-digit reporting: %p',
    v => {
      // 888 means NO ISBN. Reporting it as bad_check_digit loses that.
      expect(classify(v)).toBe('placeholder_888');
    },
  );

  test('every declared class is reachable', () => {
    // The taxonomy must have a slot for every shape, or classify() silently discards
    // repairable values. An earlier revision returned not_an_isbn for a naive-978
    // concatenation; a caller stopping at classify() would have binned it.
    const samples = [
      '9780306406157',
      '0688054552',
      '688054552',
      '8881234567890',
      '97816819180991681918099',
      '04522644649780452264464',
      '9780306406158',
      '',
    ];
    expect(new Set(samples.map(classify))).toEqual(new Set(CLASSES));
  });

  test('a repairable value is never reported as junk', () => {
    for (const v of ['9780452264464', '9780688170528', '04522644649780452264464']) {
      expect(classify(v)).toBe('naive_978_prefix');
      expect(naive978PrefixRepair(v)).not.toBeNull();
    }
  });
});

describe('splitIsbnRun', () => {
  // Concatenations are runs of N ISBNs, not only pairs. Values holding 2 to 14 ISBNs occur
  // in real data; a parser that only handles the 23-character pair reports the rest as junk.
  test.each([
    ['97816819180991681918099', ['9781681918099', '1681918099']],
    ['00624458209780062445827', ['0062445820', '9780062445827']],
    [
      '0525476881978052547688797801424107070142410705',
      ['0525476881', '9780525476887', '9780142410707', '0142410705'],
    ],
  ])('parses the run in %p', (glued, expected) => {
    expect(splitIsbnRun(glued as string)).toEqual(expected as string[]);
  });

  test('every recovered pair in a run is the same book', () => {
    const parts = splitIsbnRun('0525476881978052547688797801424107070142410705');
    const tens = parts.filter(p => p.length === 10).map(isbn10ToIsbn13);
    const thirteens = parts.filter(p => p.length === 13);
    expect(new Set(tens)).toEqual(new Set(thirteens));
  });

  test('a single ISBN is a run of one', () => {
    expect(splitIsbnRun('9780306406157')).toEqual(['9780306406157']);
  });

  test('a stall names the offset and the remainder', () => {
    // The parser never guesses past a stall — it says where it stopped so a person can
    // decide what the leftover is.
    expect(() => splitIsbnRun('978030640615700')).toThrow(/stalling at offset 13/);
  });

  test('allowPartial returns what was recovered', () => {
    expect(splitIsbnRun('978030640615700', true)).toEqual(['9780306406157']);
  });

  test('allowPartial on an unparseable head returns empty', () => {
    expect(splitIsbnRun('067187036067187229X', true)).toEqual([]);
  });

  test('empty input throws', () => {
    expect(() => splitIsbnRun('')).toThrow(IsbnError);
  });
});

describe('the module mints nothing', () => {
  test('exposes no ISBN generator', async () => {
    // failure-modes: never mint an ISBN-shaped value. If a generator ever appears in this
    // module, this is the test that should stop it.
    const mod = await import('../skills/isbn/isbn-tools.ts');
    const forbidden = Object.keys(mod).filter(
      n => /generate/i.test(n) || /\bmint/i.test(n),
    );
    expect(forbidden).toEqual([]);
  });
});
