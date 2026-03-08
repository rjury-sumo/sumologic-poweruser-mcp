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

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** SumoLogic Logs Basics Training (August 2025)
