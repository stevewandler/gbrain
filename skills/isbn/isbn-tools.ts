/**
 * ISBN validation, conversion, and triage — TypeScript port.
 *
 * Behavioural twin of the upstream canonical isbn_tools.py. The two are tested against the
 * same cases so the ports cannot drift silently.
 *
 * `classify()` is the entry point: it returns exactly one of eight classes, which is
 * every shape a real value in a book catalog takes.
 *
 * Standards: ISO 2108.
 */

/** A generated-ISBN prefix used by legacy bulk imports with no ISBN. Means "no ISBN". */
export const PLACEHOLDER_PREFIX = '888';

/** Under prefix 979, registration group 0 is reserved for ISMNs, not books. */
export const ISMN_PREFIX = '9790';

export const CLASSES = [
  'valid_isbn13',
  'valid_isbn10',
  'sbn9',
  'placeholder_888',
  'concatenated_isbns',
  'naive_978_prefix',
  'bad_check_digit',
  'not_an_isbn',
] as const;

export type IsbnClass = (typeof CLASSES)[number];

/** Raised for a conversion that is impossible rather than merely unsupported. */
export class IsbnError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'IsbnError';
  }
}

/**
 * Strip formatting and return the bare identifier.
 *
 * Removes hyphens, spaces and other punctuation, uppercases a trailing `x` (the ISBN-10
 * check digit for the value 10), and drops a leading ISBN/SBN label.
 */
export function normalize(value: string | null | undefined): string {
  if (value === null || value === undefined) return '';
  let s = String(value).trim().toUpperCase();
  s = s.replace(/^ISBN(?:-1[03])?[:\s]*/, '');
  s = s.replace(/^SBN[:\s]*/, '');
  s = s.replace(/[^0-9X]/g, '');
  // An X is only meaningful as the final character of an ISBN-10.
  if (s.slice(0, -1).includes('X')) {
    const tail = s.endsWith('X') ? 'X' : '';
    s = s.slice(0, -1).replace(/X/g, '') + tail;
  }
  return s;
}

/** Modulus-10 check digit for the first 12 digits of an ISBN-13. */
export function checkDigit13(first12: string): string {
  if (first12.length !== 12 || !/^\d{12}$/.test(first12)) {
    throw new IsbnError(`expected 12 digits, got ${JSON.stringify(first12)}`);
  }
  let total = 0;
  for (let i = 0; i < 12; i++) total += Number(first12[i]) * (i % 2 === 0 ? 1 : 3);
  const remainder = total % 10;
  return remainder === 0 ? '0' : String(10 - remainder);
}

/** Modulus-11 check digit for the first 9 digits of an ISBN-10. May be `X`. */
export function checkDigit10(first9: string): string {
  if (first9.length !== 9 || !/^\d{9}$/.test(first9)) {
    throw new IsbnError(`expected 9 digits, got ${JSON.stringify(first9)}`);
  }
  let total = 0;
  for (let i = 0; i < 9; i++) total += Number(first9[i]) * (10 - i);
  const remainder = (11 - (total % 11)) % 11;
  return remainder === 10 ? 'X' : String(remainder);
}

export function validateIsbn13(value: string): boolean {
  const s = normalize(value);
  if (s.length !== 13 || !/^\d{13}$/.test(s)) return false;
  if (!s.startsWith('978') && !s.startsWith('979')) return false;
  return checkDigit13(s.slice(0, 12)) === s[12];
}

export function validateIsbn10(value: string): boolean {
  const s = normalize(value);
  if (s.length !== 10 || !/^\d{9}$/.test(s.slice(0, 9))) return false;
  return checkDigit10(s.slice(0, 9)) === s[9];
}

/** Convert an ISBN-10 to its ISBN-13 form. Always possible. */
export function isbn10ToIsbn13(value: string): string {
  const s = normalize(value);
  if (!validateIsbn10(s)) throw new IsbnError(`not a valid ISBN-10: ${JSON.stringify(value)}`);
  const body = '978' + s.slice(0, 9);
  return body + checkDigit13(body);
}

/**
 * Convert an ISBN-13 back to its ISBN-10 form.
 *
 * Throws on any `979` prefix. **An ISBN beginning 979 has no 10-digit equivalent** — the
 * conversion is mathematically impossible, not merely discouraged, because the 979
 * registrant space was never allocated in the 10-digit scheme. Returning a
 * plausible-looking wrong answer would be worse than failing.
 */
