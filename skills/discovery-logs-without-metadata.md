# Skill: Log Discovery Without Metadata

## Intent

Discover and analyze logs in Sumo Logic when you don't know the source category, partition, or log structure. This is the starting point for users who know a service name (e.g., "cloudtrail", "kubernetes") but don't know where those logs are stored or how they're organized.

## Prerequisites

- Access to Sumo Logic API
- Basic understanding of log metadata concepts (_sourceCategory,_index, _collector)
- Access to data volume index (typically available to all users)

## Context

**Use this skill when:**

- You're new to a Sumo Logic organization and don't know the metadata schema
- You know a service/application name but not where its logs are
- You need to find logs before you can query them
- You're investigating a new use case without prior knowledge

**Don't use this when:**

- You already know the _sourceCategory or_index
- You have access to existing dashboards or searches for your use case
- Someone has shared metadata with you

## Approach

### Phase 1: Metadata Discovery (Fast, No Scan Cost)

#### Step 1.1: Search Data Volume Index

Start with the data volume index to find source categories - this is free and fast.

**Pattern:**

```
_index=sumologic_volume sourceCategory=*{hint}*
| parse regex field=sizeInBytes "\"sourceCategory\"\s*:\s*\"(?<sourceCategory>[^\"]+)\"" multi
| sum(sizeInBytes) as bytes by sourceCategory
| bytes / 1024 / 1024 / 1024 as gbytes
| sort -gbytes
| limit 20
```

**MCP Tool:** `analyze_data_volume`

```json
{
  "dimension": "sourceCategory",
  "filter_pattern": "*cloudtrail*",
  "from_time": "-7d",
  "sort_by": "gbytes",
  "limit": 20
}
```

**Benefits:**

- No scan cost (data volume index is free)
- Shows ingestion volume (helps prioritize)
- Reveals naming conventions used in your org

#### Step 1.2: Discover Partition Mapping

Once you have candidate source categories, find which partitions they're in.

**MCP Tool:** `explore_log_metadata`

```json
{
  "scope": "_sourceCategory=*cloudtrail*",
  "from_time": "-15m",
  "metadata_fields": "_view,_sourceCategory,_collector",
  "max_results": 100
}
```

**Benefits:**

- Maps source categories to partitions (_view)
- Shows collector organization
- Minimal scan (15m window)

#### Step 1.3: Check Search Audit for Prior Queries

See if others have already queried these logs.

**MCP Tool:** `run_search_audit_query`

```json
{
  "query_filter": "*cloudtrail*",
  "from_time": "-30d",
  "user_name": "*"
}
```

**Benefits:**

- Learn from existing queries
- Discover common use cases
- Find experts who work with these logs

### Phase 2: Log Structure Analysis

#### Step 2.1: Sample Raw Logs

Now that you know the metadata, sample actual logs to understand structure.

**Pattern:**

```
_sourceCategory=aws/cloudtrail
| limit 10
```

**MCP Tool:** `search_sumo_logs`

```json
{
  "query": "_sourceCategory=aws/cloudtrail | limit 10",
  "hours_back": 1
}
```

**Analyze:**

- Is it JSON, syslog, or custom format?
- Are fields auto-parsed or do you need parse operators?
- What are the key fields for filtering?

#### Step 2.2: Profile Log Schema with Facets

Discover all available fields and their cardinality.

**MCP Tool:** `profile_log_schema`

```json
{
  "scope": "_sourceCategory=aws/cloudtrail",
  "from_time": "-15m",
  "suggest_candidates": true,
  "min_cardinality": 2,
  "max_cardinality": 1000
}
```

**Returns:**

- Field names and types
- Cardinality (unique value counts)
- Suggestions for fields good for volume breakdown

**Look for:**

- Low cardinality fields (2-20 values): Good for filtering (e.g., eventName, status)
- Medium cardinality (20-1000): Good for aggregation (e.g., user, service)
- High cardinality (>1000): Use with caution in group by (e.g., requestId)

