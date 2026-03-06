# Skill: Discover and Understand Scheduled Views

## Intent

Discover available scheduled views in a Sumo Logic organization and understand their purpose, schema, and query patterns to determine if they can accelerate specific query use cases.

## Prerequisites

- Access to Sumo Logic instance with scheduled views configured
- Basic understanding of log query concepts and aggregation operators

## Context

**Use this skill when:**

- User asks "what views are available?" or "are there any scheduled views?"
- Looking for pre-aggregated data sources for a specific use case
- Dashboard queries are slow and you want to find faster alternatives
- Need to understand the schema/fields available in a view
- Investigating cost optimization opportunities (tiered or flex accounts)

**Don't use this when:**

- User needs to create or modify scheduled views (requires admin access and different tools)
- Looking for partitions instead of views (partitions are indexed at ingestion, views are query-time)
- Need real-time data (views have 1-minute processing delay)

## Approach

### Phase 1: Inventory Discovery

1. **List all scheduled views** to understand what's available:

   ```json
   {
     "name": "list_scheduled_views",
     "arguments": {
       "limit": 100,
       "instance": "default"
     }
   }
   ```

2. **Analyze the response** looking for:
   - `indexName` - The view name used in queries (`_view=name`)
   - `reduceOnlyFields` - Output schema (available fields)
   - `indexedFields` - Fields that can be filtered in query scope
   - `query` - The view's source query and aggregation logic
   - `retentionPeriod` - How long data is kept
   - `next` - Pagination token if more views exist

3. **Handle pagination** if many views exist:

   ```json
   {
     "name": "list_scheduled_views",
     "arguments": {
       "limit": 100,
       "token": "pagination_token_from_previous_response",
       "instance": "default"
     }
   }
   ```

### Phase 2: Schema Analysis

1. **Identify relevant views** based on naming patterns and query content:
   - Look for keywords matching user's domain (apache, aws, k8s, etc.)
   - Check `reduceOnlyFields` for needed output columns
   - Examine `indexedFields` for filterable dimensions

2. **Understand versioning patterns**:
   - Views named like `view_name_v1`, `view_name_v2` indicate evolution
   - Multiple versions may exist simultaneously
   - Use wildcard patterns to query all versions: `_view=view_name_*`

3. **Extract schema information**:
   - `reduceOnlyFields`: Available output fields (can use in projections, filters, aggregations)
   - `indexedFields`: Fast-filter fields (use in query scope like `_view=name field=value`)
   - Timeslice: Always 1 minute for scheduled views

### Phase 3: Use Case Mapping

1. **Match view capabilities to user needs**:
   - If user needs "http status codes by server", look for views with fields like `status_code`, `server`, `host`
   - If user needs "error counts over time", look for views aggregating error conditions
   - If user needs "API latency metrics", look for views with latency/response_time fields

2. **Assess performance benefits**:
   - Views with low cardinality (few unique dimension values) = faster queries
   - Views covering long time ranges = much faster than raw logs
   - Views with pre-computed aggregates = near-instant results for compatible queries

3. **Identify cost optimization opportunities**:
   - **Tiered accounts**: Aggregate views have 0 scan cost
   - **Flex accounts**: Views scan much less data than raw logs
   - Best impact: Dashboard panels, scheduled reports, long time range queries (days to weeks)

## Query Patterns

### View Discovery by Name Pattern

```
# List views, then filter by name pattern client-side
# Look for: indexName containing keywords like "apache", "cloudtrail", "k8s"
```

### View Schema Inspection

```
# From list_scheduled_views response, extract:
{
  "indexName": "apache_status_code_1m_v2",
  "reduceOnlyFields": ["status_code", "host", "method", "_count"],
  "indexedFields": ["status_code", "host"],
  "query": "_sourceCategory=apache | parse ... | count by status_code, host, method | timeslice 1m"
}
```

### View Query Syntax Examples

```
# Basic view query
_view=apache_status_code_1m_v2

# View query with filtering (using indexed fields)
_view=apache_status_code_1m_v2 status_code=500

# View query with wildcard (query all versions)
_view=apache_status_code_1m_*

# View query with aggregation on view fields
_view=apache_status_code_1m_v2 | sum(_count) by host

# View query over long time range (where views shine)
_view=apache_status_code_1m_v2 status_code>=400 | sum(_count) by status_code | timeslice 1h
# Note: Re-aggregating 1m timeslice to 1h for longer range analysis
```

## Examples

### Example 1: Find views for Apache web server analysis

**User request:** "Are there any views that can help me analyze Apache web server logs?"

**Approach:**

1. List all scheduled views
2. Filter results client-side for names containing "apache" or "web" or "http"
3. Present matching views with their schemas
4. Suggest query patterns based on available fields

**Sample Response:**

