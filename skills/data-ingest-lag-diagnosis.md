# Skill: Diagnose Ingest Lag and Timestamp Parsing Issues

## Intent

Identify and triage sources where logs are arriving late, carrying incorrect timestamps, or where Sumo Logic is misinterpreting the timestamp format. Uses the offset between `_receipttime` (when data arrived at Sumo) and `_messagetime` (the parsed event timestamp) as the primary signal.

## Prerequisites

- Access to the Sumo Logic org via MCP tools
- The scope of sources to investigate (source category, collector, or keyword)
- Optionally: knowledge of which data tiers/partitions are in scope

## Context

**Use this skill when:**
- Searches are returning no results in an expected time range (data is there but timestamped wrong)
- Dashboards or monitors are intermittently firing late or missing data
- A source is reported as "not sending data" but the collector appears healthy
- You suspect a timezone mismatch (event times look shifted by hours)
- AWS S3-based sources (CloudTrail, CloudWatch, S3 Access Logs) show delays
- You want a baseline health check on ingest lag across a scope

**Don't use this when:**
- The data source is genuinely not sending logs (collector offline, source disabled)
- You only need to check ingest volume, not timing — use `analyze_log_volume` instead

---

## Core Concept: _receipttime vs _messagetime

| Field | Meaning | Type |
|-------|---------|------|
| `_receipttime` | When Sumo Logic received/indexed the log | epoch ms (long) |
| `_messagetime` | The timestamp parsed from the log content | epoch ms (long) |

`lag_minutes = (_receipttime - _messagetime) / 60000`

| lag_minutes | Health status |
|-------------|---------------|
| < 0 | **Bad** — timestamp set in the future; timezone misconfiguration |
| 0–5 | Healthy |
| 5–15 | Sub-optimal; acceptable for many use cases |
| 15–60 | Problematic; investigate source/pipeline |
| > 60 | High lag; likely configuration issue |
| Hours/Days | Severe; AWS S3 missing SNS notifications is common cause |

**Why search by receipt time?** When byReceiptTime=true, the query window is based on when data arrived at Sumo, not the event timestamps. This is essential — if a source has severely wrong timestamps (e.g., year 2099), a normal message-time search would miss the data entirely.

---

## Approach

### Phase 1: Summary Scan — identify which sources have lag

#### Step 1.1: Run lag summary

Start with `summary` mode to find sources exceeding the lag threshold, sorted by worst lag first.

**MCP Tool:** `analyze_ingest_lag`
```json
{
  "scope": "_sourceCategory=aws/*",
  "from_time": "-6h",
  "to_time": "now",
  "lag_threshold_minutes": 15,
  "query_mode": "summary",
  "top_n": 50
}
```

**Result fields:** `_sourceCategory`, `_collector`, `_source`, `avg_lag_minutes`, `max_lag_minutes`, `events`

**What to look for:**
- Sources with `max_lag_minutes > 60` (high lag — investigate)
- Sources with `avg_lag_minutes < 0` (negative lag — timezone issue)
- Large `max` vs small `avg` (intermittent lag vs systemic lag)

---

### Phase 2: Distribution — understand whether lag is universal or partial

#### Step 2.1: Run distribution analysis on problem sources

For sources flagged in Phase 1, run `distribution` mode to see whether lag affects all events or only a subset. Partial lag suggests intermittent pipeline issues or mixed timestamp formats.

**MCP Tool:** `analyze_ingest_lag`
```json
{
  "scope": "_sourceCategory=aws/cloudtrail*",
  "from_time": "-6h",
  "to_time": "now",
  "lag_threshold_minutes": 15,
  "query_mode": "distribution"
}
```

**Result fields:** `_sourceCategory`, `min_lag_minutes`, `pct25/50/75_lag_minutes`, `max_lag_minutes`

**Interpretation:**
- If `min > 0` and `max > threshold` → all events are lagging (systemic — check pipeline/source config)
- If `min < 0` → some future-dated events (timezone problem)
- If `pct75` is low but `max` is very high → a small number of severely lagged events (possibly re-ingested or backfilled data)

---

### Phase 3: Check ingest volume pattern over time

For AWS S3 or polling-based sources with high lag, check whether ingest arrives in intermittent bursts (telltale sign of polling-only with no SNS notifications).

**MCP Tool:** `analyze_data_volume_grouped`
```json
{
  "source": "sourcecategory_and_tier_volume",
  "filter_value": "aws/cloudtrail*",
  "from_time": "-7d",
  "to_time": "now",
  "granularity": "1h"
}
```

**What to look for:**
- Continuous smooth ingest → healthy pipeline
- Large spikes every few hours with gaps → polling-only; configure SNS event notifications
- Complete gaps for days then a burst → manual or scheduled re-ingest

---

### Phase 4: Inspect source configuration

