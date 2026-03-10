# Skill: Sumo Logic Dashboard Panel Types and Query Patterns

## Intent

Write the correct query structure for each Sumo Logic dashboard panel type — categorical, time series, single value, honeycomb, map, and text — and apply time compare patterns for trend context.

## Prerequisites

- Ability to write Sumo Logic aggregate queries (see `search-log-search-basics`)
- Access to a Sumo Logic dashboard in edit mode

## Context

**Use this skill when:**

- Adding panels to a new or existing dashboard
- Choosing between chart types for a given data shape
- Debugging why a panel shows no data or an unexpected shape
- Building time series panels with historical comparison

**Don't use this when:**

- Building a raw log search without aggregation (panels require aggregation)

---

## Panel Type Reference

### Categorical Panels

Categorical panels (pie charts, bar charts, tables) display aggregated data **without a time dimension**. The query must aggregate and produce a finite set of rows.

**Required query shape:** aggregate with no `timeslice`; result is a flat table.

```
// Basic count by field:
_sourceCategory=Labs/Apache/Access
| parse "GET * HTTP/1.1\" * " as url, status_code
| where status_code matches "5*"
| count by status_code
| sort _count desc

// Count by two dimensions (for table panel):
_sourceCategory=aws/cloudtrail
| json "errorCode" as error_code
| json "eventSource" as event_source
| count by error_code, event_source
| sort _count desc
```

**Chart types available:**
- **Table** — most flexible; shows all dimensions; always a good default
- **Bar chart** — best for comparing categories of different sizes
- **Pie/Donut chart** — best for proportional breakdown of a small number of categories (≤7)
- **Treemap** — hierarchical proportional view

**Tips:**
- Use Table format when you have many categories — it's easier to read than a pie chart with 20 slices
- Add `| top 10 field by _count` to limit to the most significant categories

---

### Time Series Panels

Time series panels (line, area, column charts) display data **over time**. The query must include `timeslice` to produce a `_timeslice` dimension.

**Required query shape:** `timeslice` + aggregate `by _timeslice`

#### Single-Series Time Series

```
_sourceCategory=Labs/Apache/Access
| timeslice by 15m
| count by _timeslice
```

#### Multi-Series (Multiple Lines) — Requires `transpose`

To get multiple series on a single time chart (one line per field value), use `transpose`:

```
_sourceCategory=Labs/Apache/Error
| parse regex field=_raw " \[(?<log_level>[a-z]+)\] " nodrop
| timeslice
| count by _timeslice, log_level
| transpose row _timeslice column log_level
```

This converts from:

| `_timeslice` | `log_level` | `_count` |
|---|---|---|
| 14:00 | error | 12 |
| 14:00 | warn | 45 |

To:

| `_timeslice` | `error` | `warn` |
|---|---|---|
| 14:00 | 12 | 45 |

Each column becomes a series on the chart.

**Chart types available:**
- **Line chart** — best for trends over time
- **Area chart** — good for showing volume over time; stacked area shows composition
- **Column chart** — good for periodic counts (e.g., per-hour bars)
- **Stacked bar** — shows proportion changes over time

**Tips:**
- `timeslice` without a parameter auto-selects an appropriate interval based on the selected time range
- Use `| sort _count` before `transpose` to order series by volume

---

### Time Series with Time Compare

One of the most valuable panel patterns: compare current values against the same period in prior weeks.

```
// Current vs. same time last week:
_sourceCategory=Labs/Apache/Access
| timeslice by 15m
| count by _timeslice
| compare with timeshift 7d 2
```

This appends `_count_7d` and `_count_14d` columns which chart as additional series, giving instant historical context.

```
// Current vs. 3-week average:
_sourceCategory=Labs/Apache/Access
| timeslice by 15m
| count by _timeslice
| compare with timeshift 7d 3 avg
```

Use the **line chart** type with time compare — each historical period becomes a separate series.

---

### Single Value Panels

Display a single number for at-a-glance status. Common for KPIs and health indicators.

**Required query shape:** aggregate to a single row with a single metric field.

```
// Total error count:
_sourceCategory=prod/app error
| count

// P95 latency:
_sourceCategory=prod/app
| json "duration_ms" as duration
| pct(duration, 95) as p95_ms
```

**Tips:**
- Add conditional formatting (thresholds) to colour the value red/yellow/green
- Label the unit clearly (ms, requests, GB, etc.)

---

### Honeycomb Panels

A grid of coloured cells where each cell represents one entity (host, service, container). Cell colour indicates health or volume.

**Required query shape:** categorical aggregate producing one row per entity.

```
// Honeycomb of error counts by service:
_sourceCategory=prod/app error
| json "service" as service
| count by service
```

The entity field (e.g., `service`) maps to honeycomb cells; the metric field (e.g., `_count`) drives cell colour. Set colour thresholds to show green/yellow/red health states.

