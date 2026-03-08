# Skill: Time Compare and Anomaly Alerting in Sumo Logic

## Intent

Use the `compare with timeshift` operator and Anomaly/Outlier detection to create dynamic threshold alerts that detect cyclic anomalies, revenue drops, and unusual patterns — moving beyond simple static thresholds.

## Prerequisites

- Understanding of Sumo Logic Monitors (see `alerting-monitors`)
- A numeric aggregate log or metric query
- Baseline historical data available (at least 7+ days for weekly comparisons)

## Context

**Use this skill when:**

- Static thresholds produce too many false positives (e.g., normal traffic spikes look like errors)
- You need to detect unusual behaviour in cyclic patterns (e.g., daily/weekly traffic cycles)
- You want to alert when revenue, request rates, or error counts drop significantly below historical norms
- You are replacing an Outlier monitor with a newer Anomaly monitor

**Don't use this when:**

- You have a hard, known threshold that should never be exceeded (use Static instead)
- Your data has fewer than a few days of history (not enough baseline for anomaly/time compare)

---

## Time Compare (`compare with timeshift`)

### How It Works

The `compare with timeshift` operator appends historical values to the current query results. You can then compute deltas, ratios, and percentage changes to create your own dynamic threshold logic with a `where` clause.

This is used as a **Static detection method** in monitors (the alert fires when your `where` clause matches a row), giving you a **dynamic, data-driven threshold**.

### Basic Syntax

```
| timeslice <interval>
| <aggregate> by _timeslice
| compare with timeshift <period> [<count> avg]
```

- `timeshift 1d` — compare to the same time yesterday
- `timeshift 7d` — compare to the same time last week
- `timeshift 7d 3 avg` — compare to the average of the same time over the last 3 weeks
- `timeshift 1d 7 avg` — compare to the average of the last 7 days at this same time

### Example: Revenue Drop Detection

```
_sourceCategory="kubernetes/prod/analytics/svc"
| %"log.data[0].value" as revenue
| sum(revenue) as revenue
| compare with timeshift 1d 7 avg   // Compare to average of last 7 days at same time
| revenue - revenue_7d_avg as change
| 100 * (revenue / revenue_7d_avg) as pct_of_avg
| where pct_of_avg < 50   // Alert when revenue is below 50% of historical average
```

In a monitor, set **trigger condition** to: "number of results > 0" — the `where` clause means a row only appears when the condition is breached.

### Example: Simple Day-over-Day Error Rate

```
_sourceCategory=prod/app error
| timeslice 15m
| count by _timeslice
| compare with timeshift 1d 2
```

The output will include `_count` (current) and `_count_1d` (yesterday) and `_count_2d` (two days ago) columns.

### Key Advantages of Time Compare Alerts

- **Cyclic-aware**: works well with daily/weekly traffic patterns that would trigger naive static alerts during peak hours
- **Per-entity**: can be applied per service, per host, per source category using grouping
- **Fully customisable**: use the full query language in the `where` clause
- **Interpretable**: you can see the exact calculation that triggered the alert

---

## Anomaly Detection

### How It Works

Sumo Logic's Anomaly detection uses a **machine learning model** trained on historical time series data for a given monitor. The model establishes baselines for normal behaviour and fires alerts when the current value deviates significantly.

Data is streamed to an external AI/ML model — Sumo Logic maintains this model automatically.

### Configuration Options

| Setting | Description |
|---|---|
| **Sensitivity** | Low / Medium / High — controls how aggressively deviations are flagged. Start low to reduce noise, tune upwards. |
| **Direction** | Up, Down, or Both. "Up only" is usually best for error/latency monitors to avoid alerts on low-traffic periods. |

### When to Use Anomaly

- You don't know a good static threshold
- Traffic volumes vary significantly by time of day or day of week
- You want to reduce false positives versus static thresholds
- You are replacing an existing Outlier monitor (Sumo recommends migrating)

### Anomaly vs. Outlier

| Feature | Anomaly (New) | Outlier (Legacy) |
|---|---|---|
| Algorithm | External AI/ML model | Statistical standard deviation |
| False positive rate | Lower | Higher (noisier) |
| Cost efficiency | Better | Less efficient |
| Recommendation | **Use this** | Migrate to Anomaly |

**Sumo Logic recommendation:** Convert all legacy Outlier monitors to Anomaly monitors.

---

## Choosing the Right Detection Method

| Scenario | Recommended Method |
|---|---|
| Hard limit that should never be breached (e.g., error count > 500) | **Static** |
| Rate that varies with traffic (e.g., error rate spikes) | **Anomaly** |
| Business metric drop vs. historical baseline (e.g., revenue -50%) | **Time Compare** (with Static evaluation) |
| Unknown baseline, first-time alerting | **Anomaly** |
| Daily/weekly cyclic patterns with variable peaks | **Anomaly** or **Time Compare** |
| Need full control over threshold logic with query language | **Time Compare** (Static evaluation) |

---

## Time Compare in Dashboards

The `compare with timeshift` operator is not just for alerts — it is one of the most valuable patterns for dashboards too.

```
// Dashboard panel: current vs. last week, 15-minute buckets
_sourceCategory=Labs/Apache/Access
| timeslice by 15m
| count by _timeslice
| compare with timeshift 7d 2
```

This produces a multi-series chart showing current traffic alongside the same period from prior weeks — giving instant context for anomalies.

---

## Advanced Time Compare Tips

### Averaging Across Multiple Periods

```
| compare with timeshift 7d 3 avg   // Average of weeks -1, -2, -3
| compare with timeshift 1d 7 avg   // Average of same time over last 7 days
```

The `avg` keyword computes the mean across `N` prior periods, smoothing out any single anomalous prior period.

### Per-Entity Comparison

```
_sourceCategory=prod/app error
| json "service" as service
| timeslice 15m
| count by _timeslice, service
| compare with timeshift 7d 3 avg
| transpose row _timeslice column service
```

---

## MCP Tools Used

- `search_sumo_monitors` — Find and inspect existing monitors, including their detection methods
- `search_sumo_logs` — Test time compare queries interactively before setting up a monitor
- `search_system_events` with `use_case="monitor_alert_timeline"` — Review alert firing history

## Related Skills

- [Monitors — Stateful Alerting](./alerting-monitors.md)
- [Log Search Basics](./search-log-search-basics.md)
- [Dashboard Panel Types](./dashboards-panel-types.md)

## API References

- [Time Compare Operator](https://help.sumologic.com/docs/search/time-compare/)
- [Monitor Anomaly Detection](https://help.sumologic.com/docs/alerts/monitors/create-monitor/)
- [Create Monitor API](https://api.sumologic.com/docs/#tag/monitorsLibraryManagement)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** SumoLogic Logs Basics Training (August 2025)
