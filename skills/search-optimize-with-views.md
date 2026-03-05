# Skill: Optimize Queries with Scheduled Views

## Intent
Transform slow, expensive raw log queries into fast, cost-effective scheduled view queries while maintaining equivalent results and understanding when view-based optimization is appropriate.

## Prerequisites
- Understanding of Sumo Logic search query syntax
- Knowledge of aggregation operators (count, sum, avg, max, min)
- Familiarity with timeslice and grouping concepts
- Access to scheduled views in the organization

## Context

**Use this skill when:**
- Dashboard panels timeout or take >10 seconds to load
- Queries scan TBs of data and incur high costs (Flex or Infrequent tier)
- User needs aggregate data over long time ranges (days to weeks)
- Scheduled reports run the same expensive queries repeatedly
- Raw log queries involve complex parsing, lookups, or filtering that could be pre-computed

**Don't use this when:**
- User needs raw message-level detail (views only provide aggregated data)
- Use case requires fields not available in any view schema
- Real-time data is required (views have ~1 minute processing delay)
- Query involves ephemeral/one-off ad-hoc analysis (view benefits are for repeated queries)
- Time range is very short (<1 hour) where raw logs are already fast

## Approach

### Phase 1: Analyze Current Query

1. **Understand query intent:**
   - What fields/dimensions are being extracted or grouped by?
   - What aggregations are being performed (count, sum, avg, etc.)?
   - What filtering criteria are applied?
   - What's the time range being queried?

2. **Identify optimization candidates:**
   - Queries with `| count by`, `| sum by`, `| avg by` → views pre-aggregate these
   - Queries with complex parsing → views pre-parse fields
   - Queries with lookup operators → views can pre-join data
   - Long time ranges (>1 day) → views dramatically faster
   - Repeated queries (dashboards, scheduled searches) → views cache results

3. **Estimate current cost/performance:**
   - Use `get_estimated_log_search_usage` to see scan volume
   - Note query execution time from user report
   - Identify bottlenecks (parsing, filtering, aggregation, data volume)

### Phase 2: Find Matching View

1. **List available views:**
   ```json
   {
     "name": "list_scheduled_views",
     "arguments": {
       "limit": 100,
       "instance": "default"
     }
   }
   ```

2. **Match view schema to query needs:**
   - Compare query's extracted/grouped fields to view's `reduceOnlyFields`
   - Verify view has same or higher cardinality than needed
   - Check if view's source scope overlaps with query scope
   - Confirm view retention covers needed time range

3. **Identify partial matches:**
   - View may have desired fields but additional dimensions
   - May need re-aggregation to collapse extra dimensions
   - View may have stricter filtering (subset of data) - verify correctness

### Phase 3: Transform Query to Use View

#### Transformation Pattern 1: Direct Replacement
**Original raw log query:**
```
_sourceCategory=apache | parse "status=* " as status_code | count by status_code
```

**View-based query:**
```
_view=apache_status_code_1m_v2 | sum(_count) by status_code
```

**Key differences:**
- Replace scope with `_view=name`
- Replace `count` with `sum(_count)` (view already counted at 1m intervals)
- Remove parsing (view pre-parsed)

#### Transformation Pattern 2: Re-aggregation with Timeslice
**Original raw log query:**
```
_sourceCategory=apache error | parse "status=* " as status_code | where status_code >= 400 | count by status_code, _timeslice | timeslice 1h
```

**View-based query:**
```
_view=apache_status_code_1m_v2 status_code>=400 | sum(_count) by status_code, _timeslice | timeslice 1h
```

**Key differences:**
- Use indexed field filter `status_code>=400` in scope (fast)
- Sum pre-aggregated 1m counts to 1h timeslice
- Much faster: re-aggregating 1m data vs parsing/aggregating raw logs

#### Transformation Pattern 3: Collapsing Dimensions
**Original raw log query:**
```
_sourceCategory=apache | parse ... | avg(response_time) by url_path
```

