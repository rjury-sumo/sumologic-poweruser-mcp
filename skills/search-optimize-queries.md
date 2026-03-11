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

#### Rule 1: Always Include Partition (_index or_view)

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

#### Rule 3: Prefer Field Extraction Rules (FERs) Over Where Filters

**Field Extraction Rules (FERs)** are admin-defined parsing rules that extract fields at index time. Using FER-extracted fields dramatically improves performance compared to post-pipe filtering.

**Performance Hierarchy (Best to Worst):**

**Best: FER Field + Keyword in Scope**

```
_index=prod_logs status_code=5* error
| count by status_code, error_type
```

- FER extracts `status_code` at index time
- Indexed field filter + keyword in scope = maximum bloom filter efficiency
- No parsing overhead at query time

**Good: Keyword in Scope + Where Filter**

```
_index=prod_logs error
| json "status_code" as status_code
| where status_code >= 500
| count by status_code
```

- Keyword reduces initial scan via bloom filter
- Parse/filter at query time (overhead)
- Better than where-only, but not as fast as FER

**Poor: Where Filter Only (No Keyword)**

```
_index=prod_logs
| json "status_code" as status_code
| where status_code >= 500
| count by status_code
```

- Scans entire partition
- Parse all messages
- Filter after parsing
- Slowest, most expensive option

**When to Use Each:**

- **FER + keyword**: Production queries, dashboards, scheduled searches, repeated queries
- **Keyword + where**: Ad-hoc exploration, one-time investigations
- **Where only**: Last resort when neither FER nor keyword is possible (avoid in production)

**Creating a FER** (Admin Only):

```
Scope: _sourceCategory=prod/app
Parse Expression: json "status_code", "error_type", "user_id"
```

After FER is created, these fields are indexed and available without parsing.

**How to Check for FERs:**

Use the `list_field_extraction_rules` MCP tool to see available FERs for your data.

#### Rule 4: Scope Selectivity Analysis

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

1. Partition specifier (_index,_view)
2. Source category (_sourceCategory)
3. Keywords (high-selectivity terms)
4. Indexed field filters (field="value")

### Phase 2: Parse Optimization

#### Rule 5: Choose the Right Parse Operator

Parsing efficiency varies dramatically by operator choice. Use the fastest operator that meets your needs.

**Performance Ranking (Fastest to Slowest):**

1. **FER (Field Extraction Rule)** - Fastest, fields pre-extracted at index time
2. **parse anchor** - Fast, uses literal anchor strings
3. **json/csv/xml** - Moderate, structured format parsers
4. **keyvalue** - Moderate, for key=value formatted logs
5. **parse regex** - Slow, expensive pattern matching

**Use parse anchor for structured logs:**

**Good (parse anchor):**

```
_index=apache_logs
| parse "GET * HTTP" as url
| parse "\" * * \"" as status_code, bytes_sent
```

- Uses literal strings as anchors
- Fast, efficient
- Works well for structured formats

**Avoid (parse regex without FER):**

```
_index=apache_logs
| parse regex "GET (?<url>.*) HTTP.*\" (?<status>\d+) (?<bytes>\d+)"
```

- Much slower than parse anchor
- Only use when structure is complex/variable

**Parse Regex Best Practices:**

When you must use `parse regex`:

**Bad (greedy, non-specific):**

```
| parse regex "user: (?<user>.*) action"
```

- `.*` is greedy, matches too much
- Non-specific pattern

**Good (specific, constrained):**

```
| parse regex "user: (?<user>[a-zA-Z0-9_]+) action"
```

- Specific character class
- Constrained matching
- Much faster

**Better (use in FER):**

```
Admin creates FER with regex
Scope: _sourceCategory=prod/app
Parse: parse regex "user: (?<user>[a-zA-Z0-9_]+) action"
```

- One-time parse at index time
- All queries benefit
- No query-time parsing overhead

**Extract Parse Keywords to Scope:**

When using parse statements, extract literal strings to scope for bloom filter acceleration.

**Inefficient:**

```
_index=prod_logs
| parse "completed * action" as actionName
| count by actionName
```

**Efficient:**

