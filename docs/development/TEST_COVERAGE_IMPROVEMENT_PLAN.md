# Test Coverage Improvement Plan

**Current Overall Coverage:** 39% (2610 statements, 1593 missing)
**Target Coverage:** 80%+ for critical modules, 60%+ overall
**Generated:** 2026-03-07

## Executive Summary

This plan identifies modules with poor test coverage and provides actionable tasks to improve testing. Priority is given to modules that:
1. Are critical to server functionality (client, validation, error handling)
2. Have complex logic prone to bugs (search helpers, query patterns)
3. Have zero or minimal coverage currently

## Coverage by Module (Current State)

| Module | Coverage | Priority | Complexity |
|--------|----------|----------|------------|
| `sumologic_mcp_server.py` | **25%** | 🔴 Critical | High |
| `async_export_helper.py` | **0%** | 🔴 Critical | Medium |
| `content_id_utils.py` | **0%** | 🟡 High | Low |
| `search_helpers.py` | **43%** | 🔴 Critical | Medium |
| `query_patterns.py` | **64%** | 🟡 High | Medium |
| `rate_limiter.py` | **71%** | 🟢 Medium | Low |
| `exceptions.py` | **68%** | 🟢 Medium | Low |
| `validation.py` | **77%** | 🟢 Medium | Medium |
| `audit_helpers.py` | **78%** | 🟢 Low | Medium |
| `url_builder.py` | **81%** | 🟢 Low | Low |
| `config.py` | **87%** | 🟢 Low | Low |
| `response_filter.py` | **94%** | ✅ Good | Low |
| `__init__.py` | **100%** | ✅ Good | Low |

## Phase 1: Zero-Coverage Modules (Weeks 1-2)

### 1.1 `async_export_helper.py` (0% coverage)

**Current:** 45/45 statements missing
**Target:** 80%+ coverage
**Priority:** 🔴 Critical - Used by 10+ MCP tools for content export

**Missing Coverage:**
- `poll_export_job()` - Async job polling with exponential backoff
- `poll_async_folder_export()` - Folder export job polling
- `start_content_export()` - Content export job initiation
- `get_export_result()` - Export result retrieval

**Test Tasks:**
```python
# tests/test_async_export_helper.py (NEW FILE)

class TestPollExportJob:
    async def test_successful_export_immediate()
        """Test job that completes on first poll."""

    async def test_successful_export_with_polling()
        """Test job that requires multiple polls."""

    async def test_export_timeout()
        """Test job that times out after max_wait_seconds."""

    async def test_export_failure()
        """Test job that fails with error status."""

    async def test_poll_interval_increases()
        """Test exponential backoff between polls."""

class TestPollAsyncFolderExport:
    async def test_global_folder_export()
        """Test global folder export with children."""

    async def test_admin_recommended_export()
        """Test admin recommended folder export."""

    async def test_export_with_truncation()
        """Test export with max_items limit."""

class TestStartContentExport:
    async def test_content_export_admin_mode()
        """Test content export with admin mode."""

    async def test_content_export_regular_mode()
        """Test content export without admin mode."""

class TestGetExportResult:
    async def test_get_result_with_truncation()
        """Test result retrieval with item limit."""

    async def test_get_result_no_truncation()
        """Test full result retrieval."""
```

**Mocking Strategy:**
- Mock `SumoLogicClient` methods: `start_export_job()`, `get_export_status()`, `get_export_result()`
- Use `asyncio.sleep` mocks to speed up polling tests
- Test various job states: PENDING, PROCESSING, SUCCESS, FAILED

---

### 1.2 `content_id_utils.py` (0% coverage)

**Current:** 56/56 statements missing
**Target:** 95%+ coverage (pure utility functions)
**Priority:** 🟡 High - Used for URL generation and content identification

**Missing Coverage:**
- `hex_to_decimal()` - Convert 16-char hex ID to decimal
- `decimal_to_hex()` - Convert decimal ID to 16-char hex
- `is_valid_hex_id()` - Validate hex ID format
- `is_valid_decimal_id()` - Validate decimal ID format
- `normalize_content_id()` - Auto-detect and normalize IDs