**Available view fields:**
```
reduceOnlyFields: ["url_path", "host", "avg_response_time", "_count"]
```

**View-based query (weighted average):**
```
_view=apache_response_time_1m_v1 | sum(avg_response_time * _count) as total_time, sum(_count) as total_requests by url_path | total_time / total_requests as avg_response_time
```

**Key differences:**
- View has extra dimension (host) that must be collapsed
- Use weighted average: sum(avg * count) / sum(count)
- More complex but still much faster than raw logs

#### Transformation Pattern 4: Adding Post-Aggregation Filters
**Original raw log query:**
```
_sourceCategory=apache | parse ... | count by status_code, host | where _count > 100
```

**View-based query:**
```
_view=apache_status_code_1m_v2 | sum(_count) by status_code, host | where _sum > 100
```

**Key differences:**
- Post-aggregation filter applies to summed view data
- Adjust threshold if needed (view data is 1m sliced)

### Phase 4: Validate and Compare

1. **Test view query:**
   - Run view-based query on same time range
   - Verify results match original query (or explain differences)
   - Measure query execution time

2. **Estimate cost savings:**
   - Use `get_estimated_log_search_usage` for both queries
   - Compare scan volumes (view should be orders of magnitude smaller)
   - Calculate cost difference for tiered/flex accounts

3. **Document performance gains:**
   - Execution time: Before vs After
   - Data scanned: Raw log GB vs View GB
   - Cost impact: Credits saved per query execution

### Phase 5: Production Deployment

1. **Replace query in dashboard panels** (if applicable)
2. **Update scheduled search queries** (if applicable)
3. **Document the optimization:**
   - Original query and problem
   - Replacement query
   - Performance metrics
   - Maintenance notes (view version dependencies)

## Query Patterns

### Pattern: Replace Count with Sum(_count)
```
# Raw log query
_sourceCategory=app | parse ... | count by field1, field2

# View-based query
_view=app_summary_1m | sum(_count) by field1, field2
```

### Pattern: Replace Avg with Weighted Avg
```
# Raw log query
_sourceCategory=app | parse "latency=*ms" as latency | avg(latency) by service

# View with avg_latency and _count
_view=app_latency_1m | sum(avg_latency * _count) / sum(_count) as avg_latency by service
```

### Pattern: Long Time Range Re-aggregation
```
# Raw log query over 30 days (very slow)
_sourceCategory=app | parse ... | count by status, _timeslice | timeslice 1d

# View-based query (dramatically faster)
_view=app_status_1m | sum(_count) by status, _timeslice | timeslice 1d
# Re-aggregating 30 days * 1440 minutes = 43,200 pre-aggregated rows vs billions of raw logs
```

### Pattern: Multi-version View Query
```
# Query all view versions to handle view schema evolution
_view=app_metrics_1m_* | sum(_count) by metric_name | sort by _sum desc | limit 10
```

### Pattern: Indexed Field Filtering
```
# Use indexed fields in scope for fast filtering
_view=cloudtrail_events_1m eventName=DeleteBucket OR eventName=DeleteUser | sum(_count) by eventName, awsRegion
```

## Examples

### Example 1: Optimize Slow Dashboard Panel

**Original Problem:**
```
Dashboard panel queries 7 days of Apache logs, takes 60 seconds, scans 500GB:

_sourceCategory=apache/access error OR "status=5*" | parse "status=* " as status_code | where status_code >= 500 | count by status_code, _timeslice | timeslice 1h
```

**Solution:**
1. Find view: `apache_status_code_1m_v2` with fields `status_code, host, method, _count`
2. Transform query:
```
_view=apache_status_code_1m_v2 status_code>=500 | sum(_count) by status_code, _timeslice | timeslice 1h
```

**Results:**
- Execution time: 60s → 3s (20x faster)
- Data scanned: 500GB raw logs → 2GB view data (250x less)
- Cost (Flex): ~$8 per query → ~$0.03 per query (266x cheaper)
- Dashboard loads instantly instead of timing out

