# Search Job Implementation TODO

## Status: Analysis Complete, Implementation Needed

The search job functionality has critical gaps compared to the advanced script. The analysis is complete in `SEARCH_JOB_ANALYSIS.md`.

## Files Created

1. ✅ `SEARCH_JOB_ANALYSIS.md` - Complete comparison and implementation plan
2. ✅ `src/sumologic_mcp_server/search_helpers.py` - Helper functions for:
   - Query type detection (messages vs records)
   - Relative time parsing (-1h, -30m, etc.)
   - Time range formatting

## Critical Issues to Fix

### 1. Messages vs Records ❌ CRITICAL
**Current:** Always calls `/messages` endpoint
**Problem:** Aggregate queries return `records`, not `messages`!

**Queries that are BROKEN right now:**
```
error | count by _sourceHost          ← Returns NOTHING (should use /records)
| timeslice 1h | count                ← Returns NOTHING (should use /records)
_sourceCategory=* | count by level    ← Returns NOTHING (should use /records)
```

**Fix Required:**
1. Add `get_search_job_records()` method to client
2. Use `detect_query_type()` from search_helpers.py
3. Call correct endpoint based on query type
4. Set `requiresRawMessages` appropriately

### 2. Missing Parameters ❌ HIGH
- `byReceiptTime` - Not exposed (needed for delayed log scenarios)
- `requiresRawMessages` - Not set (causes performance issues)

### 3. Time Format Support ⚠️ MEDIUM
- No relative time support (-1h, -30m, etc.)
- Users must calculate timestamps manually

## Implementation Steps

### Step 1: Fix Critical Issues (30 min)

```python
# In sumologic_mcp_server.py

from .search_helpers import detect_query_type, parse_relative_time

# Add to SumoLogicClient:
async def get_search_job_records(self, job_id: str, offset: int = 0, limit: int = 10000):
    """Get aggregate records from search job."""
    params = {"offset": offset, "limit": limit}
    return await self._request(
        "GET",
        f"/search/jobs/{job_id}/records",
        api_version="v1",
        params=params
    )

# Update search_logs() method:
async def search_logs(
    self,
    query: str,
    from_time: str,
    to_time: str,
    timezone_str: str = "UTC",
    by_receipt_time: bool = False,  # NEW
    max_attempts: Optional[int] = None
):
    # Parse relative times
    from_ms = parse_relative_time(from_time)
    to_ms = parse_relative_time(to_time)

    # Detect query type
    query_type = detect_query_type(query)
    requires_raw_messages = (query_type == 'messages')

    search_data = {
        "query": query,
        "from": from_ms,
        "to": to_ms,
        "timeZone": timezone_str,
        "byReceiptTime": by_receipt_time,  # NEW
        "requiresRawMessages": requires_raw_messages  # NEW
    }

    # ... create job and poll ...

    # Get correct results
    if query_type == 'records':
        results = await self.get_search_job_records(job_id)
        return {
            "job_id": job_id,
            "query_type": "records",
            "record_count": status.get("recordCount", 0),
            "records": results.get("records", []),
            "fields": results.get("fields", [])
        }
    else:
        results = await self._request(...)
        return {
            "job_id": job_id,
            "query_type": "messages",
            "message_count": status.get("messageCount", 0),
            "messages": results.get("messages", [])
        }
```

### Step 2: Update Tools (15 min)

```python
# Update search_sumo_logs tool
@mcp.tool()
async def search_sumo_logs(
    query: str = Field(description="Sumo Logic search query"),
    hours_back: int = Field(default=1, description="Number of hours to search back"),
    from_time: str | None = Field(default=None, description="Start time (supports -1h, -30m, ISO, epoch)"),
    to_time: str | None = Field(default=None, description="End time (supports now, ISO, epoch)"),
    by_receipt_time: bool = Field(default=False, description="Search by receipt time instead of message time"),
    timezone_param: str = Field(default="UTC", description="Timezone", alias="timezone"),
    instance: str = Field(default='default', description="Instance name")
) -> str:
    """
    Search Sumo Logic logs with automatic query type detection.

    The query is automatically analyzed to determine if it returns:
    - **Messages** (raw logs): Simple filters, no aggregations
    - **Records** (aggregates): count, sum, avg, group by, timeslice, etc.

    Time Formats:
    - Relative: "-1h" (hour ago), "-30m" (30 min ago), "-2d" (2 days ago)
    - Absolute: "2024-01-01T00:00:00Z" (ISO format)
    - Epoch: 1704067200000 (milliseconds)
    - Current: "now"

    Examples:
      # Aggregate query - returns records with counts
      query: "error | count by _sourceHost"
      hours_back: 24

      # Raw logs - returns message objects
      query: "_sourceCategory=prod/app AND error"
      hours_back: 1

      # Relative time
      from_time: "-24h"
      to_time: "now"

      # By receipt time (for delayed logs)
      query: "error"
      by_receipt_time: True
    """
    # Implementation uses hours_back OR from_time/to_time
    ...
```

