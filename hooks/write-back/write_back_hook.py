#!/usr/bin/env python3
"""write_back_hook.py — automatic session write-back from Claude Code into a brain.

WHY THIS EXISTS
An agent session produces an artifact and loses the record. Whoever reads it
next — a human a week later, or a synthesis agent that was never in the room —
gets the output with no way to recover the intent behind it: what was actually
asked, what was tried and dropped, what is still open, and which check closes
each claim. They reconstruct it from the artifact, and reconstruction is
exactly where they get it wrong.

Manual write-back closes that gap only on the days someone remembers. The fix
is a hook, not a better reminder.

WHAT IT GUARANTEES

1. Durability. The record is on disk BEFORE it is offered to the brain, and it
   reaches the brain through `gbrain capture` (database + disk mirror + git),
   never through an MCP write. A write that exists in one place is not a write.

2. No silent loss. A failed capture leaves the record in the spool and a row in
   the ledger; the next SessionStart retries it and tells the session a backlog
   exists. Auto-capture that fails quietly is worse than none at all, because
   it is trusted.

3. No fabrication. Asked / Did / Evidence are derived from the transcript and
   labelled as machine-derived. Rejected / Open are agent-recorded only — when
   nothing was recorded the record says "not recorded" instead of inferring.
   Every section names where it came from, and the header states its own
   confidence per section. Honest incompleteness beats confident guessing.

EVENTS (hook payload arrives as JSON on stdin)
  SessionEnd    build the record, spool it, capture it, drain the backlog
  PreCompact    checkpoint the same slug mid-session (crash insurance)
  SessionStart  drain the backlog and report failures back into the session

SUBCOMMANDS (argv, no stdin payload)
  note --rejected TEXT | --open TEXT | --commitment TEXT
                record a section the transcript cannot know
  flush         retry every spooled record
  status        pending / failed / last success, as JSON or text
  selftest      prove the wiring end to end without touching the brain

The hook never raises and never blocks a session: every failure path is
recorded and exits 0. `selftest` is the one exception — it exits non-zero on
failure, because that is the point of it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

HOOK_VERSION = 1

# ---------------------------------------------------------------------------
# Configuration. Every knob is an environment variable: a hook has no config
# file of its own, and an incident-time escape hatch has to work from a shell.
# ---------------------------------------------------------------------------

def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return default


DISABLED = _env_flag("GBRAIN_WRITEBACK_DISABLED")
DRY_RUN = _env_flag("GBRAIN_WRITEBACK_DRY_RUN")
STATE_HOME = Path(
    os.environ.get("GBRAIN_WRITEBACK_HOME")
    or (Path.home() / ".claude" / "write-back")
).expanduser()
SLUG_PREFIX = os.environ.get("GBRAIN_WRITEBACK_SLUG_PREFIX", "ops/sessions").strip("/")
CAPTURE_TIMEOUT = _env_int("GBRAIN_WRITEBACK_TIMEOUT", 90)
MAX_ATTEMPTS = _env_int("GBRAIN_WRITEBACK_MAX_ATTEMPTS", 5)
MIN_PROMPT_CHARS = _env_int("GBRAIN_WRITEBACK_MIN_CHARS", 80)
MAX_PROMPT_CHARS = _env_int("GBRAIN_WRITEBACK_MAX_PROMPT_CHARS", 1200)
MAX_PROMPTS = _env_int("GBRAIN_WRITEBACK_MAX_PROMPTS", 40)
MAX_EVIDENCE = _env_int("GBRAIN_WRITEBACK_MAX_EVIDENCE", 25)
MAX_COMMITMENTS = _env_int("GBRAIN_WRITEBACK_MAX_COMMITMENTS", 5)
SOURCE_ID = os.environ.get("GBRAIN_WRITEBACK_SOURCE", "").strip()

SPOOL_DIR = STATE_HOME / "spool"
ARCHIVE_DIR = STATE_HOME / "archive"
FAILED_DIR = STATE_HOME / "failed"
NOTES_DIR = STATE_HOME / "notes"
LEDGER = STATE_HOME / "ledger.jsonl"

# ---------------------------------------------------------------------------
# Redaction. The record carries verbatim prompts and command lines into a
# durable, git-backed store, so anything that looks like a credential is
# scrubbed on the way in. Over-redaction is cheap; a leaked token is not.
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"), "[redacted-api-key]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), "[redacted-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), "[redacted-aws-key]"),
    (re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), "[redacted-slack-token]"),
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-]{12,}"), r"\1[redacted]"),
    # postgres://user:password@host — the password only.
    (re.compile(r"(?i)\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^:/@\s]+:)[^@\s]+@"),
     r"\1[redacted]@"),
    # FOO_TOKEN=... / api_key: "..." — the value only.
    (re.compile(r"\b([A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Za-z0-9_]*\s*=\s*)\S+"),
     r"\1[redacted]"),
    (re.compile(r"(?i)\b((?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd)\s*[:=]\s*)"
                r"(['\"]?)[^\s'\"]{6,}\2"), r"\1[redacted]"),
]


def redact(text: str) -> str:
    """Scrub credential-shaped substrings. Applied to every field that can
    carry a command line, a URL, or free text."""
    if not text:
        return text
    out = text
    for pattern, replacement in SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dirs() -> None:
    for directory in (SPOOL_DIR, ARCHIVE_DIR, FAILED_DIR, NOTES_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def ledger_append(row: dict) -> None:
    """Append-only attempt log. This is the hook's own evidence trail: it
    records what was attempted and what came back, never a status it wishes
    were true."""
    try:
        ensure_dirs()
        row = {"ts": iso(now_utc()), "hook_version": HOOK_VERSION, **row}
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # A ledger that cannot be written must not take the session with it.
        pass


def ledger_rows(limit: int = 500) -> list[dict]:
    if not LEDGER.exists():
        return []
    rows: list[dict] = []
    try:
        with LEDGER.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:]


def truncate(text: str, limit: int, marker: str = " …[truncated]") -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + marker


def find_gbrain() -> str | None:
    """Resolve the CLI. Explicit override first, then PATH, then the two
    install locations a hook is most likely to run without a login shell's
    PATH (launchd, a GUI-spawned session)."""
    override = os.environ.get("GBRAIN_BIN", "").strip()
    if override:
        return override if Path(override).exists() else None
    found = shutil.which("gbrain")
    if found:
        return found
    for candidate in (
        Path.home() / ".bun" / "bin" / "gbrain",
        Path("/usr/local/bin/gbrain"),
        Path("/opt/homebrew/bin/gbrain"),
    ):
        if candidate.exists():
            return str(candidate)
    return None


# ---------------------------------------------------------------------------
# Transcript parsing
#
# Shapes below are what the transcript JSONL actually contains, verified
# against real session files rather than assumed:
#   - a human turn is  type=user, message.content is a string (or text blocks),
#     no `toolUseResult` key, isSidechain false
#   - a tool return is type=user WITH `toolUseResult` and tool_result blocks
#   - a model turn is  type=assistant, message.content holds text and tool_use
#   - subagent turns carry isSidechain=true and are counted, never quoted as
#     something the human asked
# ---------------------------------------------------------------------------

TOOL_WRITE = {"Write", "Edit", "NotebookEdit", "MultiEdit"}
TOOL_READ = {"Read", "Glob", "Grep", "LS", "ToolSearch", "NotebookRead"}

# A command is treated as evidence when it verifies or publishes something —
# the checks a reader would want to see attached to a claim.
EVIDENCE_COMMAND = re.compile(
    r"(?:^|[;&|]\s*)(?:[A-Za-z0-9_]+=\S+\s+)*"
    r"(?P<cmd>bun\s+(?:test|run)|npm\s+(?:test|run)|pnpm\s+(?:test|run)|yarn\s+(?:test|run)"
    r"|pytest|cargo\s+(?:test|build)|go\s+test|make\s+\w+"
    r"|git\s+(?:commit|push|tag)|gh\s+(?:pr|release)|glab\s+"
    r"|gbrain\s+(?:doctor|capture|put|integrity|eval|search|sources)"
    r"|psql|curl|http|kubectl|terraform\s+(?:plan|apply)|docker\s+(?:build|compose)"
    # Local probes: ./something-selftest, scripts/check-*.sh, ./probe.py
    r"|\.?/?\S*(?:selftest|self-test|smoke|probe)\S*|\S*check-[\w.-]+\.(?:sh|py|mjs|ts))",
    re.IGNORECASE,
)


def clean_command(raw: str) -> str:
    """Collapse a Bash command to the part that is actually a command.

    A heredoc body is data, not a command: leaving it attached both pastes a
    whole file into the record and lets its contents false-match as evidence
    (a heredoc containing the text `gbrain capture` is not a capture)."""
    cut = raw.split("<<", 1)[0] if "<<" in raw else raw
    collapsed = " ".join(cut.split())
    if not collapsed:
        collapsed = " ".join(raw.split())
    return collapsed


def load_transcript(path: str | None) -> list[dict]:
    if not path:
        return []
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return []
        rows: list[dict] = []
        with target.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a partially flushed last line is normal
        return rows
    except OSError:
        return []


def strip_injected(text: str) -> str:
    """Drop harness-injected context from what we quote as the human's words.
    A system-reminder is not something anyone asked for."""
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.DOTALL)
    text = re.sub(r"<local-command-stdout>.*?</local-command-stdout>", "", text, flags=re.DOTALL)
    return text.strip()


def block_text(content) -> str:
    """Text of a message body, whether it is a bare string or a block list.
    Returns '' when the body is a tool return rather than prose."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return ""  # tool return, not a human turn
    parts = [
        b.get("text", "")
        for b in content
        if isinstance(b, dict) and b.get("type") == "text"
    ]
    return "\n".join(p for p in parts if p)