```
Found 2 scheduled views for Apache analysis:

1. apache_status_code_1m_v2
   - Fields: status_code, host, method, _count
   - Indexed: status_code, host
   - Use case: HTTP status code distribution by server
   - Query: _view=apache_status_code_1m_v2 status_code>=400

2. apache_response_time_1m_v1
   - Fields: host, url_path, avg_response_ms, max_response_ms, _count
   - Indexed: host, url_path
   - Use case: Response time analysis by endpoint
   - Query: _view=apache_response_time_1m_v1 | avg(avg_response_ms) by host
```

### Example 2: Find views for AWS CloudTrail security analysis

**User request:** "I need to analyze CloudTrail events - are there any pre-aggregated views?"

**Approach:**

1. List scheduled views
2. Search for "cloudtrail", "aws", "security" in indexName or query fields
3. Analyze schema for security-relevant fields (eventName, userIdentity, sourceIP, etc.)
4. Provide query examples for common security use cases

**Sample Response:**

```
Found 1 scheduled view for CloudTrail:

cloudtrail_events_1m_v3
- Fields: eventName, eventSource, userIdentity_principalId, sourceIPAddress, awsRegion, _count
- Indexed: eventName, eventSource, awsRegion
- Use case: CloudTrail event analysis by action type, service, and region
- Retention: 90 days

Example queries:
# Find all failed authentication attempts
_view=cloudtrail_events_1m_v3 eventName=ConsoleLogin | where status="Failure" | sum(_count) by sourceIPAddress

# Top API calls by service
_view=cloudtrail_events_1m_v3 | sum(_count) by eventSource, eventName | sort by _sum

# Security monitoring over 30 days
_view=cloudtrail_events_1m_v3 eventName IN (DeleteBucket, DeleteUser, PutBucketPolicy) | sum(_count) by eventName | timeslice 1d
```

### Example 3: Optimize slow dashboard panel

**User request:** "My dashboard panel is querying 7 days of raw logs and times out. Can a view help?"

**Approach:**

1. Understand the panel's query intent (what fields/aggregations are needed)
2. List scheduled views
3. Match view schema to panel requirements
4. Propose view-based query as replacement
5. Explain performance and cost benefits

**Original slow query:**

```
_sourceCategory=apache error OR exception | parse "status=*" as status_code | where status_code >= 400 | count by status_code, _timeslice | timeslice 1h
```

**Approach:**

1. List views, find `apache_status_code_1m_v2` with fields: status_code, host,_count
2. Propose view-based alternative:

```
_view=apache_status_code_1m_v2 status_code>=400 | sum(_count) by status_code, _timeslice | timeslice 1h
```

**Benefits:**

- **Performance**: Pre-parsed, pre-filtered, 1m aggregated → re-aggregate to 1h is near-instant
- **Cost (Tiered)**: 0 scan cost for aggregate view vs scanning raw logs
- **Cost (Flex)**: Minimal scan (1m aggregated data) vs scanning 7 days of raw logs
- **Reliability**: No query timeouts for longer time ranges

### Example 4: Discover threat intelligence lookup caching views

**User request:** "Are there any views that cache threat intelligence lookups? My security dashboard times out querying 30 days of firewall logs."

**Approach:**

1. List scheduled views
2. Search for views with "threat", "malicious", "geo", "ip" in name or query
3. Look for views using threatip, geoip, or lookup operators in query definition
4. Identify views that pre-filter to only malicious/suspicious events (reduces data volume)
5. Check for geo/ASN enrichment fields in schema

**Discovery Query Analysis:**

```json
{
  "name": "list_scheduled_views",
  "arguments": {"limit": 100}
}
```

**Found View:**

```
threat_matches_1m
- Query: Includes "threatip src_ip | where !(isempty(malicious_confidence))"
- Query: Includes "lookup asn, organization from asn://default"
- Query: Includes "geoip src_ip"
- reduceOnlyFields: [
    "_timeslice", "vendor", "product", "_sourceCategory", "_source",
    "src_ip", "action", "threat", "actor", "threat_types",
    "asn", "organization", "country_code", "city", "_count"
  ]
- indexedFields: ["src_ip", "action", "country_code", "threat"]
- retentionPeriod: 90 days
```

**Key Insights:**

- **Pre-filtering**: View only stores malicious IPs (not all traffic)
- **Lookup caching**: threatip, geoip, ASN lookups done once at 1m intervals
- **Temporal accuracy**: Threat intelligence stored as it was when logs arrived
- **Rich context**: IP, geo, ASN, threat type all pre-joined
- **Indexed filters**: Can quickly filter by country, IP, action, threat level

**Proposed Queries:**

