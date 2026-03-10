# Skill: Admin Alerting and Monitoring in Sumo Logic

## Intent

Configure the administrative alerting foundation for a Sumo Logic organisation: enable required audit policies, understand which admin apps need which indexes, and implement key operational alerts for ingest spikes, collection stops, rate limiting, excessive infrequent scan costs, and unhealthy collection events.

## Prerequisites

- Sumo Logic administrator access
- Audit index, data volume index, and search audit policy enabled (see setup section below)
- For large orgs: consider creating scheduled views to back data volume alerting (see `search-scheduled-views`)

## Context

**Use this skill when:**

- Setting up a new Sumo Logic org for production operations
- Creating proactive alerts for ingest anomalies, rate limiting, or collection failure
- Monitoring infrequent tier scan costs for cost control
- Responding to collection health issues (offline collectors, source errors)
- Investigating data volume spikes or unexpected ingest increases

**Don't use this when:**

- Configuring application-level alerting (use standard Monitors for that)
- Setting up security detection rules (use Cloud SIEM for that)

---

## Step 1: Enable Required Audit Policies

Before creating admin alerts, ensure these three policies are enabled in **Admin → Security → Policies** (or equivalent depending on plan):

| Policy | Index | Purpose | Required For |
|---|---|---|---|
| **Audit Index** | `_index=sumologic_audit` (legacy) / `_index=sumologic_audit_events` (enterprise) | Records user actions, health events, CSE insights, automation events | Admin apps, health alerts, CSE event history |
| **Data Volume Index** | `_index=sumologic_volume` | Maps ingest to GB and credits by metadata dimension and tier | Ingest spike/drop alerts, data volume app |
| **Search Audit** | `_view=sumologic_search_usage_per_query` | Records all search queries with scan stats | Search audit app, infrequent scan cost alerts |

**Recommendation for Enterprise accounts:** Create a dedicated **Sumo Admin** folder in **Admin Recommended** with manage permissions for admins only, and import the official Sumo Logic admin apps from the Library.

---

## Step 2: Install Admin Apps

Sumo Logic provides pre-built admin apps. The apps required depend on which indexes are enabled:

| App | Index Required | Purpose |
|---|---|---|
| **Audit App** | Legacy audit index (all plans) | User activity, login auditing |
| **Data Volume App v2** | Data volume index | Volume by tier (recommended over v1 which lacks tier breakdown) |
| **Enterprise Audit Apps** | Enterprise audit index | Enterprise plan only — content changes, user management, collectors |
| **Search Audit App** | Search audit view | Query performance and cost analysis |
| **Infrequent App** | Search audit view | Infrequent tier scan cost dashboards |
| **Cloud SIEM apps** | Enterprise audit + event indexes | CSE insights, signals, rules (reflected as `sec_record`, `sec_signal`) |

**Tip:** For **Data Volume**, always use **v2** over v1. v2 includes data tier breakdowns, making it useful for both tiered and Flex accounts.

---

## Alert 1: Ingest Spike or Drop by Source Category

Detects anomalies in data volume by source category, using time compare to detect weekly-cyclic patterns.

**When to use:** Hourly or daily scheduled search, triggering email or webhook when ingest changes significantly.
**For large orgs:** Run against a scheduled view instead of raw data volume for better performance (see `search-scheduled-views`).

```
/*
 Ingest spike/drop alert by source category and data tier.
 Schedule: hourly (-1h) or daily (-24h)
 Trigger: rows > 0
 Tune the WHERE clause thresholds for your environment.
*/
_index=sumologic_volume _sourceCategory=sourcecategory_and_tier_volume
| parse regex "(?<data>\{[^\{]+\})" multi
| json field=data "field","dataTier","sizeInBytes" as sourceCategory, dataTier, bytes
| bytes/1Gi as gbytes
| sum(gbytes) as gbytes by dataTier, sourceCategory

// Standard credit rates — verify against your contract:
| 20 as credit_rate
| if(dataTier = "CSE",      25,   credit_rate) as credit_rate
| if(dataTier = "Infrequent", 0.4, credit_rate) as credit_rate
| if(dataTier = "Frequent",   9,   credit_rate) as credit_rate
| gbytes * credit_rate as credits

// Compare with average of same time over last 3 weeks:
| compare timeshift 7d 3 avg

// Handle new or removed categories:
| if(isNull(gbytes), "GONE", "") as state
| if(isNull(gbytes), 0, gbytes) as gbytes
| if(isNull(gbytes_21d_avg), "NEW", state) as state
| if(isNull(gbytes_21d_avg), 0, gbytes_21d_avg) as gbytes_21d_avg

// Compute percentage change vs baseline:
| ((gbytes - gbytes_21d_avg) / gbytes) * 100 as pct_increase

// Alert condition — tune thresholds for your environment:
| where (pct_increase > 50 or state = "NEW") and (credits > 20 or gbytes > 1)
```

