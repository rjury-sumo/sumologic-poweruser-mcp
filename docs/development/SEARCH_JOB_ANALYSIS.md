# Search Job Implementation Analysis

## Comparison: Advanced Script vs MCP Server

### Key Differences Found

| Feature | Advanced Script | Current MCP | Status |
|---------|----------------|-------------|--------|
| **Result Types** | Messages OR Records | Messages only | ❌ Missing |
| **Time Format** | Relative (-1h), ISO, Epoch | ISO/Epoch only | ⚠️ Partial |
| **byReceiptTime** | Configurable | Not exposed | ❌ Missing |
| **requiresRawMessages** | Smart (False for aggregates) | Not set | ❌ Missing |
| **Pagination** | Full support (offset/limit) | Returns all | ⚠️ Limited |
| **Job ID Return** | Create-only mode | Not available | ❌ Missing |
| **Status Details** | Full status object | Limited | ⚠️ Basic |
| **Error States** | Handles all states | Basic handling | ⚠️ Basic |
| **Cookie Handling** | Full support | May be missing | ❓ Unknown |

### Critical Issues in Current MCP Implementation

#### 1. **Always Uses Messages Endpoint** ❌
```python
# Current: Always gets messages
results_response = await self._request(
    "GET",
    f"/search/jobs/{job_id}/messages",
    api_version="v1"
)
```

**Problem:** Aggregate queries (with `count`, `sum`, `avg`, etc.) return **records**, not messages!

**Impact:**
- Aggregate queries may return empty or incorrect results
- Performance hit from requesting wrong data type
- User confusion about missing data

#### 2. **Missing `byReceiptTime` Parameter** ❌

The advanced script supports:
```python
'byReceiptTime': by_receipt_time  # Critical for some use cases
```

**Impact:** Cannot search by receipt time, which is important for:
- Delayed log ingestion scenarios
- Troubleshooting ingestion issues
- Compliance requirements

#### 3. **Missing `requiresRawMessages` Parameter** ❌

The advanced script sets this intelligently:
```python
requires_raw_messages = args.mode == 'messages'  # False for aggregates!
```

**Impact:**
- Aggregate queries may perform poorly
- Unnecessary data processing
- Increased API load

#### 4. **No Relative Time Support** ⚠️

Advanced script supports:
```python
"-1h", "-30m", "-2d", "-1w", "now"
```

**Impact:** Users must calculate absolute timestamps themselves

#### 5. **No Job ID-Only Mode** ❌

Advanced script has `create-only` mode to just return job ID.

**Impact:** Cannot create jobs for later retrieval or external monitoring

#### 6. **Limited Pagination** ⚠️

Current implementation doesn't expose offset/limit parameters.

**Impact:** Large result sets cannot be retrieved in chunks

##3. Detection: How to Know if Query is Aggregate

**Aggregate query indicators:**
- Contains: `count`, `sum`, `avg`, `min`, `max`, `pct`, `stddev`
- Contains: `group by`, `by` clause
- Contains: `| parse` followed by aggregations
- Contains: timeslice with aggregations

**Message query indicators:**
- Simple filters only
- No aggregation operators
- May have `| fields` but no aggregations

### Recommended Implementation Changes

#### Phase 1: Critical Fixes (High Priority)

1. **Add Records vs Messages Detection**
   ```python
   def detect_query_type(query: str) -> str:
       """Detect if query returns records or messages."""
       aggregate_keywords = ['count', 'sum', 'avg', 'min', 'max',
                            'pct', 'stddev', 'group by', ' by ', 'timeslice']
       query_lower = query.lower()

       for keyword in aggregate_keywords:
           if keyword in query_lower:
               return 'records'
       return 'messages'
   ```

2. **Add Get Records Method**
   ```python
   async def get_search_job_records(self, job_id: str, offset: int = 0, limit: int = 10000):
       """Get aggregate records from search job."""
       params = {"offset": offset, "limit": limit}
       return await self._request(
           "GET",
           f"/search/jobs/{job_id}/records",
           api_version="v1",
           params=params
       )
   ```

3. **Update search_logs to Auto-Detect**
   ```python
   async def search_logs(self, query, from_time, to_time, ...):
       # Detect query type
       query_type = detect_query_type(query)
       requires_raw_messages = (query_type == 'messages')

       search_data = {
           "query": query,
           "from": from_time,
           "to": to_time,
           "timeZone": timezone_str,
           "requiresRawMessages": requires_raw_messages
       }

       # ... create job ...

       # Get appropriate results
       if query_type == 'records':
           results = await self.get_search_job_records(job_id)
           return {
               "job_id": job_id,
               "query_type": "records",
               "record_count": status.get("recordCount", 0),
               "records": results.get("records", [])
           }
       else:
           results = await self.get_search_job_messages(job_id)
           return {
               "job_id": job_id,
               "query_type": "messages",
               "message_count": status.get("messageCount", 0),
               "messages": results.get("messages", [])
           }
   ```

4. **Add byReceiptTime Parameter**
   ```python
   async def search_logs(
       self,
       query: str,
       from_time: str,
       to_time: str,
       timezone_str: str = "UTC",
       by_receipt_time: bool = False,  # NEW
       max_attempts: Optional[int] = None
   ):
       search_data = {
           "query": query,
           "from": from_time,
           "to": to_time,
           "timeZone": timezone_str,
           "byReceiptTime": by_receipt_time,  # NEW
           # ...
       }
   ```

#### Phase 2: Enhancements (Medium Priority)

