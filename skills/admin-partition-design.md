# Skill: Sumo Logic Partition Design for Administrators

## Intent

Design a Sumo Logic partition (index) architecture that minimises search scan, enables query rewriting, reduces cost, and is easy for users to understand and use — applying the seven rules of good partition design.

## Prerequisites

- Sumo Logic administrator access (Manage Data → Logs → Partitions)
- Understanding of how partitions affect search scope (see `search-indexes-partitions`)
- Understanding of source categories in use across your environment

## Context

**Use this skill when:**

- Designing partition architecture for a new Sumo Logic deployment
- Reviewing and improving an existing partition structure
- Troubleshooting high scan costs or slow searches caused by poor partition design
- Deciding how to route CSE (SIEM) vs. non-CSE data on Flex tier
- Advising users on why searches are slow and how to fix them

**Don't use this when:**

- Creating individual saved searches or dashboards (different concern)
- Administering data collection sources (different concern)

---

## What Are Partitions?

Partitions (also called indexes or views) are named logical groupings of log data stored together in the Sumo Logic backend. They are the primary mechanism for controlling **scan scope** — the most impactful factor in search performance and cost.

- Configured in: **Manage Data → Logs → Partitions**
- Default partition: `sumologic_default` — all data lands here unless routed elsewhere
- Referenced in queries as: `_index=<name>` or `_view=<name>` (same thing)
- On Enterprise Suite, each partition also determines the **data tier** (Continuous, Frequent, Infrequent)
- On Flex, partitions can be included or excluded from default search scope

---

## The Seven Rules of Good Partition Design

### Rule 1: Use the Same Metadata Field Across All Partitions

Scope every partition using **the same metadata field** — typically `_sourceCategory`. This consistency enables the query rewriting engine to automatically constrain queries to the correct partition without users needing to specify `_index=` explicitly.

**Good — consistent `_sourceCategory` scoping:**
```
aws_waf         _sourceCategory=aws/waf*
nginx_prod      _sourceCategory=prod/nginx/*
cloudtrail      _sourceCategory=aws/cloudtrail/*
k8s_control     _sourceCategory=kubernetes/control-plane/*
```

**Bad — mixed metadata degrades query rewriting:**
```
cdn_logs        _sourceHost=*cdn/*            ← different field
waf_logs        _collector=prod/waf/*          ← different field
nginx_logs      _sourceCategory=prod/nginx/*   ← inconsistent with others
```

Mixed metadata means users must explicitly add `_index=<name>` to every query targeting a specific partition, because the engine cannot reliably infer it from the scope. This is a significant usability and training burden.

### Rule 2: Group Partitions Around Log Types or Use Cases

Design partitions to map to concepts that **end users naturally think about**: WAF logs, CloudTrail, application errors, K8s container logs. Don't create partitions based on internal infrastructure details that users don't know or care about.

### Rule 3: Keep Partition Names Simple and Memorable

The best partition names are short, lowercase, descriptive, and easy to type. Users will need to include `_index=<name>` in queries.

```
// Good names:
waf_logs
cloudtrail_high_use
cloudtrail_low_use
nginx_prod
security_restricted
my_big_app

// Poor names:
partition_group_A_aws_infrastructure_2024
LOG_DATA_PROD_US_EAST_1_V3
```

### Rule 4: Keep Small, High-Use Logs in Small Partitions

"Collateral damage" occurs when a small, frequently queried log type shares a partition with a much larger log type. Every search for the small log type pays the scan cost of the entire large partition.

**Example:** Kubernetes control-plane logs (kubelet, events, scheduler) may only be 100 MB/day — but all K8s container logs could be 1 TB/day. Put control-plane in its own partition so searches for scheduler events scan 100 MB instead of 1 TB.

```
k8s_control     _sourceCategory=kubernetes/control-plane/*   100 MB/day
k8s_containers  _sourceCategory=kubernetes/containers/*      1 TB/day
```

### Rule 5: Don't Let the Default Partition Get Too Large

The `sumologic_default` partition is the catch-all. Every search that doesn't match a named partition lands here. If it grows large, unscoped searches become very slow and expensive.

**Target:** Keep `sumologic_default` under ~10% of total daily ingest. Move large or well-defined log types to dedicated partitions.

### Rule 6: Limit Total Number of Partitions (and Document Them)

More partitions improve scan performance per query — but past a certain point they create a usability and training problem. Users cannot easily discover or remember where to find their data.

- Up to ~20–30 partitions: manageable with basic user training
- 30–100 partitions: requires good documentation, saved example queries, and enablement content
- Over 100 partitions: requires very strong documentation, templated query content, and ongoing user support

