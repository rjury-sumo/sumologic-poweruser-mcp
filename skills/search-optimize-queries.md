# Skill: Query Optimization for Performance and Cost

## Intent
Build efficient Sumo Logic queries that execute quickly, scan minimal data, and minimize costs in Flex/Infrequent tier environments. Transform slow, expensive queries into fast, cost-effective ones.

## Prerequisites
- Basic knowledge of Sumo Logic query language
- Understanding of partition/view concepts
- Access to search logs and audit data
- Familiarity with your log schema

## Context
**Use this skill when:**
- Queries are running slowly (>60 seconds)
- Search costs are high in Flex/Infrequent tier
- Building new queries from scratch
- Optimizing existing dashboards or searches
- Query times out or hits memory limits

**Optimization Priorities:**
1. **Correctness** - Query returns accurate results
2. **Cost** - Minimize data scanned (Flex/Infrequent tier)
3. **Speed** - Fast execution for better UX
4. **Maintainability** - Clear, understandable syntax

## Approach

### Phase 1: Scope Optimization (Before the Pipe)

The scope determines which data is scanned. Well-crafted scopes can reduce scan volume by 10x-1000x.

#### Rule 1: Always Include Partition (_index or _view)
**Bad:**
```
_sourceCategory=prod/app error
```

**Good:**
```
_index=prod_logs _sourceCategory=prod/app error
```

**Why:**
- Directs query to specific partition
- Avoids scanning other partitions
- Can reduce scan from TBs to GBs

**How to Find Partition:**
```bash
MCP: explore_log_metadata
  scope: "_sourceCategory=prod/app"
  from_time: "-15m"
  metadata_fields: "_view,_sourceCategory"
```

#### Rule 2: Add Keyword Expressions for Bloom Filters

Keyword expressions in scope are processed by backend bloom filters for extremely fast pre-filtering. This technique can reduce scan volume by 10x-1000x by eliminating log blocks that don't contain your keywords.

**Bad (filters after pipe):**
```
_index=prod_logs _sourceCategory=prod/app
| json "status_code" as status_code
| where status_code = 500
```

**Good Option 1 (indexed field with wildcard):**
```
_index=prod_logs _sourceCategory=prod/app status_code=5*
| json "status_code" as status_code
| where status_code = 500
```

**Good Option 2 (high-selectivity keyword):**
```
_index=prod_logs _sourceCategory=prod/app 500
| json "status_code" as status_code
| where status_code = 500
```

**Why Option 2 Works:**
- `500` is an unusual, highly selective string
- Bloom filter eliminates blocks without "500" anywhere in the event
- May include some false positives (e.g., "user_id=50012"), but the post-pipe `where` filter handles exact matching
- Massive performance gain from smaller initial result set

**Advanced Technique 1: Push-Down Optimization**

The query engine automatically does this for some `where` filters, but you can be explicit:

**Automatic Push-Down:**
```
_index=prod_logs _sourceCategory=prod/app
| where foo = "bar"
```
Engine may add "bar" as keyword automatically.

**Explicit Push-Down (more reliable):**
```
_index=prod_logs _sourceCategory=prod/app bar
| json "foo" as foo
| where foo = "bar"
```

**Advanced Technique 2: Selective Keywords for Optional Fields**

When a field only exists in a small subset of events:

**Inefficient:**
```
_sourceCategory=*cloudtrail*
| json "errorCode" as errorCode
| where errorCode = "AccessDenied"
```
Scans all CloudTrail events.

**Efficient:**
```
_sourceCategory=*cloudtrail* errorcode
| json "errorCode" as errorCode
| where errorCode = "AccessDenied"
```
Only scans events containing the string "errorcode" (field is only in error events).

**Advanced Technique 3: Extract Keywords from Regex/Matches**

When using `where matches` with patterns, extract literal strings:

**Inefficient:**
```
_index=prod_logs
| json "url" as url
| where url matches "*/foo/bar/*"
```

**Efficient:**
```
_index=prod_logs foo bar
| json "url" as url
| where url matches "*/foo/bar/*"
```
Using "foo" and "bar" as keywords (if highly selective) dramatically reduces initial scan.

**Advanced Technique 4: JSON Literal Expression (Cheat Code)**

For JSON logs with known key-value pairs, use literal string matching:

**Inefficient:**
```
_index=prod_logs
| json "errorCode" as errorCode
| where errorCode = "AccessDenied"
```