def parse_session(rows: list[dict]) -> dict:
    """Reduce a transcript to the facts the record is built from. Pure
    extraction — no inference, no summarising."""
    prompts: list[dict] = []
    assistant_texts: list[str] = []
    tool_calls: list[dict] = []
    results: dict[str, dict] = {}
    sidechain_turns = 0
    models: dict[str, int] = {}
    git_branch = ""
    cwd = ""
    first_ts = ""
    last_ts = ""

    for row in rows:
        row_type = row.get("type")
        ts = row.get("timestamp") or ""
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        git_branch = row.get("gitBranch") or git_branch
        cwd = row.get("cwd") or cwd

        if row.get("isSidechain"):
            if row_type == "assistant":
                sidechain_turns += 1
            # Subagent prompts are the orchestrator talking to itself. Counted,
            # never quoted as something the human asked for.
            continue

        message = row.get("message") or {}

        if row_type == "user":
            if "toolUseResult" in row:
                # Tool return. Index it by tool_use_id so Evidence can report
                # the outcome of a check rather than only that it was run.
                content = message.get("content")
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            results[str(block.get("tool_use_id"))] = {
                                "is_error": bool(block.get("is_error")),
                                "raw": row.get("toolUseResult"),
                            }
                continue
            text = strip_injected(block_text(message.get("content")))
            if text:
                prompts.append({"ts": ts, "text": text})
            continue

        if row_type == "assistant":
            model = message.get("model")
            if model:
                models[model] = models.get(model, 0) + 1
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text"):
                    assistant_texts.append(block["text"])
                elif block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": str(block.get("id")),
                        "name": block.get("name") or "?",
                        "input": block.get("input") or {},
                    })

    return {
        "prompts": prompts,
        "assistant_texts": assistant_texts,
        "tool_calls": tool_calls,
        "results": results,
        "sidechain_turns": sidechain_turns,
        "models": models,
        "git_branch": git_branch,
        "cwd": cwd,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "entries": len(rows),
    }


def result_outcome(results: dict, tool_id: str) -> str:
    """'failed' / 'ok' / 'unknown' for a tool call. The block-level is_error
    flag is authoritative; the string form of an MCP error is the fallback."""
    entry = results.get(tool_id)
    if entry is None:
        return "unknown"
    if entry.get("is_error"):
        return "failed"
    raw = entry.get("raw")
    if isinstance(raw, str) and raw.lstrip().lower().startswith("error"):
        return "failed"
    if isinstance(raw, dict):
        if raw.get("interrupted"):
            return "failed"
    return "ok"