**Notes:**
- For tracking **credits** (better for tiered accounts): use as shown above
- For tracking **GB** (simpler): remove credit calculation and use `| where pct_increase > 50 and gbytes > 1`
- The `state` field flags `NEW` (no historical baseline) and `GONE` (was sending, now stopped) categories
- For auto-scaled or ephemeral infrastructure, tune min-size clause to avoid noise from short-lived sources

---

## Alert 2: Stopped or Low Collection

Detects source categories or collectors that have significantly reduced or stopped sending data.

```
/*
 Collection stop alert — detects sources with reduced or stopped ingestion.
 Schedule: hourly (-1h) or daily (-24h)
 Trigger: rows > 0
 Change _sourcecategory to _collector for collector-level alerting.
*/
// Use sourcecategory dimension (change to collector_and_tier_volume for collector):
_index=sumologic_volume _sourceCategory=collector_and_tier_volume

| parse regex "(?<data>\{[^\{]+\})" multi
| json field=data "field","dataTier","sizeInBytes" as fieldvalue, dataTier, bytes
| bytes/1Gi as gbytes
| parse field=_sourceCategory "*_*" as type, junk
| sum(gbytes) as gbytes by dataTier, fieldvalue, type

// Optional: filter to known infrastructure list
// | where fieldvalue matches /prod-collector-.*/

| 20 as credit_rate
| if(dataTier = "CSE",      25,   credit_rate) as credit_rate
| if(dataTier = "Infrequent", 0.4, credit_rate) as credit_rate
| if(dataTier = "Frequent",   9,   credit_rate) as credit_rate
| gbytes * credit_rate as credits

| compare timeshift 7d 3 avg

| if(isNull(gbytes), "GONE", "COLLECTING") as state
| if(isNull(gbytes), 0, gbytes) as gbytes
| if(isNull(gbytes_21d_avg), "NEW", state) as state
| if(isNull(gbytes_21d_avg), 0, gbytes_21d_avg) as gbytes_21d_avg
| ((gbytes - gbytes_21d_avg) / gbytes) * 100 as pct_increase

// Alert on stopped (GONE) or significantly reduced ingestion:
| where (pct_increase < -50 or state = "GONE")
```

**Notes:**
- Switch `_sourceCategory=collector_and_tier_volume` for collector-level instead of source-category-level
- `state = "GONE"` catches complete stops; `pct_increase < -50` catches significant drops
- For ephemeral/auto-scaled collectors, avoid alerting on `GONE` unless the collector is persistent infrastructure

---

## Alert 3: Rate Limiting (Throttling)

Alerts when your account is being rate-limited (throttled) due to exceeding the sustained ingest rate. Rate limiting can result in lost data.

**Alert type:** Scheduled Search (or Monitor)

```
// Simple keyword search for rate limit events in the audit index:
_index=sumologic_audit _sourceCategory=account_management
_sourceName=VOLUME_QUOTA "rate limit"
```

**How rate limits work:**
- Each org has a soft limit = sum of contracted ingest (Continuous + Frequent + Infrequent GB) × a multiplier
- Example: 100 GB Continuous + 1 GB Frequent + 200 GB Infrequent = 301 GB base → 301 × 8 = ~2.4 TB peak rate
- Sustained ingest above this rate triggers throttling, which can cause data loss
- Request a higher rate limit from Customer Success for known high-ingest events (Black Friday, product launches)

**Important caveat:** Legacy ingest budgets or exclude filters on hosted sources count toward throttle volume but **do not appear in data volume** — making throttle issues hard to diagnose without this alert.

