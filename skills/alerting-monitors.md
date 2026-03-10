# Skill: Sumo Logic Monitors — Stateful Alerting

## Intent

Create and configure Sumo Logic Monitors for stateful alerting on logs, metrics, or SLOs — including choosing detection methods (static, anomaly, outlier), configuring alert grouping, writing effective monitor queries, and using the Alert List and Alert Response Page for investigation.

## Prerequisites

- Understanding of Sumo Logic log search basics (see `search-log-search-basics`)
- A working aggregate log or metric search query that returns a numeric value
- View Alerts permission in your user role

## Context

**Use this skill when:**

- Creating new alerts for observability or security use cases
- Choosing between static, anomaly, or time compare detection methods
- Configuring alert grouping to monitor multiple entities with one monitor
- Investigating fired alerts via the Alert List or Alert Response Page
- Managing monitors as code via Terraform or the API

**Don't use this when:**

- You want a simple daily/weekly email report (use Legacy Scheduled Search for that)
- You are alerting on Infrequent or Frequent tier data (Monitors only work on Continuous tier, except Infrequent+ customers)

---

## Monitors vs. Scheduled Searches

Sumo Logic has **two alerting engines**. Choose based on your use case:

| Feature | Monitors (Recommended) | Scheduled Search (Legacy) |
|---|---|---|
| Data types | Logs, Metrics, SLO | Logs only |
| Alert model | **Stateful** — tracks state changes (normal → warning → critical) | Fires every time schedule runs and matches |
| Alert Response Page | Yes — per-alert history, context, related entities | No |
| Alert grouping | Yes — one monitor can alert per entity/time series | No |
| API / as-code | Full API + Terraform | Limited |
| Best for | Production alerting on conditions | Reporting (daily/weekly email digests) |

**Recommendation:** Use Monitors for all new alerting. Scheduled Searches are useful only for reporting use cases where a periodic email is the desired output.

---

## Monitor Types

### 1. Logs Monitor

Runs a log search query on a schedule. The query must produce a numeric value (usually via aggregation).

**Key difference from regular log search:** In a log monitor, you do **not** need `| timeslice` — the monitor's "evaluate every X minutes" setting is effectively the time slice. The query just needs to return a count or metric for the evaluation window.

```
// Simple log monitor query — no timeslice needed:
_sourceCategory=prod/app error
| count

// Or aggregate by entity for alert grouping:
_sourceCategory=prod/app error
| json "service" as service
| count by service
```

### 2. Metrics Monitor

Runs a metrics query. Useful for infrastructure-level alerting (CPU, memory, disk, etc.).

```
Namespace=aws/ecs metric=CPUUtilization statistic=Average
account=* region=* ClusterName=* ServiceName=*
| avg by ClusterName, ServiceName, account, region, namespace
```

### 3. SLO Monitor

Alerts when a Service Level Objective (SLO) enters a breach or burn-rate state over time.

---

## Detection Methods

### Static Thresholds

Fixed numeric thresholds for Warning and Critical states. Simple and predictable.

- Warning: trigger when value > X
- Critical: trigger when value > Y
- Missing Data: trigger when no data is received

Best for: known baselines, hard limits (e.g., error count > 100 = critical).

### Anomaly Detection (Recommended over Outlier)

Machine learning establishes a baseline of normal behaviour from historical data. The monitor fires when the current value deviates significantly from the baseline.

- Fewer false positives than statistical outlier
- Configurable **sensitivity** (low/medium/high) and **direction** (up, down, or both — usually "up only" is best)
- Data is streamed to an external AI/ML model
- More cost-effective than Outlier monitors

Best for: cyclic patterns, unknown baselines, reducing alert noise.

### Outlier Detection (Legacy — prefer Anomaly)

Statistical outlier detection based on standard deviations from a moving window. Functionally similar to Anomaly but tends to generate more noise. Sumo Logic recommends converting legacy Outlier monitors to Anomaly monitors.

### Time Compare (Static Evaluation with Dynamic Threshold)

A special pattern using the `compare with timeshift` operator to create a dynamic threshold based on historical values (see `alerting-time-compare-anomaly` for detail).

---

## Alert Grouping

Alert grouping (also called "one alert per time series") allows **one monitor configuration** to track and alert independently for multiple entities.

Without grouping, one alert state is tracked for the entire monitor.
With grouping, a separate alert state is tracked for each unique value of the grouping field.

```
// Monitor query grouped by service:
_sourceCategory=prod/app error
| json "service" as service
| count by service

// Alert grouping: "one alert per: service"
// Result: separate Warning/Critical states for each service value
```

This dramatically reduces the number of monitor configurations needed for multi-tenant or multi-service environments.

---

## Notification Variables

