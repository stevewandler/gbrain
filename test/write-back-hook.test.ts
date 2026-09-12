/**
 * Tests for the Claude Code write-back hook (hooks/write-back/).
 *
 * The hook's job is to make a session record exist without anyone remembering
 * to write one. What is tested here is therefore not "does it format markdown"
 * but the three properties the record is trusted on:
 *
 *   1. Durability — the record reaches disk before it is offered to the brain,
 *      and it only ever reaches the brain through `gbrain capture`. A write
 *      that exists in one place is not a write.
 *   2. No silent loss — a failed capture keeps the record and stays loud.
 *   3. No fabrication — sections the transcript cannot know say so.
 *
 * The hook's own `selftest` covers record shape (26 assertions over a
 * synthetic transcript); it is driven from here so a shape regression fails
 * the repo suite rather than waiting for someone to run it by hand.
 */

import { describe, expect, test, beforeEach, afterEach } from 'bun:test';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, readdirSync, existsSync, rmSync, chmodSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { execFileSync, spawnSync } from 'child_process';

const HOOK = join(import.meta.dir, '..', 'hooks', 'write-back', 'write_back_hook.py');

/** A transcript row set that exercises every extraction path. */
function transcriptLines(): string {
  const rows = [
    {
      type: 'user', isSidechain: false, timestamp: '2026-01-01T00:00:00Z',
      cwd: '/tmp/demo', gitBranch: 'demo/branch', promptSource: 'user',
      message: { role: 'user', content: 'Rebuild the importer and prove it works with a probe.' },
    },
    {
      type: 'assistant', isSidechain: false, timestamp: '2026-01-01T00:00:01Z',
      message: {
        model: 'test-model',
        content: [
          { type: 'text', text: 'On it.' },
          { type: 'tool_use', id: 'w1', name: 'Write', input: { file_path: '/tmp/demo/importer.ts' } },
          { type: 'tool_use', id: 'b1', name: 'Bash', input: { command: 'bun test test/importer.test.ts' } },
        ],
      },
    },
    {
      type: 'user', isSidechain: false, toolUseResult: { stdout: '3 pass', stderr: '' },
      message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'b1', content: '3 pass' }] },
    },
  ];
  return rows.map((r) => JSON.stringify(r)).join('\n') + '\n';
}

/** A stand-in `gbrain` that records its argv and answers like the real CLI. */
function fakeGbrain(dir: string, opts: { fail?: boolean } = {}): string {
  const bin = join(dir, 'gbrain');
  const argvLog = join(dir, 'argv.log');
  const body = opts.fail
    ? `#!/bin/sh\nprintf '%s\\n' "$*" >> ${argvLog}\necho "boom: connection refused" >&2\nexit 1\n`
    : `#!/bin/sh\nprintf '%s\\n' "$*" >> ${argvLog}\n`
      + `echo '{"slug":"ops/sessions/test","status":"created_or_updated","content_hash":"abc",`
      + `"written":true,"source_kind":"capture-cli","captured_at":"2026-01-01T00:00:00Z"}'\n`;
  writeFileSync(bin, body);
  chmodSync(bin, 0o755);
  return bin;
}

function runHook(
  args: string[],
  opts: { stdin?: string; env?: Record<string, string> } = {},
): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync('python3', [HOOK, ...args], {
    input: opts.stdin ?? '',
    encoding: 'utf8',
    env: { ...process.env, ...(opts.env ?? {}) },
  });
  return { status: result.status, stdout: result.stdout ?? '', stderr: result.stderr ?? '' };
}

