# Sumo Logic Content Library MCP Tools - Proposal

## Executive Summary

Based on the Hajime VSCode extension implementation, this document proposes MCP tools for the Sumo Logic Content Library APIs, addressing the complex folder/content API paradigms including:
- Personal folders (fast folder API)
- Global folders (export API with `data` array)
- Admin Recommended folders (export API with `children` array)
- isAdminMode flag behavior differences
- Hex/decimal content ID conversions
- Async export job pattern

## Background: Content Library API Complexity

### API Paradigm Differences

1. **Personal Folder** (`/api/v2/content/folders/personal`)
   - Returns folder with `children` array directly
   - Fast synchronous response
   - User-scoped only

2. **Global Folder** (`/api/v2/content/folders/global`)
   - Requires async export job
   - Uses `data` array instead of `children`
   - Different structure than other folders

3. **Admin Recommended** (`/api/v2/content/folders/adminRecommended`)
   - Requires async export job
   - Uses `children` array
   - Requires admin permissions

4. **Regular Folders** (`/api/v2/content/folders/{id}`)
   - Synchronous folder API
   - Returns `children` array
   - Can specify with/without children

5. **Content Export** (`/api/v2/content/{id}/export`)
   - Async job pattern (POST → poll status → get result)
   - Returns full content structure
   - Supports `isAdminMode` flag

### Key Challenges

- **ID Format**: APIs use hex format (16-char), web UI uses decimal
- **Scope Control**: isAdminMode flag changes what content is returned
- **Async Pattern**: Export requires job creation, polling, and result retrieval
- **Rate Limiting**: Must respect 4 requests/second per access key
- **Inconsistent Structure**: Global uses `data`, others use `children`

## Proposed MCP Tools

### Core Content Library Tools

#### 1. `get_personal_folder`
Get user's personal folder with optional children.

**Parameters:**
- `include_children` (bool, default=True): Include child items
- `instance` (str, default='default'): Instance name

**Returns:** Folder with children array

**Use Cases:**
- Get user's personal library root
- List personal content quickly

---

#### 2. `get_folder_by_id`
Get a specific folder by ID with optional children.

**Parameters:**
- `folder_id` (str): Hex folder ID
- `include_children` (bool, default=True): Include child items
- `instance` (str, default='default'): Instance name

**Returns:** Folder with children array

**Use Cases:**
- Navigate folder hierarchy
- Get specific folder contents

---

#### 3. `get_content_by_path`
Get content item by its library path.

**Parameters:**
- `content_path` (str): Full path (e.g., "/Library/Users/user@email.com/MyFolder")
- `instance` (str, default='default'): Instance name

**Returns:** Content item metadata

**Use Cases:**
- Access content by known path
- Validate path exists

---

#### 4. `get_content_path_by_id`
Get the full library path for a content ID.

**Parameters:**
- `content_id` (str): Hex content ID
- `instance` (str, default='default'): Instance name

**Returns:** `{"path": "/Library/Users/..."}`

**Use Cases:**
- Display content location
- Build breadcrumb navigation

---

#### 5. `export_content`
Export full content structure (dashboards, searches, etc.) with async job handling.

**Parameters:**
- `content_id` (str): Hex content ID
- `is_admin_mode` (bool, default=False): Use admin mode
- `max_wait_seconds` (int, default=300): Max polling time
- `instance` (str, default='default'): Instance name

**Returns:** Full content export including children, search queries, dashboard panels, etc.

**Use Cases:**
- Get complete dashboard/search definition
- Export content for backup
- Deep inspection of content structure

---

#### 6. `export_global_folder`
Export Global folder contents (async).

**Parameters:**
- `is_admin_mode` (bool, default=False): Use admin mode
- `max_wait_seconds` (int, default=300): Max polling time
- `instance` (str, default='default'): Instance name

**Returns:** Global folder with `data` array containing children

**Use Cases:**
- List global/shared content
- Discover organization-wide content

---

#### 7. `export_admin_recommended_folder`
Export Admin Recommended folder (async).

