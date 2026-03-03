# Claude Development Guidelines

This document provides guidelines for AI-assisted development (specifically Claude) to ensure consistency, quality, and repeatability in the sumologic-python-mcp project.

## Project Structure

```
sumologic-python-mcp/
├── src/sumologic_mcp_server/     # Main source code
│   ├── sumologic_mcp_server.py   # Main MCP server with all @mcp.tool() definitions
│   ├── config.py                 # Configuration and multi-instance support
│   ├── validation.py             # Input validation using Pydantic
│   ├── exceptions.py             # Custom exception classes
│   ├── rate_limiter.py           # Rate limiting implementation
│   ├── async_export_helper.py    # Async job polling helpers
│   ├── content_id_utils.py       # Content ID conversion utilities
│   ├── url_builder.py            # URL generation for web UI
│   ├── search_helpers.py         # Search-related helper functions
│   └── query_patterns.py         # Query pattern matching and examples
├── tests/                        # Test files mirroring src/ structure
│   ├── test_*.py                 # Unit and integration tests
│   └── integration/              # Integration tests
├── docs/                         # Documentation
│   ├── mcp-tools-reference.md    # ** PRIMARY TOOL DOCUMENTATION **
│   ├── development/              # Development notes and summaries
│   └── *.md                      # Feature proposals and guides
├── README.md                     # Main project documentation
├── CLAUDE.md                     # This file - development guidelines
├── .PATTERNS.md                  # Architecture patterns and standards
├── .env.example                  # Configuration template
└── pyproject.toml               # Project dependencies and metadata
```

## Core Principles

### 1. Read-Only Operations
- **NEVER** implement write, update, or delete operations
- All MCP tools must be read-only GET requests
- Exception: POST only for async job creation (export jobs, etc.)

### 2. Centralized API Access
- **ALL** Sumo Logic API calls go through `SumoLogicClient` class
- **NEVER** create direct HTTP calls in tool functions
- Add new API methods to `SumoLogicClient` before using them in tools

### 3. Multi-Instance Support
- All tools must accept `instance` parameter (default='default')
- Use `get_config()` and `get_sumo_client(instance)` pattern
- Test with multiple instances when possible

### 4. Security First
- Use validation functions from `validation.py` for all inputs
- Apply rate limiting with `get_rate_limiter()`
- Log all operations via audit logger when enabled

## Development Workflow

### Adding a New MCP Tool

Follow this **EXACT SEQUENCE** for every new tool:

#### 1. Plan the Tool
- [ ] Review Sumo Logic API documentation
- [ ] Check if similar functionality exists in existing tools
- [ ] Determine if new helper modules are needed
- [ ] Document expected inputs/outputs

#### 2. Add API Method to SumoLogicClient
```python
# In src/sumologic_mcp_server/sumologic_mcp_server.py
# Add to SumoLogicClient class (~line 80-500)

async def get_new_resource(self, param1: str, param2: int = 100) -> Dict[str, Any]:
    """
    Get resource from Sumo Logic API.

    Args:
        param1: Description
        param2: Description with default

    Returns:
        API response dictionary
    """
    params = {"param1": param1, "limit": param2}
    return await self._request("GET", "/api/path", api_version="v1", params=params)
```

#### 3. Implement the MCP Tool
```python
# In src/sumologic_mcp_server/sumologic_mcp_server.py
# Add after existing tools in appropriate category section

@mcp.tool()
async def new_tool_name(
    param1: str = Field(description="Clear description of parameter"),
    param2: int = Field(default=100, description="Parameter with default"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Brief one-line description.

    Detailed description explaining:
    - What the tool does
    - When to use it
    - What data it returns

    Example usage scenarios and results.
    """
    try:
        # 1. Initialize config and rate limiting
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("new_tool_name")

        # 2. Validate inputs
        instance = validate_instance_name(instance)
        param1 = validate_query_input(param1)  # or appropriate validator

        # 3. Get client and make API call
        client = await get_sumo_client(instance)
        result = await client.get_new_resource(param1, param2)

        # 4. Return formatted JSON
        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "new_tool_name")
```