# ---------------------------------------------------------------------------
# Commitment detection (the fast path)
#
# Deliberately narrow: a first-person promise, a named counterparty reached
# through a delivery verb, and a time reference, all in one sentence. It will
# miss commitments rather than flood the record with hedged guesses. Misses
# are recoverable at review; a board full of false promises is not.
# ---------------------------------------------------------------------------

FIRST_PERSON = re.compile(r"\b(?:I|I'?ll|I'?m|we|we'?ll|my|our)\b", re.IGNORECASE)
DELIVERY = re.compile(
    r"\b(?:promised|promise|owe|send|sending|get|give|share|deliver|report back"
    r"|follow(?:ing)? up|circle back|ship|email|call)\b\s+(?:back\s+)?(?:to\s+|with\s+|for\s+)?"
    r"(?P<who>@[A-Za-z0-9._-]{2,}|[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)",
)
TIME_REF = re.compile(
    r"\b(?:today|tonight|tomorrow|this (?:morning|afternoon|evening|week|month|quarter)"
    r"|next (?:week|month|quarter|Monday|Tuesday|Wednesday|Thursday|Friday)"
    r"|by (?:EOD|EOW|COB|end of (?:day|week|month)|noon|tonight|tomorrow|Monday|Tuesday|Wednesday|Thursday|Friday)"
    r"|on (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"|in \d+ (?:hours?|days?|weeks?)|\b\d{1,2}/\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b)",
    re.IGNORECASE,
)
# Capitalised words that are never a counterparty.
NOT_A_NAME = {
    "The", "This", "That", "These", "Those", "There", "Then", "They", "Them",
    "You", "Your", "Yours", "And", "But", "For", "With", "From", "Into", "Its",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Today", "Tomorrow",
    "Tonight", "Also", "Just", "Only", "Please", "Note", "Done", "Now", "Next",
    "First", "Last", "Both", "Here", "How", "What", "When", "Where", "Which",
    "Why", "Who", "Not", "None", "Yes", "No", "Ok", "Okay",
}

SENTENCE_SPLIT = re.compile(r"(?<=[.!?;\n])\s+")


def detect_commitments(texts: list[str]) -> list[str]:
    """Candidate deadline-bearing promises. Returned as candidates for review,
    never as established facts."""
    hits: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for sentence in SENTENCE_SPLIT.split(text or ""):
            sentence = " ".join(sentence.split())
            if not (12 <= len(sentence) <= 400):
                continue
            if not FIRST_PERSON.search(sentence) or not TIME_REF.search(sentence):
                continue
            match = DELIVERY.search(sentence)
            if not match:
                continue
            who = match.group("who").strip()
            if not who.startswith("@") and who.split()[0] in NOT_A_NAME:
                continue
            # A counterparty that opens the sentence is usually a subject, not
            # a recipient ("Charlie asked for…" is not a promise to Charlie).
            if sentence.startswith(who):
                continue
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            hits.append(sentence)
            if len(hits) >= MAX_COMMITMENTS:
                return hits
    return hits


# ---------------------------------------------------------------------------
# Agent-recorded notes — the only source for Rejected / Open
# ---------------------------------------------------------------------------

def notes_path(session_id: str | None) -> Path:
    """Notes are keyed by session when the session id is known, and land in a
    shared pending file when it is not (a `note` call from a tool has no hook
    payload). Both are consumed and cleared by the next write-back, so a note
    always belongs to the session that recorded it."""
    if session_id:
        return NOTES_DIR / f"{session_id}.jsonl"
    return NOTES_DIR / "pending.jsonl"


def note_append(kind: str, text: str, session_id: str | None) -> Path:
    ensure_dirs()
    target = notes_path(session_id)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"ts": iso(now_utc()), "kind": kind, "text": text}, ensure_ascii=False,
        ) + "\n")
    return target


def notes_consume(session_id: str | None) -> tuple[dict[str, list[str]], list[Path]]:
    """Read this session's notes plus any unkeyed pending notes. Returns the
    grouped notes and the files to clear once the record is safely spooled."""
    grouped: dict[str, list[str]] = {"rejected": [], "open": [], "commitment": []}
    consumed: list[Path] = []
    candidates = [notes_path(None)]
    if session_id:
        candidates.append(notes_path(session_id))
    for path in candidates:
        if not path.exists():
            continue
        consumed.append(path)
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = str(row.get("kind", "")).lower()
                text = str(row.get("text", "")).strip()
                if kind in grouped and text:
                    grouped[kind].append(text)
        except OSError:
            continue
    return grouped, consumed


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------

def summarise_actions(parsed: dict) -> dict:
    """Fold the tool-call list into the Did ledger. Counts and names only —
    what happened, not what it meant."""
    files: list[str] = []
    commands: list[dict] = []
    mcp_servers: dict[str, int] = {}
    reads = 0
    subagents = 0
    other: dict[str, int] = {}

    for call in parsed["tool_calls"]:
        name = call["name"]
        args = call["input"] if isinstance(call["input"], dict) else {}
        if name in TOOL_WRITE:
            path = args.get("file_path") or args.get("notebook_path") or ""
            if path and path not in files:
                files.append(path)
        elif name == "Bash":
            command = clean_command(str(args.get("command", "")))
            if command:
                commands.append({
                    "command": command,
                    "outcome": result_outcome(parsed["results"], call["id"]),
                })
        elif name in TOOL_READ:
            reads += 1
        elif name in ("Task", "Agent"):
            subagents += 1
        elif name.startswith("mcp__"):
            server = name.split("__")[1] if "__" in name else name
            mcp_servers[server] = mcp_servers.get(server, 0) + 1
        else:
            other[name] = other.get(name, 0) + 1

    return {
        "files": files,
        "commands": commands,
        "mcp_servers": mcp_servers,
        "reads": reads,
        "subagents": subagents,
        "other": other,
    }


def pick_evidence(commands: list[dict]) -> list[dict]:
    """Commands that verify or publish something, with the outcome the
    transcript recorded. Evidence is a check plus its result — a command with
    an unknown outcome is reported as unknown, not as a pass."""
    evidence: list[dict] = []
    seen: set[str] = set()
    for entry in commands:
        command = entry["command"]
        if not EVIDENCE_COMMAND.search(command):
            continue
        key = command[:160]
        if key in seen:
            continue
        seen.add(key)
        evidence.append(entry)
        if len(evidence) >= MAX_EVIDENCE:
            break
    return evidence