---

## Alert 4: High Infrequent Scan Credits

Alerts when users are generating excessive scan costs on the Infrequent tier.

**Requirement:** Search Audit policy must be enabled.

```
/*
 High infrequent scan cost alert — daily or hourly.
 Schedule: daily for -24h or hourly for -1h.
 Trigger: rows > 0.
 Tune cr_max_user and cr_max_org thresholds for your environment.
*/
_view=sumologic_search_usage_per_query
analytics_tier=*infrequent*
| json field=scanned_bytes_breakdown "Infrequent" as scan_inf
| ((query_end_time - query_start_time) / 1000 / 60) as range_minutes
| count as queries,
  sum(retrieved_message_count) as retrieved_events,
  avg(range_minutes) as range_minutes,
  avg(scanned_partition_count) as partitions,
  sum(scan_inf) as scan_inf
  by user_name, query

// Typical Infrequent credit rate — verify against your contract:
| (scan_inf / 1024 / 1024 / 1024) * 0.016 as credits
| fields -scan_inf
| credits / queries as cr_per_query
| total credits as credits_total_user by user_name
| total credits as total_credits

| sort cr_per_query

// Tune these thresholds:
| 100 as cr_max_user   // max credits per user
| 500 as cr_max_org    // max credits for entire org
| where credits_total_user > cr_max_user or total_credits > cr_max_org
```

**Notes:**
- Use results to identify users with high scan, then investigate their queries for optimisation opportunities (missing `_index=`, excessive time ranges, no keywords)
- Reach out to high-scan users with targeted training on Infrequent tier best practices
- Adjust `cr_max_user` and `cr_max_org` based on your credit budget and organisation size

---

## Alert 5: Unhealthy Collection Events

Alerts on collection health status changes for installed collectors, cloud sources, and budget events.

**Alert type:** Monitor with alert grouping (one alert per `resource_name`) or Scheduled Search.

```
/*
 Unhealthy collection event monitor/alert.
 Use alert grouping on resource_name for one alert per resource.
 Reference all health event types:
 https://service.<region>.sumologic.com/audit/docs/#tag/Health-Events-(System)
*/
_index=sumologic_system_events "Health-Change" unhealthy
| json field=_raw "status"
| json "eventType", "resourceIdentity.id" as eventType, resourceId
| json field=_raw "details.error" as error
| json field=_raw "details.trackerId" as trackerid
| json field=_raw "resourceIdentity.name" as resource_name
| max(_messagetime) as _messagetime, count
  by trackerid, error, resource_name, eventtype

// Include/exclude specific resources:
// | where resource_name matches /(?i)prod-.*/          // include pattern
// | where !(resource_name matches /(?i)exclude-.*)      // exclude pattern

// For auto-scaled environments, exclude noisy common offline events:
// | where ! (error IN (
//     "Installed collector and its sources are offline",
//     "File Collection Error",
//     "Failed to connect to the event channel"
// ))
```

**What unhealthy events detect:**

| Issue | Health Event |
|---|---|
| Installed collector offline | `Health-Change` with collector status |
| Local file source not found or permission error | Source health change |
| Cloud-to-Cloud source HTTP 500 failures | C2C source health change |
| Ingest budget exceeded | `Health-Change` on `IngestBudget` resource type |
| Hosted source access errors | Source health change |

**Detecting budget exceeded specifically:**

```
_index=sumologic_system_events "IngestBudget"
| json "eventType", "severityLevel", "resourceIdentity.type" as eventType, severity, resourceType
| where eventType = "Health-Change" AND resourceType = "IngestBudget" AND severity = "Error"
```

**Important:** For ephemeral or auto-scaled infrastructure (K8s pods, spot instances), collector offline events are normal and expected — filter these out using regex excludes on `resource_name` or `error` to avoid alert noise.

---

## Data Volume Views for Large Organisations

For organisations with very high source category cardinality (3,000+ source categories per day) or very long time ranges, raw data volume queries using `parse regex multi` will hit scale limits or become very slow.

**Solution:** Create a Scheduled View that pre-computes data volume into a structured format.