**Best for:** Status dashboards with many entities (hosts, services, pods) where you want to quickly spot outliers.

---

### Map Panels

Geographic map showing event distribution by location. Requires latitude/longitude fields.

**Required query shape:** categorical aggregate with `latitude`, `longitude`, and at least one metric.

```
_sourceCategory=web/access
| parse "* * * * \"*\" * *" as src_ip, ident, user, time, request, status, bytes
| geoip src_ip
| where !isEmpty(country_name)
| count by latitude, longitude, country_name, city
```

**Tips:**
- Use `| where !isEmpty(country_name)` to exclude events with failed geo-resolution
- The `geoip` operator resolves public IP addresses; private IPs will not resolve

---

### Text Panels

Markdown text panels for annotations, instructions, or links.

```markdown
## Service Health Dashboard

Use the **Environment** and **Service** filters above to scope the view.

For incidents:
1. Check the Error Rate panel for recent spikes
2. Click the service name to drill into the Service Detail dashboard
3. Open the Alert Response Page for active alerts

[Runbook](https://wiki.example.com/runbooks/service-health) | [Alert List](/alerts)
```

**Tips:**
- Add text panels to explain what the dashboard shows and how to use it
- Use headings to group sections of complex dashboards
- Add links to runbooks, related dashboards, or external ticketing systems

---

## Choosing the Right Chart Type

| Data Shape | Best Chart Types |
|---|---|
| Single metric at a point in time | Single Value |
| Categories by count/volume | Bar chart, Table, Pie (≤7 categories) |
| Many entities (hosts, services) at a glance | Honeycomb |
| Trend over time (single metric) | Line, Area |
| Trend over time (multiple metrics) | Multi-series Line with transpose |
| Trend with historical comparison | Line with `compare with timeshift` |
| Geographic distribution | Map |
| Proportional share over time | Stacked Area or Stacked Bar |

---

### Heatmap Panels

A newer categorical panel type designed for metrics but works for logs too. Aggregates data by value on the y-axis and over time on the x-axis. Useful for spotting patterns across many entities (e.g., CPU across all EC2 instances).

**Metrics example:**
```
instanceid=* namespace=aws/ec2 metric=CPUUtilization Statistic=average
| avg by instanceid
```

**Logs example** (requires timeslice + transpose since the heatmap expects time series format):
```
exception
| timeslice 15m
| count by _timeslice, host
| transpose row _timeslice column host
```

---

### Bubble and Scatter Panels

Scatter and bubble chart types display correlations between two numeric axes. Bubble charts add a third dimension via bubble size. Useful for correlating metrics like request rate (x) vs error rate (y) per service.

---

### Transpose Without Timeslice (Grouped Stacked Bar)

One of the most advanced — and underused — panel patterns: using `transpose` on a **categorical** (non-time) query to create a compact, high-density grouped view.

**"No one is an advanced Sumo user until they have done a transpose without timeslice."**

Use this pattern to show variable groups (e.g., error codes) as separate series on a stacked bar chart grouped by another dimension (e.g., AWS region). This enables much higher view density than a table.

```
// Error codes by AWS region — stacked bar showing all error codes per region
_sourceCategory=*cloudtrail* errorcode
| json field=_raw "errorCode"
| count by errorcode, aws_region
| transpose row aws_region column errorcode
```

The result: one bar per `aws_region`, with separate stacked segments for each `errorcode`. Use **stacked bar chart** for this pattern.

---

### Timeless Dashboards with Cat (Lookup State Tables)

Sumo Logic is a time-series database — by default you need to search all historical time to find the "current state" of something. But using a lookup table as a state store, you can build dashboards that show current state with a `-15m` query window.

**How it works:**
1. A scheduled search saves new state changes to a lookup table (using `save append` with the ID as key)
2. Dashboard queries use `cat /path/to/lookup` to read the lookup table instantly
3. Because lookups are timeless, the dashboard time range makes no difference — set all panels to `-15m`

```
// Dashboard panel: current status of all CSE insights (regardless of when they occurred)
cat path://"/Library/Admin Recommended/CSIEM/Lookups/cse_insights_status"
| where time > (now() - (1000 * 60 * 60 * 24 * 90))   // last 90 days
| formatdate(tolong(time), "yyyy-MM") as month
| count by status, month
```

**For time series charts from a lookup table:** The lookup stores the actual event time as an epoch column. Convert it back to a timeslice field at query time:

```
cat path://"/Library/Admin Recommended/CSIEM/Lookups/cse_insights_status"
| tolong(time) as _messagetime
| timeslice 1w
| count by _timeslice, status
```

**Important notes:**
- Filtering on time must use math against your stored time column: `where time > (now() - (1000 * 60 * 60 * 24 * 90))`
- Use custom JSON axis config for long-range time charts: `"interval": 1, "intervalType": "week"`
- Lookup v2 tables have a 100MB size limit — monitor usage for high-volume sources