Use `{{ResultsJson.fieldName}}` to include field values from the monitor's result in alert notifications (subject line, email body, webhook payload).

**Best used with aggregated monitor queries** that produce named output fields.

```
// Query output fields: client_ip, errors
"{{ResultsJson.client_ip}} had {{ResultsJson.errors}} errors"

// Renders as: "70.69.152.165 had 391 errors."
```

Other useful notification variables:
- `{{Name}}` — monitor name
- `{{Description}}` — monitor description
- `{{TriggerTime}}` — time the alert fired
- `{{TriggerType}}` — Warning, Critical, or ResolvedCritical

---

## Viewing and Investigating Alerts

### Alert List Page

Access via the Alerts menu. Shows all fired alerts across all monitors.

- Filter by: status (Active, Resolved), severity (Warning, Critical), custom tags (team, owner, service, environment)
- Search by keywords
- Each row shows whether the alert is per-monitor (entity is blank) or per-group/time-series (entity has a value)

### Alert Response Page

Click any alert to open its **Alert Response Page**, which provides:

- **Alert history graph** — trend of the metric over time showing when it breached and resolved
- **Related alerts** — other alerts that fired around the same time (correlation)
- **Related entities** — other services or hosts linked to the alert
- **Context cards** — additional context (e.g., recent deployments, infrastructure state)
- **Proactive search actions** — suggested log searches to investigate the root cause
- Copilot integration for natural language investigation

---

## Monitor Tips

| Tip | Detail | Example |
|---|---|---|
| Aggregate your query | Aggregate by the dimensions you want to alert or group on | `\| avg by ClusterName, ServiceName, account, region` |
| Use alert grouping | One monitor config can alert on many instances | Set "one alert per: service" |
| No timeslice needed | Monitor evaluation window acts as the time slice | `\| count` instead of `\| timeslice 5m \| count by _timeslice` |
| Use `{{ResultsJson.field}}` | Personalise notification content with field values | `"{{ResultsJson.client_ip}} had {{ResultsJson.errors}} errors"` |
| Tag monitors | Add team, owner, service, env tags for filtering in Alert List | Monitor settings → Tags |
| Start with low sensitivity for Anomaly | Avoids excessive noise when first deploying | Sensitivity: Low → tune upwards |

---

## SLOs — Service Level Objectives

Sumo Logic supports defining and tracking **Service Level Objectives (SLOs)** directly in the platform.

**Key concepts:**
- **SLI (Service Level Indicator)**: the metric you measure — e.g., "% of 5-minute windows where p99(latency) < 500ms"
- **SLO**: a target for the SLI — e.g., "SLI ≥ 99.9% in any calendar month"
- **Error budget**: the acceptable level of unreliability — e.g., 0.1% unreliability = 8 bad 5-minute windows in 30 days
- **Compliance period**: the window over which compliance is measured (typically 1 month or 7 days)

**SLO monitors in Sumo Logic:**
- Define SLO on log or metric queries with compliance period and evaluation method (periodic or aggregate)
- Visualise burn-down and compliance state via the SLO dashboard
- Generate SLO Monitor alerts when error budget is burning faster than expected
- Analyse trend across compliance periods by business, application, or service
- Automate SLO definition via OpenSLO (through the slogen tool)

**Monitor type for SLOs:** Use the **SLO monitor type** in Monitors — this is different from a standard Logs or Metrics monitor. It alerts when the SLO enters a breach or burn-rate state over the compliance period.

---

## Monitors as Code

Monitors have a dedicated REST API and are fully supported by the **Sumo Logic Terraform provider**. This enables:

- Version-controlled monitor definitions
- Repeatable deployment across environments
- Review and approval workflows for alert changes

Reference: [Monitors API](https://api.sumologic.com/docs/#tag/monitorsLibraryManagement)

---

## MCP Tools Used

- `search_sumo_monitors` — Search for existing monitors and check their status
- `search_system_events` with `use_case="monitor_alerts"` — Analyse monitor alert history
- `search_system_events` with `use_case="monitor_alert_timeline"` — View alert state timeline

## Related Skills

- [Time Compare and Anomaly Alerting](./alerting-time-compare-anomaly.md)
- [Log Search Basics](./search-log-search-basics.md)
- [Dashboards Overview](./dashboards-overview.md)

## API References

- [Monitors API](https://api.sumologic.com/docs/#tag/monitorsLibraryManagement)
- [Alert Variables](https://help.sumologic.com/docs/alerts/monitors/alert-variables/)
- [Monitor Detection Methods](https://help.sumologic.com/docs/alerts/monitors/create-monitor/)

---

**Version:** 1.1.0
**Last Updated:** 2026-03-11
**Source:** SumoLogic Logs Basics Training (August 2025); CIP Onboarding Sessions I & II