#### 4. **MANDATORY**: Update docs/mcp-tools-reference.md

**THIS STEP IS REQUIRED - DO NOT SKIP**

```markdown
### N. `new_tool_name`
Brief description.

**Parameters:**
- `param1` (str) - Description
- `param2` (int, default=100) - Description
- `instance` (str, default='default') - Instance name

**Returns:** Description of return structure

**Example:** Example output or URL

**Use Cases:**
- Use case 1
- Use case 2
- Use case 3

**API Reference:** https://api.sumologic.com/docs/#operation/operationId

---
```

**After adding the tool:**
1. Update the tool count in the header (line 4)
2. Update the category count if adding to existing category
3. Renumber all subsequent tools if needed
4. Update README.md tool count if it changed significantly

#### 5. Write Tests
```python
# In tests/test_new_module.py or tests/integration/test_integration.py

def test_new_tool_basic():
    """Test basic functionality."""
    # Test implementation
    pass

def test_new_tool_with_custom_params():
    """Test with various parameters."""
    pass

def test_new_tool_error_handling():
    """Test error conditions."""
    pass
```

#### 6. Run Tests and Validation
```bash
# Run specific test
uv run pytest tests/test_new_module.py -v

# Run all tests
uv run pytest -v

# Type checking (if implemented)
uv run mypy src/sumologic_mcp_server/
```

#### 7. Update Supporting Documentation
- [ ] Update README.md if tool is significant/featured
- [ ] Add to CHANGELOG.md under "Unreleased" section
- [ ] Create `docs/development/FEATURE_NAME.md` if complex feature

### Modifying Existing Tools

When updating an existing tool:

1. [ ] Update the tool code in `sumologic_mcp_server.py`
2. [ ] **MANDATORY**: Update `docs/mcp-tools-reference.md`
3. [ ] Update tests if behavior changed
4. [ ] Add entry to CHANGELOG.md
5. [ ] If parameters changed, update `.env.example` if relevant

## Documentation Standards

### Tool Documentation Requirements

Every tool in `docs/mcp-tools-reference.md` MUST have:
- Tool number and name
- Brief description (1-2 sentences)
- **Parameters** section with types and descriptions
- **Returns** section describing output structure
- **Use Cases** section (3-5 bullet points)
- **Example** showing typical output or usage
- **API Reference** link to Sumo Logic API docs (when applicable)

### Development Documentation

Create `docs/development/FEATURE_NAME.md` when:
- Adding complex feature requiring multiple tools
- Significant refactoring or architecture changes
- Implementation requires explanation for future developers
- Feature has multiple phases or components

**Template:**
```markdown
# Feature Name

## Overview
Brief description of what was implemented and why.

## Implementation Details
Technical details, design decisions, code locations.

## Files Modified/Created
- List of files with brief description of changes

## Testing
How to test the feature.

## API References
Links to relevant Sumo Logic API documentation.
```

### Code Comments

```python
# Good: Explains WHY, not WHAT
# Use receipt time for real-time data to avoid ingestion delays
by_receipt_time = True

# Bad: Explains WHAT (obvious from code)
# Set by_receipt_time to True
by_receipt_time = True
```

## Anti-Patterns to Avoid

### ❌ DO NOT DO THESE THINGS

1. **DO NOT** create temporary `.md` files in project root
   - Use `docs/development/` for all development notes
   - Delete working files after incorporating into permanent docs

2. **DO NOT** add tools without updating `docs/mcp-tools-reference.md`
   - This is the #1 cause of documentation drift
   - Update docs in the SAME commit/session as tool code

3. **DO NOT** make direct HTTP requests in tool functions
   - Always add methods to `SumoLogicClient` class
   - Reuse existing client methods when possible