---

### Clickable URL Columns in Tables

Use `tourl`, `urlencode`, and `concat` to create clickable links in table panels that open external systems, other Sumo Logic dashboards, or new searches with pre-filled time ranges.

```
// Clickable link to open a new Sumo Logic search for this source IP
_view=threat_geo_asn_v1
| min(_timeslice) as f, max(_timeslice) as l, count by src_ip, country_code
| "live.us2.sumologic.com" as dp
| num(l - (1000 * 60 * 60 * 3)) as f
| format("%.0f", f) as f
| format("%.0f", l) as l
| tourl(
    concat("https://", dp, "/ui/#/search/@", f, ",", l, "@", urlencode(src_ip)),
    src_ip
  ) as src_ip
| fields -dp, f, l
```

You can link to:
- External systems (Jira, PagerDuty, SIEM) by constructing the appropriate URL
- Another Sumo Logic dashboard with template variable values pre-filled
- A new search window with the time range and query pre-populated (the example above)

---

### Emoji / Visual Bar Columns in Tables

Sumo Logic supports emojis in dashboard tables and single-value panels (string type). This enables visual status bars or indicator columns using query logic.

```
// Visual bar showing error rate per URL
_sourceCategory=*apache* status_code=*
| if(status_code > 499, 1, 0) as http5xx
| count as requests, sum(http5xx) as http5xx by url
| where http5xx > 0
| ceil((http5xx / requests) * 10) as dec
| pow(10, dec) as base_ten
| replace(tostring(round(base_ten)), "1", "") as zeros
| replace(zeros, "0", "■") as bar
```

The `bar` column renders as a visual indicator in the table. Replace `"■"` with any emoji for colorful status indicators.

---

## Advanced Dashboard Configuration

### Panel Overrides (Series Customisation)

Panel overrides let you customise individual series independently within a chart panel:

- **Custom color per series** — colour important series differently (e.g., production vs. staging)
- **Alias names** — rename series labels, including `{{moustache}}` template variable values
- **Left/right axes with different scales** — overlay latency (ms) and request count on the same chart
- **Mixed chart formats** — combine line and column charts in one panel (e.g., line for trend, bars for volume)

Access overrides via: Dashboard panel → Edit → **Overrides** tab.

### JSON Panel Editing

Every panel in Sumo Logic can be edited directly in JSON mode. This unlocks configuration options not exposed in the UI.

**Access:** Edit a panel → click the JSON edit icon (top right of panel editor).

**Common JSON config use cases:**

```json
// Shrink pie chart segment labels (useful for many or long category names)
"general": {
  "indexLabelFontSize": 8
}

// Custom time interval labels on time series (e.g., weekly intervals)
"axisX": {
  "titleFontSize": 12,
  "labelFontSize": 12,
  "interval": 1,
  "intervalType": "week"
}

// Add export button (PNG/JPEG) to a panel
"general": {
  "mode": "timeSeries",
  "exportEnabled": true
}

// Labels inside bars (for bar charts)
"axisX": {
  "labelPlacement": "inside",
  "labelWrap": false,
  "labelMaxWidth": 250
}

// Auto-compress blank areas in sparse time series
"axisX": {
  "scaleBreaks": {
    "type": "wavy",
    "fillOpacity": 1,
    "autoCalculate": true
  }
}
```

**Copy panels between dashboards:** Use JSON edit → "Copy to Clipboard", then paste into a new panel on another dashboard — all settings including overrides are preserved.

---

## Common Issues

### Panel Shows No Data

- Check if the query includes a `timeslice` — time series panels require it; categorical panels don't
- Verify `_sourceCategory` or `_index` is correct for the environment
- Check the dashboard time range — the selected range may not contain matching data

### Multi-Series Chart Shows Only One Series

- Missing `| transpose row _timeslice column <field>` after `count by _timeslice, <field>`

### Pie Chart Has Too Many Slices

- Add `| top 10 field by _count` to limit categories
- Or switch to a Table panel for high-cardinality dimensions

---

## MCP Tools Used

- `search_sumo_logs` — Test and validate panel queries before adding to dashboard
- `search_query_examples` — Find example queries for specific panel patterns

## Related Skills

- [Dashboards Overview](./dashboards-overview.md)
- [Log Search Basics](./search-log-search-basics.md)
- [Time Compare and Anomaly Alerting](./alerting-time-compare-anomaly.md)

## API References

- [Time Compare Operator](https://help.sumologic.com/docs/search/time-compare/)
- [Aggregate Operators](https://help.sumologic.com/docs/search/search-query-language/group-aggregate-operators/)
- [Dashboard Panel Types](https://help.sumologic.com/docs/dashboards/panels/)

---

**Version:** 1.1.0
**Last Updated:** 2026-03-11
**Source:** SumoLogic Logs Basics Training (August 2025); Sumo Logic Advanced Topics Workshop (2025/2026)
