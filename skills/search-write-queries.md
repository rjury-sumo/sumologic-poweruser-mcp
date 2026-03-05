# Skill: Writing Sumo Logic Search Queries

## Intent
Build effective Sumo Logic search queries from raw logs to valuable insights using the five-phase query construction pattern: scope, parse, filter, aggregate, and format.

## Prerequisites
- Understanding of log structure (JSON, tab-separated, unstructured)
- Basic knowledge of metadata fields (_sourceCategory, _index, _view)
- Access to Sumo Logic with log data available

## Context

**Use this skill when:**
- Building queries for dashboards or alerts
- Investigating log data for troubleshooting
- Creating saved searches for recurring analysis
- Converting UI-based searches to API/MCP tool queries

**Don't use this when:**
- Just browsing raw logs (use simple scope-only queries)
- Working with metrics (different query syntax)

## Five-Phase Query Pattern

Sumo Logic queries follow a pipeline structure with five broad phases:

### 1. Scope Phase
**Purpose:** Narrow down which logs to search using metadata and keywords
**Performance:** Most critical for cost and speed - good scope = fast query

**Metadata fields:**
- `_sourceCategory` - Source category assigned at ingestion
- `_index` or `_view` - Partition name (same field, different names)
- `_sourceHost` - Host where logs originated
- `_source` - Source name
- `_collector` - Collector name

**Pattern:**
```
_sourceCategory=prod/app error exception
```

**Best practices:**
- Always include metadata filter when possible
- Use keywords to eliminate unwanted events early
- Implicit AND: spaces = AND operator
- Wildcards: `*cloudtrail*` for pattern matching
- Explicit logic: `(error OR exception) AND prod`

**Examples:**
```
// Good scope - specific metadata + keywords
_sourceCategory=aws/cloudtrail errorCode AccessDenied

// Good scope - partition + source category
_index=prod_logs _sourceCategory=app/service error

// Poor scope - may scan all data
error exception
```

**MCP Tool Integration:**
Use `explore_log_metadata` to discover optimal scope:
```json
{
  "scope": "*",
  "from_time": "-15m",
  "metadata_fields": "_view,_sourceCategory"
}
```

### 2. Parse Phase (Optional)
**Purpose:** Extract fields from log messages for analysis
**When to use:** When you need fields for filtering, grouping, or aggregation

**Auto-parsing:**
JSON logs are auto-parsed by default - all JSON keys become fields

**Manual parsing operators:**

**`json` - Extract JSON fields:**
```
| json field=_raw "errorCode" as error_code
| json field=_raw "errorMessage" as error_msg
| json "userIdentity.arn" as user_arn nodrop
```
- `nodrop` keyword prevents filtering out logs without the field

**`parse` - Simple anchor-based parsing:**
```
| parse "eventSource\":\"*\"" as event_source
| parse "User: * Action: *" as username, action
```

**`parse regex` - Complex patterns:**
```
| parse regex "(?<timestamp>\d{4}-\d{2}-\d{2}) (?<level>\w+) (?<message>.*)"
| parse regex field=arn "^arn:aws:[a-z]+::[0-9]+:(?<role>.+)" nodrop
```

**Other parsers:**
- `csv` - Comma-separated values
- `keyvalue` - key=value pairs
- `xml` - XML documents

**Best practices:**
- Use explicit parsing instead of auto-parsing for better performance
- Add `nodrop` for optional fields
- Parse only fields you need (parsing is compute-intensive)

### 3. Filter Phase (Optional)
**Purpose:** Narrow results using field values
**When to use:** After parsing, when you need precise field-based filtering

**`where` operator - Numeric and string filtering:**
```
| where status_code >= 400 and status_code < 500
| where duration_ms > 1000
| where user_name = "admin"
| where count > 10
```

**`matches` operator - Pattern matching:**
```
| where error_code matches "*Limit*"
| where error matches "*Limit*" or error matches "*Exceeded*"
| where field_name matches /regex pattern/
```

**Other filtering:**
```
| where field in ("value1", "value2", "value3")
| where field not in ("excluded1", "excluded2")
| where isEmpty(field)
| where isNull(field)
```

**Best practices:**
- Use keywords in scope for faster filtering (runs before parsing)
- Use `where` for numeric comparisons or complex logic
- Combine keywords + where for optimal performance:
  ```
  _sourceCategory=prod (*Limit* OR *Exceeded*)  // Fast keyword filter
  | json "errorCode" as error
  | where error matches "*Limit*" or error matches "*Exceeded*"  // Precise filter
  ```

### 4. Aggregate Phase
**Purpose:** Transform log events into insights
**When to use:** For dashboards, alerts, statistical analysis

**Categorical aggregation (no time dimension):**
```
// Simple count by field
| count by error_code
| sort _count desc

// Top N values
| count by error_code
| top 10 error_code by _count

// Multiple aggregations
| count by status_code, method
| sort _count desc
```