def confidence_line(parsed: dict, notes: dict, commitments: list[str], transcript_ok: bool) -> str:
    """Per-section freshness, stated up front. The record's trustworthiness
    comes from being honest about what it does not contain."""
    if not transcript_ok:
        machine = "none on asked/did/evidence (transcript unreadable)"
    else:
        machine = (
            f"high on asked/did/evidence (machine-derived, {parsed['entries']} transcript entries)"
        )
    recorded = len(notes["rejected"]) + len(notes["open"])
    if recorded:
        agent = f"recorded on rejected/open ({recorded} note{'s' if recorded != 1 else ''})"
    else:
        agent = "none on rejected/open (nothing recorded this session)"
    commit = (
        f"{len(commitments)} commitment candidate{'s' if len(commitments) != 1 else ''}, unverified"
        if commitments else "no commitment candidates detected"
    )
    return f"{machine} · {agent} · {commit}"


def build_record(payload: dict, parsed: dict, notes: dict, transcript_ok: bool) -> dict:
    """Assemble the five-section record. Returns the slug, the markdown, and
    the facts the caller needs for the ledger."""
    session_id = str(payload.get("session_id") or "unknown")
    short = session_id.replace("-", "")[:8] or "unknown"
    event = str(payload.get("hook_event_name") or "manual")
    cwd = str(payload.get("cwd") or parsed.get("cwd") or os.getcwd())
    project = Path(cwd).name or "session"
    when = now_utc()
    date = when.strftime("%Y-%m-%d")
    slug = f"{SLUG_PREFIX}/{date}-{short}"

    actions = summarise_actions(parsed)
    evidence = pick_evidence(actions["commands"])
    prompts = parsed["prompts"][:MAX_PROMPTS]
    dropped_prompts = max(0, len(parsed["prompts"]) - len(prompts))

    # Commitments: what the agent recorded explicitly, plus narrow detection
    # over the human's own words. Model prose is excluded — a model saying
    # "I'll run the tests" is not a commitment anyone made to anyone.
    detected = detect_commitments([p["text"] for p in prompts])
    commitments = [f"{c} _(agent-recorded)_" for c in notes["commitment"]]
    commitments += [f"{c} _(detected, unverified)_" for c in detected]
    commitments = commitments[:MAX_COMMITMENTS + len(notes["commitment"])]

    tags = ["ops", "session-record", "write-back", "claude-code"]
    if commitments:
        tags.append("commitment-flag")

    title = f"Session record — {date} — {project}"

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(
        f"**Provenance.** Written by the write-back hook (v{HOOK_VERSION}) at "
        f"`{event}`, from session `{session_id}` in `{cwd}`"
        + (f" on branch `{parsed['git_branch']}`" if parsed["git_branch"] else "")
        + "."
    )
    lines.append("")
    lines.append(f"**Confidence.** {confidence_line(parsed, notes, commitments, transcript_ok)}")
    lines.append("")

    # 1. Asked — verbatim, because the whole point is not paraphrasing intent.
    lines.append(f"## Asked ({len(parsed['prompts'])})")
    lines.append("")
    lines.append("_Verbatim from the transcript. Harness-injected context removed._")
    lines.append("")
    if prompts:
        for i, prompt in enumerate(prompts, start=1):
            body = redact(truncate(prompt["text"], MAX_PROMPT_CHARS))
            quoted = "\n".join(f"> {ln}" if ln.strip() else ">" for ln in body.splitlines())
            stamp = f" _({prompt['ts']})_" if prompt["ts"] else ""
            lines.append(f"**{i}.**{stamp}")
            lines.append("")
            lines.append(quoted)
            lines.append("")
        if dropped_prompts:
            lines.append(f"_{dropped_prompts} earlier prompt(s) omitted at the {MAX_PROMPTS}-prompt cap._")
            lines.append("")
    else:
        lines.append("_No human prompts found in the transcript._")
        lines.append("")

    # 2. Did — the action ledger, counts and names.
    lines.append("## Did")
    lines.append("")
    lines.append("_Tool-call ledger, machine-derived. Actions taken, not outcomes claimed._")
    lines.append("")
    if actions["files"]:
        lines.append(f"- **Files written via Write/Edit ({len(actions['files'])}):**")
        for path in actions["files"][:40]:
            lines.append(f"  - `{path}`")
        if len(actions["files"]) > 40:
            lines.append(f"  - _…{len(actions['files']) - 40} more_")
    elif actions["commands"]:
        # Precision about the instrument: the ledger sees tool calls, so a file
        # written by a shell command is invisible here. Say that, rather than
        # reporting "no files" and being wrong.
        lines.append(
            "- No Write/Edit tool calls. Files may still have been written by "
            "the commands below — the tool ledger cannot see inside a shell."
        )
    else:
        lines.append("- No files written or edited.")
    if actions["commands"]:
        failed = sum(1 for c in actions["commands"] if c["outcome"] == "failed")
        lines.append(
            f"- **Commands run:** {len(actions['commands'])}"
            + (f" ({failed} returned an error)" if failed else "")
        )
    if actions["mcp_servers"]:
        detail = ", ".join(f"{k} ×{v}" for k, v in sorted(actions["mcp_servers"].items()))
        lines.append(f"- **MCP calls:** {detail}")
    if actions["reads"]:
        lines.append(f"- **Reads / searches:** {actions['reads']}")
    if actions["subagents"] or parsed["sidechain_turns"]:
        lines.append(
            f"- **Subagents:** {actions['subagents']} launched, "
            f"{parsed['sidechain_turns']} subagent turns"
        )
    if actions["other"]:
        detail = ", ".join(f"{k} ×{v}" for k, v in sorted(actions["other"].items()))
        lines.append(f"- **Other tools:** {detail}")
    if parsed["models"]:
        detail = ", ".join(f"{k} ×{v}" for k, v in sorted(parsed["models"].items()))
        lines.append(f"- **Models:** {detail}")
    lines.append("")

    # 3. Rejected — agent-recorded only. Never inferred from the output.
    lines.append("## Rejected")
    lines.append("")
    if notes["rejected"]:
        lines.append("_Agent-recorded during the session._")
        lines.append("")
        for item in notes["rejected"]:
            lines.append(f"- {redact(item)}")
    else:
        lines.append(
            "_Not recorded._ Nothing was filed as a rejected path this session. "
            "The transcript cannot distinguish a considered-and-dropped approach "
            "from one never tried, so this section stays empty rather than guessing. "
            "Record with `write_back_hook.py note --rejected \"…\"`."
        )
    lines.append("")

    # 4. Open — same rule.
    lines.append("## Open")
    lines.append("")
    if notes["open"]:
        lines.append("_Agent-recorded during the session._")
        lines.append("")
        for item in notes["open"]:
            lines.append(f"- {redact(item)}")
    else:
        lines.append(
            "_Not recorded._ Nothing was filed as unresolved this session. "
            "Record with `write_back_hook.py note --open \"…\"`."
        )
    lines.append("")

    # 5. Evidence — the check that closes a claim, with the result it returned.
    lines.append("## Evidence")
    lines.append("")
    lines.append("_Verifying and publishing commands from the transcript, with the outcome recorded._")
    lines.append("")
    if evidence:
        lines.append("| Check | Result |")
        lines.append("|---|---|")
        for entry in evidence:
            command = redact(truncate(entry["command"], 180, " …")).replace("|", "\\|")
            mark = {"ok": "ok", "failed": "**failed**", "unknown": "unknown"}[entry["outcome"]]
            lines.append(f"| `{command}` | {mark} |")
        lines.append("")
    else:
        lines.append("_No verifying commands ran in this session._")
        lines.append("")
    lines.append(f"Transcript: `{payload.get('transcript_path') or 'unavailable'}`")
    lines.append("")

    # Commitments — only when there is something, so its presence is a signal.
    if commitments:
        lines.append("## Commitments (same-day flag)")
        lines.append("")
        lines.append(
            "_Candidates for review, not established facts. Detection requires a "
            "first-person promise, a named counterparty and a time reference in one "
            "sentence — deliberately narrow, so it misses rather than over-reports._"
        )
        lines.append("")
        for item in commitments:
            lines.append(f"- {redact(item)}")
        lines.append("")

    frontmatter = {
        "type": "note",
        "title": title,
        "date": date,
        "tags": tags,
        "session_id": session_id,
        "session_event": event,
        "cwd": cwd,
        "git_branch": parsed["git_branch"] or "",
        "prompts": len(parsed["prompts"]),
        "files_touched": len(actions["files"]),
        "commands_run": len(actions["commands"]),
        "commitment_candidates": len(commitments),
        "hook_version": HOOK_VERSION,
        "generated_by": "write-back-hook",
    }
    fm_lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, int):
            fm_lines.append(f"{key}: {value}")
        else:
            fm_lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    fm_lines.append("---")

    markdown = "\n".join(fm_lines) + "\n" + "\n".join(lines).rstrip() + "\n"
    return {
        "slug": slug,
        "markdown": markdown,
        "session_id": session_id,
        "event": event,
        "title": title,
        "commitments": len(commitments),
        "prompts": len(parsed["prompts"]),
    }