```
_index=prod_logs completed action
| parse "completed * action" as actionName
| count by actionName
```

- Keywords "completed" and "action" filter via bloom filter
- Only events containing both strings are parsed
- Dramatic performance improvement for optional fields

### Phase 3: Filter Optimization (After the Pipe)

#### Rule 6: Filter Early, Filter Often

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

#### Rule 7: Avoid Expensive Operations in Scope

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

### Phase 4: Aggregation Optimization

#### Rule 8: Limit Cardinality in Group By

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

#### Rule 9: Use Timeslice for Time-Series

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

#### Rule 10: Aggregate Before Lookup Operations

**Lookup operations** can be expensive when processing large result sets. Always aggregate data before performing lookups to minimize the volume of data being enriched.

**Inefficient:**

```
_index=firewall_logs
| json "src_ip" as src_ip
| lookup threat_intel on src_ip
| where threat_level = "high"
| count by src_ip, threat_type
```

- Looks up every event (potentially millions)
- Enriches data before filtering
- Wastes lookups on events that will be filtered out

**Efficient:**

```
_index=firewall_logs
| json "src_ip" as src_ip
| count by src_ip
| lookup threat_intel on src_ip
| where threat_level = "high"
| count by src_ip, threat_type
```

- Aggregates to unique IPs first (potentially thousands)
- Only lookups unique values
- Filters after enrichment on smaller dataset
- Can be 100x-1000x faster

**Why This Works:**

- Reduces lookup API calls from N events to N unique values
- Minimizes data transfer for lookup results
- Filters on smaller enriched dataset

**Pattern:**

```
scope
| extract fields
| aggregate/deduplicate  <-- Do this BEFORE lookup
| lookup enrichment
| filter/aggregate on enriched fields
```

#### Rule 11: Limit Result Set Size

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

### Phase 5: Time Range Optimization

#### Rule 12: Use Shortest Time Range Possible

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

#### Rule 13: Use Receipt Time for Real-Time Data

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

### Phase 6: Advanced Patterns

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

Returns 1M rows, OOM error, exceeds API response limits

**Fix Option 1 - Top N:**

```
| count by high_cardinality_field
| sort _count desc
| limit 100
```

**Fix Option 2 - TopK (faster):**

```
| count by high_cardinality_field
| topk(100, _count)
```

**Fix Option 3 - "Others" Grouping (preserves total):**

```
| count by high_cardinality_field
| sort _count desc
| 1 as n | accum n as rank
| if (rank > 100, "others", high_cardinality_field) as high_cardinality_field
| sum(_count) as total by high_cardinality_field
```

See [search-result-size-optimization](search-result-size-optimization.md) for complete patterns

### Anti-Pattern 5: The Brute Force Join

```
| join user_id [search other_index ...]
```

Joins are expensive

**Fix:** Use lookup tables, or denormalize data at ingest time if possible

## Platform Engine Optimisations

Understanding these built-in engine features explains *why* certain patterns are much faster — and helps you write queries that leverage them effectively.

### Bloom Filter Tokenisation Rules

All ingested log events are full-text indexed using a bloom filter. Keywords in the scope (before the first `|`) are evaluated against this index to skip non-matching events before any decompression or parsing.

Tokenisation rules:
- Tokens are alphanumeric strings bounded by space or punctuation: `foo`, `1234abcd`, `10.2.3.4`, `user@abc.com`, `abc.com`
- Keywords are **case-insensitive**: `foo`, `FOO`, and `Foo` are equivalent
- Boolean operators: space = AND, use `OR`/`NOT` with brackets: `(error OR fatal) NOT debug`
- Wildcards: `bar*`, `b?r`, `*/cart/*`, `*.php`
- Exact phrases in quotes: `"some words all together"`, `"\"key\":\"value\""`

Use 1–2 highly discriminating keywords that eliminate most unwanted events.

### Query Rewriting

If the search scope matches a partition's routing expression, the Sumo Logic engine **automatically rewrites the query** to restrict scanning to only that partition — even without an explicit `_index=` in the scope.

This is why `_sourceCategory=prod/waf/*` on a customer with a `waf_logs` partition scoped to `_sourceCategory=prod/waf*` effectively behaves as if `_index=waf_logs` were added.