### Rule 7: Use FERs for Complex Routing (Not Complex Partition Scopes)

For complex routing scenarios, set a tagging field value in a Field Extraction Rule (FER) using `if` statements, then scope the partition to that tag field. This keeps partition scope expressions simple and maintainable.

**Example:** Route nginx logs to Continuous or Infrequent tier based on HTTP status code.

```
// FER on _sourceCategory=*nginx* sets a 'tier' field:
| "" as tier
| if(status_code < 400, "infrequent", "continuous") as tier
| if(url matches "*checkout*", "continuous", tier) as tier

// Partitions use simple tier field scope:
nginx_cont      _sourceCategory=*nginx* tier=continuous
nginx_infreq    _sourceCategory=*nginx* tier=infrequent
```

---

## The Scan Reduction Impact of Good Design

A concrete example comparing two customers both ingesting 1.1 TB/day:

**Customer A: Single default partition**

Every search — regardless of scope — scans the full 1.1 TB/day. `_sourceCategory=prod/waf/*` scans 1.1 TB.

**Customer B: Many well-scoped partitions**

| Partition | Scope | Daily Volume |
|---|---|---|
| `sumologic_default` | Default catch-all | 100 GB |
| `cdn_logs` | `_sourceCategory=prod/cdn/*` | 200 GB |
| `waf_logs` | `_sourceCategory=prod/waf/*` | 200 GB |
| `lb_logs` | `_sourceCategory=prod/lb/*` | 100 GB |
| `nginx_logs` | `_sourceCategory=prod/nginx/*` | 100 GB |
| `app_errors` | `_sourceCategory=prod/app/* (level=error OR level=fatal)` | 1 GB |
| `app_info` | `_sourceCategory=prod/app/* level=info` | 100 GB |
| `app_debug` | `_sourceCategory=prod/app/* (level=debug OR level=trace)` | 300 GB |

`_sourceCategory=prod/waf/*` on Customer B uses query rewriting to scan only `waf_logs` → **200 GB instead of 1.1 TB. A ~5x scan reduction.**

For app errors specifically: `_index=app_errors` scans only 1 GB — a **1100x reduction** vs. Customer A's monolithic default.

---

## CSE / Flex Partition Considerations

On **Flex tier**, data forwarded to Cloud SIEM (`_siemforward=true`) is **exempt from search scan charges**. However, if CSE and non-CSE data share the same partition, a query scoped to that partition still incurs charges for the non-CSE portion.

**Best practice for Flex CSE customers:** Keep CSE-forwarded data in dedicated partitions, separate from non-CSE data. This allows queries scoped to `_index=cse_partition` to be zero-scan-cost.

**Example:**
- Customer A: CDN logs and CSE-forwarded WAF logs share one partition → every CDN query scans 350 GB (50 GB CSE free + 300 GB charged)
- Customer B: CSE logs in separate partition X → `_index=X` query scans 0 GB (all CSE, all free)

---

## Verifying What Data Is in Which Partition

```
// Run a sample query and look at the _view field in message results:
_sourceCategory=prod/myapp

// Or use the partitions admin page:
// Manage Data → Logs → Partitions → check routing expressions

// Or query for top partitions by volume:
_index=sumologic_volume _sourceCategory=sourcecategory_and_tier_volume
| count by _view
| sort _count desc

// Or via MCP tool:
// get_sumo_partitions — lists all partitions with routing expressions
```

---

## MCP Tools Used

- `get_sumo_partitions` — List all partitions with routing expressions and retention
- `explore_log_metadata` — Discover which partitions hold specific log data
- `analyze_data_volume` — Understand volume by source category for partition sizing
- `analyze_search_scan_cost` — Identify which users/queries are scanning expensively
- `run_search_audit_query` — Analyse query patterns to inform partition design

## Related Skills

- [Field Extraction Rules](./admin-field-extraction-rules.md)
- [Indexes and Partitions — User View](./search-indexes-partitions.md)
- [Search Performance Best Practices](./search-performance-best-practices.md)
- [Admin Alerting and Monitoring](./admin-alerting-and-monitoring.md)

## API References

- [Partitions API](https://api.sumologic.com/docs/#tag/partitionManagement)
- [Query Rewriting](https://help.sumologic.com/docs/search/optimize-search-partitions/#what-is-query-rewriting)
- [Data Tiers](https://help.sumologic.com/docs/manage/partitions/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** Sumo Logic Architecture For Log Search Performance (February 2025)