# ---------------------------------------------------------------------------
# Spool + capture
#
# Order matters and is the whole durability argument: the record is written to
# disk first, and only then offered to the brain. If the capture fails, the
# record still exists and is retried. If the process dies between the two, the
# next SessionStart finds it.
# ---------------------------------------------------------------------------

def spool_write(record: dict) -> Path:
    ensure_dirs()
    stamp = now_utc().strftime("%Y%m%dT%H%M%SZ")
    short = record["session_id"].replace("-", "")[:8]
    base = f"{stamp}-{short}-{record['event']}"
    path = SPOOL_DIR / f"{base}.md"
    path.write_text(record["markdown"], encoding="utf-8")
    (SPOOL_DIR / f"{base}.meta.json").write_text(
        json.dumps({
            "slug": record["slug"],
            "session_id": record["session_id"],
            "event": record["event"],
            "title": record["title"],
            "created": iso(now_utc()),
            "attempts": 0,
        }, indent=2),
        encoding="utf-8",
    )
    return path


def meta_for(spool_file: Path) -> tuple[Path, dict]:
    meta_file = spool_file.with_name(spool_file.stem + ".meta.json")
    try:
        return meta_file, json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return meta_file, {}


def capture_one(spool_file: Path) -> dict:
    """Offer one spooled record to the brain through the CLI. Returns a result
    dict; never raises."""
    meta_file, meta = meta_for(spool_file)
    slug = meta.get("slug")
    attempts = int(meta.get("attempts", 0)) + 1
    meta["attempts"] = attempts

    result = {"spool": str(spool_file), "slug": slug, "attempt": attempts}

    if DRY_RUN:
        result["outcome"] = "dry_run"
        return result

    gbrain = find_gbrain()
    if not gbrain:
        result.update(outcome="gbrain_missing",
                      error="gbrain CLI not found (set GBRAIN_BIN to override)")
        _write_meta(meta_file, meta)
        return result

    argv = [gbrain, "capture", "--file", str(spool_file), "--type", "note", "--json"]
    if slug:
        argv += ["--slug", slug]
    if SOURCE_ID:
        argv += ["--source", SOURCE_ID]

    try:
        # Run from the home directory on purpose. `gbrain capture` resolves the
        # source from a .gbrain-source dotfile by walking up from the working
        # directory, so running inside the project would silently route session
        # records into whatever source that project belongs to.
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=CAPTURE_TIMEOUT,
            cwd=str(Path.home()),
        )
    except subprocess.TimeoutExpired:
        result.update(outcome="timeout", error=f"gbrain capture exceeded {CAPTURE_TIMEOUT}s")
        _write_meta(meta_file, meta)
        return result
    except OSError as exc:
        result.update(outcome="spawn_failed", error=str(exc))
        _write_meta(meta_file, meta)
        return result

    if completed.returncode != 0:
        result.update(
            outcome="capture_failed",
            error=truncate((completed.stderr or completed.stdout or "").strip(), 500),
        )
        _write_meta(meta_file, meta)
        return result

    receipt = None
    try:
        receipt = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        pass

    # A zero exit with no parseable receipt is reported as such, not as a pass.
    result.update(outcome="captured", receipt=receipt)
    if isinstance(receipt, dict) and receipt.get("slug"):
        result["slug"] = receipt["slug"]
        # `written` is the CLI's disk-mirror flag. False means the page landed
        # in the database only (typically no repo configured for the source).
        # The archived spool copy is then the only second copy there is, so the
        # fact is recorded rather than assumed away.
        if not receipt.get("written"):
            result["db_only"] = True
    else:
        result["outcome"] = "captured_unverified"
        result["error"] = "capture returned 0 but no parseable receipt"

    _archive(spool_file, meta_file)
    return result