**Time series aggregation:**
```
// Simple time series
| timeslice 5m
| count by _timeslice

// Time series by field
| timeslice 5m
| count by _timeslice, error_code
| transpose row _timeslice column error_code

// Multiple metrics
| timeslice 1h
| sum(bytes) as total_bytes,
  avg(duration_ms) as avg_duration,
  count as requests
  by _timeslice
```

**Statistical aggregations:**
```
| avg(duration_ms) as avg_duration,
  max(duration_ms) as max_duration,
  min(duration_ms) as min_duration,
  pct(duration_ms, 95) as p95_duration,
  stddev(duration_ms) as stddev_duration
```

**Time comparison:**
```
| timeslice 1h
| count by _timeslice
| compare with timeshift 24h  // Compare to 24 hours ago
```

**Best practices:**
- Use `timeslice` without parameters for auto-sizing based on time range
- Use `transpose` for dynamic field values in time series
- Sort categorical results: `| sort _count desc`
- Limit results: `| top 10 field by _count`

### 5. Format Phase (Optional)
**Purpose:** Clean up output for dashboards or readability
**When to use:** For final presentation, field manipulation

**Field selection:**
```
| fields error_code, error_message, count
| fields - unwanted_field  // Exclude field
```

**String formatting:**
```
| concat(field1, " - ", field2) as combined
| toLowerCase(field) as field_lower
| toUpperCase(field) as field_upper
| substring(field, 0, 10) as field_short
| replace(field, "old", "new") as field_clean
```

**Formatting operators:**
```
| format("%s - %s", field1, field2) as formatted
| formatDate(_messageTime, "yyyy-MM-dd") as date
```

**Geo operators:**
```
| geoip client_ip
| count by latitude, longitude, country_name
```

## Complete Query Examples

### Example 1: CloudTrail Error Analysis (Categorical)
```
_sourceCategory=Labs/AWS/CloudTrail* errorcode
| json field=_raw "errorCode" as error_code
| json field=_raw "errorMessage" as error_msg
| json field=_raw "recipientAccountId" as account_id
| parse "eventSource\":\"*\"" as event_source
| parse "\"eventName\":\"*\"" as event_name
| count by error_code, event_source
| sort _count desc
| top 20 error_code by _count
```

**Breakdown:**
1. Scope: CloudTrail logs with "errorcode" keyword
2. Parse: Extract JSON fields and parse additional fields
3. Filter: None (all errors included)
4. Aggregate: Count by error code and event source
5. Format: Sort and limit to top 20

### Example 2: Rate Limit Errors Over Time
```
_sourceCategory=Labs/AWS/CloudTrail* errorcode (*exceed* or *limit*)
| json field=_raw "errorCode" as error_code
| where error_code matches "*Limit*" or error_code matches "*Exceeded*"
| timeslice 15m
| count by _timeslice, error_code
| transpose row _timeslice column error_code
```

**Breakdown:**
1. Scope: CloudTrail + keywords for fast filtering
2. Parse: Extract error code
3. Filter: Precise match on specific error patterns
4. Aggregate: Time series count by error code
5. Format: Transpose for multi-series chart

### Example 3: CloudFront Status Code Distribution
```
_sourceCategory=*cloudfront*
| parse "*\t*\t*\t*\t*\t*\t*\t*\t*" as date,time,edge,bytes,ip,method,host,uri,status
| where status >= 400
| count by status
| sort _count desc
```

**Breakdown:**
1. Scope: CloudFront logs
2. Parse: Tab-separated fields
3. Filter: Only error status codes (>= 400)
4. Aggregate: Count by status
5. Format: Sort descending

### Example 4: Response Time Statistics
```
_sourceCategory=prod/app
| json "duration" as duration_ms
| json "endpoint" as api_endpoint
| where duration_ms > 0
| avg(duration_ms) as avg_ms,
  max(duration_ms) as max_ms,
  pct(duration_ms, 50) as p50_ms,
  pct(duration_ms, 95) as p95_ms,
  pct(duration_ms, 99) as p99_ms,
  count as requests
  by api_endpoint
| sort p95_ms desc
```

**Breakdown:**
1. Scope: Production app logs
2. Parse: Extract duration and endpoint
3. Filter: Exclude zero/invalid durations
4. Aggregate: Multiple percentiles by endpoint
5. Format: Sort by p95 (high latency endpoints first)

### Example 5: Geographic Traffic Analysis
```
_sourceCategory=web/access
| parse "* * * * \"*\" * * \"*\" \"*\"" as ip, user, date, time, request, status, bytes, referrer, user_agent
| geoip ip
| where !isEmpty(country_name)
| count by latitude, longitude, country_name, city
```

**Breakdown:**
1. Scope: Web access logs
2. Parse: Common log format
3. Filter: Exclude invalid geoip results
4. Aggregate: Count by geo dimensions
5. Format: None (geo fields ready for map panel)

## Query Optimization Patterns