4. **DO NOT** skip validation
   - Always validate inputs using `validation.py` functions
   - Add new validators if needed

5. **DO NOT** hardcode API endpoints or URLs
   - Use configuration from `.env` and `config.py`
   - Use `url_builder.py` for web UI URLs

6. **DO NOT** create separate tool files
   - All tools live in `sumologic_mcp_server.py`
   - Helper functions go in separate modules (e.g., `search_helpers.py`)

7. **DO NOT** forget rate limiting
   - Every tool must call `await limiter.acquire("tool_name")`
   - This prevents API abuse and ensures fair usage

8. **DO NOT** return raw Python objects
   - Always return JSON strings: `return json.dumps(result, indent=2)`
   - Use `handle_tool_error(e, "tool_name")` for exceptions

## File Organization Rules

### Where Code Goes

| Code Type | Location | Example |
|-----------|----------|---------|
| MCP tool definitions | `sumologic_mcp_server.py` | `@mcp.tool() async def search_sumo_logs()` |
| API client methods | `SumoLogicClient` class in `sumologic_mcp_server.py` | `async def get_dashboards()` |
| Validation logic | `validation.py` | `validate_time_range()` |
| Configuration | `config.py` | `SumoInstanceConfig` |
| Utility functions | Separate module in `src/sumologic_mcp_server/` | `url_builder.py` |
| Async helpers | `async_export_helper.py` | `poll_export_job()` |
| Tests | `tests/test_*.py` | `test_search_logs()` |

### Module Responsibilities

**sumologic_mcp_server.py**
- MCP server initialization
- `SumoLogicClient` class with all API methods
- All `@mcp.tool()` definitions
- Tool-specific helper functions (if small)
- Error handling with `handle_tool_error()`

**config.py**
- Environment variable loading
- Multi-instance configuration
- Validation of configuration values
- Centralized configuration access

**validation.py**
- Input validation functions
- Pydantic models for complex validation
- Validation error messages

**url_builder.py**
- API endpoint to UI URL conversion
- URL generation for web UI (library, dashboard, search)
- Region/subdomain handling

**content_id_utils.py**
- Hex ↔ Decimal content ID conversion
- Content ID validation
- ID format normalization

**search_helpers.py**
- Search-specific helper functions
- Query parsing and manipulation
- Search result formatting

**query_patterns.py**
- Query pattern definitions
- Example query database
- Pattern matching logic

**async_export_helper.py**
- Async job polling
- Export job status checking
- Result retrieval with retry logic

## Testing Standards

### Test Structure
```python
"""Tests for module_name functionality."""

import pytest
from src.sumologic_mcp_server.module_name import function_name


class TestFunctionName:
    """Tests for function_name."""

    def test_basic_functionality(self):
        """Test basic use case."""
        result = function_name("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test edge case behavior."""
        # Test implementation

    def test_error_handling(self):
        """Test error conditions."""
        with pytest.raises(ValueError):
            function_name("invalid")
```

### Test Requirements
- Unit tests for all utility functions
- Integration tests for critical tools (when possible)
- Test error handling and edge cases
- Use descriptive test names
- Group related tests in classes

## Git Commit Guidelines

### Commit Message Format
```
<type>: <short description>

<optional longer description>
<optional issue references>
```

### Types
- `feat`: New feature or tool
- `fix`: Bug fix
- `docs`: Documentation updates
- `refactor`: Code refactoring
- `test`: Test additions or updates
- `chore`: Maintenance tasks

### Examples
```bash
feat: add search_query_examples tool for pattern discovery

- Implements tool to search 11k+ query examples
- Adds query_patterns.py with pattern database
- Updates docs/mcp-tools-reference.md with tool #10
- Adds tests for pattern matching

fix: correct dashboard URL generation in get_content_web_url

- Dashboard URLs now use dashboard/{id} format instead of library/{id}
- Fetches dashboard unique ID from export API
- Updates url_builder.py with build_dashboard_url()

docs: update mcp-tools-reference.md for new URL tools

- Document build_search_web_url tool
- Update get_content_web_url documentation
- Add subdomain configuration examples
```

