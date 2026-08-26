# Bookmarked — Claude Team Account Audit & High-Impact Plan
**Date:** 2026-08-07 · **Org ID:** 3a2473e2-27b6-4480-902e-3f520cb2ba42 · **Plan:** Team (9 seats)
**Audited by:** live walk of every page under claude.ai/admin-settings + current support.claude.com docs

---

## 1. Current state (verified, not inferred)

### Seats & people
| Member | Role | Seat tier | Usage-credit limit | MTD spend |
|---|---|---|---|---|
| Steve Wandler | Primary owner | Premium | $700 | **$666.61** |
| Patrick | Admin | Premium | $150 | $0.00 |
| Jan | User | Standard | **$0** | $0.00 |
| Michelle | User | Standard | **$0** | $0.00 |
| Teela Watson | User | Standard | **$0** | $0.00 |

- 9 seats purchased, **4 unassigned**. Seat changes already pending for next cycle.
- Next invoice Sep 2, 2026 — projected **$346.45** (subscription only).

### Usage / spend
- **$666.61 of the $700 monthly cap consumed — 95% — with the cap not resetting until Sep 1.**
- Current credit balance $68.52, auto-reload ON.
- Usage credits ON; member credit requests ON.
- Default seat limits: $10/Standard, Unlimited/Premium — but the three Standard users are individually overridden to $0.
- Service spend (Claude Code Review, Claude Tag): $0, unlimited.

### Organization & access
- Org instructions field: **empty (0/3000).**
- Domain listed as `www.bookmarked.com`, **not verified.**
- Therefore unavailable: SSO, domain capture/discovery, JIT provisioning, "restrict organization creation."
- Provisioning = invite-only; new-member approval = admin approval required (good). Invite link live until Oct 30, 2026.

### Capabilities (all ON)
Web search · Interactive content · Ask Bookmarked (org search) · Artifact connectors · Inline visualizations · Cloud code execution · Network egress (sandbox allowlist = package managers only).

### Data & privacy
Rate chats ON · Location metadata ON · **Public projects ON.**

### Claude Code
Desktop/Mobile/Web ON · Remote control ON but **"Require trusted devices" OFF** · Cloud sharing ON · Quick setup ON · **Fast mode OFF** · Routines ON · Artifacts ON, external sharing OFF · Dynamic workflows ON · Channels ON · Claude Code analytics + GitHub analytics ON · GitHub org `BookmarkED-Corp` linked · Managed settings not reviewed/locked · No Anthropic-hosted cloud environments created.

### Cowork
Enabled · Cowork in the cloud ON · Dispatch ON · Auto-approve ON · **"Skip all approvals" ON** · **"Always allow" for connector tools ON** · Require trusted devices ON · No OTel monitoring configured.

### Claude in Chrome
Enabled · Password managers OFF · **Default = "Allow all sites," blocklist empty.**

### Claude Tag (Slack)
**Not set up.** Sits on the "Start setup" wizard. Claude in Slack migrated to Claude Tag on Aug 3, 2026.

### Libraries
- **21 org skills** published (CRO, CFO, CPO, compliance-advisor, company-context, brand standards, jira-operating-model, skill-factory, etc.). Skills / user-created skills / sharing all ON.
- **16 connectors** incl. Atlassian, Bookmarked GBrain (custom), Carta, GitHub, Gmail, Google Calendar, Google Drive, HubSpot, Jam. Desktop-extension allowlist not enforced.
- Plugins: Anthropic & Partners marketplace available (91 plugins), none curated for the team.

### Other products
Claude Design ON (public links ON) · Office Agents ON · Claude Science OFF (correct — not a life-sciences org).

---

## 2. The three findings that matter

### 🔴 F1 — You are one day from a hard stop, and the burn rate is the real story
$666.61 spent in roughly the first five days of the billing cycle. At that pace the month lands near **$3,000–4,000** in usage credits on top of subscription. The $700 cap will cut off usage credits within ~24 hours, and 100% of that spend is **one person**. This is simultaneously the cost problem and the concentration problem: the account is a single-user power account with four spectators attached.

### 🔴 F2 — The team is structurally locked out
Jan, Michelle, and Teela have a **$0** usage-credit limit on Standard seats. They hit their rate limit and stop — no overflow, no request path that resolves. Patrick has $150 and has used $0. The org's entire AI leverage is Steve's personal throughput. Nothing about the current configuration produces team collaboration, shared context, or compounding.

### 🟠 F3 — Autonomy is fully unlocked while identity is fully unverified
"Skip all approvals" + "Always allow connector tools" + Dispatch, running against Gmail, Drive, HubSpot, Carta, Atlassian and GitHub — with Claude in Chrome allowed on *all* sites, no verified domain, no SSO, remote Claude Code control without device trust, and public projects on. Each toggle is individually defensible; together they are a prompt-injection blast radius with no identity perimeter under it. Carta and Gmail are the ones that would hurt.

---

## 3. The plan

### Phase 0 — Today (30 minutes, stops the bleeding)
1. **Raise the org spend cap** to a deliberate number (recommend **$1,500/mo**) *and* set threshold alerts. The cap is a circuit breaker, not a budget — being pinned at 95% mid-month means it's doing neither job.
2. **Re-tier the seat limits:** Steve $900 · Patrick $250 · Jan/Michelle/Teela **$75 each**. Nonzero is the whole point: it converts three people from blocked to usable.
3. **Decide the 4 unassigned seats.** Either fill them this month or release them at the next cycle. Idle seats on a Team plan are pure carry.
4. **Turn off "Skip all approvals"** in Cowork. Keep auto-approve; drop the blanket bypass. Nobody on a 5-person team needs it, and it's the single highest-risk toggle in the account.