**Test Tasks:**
```python
# tests/test_content_id_utils.py (NEW FILE)

class TestHexToDecimal:
    def test_valid_hex_conversion()
        """Test converting valid 16-char hex to decimal."""
        # Example: "00000000005E5403" -> "6181891"

    def test_short_hex_with_padding()
        """Test hex IDs shorter than 16 chars are padded."""

    def test_invalid_hex_raises_error()
        """Test invalid hex characters raise ValueError."""

    def test_zero_hex()
        """Test all-zeros hex ID."""

class TestDecimalToHex:
    def test_valid_decimal_conversion()
        """Test converting decimal to 16-char hex."""
        # Example: "6181891" -> "00000000005E5403"

    def test_large_decimal()
        """Test large decimal values."""

    def test_zero_decimal()
        """Test zero decimal value."""

    def test_negative_decimal_raises_error()
        """Test negative values raise ValueError."""

class TestValidation:
    def test_valid_hex_id()
        """Test is_valid_hex_id() with valid IDs."""

    def test_invalid_hex_id_length()
        """Test hex IDs of wrong length."""

    def test_invalid_hex_id_characters()
        """Test hex IDs with non-hex characters."""

    def test_valid_decimal_id()
        """Test is_valid_decimal_id() with valid IDs."""

    def test_invalid_decimal_id()
        """Test decimal IDs with non-numeric characters."""

class TestNormalize:
    def test_normalize_hex_id()
        """Test normalize_content_id() auto-detects hex."""

    def test_normalize_decimal_id()
        """Test normalize_content_id() auto-detects decimal."""

    def test_normalize_invalid_id()
        """Test normalize_content_id() with invalid input."""
```

**Approach:**
- Pure functions, no mocking needed
- Test known hex/decimal pairs from real Sumo Logic content IDs
- Test edge cases: max values, min values, boundary conditions

---

## Phase 2: Low-Coverage Critical Modules (Weeks 3-4)

### 2.1 `sumologic_mcp_server.py` (25% coverage)

**Current:** 1680 statements, 1261 missing (25% coverage)
**Target:** 60%+ coverage
**Priority:** 🔴 Critical - Main MCP server with all tools

**Coverage Analysis:**
- ✅ **Well-tested:** Basic client initialization, search job integration
- ❌ **Not tested:** Most MCP tool functions (50+ tools with 0% coverage)
- ❌ **Not tested:** Error handling in tool functions
- ❌ **Not tested:** Multi-instance support
- ❌ **Not tested:** Rate limiting integration

**Strategy:**
Focus on high-impact areas rather than exhaustive tool testing:

1. **Client API Methods** (Lines 195-700)
   - Test each `SumoLogicClient` method with mocked HTTP responses
   - Test error handling (401, 403, 429, 500 errors)
   - Test timeout handling

2. **Core MCP Tools** (Sample 10 most important)
   - `search_sumo_logs()` - Already tested ✅
   - `create_sumo_search_job()` - Not tested
   - `get_sumo_collectors()` - Not tested
   - `get_sumo_dashboards()` - Not tested
   - `export_content()` - Not tested
   - `get_content_web_url()` - Not tested
   - `list_scheduled_views()` - Not tested
   - `run_search_audit_query()` - Not tested
   - `analyze_search_scan_cost()` - Not tested
   - `get_skill()` - Already tested ✅

3. **Tool Error Handling**
   - Test `handle_tool_error()` with different exception types
   - Test validation errors in tools
   - Test rate limiting in tools

**Test Tasks:**
```python
# tests/test_sumologic_mcp_server.py (EXPAND EXISTING)

class TestSumoLogicClientAPI:
    """Test all SumoLogicClient API methods."""

    async def test_get_collectors_success()
        """Test successful collector retrieval."""

    async def test_get_collectors_auth_error()
        """Test 401 authentication error."""

    async def test_get_sources_success()
        """Test successful source retrieval."""

    async def test_get_dashboards_with_pagination()
        """Test dashboard listing with token pagination."""

    # ... test remaining 20+ client methods

class TestMCPToolsCore:
    """Test core MCP tool functions."""

    async def test_create_search_job_tool()
        """Test create_sumo_search_job tool."""

    async def test_get_collectors_tool()
        """Test get_sumo_collectors tool."""

    async def test_export_content_tool()
        """Test export_content tool."""

    async def test_tool_rate_limiting()
        """Test rate limiting is enforced in tools."""

    async def test_tool_validation_errors()
        """Test input validation in tools."""

class TestMultiInstanceSupport:
    """Test multi-instance configuration."""

    async def test_get_client_default_instance()
        """Test getting client for default instance."""

    async def test_get_client_named_instance()
        """Test getting client for named instance."""

    async def test_get_client_missing_instance()
        """Test error when instance not configured."""

class TestToolErrorHandling:
    """Test error handling in tool functions."""

    def test_handle_tool_error_api_error()
        """Test APIError formatting."""

    def test_handle_tool_error_validation_error()
        """Test ValidationError formatting."""

    def test_handle_tool_error_timeout()
        """Test timeout error formatting."""
```

