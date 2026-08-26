# Session handoff — 2026-08-12

Paste this into a fresh session to resume with full context.

---

## Start here

Read these three, in order — they carry everything durable from 2026-08-12:

1. `~/.claude/memory/github_repo_operations.md` — how the 85 repos are organized
2. `~/.claude/memory/bookmarked_os_repo.md` — the company OS repo and what was fixed
3. G-Brain slug `github-cleanup-2026-08-12` — full session record + open items

Skills now available: **`github-repo-hygiene`** (audit/clean repos) and
**`claude-team-admin`** (Claude Team admin + org skill library), both in
`~/gbrain-personal/skills/`.

---

## IN FLIGHT — check this first

**bookmarked-os history rewrite.** Steve was running the force-push when the session
ended. Verify:

```bash
gh api repos/BookmarkED-Corp/bookmarked-os --jq '.size'   # expect ~190000 KB, was 1258432
gh api repos/BookmarkED-Corp/bookmarked-os/branches/main/protection --jq '.allow_force_pushes.enabled'
```

Then, in order:
1. **Turn force-push back OFF** (it was enabled only for the rewrite):
   `gh api -X PUT repos/BookmarkED-Corp/bookmarked-os/branches/main/protection --input -`
   with `{"required_status_checks":null,"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null,"allow_force_pushes":false,"allow_deletions":false}`
2. **Re-clone Steve's local folder** — every commit ID changed, so
   `~/github-repos/bookmarked-os` is stale and `git pull` will fail confusingly.
   **Preserve the one untracked file first:** `dream-cycle-summaries/2026-07-10.md`.
3. Verify the fresh clone has **4,886 files** and **0** `.mp4`.

GitHub's reported size lags the actual reclaim by hours to a day — if it still reads
1.2 GB tomorrow that's normal, not a failure.

**Backup:** full 1.2 GB mirror at
`<session scratchpad>/bookmarked-os-BACKUP.git` — every branch and commit. This is
session-scoped and will be cleaned up; if the rewrite needs undoing, do it soon or
re-mirror from GitHub first.

---

## Waiting on humans

| Item | Who |
|---|---|
| Delete 3 public ESC 16 gists (secret copies already made, links DM'd) | Steve |
| Answer the V1-repos/prod-infra archive question (message drafted) | Raju |
| Rotate Slack tokens from the July secrets tarball — no record it ever happened | Steve |
| Decide `product_design` (empty placeholder repo) | Steve |
| Upload the 6 rewritten org skills — staged at `claude-org-skills-rewrite-2026-08-07/`, blocked by a native file picker | Steve |
| Org skill deletions 21 → 6 — audit delivered, he chose audit-only | Steve |

---

## Known broken (found, not fixed)

- **Transcript pipeline stale since 08-08** — Meet notes stop 08-03, Plaud 08-07. Today's
  standup was unreachable because of this. Probably the highest-value fix remaining.
- **Google MCP token `invalid_scope`** — use the mounted Drive folder instead:
  `~/Library/CloudStorage/GoogleDrive-steve@bookmarked.com`
- **`mcp__slack__*` returns `token_revoked`** — fallback is the bot token in
  `~/.claude/scripts/slack-dm-notify.sh` via `chat.postMessage`
- **G-Brain fork 10 releases behind** (0.42.74.0 vs 0.45.5.0)
- **GBrain org connector points at staging** with 95 unrestricted tools

---

## Standing rules learned this session

- **Raju is the engineering authority, not Patrick.** Never remove his access from
  anything; his access ≥ Patrick's. He does not need to be added to things.
- **Never guess what a repo is.** Read it or mark it UNVERIFIED. Names lie — the
  `*Folder` repos are agent workspaces; three "stale" repos are running prod services.
- **Every archive gets a tombstone** — when, why, where the content went.
- **2FA org requirement is parked.** Do not re-raise it.
- **Steve wants plain English.** No jargon, no deep-dive detail unless asked. Frame
  decisions as what he'll *see*, not schema.
- Before any destructive op: collision-check, scope to file type not directory, back up
  first. Both mistakes from this session are codified in `github-repo-hygiene`.

---

## Automation running

**`stack-watch`** — nightly ~8:50pm, DMs Steve. Watches Claude / G-Brain / GitHub /
Hermes for changes, applies an integration lens against known seams, plus a
`github_hygiene` block (undescribed repos, repos flipped public, new public gists, org
security drift, unbacked local work, registry regeneration). Silent when clean.
State: `~/.claude/stack-watch/state.json` — read it before answering "what's new."
