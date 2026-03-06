# Skill: Analyze Search Scan Costs

## Intent

Analyze and optimize search costs in Sumo Logic Flex and Infrequent Data Tier accounts where you pay per search based on data scanned. Identify expensive queries, users consuming most scan volume, and opportunities to reduce costs.

## Prerequisites

- Sumo Logic Flex or Infrequent Data Tier account
- Access to Search Audit Index (`_view=sumologic_search_usage_per_query`)
- Understanding of your organization type (Flex vs Tiered Infrequent)
- Basic knowledge of tier vs metering breakdown differences

## Context

**Use this skill when:**

- You're on Flex or Infrequent tier with pay-per-search pricing
- Monthly search costs are unexpectedly high
- You need to identify which users/queries are driving costs
- Optimizing budgets and setting scan quotas

**Don't use this when:**

- You're on legacy Continuous tier (flat pricing)
- You only need query performance metrics (use search audit without cost analysis)
- Looking for ingestion costs (use data volume analysis instead)

**Tier vs Metering Breakdown:**

- **Tier breakdown** (for Tiered Infrequent customers): Continuous, Frequent, Infrequent
- **Metering breakdown** (for Flex customers): Flex (billable), FlexSecurity (non-billable), Continuous, Frequent, etc.
- **CRITICAL:** Flex orgs MUST use metering breakdown. Tier breakdown returns near-zero scan data.

## Approach

### Step 1: Detect Organization Type (Auto)

The `analyze_search_scan_cost` tool auto-detects Flex vs Tiered via account status API.

**MCP Tool:** `analyze_search_scan_cost` with `breakdown_type='auto'` (default)

```json
{
  "from_time": "-24h",
  "breakdown_type": "auto",
  "group_by": "user"
}
```

**Auto-Detection Logic:**

- Calls account status API
- Checks plan type for "Flex" keyword
- Returns `detected_org_type: "Flex"` or `"Tiered"` in response
- Selects appropriate breakdown automatically

**Benefits:**

- No manual configuration needed
- Prevents using wrong breakdown type
- Warning if mismatch detected

### Step 2: Identify Top Users by Scan Volume

#### For All Organizations (Auto-Detect)

```json
{
  "from_time": "-7d",
  "breakdown_type": "auto",
  "group_by": "user",
  "sort_by": "billable_scan_gb",
  "limit": 20
}
```

**Returns (Flex):**

```json
{
  "user_name": "analyst@company.com",
  "queries": 487,
  "total_scan_gb": 1234.56,
  "billable_scan_gb": 1100.00,
  "billable_scan_tb": 1.10,
  "non_billable_scan_gb": 134.56,
  "metering_breakdown_gb": {
    "Flex": 1100.00,
    "FlexSecurity": 134.56
  },
  "detected_org_type": "Flex"
}
```

**Returns (Tiered Infrequent):**

```json
{
  "user_name": "analyst@company.com",
  "queries": 487,
  "total_scan_gb": 856.34,
  "scan_credits": 13.70,
  "credits_per_query": 0.028,
  "tier_breakdown_gb": {
    "Continuous": 100.00,
    "Frequent": 50.00,
    "Infrequent": 706.34
  },
  "detected_org_type": "Tiered"
}
```

**Analysis:**

- **Flex:** Focus on `billable_scan_tb` (TB is primary unit)
- **Tiered:** Focus on `scan_credits` (0.016 cr/GB = 16 cr/TB standard rate)
- Look for users with high scan per query (divide total by queries)

### Step 3: Identify Expensive Queries

#### Group by Query Text

```json
{
  "from_time": "-7d",
  "breakdown_type": "auto",
  "group_by": "user_query",
  "sort_by": "billable_scan_gb",
  "min_scan_gb": 10,
  "limit": 50
}
```

**Pattern to Look For:**

- Queries with broad scope (e.g., `*` or no partition filter)
- Long time ranges (-30d or more)
- No aggregation (raw message queries)
- Repeated similar queries (query variations)

**Example Result:**

```json
{
  "user_name": "analyst@company.com",
  "query": "* | where status_code = 500",
  "queries": 45,
  "billable_scan_tb": 5.23,
  "scope": "*",
  "analytics_tier": "Flex"
}
```

**Red Flags:**

- `scope: "*"` - Scanning all data
- No partition in scope
- High query count with same pattern (automation gone wrong?)

### Step 4: Analyze by Scope (Partition/View)

#### Group by Scope + Query

```json
{
  "from_time": "-7d",
  "breakdown_type": "auto",
  "group_by": "user_scope_query",
  "include_scope_parsing": true,
  "sort_by": "billable_scan_gb",
  "limit": 100
}
```

**Returns:**

```json
{
  "user_name": "analyst@company.com",
  "scope": "_index=prod_logs",
  "query": "error | count by service",
  "queries": 234,
  "billable_scan_tb": 2.15
}
```

**Benefits:**

- See if users are scoping queries properly
- Identify missing partition filters
- Compare scan volume by partition

### Step 5: Analyze Dashboard/Scheduled Search Costs

#### Group by Content