**Ultra-Efficient (JSON Literal):**
```
_index=prod_logs "\"errorCode\":\"AccessDenied\""
| json "errorCode" as errorCode
| where errorCode = "AccessDenied"
```

**Why This Works:**
- Literal string `"errorCode":"AccessDenied"` matches exact JSON structure in raw event
- Bloom filter processes this at index level (fastest possible)
- Only works when the literal string appears in the event exactly as specified

**Pattern Summary:**
- **Indexed fields:** Use field=value or field=wildcard* in scope
- **High-selectivity strings:** Add unusual literal strings (GUIDs, error codes, specific IDs)
- **Optional fields:** Add field name as keyword when field only in subset of events
- **Regex patterns:** Extract literal string fragments from patterns
- **JSON logs:** Use `"\"key\":\"value\""` for known key-value pairs
- **Multiple keywords:** Combine for maximum selectivity: `error exception sqlexception`

#### Rule 3: Scope Selectivity Analysis
Use `ScopePattern.analyze_scope()` pattern from query_patterns.py:

```python
scope = "_sourceCategory=prod/app error"
analysis = ScopePattern.analyze_scope(scope)
# Returns: {
#   'has_partition': False,
#   'recommendations': ['Add _index= or _view=', 'Add more keywords']
# }
```

**Optimization Order:**
1. Partition specifier (_index, _view)
2. Source category (_sourceCategory)
3. Keywords (high-selectivity terms)
4. Indexed field filters (field="value")

### Phase 2: Filter Optimization (After the Pipe)

#### Rule 4: Filter Early, Filter Often
**Bad:**
```
_index=prod_logs
| parse "status=*" as status
| count by user, service, region, status
| where status = "500"
```

**Good:**
```
_index=prod_logs status=500
| parse "status=*" as status
| where status = "500"
| count by user, service, region
```

**Why:**
- Keyword in scope reduces scan
- Where filter before aggregation reduces rows
- Only aggregate needed fields

#### Rule 5: Avoid Expensive Operations in Scope
**Bad:**
```
_index=prod_logs
| parse regex "user=(?<user>\w+)" multi
| where user = "john@company.com"
```

**Good:**
```
_index=prod_logs "john@company.com"
| parse "user=*" as user
| where user = "john@company.com"
```

**Why:**
- parse regex is expensive, minimize rows processed
- Keyword in scope reduces scan
- Use simple parse when possible (faster than regex)

### Phase 3: Aggregation Optimization

#### Rule 6: Limit Cardinality in Group By
**Bad:**
```
| count by requestId, timestamp, sessionId, traceId
```
High cardinality (millions of unique combinations) causes:
- Memory issues
- Slow execution
- Large result sets

**Good:**
```
| count by service, status_code, region
```
Medium cardinality (hundreds to thousands) is optimal.

**Tool to Check Cardinality:**
```bash
MCP: profile_log_schema
  scope: "_index=prod_logs"
  suggest_candidates: true
  min_cardinality: 2
  max_cardinality: 1000
```

Returns fields with good cardinality for aggregation.

#### Rule 7: Use Timeslice for Time-Series
**Bad:**
```
| count by _messagetime
```
Every unique timestamp = high cardinality

**Good:**
```
| timeslice 5m
| count by _timeslice
```
Bucket into intervals = lower cardinality

#### Rule 8: Limit Result Set Size
**Bad:**
```
| count by field1, field2, field3
```
May return 100K rows

**Good:**
```
| count by field1, field2, field3
| top 100 by _count
```
Limits memory and output

### Phase 4: Time Range Optimization

#### Rule 9: Use Shortest Time Range Possible
**Bad:**
```
-30d for real-time monitoring dashboard
```

**Good:**
```
-1h for real-time, -24h for trends, -30d for historical analysis
```

**Cost Impact:**
- -1h vs -24h: 24x less data scanned
- -24h vs -30d: 30x less data scanned

**Estimate Before Querying:**
```bash
MCP: get_estimated_log_search_usage
  query: "_index=prod_logs _sourceCategory=prod/app"
  from_time: "-24h"
  by_view: true
```

If scan > 100 GB, reconsider time range or scope.

#### Rule 10: Use Receipt Time for Real-Time Data
**Bad:**
```
by_receipt_time: false (default)
```
May miss data delayed in ingestion

**Good (for real-time):**
```
by_receipt_time: true
```
Searches by time data was received, not log timestamp

### Phase 5: Advanced Patterns

#### Pattern 1: Subquery for Pre-Filtering
**Scenario:** Need to find errors for users who had >100 requests

