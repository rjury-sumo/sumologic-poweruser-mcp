# Changelog

## [Unreleased] - 2026-02-25

### Fixed - CRITICAL Search Job Bug
- **BREAKING FIX**: `search_logs()` now correctly detects query type and calls appropriate endpoint
  - Aggregate queries (count, sum, avg, etc.) now call `/records` endpoint instead of `/messages`
  - Raw log queries continue to call `/messages` endpoint
  - Fixes critical bug where aggregate queries returned empty results

### Added - Search Job Enhancements

#### New Methods in SumoLogicClient
- `create_search_job()` - Create a search job without waiting for results
- `get_search_job_status()` - Check status of a running search job
- `get_search_job_records()` - Retrieve aggregate records from completed job
- `get_search_job_messages()` - Retrieve raw messages from completed job

#### New MCP Tools
- `create_sumo_search_job` - Create async search job, returns job ID immediately
- `get_sumo_search_job_status` - Check job state, counts, and metadata
- `get_sumo_search_job_results` - Retrieve paginated results with auto-detection

#### New Parameters
- `from_time` and `to_time` - Explicit time range (overrides hours_back)
- `by_receipt_time` - Use receipt time for delayed logs and recent searches
- Time format support:
  - Relative: "-1h", "-30m", "-24h", "now"
  - ISO8601: "2024-01-15T10:00:00Z"
  - Epoch milliseconds: "1705315200000"

#### Helper Functions (search_helpers.py)
- `detect_query_type()` - Automatically detect messages vs records queries
- `parse_relative_time()` - Convert relative time strings to epoch milliseconds
- `format_time_range_human()` - Human-readable time range formatting

### Changed
- `search_logs()` now includes `query_type` in response
- `search_logs()` automatically adds `requiresRawMessages` parameter
- Response now includes appropriate key ("messages" or "records") based on query type

### Documentation
- Updated [README.md](README.md) with:
  - Query type explanation (messages vs records)
  - Time format examples
  - byReceiptTime use cases
  - Async search job workflow
  - Tool list updated with new search job tools
- Created comprehensive usage examples

### Testing
- Added 9 new tests for search helpers and integration
- All 17 unit tests passing
- Query type detection tests
- Relative time parsing tests
- Integration tests for real API calls (skipped without credentials)

### Technical Details

**Before (Broken)**:
```python
# Always called /messages, even for aggregates
results = await self._request("GET", f"/search/jobs/{job_id}/messages")
return {"results": results.get("messages", [])}
```

**After (Fixed)**:
```python
# Detects query type and calls correct endpoint
query_type = detect_query_type(query)
if query_type == "records":
    results = await self._request("GET", f"/search/jobs/{job_id}/records")
    results_key = "records"
else:
    results = await self._request("GET", f"/search/jobs/{job_id}/messages")
    results_key = "messages"
return {"query_type": query_type, "results": results.get(results_key, [])}
```

## Impact

### Queries Now Working ✅
- `error | count by _sourceHost` - Returns aggregate records
- `* | timeslice 1h | count` - Returns time-series data
- `metric | avg by host` - Returns averaged metrics
- Any query with: count, sum, avg, min, max, group by, timeslice

### Queries Unchanged ✅
- `_sourceCategory=prod/app` - Returns raw messages (as before)
- `error | where level="high"` - Returns filtered messages (as before)

### New Capabilities ✅
- Async job creation for long-running queries
- Proper pagination support for large result sets
- Relative time support for simpler queries
- byReceiptTime for very recent logs
