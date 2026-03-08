# Skill: Sumo Logic Indexes, Partitions and Data Tiers

## Intent

Understand how Sumo Logic stores logs in partitions (indexes), how data tiers affect search behaviour and cost, and how to scope searches to the right partition to maximise performance.

## Prerequisites

- Basic understanding of Sumo Logic search (see `search-log-search-basics`)
- Access to a Sumo Logic instance

## Context

**Use this skill when:**

- Trying to understand why a search returns no results or is slow
- Scoping searches to reduce scan and cost on Flex or Infrequent tiers
- Determining which index holds a particular set of logs
- Building partitions or explaining the data tier model to others

**Don't use this when:**

- Working with metrics (different storage model)
- Querying traces (separate tracing index)

---

## Key Terminology

Sumo Logic uses the terms **index**, **partition**, and **view** interchangeably to refer to the same concept: a named logical grouping of log data stored together in the backend.

- `_index` = the metadata field you use to scope a search to a partition
- `_view` = the same field shown in the Log Message Inspector
- **Partition** = the object administrators create and manage in the UI/API

---

## Default Partition

All logs that are not routed to a specific partition land in `sumologic_default`. This is the most common partition for unmanaged log sources.

```
_index=sumologic_default _sourceCategory=prod/app
```

---

## Data Tiers (Licensing)

Sumo Logic has two main licensing models, each with different tier behaviours:

### Enterprise Suite (Tiered)

Logs land in one of three tiers at ingest time:

| Tier | Use Case | Cost Model | Default Scope |
|---|---|---|---|
| **Continuous** | Mission-critical, always-on analytics | Cost at ingest; search free | Yes — included in default scope |
| **Frequent** | High-usage ad-hoc analysis | Cost at ingest; search free | Yes — included in default scope |
| **Infrequent** | Low-usage, cold data | Low ingest cost; **pay per search** (cost per GB scanned) | No — must add `_index=<name>` explicitly |

Key implications for Enterprise Suite:
- Infrequent partitions are **excluded from default search scope** — you must add `_index=<partition_name>` to return results
- Monitors, dashboards, scheduled views, and scheduled searches can only be used on **Continuous** tier data (except for Infrequent+ customers)
- It is prudent to always scope with `_index=<name>` for Infrequent searches to control cost

### Cloud Flex

All logs land in `sumologic_default` by default. Search charges are applied based on GB scanned regardless of tier.

- Default scope includes all partitions marked "included in default scope"
- Each search incurs a small on-demand charge based on data scanned
- Scope searches with `_index=<name>` to minimise cost and improve speed
- Some data is **exempt** from search scan charges: logs sent to Cloud SIEM (`_siemforward=true`) and certain internal audit partitions

---

## How to Find the Index for Your Logs

### Method 1: Run a Sample Search

Run a short time-range search with your known `_sourceCategory` and no `_index`. In the results, look in the **message metadata** for the `_view` field value — that is the partition name.

```
_sourceCategory=prod/myapp
// Check the _view field in any returned message
```

### Method 2: Use the Log Message Inspector

Click any log message to open the **Log Message Inspector**. The `_view` field shown there is the partition name. Use the ellipsis menu to add it directly to your query scope.

### Method 3: Use the Field Browser

The Field Browser (side panel) shows a `_view` section listing the partitions present in your current result set.

### Method 4: Query Using the MCP `explore_log_metadata` Tool

```json
{
  "scope": "_sourceCategory=prod/myapp",
  "metadata_fields": "_view,_sourceCategory",
  "from_time": "-15m"
}
```

---

## Adding Index to Search Scope

Once you know the partition name, add it to your scope:

```
// Single partition:
_index=my_partition _sourceCategory=prod/app

// Multiple partitions (OR):
(_index=partition_a OR _index=partition_b) _sourceCategory=prod/*

// Wildcard (use with caution — may expand scan):
_index=prod_* _sourceCategory=prod/app
```

**Note:** If you specify `_sourceCategory` and Sumo can determine that category only exists in certain partitions, it will automatically reduce the scan — even without explicit `_index`. But adding `_index` explicitly is still best practice for clarity and reliability.

---

## Administrators: Creating and Managing Partitions

Administrators create partitions to:

- Group similar log data together (faster queries, lower cost for Infrequent)
- Control retention periods per log type
- Route specific log types to the appropriate data tier

Partitions are defined by a **routing expression** (e.g., `_sourceCategory=prod/app/*`) that automatically routes matching logs into the partition at ingest time.

To list partitions via MCP:

```json
// Use get_sumo_partitions tool
{}
```

---

## Practical Scoping Examples

### Well-Scoped Searches

```
// Specific production app in known partition:
_index=prod_app_logs _sourceCategory=prod/checkout error

// AWS CloudTrail in a dedicated partition:
_index=cloudtrail _sourceCategory=aws/cloudtrail "AccessDenied"

// Kubernetes logs via index + category:
_index=tl_kube _sourceCategory=kubernetes/prod stdout error
```

### Verifying Scan Before Running

Use the scan estimate feature (meter icon in search UI) to check how much data will be scanned before running expensive queries. Reference: https://help.sumologic.com/docs/manage/partitions/flex/estimate-scan-data/

---

## Common Issues

### "No results" from Infrequent Tier

If you expect results but get none from an Infrequent partition, you likely need to add `_index=<partition_name>` because Infrequent partitions are excluded from default scope on Enterprise Suite.

### High Scan Costs

If a search is scanning more data than expected, check:
1. Are you missing `_index=` in the scope?
2. Is the time range longer than needed?
3. Are you querying without `_sourceCategory`?

### Partition vs. View — Same Thing

Don't be confused by the two names: `_view` is the field name shown in log messages and the inspector, but `_index` is what you use in query scope. They refer to the same partition.

---

## MCP Tools Used

- `explore_log_metadata` — Discover which partitions/views hold your log data
- `get_sumo_partitions` — List all configured partitions (admin)
- `get_estimated_log_search_usage` — Estimate scan before running
- `list_scheduled_views` — List scheduled views (pre-aggregated partitions)

## Related Skills

- [Search Performance Best Practices](./search-performance-best-practices.md)
- [Log Search Basics](./search-log-search-basics.md)

## API References

- [Partitions API](https://api.sumologic.com/docs/#tag/partitionManagement)
- [Data Tiers Overview](https://help.sumologic.com/docs/manage/partitions/)
- [Scan Data Estimation](https://help.sumologic.com/docs/manage/partitions/flex/estimate-scan-data/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** SumoLogic Logs Basics Training (August 2025)
