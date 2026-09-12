#!/usr/bin/env python3
"""install.py — register (or remove) the write-back hook in a Claude Code
settings file.

Editing settings.json by hand is how a hook ends up registered twice, or
registered under the wrong event, or silently lost the next time something
rewrites the file. This does it as a data transform: read the JSON, add
exactly three entries, write it back, and leave every other key alone.

  install.py                       install into ~/.claude/settings.json
  install.py --settings PATH       install into a specific settings file
  install.py --uninstall           remove every entry this installer added
  install.py --dry-run             print the resulting JSON, write nothing
  install.py --hook-path PATH      register a hook script from another location

Idempotent by construction: entries are matched by the marker below, so
running it twice changes nothing, and uninstall restores the file to exactly
what it was before install.

Events registered, and why each one:
  SessionEnd    the record. This is the hook's whole reason to exist.
  PreCompact    a checkpoint onto the same slug, so a session that is killed
                after compaction still left a record behind.
  SessionStart  drains the retry spool and reports failures into the session,
                which is what keeps a broken write-back from being silent.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER = "write_back_hook.py"
EVENTS = ("SessionEnd", "PreCompact", "SessionStart")
DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"


def hook_command(hook_path: Path) -> str:
    return f"python3 {hook_path}"


def load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit(f"cannot read {path}: {exc}")
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Refuse rather than guess: a settings file that does not parse is a
        # file someone is mid-edit on, and clobbering it is unrecoverable.
        raise SystemExit(f"{path} is not valid JSON ({exc}); fix it before installing")
    if not isinstance(data, dict):
        raise SystemExit(f"{path} does not contain a JSON object")
    return data


def strip_hook(settings: dict) -> tuple[dict, int]:
    """Remove every entry this installer added. Returns the settings and how
    many were removed."""
    removed = 0
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings, 0
    for event in list(hooks.keys()):
        matchers = hooks.get(event)
        if not isinstance(matchers, list):
            continue
        removed_here = 0
        kept_matchers = []
        for matcher in matchers:
            if not isinstance(matcher, dict):
                kept_matchers.append(matcher)
                continue
            entries = matcher.get("hooks")
            if not isinstance(entries, list):
                kept_matchers.append(matcher)
                continue
            kept = [
                e for e in entries
                if not (isinstance(e, dict) and MARKER in str(e.get("command", "")))
            ]
            removed_here += len(entries) - len(kept)
            if not kept:
                continue  # the matcher existed only for this hook
            matcher = {**matcher, "hooks": kept}
            kept_matchers.append(matcher)
        removed += removed_here
        if kept_matchers:
            hooks[event] = kept_matchers
        elif removed_here:
            del hooks[event]  # the event group existed only for this hook
        # An event that was already empty is left exactly as it was found:
        # uninstall removes what install added, and nothing else.
    if not hooks and removed:
        settings.pop("hooks", None)
    return settings, removed


def add_hook(settings: dict, hook_path: Path) -> dict:
    command = hook_command(hook_path)
    hooks = settings.setdefault("hooks", {})
    for event in EVENTS:
        matchers = hooks.setdefault(event, [])
        if not isinstance(matchers, list):
            raise SystemExit(f"hooks.{event} is not a list; refusing to edit")
        entry = {"type": "command", "command": command}
        # Reuse the empty-matcher group if one is already there, so the hook
        # sits alongside whatever else runs on this event.
        target = next(
            (m for m in matchers
             if isinstance(m, dict) and not str(m.get("matcher", "")).strip()),
            None,
        )
        if target is None:
            matchers.append({"matcher": "", "hooks": [entry]})
        else:
            target.setdefault("hooks", []).append(entry)
    return settings


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    parser.add_argument("--hook-path", default=str(Path(__file__).resolve().parent / MARKER))
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings_path = Path(args.settings).expanduser()
    hook_path = Path(args.hook_path).expanduser()

    if not args.uninstall and not hook_path.exists():
        raise SystemExit(f"hook script not found at {hook_path}")

    settings = load_settings(settings_path)

    # Always strip first. Install then becomes "remove and re-add", which is
    # what makes running it twice a no-op instead of a duplicate.
    settings, removed = strip_hook(settings)
    if not args.uninstall:
        settings = add_hook(settings, hook_path)

    rendered = json.dumps(settings, indent=2) + "\n"

    if args.dry_run:
        print(rendered, end="")
        return 0

    if settings_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = settings_path.with_name(f"{settings_path.name}.writeback-{stamp}.bak")
        shutil.copy2(settings_path, backup)
        print(f"backed up {settings_path} -> {backup}")

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    # Write via a temp file in the same directory, then replace, so an
    # interrupted install cannot leave a half-written settings file.
    tmp = settings_path.with_name(settings_path.name + ".writeback.tmp")
    tmp.write_text(rendered, encoding="utf-8")
    tmp.replace(settings_path)

    if args.uninstall:
        print(f"removed {removed} write-back hook entr{'y' if removed == 1 else 'ies'} "
              f"from {settings_path}")
        print("State in ~/.claude/write-back was left alone: spooled and archived "
              "records are not the installer's to delete.")
    else:
        print(f"installed write-back hook into {settings_path}")
        print(f"  events:  {', '.join(EVENTS)}")
        print(f"  command: {hook_command(hook_path)}")
        print("")
        print("Verify before trusting it:")
        print(f"  python3 {hook_path} selftest")
        print(f"  python3 {hook_path} status")
        print("")
        print("The hook takes effect in the NEXT session, not this one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
