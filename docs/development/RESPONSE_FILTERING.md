# Response Filtering Implementation

## Overview

Added client-side response filtering to handle large API responses that exceed Claude's 1MB context limit. The `response_filter.py` module provides auto-detection of array keys and flexible filtering capabilities.

**Implementation Date:** 2026-03-04

## Problem Solved

Some Sumo Logic APIs (collectors, dashboards, users, etc.) can return payloads > 1MB when listing all resources. This causes:
- Responses that exceed Claude UI limits
- Inability to work with full result sets
- Poor user experience when searching for specific items

## Solution

### Core Features

1. **Auto-Detection of Array Keys**
   - Automatically finds array key in responses (`data`, `dashboards`, `collectors`, etc.)
   - Works with any Sumo Logic API response format
   - No manual configuration needed

2. **Multiple Filtering Modes**
   - **Field filtering**: Filter by specific field (e.g., `name="prod"`)
   - **Multi-field search**: Search across multiple fields (e.g., search in `name` or `description`)
   - **Custom filtering**: Use lambda functions for complex criteria
   - **Size limits**: Truncate by item count or byte size

3. **Filtering Metadata**
   - Adds `_metadata` object to filtered responses
   - Shows original count, filtered count, returned count
   - Indicates if filtering or truncation occurred
   - Preserves filter criteria for debugging

## Files Created

### src/sumologic_mcp_server/response_filter.py

Main filtering module with functions:

- `find_array_key()` - Auto-detect array key in response
- `filter_by_field()` - Filter items by single field
- `filter_by_multiple_fields()` - Search across multiple fields
- `filter_by_custom()` - Apply custom filter function
- `truncate_response()` - Limit response size
- `filter_response()` - Main filtering entry point
- `get_common_search_fields()` - Get default search fields by type

### tests/test_response_filter.py

Comprehensive test suite with 30 tests covering:
- Array key detection
- Field filtering (case-sensitive, exact match, substring)
- Multi-field search
- Custom filters
- Truncation by size and count
- Integration scenarios

All tests passing ✅

## Integration Pattern

### Example: Enhanced get_sumo_dashboards

```python
@mcp.tool()
async def get_sumo_dashboards(
    limit: int = Field(default=100, description="Maximum number of results"),
    filter_name: Optional[str] = Field(default=None, description="Filter by title"),
    filter_description: Optional[str] = Field(default=None, description="Filter by description"),
    search_term: Optional[str] = Field(default=None, description="Search title and description"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of dashboards with optional client-side filtering."""
    try:
        from .response_filter import filter_response

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_dashboards")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        dashboards = await client.get_dashboards(limit=limit)

        # Resolve Field values when called directly from Python
        filter_name = _resolve_field_value(filter_name)
        filter_description = _resolve_field_value(filter_description)
        search_term = _resolve_field_value(search_term)

        # Apply filtering if requested
        if filter_name:
            dashboards = filter_response(
                dashboards,
                field='title',
                value=filter_name,
                case_sensitive=False
            )
        elif filter_description:
            dashboards = filter_response(
                dashboards,
                field='description',
                value=filter_description,
                case_sensitive=False
            )
        elif search_term:
            dashboards = filter_response(
                dashboards,
                search_term=search_term,
                search_fields=['title', 'description'],
                case_sensitive=False
            )

        return json.dumps(dashboards, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_dashboards")
```

### Helper Function: _resolve_field_value()

Added to `sumologic_mcp_server.py` to handle Field objects when tools are called directly:

```python
def _resolve_field_value(value: Any) -> Any:
    """
    Resolve Pydantic Field values to actual values.

    When tools are called directly from Python (not via MCP), Field() objects
    may be passed instead of actual values. This helper extracts the real value.
    """
    from pydantic.fields import FieldInfo

    if isinstance(value, FieldInfo):
        return value.default if hasattr(value, 'default') else None
    return value
```

## Usage Examples

### Filter Dashboards by Name
```python
# MCP client call
result = await get_sumo_dashboards(filter_name="AWS")

# Response includes metadata
{
  "dashboards": [
    {"id": "...", "title": "AWS CloudTrail", ...},
    {"id": "...", "title": "AWS Lambda", ...}
  ],
  "_metadata": {
    "array_key": "dashboards",
    "original_count": 100,
    "filtered_count": 49,
    "returned_count": 49,
    "was_filtered": true,
    "filter": {
      "field": "title",
      "value": "AWS",
      "case_sensitive": false
    }
  }
}
```

### Search Across Multiple Fields
```python
# Search for "security" in title or description
result = await get_sumo_dashboards(search_term="security")
```

### Custom Filter Example
```python
from src.sumologic_mcp_server.response_filter import filter_response

# Filter for active collectors
result = filter_response(
    collectors_response,
    custom_filter=lambda c: c.get('alive', False) and c.get('collectorType') == 'Installed'
)
```

### Truncate Large Results
```python
# Limit to 50 items even if more match
result = filter_response(
    response,
    field='name',
    value='prod',
    max_items=50
)

# Limit by byte size (stay under 500KB)
result = filter_response(
    response,
    search_term='error',
    search_fields=['name', 'description'],
    max_bytes=500000
)
```

## Performance Results

Real-world test with dashboard API:

| Scenario | Original Size | Filtered Size | Reduction |
|----------|--------------|---------------|-----------|
| All dashboards (100) | 3,200,764 bytes | N/A | N/A |
| Filter "AWS" (49 results) | 3,200,764 bytes | ~1,500,000 bytes | ~53% |
| Filter "APITest" (0 results) | 3,200,764 bytes | 393 bytes | 100% |

**Key Insight:** Even when no results match, filtering prevents massive payload transfers to Claude.

