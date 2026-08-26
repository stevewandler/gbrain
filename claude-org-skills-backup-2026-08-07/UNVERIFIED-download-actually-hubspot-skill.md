---
name: hubspot
description: When reading or writing HubSpot CRM data (contacts, companies, deals) — Private App token, no refresh, long-lived.
language: bash
---

# HubSpot Skill — Private App Edition

## Read this first

Bookmarked uses **one HubSpot Private App token** for all agents. It is:
- **Long-lived.** No 30-minute expiry. No refresh flow. No `client_id` / `client_secret`.
- **Available as `$HUBSPOT_ACCESS_TOKEN`** in your shell environment (loaded from your profile `.env` by Hermes at startup).
- **Begins with `pat-`** and is ~44 characters long.

If you've seen older instructions about "tokens expire every 30 minutes" or "run `auth.sh` with a code from a redirect URL" — those describe the OAuth flow we no longer use. **Ignore them.**

## Bookmarked tracked-pipeline rule

For Bookmarked GBrain ingestion, operating-scorecard work, or CEO/revenue summaries, do **not** assume all HubSpot pipelines are operational truth. Steve clarified that Bookmarked tracks only specific pipelines.

Before ingesting HubSpot data into GBrain or using it in CEO signal briefs, require Zig/Nexus to provide:
- pipeline allowlist — which HubSpot pipelines Bookmarked actually tracks;
- reliable fields/stages;
- fields/stages to exclude as noisy, stale, or not operational truth;
- recommended snapshot shape, such as pipeline risk, renewal exposure, deal movement, or stage velocity;
- freshness cadence.

Until that allowlist exists, HubSpot is preliminary/Yellow even if API access is Green.

## Bookmarked ownership boundary

For Bookmarked operating-scorecard and CRM source-of-truth work:
- **Nexus is the HubSpot expert.** Nexus owns HubSpot business configuration/admin recommendations and changes where scopes allow: source tagging, properties/fields, pipeline hygiene, CRM source-of-truth design, and recommendations for making HubSpot reliable operating truth.
- **Woz is not the default HubSpot owner.** Woz owns only technical plumbing/integration dependencies that Nexus escalates, such as credentials/runtime support, non-HubSpot automation, or dashboard/Confluence data flow.
- **Zig owns revenue interpretation.** Zig interprets the pipeline against sales strategy; Nexus owns HubSpot mechanics; Ford synthesizes into the operating scorecard.
- If a request asks for HubSpot setup, source tagging, fields, or pipeline hygiene, route to Nexus first. Escalate to Woz only after Nexus identifies a technical dependency outside normal HubSpot administration.

## How to call HubSpot

Use the token directly as a bearer credential. No refresh step.

```bash
curl -s -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     "https://api.hubapi.com/account-info/v3/details"
```

For Python (any agent script):

```python
import os, requests
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
r = requests.get("https://api.hubapi.com/crm/v3/objects/deals", headers=HEADERS, params={"limit": 100})
r.raise_for_status()
```

## Self-diagnostic (run this first if anything looks wrong)

```bash
bash /opt/hermes/skills/crm/hubspot/scripts/healthcheck.sh
```

Expected output: `OK portalId=39855019 uiDomain=app-na2.hubspot.com`. Any other result is a real problem — do not paper over it.

## Scope / capability verification

HubSpot Private App tokens do **not** expose a scope introspection endpoint. The only way to verify which scopes are active is by probing endpoints and reading HTTP status codes.

**When to use:** When asked what scopes are active, when a new scope is granted and needs verification, or when an endpoint returns 403 and you need to confirm which scope is missing.

**Pattern:** Test a known endpoint for each scope area. A `200` means the scope is active; `403` means it's missing.

```bash
# Core CRM scopes (all should return 200 if active)
echo "deals read:"    && curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/objects/deals?limit=1&properties=dealname"
echo ""
echo "contacts read:" && curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/objects/contacts?limit=1"
echo ""
echo "companies read:" && curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/objects/companies?limit=1"
echo ""
echo "owners read:"    && curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/owners?limit=1"
echo ""
echo "line_items:"    && curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/objects/line_items?limit=1"
echo ""
echo "pipelines:"     && curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/pipelines/deals"

# Write scope — use a real deal ID (fetch first, then PATCH a non-critical field)
DEAL_ID=$(curl -s -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" "https://api.hubapi.com/crm/v3/objects/deals?limit=1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['results'][0]['id'])")
echo ""
echo "deals write (PATCH):" && curl -s -o /dev/null -w "%{http_code}" -X PATCH -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"properties":{"dealtype":"newbusiness"}}' "https://api.hubapi.com/crm/v3/objects/deals/$DEAL_ID"
# Note: This makes a real write. Use a real deal ID, not a test ID, to avoid 404s.
```

