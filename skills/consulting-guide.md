# Skill: Sumo Logic Consulting Guide (Virtual TAE)

## Intent

Act as a virtual Technical Account Engineer (TAE) for Sumo Logic — providing architecture advice, design reviews, trade-off analysis, and best-practice guidance, not just running queries. This skill is the entry point for any open-ended, "how should I", or design question.

## Prerequisites

- Access to this skills library (`get_skill` tool)
- Awareness that the user may be at any stage: new deployment, optimisation, incident, or architecture review

## Context

**Use this skill when:**

- User asks a broad or open-ended question ("how should I set up X?", "what's the best way to Y?")
- User asks a trade-off question ("should I use X or Y?", "monitors vs scheduled search?")
- User wants a design review or architecture check ("is my setup sensible?", "review my partition design")
- User is troubleshooting a platform-level problem ("why is Sumo Logic so expensive?", "why are my searches slow?")
- User asks about getting started or onboarding ("how do I structure my data?")
- Any question that doesn't map cleanly to a specific data task

**Don't use this when:**

- The user has asked a specific, well-scoped data task (e.g. "run this query", "find my logs") — go straight to the relevant task skill instead

---

## Consulting Approach

### 1. Open with a Focus Check

Before diving into advice, use these **opening questions** to calibrate the session. A real TAE always opens an onboarding or advisory session this way:

- "Are there specific architecture issues or topics top of mind for you?"
- "What does your environment look like (cloud provider, on-prem, Kubernetes)?"
- "Are there key or high-priority log sources you need to cover?"
- "Where is your Sumo Logic deployment at now vs. when it's complete?"
- "What is the audience skill level? (developer, analyst, admin?)"
- "Is it just logs, or also metrics and traces?"

### 2. Understand Before Advising

Before giving advice, briefly establish:
- What tier/plan is the user on? (Enterprise Suite with tiers, or Flex?)
- What is the data volume and source type? (logs, metrics, traces?)
- What is the user's role? (admin, developer, analyst, architect?)
- What is the immediate goal vs. the underlying need?
- Are they new/POV stage, onboarding, or in production?

Use MCP tools to gather context before advising where possible:
- `get_account_status` — plan type, credits, subscription
- `explore_log_metadata` — what data sources exist
- `get_sumo_partitions` — how data is currently organised
- `analyze_data_volume` — what's driving ingest volume

### 3. Map the Question to the Right Skill

See the **Question Taxonomy** section below. Fetch the relevant skill(s) with `get_skill` before advising.

### 4. Give Layered Advice

Structure advice around the **four platform layers** (see Architecture Framework below):
1. Start with the layer where the problem originates
2. Explain the trade-offs at that layer
3. Show how the choice affects other layers

### 5. Provide Concrete Next Steps

Every advisory response should end with concrete, actionable next steps the user can take in Sumo Logic — whether that's enabling a policy, running a query, creating a partition, or adjusting a monitor.

---

## Architecture Framework: The Four Layers

Every Sumo Logic deployment has four layers. Problems at one layer ripple upward. Good architecture means making deliberate decisions at each layer.

```
┌─────────────────────────────────────────────────┐
│  Layer 4: MONITORING & ALERTING                 │
│  Monitors, dashboards, scheduled searches       │
│  Skills: alerting-monitors, dashboards-overview │
├─────────────────────────────────────────────────┤
│  Layer 3: ACCELERATION                          │
│  Scheduled Views (pre-aggregated data)          │
│  Field Extraction Rules (index-time fields)     │
│  Skills: search-scheduled-views,                │
│          admin-field-extraction-rules           │
├─────────────────────────────────────────────────┤
│  Layer 2: ORGANISATION                          │
│  Partitions (indexes), data tiers               │
│  Source categories, routing expressions         │
│  Skills: admin-partition-design,                │
│          search-indexes-partitions              │
├─────────────────────────────────────────────────┤
│  Layer 1: COLLECTION                            │
│  Collectors, sources, source categories         │
│  OpenTelemetry, HTTPS, C2C, Installed           │
│  Skill: data-collection-patterns                │
└─────────────────────────────────────────────────┘
```

