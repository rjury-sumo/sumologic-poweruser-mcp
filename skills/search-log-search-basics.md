# Skill: Sumo Logic Log Search Basics

## Intent

Understand and apply Sumo Logic's core log search pipeline — from scoping with metadata and keywords, through search-time field parsing, to filtering and aggregation — to turn raw logs into actionable insights.

## Prerequisites

- Access to a Sumo Logic instance with log data
- Basic understanding of what log data looks like (structured JSON, Apache-style, syslog, etc.)
- Familiarity with the log sources you want to query (source categories, indexes)

## Context

**Use this skill when:**

- Starting a new investigation or troubleshooting session
- Building a search query from scratch
- Teaching someone the fundamentals of Sumo Logic search
- Preparing queries for dashboards or monitors

**Don't use this when:**

- Querying metrics (different language and tools)
- Working with traces (use APM/tracing UI)
- You already have an established query and just need to tune performance (see `search-performance-best-practices`)

## The Log Search Pipeline

Sumo Logic queries are a **pipeline** of stages separated by `|`. Each stage transforms or filters the data flowing through it. There are over 120 search operators.

```
<scope: metadata + keywords>
| parse <fields from raw log>
| where <filter on field values>
| aggregate <count / sum / avg etc.>
| format <sort / limit / fields>
```

### Complete Example

```
_sourceCategory=Labs/Apache/Access "Mozilla"
| parse "GET * HTTP/1.1\" * " as url, status_code
| where status_code matches "5*"
| count by status_code
| sort by _count
| limit 3
```

---

## The Three Phases of Query Performance

Every Sumo Logic query goes through three phases. Understanding which phase is slow determines how to fix it:

| Phase | What It Does | How to Reduce |
|---|---|---|
| **Scan** | Determines which partition(s) to read over the time range | Use `_index=` to target a single partition; good partition design is the foundation |
| **Retrieval** | Uses bloom filter to identify which events to load | Include keywords or index-time (FER) fields in scope — `status_code=5*` instead of `\| where status_code matches "5*"` |
| **Compute** | Executes parse, filter, and aggregation operators on retrieved events | Avoid complex regex, unnecessary parsing, high cardinality; move `where` clauses as early as possible |

**Golden rule: Reducing scan has the most impact. Reducing retrieval is second. Reducing compute is third.**

The "Ladder of Acceleration" — from lowest to highest impact:
1. Add keyword(s) to scope (bloom filter, zero config change)
2. Add `_index=` or `_sourceCategory=` to scope (reduce scan to one partition)
3. Use indexed fields from FERs in scope (5–10x faster than search-time parsing)
4. Back repeated aggregate queries with a scheduled view (50–100x faster)

---

## Stage 1 — Scope (Before the First Pipe)

The scope is everything **before** the first `|`. It is the most important part for performance and cost. It tells Sumo which partitions to scan and which raw log events to retrieve.

### Metadata Fields

Metadata is attached to every log event at ingest time and is stored in the index alongside the data. Using metadata in scope significantly speeds up searches.

| Field | Description |
|---|---|
| `_sourceCategory` | Category assigned to the source at configuration time. Most important for scoping. |
| `_index` / `_view` | Partition (index) where the logs are stored. Same field, two aliases. |
| `_collector` | Name of the collector that received the log. |
| `_source` | Name of the source within a collector. |
| `_sourceHost` | Hostname of the source machine. |
| `_sourceName` | File path or source name (e.g., `/var/log/app.log`). |

**Best practice:** Always include `_sourceCategory` or `_index` in every search scope. This is the single most effective way to reduce scan and improve speed.

```
// Good — scoped to specific category
_sourceCategory=Labs/Apache/Error

// Good — scoped to index and category
_index=prod_logs _sourceCategory=app/service

// Poor — scans everything
error exception
```

### Keywords

Keywords are free-text terms that further filter events retrieved from the index using a bloom filter (very fast pre-filtering). Place 1–2 keywords after your metadata scope to reduce retrieved events before any parsing occurs.

```
_sourceCategory=prod/app "OutOfMemoryError"
_sourceCategory=prod/app (error OR exception)
_sourceCategory=prod/app "access denied"
```

**Keyword syntax rules:**

- Keywords are **not case-sensitive**
- Wildcards: `fatal*`, `*denied*`, `fo?bar`
- Exact phrase: `"access denied"`
- Boolean: `(error OR warn*) AND NOT debug`
- Implicit AND: spaces between terms

---

## Stage 2 — Parse (Extract Fields at Search Time)

Sumo Logic uses **Schema on Read**: you extract fields from the raw log text when you need them, not at ingest time. This is flexible but slower than index-time fields.

### Auto-Parsing (JSON)

JSON-structured logs are **automatically parsed** — all top-level JSON keys become available as fields without any `parse` statement.

```
// JSON log: {"level":"ERROR","message":"timeout","user_id":"abc123"}
// After auto-parse you can reference: level, message, user_id directly
_sourceCategory=prod/app
| where level = "ERROR"
```

### `parse` — Anchor-Based Parsing

Use two anchor strings around the value you want to capture. Simple and fast.