### Example 2: Optimize Scheduled Report

**Original Problem:**
```
Daily scheduled search generates weekly report, scans 5TB:

_sourceCategory=ecommerce/transactions | parse "user=* amount=* status=*" as user, amount, status | where status="completed" | sum(amount) by user, _timeslice | timeslice 1d | sort by _sum desc | limit 100
```

**Solution:**
1. Find view: `ecommerce_transactions_1m_v1` with fields `user, amount, transaction_status, _count, sum_amount`
2. Transform query:
```
_view=ecommerce_transactions_1m_v1 transaction_status="completed" | sum(sum_amount) by user, _timeslice | timeslice 1d | sort by _sum desc | limit 100
```

**Results:**
- Scheduled search completes in minutes instead of timing out
- Data scanned: 5TB → 50GB (100x reduction)
- Reduced credit consumption for Flex account
- Report generation no longer fails during high-traffic days

### Example 3: Optimize Multi-Panel Dashboard

**Original Problem:**
```
Dashboard with 5 panels, each querying 30 days of logs:
- Total requests by status code
- Top 10 slowest endpoints
- Error rate over time
- Request count by region
- 95th percentile response time

All panels scan TBs, dashboard takes 3+ minutes to load.
```

**Solution:**
1. Find views:
   - `api_requests_1m_v2`: status_code, endpoint, region, _count
   - `api_response_time_1m_v1`: endpoint, avg_response_time, p95_response_time, _count

2. Transform all panel queries to use views:

**Panel 1 - Total requests by status code:**
```
_view=api_requests_1m_v2 | sum(_count) by status_code
```

**Panel 2 - Top 10 slowest endpoints:**
```
_view=api_response_time_1m_v1 | sum(avg_response_time * _count) / sum(_count) as avg_response by endpoint | sort by avg_response desc | limit 10
```

**Panel 3 - Error rate over time:**
```
_view=api_requests_1m_v2 | sum(_count) by status_code, _timeslice | timeslice 1h | where status_code >= 400
```

**Panel 4 - Request count by region:**
```
_view=api_requests_1m_v2 | sum(_count) by region
```

**Panel 5 - 95th percentile response time:**
```
_view=api_response_time_1m_v1 | avg(p95_response_time) by _timeslice | timeslice 1h
```

**Results:**
- Dashboard load time: 3+ minutes → 10 seconds (18x faster)
- All panels complete successfully without timeouts
- Dramatically reduced scan costs
- Dashboard usable for daily operations instead of occasional use

### Example 4: Apache Access Log Reporting Dashboard

**Use Case:** Accelerate Apache access log reporting with transpose visualization

**View Definition:**
```
_sourceCategory=Labs/Apache/Access
| parse "HTTP/1.1\" * " as status_code
| timeslice 1m
| count by status_code, _timeslice
```

**View Schema:**
- `indexName`: apache_status
- `reduceOnlyFields`: ["status_code", "_timeslice", "_count"]
- `indexedFields`: ["status_code"]

**Original Raw Log Query (slow over 7 days):**
```
_sourceCategory=Labs/Apache/Access
| parse "HTTP/1.1\" * " as status_code
| timeslice 1h
| count by status_code, _timeslice
| transpose row _timeslice column status_code
```
- Time: 60+ seconds
- Scans: 200GB raw logs

**Optimized View Query:**
```
_view=apache_status
| sum(_count) as requests by status_code, _timeslice
| timeslice 1h
| transpose row _timeslice column status_code
```
- Time: 3 seconds (20x faster)
- Scans: 5GB pre-aggregated view data (40x less)
- Re-aggregates 10,080 pre-computed 1m buckets (7 days * 1440 min/day) to 168 hourly buckets

**Key Benefits:**
- Parsing done once at ingestion (not repeated per query)
- 1m aggregation cached (not repeated per query)
- Dashboard panels load instantly for 7-30 day time ranges