**Key requirement:** Query rewriting works best when all partitions use the **same metadata field** (e.g., all scoped by `_sourceCategory`). Mixed metadata across partitions (some by `_collector`, others by `_sourceCategory`) degrades rewriting and forces users to specify `_index=` explicitly.

### Push-Down Optimisation (Automatic)

For `where field = "value"` equality filters, the engine automatically infers `value` as an additional keyword and applies the bloom filter at retrieval time — converting a compute-time filter into a retrieval-time filter for free.

```
// User writes:
_sourceCategory=prod/app
| json "status" as status
| where status = "critical"

// Engine automatically adds "critical" as bloom filter keyword
```

**Limitation:** Push-down only works for `where field = "value"` equality. It does **not** trigger for `where field matches "..."` (regex/wildcard patterns).

### The Pushdown Hack — Manual Push-Down for `matches`

Since push-down doesn't trigger for `where matches`, you can emulate it by explicitly adding literal keyword fragments to the scope:

```
// Slow — regex match runs at compute time on all retrieved events:
_sourceCategory=abc
| json "url" as url
| where url matches "*/checkout/*"

// Fast — keyword pre-filters in retrieval phase, then regex confirms:
_sourceCategory=abc checkout
| json "url" as url
| where url matches "*/checkout/*"
```

The same applies to rare optional JSON fields — add the field name as a keyword when only a small fraction of events contain it:

```
// Only a small % of logs contain "errorDescription" — add it as keyword:
_sourceCategory=abc errorDescription "replication failed"
| json "errorDescription" as errorDescription
| where errorDescription matches /(?i)replication failed .*/
```

---

## Measuring Performance: Search Audit

Use the search audit view to identify slow, expensive, or poorly-scoped queries across your organisation.

```
// The search audit view (requires Search Audit policy to be enabled):
_view=sumologic_search_usage_per_query
```

Key fields: `user_name`, `query_type`, `data_scanned_bytes`, `execution_duration_ms`, `scanned_partition_count`, `scanned_bytes_breakdown` (by tier), `query`, `content_name`.

Red flags: scan > 1 TB per query, runtime > 5 minutes, scanning > 3 partitions, high billable scan in Infrequent/Flex tiers.

**Top scanners by total bytes:**

```
_view=sumologic_search_usage_per_query
| where data_scanned_bytes > (1 * 1G)
| (query_end_time - query_start_time)/1000 as range_s
| execution_duration_ms / 1000 as duration_s
| if(execution_duration_ms > 1000 * 30, 1, 0) as slow
| if(status_message = "Finished successfully", 0, 1) as fail
| count_distinct(query) as unique_queries,
  max(scanned_partition_count) as max_partitions,
  avg(scanned_partition_count) as avg_partitions,
  count_distinct(user_name) as users,
  sum(duration_s) as total_sec,
  count as searches,
  sum(data_scanned_bytes) as bytes_scanned,
  sum(slow) as %"slow > 30s",
  sum(fail) as %"fail/cancelled"
  by user_name, query_type
| sort bytes_scanned
| bytes_scanned / 1024/1024/1024 as scan_gb
```

**Infrequent scan with credit estimate:**

```
_view=sumologic_search_usage_per_query
analytics_tier=*infrequent*
| json field=scanned_bytes_breakdown "Infrequent" as scan_inf nodrop
| ((query_end_time - query_start_time) /1000 / 60 /60/24) as range_days
| parse regex field=query "(?i)(?<scope>(?:_datatier|_index|_view) *= *[a-zA-Z]+)" nodrop
| count as queries,
  sum(data_scanned_bytes) as total_bytes,
  pct(range_days, 50, 95),
  avg(scanned_partition_count) as partitions,
  sum(scan_inf) as infreq_scan
  by user_name, scope
| limit 100
| round(infreq_scan/1G, 2) as inf_scan_gb
| round(inf_scan_gb * 0.016, 2) as scan_credits
| sort scan_credits
```

MCP tools: `run_search_audit_query`, `analyze_search_scan_cost` (for Flex/Infrequent tier breakdown by user/query).

---

