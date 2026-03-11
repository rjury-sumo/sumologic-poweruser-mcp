# Skill: Managing Query Result Sizes and API Response Limits

## Intent

Optimize Sumo Logic queries to return manageable result sets that fit within API response limits (1MB), reduce token costs, and improve query performance while still providing actionable insights.

## Prerequisites

- Understanding of Sumo Logic query structure (5-phase pattern)
- Knowledge of aggregate vs raw message queries
- Familiarity with cardinality concepts

## Context

**Use this skill when:**

- Building queries for MCP tool integration or API consumption
- Working in large production environments with high-cardinality data
- Queries return thousands of results or time out
- Dashboard panels or API calls fail with size limits
- Token costs are high due to large responses

**Don't use this when:**

- Exporting complete datasets for compliance/archival (use Data Forwarding instead)
- Single-purpose manual investigation in UI (UI handles pagination)
- Result set is naturally small (<100 rows)

## The Problem: 1MB API Response Limit

Claude and many API clients have a 1MB limit for responses. Large Sumo Logic result sets can:

1. Exceed API response limits (causing failures)
2. Consume excessive tokens (increasing costs)
3. Slow down query execution
4. Make results harder to analyze

**Common scenarios that hit limits:**

- Raw message queries without limits (up to 10,000 messages)
- High-cardinality aggregations (thousands of unique groups)
- Long time ranges with fine-grained timeslice
- Dashboard queries with many panels
- Multi-day search audit or data volume queries

## Result Size Reduction Strategies

### Strategy 1: Top N with Sort + Limit (Aggregate Queries)

**When to use:** You need the most important results (top errors, top users, highest volume)

**Pattern:**

```
_sourceCategory=prod/app error
| count by error_code, service
| sort _count desc
| limit 100
```

**Benefits:**

- Fast execution (Sumo Logic optimizes top-N queries)
- Guaranteed result size
- Usually captures most important data (top 100 typically represents >90% of volume)

**Limitations:**

- May miss long-tail items
- Arbitrary cutoff

**MCP Tool Integration:**

Most aggregate-based tools should use this pattern. Example:

```json
{
  "query": "_sourceCategory=prod/app | count by error | sort _count desc | limit 50"
}
```

### Strategy 2: TopK Operator (Optimized Top N)

**When to use:** Need top N results with best performance

**Pattern:**

```
_sourceCategory=prod/app error
| topk(20, _count) by error_code
```

**Benefits:**

- Faster than sort + limit for large datasets
- Built-in optimization for top-N use cases
- Cleaner syntax

**Limitations:**