**Golden rule:** Problems felt at Layer 4 (slow dashboards, expensive searches) are almost always caused by under-investment at Layers 2 and 3.

---

## Question Taxonomy

### "My searches are slow / expensive"

**Fetch:** `search-optimize-queries`, `search-indexes-partitions`, `admin-partition-design`

**Diagnostic questions:**
- Is there an `_index=` in the scope? (If not → partition issue, Layer 2)
- Are there keywords before the first `|`? (If not → bloom filter not used, fix at query level)
- Is the data in a single monolithic partition? (If yes → redesign, Layer 2)
- Are the same expensive queries run repeatedly? (If yes → scheduled view candidate, Layer 3)
- Does the query use complex regex or `threatip`/`geoip`? (If yes → view caching candidate, Layer 3)

**Quick wins (in order of effort):**
1. Add `_index=` to scope (zero code change, immediate reduction)
2. Add 1–2 keywords to scope (zero code change, immediate reduction)
3. Identify and push slow repeated queries to scheduled views (admin effort, 10x–100x gains)
4. Redesign partition strategy (significant effort, 5x–1100x gains)

---

### "My dashboard is slow / timing out"

**Fetch:** `search-optimize-with-views`, `search-scheduled-views`, `dashboards-panel-types`

**Common causes:**
- Panels query raw logs over days/weeks without a scheduled view
- Time series panels missing `timeslice` or `transpose`
- Too many panels refreshing simultaneously

**Solution path:**
1. Identify which panels are slow (check their queries)
2. Check if a scheduled view exists that covers this data (`list_scheduled_views`)
3. If yes: transform panel query to use `_view=name | sum(_count) ...` pattern
4. If no: request admin create a view, or redesign as a lower-frequency scheduled search

---

### "How should I design my partitions?"

**Fetch:** `admin-partition-design`

**Key principle:** All partitions should use the **same metadata field** as their routing expression (usually `_sourceCategory`). This enables the engine's query rewriting feature — queries automatically restrict to the right partition without needing `_index=`.

**Seven rules summary:**
1. Use one consistent metadata field across all partitions
2. Group by use case (security, application, infrastructure)
3. Use simple, lowercase names (`prod_app_logs` not `Production-Application-Logs`)
4. Put small, frequently-queried data in dedicated partitions (avoid burying it in default)
5. Keep the default partition to < 10% of total ingest if possible
6. Don't create too many partitions (< 50 is a reasonable target)
7. Use FERs for complex routing logic that can't be expressed in source category alone

---

### "How should I set up alerting?"

**Fetch:** `alerting-monitors`, `alerting-time-compare-anomaly`

**Decision framework:**

| Situation | Recommended approach |
|---|---|
| Fixed threshold (e.g. error rate > 5%) | Static monitor |
| Traffic with weekly seasonality | `compare with timeshift` + Static monitor |
| Unknown normal baseline | Anomaly monitor |
| Multiple similar entities (hosts, services) | Outlier monitor or Anomaly per entity |
| High volume, aggregate metric | Metrics monitor (avoid log monitor if metric exists) |
| Compliance / uptime reporting | SLO monitor |
| Legacy alert migration | Migrate to stateful Monitor (not Scheduled Search) |

**Alert grouping is critical:** Always set a grouping field (e.g. `host`, `service`, `source_name`) to prevent alert storms when multiple entities fail simultaneously.

---

### "Should I use Infrequent tier or Continuous?"

**Fetch:** `search-indexes-partitions`

| Factor | Use Continuous | Use Infrequent |
|---|---|---|
| Query frequency | Daily or more | Weekly or less |
| Dashboard usage | Yes (panels load on open) | No (scans on every load) |
| Real-time alerting | Yes (monitors run continuously) | No (monitors scan = cost) |
| Archive/compliance data | No | Yes (low ingestion cost) |
| Data accessed ad-hoc | No | Yes (pay per search) |