**Mocking Strategy:**
- Mock `httpx.AsyncClient` responses for client methods
- Mock `get_sumo_client()` for tool tests to avoid real API calls
- Mock rate limiter for fast tests
- Use `pytest-asyncio` for async test support

**Effort Estimation:** High - This is the largest file with 1680 statements

---

### 2.2 `search_helpers.py` (43% coverage)

**Current:** 100 statements, 57 missing (43% coverage)
**Target:** 85%+ coverage
**Priority:** 🔴 Critical - Used by all search-related tools

**Missing Coverage:**
- Lines 134-135: `format_time_range_human()` - Human-readable time formatting
- Lines 158-175: `extract_scope_from_query()` - Scope extraction logic
- Lines 211-231: `parse_scope_expression()` - Scope parsing
- Lines 255-267: `extract_aggregate_fields()` - Field extraction
- Lines 279, 333: Error handling branches
- Lines 413-457: `build_search_query_with_scope()` - Query building

**Test Tasks:**
```python
# tests/test_search_helpers.py (NEW FILE)

class TestFormatTimeRange:
    def test_format_minutes()
        """Test formatting time range in minutes."""

    def test_format_hours()
        """Test formatting time range in hours."""

    def test_format_days()
        """Test formatting time range in days."""

class TestExtractScope:
    def test_extract_index_scope()
        """Test extracting _index=partition scope."""

    def test_extract_view_scope()
        """Test extracting _view=view_name scope."""

    def test_extract_datatier_scope()
        """Test extracting _dataTier=tier scope."""

    def test_extract_no_scope()
        """Test query with no scope returns None."""

    def test_extract_complex_scope()
        """Test query with multiple scope keywords."""

class TestParseScopeExpression:
    def test_parse_field_equals()
        """Test field=value expressions."""

    def test_parse_field_wildcard()
        """Test field=*wildcard* expressions."""

    def test_parse_multiple_expressions()
        """Test multiple space-separated expressions."""

class TestExtractAggregateFields:
    def test_extract_count_by()
        """Test extracting fields from '| count by field1, field2'."""

    def test_extract_sum_by()
        """Test extracting fields from '| sum(field) by group'."""

    def test_extract_no_aggregation()
        """Test query with no aggregation."""

class TestBuildSearchQuery:
    def test_build_with_scope_filters()
        """Test building query with scope_filters."""

    def test_build_with_where_filters()
        """Test building query with where_filters."""

    def test_build_with_both_filters()
        """Test building query with both filter types."""
```

**Approach:**
- Test with real Sumo Logic query examples
- Test edge cases: empty queries, malformed queries
- Test all operators: count, sum, avg, max, min, etc.

---

## Phase 3: Medium-Coverage Modules (Week 5)

### 3.1 `query_patterns.py` (64% coverage)

**Current:** 234 statements, 85 missing (64% coverage)
**Target:** 75%+ coverage
**Priority:** 🟡 High - Query example database with 11,000+ patterns

**Missing Coverage:**
- Lines 667-696: `_build_pattern_index()` - Index building
- Lines 736-946: `_load_examples()` - Example loading from JSON
- Lines 976-1062: `_score_example()` - Relevance scoring
- Lines 1097-1301: `search_examples()` - Main search function

**Test Tasks:**
```python
# tests/test_query_patterns.py (EXPAND EXISTING)

class TestPatternIndex:
    def test_pattern_index_building()
        """Test pattern index is built correctly."""

    def test_pattern_index_caching()
        """Test pattern index is cached after first load."""

class TestExampleLoading:
    def test_load_examples_from_json()
        """Test loading examples from JSON file."""

    def test_load_examples_handles_missing_file()
        """Test graceful handling of missing JSON file."""

    def test_load_examples_validates_structure()
        """Test validation of example structure."""

class TestScoringLogic:
    def test_score_app_name_match()
        """Test scoring when app_name matches."""

    def test_score_use_case_match()
        """Test scoring when use_case matches."""

    def test_score_query_keyword_match()
        """Test scoring when query keywords match."""

    def test_score_combined_matches()
        """Test scoring with multiple field matches."""

class TestSearchExamples:
    def test_search_by_app_name()
        """Test searching by app_name filter."""

    def test_search_by_keywords()
        """Test searching by query keywords."""

    def test_search_with_match_mode_all()
        """Test strict AND matching."""

    def test_search_with_match_mode_fuzzy()
        """Test fuzzy matching with fallback."""

    def test_search_returns_top_results()
        """Test result limiting and ranking."""
```