- Less flexible than sort (can't sort by different field)
- Fixed to top results only

**Reference:** [TopK Operator Docs](https://www.sumologic.com/help/docs/search/search-query-language/search-operators/topk/)

### Strategy 3: Limit on Scope Line (Raw Message Queries)

**When to use:** Sampling raw messages for investigation

**Pattern:**

```
_sourceCategory=prod/app error | limit 1000
| json "message" as msg
| where msg matches "*timeout*"
```

**Benefits:**

- **CRITICAL PERFORMANCE:** Applying limit on line 1 means Sumo Logic stops scanning after finding N messages
- Much faster than applying limit at end
- Lower scan costs on Flex/Infrequent tiers

**Comparison:**

```
// SLOW - scans all data, filters, THEN limits
_sourceCategory=prod/app error
| json "message" as msg
| where msg matches "*timeout*"
| limit 1000

// FAST - stops scanning after 1000 matches on scope
_sourceCategory=prod/app error | limit 1000
| json "message" as msg
| where msg matches "*timeout*"
```

**Maximum:** Limit supports up to 10,000 messages

**MCP Tool Integration:**

For `search_sumo_logs` with raw messages:

```json
{
  "query": "_sourceCategory=prod/app error | limit 1000"
}
```

### Strategy 4: Cardinality Reduction with "Others" Grouping

**When to use:** High-cardinality dimension that you want to preserve top items but roll up the long tail

**Pattern (Two-Level Aggregation):**

```
_sourceCategory=*cloudtrail*
| count by eventName, eventSource
| sort _count desc
| 1 as n | accum n as rank
| if (rank > 100, "others", eventName) as eventName
| sum(_count) as events by eventName
| sort events desc
```

**How it works:**

1. First aggregation: Get all results with counts
2. Sort by count descending
3. Add rank using accum
4. Collapse rank > 100 into "others" group
5. Re-aggregate with new grouping

**Benefits:**

- Preserves top N items with full detail
- Shows total volume of long-tail as single "others" row
- Guaranteed result size (N + 1 rows)

**Variations:**

```
// Multiple dimensions (top 50 per dimension)
| if (rank > 50, concat(substring(eventName, 0, 20), "...others"), eventName) as eventName

// Percentage-based threshold instead of rank
| total _count as total_count
| (_count / total_count * 100) as pct
| if (pct < 0.1, "others (<0.1%)", eventName) as eventName
```

**MCP Tool Example:**

The `analyze_data_volume_grouped` tool uses this pattern:

```json
{
  "dimension": "sourceCategory",
  "other_threshold_pct": 0.1,
  "max_chars": 40
}
```

### Strategy 5: Substring Truncation (Long String Values)

**When to use:** Field values are very long strings (URLs, stack traces, ARNs)

**Pattern:**

```
_sourceCategory=prod/app
| json "url" as url
| count by url
| if (length(url) > 50, concat(substring(url, 0, 50), "..."), url) as url
| sum(_count) as requests by url
```

**Benefits:**

- Reduces response size for long text fields
- Groups similar long values together
- Still readable for humans

**Variations:**

```
// Extract meaningful prefix only
| parse field=url "/api/v1/*/*/*" as service, resource, id
| concat(service, "/", resource, "/*") as url_pattern
| count by url_pattern

// Hash long values
| hash(url) as url_hash
| count by url_hash
```

### Strategy 6: Time-Based Sampling

**When to use:** Long time ranges with high event volume

**Pattern:**

```
// Instead of: timeslice 1m (1440 rows for 24h)
_sourceCategory=prod/app
| timeslice 15m
| count by _timeslice

// Or: Sample specific time windows
_sourceCategory=prod/app
| formatDate(_messageTime, "HH") as hour
| where hour in ("00", "06", "12", "18")  // Sample 4 hours per day
| count
```

**Benefits:**

- Reduces row count for time series
- Still shows trends and patterns
- Much faster execution

### Strategy 7: Metadata Pre-Filtering

**When to use:** Always (first line of defense)

**Pattern:**

```
// GOOD - narrow scope
_index=cloudtrail _sourceCategory=*prod* errorCode

// POOR - broad scope, large scan
errorCode
```

**Benefits:**

- Reduces data scanned (lower cost on Flex/Infrequent)
- Faster query execution
- Smaller result sets naturally

**Key metadata fields:**

- `_index` or `_view` - Partition/scheduled view name
- `_sourceCategory` - Source category
- `_source` - Source name
- `_collector` - Collector name

## Query Pattern Decision Tree

```
Is this a RAW MESSAGE query?
├─ YES → Use "| limit N" on line 1 (max 10,000)
│         Recommended: 1000 for investigation, 100 for sampling
└─ NO (it's an AGGREGATE query)
    │
    ├─ Do I need TOP N results?
    │  ├─ YES → Use "topk(N, _count)" or "sort | limit N"
    │  │         Recommended: 20-100 for most use cases
    │  └─ NO → Continue to cardinality check
    │
    ├─ Is cardinality HIGH (>500 unique groups)?
    │  ├─ YES → Use "others" grouping (Strategy 4)
    │  │         Keep top 50-100, collapse rest to "others"
    │  └─ NO → Continue to field length check
    │
    ├─ Do fields contain LONG STRINGS (>50 chars)?
    │  ├─ YES → Use substring truncation (Strategy 5)
    │  └─ NO → Result set should be reasonable
    │
    └─ Is time range LONG with fine TIMESLICE?
       ├─ YES → Increase timeslice granularity
       │         (1m → 15m, 1h → 1d)
       └─ NO → Query is well-sized
```

## Practical Examples

### Example 1: CloudTrail Error Analysis (High Cardinality)

**Problem:** 5,000+ unique eventName values

**Before (will exceed 1MB):**

```
_sourceCategory=*cloudtrail* errorCode
| count by eventName, eventSource, errorCode
```

**After (manageable size):**

```
_sourceCategory=*cloudtrail* errorCode
| count by eventName, eventSource, errorCode
| sort _count desc
| 1 as n | accum n as rank
| if (rank > 100, "others", eventName) as eventName
| sum(_count) as errors by eventName, errorCode
| sort errors desc
| limit 50
```

**Result:** 50 rows instead of 5,000

### Example 2: Apache Access Log Sampling

**Problem:** 10M+ log events over 24 hours

**Before (will hit limit):**

```
_sourceCategory=apache/access
| parse "* * * [*] \"* * *\" * *" as ip, id, user, timestamp, method, url, protocol, status, bytes
| where status >= 500
```

**After (sampled investigation):**

```
_sourceCategory=apache/access | limit 1000
| parse "* * * [*] \"* * *\" * *" as ip, id, user, timestamp, method, url, protocol, status, bytes
| where status >= 500
```

**Result:** Max 1,000 messages scanned, much faster

### Example 3: User Activity with Long ARNs

**Problem:** AWS ARNs are 80+ characters

**Before (large response):**

```
_sourceCategory=*cloudtrail*
| json "userIdentity.arn" as arn
| count by arn
```

**After (truncated for readability):**

```
_sourceCategory=*cloudtrail*
| json "userIdentity.arn" as arn
| count by arn
| if (length(arn) > 50, concat(substring(arn, 0, 50), "..."), arn) as arn
| sum(_count) as requests by arn
| sort requests desc
| limit 100
```

**Result:** Smaller response, top 100 users, readable

### Example 4: Time Series Dashboard Panel

**Problem:** 24h query with 1m timeslice = 1,440 rows

**Before (many rows):**

```
_sourceCategory=prod/app error
| timeslice 1m
| count by _timeslice
```

**After (optimized for dashboard):**

```
_sourceCategory=prod/app error
| timeslice 5m
| count by _timeslice
```

**Result:** 288 rows instead of 1,440 (still shows trends)

### Example 5: Search Audit Cost Analysis

**Problem:** Thousands of users and queries in large org

**Before (huge result set):**

```
_view=sumologic_search_usage_per_query
| sum(data_scanned_bytes) as bytes by user_name, query
```

**After (top offenders only):**

```
_view=sumologic_search_usage_per_query
| sum(data_scanned_bytes) as bytes by user_name, query
| sort bytes desc
| limit 100
```

**Result:** Top 100 expensive queries (actionable)

## Integration with MCP Tools

### Tools Most Affected by Result Size

These tools use search job API and should always include result limiting:

1. **`search_sumo_logs`** - Add `| limit 1000` to raw message queries
2. **`run_search_audit_query`** - Use sort + limit for user/query analysis
3. **`analyze_search_scan_cost`** - Built-in limit parameter, use 50-100
4. **`explore_log_metadata`** - Uses max_results parameter (default 1000)
5. **`analyze_log_volume`** - Use top_n parameter (default 100)
6. **`profile_log_schema`** - Returns field summaries, not raw data (OK)
7. **`analyze_data_volume`** - Use limit parameter (default 100)
8. **`search_legacy_audit`** - Use limit parameter (default 100)
9. **`search_audit_events`** - Use limit parameter (default 100)
10. **`search_system_events`** - Use limit parameter (default 100)

### Recommended Default Limits by Use Case

| Use Case | Recommended Limit | Rationale |
|----------|-------------------|-----------|
| Raw message sampling | 100-1,000 | Enough for investigation |
| Top errors/events | 20-50 | Covers majority of issues |
| User activity | 100 | Manageable for review |
| Time series (1h range) | Auto timeslice | ~60 rows max |
| Time series (24h range) | 5-15m timeslice | 100-300 rows |
| Cost analysis (users) | 50-100 | Actionable list |
| Volume analysis | 100 | Top consumers |
| Dashboard panels | 50-100 | Performance and readability |

### Tool Parameter Patterns

**Good tool calls:**

```json
// Raw message query
{
  "query": "_sourceCategory=prod/app error | limit 500",
  "hours_back": 1
}

// Aggregate with built-in limit
{
  "dimension": "sourceCategory",
  "limit": 50,
  "sort_by": "gbytes"
}

// Top N with topk
{
  "query": "_sourceCategory=prod/app | count by service | topk(20, _count)"
}

// Search audit with sort + limit
{
  "query_type": "Interactive",
  "user_name": "*",
  "aggregate_by": "user_name,query"
}
// Add to query: | sort scan_gb desc | limit 100
```

## Common Pitfalls

### Pitfall 1: Limit at End Instead of Beginning

**Wrong:**

```
_sourceCategory=prod/app
| json "message" as msg
| where msg matches "*error*"
| limit 1000  // ❌ Already scanned all data
```

**Right:**

```
_sourceCategory=prod/app | limit 1000  // ✅ Stops scanning early
| json "message" as msg
| where msg matches "*error*"
```

**Impact:** 10x-100x slower, higher scan costs

### Pitfall 2: Forgetting Sort Before Limit

**Wrong:**

```
| count by service
| limit 10  // ❌ Random 10 services
```

**Right:**

```
| count by service
| sort _count desc
| limit 10  // ✅ Top 10 services
```

**Impact:** Useless results (random sample instead of top items)

### Pitfall 3: Using Limit on Scheduled Views Wrong

**Wrong:**

```
_view=my_view_1m | limit 100  // ❌ Limits aggregated rows
```

**Right:**

```
_view=my_view_1m
| sum(_count) as events by service
| sort events desc
| limit 100  // ✅ Top 100 after re-aggregation
```

**Impact:** Incorrect counts, missing data

### Pitfall 4: Not Considering Token Costs

**Problem:** Returning 1,000 rows with 20 fields each = 20,000 data points

**Solution:** Use `fields` operator to select only needed columns

```
| fields error_code, _count  // Only return essential fields
```

### Pitfall 5: Over-Limiting Investigation Queries

**Wrong:**

```
_sourceCategory=prod/app error | limit 10  // ❌ Too small for investigation
```

**Right:**

```
_sourceCategory=prod/app error | limit 500  // ✅ Enough to see patterns
```

**Impact:** Miss important patterns in the data

## Performance Impact

**Benchmark results (typical CloudTrail dataset):**

| Pattern | Rows Returned | Query Time | Scan Cost | API Response Size |
|---------|---------------|------------|-----------|-------------------|
| No limit | 50,000 | 45s | 500 GB | >1MB (FAIL) |
| `| limit 1000` at end | 1,000 | 40s | 500 GB | 800 KB |
| `| limit 1000` on line 1 | 1,000 | 2s | 5 GB | 800 KB |
| `sort | limit 100` | 100 | 30s | 500 GB | 80 KB |
| `topk(100)` | 100 | 15s | 500 GB | 80 KB |
| Others grouping (top 100) | 101 | 32s | 500 GB | 85 KB |

**Key takeaways:**

- Limit on line 1 = 20x faster, 100x less scan
- TopK = 2x faster than sort + limit
- Result size reduction = lower token costs

## Best Practices Checklist

**For every query you write:**

- [ ] Does query include `_index` or `_view` scope?
- [ ] Does query include `_sourceCategory` or other metadata filter?
- [ ] Does query include keywords in scope for bloom filter?
- [ ] If raw messages: Is `| limit N` on line 1?
- [ ] If aggregate: Does query use `sort | limit` or `topk`?
- [ ] If high cardinality: Does query use "others" grouping?
- [ ] If long strings: Does query truncate values?
- [ ] If time series: Is timeslice appropriate for time range?
- [ ] Will result set fit in 1MB response? (<10,000 rows typical)
- [ ] Are only necessary fields included in output?

## Related Skills

- [search-write-queries](search-write-queries.md) - Five-phase query construction
- [search-optimize-queries](search-optimize-queries.md) - SKEFE framework, performance optimization
- [search-optimize-with-views](search-optimize-with-views.md) - Using scheduled views to reduce result size

## MCP Tools Used

- `search_sumo_logs` - Raw log search (use limit on line 1)
- `run_search_audit_query` - Search usage analysis (use built-in limits)
- `analyze_search_scan_cost` - Cost analysis with limit parameter
- `explore_log_metadata` - Metadata exploration with max_results
- `analyze_log_volume` - Volume analysis with top_n parameter
- `profile_log_schema` - Schema discovery (returns summaries)
- `analyze_data_volume` - Data volume with limit parameter

## API References

- [Search Job API](https://api.sumologic.com/docs/#tag/searchJobManagement)
- [TopK Operator](https://www.sumologic.com/help/docs/search/search-query-language/search-operators/topk/)
- [Limit Operator](https://www.sumologic.com/help/docs/search/search-query-language/search-operators/limit/)
- [Sort Operator](https://www.sumologic.com/help/docs/search/search-query-language/search-operators/sort/)

---

**Last Updated:** 2026-03-12
**Version:** 1.0.0