Retrieve the collector and source configuration to check timestamp and timezone settings. Note: if timezone is not set on the source, it inherits from the parent collector.

#### Step 4.1: Get collectors

**MCP Tool:** `get_sumo_collectors`
```json
{
  "search": "aws-collector",
  "limit": 10
}
```

#### Step 4.2: Get sources for the collector

**MCP Tool:** `get_sumo_sources`
```json
{
  "collector_id": "<collector_id_from_step_4.1>"
}
```

**What to examine in source config:**
- `timeZone` — if null/absent on source, check the collector-level `timeZone`
- `automaticDateParsing` — if false, receipt time is used as _messagetime (t:none in _format)
- `defaultDateFormats` — custom timestamp format(s) configured
- `forceTimeZone` — if true, the source timezone overrides any timezone in the log

---

### Phase 5: Debug timestamp format parsing

When you suspect Sumo Logic is misidentifying the timestamp (e.g., picking a different date field in the log, or using the wrong format), use `format_debug` mode to see the `_format` field for sampled events.

**MCP Tool:** `analyze_ingest_lag`
```json
{
  "scope": "_sourceCategory=app/nginx",
  "from_time": "-1h",
  "to_time": "now",
  "query_mode": "format_debug",
  "top_n": 20
}
```

**_format field structure:** `t:<parse_type>,o:<offset>,l:<length>,p:<date_format>`

| parse_type | Meaning |
|------------|---------|
| `full` | Timestamp found using pattern library — healthy |
| `cache` | Cached format reused from prior message — healthy |
| `def` | User-defined default format matched |
| `none` | Timestamp parsing disabled; receipt time used |
| `fail` | No timestamp found in log; receipt time assigned |
| `ac1` | Auto-corrected — timestamp was >1 day from recent messages |
| `ac2` | Auto-corrected — timestamp was outside -1yr/+2day window |

**Diagnosis by parse_type:**
- `t:fail` → No timestamp found. Specify a custom timestamp format on the Source.
- `t:none` → Automatic date parsing is disabled. Enable it or set a custom format.
- `t:ac1` or `t:ac2` → Timestamp was out of range. Often indicates timezone offset causing drift (e.g., reading PST timestamp as UTC gives +8h offset). Check source/collector timezone.
- `t:full` with large lag → Sumo found A timestamp, but may be picking the wrong one from the log. Compare `o` (offset) and `l` (length) against the raw log to identify which field it matched.

---

## Query Patterns

### Basic Lag Summary
```
<scope>
| (_receipttime - _messagetime) / 60000 as lag_minutes
| where abs(lag_minutes) > 15
| avg(lag_minutes) as avg_lag_minutes, max(lag_minutes) as max_lag_minutes, count as events by _sourcecategory, _collector, _source
| sort max_lag_minutes desc
```

### Lag Distribution (percentile breakdown)
```
<scope>
| (_receipttime - _messagetime) / 60000 as lag_minutes
| min(lag_minutes), max(lag_minutes), pct(lag_minutes, 25, 50, 75) by _sourcecategory
| where _max > 15 or _min < 0
```

### Timestamp Format Debug
```
<scope>
| (_receipttime - _messagetime) / 60000 as lag_minutes
| _format as timestampFormat
| limit 20
| fields _messagetime, _receipttime, lag_minutes, _sourcecategory, timestampFormat, _raw
```

---

## Examples

### Example 1: AWS CloudTrail showing hours of lag

**Symptom:** CloudTrail dashboards are empty for the last 2 hours but the collector appears healthy.

**Step 1** — Run summary scan:
```json
analyze_ingest_lag: scope="_sourceCategory=aws/cloudtrail*", from_time="-24h", query_mode="summary"
```
Result shows `max_lag_minutes: 480` (8 hours).

**Step 2** — Check ingest volume pattern:
```json
analyze_data_volume_grouped: source="sourcecategory_and_tier_volume", filter_value="aws/cloudtrail*", from_time="-7d", granularity="1h"
```
Result shows large spikes every ~6 hours with gaps → polling-only pattern confirmed.

**Fix:** Configure SNS event notifications on the S3 source in the Sumo Logic UI.
See: https://www.sumologic.com/help/docs/send-data/hosted-collectors/amazon-aws/aws-s3-source/#s3-event-notifications-integration

---

### Example 2: Windows Event Logs with negative lag (timezone issue)

**Symptom:** Windows server logs show events timestamped 5 hours in the future.

**Step 1** — Run distribution scan:
```json
analyze_ingest_lag: scope="_sourceCategory=windows/*", query_mode="distribution"
```
Result shows `min_lag_minutes: -300` (−5 hours) for all percentiles.

**Step 2** — Get source config:
```json
get_sumo_collectors: search="windows-collector"
get_sumo_sources: collector_id="<id>"
```
Source has `timeZone: null` → inherits from collector. Collector `timeZone: "UTC"` but Windows logs carry `America/New_York` timestamps.