5. **Add Relative Time Parsing**
   ```python
   def parse_relative_time(time_str: str) -> str:
       """Convert relative time to ISO format."""
       if time_str == "now":
           return datetime.now(timezone.utc).isoformat()

       # Handle -1h, -30m, etc.
       pattern = r'^-(\d+)([smhdw])$'
       match = re.match(pattern, time_str)
       if match:
           amount, unit = int(match.group(1)), match.group(2)
           units = {'s': 'seconds', 'm': 'minutes', 'h': 'hours',
                   'd': 'days', 'w': 'weeks'}
           delta = timedelta(**{units[unit]: amount})
           target = datetime.now(timezone.utc) - delta
           return target.isoformat()

       return time_str  # Return as-is if not relative
   ```

6. **Add Job Creation Tool**
   ```python
   @mcp.tool()
   async def create_sumo_search_job(
       query: str,
       from_time: str,
       to_time: str,
       timezone: str = "UTC",
       by_receipt_time: bool = False,
       instance: str = 'default'
   ) -> str:
       """Create a search job and return job ID without waiting."""
       # ... implementation ...
       return json.dumps({
           "job_id": job_id,
           "link": f"{client.endpoint}/ui/#/search/{job_id}"
       })
   ```

7. **Add Job Status Tool**
   ```python
   @mcp.tool()
   async def get_sumo_search_job_status(
       job_id: str,
       instance: str = 'default'
   ) -> str:
       """Get status of a search job."""
       # ... implementation ...
   ```

8. **Add Explicit Records/Messages Tools**
   ```python
   @mcp.tool()
   async def get_sumo_search_job_results(
       job_id: str,
       result_type: str = "auto",  # auto, messages, records
       offset: int = 0,
       limit: int = 10000,
       instance: str = 'default'
   ) -> str:
       """Get results from a completed search job."""
       # ... implementation ...
   ```

#### Phase 3: Advanced Features (Low Priority)

9. **Add Pagination Support to Main Search**
10. **Add Progress Callbacks**
11. **Add Batch Time Range Support**

### Tool Descriptions & Hints

#### Updated search_sumo_logs Description

```python
"""
Search Sumo Logic logs with auto-detection of query type.

Automatically determines if query is:
- **Aggregate query** (count, sum, avg, etc.) → Returns records
- **Raw log query** → Returns messages

Time formats supported:
- Relative: "-1h", "-30m", "-1d" (hours/minutes/days back from now)
- ISO: "2024-01-01T00:00:00Z"
- Epoch: Integer milliseconds

Examples:
  # Aggregate query (returns records)
  query: "error | count by _sourceHost"
  hours_back: 24

  # Raw logs (returns messages)
  query: "_sourceCategory=prod/app AND error"
  hours_back: 1

  # By receipt time (for delayed logs)
  query: "error"
  hours_back: 2
  by_receipt_time: True

Returns:
  - query_type: "messages" or "records"
  - messages: Array of log messages (if type=messages)
  - records: Array of aggregate results (if type=records)
  - job_id: For reference/debugging
"""
```

#### New Tool: create_sumo_search_job

```python
"""
Create a Sumo Logic search job without waiting for results.

Useful for:
- Long-running queries (check status later)
- Creating multiple jobs in parallel
- External monitoring/alerting
- Debugging query performance

Returns job_id which can be used with:
- get_sumo_search_job_status
- get_sumo_search_job_results

Example:
  query: "error | count by _sourceHost | sort by _count"
  from_time: "-24h"
  to_time: "now"

  Returns: {"job_id": "ABC123", "link": "https://..."}
"""
```

### Testing Requirements

1. **Test aggregate queries**
   - `error | count`
   - `_sourceCategory=* | count by _sourceHost`
   - `| timeslice 1h | count by _timeslice`

2. **Test message queries**
   - `error`
   - `_sourceCategory=prod/app`
   - `error | fields _raw, _sourceHost`

3. **Test relative times**
   - `-1h`, `-30m`, `-1d`
   - `now`

4. **Test byReceiptTime**
   - With delayed logs
   - Compare vs normal time

5. **Test pagination**
   - Large result sets
   - Offset/limit combinations

### Documentation Additions

Add to README.md:

```markdown
## Search Query Types

The Sumo Logic MCP server automatically detects your query type:

### Aggregate Queries (Returns Records)
Queries with aggregation operators return structured records:
- `count`, `sum`, `avg`, `min`, `max`
- `group by` or `by` clauses
- `timeslice` with aggregations

Example:
```
error | count by _sourceHost | sort by _count
```

### Raw Log Queries (Returns Messages)
Queries without aggregations return raw log messages:
- Simple filters
- Field extraction without aggregation
- Full text search

Example:
```
_sourceCategory=prod/app AND error
```

### Time Formats

- **Relative**: `-1h` (1 hour ago), `-30m`, `-2d`
- **ISO**: `2024-01-01T00:00:00Z`
- **Epoch**: Milliseconds since epoch
```

## Summary of Changes Needed

### Critical (Must Fix)
- [ ] Add `get_search_job_records()` method
- [ ] Add query type detection
- [ ] Update `search_logs()` to use correct endpoint
- [ ] Add `byReceiptTime` parameter
- [ ] Add `requiresRawMessages` parameter

### Important (Should Add)
- [ ] Add relative time parsing
- [ ] Add pagination parameters
- [ ] Add `create_sumo_search_job` tool
- [ ] Add `get_sumo_search_job_status` tool
- [ ] Update tool descriptions with examples

### Nice to Have
- [ ] Add explicit records/messages tools
- [ ] Add batch time range support
- [ ] Add progress indicators

---

**Priority Order:**
1. Fix records vs messages (CRITICAL - queries may be broken)
2. Add byReceiptTime (HIGH - important use cases)
3. Add requiresRawMessages (HIGH - performance)
4. Add relative time support (MEDIUM - usability)
5. Add job management tools (MEDIUM - flexibility)