## Quick Reference: Optimization Rules Summary

**Scope Optimization (Phase 1):**

1. Always include partition (_index or_view)
2. Add keyword expressions for bloom filters (including JSON literals)
3. Prefer FER fields over where filters (FER + keyword > keyword + where > where only)
4. Analyze scope selectivity

**Parse Optimization (Phase 2):**
5. Choose right parse operator (FER > parse anchor > json/csv > parse regex)
6. Extract parse keywords to scope for bloom filtering

**Filter Optimization (Phase 3):**
7. Avoid expensive operations in scope (use keywords instead)

**Aggregation Optimization (Phase 4):**
8. Limit cardinality in group by (<10K unique values)
9. Use timeslice for time-series (not _messagetime)
10. Aggregate before lookup operations (dedupe first, then enrich)
11. Limit result set size (use top/limit)

**Time Range Optimization (Phase 5):**
12. Use shortest time range possible
13. Use receipt time for real-time data

## Optimization Checklist

Before committing a query to production:

- [ ] Scope includes partition (_index or_view)
- [ ] Scope includes high-selectivity keywords (or JSON literals for known fields)
- [ ] Using FER fields instead of where filters when possible
- [ ] Checked for available FERs with `list_field_extraction_rules`
- [ ] Parse keywords extracted to scope (e.g., "completed action" for parse "completed * action")
- [ ] Using parse anchor or json/csv instead of parse regex when possible
- [ ] Parse regex patterns are specific (not .* or .+)
- [ ] Time range is as short as possible for use case
- [ ] Where filters before aggregation
- [ ] Aggregation before lookup operations
- [ ] Group by fields have medium cardinality (<10K values)
- [ ] Result set is limited (top/limit)
- [ ] Tested on representative time range
- [ ] Estimated scan cost is acceptable (use `get_estimated_log_search_usage`)
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

- `explore_log_metadata` - Find partitions and source categories for scope
- `profile_log_schema` - Check field cardinality for aggregation planning
- `get_estimated_log_search_usage` - Estimate scan volume before running query
- `analyze_search_scan_cost` - Measure actual costs and identify expensive queries
- `run_search_audit_query` - Analyse which queries are expensive (search audit view)
- `search_query_examples` - Find optimized query patterns and examples
- `list_field_extraction_rules` - Discover available FERs for your data
- `get_field_extraction_rule` - Get details of specific FER configuration
- `list_custom_fields` - See custom fields defined in your organization

## API References

- [Query Language Reference](https://help.sumologic.com/docs/search/)
- [Best Practices for Searches](https://www.sumologic.com/help/docs/search/get-started-with-search/build-search/best-practices-search/)
- [Optimize Search Performance](https://help.sumologic.com/docs/search/optimize-search-performance/)
- [Optimize with Partitions](https://help.sumologic.com/docs/search/optimize-search-partitions/)
- [Field Extraction Rules](https://help.sumologic.com/docs/manage/field-extractions/)
- [Search Operators](https://help.sumologic.com/docs/search/search-query-language/group-aggregate-operators/)

---

**Version:** 2.1.0
**Last Updated:** 2026-03-09
**Domain:** Search & Performance
**Complexity:** Intermediate to Advanced
**Estimated Impact:** 10x-100x improvement in speed and cost

**Changelog v2.0:**

- Added Rule 3: Prefer FERs over where filters (performance hierarchy)
- Added Rule 5: Parse operator selection (FER > parse anchor > parse regex)
- Added Rule 10: Aggregate before lookup operations
- Enhanced Rule 2: JSON literal expressions and push-down optimization
- Added parse keyword extraction technique
- Added parse regex best practices (avoid .*, be specific)
- Renumbered all rules for logical flow (13 rules total)
- Added FER-related MCP tools to reference
- Enhanced checklist with FER and parse optimization items

**Changelog v2.1:**

- Added Platform Engine Optimisations section (bloom filter tokenisation rules, query rewriting, push-down, pushdown hack)
- Added Measuring Performance: Search Audit section with two example queries
- Added `run_search_audit_query` to MCP Tools Used
- Source: Sumo Logic Architecture For Log Search Performance (February 2025)