### Example 5: Threat Intelligence Lookup Caching

**Use Case:** Pre-compute expensive threat intelligence and geo lookups for security dashboards

**View Definition (caches threatip + geoip results):**
```
_sourceCategory=logs/firewall
| json field=_raw "httpRequest.clientIp" as src_ip
| where ispublicip(src_ip)
| json field=_raw "action"
| threatip src_ip | where !(isempty(malicious_confidence))
| timeslice 1m
| "firewall" as vendor
| "cloudflare" as product
| malicious_confidence as threat
| json field=raw_threat "threat_types"
| count by _timeslice, vendor, product, _sourceCategory, _source, src_ip, action, threat, actor, threat_types
| lookup asn, organization from asn://default on ip=src_ip
| geoip src_ip
| fields -latitude, longitude, country_name, state
```

**View Schema:**
- `indexName`: threat_matches_1m
- `reduceOnlyFields`: ["_timeslice", "vendor", "product", "_sourceCategory", "_source", "src_ip", "action", "threat", "actor", "threat_types", "asn", "organization", "country_code", "city", "_count"]
- `indexedFields`: ["src_ip", "action", "country_code", "threat"]

**Original Raw Log Query (extremely slow, 30 days):**
```
_sourceCategory=logs/firewall
| json "httpRequest.clientIp" as src_ip
| where ispublicip(src_ip)
| threatip src_ip | where !(isempty(malicious_confidence))
| count by src_ip, malicious_confidence
| geoip src_ip
| sort by _count desc
| limit 100
```
- Time: 5+ minutes or timeout
- Scans: 5TB raw logs
- Performs threatip lookup on billions of IPs
- Performs geoip lookup on billions of IPs

**Optimized View Query (weeks of data in seconds):**
```
_view=threat_matches_1m country_code=CN OR country_code=RU
| sum(_count) as threat_events by src_ip, country_code, threat, threat_types
| sort by threat_events desc
| limit 100
```
- Time: 5 seconds (60x+ faster)
- Scans: 10GB pre-filtered/aggregated view data (500x less)
- Threat/geo lookups already cached in view
- Can query weeks of data instantly

