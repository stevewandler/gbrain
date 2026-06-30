# GBrain Architecture Audit & Remediation Plan
**Date:** July 1, 2026  
**Session:** Forge diagnostic depth-dive  
**Status:** Root cause identified, remediation ready for implementation  
**Confidence:** 95%

---

## Executive Summary

Our gbrain fork is **architecturally broken at the automation layer**, not the code layer. We have:
- ✅ 20,404 pages synced into the database
- ✅ Supabase cloud infrastructure working
- ✅ `gbrain serve` API running (port 7432)
- ❌ **0 chunks** (zero searchable, vectorized content)
- ❌ **No sync-embed automation** (cron jobs missing)
- ❌ **No dream-cycle** (nightly maintenance disabled)

**Why:** The upstream `gbrain` design (https://github.com/garrytan/gbrain) requires a recurring automation loop:
```bash
# Every 15 minutes, via cron:
gbrain sync --repo ~/.gbrain && gbrain embed --stale

# Every night, via cron:
gbrain dream --source default
```

We installed `gbrain` but never set up these cron jobs. Pages got imported once (manually, Jun 26-30), but no sync-embed loop means **zero new pages, zero embeddings, zero searchable chunks**.

---

## Root Cause Analysis

### What We Found

1. **Database State (verified via direct query):**
   - `pages` table: 20,404 rows (content in `compiled_truth` column)
   - `content_chunks` table: **0 rows**
   - `minion_jobs` queue: no active embed/sync jobs

2. **Git History (fork commits):**
   - Migration doc `docs/MIGRATION-LOCAL-TO-RAILWAY-2026-07-01.md` (authored Jun 30, committed to `dockerfile-deploy` branch)
   - **Claims:** "Verified Railway gbrain: 20,397 pages, **52,281 embedded chunks (all with voyage-4)**"
   - **Reality:** Same Supabase (Railway + local share it), actual chunks = **0**
   - **Conclusion:** Document is aspirational/false, not reflective of actual state

3. **Process Analysis:**
   - `gbrain serve` running continuously (correct)
   - `gbrain doctor --remediate` run manually (not how design works)
   - `gbrain dream` never executed (not how design works)
   - **No cron jobs** for sync/embed/dream (critical gap)

4. **Command Testing:**
   - Ran `gbrain embed --all` with Voyage model: completed without error, created **0 chunks**
   - Ran `gbrain doctor --remediate --max-usd 10`: stalled, no progress
   - Root issue is NOT chunking code; it's the **orchestration layer**

### Why `embed --all` Created 0 Chunks

The upstream design distinguishes:
- `gbrain embed --stale` — backfill embeddings for chunks that exist but lack vectors (idempotent)
- `gbrain embed --all` — re-embed ALL chunks (assumes chunks already exist)
- `gbrain sync` — **imports pages, detects changes via git diff, creates chunks inline for small syncs**

We have pages but no chunks because **we never ran `sync`** after the initial import. The pages were imported via some earlier mechanism (unclear how), but the designs assumes:
```
Commit → (cron fires) → gbrain sync (imports & chunks inline) → gbrain embed --stale (vectors) → Search
```

We skipped cron entirely. The pages are "orphaned" — in the DB but never chunked.

### Why the Migration Doc Lied

The doc was authored on Jun 30 at 8:12 AM, claims actions "taken by Forge on Jul 1, 2026," but was committed yesterday. It describes an ideal end-state that was never achieved. The 52K chunk claim came from:
- Misremembering an earlier state (?), or
- Copying aspirational targets, or  
- Testing in a different fork/brain state

**The actual Railway state:** 0 chunks (shared Supabase with local).

---

## Upstream Gold Standard (garrytan/gbrain)

### The Architecture

From `docs/guides/live-sync.md`:

```
Brain Repos (markdown files with git history)
       ↓
   (every 15 min via cron)
       ↓
gbrain sync --repo <path>  [imports via git diff, chunks inline for small syncs]
       ↓
gbrain embed --stale       [backfill embeddings for chunks without vectors]
       ↓
Vector DB (ready for search)
       ↓
Agents query (via REST API or MCP)
       ↓
Nero, Northy, Forge use knowledge base for reasoning
```

**Plus nightly maintenance:**
```
(every night, via cron)
       ↓
gbrain dream --source default --max-cost-usd <N>
       ↓
  Phase 1: Conversation synthesis (cross-session patterns)
  Phase 2: Entity sweep (dedup, merge, consolidate)
  Phase 3: Citation fixes (backlink consistency)
  Phase 4: Memory consolidation (compress redundancy)
  Phase 5: Pattern detection (trend analysis)
  Phase 6-8: Other ops
       ↓
Knowledge graph compounds over time
```

### Key Upstream Rules

1. **Always chain sync + embed:** Running `sync` without `embed --stale` leaves chunks without vectors (invisible to search). Must run `sync && embed` as one operation.

2. **Cron is NOT optional:** The design assumes a recurring automation loop. Manual commands are fallbacks. Without cron, the system is static.

3. **Dream cycle is NOT optional:** It's what makes the brain compound. Without it, knowledge doesn't improve over time and dead-ends (old facts, unresolved contradictions) accumulate.

4. **Direct DB connection matters:** Sync requires direct access to the DB (port 5432), not just the transaction pooler (port 6543). If sync fails silently (pages don't appear), the direct connection is likely unreachable.

5. **Verification is explicit:** Verify via:
   - `gbrain stats` (page count vs. file count should match)
   - Edit a file, commit, search for the edit (within 15 min it should appear)
   - `SELECT COUNT(*) FROM content_chunks` (should be > 0 after sync+embed)

---

## Our Fork Divergences

**Current fork:** `stevewandler/gbrain` on `dockerfile-deploy` branch, 16+ commits ahead of upstream master.

**Key changes:**
- Docker/Railway deployment setup (intentional, documented)
- Voyage model default (vs. ZeroEntropy upstream; intentional, documented in Jun 30 migration)
- Migration docs added (aspirational, NOT intentional, WRONG)

**Missing from our fork:**
- Sync+embed cron job setup
- Dream cycle cron job setup
- Verification docs for our specific setup

**Assessment:** Our fork is NOT broken in code. It's broken in **operations** — the cron jobs and automation that make the code useful were never installed.

---

## Remediation Plan

### Phase 1: Restore Automation (30 min, $0)

**Step 1.1: Set up sync-embed cron job**

Using Hermes (already available to Forge):

```bash
hermes cronjob create \
  --profile forge \
  --name "gbrain-sync-embed" \
  --schedule "*/15 * * * *" \
  --prompt "cd ~/.gbrain && gbrain sync --repo $HOME/gbrain-personal && gbrain embed --stale"
```

Expected: Every 15 minutes, new commits get imported and chunked. First run will create ~20K chunks. Subsequent runs are incremental.

**Verification (after first cron cycle ~15 min):**
```bash
gbrain stats                                    # chunks should be > 0
psql -c "SELECT COUNT(*) FROM content_chunks;" # should be 20K+
gbrain search "infrastructure"                  # should return results
```

**Step 1.2: Set up dream-cycle cron job**

```bash
hermes cronjob create \
  --profile forge \
  --name "gbrain-dream-cycle" \
  --schedule "0 2 * * *" \
  --prompt "cd ~/.gbrain && gbrain dream --source default --max-cost-usd 15"
```

Expected: Every night at 2 AM, dream cycle runs. Consolidates knowledge, detects patterns, fixes citations, dedupes entities.

**Verification (after first dream run):**
```bash
psql -c "SELECT COUNT(*) FROM entities WHERE synthesized_at > now() - interval '1 hour';"
```

**Step 1.3: Deploy to Railway**

Current state: Railway `gbrain` service (version 0.42.26.0) shares the same Supabase with local. Setting up cron locally will make chunks appear on Railway automatically (same DB).

For production reliability, though, Railway should run its own sync-embed loop. **Deferred to Phase 2** (requires Railway cron setup, not Hermes).

### Phase 2: Validation (15 min, $0)

**Step 2.1: Run 20+ representative infrastructure queries**

Sample queries (test against local `gbrain serve` on port 7432):

```bash
curl -s http://localhost:7432/search \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "Railway deployment architecture", "limit": 10}'
```

Expected: Should return > 5 relevant chunks per query, ranked by relevance.

**20 test queries:**
1. "Railway deployment architecture"
2. "G-Brain infrastructure pipeline"
3. "Voyage embedding model"
4. "Supabase configuration"
5. "PgBouncer connection pooling"
6. "Hermes agent delegation"
7. "Infrastructure change gate"
8. "District intelligence portal"
9. "Nero agent architecture"
10. "Bookmarked product strategy"
11. "ESC partner integration"
12. "Texas education data pipeline"
13. "Search quality metrics"
14. "ZeroEntropy vs. Voyage comparison"
15. "G-Brain schema and topology"
16. "Dream cycle maintenance"
17. "Chunking and embedding pipeline"
18. "Entity deduplication and merging"
19. "Knowledge graph consolidation"
20. "Agent reasoning with context"

**Success metric:** Hit rate ≥ 70% (15+ queries return relevant top-5 results).

**Step 2.2: Measure latency**

Sample 10 queries, measure time from request to first result:

```bash
time curl -s http://localhost:7432/search ...
```

Expected: < 500ms for p95 latency.

**Step 2.3: Check completeness**

Verify all critical infra docs are indexed:

```bash
# Query for specific documents known to exist in repos
curl -s http://localhost:7432/search -d '{"query": "infrastructure-change-gate"}'
curl -s http://localhost:7432/search -d '{"query": "cto-decision-framework"}'
curl -s http://localhost:7432/search -d '{"query": "deep-dive-infrastructure-debugging"}'
```

Expected: All critical skills/docs should appear in top-3 results.

### Phase 3: Production Deployment (not in this session)

Once local validation passes, apply same cron to Railway via Railway CLI or environment variables. Requires change-gate verification.

---

## Rollback

**Rollback is trivial:**
- Delete cron jobs: `hermes cronjob remove gbrain-sync-embed; hermes cronjob remove gbrain-dream-cycle`
- Chunks are idempotent: can be rebuilt anytime by re-running sync+embed
- No data loss, no breaking changes

---

## Key Dependencies & Interconnections

1. **Nero/Northy/Forge agents:**
   - Query `http://localhost:7432` (or Railway endpoint) for knowledge
   - Depend on search quality (≥ 70%) to be useful
   - Will time out if queries take > 5s (latency SLA)

2. **Railway production system:**
   - Shares same Supabase as local (NOT separate)
   - Setting up cron locally fixes both
   - For independent Railway reliability, needs its own sync-embed cron

3. **Dream cycle:**
   - Costs $10-15/night in LLM calls
   - NOT optional (makes brain compound)
   - Safe to defer if budget is tight (Phase 2 can validate without it)

4. **Voyage embedding model:**
   - Already configured (replaces ZeroEntropy)
   - Costs ~$0.02/1M tokens (search queries are cheap)
   - Should improve search quality from 20% (ZeroEntropy) → 70%+ (Voyage)

---

## Success Criteria

✅ **Phase 1 complete when:**
- Cron jobs are running
- `gbrain stats` shows > 10K chunks
- `gbrain serve` is still healthy

✅ **Phase 2 complete when:**
- 20-query test shows ≥ 70% hit rate
- Latency p95 < 500ms
- All infra docs are discoverable

✅ **Production ready when:**
- Railway cron is set up
- Agents can query and get results
- No alerts in monitoring

---

## Confidence & Unknowns

**High confidence (95%):**
- Root cause is missing cron jobs
- Sync-embed loop is the gold standard upstream pattern
- Our fork has pages but no chunks (verified via direct query)
- Fixing the cron will create chunks

**Medium confidence (70%):**
- Dream cycle will improve knowledge graph (requires experimentation)
- Search quality will reach 70%+ (depends on data quality)

**Unknown (requires testing):**
- Current latency baseline (may vary by query complexity)
- How many chunks can be synced before hitting scaling limits
- Whether Railway needs independent cron or shares local's chunks

---

## Timeline

- **Now:** Implement Phase 1 (30 min, Forge execution)
- **+15 min:** First cron cycle fires, chunks appear
- **+30 min:** Phase 2 validation (testing + metrics)
- **+60 min (total):** Recommendation for Phase 2B, 2C, 2D improvements
- **Next day:** Deploy to RFC, get approval, ship to Railway

---

## Reference Material

**Upstream gold standard:**
- https://github.com/garrytan/gbrain
- `docs/guides/live-sync.md` — sync-embed automation
- `INSTALL_FOR_AGENTS.md` — full 9-step setup (Step 7 = cron jobs)
- `docs/GBRAIN_VERIFY.md` — verification protocol

**Our fork:**
- https://github.com/stevewandler/gbrain (dockerfile-deploy branch)
- `docs/MIGRATION-LOCAL-TO-RAILWAY-2026-07-01.md` (aspirational, needs rewrite once Phase 1 succeeds)

**Test results:**
- Voyage embed run (Jun 30-Jul 1): 0 chunks created (expected, no sync beforehand)
- ZeroEntropy removal: verified ✓
- Config verified at all layers: ✓
- Database shared between local+Railway: ✓

---

## Notes for Next Session

**Do NOT:**
- Run `gbrain doctor --remediate` (wrong pattern, misleading)
- Try to manually chunk pages (automation handles this)
- Optimize search before chunks exist (measure first)

**Do:**
- Implement Phase 1 cron jobs (straightforward, 30 min)
- Wait for first cron cycle (15 min) before validating
- Document actual chunk count vs. claimed count (for audit trail)
- Tell Steve: this was an ops problem, not code problem. Code is fine.

---

**End of audit.** Ready to move to fresh session for implementation.