## Security Checklist

Before committing any code:

- [ ] All inputs are validated using `validation.py`
- [ ] No hardcoded credentials or tokens
- [ ] Rate limiting applied with `get_rate_limiter()`
- [ ] Audit logging enabled for API calls
- [ ] Error messages don't leak sensitive information
- [ ] Only read-only operations implemented
- [ ] Configuration comes from `.env` file

## Common Patterns

### Pattern 1: Simple API Tool
```python
@mcp.tool()
async def get_simple_resource(
    instance: str = Field(default='default', description="Instance name")
) -> str:
    """Get simple resource from Sumo Logic."""
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_simple_resource")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)
        result = await client.get_simple_resource_api()

        return json.dumps(result, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_simple_resource")
```

### Pattern 2: Complex Query Tool with Time Range
```python
@mcp.tool()
async def query_with_time_range(
    query: str = Field(description="Query"),
    hours_back: int = Field(default=24, description="Hours to search back"),
    instance: str = Field(default='default', description="Instance name")
) -> str:
    """Execute query with time range."""
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("query_with_time_range")

        instance = validate_instance_name(instance)
        query = validate_query_input(query)
        hours_back = validate_time_range(hours_back)

        # Calculate time range
        to_time = datetime.now(timezone.utc)
        from_time = to_time - timedelta(hours=hours_back)

        client = await get_sumo_client(instance)
        result = await client.search_logs(
            query=query,
            from_time=from_time.isoformat(),
            to_time=to_time.isoformat()
        )

        return json.dumps(result, indent=2)
    except Exception as e:
        return handle_tool_error(e, "query_with_time_range")
```

### Pattern 3: Async Job with Polling
```python
@mcp.tool()
async def export_async_resource(
    resource_id: str = Field(description="Resource ID"),
    max_wait_seconds: int = 300,
    instance: str = Field(default='default', description="Instance name")
) -> str:
    """Export resource with async job polling."""
    try:
        from .async_export_helper import poll_export_job

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_async_resource")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        result = await poll_export_job(
            client,
            resource_id,
            is_admin_mode=False,
            max_wait_seconds=max_wait_seconds
        )

        return json.dumps(result, indent=2)
    except Exception as e:
        return handle_tool_error(e, "export_async_resource")
```

## Session Checklist

At the end of each Claude session:

- [ ] All new tools documented in `docs/mcp-tools-reference.md`
- [ ] Tool count updated in `docs/mcp-tools-reference.md` header
- [ ] Tool count updated in `README.md` if changed significantly
- [ ] Tests written and passing
- [ ] No temporary `.md` files in project root
- [ ] CHANGELOG.md updated with changes
- [ ] `.env.example` updated if new config options added
- [ ] All code follows established patterns
- [ ] Security checklist items verified

## Getting Help

### Sumo Logic API References
- Main API Docs: https://api.sumologic.com/docs/
- API Getting Started: https://help.sumologic.com/docs/api/
- Search Job API: https://api.sumologic.com/docs/#tag/searchJobManagement
- Content API: https://api.sumologic.com/docs/#tag/contentManagement

### Project Resources
- Main documentation: `docs/mcp-tools-reference.md`
- Architecture patterns: `.PATTERNS.md`
- Development notes: `docs/development/`
- Example queries: See `query_patterns.py`

## Version Control

### What to Commit
- Source code changes
- Test files
- Documentation updates
- Configuration examples (`.env.example`)
- CHANGELOG.md updates

### What NOT to Commit
- `.env` file (contains secrets)
- `__pycache__/` directories
- `.pytest_cache/` directories
- `.venv/` virtual environments
- Temporary development notes
- IDE-specific files (unless in `.gitignore`)

See `.gitignore` for complete list.

---

**Last Updated:** 2026-03-04
**Version:** 1.0.0