### Phase 1 — This week (the highest-leverage moves)
5. **Verify the domain** — and fix the entry: it should be `bookmarked.com`, not `www.bookmarked.com`. This one action unlocks SSO, domain capture, JIT provisioning, and "restrict organization creation" (which stops shadow personal Claude accounts on your domain). It is the cheapest compliance + onboarding win available.
6. **Write the Organization Instructions** (currently empty, 3,000 chars, applies to every conversation org-wide, overrides personal preferences). This is free token-efficiency and free brand consistency. Load it with: the evidence-discipline rule (facts or explicit unknowns), the privacy rule (no real district/contact names in public artifacts), locked brand phrases, the "ask in product terms" rule, and an output-brevity standard. Every conversation by every member inherits it. Changes take up to an hour to propagate.
7. **Set up Claude Tag in Slack.** This is the #1 collaboration and #1 cost-shape change in the account:
   - No per-seat charge — consumption-billed, so it scales with value not headcount.
   - Zero per-user setup; Owner configures once, whole channel benefits.
   - It uses your *existing* org connectors — HubSpot, Drive, Gmail, Atlassian, GitHub, GBrain — inside the tool Jan, Michelle, Teela and Patrick already live in.
   - Set per-channel spend limits (start $100/channel/mo) with 75%/95% alerts.
   - Start with 3 channels: one revenue/HubSpot, one eng/Jira, one ops. Note: channel work bills to the org; DMs bill personally.
   - Requires Owner (not Admin) to configure — that's you, not Patrick.
8. **Lock Claude Code managed settings.** Define org-level permissions and allowed directories once; it overrides user and project settings across CLI, IDE and Desktop. Pair with **"Require trusted devices" ON** now that remote control is enabled.

### Phase 2 — Next two weeks (make the team compound)
9. **Curate the skill library for humans, not just for Steve.** You have 21 org skills, all written in CEO voice and all invisible to the people who'd benefit. Pick the 5 that a non-Steve user would actually reach for (company-context, brand-messaging-intelligence, compliance-advisor, jira-operating-model, collateral-creator), and run a 45-minute working session showing Jan/Michelle/Teela/Patrick how to invoke them. An unused skill library is a maintenance cost, not an asset.
10. **Turn on Ask Bookmarked properly.** Org search is enabled but only pays off once Drive/Confluence/HubSpot content is reachable and people know to ask it. Make it the default first stop before anyone asks Steve a question — that is the direct substitute for "Steve is the API."
11. **Use Claude Code analytics** (already ON) to see where the $666 actually goes — accept rates, code generated, session shapes. You cannot optimize spend you can't attribute. Revisit Fast mode only after you see the data; it bills at a premium and should stay OFF until there's a measured reason.
12. **Tighten Claude in Chrome:** switch the default from "Allow all sites," or at minimum blocklist the high-consequence surfaces — Carta, banking, HubSpot admin, Supabase.
13. **Review "Public projects" ON.** Fine for a 5-person team that wants shared context; revisit before headcount grows or before any district/student-adjacent material lands in a project.

### Phase 3 — Structural (this quarter)
14. **Move recurring work from interactive sessions to Routines** (already enabled). Scheduled and webhook-triggered Claude Code runs are dramatically cheaper per unit of output than long human-in-the-loop sessions, and they're where the district-intel/board-crawl/watchdog patterns you already run belong.
15. **Re-evaluate seat mix at the next cycle** against real data: if Patrick's usage stays near zero, he's a Standard seat, not Premium (a $80–100/mo swing). Premium seats are 5× Standard usage — pay for that only where consumption proves it.
16. **Set the enforcement floor:** desktop-extension allowlist ON, so the connector surface stays curated as the team grows.

---

## 4. Expected impact

| Lever | Effect |
|---|---|
| Cap raise + per-seat reallocation | Removes the hard stop; distributes work off a single ceiling |
| Claude Tag in 3 Slack channels | 4 people go from spectators to users at **$0 incremental seat cost** |
| Org instructions | Every conversation inherits brand + evidence discipline — no re-prompting tax |
| Domain verification + SSO | Closes the identity gap; kills shadow accounts on the domain |
| Skip-all-approvals OFF + Chrome blocklist + trusted devices | Largest risk reduction in the account, zero capability lost |
| Skill enablement session | Converts a 21-skill library from Steve-only to team asset |
| Routines migration | Structural cost reduction — the only lever that lowers burn without lowering output |

**The one-line version:** the account is configured as a single-user power tool with maximum autonomy and minimum identity control. Every high-impact move points the same direction — spread the usage, verify the perimeter, and put Claude where the team already works.

---

## Sources
- [What is the Team plan?](https://support.claude.com/en/articles/9266767-what-is-the-team-plan)
- [Purchase and manage seats on Team plans](https://support.claude.com/en/articles/12004354-purchase-and-manage-seats-on-team-plans)
- [What is Claude Tag?](https://support.claude.com/en/articles/15594475-what-is-claude-tag)
- [Get started with Claude in Slack](https://support.claude.com/en/articles/11506255-get-started-with-claude-in-slack)
- [Manage usage credits for Team and seat-based Enterprise plans](https://support.anthropic.com/en/articles/12005970-extra-usage-for-claude-for-work-team-and-enterprise-plans)
- [Release notes](https://support.claude.com/en/articles/12138966-release-notes)
- [How is my Team plan bill calculated?](https://support.claude.com/en/articles/9267289-how-is-my-team-plan-bill-calculated)