describe('write-back hook', () => {
  let tmp: string;
  let state: string;
  let binDir: string;
  let transcript: string;

  beforeEach(() => {
    tmp = mkdtempSync(join(tmpdir(), 'write-back-'));
    state = join(tmp, 'state');
    binDir = join(tmp, 'bin');
    mkdirSync(binDir, { recursive: true });
    transcript = join(tmp, 'transcript.jsonl');
    writeFileSync(transcript, transcriptLines());
  });

  afterEach(() => {
    rmSync(tmp, { recursive: true, force: true });
  });

  function sessionEndPayload(sessionId = 'aaaaaaaa-1111-2222-3333-444444444444'): string {
    return JSON.stringify({
      session_id: sessionId,
      hook_event_name: 'SessionEnd',
      reason: 'other',
      cwd: '/tmp/demo',
      transcript_path: transcript,
    });
  }

  test('python3 is available (the hook is a python script)', () => {
    const probe = spawnSync('python3', ['--version'], { encoding: 'utf8' });
    expect(probe.status).toBe(0);
  });

  test('selftest passes — record shape and the stated guarantees hold', () => {
    const run = runHook(['selftest'], { env: { GBRAIN_WRITEBACK_HOME: state } });
    expect(run.stdout).toContain('all checks passed');
    expect(run.stdout).not.toContain('FAIL');
    expect(run.status).toBe(0);
  });

  test('reaches the brain only through `gbrain capture` — never an MCP write', () => {
    const bin = fakeGbrain(binDir);
    const run = runHook([], {
      stdin: sessionEndPayload(),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin },
    });
    expect(run.status).toBe(0);

    const argv = readFileSync(join(binDir, 'argv.log'), 'utf8');
    expect(argv).toContain('capture --file');
    expect(argv).toContain('--slug ops/sessions/');
    // The durability rule, asserted rather than trusted: an MCP page write
    // lands in one place only, so the hook must never reach for one.
    expect(argv).not.toContain('put_page');
    expect(argv).not.toContain('put-page');
    const source = readFileSync(HOOK, 'utf8');
    expect(source).not.toContain('put_page');
  });

  test('writes the record to disk BEFORE offering it to the brain', () => {
    // A capture that fails leaves the record behind. If the spool were written
    // after the capture, this file would not exist.
    const bin = fakeGbrain(binDir, { fail: true });
    runHook([], {
      stdin: sessionEndPayload(),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin },
    });
    const spooled = readdirSync(join(state, 'spool')).filter((f) => f.endsWith('.md'));
    expect(spooled.length).toBe(1);
    const body = readFileSync(join(state, 'spool', spooled[0]), 'utf8');
    expect(body).toContain('## Asked');
    expect(body).toContain('Rebuild the importer');
  });

  test('a failed capture is recorded, retried, and never silently dropped', () => {
    const failing = fakeGbrain(binDir, { fail: true });
    runHook([], {
      stdin: sessionEndPayload(),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: failing },
    });

    const ledger = readFileSync(join(state, 'ledger.jsonl'), 'utf8').trim().split('\n');
    const last = JSON.parse(ledger[ledger.length - 1]);
    expect(last.outcome).toBe('capture_failed');
    expect(last.error).toContain('connection refused');

    // The next session start says so out loud, in the session's own context.
    const start = runHook([], {
      stdin: JSON.stringify({ session_id: 's2', hook_event_name: 'SessionStart', source: 'startup' }),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: failing },
    });
    const announced = JSON.parse(start.stdout);
    expect(announced.hookSpecificOutput.hookEventName).toBe('SessionStart');
    expect(announced.hookSpecificOutput.additionalContext).toContain('pending capture');

    // And once the brain is reachable again, the backlog drains itself.
    const working = join(binDir, 'good');
    mkdirSync(working, { recursive: true });
    const good = fakeGbrain(working);
    const recovered = runHook([], {
      stdin: JSON.stringify({ session_id: 's3', hook_event_name: 'SessionStart', source: 'startup' }),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: good },
    });
    expect(recovered.stdout).toContain('captured on retry');
    expect(readdirSync(join(state, 'spool')).filter((f) => f.endsWith('.md')).length).toBe(0);
    expect(readdirSync(join(state, 'archive')).filter((f) => f.endsWith('.md')).length).toBe(1);
  });

  test('past the retry cap the record is parked, not deleted, and stays loud', () => {
    const failing = fakeGbrain(binDir, { fail: true });
    const env = { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: failing, GBRAIN_WRITEBACK_MAX_ATTEMPTS: '1' };
    runHook([], { stdin: sessionEndPayload(), env });
    const start = runHook([], {
      stdin: JSON.stringify({ session_id: 's2', hook_event_name: 'SessionStart', source: 'startup' }),
      env,
    });
    expect(start.stdout).toContain('NOT reaching the brain');
    expect(readdirSync(join(state, 'failed')).filter((f) => f.endsWith('.md')).length).toBe(1);

    // `status` exits non-zero in that state, so a wiring check can use it.
    const status = runHook(['status'], { env });
    expect(status.status).toBe(1);
  });

  test('Rejected/Open say "not recorded" rather than inventing content', () => {
    const bin = fakeGbrain(binDir);
    runHook([], { stdin: sessionEndPayload(), env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin } });
    const archived = readdirSync(join(state, 'archive')).filter((f) => f.endsWith('.md'));
    const body = readFileSync(join(state, 'archive', archived[0]), 'utf8');
    expect(body).toContain('## Rejected');
    expect(body).toContain('_Not recorded._');
    expect(body).toContain('none on rejected/open');
  });

  test('agent-recorded notes land in the record and are cleared after spooling', () => {
    const bin = fakeGbrain(binDir);
    const env = { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin };
    runHook(['note', '--rejected', 'dropped the queue approach: needs a schema change'], { env });
    runHook(['note', '--open', 'the pooler limit is still unverified'], { env });
    runHook([], { stdin: sessionEndPayload(), env });

    const archived = readdirSync(join(state, 'archive')).filter((f) => f.endsWith('.md'));
    const body = readFileSync(join(state, 'archive', archived[0]), 'utf8');
    expect(body).toContain('dropped the queue approach');
    expect(body).toContain('pooler limit is still unverified');
    expect(body).toContain('recorded on rejected/open (2 notes)');

    // Consumed, so the next session does not inherit them.
    expect(existsSync(join(state, 'notes', 'pending.jsonl'))).toBe(false);
  });

  test('credential-shaped strings are scrubbed on the way in', () => {
    const rows = [
      {
        type: 'user', isSidechain: false, timestamp: '2026-01-01T00:00:00Z', cwd: '/tmp/demo',
        message: { role: 'user', content: 'deploy with GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz01 please, it matters' },
      },
      {
        type: 'assistant', isSidechain: false,
        message: {
          model: 'm', content: [{
            type: 'tool_use', id: 'b1', name: 'Bash',
            input: { command: 'curl -H "Authorization: Bearer sk-live-abcdefghijklmnopqrs" https://x.test' },
          }],
        },
      },
    ];
    writeFileSync(transcript, rows.map((r) => JSON.stringify(r)).join('\n') + '\n');
    const bin = fakeGbrain(binDir);
    runHook([], { stdin: sessionEndPayload(), env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin } });
    const archived = readdirSync(join(state, 'archive')).filter((f) => f.endsWith('.md'));
    const body = readFileSync(join(state, 'archive', archived[0]), 'utf8');
    expect(body).not.toContain('ghp_abcdefghijklmnopqrstuvwxyz01');
    expect(body).not.toContain('sk-live-abcdefghijklmnopqrs');
    expect(body).toContain('[redacted');
  });

  test('a trivial session writes nothing at all', () => {
    writeFileSync(transcript, JSON.stringify({
      type: 'user', isSidechain: false, message: { role: 'user', content: 'thanks' },
    }) + '\n');
    const bin = fakeGbrain(binDir);
    runHook([], { stdin: sessionEndPayload(), env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin } });
    const ledger = readFileSync(join(state, 'ledger.jsonl'), 'utf8').trim().split('\n');
    expect(JSON.parse(ledger[ledger.length - 1]).outcome).toBe('skipped');
    expect(existsSync(join(binDir, 'argv.log'))).toBe(false);
  });

  test('never breaks a session: bad payload, missing transcript, no CLI all exit 0', () => {
    const env = { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: '/nonexistent/gbrain' };
    expect(runHook([], { stdin: 'not json at all', env }).status).toBe(0);
    expect(runHook([], { stdin: JSON.stringify({ hook_event_name: 'SessionEnd', session_id: 'x', transcript_path: '/nope' }), env }).status).toBe(0);
    expect(runHook([], { stdin: sessionEndPayload(), env }).status).toBe(0);
    // The last one had no CLI to call, so the record must still be spooled.
    expect(readdirSync(join(state, 'spool')).filter((f) => f.endsWith('.md')).length).toBe(1);
  });

  test('the kill switch is absolute', () => {
    const bin = fakeGbrain(binDir);
    const run = runHook([], {
      stdin: sessionEndPayload(),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin, GBRAIN_WRITEBACK_DISABLED: '1' },
    });
    expect(run.status).toBe(0);
    expect(existsSync(join(state, 'spool'))).toBe(false);
    expect(existsSync(join(binDir, 'argv.log'))).toBe(false);
  });

  test('unrelated hook events are a no-op', () => {
    const bin = fakeGbrain(binDir);
    runHook([], {
      stdin: JSON.stringify({ session_id: 'x', hook_event_name: 'PreToolUse', cwd: '/tmp/demo' }),
      env: { GBRAIN_WRITEBACK_HOME: state, GBRAIN_BIN: bin },
    });
    expect(existsSync(join(binDir, 'argv.log'))).toBe(false);
  });

  test('installer is idempotent and fully reversible', () => {
    const settings = join(tmp, 'settings.json');
    writeFileSync(settings, JSON.stringify({ model: 'sonnet', hooks: { Stop: [] } }, null, 2));
    const installer = join(import.meta.dir, '..', 'hooks', 'write-back', 'install.py');

    const before = readFileSync(settings, 'utf8');
    execFileSync('python3', [installer, '--settings', settings], { encoding: 'utf8' });
    const once = JSON.parse(readFileSync(settings, 'utf8'));
    expect(Object.keys(once.hooks)).toContain('SessionEnd');
    expect(Object.keys(once.hooks)).toContain('SessionStart');
    expect(Object.keys(once.hooks)).toContain('PreCompact');
    expect(once.model).toBe('sonnet');       // untouched keys survive
    expect(once.hooks.Stop).toEqual([]);     // untouched hooks survive

    execFileSync('python3', [installer, '--settings', settings], { encoding: 'utf8' });
    const twice = JSON.parse(readFileSync(settings, 'utf8'));
    expect(JSON.stringify(twice)).toBe(JSON.stringify(once));  // no duplicate entries

    execFileSync('python3', [installer, '--settings', settings, '--uninstall'], { encoding: 'utf8' });
    expect(JSON.parse(readFileSync(settings, 'utf8'))).toEqual(JSON.parse(before));
  });
});
