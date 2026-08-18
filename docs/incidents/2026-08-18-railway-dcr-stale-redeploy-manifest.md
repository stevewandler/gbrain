# 2026-08-18 Railway DCR Stale Redeploy Manifest

Source context: Steve's G-Brain / Steve's Hermes.

**Status:** Resolved  
**Owner:** Steve Wandler  
**Runtime:** Railway production service `gbrain` (`a23b077c-0c15-4a2d-9ffb-c43be656c6cc`)  
**Public endpoint:** `https://gbrain-production-c2e0.up.railway.app`  
**Resolved deployment:** `0d62cfbd-1bd9-4275-b94f-2bb32a575735`  
**Source commit:** `884e0fefbd73c7362d1643489a358cdc1c904ea0` (`dockerfile-deploy`)

## Summary

The public Railway-hosted G-Brain MCP server exposed OAuth Dynamic Client
Registration even though the current Railway service setting, all three
start-command environment variables, `railway.json`, and the Dockerfile omitted
`--enable-dcr`.

The application was behaving correctly. Railway's ordinary Redeploy operation
had cloned the previous deployment's frozen
`meta.serviceManifest.deploy.startCommand`, which still contained
`--enable-dcr`. Editing the current `ServiceInstance.startCommand` did not
rewrite that historical deployment manifest, and three subsequent ordinary
redeploys continued to launch the stale command.

## Impact

- The public OAuth discovery document advertised `registration_endpoint`.
- `GET /register` reached an enabled registration route and returned `405` with
  `Allow: POST`.
- Any network caller could submit a Dynamic Client Registration request.
- DCR-created clients defaulted to consent-bearing `authorization_code`; the
  consent-bypassing `client_credentials` DCR grant remained rejected.
- No registration request was sent during this closeout. The registered-client
  count remained 90 before and after remediation.

## Root cause evidence

The current service setting was clean:

```text
bun run src/cli.ts serve --http --bind 0.0.0.0 --public-url https://gbrain-production-c2e0.up.railway.app
```

The old active deployment `6304b8f1-2c88-4116-9d87-0174afd13457` had
`reason=redeploy` and retained this frozen manifest command:

```text
bun run src/cli.ts serve --http --bind 0.0.0.0 --public-url https://gbrain-production-c2e0.up.railway.app --enable-dcr
```

Container ground truth matched that manifest:

```text
/proc/1/cmdline -> bun run src/cli.ts serve ... --enable-dcr
```

In the deployed source, DCR is controlled only by argv:

```ts
const enableDcrInsecure = args.includes('--enable-dcr-insecure');
const enableDcr = args.includes('--enable-dcr') || enableDcrInsecure;
```

`runServeHttp` passes `dcrDisabled: !enableDcr` to the OAuth provider, and the
startup banner is rendered from the same boolean. There was no second
environment-variable, database, or banner-only decision path.

## Corrective action

A fresh deployment was created from the configured GitHub source instead of
cloning the old deployment:

```bash
railway redeploy \
  --project dd2ad9b3-1782-4a8a-b494-11a348e5c8e2 \
  --environment f0255f05-ce5b-4e83-9bd0-c2795dd119f4 \
  --service a23b077c-0c15-4a2d-9ffb-c43be656c6cc \
  --from-source --yes
```

Deployment `0d62cfbd-1bd9-4275-b94f-2bb32a575735` completed successfully and
materialized the current flag-free start command.

No application code, environment variable, OAuth client, or database row was
changed as part of the remediation.

## Source of truth

For the command a Railway container is actually running, use these surfaces in
order:

1. `/proc/1/cmdline` inside the active deployment instance.
2. `activeDeployments[].meta.serviceManifest.deploy.startCommand` from
   `railway status --json`.
3. The active deployment's startup log.

`ServiceInstance.startCommand`, dashboard settings, repo config, and environment
variables describe configuration inputs. They are not proof of the argv used by
an already-captured deployment.

## Verification

The resolved deployment passed all acceptance checks:

```text
Deployment status: SUCCESS
/health: 200, version 0.46.19.0, engine postgres
PID 1 argv: no --enable-dcr or --enable-dcr-insecure
Startup banner: DCR: disabled
OAuth discovery: no registration_endpoint property
GET /register: 404
Registered clients: 90
```

Repeatable checks:

```bash
railway ssh --service gbrain --environment production /bin/cat /proc/1/cmdline \
  | tr '\0' ' '

curl -fsS https://gbrain-production-c2e0.up.railway.app/health | jq .

curl -fsS \
  https://gbrain-production-c2e0.up.railway.app/.well-known/oauth-authorization-server \
  | jq 'has("registration_endpoint")'

curl -sS -o /dev/null -w '%{http_code}\n' \
  https://gbrain-production-c2e0.up.railway.app/register
```

Expected results are a flag-free PID 1 command, healthy version output,
`false`, and `404` respectively.

The canonical local runtime checks remain:

```bash
/opt/homebrew/bin/gbrain doctor --json
/opt/homebrew/bin/gbrain call get_health '{}'
```

The local CLI Doctor is authoritative for Steve's laptop/runtime health. The
Railway `/health` endpoint is a remote liveness surface and is not comparable to
the local Doctor score.

## Recovery and rollback

Do not roll back to deployment `6304b8f1-2c88-4116-9d87-0174afd13457`; its
captured command re-enables public DCR. If the current deployment must be
replaced, deploy the desired known-good source revision with `--from-source`
after verifying the current start command is flag-free, then repeat the
acceptance checks above.

## Monitoring and prevention

- Treat `registration_endpoint` reappearing in OAuth discovery as a security
  regression.
- Require every production startup banner to contain `DCR: disabled`.
- After any Railway command/configuration change, inspect both the active
  deployment manifest and `/proc/1/cmdline`.
- Use `railway redeploy --from-source` when the desired outcome depends on
  current source or service configuration. Plain `railway redeploy` can clone
  the previous deployment's frozen service manifest and preserve stale argv.
- A healthy `/health` response does not validate OAuth security posture; keep
  the discovery and `/register` checks in the deployment acceptance gate.