```
# Top malicious IPs from specific countries (weeks of data in seconds)
_view=threat_matches_1m country_code=CN OR country_code=RU
| sum(_count) as threat_events by src_ip, country_code, threat, threat_types
| sort by threat_events desc
| limit 50

# Threat trend over time
_view=threat_matches_1m
| sum(_count) by threat, _timeslice
| timeslice 1d
| transpose row _timeslice column threat

# ASN-based threat analysis
_view=threat_matches_1m
| sum(_count) by asn, organization, country_code
| sort by _sum desc
| limit 20

# Specific threat actor investigation
_view=threat_matches_1m actor="apt29"
| sum(_count) by src_ip, threat_types, country_code, action
```

**Benefits vs Raw Log Query:**

- **Performance**: 5+ minutes (or timeout) → 5 seconds (60x+ faster)
- **Scan volume**: 5TB raw logs → 10GB pre-filtered view (500x reduction)
- **Cost (Flex)**: Massive scan cost savings
- **Lookup caching**: No repeated threatip/geoip API calls
- **Historical accuracy**: Threat intelligence preserved from log arrival time
- **Dashboard enablement**: Security teams can query 30-90 days without timeouts

**View Pattern Recognition:**
Views containing these query patterns indicate lookup caching:

- `threatip` operator → Threat intelligence enrichment cached
- `geoip` operator → Geographic enrichment cached
- `lookup ... from asn://` → ASN enrichment cached
- `| where !(isempty(malicious_confidence))` → Pre-filtered to threats only
- Fields like `malicious_confidence`, `threat_types`, `actor` → Threat metadata cached

## Common Pitfalls

### Pitfall 0: Using count instead of sum on aggregate columns (CRITICAL)

**Problem:** `_view=apache_status | count by status_code` counts view rows, NOT original events

**Solution:**

- **Always check `reduceOnlyFields`** to find aggregate column names
- Use `sum(_count)`, `sum(requests)`, etc. based on actual field names
- Never use bare `| count` on aggregate views
- Common column names: `_count`, `_sum`, `_avg`, or custom aliases like `requests`, `total_bytes`

**Example:**

```
# View definition: | count by status_code, _timeslice
# reduceOnlyFields: ["status_code", "_timeslice", "_count"]
_view=apache_status | sum(_count) as total_requests by status_code  # ✓ Correct

# View definition with alias: | count as requests by status_code
# reduceOnlyFields: ["status_code", "_timeslice", "requests"]
_view=apache_status | sum(requests) as total by status_code  # ✓ Correct
```

### Pitfall 1: Querying views with keywords

**Problem:** `_view=apache_status_code_1m error` fails - views don't support keyword search

**Solution:** Views have fixed schemas. Only use:

- Field=value filters: `_view=name field=value`
- Indexed field filters for best performance
- Post-aggregation filtering with `| where` if needed

### Pitfall 2: Expecting real-time data

**Problem:** Views show data with ~1 minute delay

**Solution:**

- For real-time use cases, query raw logs instead
- For historical analysis and dashboards, views are ideal
- Views are perfect for time ranges > 1 hour where delay doesn't matter

### Pitfall 3: Not understanding schema limitations

**Problem:** Trying to parse or extract new fields from view data

**Solution:**

- Views have fixed schema defined by `reduceOnlyFields`
- You can't extract new fields from view data (already aggregated)
- Check schema before proposing view-based query
- If needed fields aren't in view, must use raw logs or request new view

### Pitfall 4: Ignoring view versioning

**Problem:** Querying old view version (v1) when newer version (v2) has better schema

**Solution:**

- Always check for multiple versions of similarly-named views
- Compare `reduceOnlyFields` across versions
- Use wildcard `_view=name_*` to query all versions if appropriate
- Recommend latest version unless specific version needed

### Pitfall 5: Not leveraging indexed fields

**Problem:** Filtering on non-indexed fields causes slower queries

**Solution:**

- Use `indexedFields` for scope filtering: `_view=name indexed_field=value`
- Use non-indexed fields in post-aggregation filters: `| where non_indexed_field=value`
- Indexed filters are pushed down → much faster

## Related Skills

- [Discovery: Log Metadata](./discovery-log-metadata.md) - For discovering raw log structure before views
- [Search: Optimize Queries](./search-optimize-queries.md) - Query optimization techniques including view usage
- [Cost: Analyze Scan Costs](./cost-analyze-scan-costs.md) - Understanding cost benefits of views vs raw logs
- [Search: Build Aggregate Queries](./search-build-aggregate-queries.md) - Constructing queries that work with view schemas

## MCP Tools Used

- `list_scheduled_views` - List available scheduled views with pagination
  - Required for inventory discovery
  - Returns view names, schemas, queries, retention
  - Supports pagination for large view sets

## API References

- [Scheduled View Management API](https://api.sumologic.com/docs/#tag/scheduledViewManagement)
- [Scheduled Views Help Docs](https://www.sumologic.com/help/docs/manage/scheduled-views/)
- [Query Scheduled Views](https://www.sumologic.com/help/docs/manage/scheduled-views/query-scheduled-view/)