**Critical Benefits:**
- **Lookup caching**: threatip and geoip lookups done once, stored in view
- **Temporal accuracy**: Threat intelligence stored as it was when logs arrived (doesn't change retroactively)
- **Pre-filtering**: Only malicious IPs stored (not all traffic)
- **Cost savings**: Massive scan reduction for Flex/Infrequent customers
- **Dashboard enablement**: Security dashboards can query 30+ days without timeouts

**Query Patterns:**
```
# Top malicious IPs by country
_view=threat_matches_1m
| sum(_count) by src_ip, country_code, threat
| sort by _sum desc | limit 50

# Threat trend over time
_view=threat_matches_1m
| sum(_count) by threat, _timeslice
| timeslice 1d
| transpose row _timeslice column threat

# ASN analysis
_view=threat_matches_1m
| sum(_count) by asn, organization
| sort by _sum desc | limit 20

# Filter by specific threat actor
_view=threat_matches_1m actor="apt29"
| sum(_count) by src_ip, threat_types, country_code
```

## Common Pitfalls

### Pitfall 1: Using count instead of summing pre-aggregated columns (CRITICAL)
**Problem:**
```
_view=apache_status_1m | count by status_code
# ⚠️ WRONG: This counts number of 1m aggregated rows, NOT original events!
# If view has 1440 rows (1 day * 1440 minutes), count = 1440, regardless of actual events
```

**Solution - Check reduceOnlyFields for actual aggregate column names:**
```
# View definition: | count by status_code, _timeslice
# reduceOnlyFields: ["status_code", "_timeslice", "_count"]
_view=apache_status_1m | sum(_count) as requests by status_code
# ✓ Correct: Sums pre-counted events from view

# View definition: | sum(bytes) as total_bytes, count as requests by status_code
# reduceOnlyFields: ["status_code", "total_bytes", "requests"]
_view=apache_status_1m | sum(requests) as total_requests by status_code
# ✓ Correct: Uses aliased column name from view definition

# View definition with custom aliases
# reduceOnlyFields: ["endpoint", "avg_latency", "request_count"]
_view=api_latency_1m | sum(request_count) as total by endpoint
# ✓ Correct: Uses the exact field name from reduceOnlyFields
```

**Key Points:**
- **Always check `reduceOnlyFields`** in view definition to find aggregate column names
- Common names: `_count`, `_sum`, `_avg`, `_max`, `_min`
- Aliased names: `requests`, `total_bytes`, `avg_latency`, etc. (depends on view creator)
- NEVER use bare `| count` on aggregate views (counts rows, not events)

### Pitfall 2: Incorrect weighted average calculation
**Problem:**
```
_view=response_time_1m | avg(avg_response_time) by endpoint
# This gives average of averages (incorrect for different count sizes)
```

**Solution:**
```
_view=response_time_1m | sum(avg_response_time * _count) / sum(_count) as avg_response_time by endpoint
# Weighted average: sum(avg * count) / sum(count)
```

### Pitfall 3: Not using indexed fields for filtering
**Problem:**
```
_view=app_logs_1m | where status_code >= 400 | sum(_count) by status_code
# Post-aggregation filter scans all view data first
```

**Solution:**
```
_view=app_logs_1m status_code>=400 | sum(_count) by status_code
# Scope filter uses indexed field (much faster if status_code is indexed)
```

### Pitfall 4: Expecting view to have raw message fields
**Problem:**
```
_view=apache_status_1m | parse "user=* " as user
# Views contain aggregated data only, no raw messages to parse
```

**Solution:**
- Check `reduceOnlyFields` to see available fields
- If field not in view, must query raw logs or request view enhancement

### Pitfall 5: Not adjusting thresholds for timeslice differences
**Problem:**
```
# Raw query with 1h timeslice, threshold 1000
_sourceCategory=app | count by status | timeslice 1h | where _count > 1000

# View query with 1m base timeslice
_view=app_status_1m | sum(_count) by status | timeslice 1h | where _sum > 1000
# Same threshold but querying different time ranges might not be equivalent
```

**Solution:**
- Understand view's base timeslice (usually 1m)
- Test both queries to ensure threshold equivalence
- Document any threshold adjustments

### Pitfall 6: Over-optimizing short time ranges
**Problem:** Using views for queries over 15 minutes where raw logs are already fast

**Solution:**
- Views benefit long time ranges (hours to weeks)
- For <1 hour queries, raw logs may be fine
- Balance optimization effort vs actual gain

## Related Skills

- [Discovery: Scheduled Views](./discovery-scheduled-views.md) - Finding available views and their schemas
- [Cost: Analyze Scan Costs](./cost-analyze-scan-costs.md) - Measuring cost impact of optimization
- [Search: Build Aggregate Queries](./search-build-aggregate-queries.md) - Understanding aggregation patterns
- [Discovery: Log Metadata](./discovery-log-metadata.md) - Understanding raw log structure before optimizing

## MCP Tools Used

- `list_scheduled_views` - Find available views with matching schemas
- `get_estimated_log_search_usage` - Measure scan volume before/after optimization
- `search_sumo_logs` - Test transformed queries
- `search_query_examples` - Find similar query patterns for reference

## API References

- [Scheduled Views Help](https://www.sumologic.com/help/docs/manage/scheduled-views/)
- [Query Scheduled Views](https://www.sumologic.com/help/docs/manage/scheduled-views/query-scheduled-view/)
- [Search Query Syntax](https://www.sumologic.com/help/docs/search/search-query-language/)
- [Infrequent Tier with Views Blog](https://www.sumologic.com/blog/optimize-value-of-cloudtrail-logs-with-infrequent-tier)