**Parameters:**
- `is_admin_mode` (bool, default=False): Use admin mode
- `max_wait_seconds` (int, default=300): Max polling time
- `instance` (str, default='default'): Instance name

**Returns:** Admin Recommended folder with `children` array

**Use Cases:**
- Access admin-curated content
- Discover best practices content

---

### Content ID Utility Tools

#### 8. `convert_content_id_hex_to_decimal`
Convert hex content ID to decimal format (for web UI URLs).

**Parameters:**
- `hex_id` (str): Hex ID (e.g., "00000000005E5403")

**Returns:** `{"decimal_id": "6181891", "hex_id": "00000000005E5403"}`

**Use Cases:**
- Generate web UI URLs
- Display user-friendly IDs

---

#### 9. `convert_content_id_decimal_to_hex`
Convert decimal content ID to hex format (for API calls).

**Parameters:**
- `decimal_id` (str): Decimal ID (e.g., "6181891")

**Returns:** `{"hex_id": "00000000005E5403", "decimal_id": "6181891"}`

**Use Cases:**
- Convert web UI IDs to API format
- Normalize ID input

---

#### 10. `get_content_web_url`
Generate web UI URL for content item.

**Parameters:**
- `content_id` (str): Hex or decimal content ID
- `instance` (str, default='default'): Instance name

**Returns:** `{"url": "https://instance.sumologic.com/library/6181891"}`

**Use Cases:**
- Share content links
- Open content in browser

---

### Advanced Navigation Tools

#### 11. `search_content_by_name`
Search for content items by name pattern.

**Parameters:**
- `name_pattern` (str): Name search pattern (supports wildcards)
- `content_types` (list[str], optional): Filter by types (Dashboard, Search, Folder, etc.)
- `scope` (str, default='all'): Search scope (personal, global, adminRecommended, all)
- `limit` (int, default=100): Max results
- `instance` (str, default='default'): Instance name

**Returns:** Array of matching content items

**Use Cases:**
- Find content by name
- Discover similar content

---

#### 12. `list_content_tree`
Get hierarchical tree structure from a folder root.

**Parameters:**
- `root_folder_id` (str, optional): Root folder hex ID (defaults to personal)
- `max_depth` (int, default=3): Maximum depth to traverse
- `include_content` (bool, default=True): Include non-folder items
- `instance` (str, default='default'): Instance name

**Returns:** Hierarchical tree structure with nested children

**Use Cases:**
- Visualize folder structure
- Export folder hierarchy
- Build navigation trees

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Deliverables:**
1. Content ID conversion utilities module (`content_id_utils.py`)
   - hex_to_decimal()
   - decimal_to_hex()
   - format_content_id()
   - is_valid_hex_id()
   - normalize_to_hex()

2. Async export polling helper (`async_export_helper.py`)
   - poll_export_job()
   - Handles InProgress → Success/Failed states
   - Configurable polling interval and timeout

3. Update SumoLogicClient with content methods:
   - get_personal_folder()
   - get_folder()
   - get_content_by_path()
   - get_content_path()
   - begin_async_export()
   - get_export_status()
   - get_export_result()

**Reference Code:** `/Users/rjury/Documents/sumo2024/Hajime/src/api/content.ts`

---

### Phase 2: Basic Content Tools (Week 2)

**Deliverables:**
1. Implement MCP tools 1-4 (synchronous folder/content operations)
2. Add proper error handling for 403, 404, 429 responses
3. Add rate limiting (max 4 req/sec)
4. Unit tests for each tool

**Tests:**
- Test personal folder retrieval
- Test folder navigation
- Test path-based content lookup
- Test error scenarios

---

### Phase 3: Export & Async Tools (Week 3)

**Deliverables:**
1. Implement MCP tools 5-7 (async export operations)
2. Implement polling logic with timeout
3. Handle Global folder `data` array vs `children` array
4. Add progress indicators for long-running exports
5. Integration tests with real API