### Phase 3: Use-Case Query Building

#### Step 3.1: Search Query Examples Library

Find pre-built queries from 11,000+ examples in 280+ Sumo Logic apps.

**MCP Tool:** `search_query_examples`

```json
{
  "query": "cloudtrail security failed",
  "max_results": 10
}
```

**Benefits:**

- Learn best practices from published apps
- Find relevant operators for your use case
- Discover query patterns you might not know

#### Step 3.2: Build Your First Query

Combine your discoveries:

```
_index=aws_logs _sourceCategory=aws/cloudtrail
| where eventName = "ConsoleLogin"
| where errorCode != ""
| count by userIdentity_principalId, sourceIPAddress, errorCode
| sort -_count
```

**Structure:**

1. **Scope** (before pipe): Partition + source category + optional keywords
2. **Filters** (where): Narrow to specific events
3. **Aggregation** (count by): Summarize patterns
4. **Sorting/Limiting**: Focus on top results

## Query Patterns

### Metadata Discovery Pattern

```
_index=sumologic_volume sourceCategory=*{hint}*
| parse regex multi for sourceCategory extraction
| aggregate by sourceCategory
| calculate bytes -> GB
| sort by volume descending
```

### Schema Profiling Pattern

```
{scope}
| limit for sampling
| facets for field discovery
| filter by cardinality range
| suggest aggregation candidates
```

### Log Sampling Pattern

```
{scope with partition + sourceCategory}
| optional: where {high-selectivity-filter}
| limit {small number like 10-100}
```

## Examples

### Example 1: Find Kubernetes Logs

**Scenario:** New to org, need to find Kubernetes logs.

**Step 1:** Volume search

```bash
MCP: analyze_data_volume
  dimension: "sourceCategory"
  filter_pattern: "*k8s*"
  from_time: "-7d"
```

**Result:** Finds `kubernetes/prod/pods`, `kubernetes/prod/nodes`

**Step 2:** Discover partition

```bash
MCP: explore_log_metadata
  scope: "_sourceCategory=kubernetes/prod/pods"
  from_time: "-15m"
```

**Result:** Logs are in `_index=prod_kubernetes`

**Step 3:** Profile schema

```bash
MCP: profile_log_schema
  scope: "_index=prod_kubernetes _sourceCategory=kubernetes/prod/pods"
  suggest_candidates: true
```

**Result:** Discover fields: `namespace`, `pod_name`, `container_name`, `level`

**Step 4:** Build query

```
_index=prod_kubernetes _sourceCategory=kubernetes/prod/pods
| where level = "error"
| count by namespace, pod_name
| sort -_count
```

### Example 2: CloudTrail Security Analysis

**Scenario:** Investigate AWS CloudTrail for security events.

**Step 1:** Search audit for prior queries

```bash
MCP: run_search_audit_query
  query_filter: "*cloudtrail*"
  scope_filters: ["query_type=Interactive"]
  from_time: "-30d"
```

**Result:** Find user `security@company.com` has run CloudTrail queries

**Step 2:** Check if CloudTrail app is installed

```bash
MCP: list_installed_apps
  filter_name: "CloudTrail"
```

**Result:** AWS CloudTrail app installed with pre-built dashboards

**Step 3:** Export app to see queries

```bash
MCP: export_installed_apps
```

**Step 4:** Find relevant dashboard queries and adapt

### Example 3: Apache Access Logs - Unknown Format

**Scenario:** Need to query Apache logs, don't know format.

**Step 1:** Find source category

```bash
MCP: analyze_data_volume
  dimension: "sourceCategory"
  filter_pattern: "*apache*"
```

**Result:** `apache/access`, `apache/error`

**Step 2:** Sample logs

```bash
MCP: search_sumo_logs
  query: "_sourceCategory=apache/access | limit 5"
  hours_back: 1
```

**Result:** See log format:

```
192.168.1.1 - - [05/Mar/2026:10:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234
```

