# GBrain Migration: Local → Railway Only (July 1, 2026)

## Decision

**Consolidated gbrain to Railway Postgres. Disabled local pglite. All agents query production endpoint only.**

**Rationale:**
- Railway gbrain is production-grade (managed Supabase Postgres, 20K+ pages, fully embedded, currently syncing)
- Local pglite was secondary, broken (dimension mismatch, API key missing, no synced data)
- Keeping both = operational complexity, sync risk, unclear source of truth
- Single system = simpler, more reliable, scales better

---

## What Was Done

### Date: July 1, 2026 (Session: Forge)

#### Step 1: Audit Current State
- Verified Railway gbrain: 20,397 pages, 52,281 embedded chunks (all with voyage-4, 1024d vectors)
- Verified local pglite: 2,549 pages detected (zero embedded), dimension mismatch (768 != 1280), ZEROENTROPY_API_KEY missing
- Sources audit: Railway had 6 registered sources synced; local had 3 detected but never synced
- Last Railway sync: June 30, 2026 12:49 UTC

#### Step 2: Disabled Local Services
```bash
launchctl unload ~/Library/LaunchAgents/com.gbrain.serve.plist
launchctl unload ~/Library/LaunchAgents/com.gbrain.autopilot.plist
launchctl unload ~/Library/LaunchAgents/com.gbrain.sync-all.plist
```

#### Step 3: Preserved Local Data
Renamed local directory for clarity:
```bash
mv ~/.gbrain ~/.gbrain-backup-local
```

**Location on disk:** `/Users/stevewandler/.gbrain-backup-local`
**Purpose:** Cold backup; can be re-enabled if Railway fails catastrophically

#### Step 4: Deleted Broken Service
Removed non-functional `gbrain-dream-cycle` cron job from Railway.
- Was in `created` status (container never deployed)
- Was scheduled for 2 AM daily but never ran
- Can be re-added later if knowledge refinement is enabled

#### Step 5: Verified Production
```bash
curl -s -I https://gbrain-production-c2e0.up.railway.app/health
# HTTP/2 200 ✓
```

---

## Current Production State

### System Architecture

```
Sources (git repos)
  ├── gbrain-personal (~14,495 pages)
  ├── personal-sensitive (~2,178 pages)
  ├── bookmarked-strategy (~1,377 pages)
  ├── bookmarked-os (~1,167 pages)
  ├── product-ideation (~608 pages)
  └── ruiz-wandler (~572 pages)
           ↓
   [Railway gbrain HTTP server]
   (https://gbrain-production-c2e0.up.railway.app)
           ↓
   Supabase Postgres
   (db.vaevjtfxbduyqcfuvzfv.supabase.co)
           ↓
   Agents / Tools / APIs
   (Nero, Northy, Claude, etc.)
```

### Endpoint

**Primary:** `https://gbrain-production-c2e0.up.railway.app`

MCP protocol: `gbrain serve --http --public-url https://gbrain-production-c2e0.up.railway.app`

### Data Counts

| Metric | Value | Status |
|--------|-------|--------|
| Total pages | 20,397 | ✅ All indexed |
| Content chunks | 52,281 | ✅ All embedded |
| Embedding model | voyage-4 (1024d) | ✅ Current |
| Sources registered | 6 | ✅ All synced |
| Last sync | Jun 30, 2026 12:49 UTC | ✅ Recent |
| Database | Supabase Postgres (PgBouncer pool) | ✅ Managed backups |
| Health check | HTTP 200 | ✅ Operational |

### Source Sync Status

```sql
-- Query: SELECT source_id, COUNT(*) as page_count FROM pages GROUP BY source_id
default              14,495 pages
personal-sensitive    2,178 pages
bookmarked-strategy   1,377 pages
bookmarked-os         1,167 pages
product-ideation        608 pages
ruiz-wandler            572 pages
─────────────────────────────────
Total                 20,397 pages
```

---

## If You Need to Recover Local GBrain

The local backup is dormant but recoverable:

```bash
# Option A: Re-enable local pglite services (for testing/staging)
launchctl load ~/Library/LaunchAgents/com.gbrain.serve.plist
launchctl load ~/Library/LaunchAgents/com.gbrain.autopilot.plist

# Option B: Inspect local data without starting services
cd ~/.gbrain-backup-local
sqlite3 brain.pglite ".tables"  # Note: pglite is not standard SQLite
```

**Don't do this unless Railway is down AND you can't wait for Supabase backup recovery.**

---

## What's NOT Being Done (Intentionally)

### ❌ Dream Cycle (Knowledge Refinement)
Not scheduled yet. When enabled in future:
- Extracts facts, synthesizes concepts, identifies patterns
- Costs ~$20–50 per run (LLM calls)
- Should only run once you're actively querying gbrain
- Can be re-added with: `gbrain dream --source default --max-cost-usd 25`

### ❌ Embeddings Migration from Local
Not needed. Local had zero embeddings (broken state).
Railway already has 52,281 fully embedded chunks from previous syncs.

### ❌ Local ↔ Railway Sync Daemon
Not configured. Railway sources point to git repos (automatic sync on schedule).
No bidirectional sync needed.

---

## Monitoring Forward

### Health Checks

**Daily:** Monitor Railway logs for errors
```bash
railway logs --service gbrain --lines 50
```

**Weekly:** Verify sync freshness
```bash
PGPASSWORD="..." psql -h db.vaevjtfxbduyqcfuvzfv.supabase.co -U postgres -d postgres \
  -c "SELECT source_id, last_sync_at FROM sources ORDER BY last_sync_at DESC;"
```

**Monthly:** Check database size and growth
```bash
PGPASSWORD="..." psql -h db.vaevjtfxbduyqcfuvzfv.supabase.co -U postgres -d postgres \
  -c "SELECT COUNT(*) as pages, COUNT(*) * 5 as estimated_chunks_mb FROM pages;"
```

---

## Rollback Plan

**If Railway gbrain becomes unavailable for >1 hour:**

1. Re-enable local pglite:
   ```bash
   mv ~/.gbrain-backup-local ~/.gbrain
   launchctl load ~/Library/LaunchAgents/com.gbrain.serve.plist
   ```

2. Update agent endpoints from:
   - `https://gbrain-production-c2e0.up.railway.app` → `localhost:8765`

3. Caveat: Local will be stale (last data state from Jun 30). Supabase has point-in-time recovery — use that if possible instead.

---

## References

- **gbrain CLI:** https://github.com/garrytan/gbrain
- **Supabase Postgres:** https://supabase.com/docs/guides/database/postgres
- **Railway Documentation:** https://docs.railway.app
- **This repo's AGENTS.md:** Operator setup and install protocol
- **Local backup location:** `/Users/stevewandler/.gbrain-backup-local`

---

## Questions

If you need to understand:
- **Why this architecture?** → Read this file
- **How to deploy changes?** → See `./docs/DEPLOY.md`
- **How to troubleshoot?** → See `./docs/GBRAIN_VERIFY.md`
- **How to run knowledge refinement?** → See `./CHANGELOG.md` (search "dream cycle")

---

**Document created:** 2026-07-01  
**Last updated:** 2026-07-01  
**Owner:** Forge (infrastructure CTO)  
**Status:** Reference documentation (no immediate action needed)