**Inefficient:**
```
_index=prod_logs
| count by user
| where _count > 100
| join user [search _index=prod_logs error | count by user]
```

**Efficient:**
```
_index=prod_logs
| where user in (
    _index=prod_logs
    | count by user
    | where _count > 100
    | fields user
)
| where error
| count by user
```

#### Pattern 2: Sampling for Exploration
**Scenario:** Exploring log structure, don't need all data

**Inefficient:**
```
_index=prod_logs -24h
| parse ...
| count ...
```
Scans 500 GB

**Efficient:**
```
_index=prod_logs -1h
| limit 10000
| parse ...
| count ...
```
Scans 20 GB, same insights

#### Pattern 3: Materialized Results via Scheduled Search
**Scenario:** Dashboard queries same data every 5 minutes

**Inefficient:**
Each panel queries -24h of raw logs

**Efficient:**
1. Create scheduled search (runs every 15m):
   ```
   _index=prod_logs
   | timeslice 5m
   | count by service, status
   | save to _index=dashboard_results
   ```

2. Dashboard queries results index:
   ```
   _index=dashboard_results -24h
   | ...
   ```

**Impact:** Raw log scan → summary index scan (100x reduction)

## Query Patterns Library

### Optimal Query Structure Template
```
[partition] [metadata] [keywords] ["indexed_field"="value"]
| [where filters - high selectivity first]
| [parse - simple parse preferred over regex]
| [where filters - on parsed fields]
| [aggregation - low to medium cardinality]
| [post-aggregation filters]
| [sorting / limiting]
```

### Example: Optimized Error Query
```
_index=prod_logs _sourceCategory=prod/api error "status_code"="5"
| parse "status_code=* " as status
| parse "service=* " as service
| where status matches "5*"
| where service != "health-check"
| timeslice 5m
| count by _timeslice, service, status
| where _count > 10
| sort -_count
| limit 100
```

**Optimizations Applied:**
1. ✅ Partition specified
2. ✅ Keywords in scope (error, status_code=5)
3. ✅ Simple parse (not regex)
4. ✅ Where filters before aggregation
5. ✅ Timeslice for time-series
6. ✅ Medium cardinality group by
7. ✅ Result limiting

## Examples

### Example 1: Transform Slow Query
**Before (90 seconds, scans 2.3 TB):**
```
*
| where status_code = 500
| count by user
```

**Issues:**
- Scope `*` scans ALL data
- No partition filter
- No time optimization

**After (3 seconds, scans 45 GB):**
```
_index=prod_logs _sourceCategory=prod/api "status_code"="500"
| json "user", "status_code" as user, status nodrop
| where status = 500
| count by user
| top 100 by _count
```

**Improvements:**
- Added partition _index=prod_logs (100x reduction)
- Added keyword status_code=500 in scope (2x reduction)
- Limited results to top 100 (memory optimization)

**Result:** 30x faster, 51x less data scanned

### Example 2: Dashboard Optimization
**Before:** 12-panel dashboard, each panel queries -24h every 5 minutes
- Panels × Queries/day: 12 × 288 = 3,456 queries/day
- Scan per query: ~50 GB
- Total scan/day: 172 TB

**After Optimization:**
1. Reduced refresh rate: 5m → 15m (3x reduction)
2. Reduced time range on 8 panels: -24h → -4h (6x reduction)
3. Added partition scoping to all panels (5x reduction)

**Result:**
- Queries/day: 12 × 96 = 1,152 (3x fewer)
- Scan per query: ~10 GB (5x less via scoping)
- Scan/day: 11.5 TB (15x reduction)

**Cost Impact:** $3,096/month → $207/month (15x savings at $0.018/GB)

### Example 3: Finding Optimization Opportunities
**Step 1:** Find expensive queries
```bash
MCP: analyze_search_scan_cost
  from_time: "-7d"
  group_by: "user_query"
  sort_by: "billable_scan_gb"
  min_scan_gb: 100
  limit: 20
```

**Step 2:** Analyze query scope
```bash
MCP: analyze_search_scan_cost
  from_time: "-7d"
  group_by: "user_scope_query"
  include_scope_parsing: true
```

**Step 3:** Identify missing partitions
Filter results where `scope` doesn't contain `_index=` or `_view=`

**Step 4:** Provide optimized versions to users

## Common Anti-Patterns

### Anti-Pattern 1: The Kitchen Sink
```
*
| parse everything
| count by every possible field
```
**Fix:** Specific scope, targeted parsing, focused aggregation