**Fix:** Set `timeZone: "America/New_York"` on the source (or collector if all sources are affected).

---

### Example 3: Application logs — auto-parsing picking wrong timestamp

**Symptom:** App logs are getting timestamped with the exception line's embedded date rather than the log prefix timestamp.

**Step 1** — Run format_debug:
```json
analyze_ingest_lag: scope="_sourceCategory=app/java-api", query_mode="format_debug", top_n=20
```
Some rows show `_format: t:full,o:247,l:19,p:yyyy-MM-dd HH:mm:ss` — offset 247 is deep inside the log line (the exception trace), not the standard prefix timestamp at offset 0.

**Fix:** Specify a custom timestamp format and locator regex in Source Advanced Options to anchor to the correct position.

---

## Common Pitfalls

### Pitfall 1: Searching by message time when timestamps are wrong
- **Problem:** Using a normal search job (byReceiptTime=false) when events have future timestamps — the query window misses the data entirely.
- **Solution:** Always use `analyze_ingest_lag` which forces byReceiptTime=true, or use `create_sumo_search_job` with `by_receipt_time: true`.

### Pitfall 2: Assuming all sources in a category have the same lag
- **Problem:** A source category like `aws/*` may contain dozens of sources with very different lag profiles.
- **Solution:** Use `summary` mode first to identify the specific `_source` and `_collector` that are problematic, then drill down.

### Pitfall 3: Confusing negative lag with clock drift
- **Problem:** A few events with slightly negative lag (−1 to −2 minutes) may just be clock skew on the sending host.
- **Solution:** Negative lag of more than a few minutes (or consistent negative lag across many events) is the real signal. Single-digit negative values on isolated events can usually be ignored.

### Pitfall 4: Ignoring timezone inheritance
- **Problem:** The source has no timezone set and appears correct in isolation, but inherits a wrong timezone from the collector.
- **Solution:** Always check both source AND collector timezone config via `get_sumo_collectors` and `get_sumo_sources`.

---

## Optimization Tips

### Tip 1: Start with a wide time window
Use `-24h` or `-48h` for the initial scan. Severe lag (hours or days) won't show up in a `-1h` window since those events may not have arrived yet in the receipt-time window.

### Tip 2: Use distribution mode before making config changes
Distribution mode tells you whether all events are affected or just a subset. If only 5% of events have high lag (outliers at pct99), a configuration change may not help — it could be pipeline backpressure on the sending side.

### Tip 3: Correlate with volume pattern
A spiky, burst-style ingest pattern (from `analyze_data_volume_grouped` over `-7d`) combined with high lag is the strongest indicator of an AWS S3 source missing SNS notifications — this is the most common severe-lag pattern.

### Tip 4: Check _format parse_type field values
The `p:<date_format>` component of _format shows exactly which format pattern matched. Cross-reference the offset `o` and length `l` values against a sample raw log to verify the correct field is being parsed.

---

## Related Skills

- [data-collection-patterns.md](data-collection-patterns.md) — Collector and source architecture overview
- [admin-field-extraction-rules.md](admin-field-extraction-rules.md) — Configuring parse-at-ingest rules
- [audit-system-health.md](audit-system-health.md) — Monitoring collector health and ingest anomalies
- [discovery-logs-without-metadata.md](discovery-logs-without-metadata.md) — Finding logs when scope is unknown

## MCP Tools Used

- `analyze_ingest_lag` — Primary tool for all lag detection modes (summary, distribution, format_debug)
- `analyze_data_volume_grouped` — Check ingest volume pattern over time (spiky vs continuous)
- `get_sumo_collectors` — Retrieve collector configuration including timezone
- `get_sumo_sources` — Retrieve source configuration including timestamp and timezone settings
- `search_sumo_logs` — Ad-hoc raw log sampling when manual inspection is needed
- `create_sumo_search_job` — Custom lag queries with byReceiptTime=true for advanced analysis

## API References

- Timestamp Reference: https://www.sumologic.com/help/docs/send-data/reference-information/time-reference/
- Custom Timestamp Formats: https://www.sumologic.com/help/docs/send-data/reference-information/time-reference/#specifying-a-custom-timestamp-format
- _format Troubleshooting: https://www.sumologic.com/help/docs/send-data/reference-information/time-reference/#using-_format-for-troubleshooting
- AWS S3 SNS Notifications: https://www.sumologic.com/help/docs/send-data/hosted-collectors/amazon-aws/aws-s3-source/#s3-event-notifications-integration
- Search Job API: https://api.sumologic.com/docs/#tag/searchJobManagement

---

**Version:** 1.0.0
**Domain:** Data Collection / Ingest Health
**Complexity:** Intermediate
**Estimated Time:** 15–45 minutes for complete triage workflow