**Approach:**
- Test with subset of real query examples
- Test scoring algorithm correctness
- Test search result relevance

---

### 3.2 `rate_limiter.py` (71% coverage)

**Current:** 49 statements, 14 missing (71% coverage)
**Target:** 90%+ coverage
**Priority:** 🟢 Medium - Rate limiting for API protection

**Missing Coverage:**
- Line 42: `_cleanup_old_requests()` - Cleanup logic
- Line 73: `wait_time_ms` calculation
- Lines 87-90: Log rate limit warning
- Lines 108, 122-129: Edge cases in acquire/release

**Test Tasks:**
```python
# tests/test_rate_limiter.py (EXPAND EXISTING)

class TestRateLimiterAdvanced:
    async def test_cleanup_old_requests()
        """Test old requests are removed from tracking."""

    async def test_wait_time_calculation()
        """Test wait time is calculated correctly when limited."""

    async def test_rate_limit_logging()
        """Test rate limit warnings are logged."""

    async def test_concurrent_acquire()
        """Test multiple concurrent acquire calls."""

    async def test_acquire_release_cycle()
        """Test acquire/release in rapid succession."""
```

---

## Phase 4: Improve Moderate Coverage (Week 6)

### 4.1 `validation.py` (77% coverage)

**Current:** 109 statements, 25 missing (77% coverage)
**Target:** 90%+ coverage
**Priority:** 🟢 Medium - Input validation for security

**Missing Coverage:**
- Lines 44, 49, 53: Query validation edge cases
- Lines 69, 71, 79, 81: Time range validation edge cases
- Lines 94-96, 109, 113: Pagination validation
- Lines 129-139: CollectorValidation
- Lines 151-157: ContentTypeValidation
- Lines 192-193: MonitorSearchValidation

**Test Tasks:**
```python
# tests/test_validation.py (NEW FILE)

class TestQueryValidation:
    def test_validate_empty_query()
        """Test empty query raises ValidationError."""

    def test_validate_query_max_length()
        """Test query exceeding max length is rejected."""

    def test_validate_query_dangerous_patterns()
        """Test potentially dangerous query patterns."""

class TestTimeRangeValidation:
    def test_validate_negative_hours()
        """Test negative hours raises error."""

    def test_validate_zero_hours()
        """Test zero hours raises error."""

    def test_validate_max_hours()
        """Test hours exceeding maximum."""

class TestPaginationValidation:
    def test_validate_negative_offset()
        """Test negative offset raises error."""

    def test_validate_zero_limit()
        """Test zero limit raises error."""

    def test_validate_limit_exceeds_max()
        """Test limit exceeding maximum."""

class TestPydanticValidators:
    def test_collector_validation()
        """Test CollectorValidation model."""

    def test_content_type_validation()
        """Test ContentTypeValidation model."""

    def test_monitor_search_validation()
        """Test MonitorSearchValidation model."""
```

---

### 4.2 `exceptions.py` (68% coverage)

**Current:** 31 statements, 10 missing (68% coverage)
**Target:** 95%+ coverage
**Priority:** 🟢 Medium - Custom exception classes

**Missing Coverage:**
- Lines 14-17: `SumoMCPError.__init__()`
- Lines 44-45: `APIError.__init__()`
- Lines 49-52: `TimeoutError.__init__()`

**Test Tasks:**
```python
# tests/test_exceptions.py (NEW FILE)

class TestExceptions:
    def test_sumo_mcp_error_creation()
        """Test SumoMCPError with message and details."""

    def test_api_error_with_status_code()
        """Test APIError with status_code."""

    def test_authentication_error()
        """Test AuthenticationError creation."""

    def test_validation_error()
        """Test ValidationError creation."""

    def test_timeout_error()
        """Test TimeoutError creation."""

    def test_exception_inheritance()
        """Test exception hierarchy."""

    def test_exception_str_representation()
        """Test string representation of exceptions."""
```

---

## Phase 5: Additional Improvements (Weeks 7-8)

### 5.1 Improve `config.py` (87% → 95%)

**Test Tasks:**
- Test environment variable parsing edge cases
- Test missing required variables
- Test invalid configuration values
- Test multi-instance configuration loading

### 5.2 Improve `audit_helpers.py` (78% → 90%)

**Test Tasks:**
- Test all pre-built use case queries
- Test query builder with all parameter combinations
- Test edge cases in event filtering

### 5.3 Improve `url_builder.py` (81% → 95%)

