import { describe, test, expect } from 'bun:test';
import {
  CHANGELOG_DIFF_MAX_CHARS,
  capChangelogDiff,
  extractChangelogBetween,
  isMinorOrMajorBump,
  parseSemver,
} from '../src/commands/check-update.ts';

describe('capChangelogDiff — the CI failure this test file exists to catch', () => {
  // CHANGELOG.md is ~2 MB and extractChangelogBetween captures every entry newer
  // than the running version, so a stale install produced a diff of hundreds of
  // kilobytes emitted as ONE JSON string on stdout. That payload truncated
  // mid-string in CI: exit code 0, unparseable JSON. Locally the upstream release
  // fetch returns nothing, changelog_diff is '', and the failure never appeared.
  test('leaves a normal diff untouched', () => {
    const small = '## [0.42.55.0] - 2026-09-04\n\n- something changed\n';
    expect(capChangelogDiff(small)).toBe(small);
  });

  test('a diff at exactly the cap is not truncated', () => {
    const exact = 'x'.repeat(CHANGELOG_DIFF_MAX_CHARS);
    expect(capChangelogDiff(exact)).toBe(exact);
  });

  test('an oversized diff is bounded and says so', () => {
    const huge = 'x'.repeat(500_000);
    const capped = capChangelogDiff(huge);
    expect(capped.length).toBeLessThan(huge.length);
    expect(capped).toContain('truncated');
    expect(capped).toContain('release_url');
  });

  test('the bound keeps a full --json payload comfortably parseable', () => {
    // The regression in one assertion: a payload built from a capped diff stays
    // small enough that stdout capture cannot truncate it mid-string.
    const payload = JSON.stringify(
      {
        current_version: '0.42.54.0',
        current_source: 'package-json',
        latest_version: '0.43.0.0',
        update_available: true,
        upgrade_command: 'gbrain upgrade',
        release_url: 'https://example.invalid/releases/latest',
        changelog_diff: capChangelogDiff('x'.repeat(2_000_000)),
        published_at: '2026-09-04T00:00:00Z',
      },
      null,
      2,
    );
    expect(payload.length).toBeLessThan(64_000);
    expect(() => JSON.parse(payload)).not.toThrow();
  });
});

describe('parseSemver', () => {
  test('parses standard version', () => {
    expect(parseSemver('0.4.0')).toEqual([0, 4, 0]);
  });

  test('strips v prefix', () => {
    expect(parseSemver('v0.5.0')).toEqual([0, 5, 0]);
  });

  test('returns null for malformed version', () => {
    expect(parseSemver('0.4')).toBeNull();
    expect(parseSemver('abc')).toBeNull();
    expect(parseSemver('')).toBeNull();
  });

  test('handles 4-part versions (takes first 3)', () => {
    expect(parseSemver('0.2.0.1')).toEqual([0, 2, 0]);
  });
});

describe('isMinorOrMajorBump', () => {
  test('0.4.0 vs 0.5.0 → update available (minor bump)', () => {
    expect(isMinorOrMajorBump('0.4.0', '0.5.0')).toBe(true);
  });

  test('0.4.0 vs 0.4.1 → NOT available (patch only)', () => {
    expect(isMinorOrMajorBump('0.4.0', '0.4.1')).toBe(false);
  });

  test('0.4.0 vs 1.0.0 → update available (major bump)', () => {
    expect(isMinorOrMajorBump('0.4.0', '1.0.0')).toBe(true);
  });

  test('0.4.0 vs 0.4.0 → NOT available (same version)', () => {
    expect(isMinorOrMajorBump('0.4.0', '0.4.0')).toBe(false);
  });

  test('0.4.0 vs 0.3.0 → NOT available (older)', () => {
    expect(isMinorOrMajorBump('0.4.0', '0.3.0')).toBe(false);
  });

  test('0.4.1 vs 0.5.0 → update available (minor bump, different patch)', () => {
    expect(isMinorOrMajorBump('0.4.1', '0.5.0')).toBe(true);
  });

  test('malformed version → returns false', () => {
    expect(isMinorOrMajorBump('0.4.0', 'abc')).toBe(false);
    expect(isMinorOrMajorBump('bad', '0.5.0')).toBe(false);
  });

  test('handles v prefix on latest', () => {
    expect(isMinorOrMajorBump('0.4.0', 'v0.5.0')).toBe(true);
  });
});

describe('extractChangelogBetween', () => {
  const changelog = `# Changelog

## [0.5.0] - 2026-05-01

### Added
- Feature X

## [0.4.1] - 2026-04-15

### Fixed
- Bug Y

## [0.4.0] - 2026-04-09

### Added
- Feature Z

## [0.3.0] - 2026-04-08

### Added
- Feature W
`;

  test('extracts entries between 0.4.0 and 0.5.0', () => {
    const result = extractChangelogBetween(changelog, '0.4.0', '0.5.0');
    expect(result).toContain('Feature X');
    expect(result).toContain('Bug Y');
    expect(result).not.toContain('Feature Z');
    expect(result).not.toContain('Feature W');
  });

  test('extracts only 0.5.0 when upgrading from 0.4.1', () => {
    const result = extractChangelogBetween(changelog, '0.4.1', '0.5.0');
    expect(result).toContain('Feature X');
    expect(result).not.toContain('Bug Y');
  });

  test('returns empty for same version', () => {
    const result = extractChangelogBetween(changelog, '0.5.0', '0.5.0');
    expect(result).toBe('');
  });

  test('returns empty for malformed from version', () => {
    const result = extractChangelogBetween(changelog, 'bad', '0.5.0');
    expect(result).toBe('');
  });

  test('does not capture older major versions incorrectly', () => {
    const crossMajor = `# Changelog

## [2.0.0] - 2026-06-01
### Added
- Major 2

## [0.5.0] - 2026-05-01
### Added
- Minor 5
`;
    const result = extractChangelogBetween(crossMajor, '1.2.0', '2.0.0');
    expect(result).toContain('Major 2');
    expect(result).not.toContain('Minor 5');
  });
});

describe('check-update CLI', () => {
  test('check-update is in CLI_ONLY set', async () => {
    const source = await Bun.file(
      new URL('../src/cli.ts', import.meta.url).pathname
    ).text();
    expect(source).toContain("'check-update'");
  });

  test('--help prints usage and exits 0', async () => {
    const proc = Bun.spawn(['bun', 'run', 'src/cli.ts', 'check-update', '--help'], {
      cwd: new URL('..', import.meta.url).pathname,
      stdout: 'pipe',
      stderr: 'pipe',
    });
    const stdout = await new Response(proc.stdout).text();
    const exitCode = await proc.exited;
    expect(stdout).toContain('check-update');
    expect(exitCode).toBe(0);
  });

  test('--json returns valid JSON with required fields', async () => {
    const proc = Bun.spawn(['bun', 'run', 'src/cli.ts', 'check-update', '--json'], {
      cwd: new URL('..', import.meta.url).pathname,
      stdout: 'pipe',
      stderr: 'pipe',
    });
    const stdout = await new Response(proc.stdout).text();
    const exitCode = await proc.exited;
    expect(exitCode).toBe(0);

    const output = JSON.parse(stdout);
    expect(output).toHaveProperty('current_version');
    expect(output).toHaveProperty('update_available');
    expect(output).toHaveProperty('upgrade_command');
    expect(output).toHaveProperty('current_source', 'package-json');
    expect(typeof output.update_available).toBe('boolean');
  });
});