def _write_meta(meta_file: Path, meta: dict) -> None:
    try:
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except OSError:
        pass


def _archive(spool_file: Path, meta_file: Path) -> None:
    """Keep the captured record on disk. It is the local copy of what the brain
    now holds, and it is what makes a lost page recoverable."""
    try:
        ensure_dirs()
        shutil.move(str(spool_file), str(ARCHIVE_DIR / spool_file.name))
        if meta_file.exists():
            shutil.move(str(meta_file), str(ARCHIVE_DIR / meta_file.name))
    except OSError:
        pass


def _give_up(spool_file: Path, meta_file: Path) -> None:
    """Past the retry cap, move the record aside so it stops being retried on
    every session start — but never delete it, and keep it in `status`."""
    try:
        ensure_dirs()
        shutil.move(str(spool_file), str(FAILED_DIR / spool_file.name))
        if meta_file.exists():
            shutil.move(str(meta_file), str(FAILED_DIR / meta_file.name))
    except OSError:
        pass


def drain_spool(limit: int = 20) -> list[dict]:
    """Retry every spooled record, oldest first."""
    ensure_dirs()
    outcomes: list[dict] = []
    for spool_file in sorted(SPOOL_DIR.glob("*.md"))[:limit]:
        meta_file, meta = meta_for(spool_file)
        if int(meta.get("attempts", 0)) >= MAX_ATTEMPTS:
            _give_up(spool_file, meta_file)
            row = {"outcome": "gave_up", "spool": str(spool_file),
                   "slug": meta.get("slug"), "attempt": meta.get("attempts")}
            ledger_append(row)
            outcomes.append(row)
            continue
        result = capture_one(spool_file)
        ledger_append({"event": "drain", **result})
        outcomes.append(result)
    return outcomes


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def should_write(parsed: dict) -> tuple[bool, str]:
    """Skip sessions with nothing worth recording, so the brain does not fill
    with empty pages."""
    if not parsed["prompts"]:
        return False, "no human prompts in transcript"
    total = sum(len(p["text"]) for p in parsed["prompts"])
    has_action = bool(parsed["tool_calls"])
    if total < MIN_PROMPT_CHARS and not has_action:
        return False, f"trivial session ({total} prompt chars, no tool calls)"
    return True, ""


def write_back(payload: dict) -> dict:
    """Build, spool, capture. The single path both SessionEnd and PreCompact
    take — a checkpoint and a final record differ only in the payload event
    and both land on the same slug, so the later one supersedes the earlier."""
    transcript_path = payload.get("transcript_path")
    rows = load_transcript(transcript_path)
    transcript_ok = bool(rows)
    parsed = parse_session(rows)

    ok, reason = should_write(parsed)
    if not ok:
        row = {"event": payload.get("hook_event_name"), "outcome": "skipped",
               "reason": reason, "session_id": payload.get("session_id")}
        ledger_append(row)
        return row

    session_id = payload.get("session_id")
    notes, note_files = notes_consume(session_id)
    record = build_record(payload, parsed, notes, transcript_ok)

    try:
        spool_file = spool_write(record)
    except OSError as exc:
        row = {"event": payload.get("hook_event_name"), "outcome": "spool_failed",
               "error": str(exc), "session_id": session_id}
        ledger_append(row)
        return row

    # The record is on disk and holds the notes, so clearing them cannot lose
    # them. Only ever after the spool write succeeds.
    for note_file in note_files:
        try:
            note_file.unlink()
        except OSError:
            pass

    result = capture_one(spool_file)
    row = {
        "event": payload.get("hook_event_name"),
        "session_id": record["session_id"],
        "prompts": record["prompts"],
        "commitments": record["commitments"],
        **result,
    }
    ledger_append(row)
    return row


def handle_session_start(payload: dict) -> None:
    """Drain the backlog and tell the session what it found. This is the
    silent-failure detector: a broken write-back becomes visible at the start
    of the next session instead of never."""
    outcomes = drain_spool()
    pending = len(list(SPOOL_DIR.glob("*.md"))) if SPOOL_DIR.exists() else 0
    failed = len(list(FAILED_DIR.glob("*.md"))) if FAILED_DIR.exists() else 0

    messages: list[str] = []
    recovered = sum(1 for o in outcomes if o.get("outcome") == "captured")
    if recovered:
        messages.append(f"{recovered} spooled session record(s) captured on retry.")
    if pending:
        messages.append(f"{pending} session record(s) still pending capture in {SPOOL_DIR}.")
    if failed:
        messages.append(
            f"{failed} session record(s) exceeded {MAX_ATTEMPTS} capture attempts and are "
            f"parked in {FAILED_DIR}. Write-back is NOT reaching the brain — investigate "
            f"before trusting the session history."
        )
    if not find_gbrain():
        messages.append(
            "gbrain CLI not found on PATH: session write-back cannot reach the brain. "
            "Set GBRAIN_BIN or fix PATH."
        )

    if not messages:
        return
    context = "Write-back hook status: " + " ".join(messages)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_note(argv: list[str]) -> int:
    kinds = {"--rejected": "rejected", "--open": "open", "--commitment": "commitment"}
    session_id = os.environ.get("CLAUDE_SESSION_ID") or None
    recorded = 0
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--session" and i + 1 < len(argv):
            session_id = argv[i + 1]
            i += 2
            continue
        if arg in kinds and i + 1 < len(argv):
            note_append(kinds[arg], argv[i + 1].strip(), session_id)
            recorded += 1
            i += 2
            continue
        i += 1
    if not recorded:
        print("usage: write_back_hook.py note [--session ID] "
              "--rejected TEXT | --open TEXT | --commitment TEXT", file=sys.stderr)
        return 2
    print(f"recorded {recorded} note(s) for {'session ' + session_id if session_id else 'the next write-back'}")
    return 0