**Interpretation:**
| Status | Meaning |
|--------|---------|
| `200` | Scope is active — proceed |
| `403` | Scope missing — report to Steve with the endpoint and required scope |
| `404` | Endpoint valid but resource doesn't exist (e.g., bad deal ID on write test) — re-run with a real ID |
| `401` | Token is invalid/rotated — escalate to Steve immediately |

**Automation scope** (workflows) requires a separate endpoint and is not tested by CRM object probes. If workflows are the question, test with the Workflows API directly or report that the automation scope needs to be added in HubSpot Private App settings.

## Interpreting failures (this is the part that has gone wrong before)

| HTTP | Meaning | Action |
|---|---|---|
| **200** | Working. | Proceed. |
| **401 Unauthorized** | Token was rotated or revoked in HubSpot. | **Escalate to Steve.** Do NOT attempt OAuth refresh — there is no refresh token to use. The fix is for Steve to mint a new Private App token in HubSpot and update `/home/raju/.hermes/shared-credentials.env`. |
| **403 Forbidden** | Token is valid but lacks the scope for this endpoint. | Tell Steve which endpoint and scope. He'll grant it in the Private App settings. Do not try alternate auth. |
| **429 Too Many Requests** | Rate limit hit (HubSpot allows ~100 req / 10s per portal). | Wait, then retry with exponential backoff. **This is NOT an auth problem** — do not report it as one. |
| **5xx** | HubSpot upstream issue. | Retry once; if persistent, escalate. |

## What you must never do

- **Never claim the token "needs refreshing."** Private App tokens do not refresh.
- **Never run an OAuth code-exchange.** There is no code, no redirect URI, no client secret in this setup.
- **Never edit `$HUBSPOT_ACCESS_TOKEN` from within an agent session.** Token rotation happens out-of-band by Steve.
- **Never echo, log, or post the token value.** It's a credential.

## Token rotation runbook (for Steve / Raju, not for agents)

Only when intentionally rotating:

1. HubSpot UI → Settings → Integrations → Private Apps → bookmarked-private-app → "Rotate access token."
2. Copy the new `pat-...` value.
3. Edit `/home/raju/.hermes/shared-credentials.env` — replace the `HUBSPOT_ACCESS_TOKEN=` line.
4. Run `sudo bash /opt/hermes/skills/crm/hubspot/scripts/propagate-to-profiles.sh` to push the new token to each profile's `.env`.
5. `sudo systemctl restart 'hermes-gateway-*'` to pick up the new value.
6. `bash /opt/hermes/skills/crm/hubspot/scripts/healthcheck.sh` should print OK.

That is the entire rotation procedure. There is nothing else. If anyone tells you a Hermes agent needs to do an OAuth flow to get HubSpot working, they are reading documentation from a previous architecture.

## Common queries (cheat-sheet)

```bash
# Account / portal info
curl -s -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" https://api.hubapi.com/account-info/v3/details

# Deals (paginated; use `after` cursor for next page)
curl -s -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  "https://api.hubapi.com/crm/v3/objects/deals?limit=100&properties=dealname,amount,dealstage,closedate"

# Pipelines (so you know stage IDs)
curl -s -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" \
  "https://api.hubapi.com/crm/v3/pipelines/deals"

# Contacts search
curl -s -X POST -H "Authorization: Bearer $HUBSPOT_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{"filterGroups":[{"filters":[{"propertyName":"email","operator":"EQ","value":"someone@example.com"}]}]}' \
  https://api.hubapi.com/crm/v3/objects/contacts/search
```

## Pagination, always

HubSpot list endpoints return a cursor `paging.next.after` when more results exist. Always loop until exhausted, or you'll silently miss data:

```python
deals, after = [], None
while True:
    params = {"limit": 100, "properties": "dealname,amount,dealstage,closedate"}
    if after: params["after"] = after
    r = requests.get("https://api.hubapi.com/crm/v3/objects/deals", headers=HEADERS, params=params).json()
    deals.extend(r.get("results", []))
    after = r.get("paging", {}).get("next", {}).get("after")
    if not after: break
```