export function isbn13ToIsbn10(value: string): string {
  const s = normalize(value);
  if (!validateIsbn13(s)) throw new IsbnError(`not a valid ISBN-13: ${JSON.stringify(value)}`);
  if (s.startsWith('979')) {
    throw new IsbnError(`${s} has no ISBN-10 equivalent: 979-prefixed ISBNs cannot be converted`);
  }
  const body = s.slice(3, 12);
  return body + checkDigit10(body);
}

/**
 * Convert a 9-digit Standard Book Number to an ISBN-10 by prepending a zero.
 *
 * Valid ONLY for SBNs from an English-speaking territory (US, UK, Canada, Australia, New
 * Zealand, South Africa, Zimbabwe). The caller owns that determination — this function
 * cannot tell territory from the digits. SBNs from elsewhere are routed to MARC `$z`.
 */
export function sbnToIsbn10(value: string): string {
  const s = normalize(value);
  if (s.length !== 9) throw new IsbnError(`expected a 9-digit SBN, got ${JSON.stringify(value)}`);
  const candidate = '0' + s;
  if (!validateIsbn10(candidate)) {
    throw new IsbnError(`${JSON.stringify(value)} does not zero-pad to a valid ISBN-10`);
  }
  return candidate;
}

/**
 * Split a run of concatenated ISBNs into the list of ISBNs it contains.
 *
 * A legacy import bug glues ISBNs together when a separator is not split. The result is
 * NOT always a pair: runs of 2 to 14 ISBNs occur in real data, mixing 13- and 10-digit
 * forms in either order. A parser that only handles the 23-character pair reports
 * everything longer as junk and discards it.
 *
 * The parse is greedy, left to right: take the next 13 characters if they are a valid
 * ISBN-13, else the next 10 if they are a valid ISBN-10, else stop. Preferring 13 is a
 * heuristic rather than a rule from the standard — it is what the real shapes require,
 * since an ISBN-13 begins 978/979 and an ISBN-10 starting with those digits would be
 * coincidence.
 *
 * **The parser never guesses past a stall.** When it cannot consume what comes next it
 * throws, naming the offset and the remainder, so a person decides what the leftover is.
 * Runs stall for several different reasons — a bad check digit mid-run, a stray leading
 * digit, a 9-digit SBN, a naive-978 half — and each needs a different answer. Pass
 * `allowPartial` to get what was recovered instead of the error; that is for triage
 * reporting, never for deciding what to write.
 */
export function splitIsbnRun(value: string, allowPartial = false): string[] {
  const s = normalize(value);
  if (!s) throw new IsbnError('nothing to split');
  const found: string[] = [];
  let i = 0;
  while (i < s.length) {
    if (i + 13 <= s.length && validateIsbn13(s.slice(i, i + 13))) {
      found.push(s.slice(i, i + 13));
      i += 13;
    } else if (i + 10 <= s.length && validateIsbn10(s.slice(i, i + 10))) {
      found.push(s.slice(i, i + 10));
      i += 10;
    } else {
      break;
    }
  }
  if (i === s.length && found.length > 0) return found;
  if (allowPartial) return found;
  const repair = naive978PrefixRepair(s);
  const hint = repair
    ? ` This is a naive-978-prefix defect: the ISBN-10 ${s.slice(0, 10)} is valid and the ` +
      `correct ISBN-13 is ${repair}. Use naive978PrefixRepair() to act on it deliberately ` +
      `rather than having it silently corrected here.`
    : '';
  throw new IsbnError(
    `could not parse ${JSON.stringify(value)} as a run of ISBNs: recovered ${found.length} ` +
      `before stalling at offset ${i}, remainder ${JSON.stringify(s.slice(i))}.${hint}`,
  );
}

/**
 * Split a 23-character ISBN-13+ISBN-10 concatenation into `[isbn13, isbn10]`.
 *
 * The pair case of {@link splitIsbnRun}, kept because it is the shape most callers mean
 * and a tuple is easier to use. Both halves refer to the same book.
 *
 * **Both orders occur** — 13-then-10 and 10-then-13 — and this always returns the pair as
 * `[isbn13, isbn10]` regardless of how it was stored. For anything longer than a pair, use
 * {@link splitIsbnRun}.
 */