**Test Tasks:**
- Test subdomain handling edge cases
- Test all region endpoints
- Test query parameter encoding

---

## Testing Infrastructure Improvements

### Mocking Utilities

Create shared mocking utilities to reduce duplication:

```python
# tests/conftest.py (EXPAND)

@pytest.fixture
def mock_sumo_client():
    """Mock SumoLogicClient for testing."""
    client = AsyncMock(spec=SumoLogicClient)
    # Configure common mocks
    return client

@pytest.fixture
def mock_search_job_response():
    """Mock search job response."""
    return {
        "id": "test-job-id",
        "state": "DONE GATHERING RESULTS",
        "messageCount": 100,
        "recordCount": 10
    }

@pytest.fixture
def mock_http_response():
    """Mock httpx response."""
    def _mock(status_code=200, json_data=None):
        response = Mock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        return response
    return _mock
```

### Test Data Files

Create test data files for consistent testing:

```
tests/
  data/
    query_examples_sample.json       # Sample query examples
    search_responses/
      aggregate_response.json         # Sample aggregate query response
      message_response.json          # Sample message query response
    export_responses/
      dashboard_export.json          # Sample dashboard export
      folder_export.json             # Sample folder export
```

### Performance Testing

Add basic performance tests:

```python
# tests/test_performance.py (NEW FILE)

class TestPerformance:
    def test_query_pattern_search_performance()
        """Test search_examples() completes in <100ms."""

    def test_hex_conversion_performance()
        """Test ID conversion completes in <1ms."""

    def test_response_filtering_performance()
        """Test filter_response() with 1000 items."""
```

---

## Success Metrics

### Coverage Targets by Phase

| Phase | Target Coverage | Modules Improved |
|-------|----------------|------------------|
| Phase 1 | 50% overall | 2 (zero-coverage) |
| Phase 2 | 55% overall | 2 (critical modules) |
| Phase 3 | 60% overall | 2 (medium coverage) |
| Phase 4 | 65% overall | 2 (moderate coverage) |
| Phase 5 | 70% overall | 3 (final improvements) |

### Quality Metrics

- ✅ All critical modules (priority 🔴) at 60%+ coverage
- ✅ All high-priority modules (priority 🟡) at 75%+ coverage
- ✅ Zero modules with 0% coverage
- ✅ All utility modules at 90%+ coverage
- ✅ Integration tests run successfully on PRs

### CI/CD Integration

Update GitHub Actions workflow:

```yaml
# .github/workflows/ci.yml

- name: Check coverage thresholds
  run: |
    uv run pytest --cov=src --cov-fail-under=60
    uv run pytest --cov=src/sumologic_mcp_server/validation.py --cov-fail-under=85
    uv run pytest --cov=src/sumologic_mcp_server/response_filter.py --cov-fail-under=90
```

---

## Effort Estimation

| Phase | Effort | Modules | Estimated Hours |
|-------|--------|---------|-----------------|
| Phase 1 | High | 2 | 40 hours |
| Phase 2 | Very High | 2 | 60 hours |
| Phase 3 | Medium | 2 | 30 hours |
| Phase 4 | Low | 2 | 20 hours |
| Phase 5 | Medium | 3 | 30 hours |
| **Total** | | **11 modules** | **180 hours** |

**Timeline:** 8 weeks at ~20-25 hours/week

---

## Implementation Notes

### Test Writing Best Practices

1. **Follow AAA Pattern:** Arrange, Act, Assert
2. **One assertion per test** (when reasonable)
3. **Descriptive test names** that explain the scenario
4. **Use fixtures** for common setup
5. **Mock external dependencies** (HTTP, file I/O, time)
6. **Test edge cases** not just happy paths
7. **Add docstrings** explaining test purpose

### Running Tests During Development

```bash
# Run specific module tests
uv run pytest tests/test_async_export_helper.py -v

# Run with coverage for specific module
uv run pytest tests/test_async_export_helper.py \
  --cov=src/sumologic_mcp_server/async_export_helper.py \
  --cov-report=term-missing

# Watch mode for TDD
uv run pytest-watch tests/test_async_export_helper.py
```

### Updating Documentation

When adding tests:
1. Update `CHANGELOG.md` with coverage improvements
2. Update `README.md` if test running instructions change
3. Update `.github/workflows/ci.yml` if new test categories added

---

**Last Updated:** 2026-03-07
**Status:** Draft - Ready for Review
**Next Steps:**
1. Review and approve plan
2. Create GitHub issues for each phase
3. Assign phases to development sprints
4. Begin Phase 1 implementation
