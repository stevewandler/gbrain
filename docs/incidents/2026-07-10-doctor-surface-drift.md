# 2026-07-10 Doctor Surface Drift

## Summary

Steve received a G-Brain Doctor report from a Railway-hosted MCP surface that showed stale warnings:

- Calibration profile stale.
- Contextual retrieval coverage gap.

The local CLI Doctor showed a different and healthier state after local remediation:

- Health score: 100.
- Brain score: 99.
- Warnings: 0.
- CR pending: 0.
- Calibration current.

## Root cause

The remote MCP Doctor path did not route through the local canonical CLI wrapper. It used the Railway-hosted G-Brain MCP deployment, which can lag the local repository/runtime and produce stale Doctor output.

Canonical local path:

```text
/opt/homebrew/bin/gbrain
  -> /Users/stevewandler/.hermes/scripts/gbrain_wrapper.sh
  -> bun /Users/stevewandler/github-repos/gbrain/src/cli.ts
```

Remote Railway MCP Doctor is therefore a diagnostic cross-check, not the authoritative health source, unless deployment/version parity is proven.

## Impact

Agents interpreted remote MCP warnings as if they were local G-Brain state. This caused unnecessary reindex/calibration discussion and obscured the actual operational issue: health reports were coming from different surfaces.

## Corrective actions

- Documented Doctor surface authority in `docs/operations/doctor-authority-and-surface-routing.md`.
- Added a Codex skill, `gbrain-authority-check`, for any future Doctor/Hermes/Railway/local CLI disagreement.
- Updated the G-Brain checkup skill to prefer local CLI Doctor and treat MCP Doctor as a remote cross-check.
- Added explicit GitHub note requirements for future infrastructure changes.

## Prevention

No agent should summarize G-Brain health without naming its surface. If the surface is Railway MCP, the agent must also provide deployment/version identity and compare against local CLI before diagnosing the brain itself.
