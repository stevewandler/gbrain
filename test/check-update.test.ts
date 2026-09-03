import { describe, test, expect } from 'bun:test';
import { parseSemver, isMinorOrMajorBump, extractChangelogBetween } from '../src/commands/check-update.ts';

/**
 * Emit a GitHub Actions error annotation.
 *
 * Annotations appear at the top of the job page AND are exposed through the
 * checks API, so unlike ordinary test output they survive log truncation and are
 * readable by tooling rather than only by a human with a browser.
 *
 * That is not a theoretical benefit here. GitHub's job-log API caps at roughly
 * 386 KB, which for the Test shards is about the last 74 seconds of a 140-second
 * run. This test executes in the first half, so its failure output has been past
 * the cap on every red run — which is a large part of why it stayed red for two
 * weeks without anyone being able to say what was wrong.
 *
 * No-op outside GitHub Actions, so local runs stay clean.
 */
function annotateCI(title: string, body: string): void {
  if (process.env.GITHUB_ACTIONS !== 'true') return;
  // Annotation messages are size-capped; keep well under it and keep the head of
  // the output, which is where a stray banner or stack trace would appear.
  const clipped = body.length > 3000 ? `${body.slice(0, 3000)}\n…truncated` : body;
  const escape = (v: string) =>
    v.replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A');
  process.stdout.write(`::error title=${escape(title)}::${escape(clipped)}\n`);
}

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
    // GBRAIN_SKIP_STARTUP_HOOKS drops the startup hook's detached
    // `spawn('gbrain', ...)`, which resolves a binary that is on a developer's
    // PATH and not on a runner's. That is NOT the cause of the CI failure — it
    // was ruled out by running with this set and seeing the same red — but a
    // unit test should not depend on it either way.
    const proc = Bun.spawn(['bun', 'run', 'src/cli.ts', 'check-update', '--json'], {
      cwd: new URL('..', import.meta.url).pathname,
      stdout: 'pipe',
      stderr: 'pipe',
      env: { ...process.env, GBRAIN_SKIP_STARTUP_HOOKS: '1' },
    });
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ]);

    const context = `exit=${exitCode}\n--- stdout ---\n${stdout}\n--- stderr ---\n${stderr}`;

    // Collect every problem before asserting, so the annotation below carries the
    // whole picture rather than only whichever expect() happened to fire first.
    const problems: string[] = [];
    if (exitCode !== 0) problems.push(`exit code was ${exitCode}, expected 0`);

    let output: Record<string, unknown> | undefined;
    try {
      output = JSON.parse(stdout) as Record<string, unknown>;
    } catch (err) {
      problems.push(`stdout is not parseable JSON: ${String(err)}`);
    }

    if (output) {
      for (const key of ['current_version', 'update_available', 'upgrade_command']) {
        if (!(key in output)) problems.push(`missing required field: ${key}`);
      }
      if (output.current_source !== 'package-json') {
        problems.push(`current_source was ${JSON.stringify(output.current_source)}`);
      }
      if (typeof output.update_available !== 'boolean') {
        problems.push(`update_available was ${typeof output.update_available}, expected boolean`);
      }
    }

    if (problems.length > 0) {
      annotateCI('check-update --json failed', `${problems.join('; ')}\n${context}`);
    }

    // The assertions themselves. Each carries the context too, for a local run
    // where the annotation is a no-op.
    expect(problems, context).toEqual([]);
  });
});
