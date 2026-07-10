# Doctor Authority and Surface Routing

Updated: 2026-07-10

## Rule

Every G-Brain health report must name the surface it used before it interprets results.

For Steve's production brain, the authoritative Doctor path is:

```text
/opt/homebrew/bin/gbrain
  -> /Users/stevewandler/.hermes/scripts/gbrain_wrapper.sh
  -> bun /Users/stevewandler/github-repos/gbrain/src/cli.ts
```

Remote MCP Doctor surfaces, including Railway-hosted MCP, are cross-checks. They are not allowed to override the local CLI unless the report proves the remote deployment is on the same code version, database, schema pack, and source set.

## Required health-report fields

Agents must include these fields in G-Brain Doctor summaries:

- Surface used: local CLI, local stdio MCP, Railway MCP, or another named endpoint.
- Command or tool name used.
- Resolved binary/script path when local CLI is used.
- Deployment/version identity when remote MCP is used.
- Database/project identity at a non-secret level.
- Doctor status, health score, brain score, warning count, and warning names.
- Whether local CLI and remote MCP agree. If they disagree, call it surface drift.

## Surface drift protocol

If two surfaces disagree:

1. Stop treating the warning as a data-quality fact.
2. Run the local CLI Doctor and record the resolved wrapper path.
3. Run the remote MCP Doctor and record the remote deployment/version identity.
4. Compare database, schema pack, source count, calibration state, and queue state.
5. Fix or redeploy the stale surface before telling the operator the brain itself is unhealthy.

## GitHub note requirement for infrastructure changes

Any change to wrappers, LaunchAgents, cron jobs, Railway deploys, MCP servers, queue workers, source sync, embeddings, calibration, or Doctor checks must leave a GitHub note in `docs/operations/` or `docs/incidents/`.

The note must include:

- Owner and purpose.
- Exact runtime path or deployment surface.
- Source of truth and fallback path.
- Verification command.
- Rollback or recovery command.
- Monitoring signal that proves the change is still working.
- Known stale-result or drift failure mode.

If this note is missing, the setup is incomplete.