```json
{
  "from_time": "-30d",
  "breakdown_type": "auto",
  "query_type": "Scheduled",
  "group_by": "content",
  "sort_by": "billable_scan_gb",
  "limit": 30
}
```

**Use Cases:**

- Find expensive dashboards that auto-refresh
- Identify scheduled searches needing optimization
- Audit automated queries

## Query Patterns

### Search Audit Cost Query (Flex - Metering)

```
_view=sumologic_search_usage_per_query
| json field=scanned_bytes_breakdown_by_metering_type "$['Flex']" as flex_bytes nodrop
| json field=scanned_bytes_breakdown_by_metering_type "$['FlexSecurity']" as flexsec_bytes nodrop
| 0 as billable_bytes, 0 as non_billable_bytes
| if(!isNull(flex_bytes), flex_bytes, 0) as billable_bytes
| if(!isNull(flexsec_bytes), flexsec_bytes, 0) + non_billable_bytes as non_billable_bytes
| billable_bytes + non_billable_bytes as total_bytes
| sum(billable_bytes) as billable_bytes_sum by user_name
| billable_bytes_sum / 1024 / 1024 / 1024 as billable_gb
| billable_gb / 1024 as billable_tb
| sort -billable_tb
```

### Search Audit Cost Query (Tiered Infrequent)

```
_view=sumologic_search_usage_per_query
| json field=scanned_bytes_breakdown "$['Infrequent']" as inf_bytes nodrop
| if(!isNull(inf_bytes), inf_bytes, 0) as inf_bytes
| sum(inf_bytes) as inf_bytes_sum by user_name
| inf_bytes_sum / 1024 / 1024 / 1024 as inf_gb
| inf_gb * 0.016 as scan_credits
| count as queries by user_name, scan_credits, inf_gb
| scan_credits / queries as credits_per_query
| sort -scan_credits
```

### Scope Extraction Pattern

```
| parse regex field=query "^(?<scope>[^|]+)" nodrop
| where scope matches "*_index=*" OR scope matches "*_view=*"
| scope as has_partition
```

## Examples

### Example 1: Flex Org - Find Top Scan Users

**Scenario:** Flex customer, need to identify top 10 users by billable scan in last month.

```bash
MCP: analyze_search_scan_cost
  from_time: "-30d"
  breakdown_type: "auto"  # Will detect Flex
  group_by: "user"
  sort_by: "billable_scan_gb"
  limit: 10
```

**Result:**

```
1. analyst@company.com: 23.4 TB billable (487 queries, 48 GB/query avg)
2. data-engineer@company.com: 18.7 TB billable (1234 queries, 15 GB/query avg)
3. dashboard-service@company.com: 15.2 TB billable (8900 queries, 1.7 GB/query avg)
```

**Analysis:**

- User 1: High scan per query (48 GB) - investigate queries
- User 3: High query count (8900) - likely automated dashboard, optimize refresh rate

**Next Steps:**

- Drill into <analyst@company.com> queries:

  ```json
  {
    "user_name": "analyst@company.com",
    "group_by": "user_query",
    "from_time": "-30d"
  }
  ```

### Example 2: Tiered Infrequent - Expensive Queries

**Scenario:** Infrequent tier customer, find queries costing >1 credit each.

```bash
MCP: analyze_search_scan_cost
  from_time: "-7d"
  breakdown_type: "tier"
  analytics_tier_filter: "*infrequent*"
  group_by: "user_query"
  sort_by: "scan_credits"
  limit: 20
```

**Result:**

```
Query: "* | where error" by user@company.com
- Queries: 12
- Scan: 1875 GB Infrequent
- Credits: 30.00 (2.5 cr/query)
- Scope: * (no partition!)
```

**Optimization:**
Add partition scope:

```
Before: * | where error
After:  _index=prod_logs error | where ...
Scan:   1875 GB → 45 GB (41x reduction!)
```

### Example 3: Dashboard Cost Analysis

**Scenario:** Identify most expensive dashboards.

```bash
MCP: analyze_search_scan_cost
  from_time: "-30d"
  query_type: "Scheduled"
  group_by: "content"
  sort_by: "billable_scan_gb"
  limit: 20
```

**Result:**

```
Dashboard: "Production Monitoring Overview"
- Queries: 4320 (every 10 min for 30 days)
- Billable scan: 5.2 TB
- Cost driver: 12 panels, each queries -24h
```

**Optimization Options:**

1. Reduce refresh rate (10m → 30m): 4320 → 1440 queries
2. Reduce time range (-24h → -6h on some panels)
3. Use scheduled searches to pre-aggregate data
4. Move high-volume panels to Continuous tier partition

### Example 4: Find Queries Missing Partition Scope

**Scenario:** Audit queries to find those not using partitions.

```bash
MCP: analyze_search_scan_cost
  from_time: "-7d"
  group_by: "user_scope_query"
  include_scope_parsing: true
  sort_by: "billable_scan_gb"
```

**Filter results where `scope` does NOT contain `_index=` or `_view=`:

```
# High-cost queries without partition:
1. scope: "error", scan: 234 GB
2. scope: "_sourceCategory=prod/app", scan: 189 GB
3. scope: "*", scan: 456 GB
```