### Step 3: Add Job Management Tools (20 min)

```python
@mcp.tool()
async def create_sumo_search_job(
    query: str,
    from_time: str = "-1h",
    to_time: str = "now",
    timezone: str = "UTC",
    by_receipt_time: bool = False,
    instance: str = 'default'
) -> str:
    """
    Create a search job without waiting for results.

    Returns job_id immediately for:
    - Long-running queries
    - Parallel job creation
    - External monitoring
    - Manual result retrieval

    Use get_sumo_search_job_status() to check progress.
    Use get_sumo_search_job_results() to retrieve results.
    """
    ...

@mcp.tool()
async def get_sumo_search_job_status(
    job_id: str,
    instance: str = 'default'
) -> str:
    """
    Get status of a search job.

    Returns:
    - state: "GATHERING RESULTS", "DONE GATHERING RESULTS", etc.
    - messageCount: Number of messages found
    - recordCount: Number of records found
    - Progress information
    """
    ...

@mcp.tool()
async def get_sumo_search_job_results(
    job_id: str,
    result_type: str = "auto",  # auto, messages, records
    offset: int = 0,
    limit: int = 10000,
    instance: str = 'default'
) -> str:
    """
    Get results from a completed search job.

    Supports:
    - Automatic detection of result type
    - Pagination with offset/limit
    - Both messages and records
    """
    ...
```

### Step 4: Update Documentation (10 min)

Update README.md with:
1. Query type explanation (messages vs records)
2. Time format examples
3. byReceiptTime use cases
4. Job management workflow

### Step 5: Add Tests (20 min)

```python
# tests/test_search_helpers.py
def test_detect_query_type_aggregate():
    assert detect_query_type("error | count") == "records"
    assert detect_query_type("| sum(bytes)") == "records"

def test_detect_query_type_messages():
    assert detect_query_type("error") == "messages"
    assert detect_query_type("_sourceCategory=*") == "messages"

def test_parse_relative_time():
    # Test -1h, -30m, now, etc.
    ...
```

## Quick Test Commands

After implementation:

```bash
# Test aggregate query (should return records)
uv run python -c "
from sumologic_mcp_server.search_helpers import detect_query_type
print(detect_query_type('error | count by _sourceHost'))  # Should print: records
"

# Test message query (should return messages)
uv run python -c "
from sumologic_mcp_server.search_helpers import detect_query_type
print(detect_query_type('error'))  # Should print: messages
"

# Test relative time
uv run python -c "
from sumologic_mcp_server.search_helpers import parse_relative_time
print(parse_relative_time('-1h'))  # Should print epoch ms 1 hour ago
"
```

## Verification Checklist

After implementation, verify:

- [ ] Aggregate query (`error | count`) returns records, not messages
- [ ] Message query (`error`) returns messages, not records
- [ ] Relative times work (`-1h`, `-30m`, `now`)
- [ ] `byReceiptTime=True` parameter is sent to API
- [ ] `requiresRawMessages` is set correctly (False for aggregates)
- [ ] Job ID is returned in all responses
- [ ] Create-only mode works (returns job ID without waiting)
- [ ] Status tool shows progress correctly
- [ ] Pagination works with offset/limit
- [ ] Tool descriptions include examples
- [ ] Tests pass

## Files to Modify

1. ✅ `src/sumologic_mcp_server/search_helpers.py` (DONE)
2. `src/sumologic_mcp_server/sumologic_mcp_server.py` - Update client methods and tools
3. `tests/test_search_helpers.py` - New test file
4. `tests/test_sumologic_mcp_server.py` - Add search tests
5. `README.md` - Update documentation

## Estimated Time

- Critical fixes: 30 minutes
- Tool updates: 15 minutes
- New tools: 20 minutes
- Documentation: 10 minutes
- Tests: 20 minutes

**Total: ~1.5 hours**

## Priority

🔴 **URGENT** - Current aggregate queries may be broken!

Test immediately:
```
query: "error | count by _sourceHost"
```

If this returns empty results, it's because we're calling `/messages` instead of `/records`.

---

**Next Steps:**
1. Run quick test with aggregate query
2. Implement Step 1 (critical fixes)
3. Test with real queries
4. Implement remaining steps
5. Update documentation
