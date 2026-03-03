# Quick Reference Card

Quick lookup for common development tasks in the sumologic-python-mcp project.

## Starting a New Feature

1. Read: `CLAUDE.md` (guidelines) and `.PATTERNS.md` (architecture)
2. Copy: `docs/development/.CHECKLIST_TEMPLATE.md` → `docs/development/FEATURE_NAME.md`
3. Plan: Review API docs, check existing code, plan implementation
4. Branch: `git checkout -b feature/feature-name`

## Adding a New MCP Tool - Quick Steps

```python
# 1. Add API method to SumoLogicClient class (~line 100-500)
async def get_resource(self, param: str) -> Dict[str, Any]:
    """API method docstring."""
    return await self._request("GET", "/path", api_version="v1")

# 2. Add @mcp.tool() (follow category organization)
@mcp.tool()
async def tool_name(
    param: str = Field(description="Description"),
    instance: str = Field(default='default', description="Instance name")
) -> str:
    """Tool docstring with use cases."""
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("tool_name")

        instance = validate_instance_name(instance)
        param = validate_query_input(param)

        client = await get_sumo_client(instance)
        result = await client.get_resource(param)

        return json.dumps(result, indent=2)
    except Exception as e:
        return handle_tool_error(e, "tool_name")
```

## MANDATORY Documentation Updates

**After adding/modifying ANY tool:**

1. **Update `docs/mcp-tools-reference.md`** ← REQUIRED, NO EXCEPTIONS
   - Add/update tool documentation
   - Update tool count (line 4)
   - Update category count if needed
   - Renumber subsequent tools if needed

2. **Update `README.md`** (if significant change)
   - Update tool count
   - Add to Featured Tools if appropriate

3. **Update `CHANGELOG.md`**
   - Add entry under "Unreleased"

## File Locations Quick Reference

| What | Where |
|------|-------|
| All MCP tools | `src/sumologic_mcp_server/sumologic_mcp_server.py` |
| API client methods | `SumoLogicClient` class (same file, ~line 80-500) |
| Configuration | `src/sumologic_mcp_server/config.py` |
| Validation | `src/sumologic_mcp_server/validation.py` |
| URL generation | `src/sumologic_mcp_server/url_builder.py` |
| Content ID utils | `src/sumologic_mcp_server/content_id_utils.py` |
| Async helpers | `src/sumologic_mcp_server/async_export_helper.py` |
| Query patterns | `src/sumologic_mcp_server/query_patterns.py` |
| Unit tests | `tests/test_*.py` |
| Integration tests | `tests/integration/` |
| Tool documentation | `docs/mcp-tools-reference.md` ← PRIMARY DOCS |
| Development notes | `docs/development/*.md` |
| Guidelines | `CLAUDE.md` |
| Architecture | `.PATTERNS.md` |
| Checklist template | `docs/development/.CHECKLIST_TEMPLATE.md` |

## Common Validation Functions

```python
from .validation import (
    validate_instance_name,     # Instance name format
    validate_query_input,        # Query string (max 10k chars)
    validate_time_range,         # Hours (0-8760)
    validate_pagination,         # limit (1-1000), offset (0-100k)
)
```

## Testing Commands

```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_module.py -v

# Run with coverage
uv run pytest --cov=src/sumologic_mcp_server --cov-report=html

# Run specific test
uv run pytest tests/test_module.py::TestClass::test_method -v

# Run integration tests only
uv run pytest tests/integration/ -v
```

## Environment Variables

```bash
# Default instance
SUMO_ACCESS_ID=your_id
SUMO_ACCESS_KEY=your_key
SUMO_ENDPOINT=https://api.sumologic.com
SUMO_SUBDOMAIN=mycompany  # optional

# Named instance: SUMO_<NAME>_<FIELD>
SUMO_PROD_ACCESS_ID=prod_id
SUMO_PROD_ACCESS_KEY=prod_key
SUMO_PROD_ENDPOINT=https://api.us2.sumologic.com
SUMO_PROD_SUBDOMAIN=mycompany-prod
```