**Optimization:**
Work with users to add partition scoping.

## Common Pitfalls

### Pitfall 1: Using Tier Breakdown on Flex Org

**Problem:** `breakdown_type='tier'` on Flex org returns near-zero scan data

**Solution:** Always use `'auto'` or `'metering'` for Flex customers

**Detection:**
Tool warns if tier breakdown used on suspected Flex org:

```json
{
  "warning": "Detected Flex organization but using tier breakdown. Consider using breakdown_type='metering'"
}
```

### Pitfall 2: Not Filtering to Billable Data

**Problem:** Analyzing all scans including FlexSecurity (non-billable)

**Solution:** Focus on `billable_scan_gb` field, not `total_scan_gb`

### Pitfall 3: Ignoring Credits Per Query Metric

**Problem:** Only looking at total scan, not scan efficiency

**Solution:** Calculate `scan_gb / queries` to find inefficient query patterns

### Pitfall 4: Short Time Range for Analysis

**Problem:** Analyzing only 24h might miss periodic expensive queries

**Solution:** Use 7d or 30d time range for comprehensive analysis

### Pitfall 5: Not Correlating with Users

**Problem:** Finding expensive queries but not knowing who runs them

**Solution:** Always include `user_name` in group_by or start with user-level analysis

## Optimization Strategies

### Strategy 1: Add Partition Scoping

**Before:**

```
_sourceCategory=prod/app error | count by service
```

**After:**

```
_index=prod_logs _sourceCategory=prod/app error | count by service
```

**Impact:** Can reduce scan 10x-100x depending on partition size

### Strategy 2: Reduce Dashboard Refresh Rates

**Before:** Every 5 minutes (288 queries/day/panel)
**After:** Every 30 minutes (48 queries/day/panel)
**Impact:** 6x reduction in query count

### Strategy 3: Use Scheduled Searches for Pre-Aggregation

**Before:** Dashboard queries raw logs every refresh
**After:** Scheduled search runs hourly, dashboard queries results index
**Impact:** Query cost moves to scheduled search (predictable), dashboard becomes cheap

### Strategy 4: Optimize Time Ranges

**Before:** All panels query -24h
**After:**

- Summary panels: -1h (refreshed often)
- Trend panels: -24h (refreshed less often)
- Historical panels: -7d (manual refresh only)

**Impact:** Reduce time range by 24x on frequently refreshed panels

### Strategy 5: Move Hot Data to Continuous Tier

**Before:** High-query-frequency data in Flex/Infrequent (pay per scan)
**After:** Hot data in Continuous tier partition (flat rate)
**Impact:** Predictable costs for high-query-volume data

## Advanced Filtering

### Filter by Analytics Tier

```json
{
  "analytics_tier_filter": "*flex*",
  "group_by": "user_query"
}
```

### Filter by User Pattern

```json
{
  "user_name": "*@company.com",
  "exclude_service_accounts": true
}
```

### Filter by Query Pattern (Regex)

```bash
MCP: run_search_audit_query
  scope_filters: ["query=*count by*"]
  where_filters: ["execution_duration_ms > 60000"]
```

Finds slow aggregate queries.

## Cost Estimation

### Flex Pricing (Example - Verify with Contract)

- Typical range: $0.016 - $0.02 per GB scanned
- 1 TB scan ≈ $16-20 USD

**Example Calculation:**

- User scans 10 TB billable in a month
- At $0.018/GB: 10,000 GB × $0.018 = $180

### Infrequent Tier Pricing (Standard Rates)

- 0.4 credits per GB (0.016 credits × 25)
- 1 TB = 400 credits
- Credits cost varies by contract

**Example Calculation:**

- User scans 5 TB Infrequent in a month
- 5,000 GB × 0.4 cr/GB = 2,000 credits

## Related Skills

- [Query Optimization](./search-optimize-queries.md) - Reduce scan volume
- [Log Discovery](./discovery-logs-without-metadata.md) - Find right partitions
- [Data Volume Analysis](./cost-analyze-data-volume.md) - Analyze ingestion costs

## MCP Tools Used

- `analyze_search_scan_cost` - Primary tool for scan cost analysis
- `run_search_audit_query` - Low-level search audit queries
- `get_account_status` - Detect org type (Flex vs Tiered)
- `get_estimated_log_search_usage` - Estimate scan before querying

## API References

- [Search Audit Index](https://help.sumologic.com/docs/manage/security/audit-indexes/search-audit-index/)
- [Infrequent Data Tier](https://help.sumologic.com/docs/manage/partitions/data-tiers/infrequent-data-tier/)
- [Flex Pricing](https://help.sumologic.com/docs/manage/partitions/flex/)
- [Query Optimization](https://help.sumologic.com/docs/search/optimize-search-performance/)

---

**Version:** 1.0.0
**Domain:** Cost Analysis
**Complexity:** Intermediate to Advanced
**Estimated Time:** 30-60 minutes for comprehensive analysis
**ROI:** High - Can reduce search costs by 50-90% through optimization