## Applying to Other Tools

To add filtering to other large-response tools:

### 1. Identify Candidate Tools

Tools that return large lists:
- ✅ `get_sumo_dashboards` - Implemented
- 🔄 `get_sumo_collectors` - Should add filtering
- 🔄 `get_sumo_sources` - Consider filtering
- 🔄 `get_sumo_users` - Consider filtering
- 🔄 `list_field_extraction_rules` - Consider filtering
- 🔄 `search_sumo_monitors` - Already has search, could enhance

### 2. Add Optional Filter Parameters

```python
@mcp.tool()
async def get_sumo_collectors(
    limit: int = Field(default=100, description="Maximum number of results"),
    filter_name: Optional[str] = Field(default=None, description="Filter collectors by name"),
    filter_alive: Optional[bool] = Field(default=None, description="Filter by alive status"),
    search_term: Optional[str] = Field(default=None, description="Search name, description, hostName"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
```

### 3. Determine Search Fields

Use `get_common_search_fields()` or define custom fields:

```python
# Auto-detect common fields
search_fields = get_common_search_fields('collectors')
# Returns: ['name', 'description', 'hostName']

# Or specify custom fields
search_fields = ['name', 'category', 'sourceType']
```

### 4. Apply Filtering Logic

```python
# Resolve Field values
filter_name = _resolve_field_value(filter_name)
search_term = _resolve_field_value(search_term)

# Apply filters
if filter_name:
    collectors = filter_response(collectors, field='name', value=filter_name)
elif search_term:
    collectors = filter_response(
        collectors,
        search_term=search_term,
        search_fields=['name', 'description', 'hostName']
    )
```

## Common Search Fields by Type

From `get_common_search_fields()`:

```python
{
    'collectors': ['name', 'description', 'hostName'],
    'sources': ['name', 'description', 'category'],
    'dashboards': ['name', 'description'],  # Uses 'title' in API
    'users': ['firstName', 'lastName', 'email'],
    'monitors': ['name', 'description'],
    'fields': ['fieldName'],
    'rules': ['name', 'scope'],
    'partitions': ['name'],
    'roles': ['name', 'description'],
    'data': ['name', 'title', 'description'],  # Generic fallback
}
```

## Best Practices

### 1. Always Include Metadata
The `_metadata` field helps users understand:
- How many total items exist
- How many matched their filter
- What filter was applied

### 2. Use Descriptive Field Descriptions
```python
# Good
filter_name: Optional[str] = Field(
    default=None,
    description="Filter collectors by name (substring match, case-insensitive)"
)

# Not as good
filter_name: Optional[str] = Field(default=None, description="Filter by name")
```

### 3. Combine Multiple Filter Options
Allow users to choose their preferred filtering method:
- Single field filter (precise)
- Multi-field search (flexible)
- Custom filter (advanced)

### 4. Document in Tool Docstring
```python
"""
Get list of collectors with optional client-side filtering.

Client-side filtering helps when API returns large result sets (>1MB).
Use filter_name or search_term to reduce results.

Filtering Examples:
    - filter_name="prod" - Find collectors with "prod" in name
    - filter_alive=True - Only show active collectors
    - search_term="aws" - Search across name, description, hostname
"""
```

### 5. Test with Real Data
Always test filtering with actual API responses to ensure:
- Correct array key detection
- Expected field names exist
- Size reduction is meaningful

## Limitations

1. **API Limits Still Apply**
   - If API limits result set to 100, filtering can't find item #101
   - May need pagination support in future

2. **Client-Side Only**
   - Filtering happens after API call
   - Doesn't reduce API load or response time
   - Still transfers full response from Sumo Logic

3. **Field Name Sensitivity**
   - Must know correct field names
   - Dashboard API uses `title`, not `name`
   - Requires inspection or documentation

## Future Enhancements

Potential improvements:

1. **Pagination Support**
   - Fetch multiple pages until filter finds N results
   - Combine with filtering for large datasets

2. **Response Caching**
   - Cache full responses locally
   - Apply different filters without re-fetching
   - Useful for exploratory analysis

3. **Advanced Filtering**
   - Regex pattern matching
   - Date range filtering
   - Numeric comparisons (>, <, ==)
   - Boolean operators (AND, OR, NOT)

4. **Filter Presets**
   - Common filter combinations
   - Saved filter templates
   - User-defined filter functions

## Testing

Run response_filter tests:

```bash
uv run pytest tests/test_response_filter.py -v
```

All 30 tests should pass:
- ✅ Array key detection (5 tests)
- ✅ Field filtering (5 tests)
- ✅ Multi-field search (4 tests)
- ✅ Custom filters (2 tests)
- ✅ Truncation (4 tests)
- ✅ Integration (5 tests)
- ✅ Helper functions (3 tests)
- ✅ Integration scenarios (2 tests)

## API References

- Dashboards API: https://api.sumologic.com/docs/#operation/listDashboards
- Collectors API: https://api.sumologic.com/docs/#operation/getCollectors
- Content API: https://api.sumologic.com/docs/#tag/contentManagement

## Related Files

- `src/sumologic_mcp_server/response_filter.py` - Main implementation
- `src/sumologic_mcp_server/sumologic_mcp_server.py` - Integration in tools
- `tests/test_response_filter.py` - Test suite
- `docs/mcp-tools-reference.md` - Tool documentation (needs update)

---

**Status:** ✅ Complete
**Next Steps:**
1. Update `docs/mcp-tools-reference.md` with new dashboard filter parameters
2. Apply filtering pattern to `get_sumo_collectors` tool
3. Consider filtering for `get_sumo_users` and other list tools