**Key insight:** Monitors that run on Infrequent tier data incur scan costs on every evaluation. Budget for this or move alerting data to Continuous.

---

### "How should I collect my data?"

**Fetch:** `data-collection-patterns`

**Decision by source type:**

| Source | Recommended pattern |
|---|---|
| Application logs on VMs/bare metal | Installed Collector (local file source) |
| Cloud service (AWS, GCP, Azure) | Cloud-to-Cloud (C2C) or Hosted Collector + cloud source |
| Kubernetes | OpenTelemetry Collector (Helm chart) |
| Custom application | HTTPS Source (most flexible) |
| Network/syslog devices | Installed Collector with Syslog source |
| SaaS applications (Okta, Salesforce, etc.) | Cloud-to-Cloud (C2C) Framework |

**Source category naming:** Use a consistent 3-level hierarchy:
`environment/technology/role` → `prod/nginx/access`, `dev/kubernetes/pod-events`

---

### "How do I reduce my Sumo Logic bill?"

**Fetch:** `search-optimize-queries`, `cost-analyze-search-costs`, `admin-partition-design`, `search-scheduled-views`

**Ingest cost reduction (Layer 2):**
- Identify top ingest contributors: `analyze_data_volume` tool
- Move low-access data to Infrequent tier
- Filter noisy data at the collector (drop debug logs, health checks)

**Search scan cost reduction (Layer 3):**
- Identify expensive queries: `run_search_audit_query` or `analyze_search_scan_cost`
- Add `_index=` and keywords to poorly-scoped queries (immediate gain)
- Move repeated expensive queries to scheduled views (ongoing gain)

**Dashboard cost reduction:**
- Audit dashboard refresh rates — daily dashboards don't need 15-minute refresh
- Replace raw-log panels with view-based panels

---

### "My data isn't arriving / collector is unhealthy"

**Fetch:** `audit-system-health`

**Immediate triage:**
```
MCP: search_system_events
  use_case: "collector_source_health"
  from_time: "-1h"
```

**Common causes:**
- Collector offline: check collector host network, disk space, credentials
- Source misconfigured: verify file path, permissions, encoding
- Rate limiting: check for rate limit events in audit index
- Ingest quota exceeded: check account status

**Escalation path:** If `Health-Change` events show `unhealthy` persisting > 30 minutes, open a support ticket with the `trackerid` value from the event for faster resolution.

---

### "How should I set up RBAC / access control?"

**Fetch:** `admin-rbac-security`

**Sumo Logic security architecture has three layers:**
1. **Authentication** — User/password or SAML (SAML strongly recommended; can be made mandatory with an allow-list for emergency access)
2. **RBAC: Capabilities** — What actions a role can perform (view collection, manage users, create alerts, etc.)
3. **RBAC: Role Search Scope** — What data a role can see (`_sourceCategory=prod/*`, `_sourceCategory=security/*`, negation patterns like `!(_sourceCategory=*restricted*)`)

**Standard role tiers:**
- **Admin**: all capabilities, `*` search scope
- **Power User**: deploy collection, create content and alerts, limited admin capabilities
- **User**: run searches, view config, create alerts
- **Restricted User**: very limited view/search only

**Key decisions:**
- Decide on capability layers before users are created
- Decide on search scope groups (functional scope like `prod/*` or environment scope)
- Use SAML with role provisioning attribute for automated role assignment
- Use service accounts (dedicated email, restricted role) for API automation — never use personal API keys in automated systems

---

### "I want to set up admin monitoring / health dashboards"

**Fetch:** `admin-alerting-and-monitoring`, `audit-system-health`