export function splitConcatenated(value: string): [string, string] {
  const s = normalize(value);
  if (s.length !== 23) {
    throw new IsbnError(`expected 23 characters, got ${s.length}: ${JSON.stringify(value)}`);
  }
  const parts = splitIsbnRun(s);
  const thirteen = parts.find(p => p.length === 13);
  const ten = parts.find(p => p.length === 10);
  if (parts.length !== 2 || !thirteen || !ten) {
    throw new IsbnError(`${JSON.stringify(value)} is not one ISBN-13 and one ISBN-10`);
  }
  return [thirteen, ten];
}

/**
 * Return the correct ISBN-13 for a naive-978-prefix defect, or null.
 *
 * The defect: `978` was prefixed to a valid ISBN-10 while keeping the ISBN-10's Modulus-11
 * check digit instead of recomputing the Modulus-10 one. The underlying ISBN-10 is intact,
 * so the correct ISBN-13 is derivable by the standard conversion — this is converting a
 * number we hold, not minting one.
 *
 * Handles both the bare 13-character form and the 23-character concatenated form.
 * Returns null when the value is not this defect, including a wrong ISBN-13 with no
 * recoverable ISBN-10 inside it.
 */
export function naive978PrefixRepair(value: string): string | null {
  const s = normalize(value);
  if (s.length === 23 && /^\d{23}$/.test(s)) {
    // The concatenated form of the same defect.
    const ten = s.slice(0, 10);
    if (validateIsbn10(ten) && s.slice(10) === '978' + ten) return isbn10ToIsbn13(ten);
    return null;
  }
  if (s.length !== 13 || !/^\d{13}$/.test(s) || !s.startsWith('978')) return null;
  if (validateIsbn13(s)) return null; // already valid; nothing to repair
  const ten = s.slice(3);
  if (!validateIsbn10(ten)) return null;
  return isbn10ToIsbn13(ten);
}

/**
 * True if a Modulus-10 transposition error could be hiding in this ISBN-13.
 *
 * Under Mod-10, transposing two adjacent digits whose difference is exactly 5 leaves the
 * checksum unchanged, so validation cannot see the error. True does not mean the ISBN is
 * wrong — it means a passing check digit is not evidence that it is right.
 */
export function transpositionRisk(value: string): boolean {
  const s = normalize(value);
  if (s.length !== 13 || !/^\d{13}$/.test(s)) return false;
  for (let i = 0; i < 12; i++) {
    if (Math.abs(Number(s[i]) - Number(s[i + 1])) === 5) return true;
  }
  return false;
}

/**
 * Return exactly one of the eight classes in {@link CLASSES}.
 *
 * Order matters. Placeholder, concatenation and the naive-978 defect are all recognised
 * BEFORE plain check-digit validation, because each carries information the caller needs
 * in order to act — collapsing them into "bad check digit" or "not an ISBN" throws away a
 * repairable value. That is not hypothetical: an earlier revision returned `not_an_isbn`
 * for a naive-978 concatenation, so a caller that stopped at classify() would have
 * discarded a value whose correct ISBN-13 was fully derivable.
 */
export function classify(value: string | null | undefined): IsbnClass {
  const s = normalize(value);
  if (!s) return 'not_an_isbn';
  if (s.startsWith(PLACEHOLDER_PREFIX) && (s.length === 10 || s.length === 13)) {
    return 'placeholder_888';
  }
  if (s.length > 13) {
    try {
      if (splitIsbnRun(s).length >= 2) return 'concatenated_isbns';
    } catch {
      // fall through to the naive-978 check
    }
    // A run whose 13-digit half is a naive-978 defect still yields something usable;
    // it is not junk.
    if (naive978PrefixRepair(s) !== null) return 'naive_978_prefix';
    return 'not_an_isbn';
  }
  if (s.length === 13) {
    if (!/^\d{13}$/.test(s) || (!s.startsWith('978') && !s.startsWith('979'))) {
      return 'not_an_isbn';
    }
    if (validateIsbn13(s)) return 'valid_isbn13';
    return naive978PrefixRepair(s) ? 'naive_978_prefix' : 'bad_check_digit';
  }
  if (s.length === 10) {
    if (!/^\d{9}$/.test(s.slice(0, 9))) return 'not_an_isbn';
    return validateIsbn10(s) ? 'valid_isbn10' : 'bad_check_digit';
  }
  if (s.length === 9 && /^\d{9}$/.test(s)) {
    try {
      sbnToIsbn10(s);
      return 'sbn9';
    } catch {
      return 'not_an_isbn';
    }
  }
  return 'not_an_isbn';
}