**Step 3:** Search for Apache query examples

```bash
MCP: search_query_examples
  query: "apache access status code"
  max_results: 5
```

**Result:** Find parse patterns:

```
| parse "* - - [*] \"* * *\" * *" as ip, datetime, method, url, protocol, status, bytes
```

**Step 4:** Build query

```
_sourceCategory=apache/access
| parse "* - - [*] \"* * *\" * *" as ip, datetime, method, url, protocol, status, bytes
| where status matches "5*"
| count by status, url
| sort -_count
```

## Common Pitfalls

### Pitfall 1: Searching All Data (`*`)

**Problem:** `scope: "*"` scans all data, expensive in Flex/Infrequent tier

**Solution:** Always use data volume index first to find source categories, then scope queries

### Pitfall 2: Long Time Ranges in Discovery

**Problem:** Using `-24h` or `-7d` for schema profiling incurs high scan costs

**Solution:** Use `-15m` for metadata exploration, only extend time range once you have good scope

### Pitfall 3: Ignoring Partitions

**Problem:** Querying by _sourceCategory alone may scan multiple partitions

**Solution:** Always include `_index=` or `_view=` in scope when known

### Pitfall 4: Assuming Auto-Parse

**Problem:** Expecting JSON auto-parse to work on all logs

**Solution:** Sample logs first, use `profile_log_schema` to see what's actually parsed

### Pitfall 5: Not Checking Installed Apps

**Problem:** Building queries from scratch when pre-built app exists

**Solution:** Always check `list_installed_apps` and `export_installed_apps` first

## Optimization Tips

### Tip 1: Use Estimated Usage API Before Querying

Before running a broad discovery query, estimate scan volume:

```bash
MCP: get_estimated_log_search_usage
  query: "_sourceCategory=*cloudtrail*"
  from_time: "-24h"
  by_view: true
```

If estimated scan > 100GB, narrow the scope or shorten time range.

### Tip 2: Leverage Query Examples for Speed

Instead of trial-and-error:

```bash
MCP: search_query_examples
  query: "{service_name} {use_case}"
  max_results: 10
```

Example: `"kubernetes pod errors"` returns proven query patterns

### Tip 3: Build Incrementally

1. Start with metadata discovery (free)
2. Sample small time window (-15m)
3. Profile schema to understand fields
4. Test query on -15m before extending to -24h or -7d

### Tip 4: Reuse Search Audit Insights

Don't reinvent the wheel:

```bash
MCP: run_search_audit_query
  scope_filters: ["query=*{service}*"]
  group_by: "user_query"
  from_time: "-90d"
```

See what queries others have successfully run.

## Related Skills

- [Query Optimization](./search-optimize-queries.md) - Make queries faster and cheaper
- [Search Cost Analysis](./cost-analyze-search-costs.md) - Understand scan costs
- [Content Library Navigation](./content-library-navigation.md) - Find existing dashboards

## MCP Tools Used

- `analyze_data_volume` - Find source categories by volume
- `explore_log_metadata` - Map metadata to partitions
- `profile_log_schema` - Discover fields and cardinality
- `search_sumo_logs` - Sample logs
- `search_query_examples` - Find example queries
- `run_search_audit_query` - See what others have queried
- `list_installed_apps` - Check for pre-built apps
- `get_estimated_log_search_usage` - Estimate scan costs

## API References

- [Data Volume Index](https://help.sumologic.com/docs/manage/ingestion-volume/data-volume-index/)
- [Search Query Language](https://help.sumologic.com/docs/search/)
- [Keyword Expressions](https://help.sumologic.com/docs/search/get-started-with-search/build-search/keyword-search-expressions/)
- [Partition Routing](https://help.sumologic.com/docs/search/optimize-search-partitions/)

---

**Version:** 1.0.0
**Domain:** Discovery
**Complexity:** Beginner to Intermediate
**Estimated Time:** 10-30 minutes for complete discovery workflow