```
/*
 Scheduled View definition for data volume — run as 1m timeslice view.
 View name: dv_by_sourcecategory_v1
 Replace sourcecategory_and_tier_volume with other dimensions as needed.
*/
_index=sumologic_volume _sourceCategory=sourcecategory_and_tier_volume
| parse regex "(?<element>\{[^\}]+})" multi
| json field=element "field", "dataTier", "sizeInBytes", "count" as name, uom, bytes, events
| timeslice 1m
| bytes/1Gi as units
| if(uom = "CSE",      25,   20) as rate
| if(uom = "Infrequent", 0.4, rate) as rate
| if(uom = "Frequent",   9,   rate) as rate
| "gbytes" as unit
| units * rate as credits
| sum(credits) as credits, sum(units) as units
  by _timeslice, uom, unit, rate
| todouble(rate) as rate | todouble(credits) as credits
| tolong(_timeslice) as _timeslice | todouble(units) as units
```

Queries and alerts run against `_view=dv_by_sourcecategory_v1` will execute **10x–100x faster** and scale to weeks or months of data volume analysis.

---

## MCP Tools Used

- `search_legacy_audit` — Query the legacy audit index for user activity and health events
- `search_audit_events` — Query the enterprise audit events index
- `search_system_events` — Query system events including collection health and monitor alerts
- `analyze_data_volume` — Analyse ingest volume by dimension (uses data volume index)
- `analyze_search_scan_cost` — Identify high scan users (uses search audit view)
- `run_search_audit_query` — Run custom search audit queries

## Admin Setup Checklist — Content Management Governance

Once core alerting is in place, establish these governance practices to keep the Sumo Logic organisation well-managed as it scales:

**Naming Conventions (agree these before users create content at scale):**
- **Monitor folders**: use a consistent folder/naming convention (e.g., `[TeamName] - [Description]`, `[Severity] - [Service] - [CheckType]`)
- **Scheduled views**: use versioned names (`viewname_v1`, `viewname_v2`) for safe updates; include a date or version suffix
- **Dashboards**: include team/service and purpose in the name
- **Source categories**: enforce the agreed `env/technology/role` taxonomy via governance documentation and user training

**Admin Recommended Folder:**
- Create a **Sumo Admin** folder in Admin Recommended with **manage** permissions for admins only
- Import the following admin apps from the Library into this folder: Data Volume App v2, Audit App, Search Audit App, Infrequent App
- Use Admin Recommended for any shared searches, dashboards, or scheduled searches that all users should access

**Ongoing Administrative Processes:**
- Schedule a regular review for users accessing Infrequent tier incorrectly (high scan cost from running dashboards or frequent scheduled searches against Infrequent tier data)
- Establish a process for new user onboarding training (not just access provisioning)
- Establish a process for source category and partition name governance — new sources should follow the agreed taxonomy before going live
- Email yourself the **Weekly Usage Report** from Admin settings to track credit consumption trends

**Support Account and Operations:**
- Enable a support account user for Sumo Logic Support team access (minimum 1 year; infinite recommended for production orgs)
- Register at **status.sumologic.com** for platform status notifications
- Subscribe to the Sumo Logic **RSS feed** for release notes to stay current on new features

## Related Skills

- [Scheduled Views for Acceleration](./search-scheduled-views.md)
- [Partition Design](./admin-partition-design.md)
- [Alerting — Monitors](./alerting-monitors.md)
- [Alerting — Time Compare and Anomaly](./alerting-time-compare-anomaly.md)

## API References

- [Audit Index](https://help.sumologic.com/docs/manage/security/audit-indexes/audit-index/)
- [Audit Event Index](https://help.sumologic.com/docs/manage/security/audit-indexes/audit-event-index/)
- [System Event Index](https://help.sumologic.com/docs/manage/security/audit-indexes/system-event-index/)
- [Search Audit Index](https://help.sumologic.com/docs/manage/security/audit-indexes/search-audit-index/)
- [Data Volume Index](https://help.sumologic.com/docs/manage/ingestion-volume/data-volume-index/)
- [Health Events Reference](https://service.sumologic.com/audit/docs/#tag/Health-Events-(System))

---

**Version:** 1.1.0
**Last Updated:** 2026-03-11
**Source:** Admin Indexes, Apps and Alerts Playbook (Sumo Logic Customer Success); CIP Onboarding Sessions I & II
