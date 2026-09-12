# Write-back hook — automatic session capture

A Claude Code hook that writes a record of every session into your brain,
through `gbrain capture`, with no habit to remember.

## The problem it solves

An agent session produces an artifact and loses the record. Whoever reads that
artifact next — you in a week, or an agent that was never in the room — gets
the output with no way to recover the intent behind it:

- what was actually asked, in the asker's own words
- what was tried and dropped, and why
- what is still open
- which check closes each claim

They reconstruct it from the artifact, and reconstruction is where they get it
wrong. A manual write-back habit closes the gap only on the days someone
remembers, which is the same as saying it closes on the easy days.

## The record

Five sections, one shape, every session:

| Section | Source | Can it be wrong? |
|---|---|---|
| **Asked** | Verbatim human prompts from the transcript | No — quoted, not summarised |
| **Did** | Tool-call ledger: files, commands, MCP calls, subagents | No — counted, not interpreted |
| **Rejected** | Agent-recorded notes only | Absent if nothing was recorded |
| **Open** | Agent-recorded notes only | Absent if nothing was recorded |
| **Evidence** | Verifying/publishing commands with the outcome the transcript recorded | Reports `unknown` when the outcome is unknown |

Plus **Commitments**, which appears only when something was detected, so its
presence is itself the signal.

Every record opens with a provenance line and a per-section confidence line:

```
high on asked/did/evidence (machine-derived, 182 transcript entries) ·
none on rejected/open (nothing recorded this session) ·
2 commitment candidates, unverified
```

That line is the point of the whole design. A record that cannot state its own
gaps gets trusted where it should not be. Rejected and Open are never inferred
from the output — the transcript cannot tell a considered-and-dropped approach
from one that was never tried, so when nothing was recorded the record says
`Not recorded` instead of guessing.

## Three guarantees

**1. Durability — a write that exists in one place is not a write.**
The record is written to disk *before* it is offered to the brain, and it
reaches the brain only through `gbrain capture` (database + disk mirror + git).
It never uses an MCP page write, which lands in one place and leaves nothing to
recover from. A test asserts the hook cannot even reach for one.

**2. No silent loss.**
A failed capture keeps the record in the spool and writes the failure to an
append-only ledger. The next session start retries it and reports the backlog
into the session. Past the retry cap the record is *parked, never deleted*, and
the warning gets louder:

```
N session record(s) exceeded 5 capture attempts and are parked in …
Write-back is NOT reaching the brain — investigate before trusting the
session history.
```

Auto-capture that fails quietly is worse than no auto-capture, because it is
trusted. `status` exits non-zero in that state so a scheduled wiring check can
use the exit code directly.

**3. It cannot break a session.**
Every failure path — unparseable payload, missing transcript, no CLI on PATH,
an internal bug — is recorded and exits 0. The one exception is `selftest`,
which exits non-zero on failure, because that is what it is for.

## Install

```bash
python3 hooks/write-back/install.py            # ~/.claude/settings.json
python3 hooks/write-back/install.py --dry-run  # print the result, write nothing
```

Registers three events, and nothing else in the settings file is touched:

| Event | Why |
|---|---|
| `SessionEnd` | The record. The hook's reason to exist. |
| `PreCompact` | A checkpoint onto the same slug, so a session killed after compaction still left a record. |
| `SessionStart` | Drains the retry spool and reports failures. This is what keeps a break from being silent. |

The installer backs up the settings file, writes atomically, and is idempotent:
running it twice changes nothing, and `--uninstall` restores the file to exactly
what it was. It never deletes spooled or archived records — those are not the
installer's to remove.

Then verify, before trusting it:

```bash
python3 hooks/write-back/write_back_hook.py selftest   # 26 checks, brain untouched
python3 hooks/write-back/write_back_hook.py status
```

The hook takes effect in the next session, not the one that installed it.

## Recording what the transcript cannot know

Rejected and Open come from the session, not from inference. Record them as
they happen:

```bash
python3 hooks/write-back/write_back_hook.py note --rejected "queue-based approach: needs a schema change"
python3 hooks/write-back/write_back_hook.py note --open    "pooler connection limit still unverified"
python3 hooks/write-back/write_back_hook.py note --commitment "numbers to Alice by Thursday"
```