```
| parse "GET * HTTP/1.1\" * " as url, status_code
| parse "Invalid arguments passed in * on line *" as path, line
| parse "User: * Action: *" as username, action
```

### `parse regex` — Regex Extraction

Use for complex patterns or when anchor-based parsing is not possible. Add `nodrop` to avoid filtering out events that don't match.

```
| parse regex field=_raw " \[(?<log_level>[a-z]+)\] " nodrop
| parse regex field=_raw "\[client (?<src_ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})" nodrop
| parse regex field=_raw " \[(?<module>[a-z-_]+):(?<log_level>[a-z]+)\] " nodrop
```

### `json` — Explicit JSON Extraction

More explicit and performant than auto-parsing for production queries. Supports nested paths.

```
| json field=_raw "errorCode" as error_code
| json field=_raw "userIdentity.arn" as user_arn nodrop
| json "log","stream"
```

**`nodrop` keyword:** Prevents a log event from being discarded if the field doesn't exist. Always use `nodrop` for optional or inconsistently present fields.

---

## Stage 3 — Filter (Narrow on Field Values)

Filter after parsing when you need field-level precision. Keywords in the scope phase are preferred for performance; `where` clauses are for post-parse filtering.

```
| where status_code matches "5*"
| where duration_ms > 1000
| where log_level = "ERROR"
| where error_code in ("AccessDenied", "ThrottlingException")
| where !isEmpty(user_id)
```

**Note:** `where` clauses using string comparisons **are case-sensitive**.

---

## Stage 4 — Aggregate (Compute Insights)

Aggregation transforms log events into summarised results for charts and alerts.

### Categorical (No Time Dimension)

```
// Count by field — most common pattern
| count by status_code
| sort _count desc

// Multiple dimensions
| count by error_code, service_name
| sort _count desc

// Top N shorthand
| top 10 error_code by _count
```

### Time Series

```
// Simple time series
| timeslice 5m
| count by _timeslice

// Multi-series (requires transpose for charting)
| timeslice 5m
| count by _timeslice, log_level
| transpose row _timeslice column log_level
```

### Statistical

```
| avg(duration_ms) as avg_ms, max(duration_ms) as max_ms, pct(duration_ms, 95) as p95_ms by service
```

**Multiple percentiles in one call:** Pass comma-separated percentile values to `pct()` to get all distribution quantiles in a single aggregation. Sumo creates output columns `pct_25`, `pct_50`, `pct_75`, etc. automatically:

```
// Full distribution for latency analysis — output: pct_10, pct_50, pct_95, pct_99
| pct(duration_ms, 10, 50, 95, 99) by service
```

**`count_distinct`** — count unique values of a field. Important: this is an approximation for large cardinalities.

```
| count_distinct(user_id) as unique_users by service
```

**Geographic average workaround for live dashboards:** Live dashboards apply a 1000-group output limit. When querying geo-location data, avoid aggregating directly by latitude/longitude (too many unique combinations). Instead, aggregate by a coarser dimension (country, city) and use `avg(latitude), avg(longitude)` to get centroid coordinates for map placement:

```
// Works within 1000-group limit for map panels
_sourceCategory=web/access
| parse "* * * * \"*\" * *" as src_ip, ident, user, time, request, status, bytes
| geoip src_ip
| where !isEmpty(country_name)
| avg(latitude) as latitude, avg(longitude) as longitude, count by country_code, country_name
```

This approach aggregates by country (bounded cardinality) and places a single map marker per country at the geographic centroid.

---

## Stage 5 — Format (Shape the Output)

```
| sort _count desc
| limit 25
| fields error_code, error_message, _count
| fields - unwanted_column
```

---

## Reading the UI

After running a search you will see:

- **Histogram** — distribution of events across the time range
- **Messages tab** — raw log events matching your scope
- **Field Browser** — discovered fields available for filtering and aggregation
- **Log Message Inspector** — click any message to see all its fields and their values; the `_view` field shown here is the partition/index

You can click any field value in the Field Browser or inspector to add it directly to your query scope.

---

## Common Patterns

### Apache / Web Access Logs

```
_sourceCategory=Labs/Apache/Access
| parse "* * * * \"* * *\" * *" as src_ip, ident, user, time, method, url, protocol, status, bytes
| where status >= 400
| count by status
| sort _count desc
```

### JSON App Logs — Error Count by Level

```
_sourceCategory=prod/app
| json "level" as log_level
| count by log_level
| sort _count desc
```

### Time Series Error Rate

```
_sourceCategory=Labs/Apache/Error
| parse regex field=_raw " \[(?<log_level>[a-z]+)\] " nodrop
| where log_level = "crit"
| timeslice
| count by _timeslice
```

---

## Ingest Lag Detection

Use this query to detect timestamp/timezone issues causing stale data in search:

```
_sourcecategory=prod/*
| _format as tz_format
| _receipttime - _messagetime as lag_ms
| lag_ms / (1000 * 60) as lag_m
| values(tz_format) as tz_formats, min(lag_m) as min_lag, avg(lag_m) as avg_lag, max(lag_m) as max_lag by _collector, _source, _sourcecategory
| sort avg_lag
| if(avg_lag < 0, "ERROR - future timestamp!", "OK") as status
| if(avg_lag > 5, "WARN - high lag source", status) as status
| if(avg_lag > 60, "ERROR - Very high lag time on source ingestion", status) as status
```

Adjust `_sourcecategory` scope to the sources you want to audit.

---

## Advanced Operators Reference

Sumo Logic has over **120 search operators**. Beyond the pipeline basics, these are frequently valuable:

- **`compare with timeshift`** — compare current values against prior periods (daily/weekly baselines)
- **`LogReduce`** — ML clustering to group similar log messages and surface unknown patterns. Works on the whole message by default or on a specific field: `| logreduce field=error_message`. Best on moderate-volume, structured-ish logs. For repeated use, `logreduce optimize` caches signatures for faster reuse.
- **`LogCompare`** — like LogReduce but compares two time windows (e.g., before and after a deploy) to show what changed in log patterns
- **`transaction`** / **`transactionize`** — correlate events into multi-event transactions by a key (e.g., user session, request ID). Has memory and event limits; for high-cardinality use, prefer the aggregation pattern (see `search-subquery`)
- **`subquery`** — use results of one (child) query to filter or enrich another (parent) query. See the dedicated `search-subquery` skill for full patterns including `compose`, sneaky save, and cat-based filtering
- **`predict`** — time series forecasting to project future values. Two models available: `model=ar` (auto-regression, good for repeating/seasonal patterns) and `model=linear` (simple linear trend). Example: `| predict _count by 1m model=ar, ar.window=5, forecast=100` forecasts 100 data points ahead using the last 5-point AR window. Requires a prior `timeslice` + aggregate.
- **`smooth`** — moving average to reduce noise in time series charts. **Critical:** always `| sort _timeslice asc` BEFORE applying smooth, otherwise the moving average is computed on unsorted data and gives wrong results. Example: `| timeslice 5m | count by _timeslice | sort _timeslice asc | smooth _count, 5 as trend` — the `5` is the window size in data points.
- **`outlier`** — statistical anomaly detection (standard deviation based). Configurable parameters: `window` (rolling window size), `threshold` (standard deviations), `consecutive` (how many consecutive out-of-band points to trigger), `direction` (`+` positive only, `-` negative only, `+-` both). Example: `| outlier error_count window=10, threshold=3, consecutive=3, direction=+-`. Legacy — prefer Anomaly monitors for ongoing alerting.
- **`threatip`** / **`geoip`** — threat intelligence and geolocation enrichment (best cached in a scheduled view for performance since these are expensive operations)
- **`lookup`** — enrich events with data from a lookup table
- **`cat`** — read a lookup table as if it were a query result set; enables timeless dashboard queries from state tables

### Field Cardinality Reduction

When a field has very high cardinality (e.g., long ARN strings, full request paths with IDs), you can normalize it into a lower-cardinality version before aggregating. This makes charts readable and improves performance. Consider moving these transformations to a Field Extraction Rule (FER) if the pattern is queried frequently.

```
// Truncate long error strings to first 50 chars
| if(length(error) > 50, concat(substring(error, 0, 50), "*"), error) as shorterr
| count by shorterr

// Extract first two URL segments (removes high-cardinality trailing IDs)
// /myapi/api1/a/b/c/d/18923491982409231 → /myapi/api1
| parse regex field=url "^(?<endpoint>\/[^\/]+\/[^\/]+)" nodrop
| if(isempty(endpoint), substring(url, 0, 30), endpoint) as endpoint

// Replace GUIDs/instance IDs with placeholder
// /my/web/url/!9876fea1a3/inventory → /my/web/url/<code>/inventory
| replace(url, /\/![a-zA-Z0-9\!\-]{4,}/, "/<code>") as path

// Extract account and role from AWS ARN
// arn:aws:sts::224012340808:assumed-role/myapp-external-dns/175430395977 → accountid + role
| parse regex field=arn "^arn:aws:[a-z]+::(?<accountid>[0-9]+):assumed-role\/(?<role>[^\/]+)" nodrop
```

**Tip:** If a cardinality-reduction transformation is applied repeatedly in production queries, define it as a FER so the lower-cardinality field is indexed and available without re-computing at search time.

---

## Related Skills

- [Search Performance Best Practices](./search-performance-best-practices.md)
- [Indexes and Partitions](./search-indexes-partitions.md)
- [AI Copilot](./search-copilot.md)

## API References

- [Log Operators Cheat Sheet](https://help.sumologic.com/docs/search/search-cheat-sheets/log-operators/)
- [Parse Operators](https://help.sumologic.com/docs/search/search-query-language/parse-operators/)
- [Getting Started with Search](https://help.sumologic.com/docs/search/get-started-with-search/)

---

**Version:** 1.3.0
**Last Updated:** 2026-03-12
**Source:** SumoLogic Logs Basics Training (August 2025); CIP Onboarding Sessions I & II; Sumo Logic Advanced Topics Workshop (2025/2026); Sumo Logic Dashboard Cookbooks (2026)