def status_dict() -> dict:
    ensure_dirs()
    rows = ledger_rows()
    captures = [r for r in rows if r.get("outcome") in ("captured", "captured_unverified")]
    last_success = captures[-1] if captures else None
    failures = [
        r for r in rows
        if r.get("outcome") in
        ("capture_failed", "timeout", "spawn_failed", "gbrain_missing", "spool_failed", "gave_up")
    ]
    return {
        "state_home": str(STATE_HOME),
        "gbrain": find_gbrain(),
        "disabled": DISABLED,
        "pending": sorted(p.name for p in SPOOL_DIR.glob("*.md")),
        "parked_failed": sorted(p.name for p in FAILED_DIR.glob("*.md")),
        "archived": len(list(ARCHIVE_DIR.glob("*.md"))),
        "last_success": last_success,
        "recent_failures": failures[-5:],
        "ledger_rows": len(rows),
        "hook_version": HOOK_VERSION,
    }


def cmd_status(argv: list[str]) -> int:
    info = status_dict()
    if "--json" in argv:
        print(json.dumps(info, indent=2))
        return 0
    print(f"write-back hook v{info['hook_version']}")
    print(f"  state home:   {info['state_home']}")
    print(f"  gbrain:       {info['gbrain'] or 'NOT FOUND'}")
    print(f"  disabled:     {info['disabled']}")
    print(f"  pending:      {len(info['pending'])}")
    print(f"  parked:       {len(info['parked_failed'])}")
    print(f"  archived:     {info['archived']}")
    last = info["last_success"]
    print(f"  last success: {last['ts'] + ' -> ' + str(last.get('slug')) if last else 'never'}")
    db_only = [r for r in ledger_rows() if r.get("db_only")]
    if db_only:
        print(f"  db-only:      {len(db_only)} capture(s) had no disk mirror "
              f"(archived spool copy is the second copy)")
    if info["recent_failures"]:
        print(f"  recent failures ({len(info['recent_failures'])}):")
        for row in info["recent_failures"]:
            print(f"    {row.get('ts')} {row.get('outcome')} {truncate(str(row.get('error', '')), 120)}")
    # Non-zero when write-back is not reaching the brain, so a wiring check can
    # use the exit code directly.
    return 1 if (info["parked_failed"] or not info["gbrain"]) else 0


def cmd_flush(argv: list[str]) -> int:
    outcomes = drain_spool(limit=100)
    if "--json" in argv:
        print(json.dumps(outcomes, indent=2))
    else:
        if not outcomes:
            print("spool empty — nothing to flush")
        for row in outcomes:
            print(f"  {row.get('outcome')}  {row.get('slug')}  {row.get('error', '')}".rstrip())
    bad = [o for o in outcomes if o.get("outcome") not in ("captured", "dry_run")]
    return 1 if bad else 0


SELFTEST_TRANSCRIPT = [
    {"type": "user", "isSidechain": False, "timestamp": "2026-01-01T00:00:00Z",
     "cwd": "/tmp/demo", "gitBranch": "demo/branch", "promptSource": "user",
     "message": {"role": "user", "content":
                 "Fix the importer and probe it. I'll send Alice the numbers by Thursday.\n"
                 "<system-reminder>ignore me</system-reminder>"}},
    {"type": "assistant", "isSidechain": False, "timestamp": "2026-01-01T00:00:01Z",
     "message": {"model": "test-model", "content": [
         {"type": "text", "text": "Working on it. I'll email Bob tomorrow."},
         {"type": "tool_use", "id": "t1", "name": "Edit",
          "input": {"file_path": "/tmp/demo/importer.py"}},
         {"type": "tool_use", "id": "t2", "name": "Bash",
          "input": {"command": "bun test test/importer.test.ts"}},
         {"type": "tool_use", "id": "t3", "name": "Bash",
          "input": {"command": "curl -H 'Authorization: Bearer abcdefghijklmnop' https://x.test"}},
         {"type": "tool_use", "id": "t4", "name": "Read", "input": {"file_path": "/tmp/demo/x"}},
         {"type": "tool_use", "id": "t5", "name": "mcp__Some_Brain__get_page", "input": {}},
     ]}},
    {"type": "user", "isSidechain": False, "toolUseResult": {"stdout": "1 pass", "stderr": ""},
     "message": {"role": "user", "content": [
         {"type": "tool_result", "tool_use_id": "t2", "content": "1 pass"}]}},
    {"type": "user", "isSidechain": False, "toolUseResult": "Error: connection refused",
     "message": {"role": "user", "content": [
         {"type": "tool_result", "tool_use_id": "t3", "is_error": True,
          "content": "Error: connection refused"}]}},
    {"type": "user", "isSidechain": True, "timestamp": "2026-01-01T00:00:02Z",
     "message": {"role": "user", "content": "subagent prompt that must not be quoted"}},
    {"type": "assistant", "isSidechain": True, "timestamp": "2026-01-01T00:00:03Z",
     "message": {"model": "test-model", "content": [{"type": "text", "text": "sub work"}]}},
]