## Sumo Logic API Versions by Endpoint

| API Endpoint | Version | Path Example |
|--------------|---------|--------------|
| Search Jobs | v1 | `/api/v1/search/jobs` |
| Collectors & Sources | v1 | `/api/v1/collectors` |
| Users | v1 | `/api/v1/users` |
| Content | v2 | `/api/v2/content` |
| Dashboards | v2 | `/api/v2/dashboards` |
| Roles | v2 | `/api/v2/roles` |
| Metrics | v1 | `/api/v1/metrics/queries` |
| Monitors | v1 | `/api/v1/monitors/search` |
| Partitions | v1 | `/api/v1/partitions` |
| Fields | v1 | `/api/v1/fields` |
| Field Extraction | v1 | `/api/v1/extractionRules` |

## API Endpoint to UI URL Mapping

```python
# Standard regions
api.sumologic.com      → service.sumologic.com
api.au.sumologic.com   → service.au.sumologic.com
api.eu.sumologic.com   → service.eu.sumologic.com
api.us2.sumologic.com  → service.us2.sumologic.com

# With custom subdomain
api.au.sumologic.com + subdomain "mycompany"
  → mycompany.au.sumologic.com
```

## Common Patterns

### Simple GET Tool
```python
@mcp.tool()
async def get_simple(instance: str = 'default') -> str:
    try:
        client = await get_sumo_client(instance)
        result = await client.get_api_method()
        return json.dumps(result, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_simple")
```

### Tool with Time Range
```python
from datetime import datetime, timedelta, timezone

hours_back = validate_time_range(hours_back)
to_time = datetime.now(timezone.utc)
from_time = to_time - timedelta(hours=hours_back)

result = await client.search_logs(
    query=query,
    from_time=from_time.isoformat(),
    to_time=to_time.isoformat()
)
```

### Async Job Tool
```python
from .async_export_helper import poll_export_job

result = await poll_export_job(
    client,
    resource_id,
    is_admin_mode=False,
    max_wait_seconds=300
)
```

## Git Commit Messages

```
feat: add new_tool for discovering X
fix: correct URL generation for dashboards
docs: update tool reference for new_tool
refactor: extract common logic to helper
test: add integration tests for new_tool
chore: update dependencies
```

## Security Checklist

- [ ] No hardcoded credentials
- [ ] All inputs validated
- [ ] Rate limiting applied
- [ ] Audit logging enabled
- [ ] Error messages sanitized (no sensitive data)
- [ ] Read-only operations only
- [ ] Configuration from `.env` only

## Pre-Commit Checklist

- [ ] `docs/mcp-tools-reference.md` updated (MANDATORY)
- [ ] Tool counts updated
- [ ] Tests written and passing
- [ ] No temp files in root directory
- [ ] CHANGELOG.md updated
- [ ] Code follows patterns from `.PATTERNS.md`
- [ ] Security checklist verified

## Common URLs

- **Sumo Logic API Docs**: https://api.sumologic.com/docs/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Project GitHub**: https://github.com/[your-org]/sumologic-python-mcp
- **FastMCP Docs**: https://github.com/jlowin/fastmcp

## Troubleshooting

### Tool not appearing
- Check `@mcp.tool()` decorator
- Verify tool returns `str` (JSON)
- Restart MCP server

### API authentication fails
- Check `.env` file configuration
- Verify `SUMO_ACCESS_ID` and `SUMO_ACCESS_KEY`
- Check endpoint matches region

### Tests fail
- Run `uv sync` to update dependencies
- Check `.env` is configured for tests
- Verify API credentials are valid

### Documentation out of sync
- Review git log: `git log --oneline docs/mcp-tools-reference.md`
- Compare tool count in code vs docs
- Update docs immediately

## Support

- Read: `CLAUDE.md` for detailed guidelines
- Read: `.PATTERNS.md` for architecture patterns
- Review: `docs/development/` for implementation examples
- Check: Git history for similar changes

---

**Remember:** Always update `docs/mcp-tools-reference.md` when adding/modifying tools!

**Last Updated:** 2026-03-04