**Tests:**
- Test export job lifecycle
- Test Global folder special handling
- Test Admin Recommended folder
- Test timeout behavior

---

### Phase 4: Utility & Navigation Tools (Week 4)

**Deliverables:**
1. Implement MCP tools 8-12 (ID conversion, search, tree)
2. Add web URL generation
3. Implement content search
4. Implement hierarchical tree builder
5. Documentation and examples

**Tests:**
- Test ID conversions
- Test URL generation
- Test search functionality
- Test tree traversal

---

## Python Implementation Reference

### Content ID Conversion Module

```python
# src/sumologic_mcp_server/content_id_utils.py

def hex_to_decimal(hex_id: str) -> str:
    """Convert hex content ID to decimal string."""
    if not hex_id or not isinstance(hex_id, str):
        raise ValueError("Invalid hex ID: must be non-empty string")

    clean_hex = hex_id.strip().replace('0x', '').replace('0X', '')

    if not all(c in '0123456789ABCDEFabcdef' for c in clean_hex):
        raise ValueError(f"Invalid hex format: {hex_id}")

    return str(int(clean_hex, 16))


def decimal_to_hex(decimal_id: str) -> str:
    """Convert decimal content ID to hex string (16-char padded)."""
    if not decimal_id or not isinstance(decimal_id, str):
        raise ValueError("Invalid decimal ID: must be non-empty string")

    clean_decimal = decimal_id.strip()

    if not clean_decimal.isdigit():
        raise ValueError(f"Invalid decimal format: {decimal_id}")

    hex_val = hex(int(clean_decimal))[2:].upper()
    return hex_val.zfill(16)


def format_content_id(hex_id: str) -> str:
    """Format ID as 'HEX (decimal)'."""
    try:
        decimal = hex_to_decimal(hex_id)
        return f"{hex_id} ({decimal})"
    except ValueError:
        return hex_id
```

### Async Export Helper

```python
# src/sumologic_mcp_server/async_export_helper.py

import asyncio
from typing import Callable, Awaitable, Dict, Any

async def poll_export_job(
    job_id: str,
    content_id: str,
    get_status_func: Callable[[str, str], Awaitable[Dict[str, Any]]],
    get_result_func: Callable[[str, str], Awaitable[Dict[str, Any]]],
    max_wait_seconds: int = 300,
    poll_interval_seconds: int = 2
) -> Dict[str, Any]:
    """
    Poll async export job until completion.

    Args:
        job_id: Export job ID
        content_id: Content ID being exported
        get_status_func: Async function to check job status
        get_result_func: Async function to get job result
        max_wait_seconds: Maximum time to wait
        poll_interval_seconds: Seconds between polls

    Returns:
        Export result dictionary

    Raises:
        TimeoutError: If job doesn't complete in time
        APIError: If job fails
    """
    max_attempts = max_wait_seconds // poll_interval_seconds

    for attempt in range(max_attempts):
        await asyncio.sleep(poll_interval_seconds)

        status_response = await get_status_func(content_id, job_id)

        if 'error' in status_response:
            raise APIError(status_response['error'])

        status = status_response.get('status')

        if status == 'Success':
            return await get_result_func(content_id, job_id)

        if status == 'Failed':
            error_msg = status_response.get('error') or status_response.get('statusMessage', 'Export failed')
            raise APIError(f"Export job failed: {error_msg}")

        # Continue polling if InProgress

    raise TimeoutError(f"Export job {job_id} timed out after {max_wait_seconds}s")
```

### MCP Tool Example