Notes are consumed by the next write-back and cleared, so a note always belongs
to the session that recorded it. Nothing is lost if none are recorded — the
record simply says so, and says it in the confidence line too.

## Commitment detection

A commitment made inside a session is invisible to everything outside it. The
hook flags candidates from the human's own words, requiring **all three** in one
sentence: a first-person promise, a named counterparty reached through a
delivery verb, and a time reference.

Deliberately narrow. It will miss commitments rather than fill the record with
hedged guesses — precision over recall, because a false promise on a board is
worse than a missing one, and misses are recoverable at review. Model prose is
excluded entirely: an assistant saying "I'll run the tests" is not a promise
anyone made to anyone.

Candidates are labelled `detected, unverified`. They are inputs to review, not
facts.

## Operational notes

- **Slug.** `ops/sessions/YYYY-MM-DD-<session8>`, stable per session, so a
  `PreCompact` checkpoint and the final `SessionEnd` record land on the same
  page rather than making two. Change the namespace with
  `GBRAIN_WRITEBACK_SLUG_PREFIX`.
- **Trivial sessions write nothing.** No human prompts, or a very short prompt
  with no tool calls, and the hook skips — the brain does not fill with empty
  pages.
- **Secrets are scrubbed** on the way in: API keys, bearer tokens, connection
  strings, `*_TOKEN=` assignments. The record carries verbatim prompts and
  command lines into durable storage, so over-redaction is the cheap side to
  err on. Heredoc bodies are cut from commands for the same reason.
- **Source routing.** `gbrain capture` runs from the home directory on purpose:
  it resolves the source by walking up from the working directory, so running
  it inside a project would silently route session records into that project's
  source. Set `GBRAIN_WRITEBACK_SOURCE` to choose one deliberately.
- **`db_only` in the ledger** means the capture landed in the database with no
  disk mirror (usually no repo configured for the source). The archived record
  is then the only second copy there is, which is worth knowing rather than
  discovering later. `status` reports the count.

## Configuration

All environment variables, so it can be changed from a shell mid-incident.

| Variable | Default | Effect |
|---|---|---|
| `GBRAIN_WRITEBACK_DISABLED` | off | Kill switch: the hook does nothing at all |
| `GBRAIN_WRITEBACK_DRY_RUN` | off | Build and spool, never capture |
| `GBRAIN_WRITEBACK_HOME` | `~/.claude/write-back` | State directory |
| `GBRAIN_WRITEBACK_SLUG_PREFIX` | `ops/sessions` | Slug namespace |
| `GBRAIN_WRITEBACK_SOURCE` | (brain default) | Write under a named source |
| `GBRAIN_WRITEBACK_TIMEOUT` | `90` | Seconds allowed for `gbrain capture` |
| `GBRAIN_WRITEBACK_MAX_ATTEMPTS` | `5` | Retries before a record is parked |
| `GBRAIN_WRITEBACK_MIN_CHARS` | `80` | Trivial-session threshold |
| `GBRAIN_WRITEBACK_MAX_PROMPTS` | `40` | Prompt cap per record |
| `GBRAIN_BIN` | resolved | Explicit `gbrain` binary |

## State directory

```
~/.claude/write-back/
  spool/     records awaiting capture (with a .meta.json carrying slug + attempts)
  archive/   captured records — the local copy of what the brain now holds
  failed/    parked past the retry cap; never deleted
  notes/     agent-recorded rejected/open/commitment notes, pending consumption
  ledger.jsonl   append-only attempt log with the CLI's own receipts
```

The ledger records what was attempted and what came back. It is the hook's
evidence trail, not a status it wishes were true.

## Scheduled verification

`status` exits non-zero when write-back is not reaching the brain, so it drops
into a nightly wiring check as-is. See `wiring-check.json` for a ready-made
entry; adding a check to a gate that other decisions depend on is a change to
that gate, so install it deliberately rather than by default.

## Requirements

Python 3.9+ (standard library only) and the `gbrain` CLI on `PATH`. No
dependencies to install, so the hook cannot break on a dependency it does not
have.

## Tests

`test/write-back-hook.test.ts` — 14 tests covering the three guarantees, the
redaction pass, the kill switch, installer idempotency and reversibility, and
the hook's own 26-assertion `selftest`.
