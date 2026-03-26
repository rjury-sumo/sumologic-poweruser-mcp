# Changelog

## [0.1.2] - 2026-03-27

### Added

- **`analyze_ingest_lag` tool**: Detect and triage ingest lag and source timestamp parsing issues
  - Compares `_receipttime` vs `_messagetime` to measure lag in minutes per source
  - Searches by receipt time (`byReceiptTime=true`) to catch sources with severely wrong timestamps
  - Three query modes: `summary` (avg/max lag by source), `distribution` (percentile breakdown),
    `format_debug` (sample events with `_format` field for timestamp parse diagnosis)
  - Auto-generates `interpretation` and `recommendations` from results:
    - Negative lag → timezone misconfiguration detection
    - >24h lag → AWS S3 SNS notification missing (with fix link)
    - Recommends `analyze_data_volume_grouped` to check for spiky/intermittent ingest pattern
    - Recommends `get_sumo_collectors`/`get_sumo_sources` to inspect timezone config
  - `_format` parse_type decoding: `fail`, `none`, `ac1`, `ac2` trigger specific recommendations
- **`data-ingest-lag-diagnosis.md` skill**: 5-phase triage workflow for lag and timestamp issues
  - Phase 1: Summary scan to identify problem sources
  - Phase 2: Distribution analysis (universal vs partial lag)
  - Phase 3: Ingest volume pattern check via `analyze_data_volume_grouped`
  - Phase 4: Source configuration inspection via `get_sumo_collectors`/`get_sumo_sources`
  - Phase 5: Timestamp format debug with `_format` field interpretation guide
  - Covers: AWS S3 SNS notification pattern, timezone inheritance, auto-parse field selection

## [Unreleased] - 2026-03-10

### Changed

- **Package Renamed**: Project renamed from `sumologic-python-mcp` to `sumologic-poweruser-mcp`
  - Repository: `sumologic-poweruser-mcp`
  - Python package: `sumologic-poweruser-mcp`
  - Module: `sumologic_poweruser_mcp` (imports remain `from sumologic_poweruser_mcp.sumologic_mcp_server`)
  - CLI command: `sumologic-poweruser-mcp`
  - **Migration Required**: Users must update Claude Desktop `claude_desktop_config.json` to reference new package name

### Reason for Rename

To avoid confusion with the official Sumo Logic MCP server. This is a community power-user focused implementation with advanced analytics and cost optimization tools.

## [Previous] - 2026-03-05

### Added

- **Audit Index Search Tools (3 new tools)**: Comprehensive tools for searching Sumo Logic audit indexes
  - `search_legacy_audit`: Search legacy audit index (_index=sumologic_audit) for user activity and system events
    - Pre-built use cases: logins, scheduled_search_triggers, user_activity, content_changes
    - Supports action, status, and source_category filtering
    - Optional aggregation and keyword search
  - `search_audit_events`: Search enterprise audit events (_index=sumologic_audit_events) with JSON parsing
    - Structured JSON logs for user and system actions across all Sumo Logic features
    - Auto-extracts: eventName, eventTime, operator.email, operator.id, operator.sourceIp
    - Common event categories: authentication, content management, CSE operations, user management
  - `search_system_events`: Search enterprise system events (_index=sumologic_system_events) for system operations
    - Pre-built use cases: collector_source_health, monitor_alerts, monitor_alert_timeline
    - Collector/source health monitoring with unhealthy state detection
    - Monitor alert analysis and timeline views with alert duration tracking
- **Audit Helpers Module**: New `audit_helpers.py` with query builders and use case patterns
  - `build_legacy_audit_query()`: Construct queries for legacy audit index
  - `build_enterprise_audit_query()`: Construct queries for enterprise audit indexes with JSON parsing
  - Pre-built query patterns for common audit use cases
  - Event category documentation and field extraction helpers
- **Use Case Examples**: Pre-built queries for common audit scenarios
  - User login tracking and authentication analysis
  - Scheduled search alert trigger monitoring
  - Collector/source health monitoring for alerting
  - Monitor alert frequency and timeline analysis
  - Content change auditing
- **Tests**: Comprehensive test suite for audit tools (28 tests covering all query builders and use cases)
- **Documentation**: Full documentation in `docs/mcp-tools-reference.md` for all 3 new audit tools

### Changed

- Updated `docs/mcp-tools-reference.md`:
  - Total tools: 41 → 44 (added 3 audit index search tools)
  - Added new "Audit Index Tools (3)" category
  - Renumbered existing tools to maintain sequential order (tools 10-41 became 13-44)
- Enhanced documentation with comprehensive use cases for audit index searches

## [Previous] - 2026-03-04

### Added

- **Development Guidelines**: Comprehensive development documentation for consistent AI-assisted development
  - `CLAUDE.md`: Guidelines for Claude/AI-assisted development with patterns, workflows, and checklists
  - `.PATTERNS.md`: Architecture patterns and coding standards with detailed examples
  - `docs/QUICK_REFERENCE.md`: Quick lookup reference for common development tasks
  - `docs/development/.CHECKLIST_TEMPLATE.md`: Template checklist for new features
- **URL Generation Improvements**: Enhanced web URL generation with proper regional and subdomain support
  - New `url_builder.py` module for centralized URL generation
  - Support for custom subdomains in `.env` configuration (`SUMO_SUBDOMAIN`, `SUMO_<INSTANCE>_SUBDOMAIN`)
  - Added `build_search_web_url` tool to generate shareable search URLs with pre-filled queries
  - Enhanced `get_content_web_url` to auto-detect dashboards and generate correct URLs
  - Support for all Sumo Logic regions (au, ca, de, eu, fed, in, jp, kr, us2)
- **Configuration**: Added optional `subdomain` field to instance configuration
- **Tests**: Comprehensive URL builder tests (16 tests covering all functions and edge cases)
- **Documentation Verification Script**: `scripts/verify_docs.py` to catch documentation drift automatically
- **Enhanced Docstrings**: Improved documentation for 5 high-traffic tools with comprehensive examples and use cases

### Changed

- Updated `get_content_web_url` tool to handle dashboard URLs differently from library content
  - Dashboards now use `/dashboard/{id}` format instead of `/library/{id}`
  - Auto-detects content type and fetches dashboard unique ID when needed
- Updated `.env.example` with subdomain configuration examples
- Enhanced `.gitignore` to prevent temporary development files from being committed
- Updated README.md with links to new development documentation
- Updated `docs/mcp-tools-reference.md`:
  - Total tools: 40 → 41
  - Enhanced documentation for `get_content_web_url` with URL formats and subdomain examples
  - Added documentation for `build_search_web_url` tool
  - Renumbered tools 25-41 to maintain sequential order

### Fixed

- Web URL generation now correctly maps API endpoints to UI endpoints for all regions
- Dashboard URLs now use proper dashboard ID instead of content ID

## [Previous] - 2026-02-25

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