```python
# src/sumologic_mcp_server/sumologic_mcp_server.py

@mcp.tool()
async def get_personal_folder(
    include_children: bool = True,
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Get user's personal folder with optional children.

    This is the fastest way to access personal library content as it uses
    a synchronous folder API rather than async export.
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_personal_folder")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Construct URL with query param
        url = "/content/folders/personal"
        if not include_children:
            url += "?includeChildren=false"

        result = await client._request("GET", url, api_version="v2")

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_personal_folder")


@mcp.tool()
async def export_content(
    content_id: str = Field(description="Hex content ID to export"),
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Export full content structure with async job handling.

    This tool handles the complete async export workflow:
    1. Start export job
    2. Poll for completion
    3. Return result

    Use this for dashboards, searches, and other content types to get
    their full definition including nested structures.
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_content")

        instance = validate_instance_name(instance)
        content_id = validate_content_id(content_id)

        client = await get_sumo_client(instance)

        # Start export job
        params = {}
        if is_admin_mode:
            params['isAdminMode'] = 'true'

        job_response = await client._request(
            "POST",
            f"/content/{content_id}/export",
            api_version="v2",
            params=params
        )

        job_id = job_response['id']

        # Poll for completion
        result = await poll_export_job(
            job_id=job_id,
            content_id=content_id,
            get_status_func=lambda cid, jid: client._request(
                "GET",
                f"/content/{cid}/export/{jid}/status",
                api_version="v2"
            ),
            get_result_func=lambda cid, jid: client._request(
                "GET",
                f"/content/{cid}/export/{jid}/result",
                api_version="v2"
            ),
            max_wait_seconds=max_wait_seconds
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_content")


@mcp.tool()
async def convert_content_id_hex_to_decimal(
    hex_id: str = Field(description="Hex content ID (e.g., 00000000005E5403)")
) -> str:
    """
    Convert hex content ID to decimal format for web UI URLs.

    Sumo Logic stores content IDs as 16-character hex strings but the
    web UI uses decimal format in URLs.
    """
    try:
        from .content_id_utils import hex_to_decimal

        decimal_id = hex_to_decimal(hex_id)

        return json.dumps({
            "hex_id": hex_id,
            "decimal_id": decimal_id,
            "formatted": f"{hex_id} ({decimal_id})"
        }, indent=2)

    except Exception as e:
        return handle_tool_error(e, "convert_content_id_hex_to_decimal")
```

## Testing Strategy

### Unit Tests
- Content ID conversions (hex ↔ decimal)
- Export polling logic
- Error handling (403, 404, 429)
- Rate limiting

### Integration Tests
- Personal folder retrieval
- Folder navigation
- Content export end-to-end
- Global folder special handling
- Admin Recommended folder
- Search functionality
- Tree traversal

### Manual Testing Checklist
- [ ] Get personal folder with/without children
- [ ] Navigate multi-level folder hierarchy
- [ ] Export dashboard content
- [ ] Export search content
- [ ] Export Global folder (verify `data` array)
- [ ] Export Admin Recommended (verify `children` array)
- [ ] Convert IDs hex ↔ decimal
- [ ] Generate web URLs
- [ ] Search content by name
- [ ] Build content tree
- [ ] Handle 404 for missing content
- [ ] Handle 403 for insufficient permissions
- [ ] Handle 429 rate limiting
- [ ] Verify isAdminMode flag behavior

## Configuration Settings

```python
# Add to server config
library_config = {
    "export_max_wait_seconds": 300,  # 5 minutes
    "export_poll_interval": 2,  # seconds
    "content_search_limit": 100,
    "tree_max_depth": 5,
}
```

## Benefits of This Approach

1. **Addresses Real Complexity**: Handles all the API inconsistencies identified in Hajime
2. **Reuses Proven Patterns**: Leverages working code from production VSCode extension
3. **Progressive Enhancement**: Can implement in phases
4. **Comprehensive Coverage**: Covers all major content library use cases
5. **User-Friendly**: Provides both low-level and high-level tools

## References

- Hajime Project: `/Users/rjury/Documents/sumo2024/Hajime`
- Implementation Plan: `docs/library-explorer-implementation-plan.md`
- Content API Client: `src/api/content.ts`
- Content ID Utils: `src/utils/contentId.ts`
- Sumo Logic Content API Docs: https://api.sumologic.com/docs/#tag/contentManagement

---

**Document Version**: 1.0
**Created**: 2026-02-26
**Author**: Claude (AI Assistant)