### Pattern 1: Keywords Before Parse
**Bad:**
```
_sourceCategory=prod/app
| json "level" as log_level
| where log_level = "ERROR"
```

**Good:**
```
_sourceCategory=prod/app ERROR
| json "level" as log_level
| where log_level = "ERROR"
```
Keywords filter before parsing (faster).

### Pattern 2: Explicit Parsing vs Auto-Parsing
**Bad (auto-parsing):**
```
_sourceCategory=prod/app
| count by %"errorCode"
```

**Good (explicit):**
```
_sourceCategory=prod/app
| json "errorCode" as error_code
| count by error_code
```
Explicit parsing is faster and more maintainable.

### Pattern 3: Filter Before Aggregate
**Bad:**
```
_sourceCategory=prod/app
| timeslice 5m
| count by _timeslice, level
| where level = "ERROR"
```

**Good:**
```
_sourceCategory=prod/app ERROR
| json "level" as level
| where level = "ERROR"
| timeslice 5m
| count by _timeslice
```
Filter reduces data before aggregation.

### Pattern 4: Use Specific Scope
**Bad:**
```
error exception timeout
| count
```

**Good:**
```
_index=prod_logs _sourceCategory=app/service (error OR exception OR timeout)
| count
```
Specific scope reduces scan volume significantly.

## Dashboard Query Patterns

### For Categorical Panels (Pie, Bar, Table)
```
// Must have aggregation without timeslice
<scope>
| <parse>
| <filter>
| count by field1, field2
| sort _count desc
```

### For Time Series Panels (Line, Area, Column)
```
// Must have timeslice
<scope>
| <parse>
| <filter>
| timeslice <interval>
| count by _timeslice [, field]
[| transpose row _timeslice column field]  // For multi-series
```

### For Single Value Panels
```
// Single metric result
<scope>
| <parse>
| <filter>
| count  // or avg(), sum(), max(), etc.
```

### For Honeycomb Panels
```
// Categorical aggregation for nodes
<scope>
| <parse>
| count by dimension_field
| sort _count
```

### For Map Panels
```
// Must have latitude, longitude fields
<scope>
| <parse>
| geoip ip_field
| count by latitude, longitude, country_name
```

## Common Pitfalls

### Pitfall 1: No Scope on Aggregate Queries
**Problem:** Scans all data in account
```
error | count by _sourceHost
```
**Solution:** Always add scope
```
_sourceCategory=prod/* error | count by _sourceHost
```

### Pitfall 2: Forgetting nodrop for Optional Fields
**Problem:** Filters out logs without the field
```
| json "optional_field" as field
```
**Solution:** Add nodrop
```
| json "optional_field" as field nodrop
```

### Pitfall 3: Using Auto-Parsed Fields in Production
**Problem:** Slower queries, fragile field names
```
| count by %"errorCode"
```
**Solution:** Explicit parsing
```
| json "errorCode" as error_code
| count by error_code
```

### Pitfall 4: Filtering After Aggregation
**Problem:** Aggregates all data then filters (inefficient)
```
| timeslice 5m
| count by _timeslice, status
| where status = "500"
```
**Solution:** Filter before aggregation
```
| where status = "500"
| timeslice 5m
| count by _timeslice
```

### Pitfall 5: Missing transpose for Multi-Series Time Charts
**Problem:** Wrong format for charting
```
| timeslice 5m
| count by _timeslice, error_code
```
**Solution:** Add transpose
```
| timeslice 5m
| count by _timeslice, error_code
| transpose row _timeslice column error_code
```

## MCP Tools Used

- `search_sumo_logs` - Execute queries and retrieve results
- `create_sumo_search_job` - Create async search jobs for large queries
- `get_sumo_search_job_status` - Check job progress
- `get_sumo_search_job_results` - Retrieve job results
- `explore_log_metadata` - Discover optimal scope (Phase 1)
- `profile_log_schema` - Discover fields for parsing (Phase 2)
- `search_query_examples` - Find example queries for patterns
- `get_estimated_log_search_usage` - Estimate query cost before running

## Related Skills

- [Query Optimization](./search-optimize-queries.md) - Optimize query performance
- [Log Discovery](./discovery-logs-without-metadata.md) - Find logs and build scope
- [Search Cost Analysis](./cost-analyze-search-costs.md) - Understand query costs
- [Content Library Navigation](./content-library-navigation.md) - Save queries for reuse

## API References

- [Search Job API](https://api.sumologic.com/docs/#tag/searchJobManagement)
- [Log Operators Cheat Sheet](https://help.sumologic.com/docs/search/search-cheat-sheets/log-operators/)
- [Search Best Practices](https://help.sumologic.com/docs/search/get-started-with-search/build-search/best-practices-search/)
- [Aggregate Operators](https://help.sumologic.com/docs/search/search-query-language/group-aggregate-operators/)
- [Parse Operators](https://help.sumologic.com/docs/search/search-query-language/parse-operators/)
- [Time Compare](https://help.sumologic.com/docs/search/time-compare/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-06