**Admin monitoring checklist:**
1. Enable three audit policies: Audit Index, Data Volume Index, Search Audit
2. Install recommended apps: Data Volume App v2, Audit App, Search Audit App
3. Set up five core alerts:
   - Ingest spike/drop (data volume time compare)
   - Collection stopped (GONE state detection)
   - Rate limiting (audit index)
   - High scan costs (search audit view)
   - Unhealthy collection events (system events index)
4. For large orgs (3,000+ source categories): create data volume scheduled view first

---

### "How do FERs (Field Extraction Rules) help?"

**Fetch:** `admin-field-extraction-rules`

**Speed hierarchy (best to worst):**
1. FER-extracted index-time field in scope → **fastest** (indexed, no parse at query time)
2. Keyword in scope + search-time parse → fast
3. Search-time parse + `where` filter → slow (parses all events, then filters)

**When a FER is worth creating:**
- Same field parsed in 5+ frequently-run queries
- Field used in high-traffic dashboard panels
- Numeric `where` comparisons on frequently queried data (stripe pattern → 342x speedup)
- Routing: when partition membership depends on a field value, not just source category

---

## Key Trade-Off Tables

### Monitors vs Scheduled Searches

| Factor | Monitor | Scheduled Search |
|---|---|---|
| Alerting model | Stateful (tracks open/resolved) | Stateless (fires every run) |
| Detection | Static, Anomaly, Outlier | Static only |
| Alert grouping | Yes (per entity) | No |
| Infrequent tier | Scan cost per run | Same |
| Recommended | Yes (modern, preferred) | Legacy only |

### Anomaly vs Outlier Detection

| Factor | Anomaly | Outlier |
|---|---|---|
| Baseline training | ML-learned, adapts over time | Statistical (rolling window) |
| Sensitivity control | Sensitivity slider | Threshold multiplier |
| Best for | Single time series | Multiple entities comparison |
| False positive rate | Lower | Higher |
| Cost | Higher (ML computation) | Lower |
| Recommended | Prefer for single-series | Use for per-entity comparison |

### Partition vs No Partition

| Factor | Well-partitioned | Monolithic (default only) |
|---|---|---|
| Scan per query | GB (targeted) | TB (full scan) |
| Query rewriting | Auto-applies `_index=` | Never applies |
| Cost (Flex) | Low | Very high |
| Setup effort | Medium (admin, one-time) | None |
| Recommended | Yes for > 100GB/day | Not recommended |

---

## Customer Maturity Stages

Sumo Logic customers typically evolve through four stages. Advising should be anchored to where the customer currently is:

| Stage | Name | Characteristics |
|---|---|---|
| **Stage 1 — Initial** | Comprehensive Collection | Logs, metrics, traces collected; rich query language; OOB dashboards; partitioned by tier/performance |
| **Stage 2 — Managed** | Automated Analytics | ML-driven analytics (Outlier, LogReduce); Dev/Test analytics; Audit & Compliance; Cloud SIEM |
| **Stage 3 — Measured** | Service-Driven (SLI/SLO) | SLI/SLO defined; 3rd party integrations for notification/collaboration; refined collection/tiering |
| **Stage 4 — Optimised** | DevSecOps Extended | Full platform suite; BI/ITxM/AIOps integration; automated workflows; best-of-breed tooling decisions |

**Security maturity** follows a parallel ladder:
- Stage 1 — Log management, granular analytical queries (no SOC)
- Stage 2 — Cloud security monitoring, dashboards and alerts (no SOC)
- Stage 3 — Automated threat detection, incident investigation, threat hunting (SOC present)
- Stage 4 — Automated threat response, DevSecOps, Cloud SOAR

---

## Useful First Steps for New Deployments

When a user is setting up Sumo Logic from scratch or reviewing an existing deployment, suggest these actions in order:

1. **Audit policies** — Enable Data Volume Index, Search Audit, Audit Index (Admin → Security → Policies)
2. **Source category naming convention** — Agree on `env/technology/role` format before ingesting at scale
3. **Partition design** — Plan partitions by use case using the 7 rules before data volume grows
4. **FER design** — Identify 3–5 high-value fields to extract at index time for top log sources
5. **Admin alerts** — Set up ingest monitoring and collection health alerts on day one
6. **Scheduled views** — Identify top 3 slow/expensive repeated queries within first month and build views
7. **Dashboard strategy** — Decide on the four dashboard types for each persona (ops, security, business)
8. **Subdomain** — Set up a named subdomain (`myco.us2.service.sumologic.com`) for SSO/SAML and stable bookmarks
9. **Support account** — Enable a support account user (minimum 1 year, infinite recommended) for Sumo Support access
10. **Admin recommended folder** — Create a Sumo Admin folder in Admin Recommended; import admin apps; grant manage permissions to admin role only
11. **Audit partition retention** — Set Sumo Audit partition retention to 365 days
12. **Register for release notes** — Subscribe to RSS feed; register at `status.sumologic.com`
13. **Weekly usage report** — Set up email for weekly usage report from Admin settings
14. **Content management governance** — Establish naming conventions for monitors, scheduled views, and folders before users proliferate content

**Full CIP onboarding checklist tracks:**
- **Track 1-2:** Log ingestion (throttling, processing rules, FER, lookup tables, partitions, scheduled views, scheduled search)
- **Track 1-4:** Alerting (monitors, alert groups, mute, subscriptions)
- **Track 1-5:** Dashboards and reports (panels, public dashboards, scheduled reports)
- **Track 1-6:** Org management (credit usage, Sumo orgs)
- **Track 1-7:** SLOs (definition, dashboards, alerts)
- **Track 1-8:** Security (access keys, ACL, role search filter, SAML)
- **Track 2-1:** BP Application (partition management, subdomains, audit apps, support account)
- **Track 2-2:** BP Process (sourceCategory/partition naming governance, regular training, Infrequent tier usage review)
- **Track 3-1:** Admin training (content management naming rules, Admin Recommended folder usage)
- **Track 3-2:** User training (field naming conventions, Infrequent tier best practices, Scheduled Search vs Monitor)

---

## Related Skills

All skills in this library are relevant — consult this guide to find the right one. Key entry points:

- [Search Log Basics](./search-log-search-basics.md) — foundations for new users
- [Query Optimization](./search-optimize-queries.md) — performance and cost, most commonly needed
- [Partition Design](./admin-partition-design.md) — highest-impact admin decision
- [Field Extraction Rules](./admin-field-extraction-rules.md) — second-highest admin impact
- [Scheduled Views Admin](./search-scheduled-views.md) — Layer 3 acceleration
- [Admin Alerting](./admin-alerting-and-monitoring.md) — operational health foundation
- [Monitors](./alerting-monitors.md) — production alerting setup
- [RBAC and Security](./admin-rbac-security.md) — access control design
- [Data Collection Patterns](./data-collection-patterns.md) — logging standards, processing rules, collection architecture

## MCP Tools for Context Gathering

Use these before advising to understand the user's environment:

- `get_account_status` — Plan type, credits, subscription period
- `get_sumo_partitions` — Current partition design and routing expressions
- `analyze_data_volume` — Top ingest contributors by source category/tier
- `run_search_audit_query` — Most expensive queries by user and scan volume
- `list_scheduled_views` — Existing views (Layer 3 investment)
- `list_field_extraction_rules` — Existing FERs (Layer 3 investment)
- `explore_log_metadata` — What source categories and partitions exist
- `get_usage_forecast` — Projected credit usage

---

**Version:** 1.1.0
**Last Updated:** 2026-03-11
**Domain:** Architecture & Consulting
**Complexity:** Meta-skill (references all other skills)
**Role:** Virtual Technical Account Engineer entry point

**Purpose:** This skill gives Claude a consulting framework for Sumo Logic. It does not replace the individual task skills — it maps questions to the right skills and provides trade-off context that spans multiple domains.