### Anti-Pattern 2: The Regex Hammer
```
| parse regex complex_multi_line_pattern
```
**Fix:** Use simple parse when possible, json operator for JSON, csv for CSV

### Anti-Pattern 3: The Where After Aggregation
```
| count by field1, field2, field3
| where field1 = "specific_value"
```
**Fix:** Filter BEFORE aggregation:
```
| where field1 = "specific_value"
| count by field1, field2, field3
```

### Anti-Pattern 4: The Unlimited Result Set
```
| count by high_cardinality_field
```
Returns 1M rows, OOM error

**Fix:**
```
| count by high_cardinality_field
| top 1000 by _count
```

### Anti-Pattern 5: The Brute Force Join
```
| join user_id [search other_index ...]
```
Joins are expensive

**Fix:** Use lookup tables, or denormalize data at ingest time if possible

## Optimization Checklist

Before committing a query to production:

- [ ] Scope includes partition (_index or _view)
- [ ] Scope includes high-selectivity keywords
- [ ] Time range is as short as possible for use case
- [ ] Where filters before aggregation
- [ ] Group by fields have medium cardinality (<10K values)
- [ ] Result set is limited (top/limit)
- [ ] Tested on representative time range
- [ ] Estimated scan cost is acceptable
- [ ] Query completes in <30 seconds

For dashboards specifically:
- [ ] Refresh rate is appropriate (not faster than needed)
- [ ] Considered scheduled search for pre-aggregation
- [ ] Each panel's time range is justified

## Query Construction Helpers

The `search_helpers` module provides utilities to help build optimized queries:

### Build Scope Expression
```python
from search_helpers import build_scope_expression

scope = build_scope_expression(
    source_category="prod/app",
    index="prod_logs",
    keywords=["error", "exception"],
    additional_metadata={"_sourceHost": "server1"}
)
# Returns: "_sourceCategory=prod/app _index=prod_logs _sourceHost=server1 error exception"
```

### Suggest Scope from Discovery
```python
from search_helpers import suggest_scope_from_discovery

# After running explore_log_metadata
metadata_results = {...}  # Results from MCP tool
suggested_scope = suggest_scope_from_discovery(metadata_results)
# Returns optimal scope based on discovery
```

### Validate Query Structure
```python
from search_helpers import validate_query_structure

query = "_sourceCategory=prod/app error | count"
validation = validate_query_structure(query)
# Returns: {
#   'is_valid': True,
#   'has_scope': True,
#   'has_aggregation': True,
#   'warnings': [],
#   'suggestions': ['Add _index to reduce scan volume']
# }
```

### Common Query Patterns
```python
from search_helpers import get_common_query_patterns

patterns = get_common_query_patterns()
# Access optimized patterns:
# - patterns['categorical_count']
# - patterns['time_series_by_field']
# - patterns['filtering_where']
# - patterns['aggregation_stats']
```

### Operator Categories Reference
```python
from search_helpers import get_operator_category_info

operators = get_operator_category_info()
# Returns operators grouped by category:
# - parsing: json, parse, csv, xml, keyvalue
# - filtering: where, matches, in, contains
# - aggregation: count, sum, avg, pct, stddev
# - time_series: timeslice, transpose
# - formatting: fields, concat, format
```

## Related Skills
- [Writing Queries](./search-write-queries.md) - Complete query construction guide
- [UI Navigation](./ui-navigate-and-search.md) - Interactive query building
- [Log Discovery](./discovery-logs-without-metadata.md) - Find right partitions and scope
- [Search Cost Analysis](./cost-analyze-search-costs.md) - Measure optimization impact

## MCP Tools Used
- `explore_log_metadata` - Find partitions
- `profile_log_schema` - Check field cardinality
- `get_estimated_log_search_usage` - Estimate scan before running
- `analyze_search_scan_cost` - Measure actual costs
- `search_query_examples` - Find optimized examples

## API References
- [Query Language Reference](https://help.sumologic.com/docs/search/)
- [Optimize Search Performance](https://help.sumologic.com/docs/search/optimize-search-performance/)
- [Optimize with Partitions](https://help.sumologic.com/docs/search/optimize-search-partitions/)
- [Search Operators](https://help.sumologic.com/docs/search/search-query-language/group-aggregate-operators/)

---

**Version:** 1.0.0
**Domain:** Search & Performance
**Complexity:** Intermediate to Advanced
**Estimated Impact:** 10x-100x improvement in speed and cost