def cmd_selftest(argv: list[str]) -> int:
    """Prove the wiring without touching the brain: parse a synthetic
    transcript, build a record, and assert the properties that matter. Run it
    after install, and from a scheduled wiring check."""
    import tempfile

    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  ok    {label}")
        else:
            failures.append(f"{label}{': ' + detail if detail else ''}")
            print(f"  FAIL  {label}{': ' + detail if detail else ''}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            "\n".join(json.dumps(r) for r in SELFTEST_TRANSCRIPT) + "\n", encoding="utf-8")

        rows = load_transcript(str(transcript))
        check("transcript parses", len(rows) == len(SELFTEST_TRANSCRIPT),
              f"{len(rows)} of {len(SELFTEST_TRANSCRIPT)} rows")

        parsed = parse_session(rows)
        check("one human prompt extracted", len(parsed["prompts"]) == 1,
              f"got {len(parsed['prompts'])}")
        check("subagent prompt excluded",
              all("subagent prompt" not in p["text"] for p in parsed["prompts"]))
        check("subagent turn counted", parsed["sidechain_turns"] == 1,
              f"got {parsed['sidechain_turns']}")
        check("injected context stripped",
              "system-reminder" not in (parsed["prompts"][0]["text"] if parsed["prompts"] else "x"))
        check("tool results indexed", len(parsed["results"]) == 2,
              f"got {len(parsed['results'])}")
        check("failed command detected",
              result_outcome(parsed["results"], "t3") == "failed",
              result_outcome(parsed["results"], "t3"))
        check("passing command detected",
              result_outcome(parsed["results"], "t2") == "ok",
              result_outcome(parsed["results"], "t2"))
        check("git branch recovered", parsed["git_branch"] == "demo/branch", parsed["git_branch"])

        notes, _ = ({"rejected": ["dropped the queue approach: needs a schema change"],
                     "open": ["the pooler limit is still unverified"],
                     "commitment": []}, [])
        record = build_record(
            {"session_id": "abcdef12-0000-0000-0000-000000000000",
             "hook_event_name": "SessionEnd", "cwd": "/tmp/demo",
             "transcript_path": str(transcript)},
            parsed, notes, True)
        body = record["markdown"]

        for section in ("## Asked", "## Did", "## Rejected", "## Open", "## Evidence"):
            check(f"section present: {section}", section in body)
        check("slug is session-scoped", record["slug"].startswith(SLUG_PREFIX + "/"), record["slug"])
        check("frontmatter present", body.startswith("---\n"))
        check("prompt quoted verbatim", "Fix the importer and probe it" in body)
        check("bearer token redacted",
              "abcdefghijklmnop" not in body and "[redacted]" in body)
        check("evidence table built", "| Check | Result |" in body)
        check("failed check reported as failed", "**failed**" in body)
        check("agent notes surfaced",
              "dropped the queue approach" in body and "pooler limit" in body)
        check("commitment detected (human prompt)",
              "Commitments (same-day flag)" in body and "Alice" in body)
        check("model prose excluded from commitments", "email Bob tomorrow" not in body)

        empty = parse_session([])
        ok, reason = should_write(empty)
        check("empty session skipped", ok is False, reason)

        notes_none = {"rejected": [], "open": [], "commitment": []}
        no_notes = build_record(
            {"session_id": "x", "hook_event_name": "SessionEnd", "cwd": "/tmp/demo",
             "transcript_path": str(transcript)}, parsed, notes_none, True)
        check("missing notes stated, not invented",
              "_Not recorded._" in no_notes["markdown"])
        check("confidence line reports the gap",
              "none on rejected/open" in no_notes["markdown"])

    binary = find_gbrain()
    if binary:
        print(f"  ok    gbrain CLI found: {binary}")
    else:
        msg = "gbrain CLI not found (capture would spool and retry)"
        if "--require-gbrain" in argv:
            failures.append(msg)
            print(f"  FAIL  {msg}")
        else:
            print(f"  warn  {msg}")

    print("")
    if failures:
        print(f"  {len(failures)} check(s) FAILED")
        return 1
    print("  all checks passed — the record shape and the guarantees hold")
    return 0


HELP = """write_back_hook.py — automatic session write-back into a brain

As a hook (payload on stdin, registered in settings.json):
  SessionEnd    build + spool + capture the session record
  PreCompact    mid-session checkpoint onto the same slug
  SessionStart  retry the spool, report failures into the session

As a command:
  write_back_hook.py note --rejected TEXT   record a dropped path
  write_back_hook.py note --open TEXT       record something unresolved
  write_back_hook.py note --commitment TEXT record a promise made
  write_back_hook.py flush [--json]         retry every spooled record
  write_back_hook.py status [--json]        pending / parked / last success
  write_back_hook.py selftest               prove the wiring, brain untouched

Environment:
  GBRAIN_WRITEBACK_DISABLED=1   turn the hook off entirely
  GBRAIN_WRITEBACK_DRY_RUN=1    build and spool, never capture
  GBRAIN_WRITEBACK_HOME=PATH    state directory (default ~/.claude/write-back)
  GBRAIN_WRITEBACK_SLUG_PREFIX  slug namespace (default ops/sessions)
  GBRAIN_WRITEBACK_SOURCE=ID    write under a non-default brain source
  GBRAIN_WRITEBACK_TIMEOUT=N    seconds to allow gbrain capture (default 90)
  GBRAIN_WRITEBACK_MAX_ATTEMPTS retries before a record is parked (default 5)
  GBRAIN_BIN=PATH               explicit gbrain binary
"""


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("--help", "-h", "help"):
        print(HELP)
        return 0

    if argv:
        command = argv[0]
        if command == "note":
            return cmd_note(argv[1:])
        if command == "status":
            return cmd_status(argv[1:])
        if command == "flush":
            if DISABLED:
                print("write-back disabled (GBRAIN_WRITEBACK_DISABLED)")
                return 0
            return cmd_flush(argv[1:])
        if command == "selftest":
            return cmd_selftest(argv[1:])
        print(HELP, file=sys.stderr)
        return 2

    # Hook mode: the payload arrives as JSON on stdin.
    raw = ""
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
    except OSError:
        raw = ""
    if not raw.strip():
        print(HELP, file=sys.stderr)
        return 2

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        ledger_append({"outcome": "bad_payload", "error": str(exc)})
        return 0
    if not isinstance(payload, dict):
        ledger_append({"outcome": "bad_payload", "error": "payload was not an object"})
        return 0

    if DISABLED:
        return 0

    event = str(payload.get("hook_event_name") or "")
    if event == "SessionStart":
        handle_session_start(payload)
    elif event in ("SessionEnd", "PreCompact"):
        write_back(payload)
    # Any other event is a no-op: registering this hook somewhere unexpected
    # should do nothing rather than something surprising.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except BaseException:
        # A write-back bug must never be able to break a session. Record the
        # traceback where it can be found, and exit clean.
        ledger_append({"outcome": "hook_crashed",
                       "error": truncate(traceback.format_exc(), 2000)})
        sys.exit(0)
