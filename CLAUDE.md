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

## Skills Reference

Before performing common tasks, consult the relevant skill in `skills/`. Skills capture **how to accomplish tasks** using MCP tools and Sumo Logic best practices.

### Query & Search Tasks

- **Before writing Sumo Logic queries**: Read [skills/search-write-queries.md](skills/search-write-queries.md)
  - 5-phase query construction pattern (Scope → Parse → Filter → Aggregate → Format)
  - Dashboard panel patterns and complete examples
- **Before optimizing slow/expensive queries**: Read [skills/search-optimize-queries.md](skills/search-optimize-queries.md)
  - Scope optimization techniques for 10x-100x cost reduction
  - Anti-patterns to avoid
- **Before using scheduled views**: Read [skills/search-optimize-with-views.md](skills/search-optimize-with-views.md)
  - Transform raw log queries to use pre-aggregated views
  - Achieve dramatic performance and cost improvements
- **For interactive UI investigation**: Read [skills/ui-navigate-and-search.md](skills/ui-navigate-and-search.md)
  - Field Browser, Log Inspector, histogram features
  - Iterative workflow patterns

### Discovery Tasks

- **Before helping users find logs**: Read [skills/discovery-logs-without-metadata.md](skills/discovery-logs-without-metadata.md)
  - Multi-phase discovery when metadata is unknown
  - Collector/partition/schema exploration
- **Before working with scheduled views**: Read [skills/discovery-scheduled-views.md](skills/discovery-scheduled-views.md)
  - Inventory views, understand schemas, match to use cases
  - Query patterns for versioned views

### Cost Analysis Tasks

- **Before analyzing search costs**: Read [skills/cost-analyze-search-costs.md](skills/cost-analyze-search-costs.md)
  - Flex/Infrequent tier scan cost breakdown
  - User/query cost ranking

### Audit & Compliance Tasks

- **Before searching audit indexes**: Read [skills/audit-user-activity.md](skills/audit-user-activity.md) or [skills/audit-system-health.md](skills/audit-system-health.md)
  - Audit events vs system events vs search audit
  - Pre-built use cases and query patterns

### Content Management Tasks

- **Before navigating content library**: Read [skills/content-library-navigation.md](skills/content-library-navigation.md)
  - Export dashboards, searches, folders
  - Path resolution and URL generation

### Development Tasks

- **Before adding new MCP tools**: Review patterns in existing skills to understand tool usage
- **After adding tools**: Update related skills per "Skills Library Maintenance" section below
- **For skill overview**: See [skills/README.md](skills/README.md) index

**Quick Access:** Use the `get_skill` MCP tool to fetch skill content dynamically.

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

## Code Quality Standards

### Linting and Formatting

**Run these checks before committing:**

```bash
# Format code with Black (required - CI will fail if not formatted)
uv run black src/ tests/

# Check and fix linting issues with Ruff
uv run ruff check src/ tests/ --fix

# Security scan with Bandit
uv run bandit -r src/
```

### Ruff Configuration

Project uses Ruff for linting with these important rules:

**Enabled checks:**

- `E/W` - pycodestyle (PEP 8 compliance)
- `F` - pyflakes (unused imports, undefined names)
- `I` - isort (import sorting)
- `B` - flake8-bugbear (common bugs)
- `C4` - flake8-comprehensions (list/dict comprehension improvements)
- `UP` - pyupgrade (Python version upgrades)

**Intentionally ignored:**

- `E501` - Line too long (handled by Black)
- `B008` - Function calls in argument defaults (required for FastMCP Field())
- `B007` - Loop control variable not used (common in polling loops)
- `B904` - Exception chaining with `from` (intentionally omitted for API errors)

**Test-specific allowances:**

- `B017` - Allow `pytest.raises(Exception)` in tests
- `C416` - Allow list comprehensions in tests

### Exception Handling Best Practices

**DO:** Use specific exception types

```python
try:
    await client.delete_search_job(job_id)
except Exception:  # noqa: S110
    pass  # Best effort cleanup
```

**DON'T:** Use bare except clauses

```python
# WRONG - Bandit security warning B110, Ruff E722
try:
    await client.delete_search_job(job_id)
except:  # ❌ Catches SystemExit, KeyboardInterrupt, etc.
    pass
```

**DO:** Use exception chaining when re-raising

```python
try:
    result = parse_config(data)
except ValueError as e:
    raise ValidationError("Invalid config") from e
```

**Exception to B904 rule:**
When catching and re-raising API errors, we intentionally don't chain exceptions to avoid exposing internal error details to clients. This is documented with `# noqa: B904` or globally ignored in `pyproject.toml`.

### Loop Variables Best Practices

**DO:** Use `_` for unused loop variables when appropriate

```python
# If attempt number doesn't matter
for _ in range(max_attempts):
    if await check_status():
        break
    await asyncio.sleep(poll_interval)
```

**ACCEPTABLE:** Don't use loop variable in polling loops (B007)

```python
# Polling loop where we just need N attempts
for attempt in range(max_attempts):  # noqa: B007
    status = await client.get_job_status(job_id)
    if status == "COMPLETE":
        break
    await asyncio.sleep(5)
```

The project globally ignores B007 because polling loops are common in async API clients.

### Security: Bandit Compliance

Bandit scans for security issues. Address these common warnings:

**B110: Try/Except/Pass**

```python
# BAD - Silent failures hide problems
try:
    dangerous_operation()
except:
    pass

# GOOD - Specific exception, with noqa if intentional
try:
    await client.delete_search_job(job_id)
except Exception:  # noqa: S110
    pass  # Best effort cleanup - job deletion failure is acceptable
```

**B608: SQL Injection**

- Not applicable - this project uses REST APIs, not SQL

**General security rules:**

- Never hardcode credentials
- Always validate user input
- Use rate limiting
- Log security-relevant events

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

## Pre-Commit Checklist

Before committing any code:

**Code Quality:**

- [ ] Code formatted with `uv run black src/ tests/`
- [ ] Linting passes with `uv run ruff check src/ tests/`
- [ ] No bare `except:` clauses (use `except Exception:` with `# noqa: S110`)
- [ ] Security scan passes with `uv run bandit -r src/`
- [ ] All tests pass with `uv run pytest`

**Security:**

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

## Skills Library Maintenance

The `skills/` directory contains portable skill definitions for use with Claude Code and other LLM systems. These skills capture **how to accomplish tasks** using the MCP tools and Sumo Logic knowledge.

### When to Update Skills

**Update existing skills when:**

- Adding new MCP tools that enhance existing capabilities
- Discovering optimization patterns or best practices
- Finding common pitfalls users encounter
- Tools change parameters or behavior

**Create new skills when:**

- Adding entirely new capability areas (e.g., new audit index)
- Implementing complex multi-step workflows
- Discovering reusable patterns not covered by existing skills

### Skill Maintenance Workflow

When adding or modifying tools:

1. **Review Related Skills**
   - Check `skills/README.md` index for related skills
   - Determine if existing skills need updates

2. **Update Existing Skills**
   - Add new tool references to "MCP Tools Used" section
   - Update examples if tool provides better approach
   - Add new patterns to "Query Patterns" section
   - Update "Common Pitfalls" if tool prevents mistakes

3. **Create New Skill (if needed)**
   - Follow template in `skills/README.md`
   - Include: Intent, Prerequisites, Context, Approach, Patterns, Examples, Pitfalls
   - Cross-reference related skills
   - Add to skills index in `skills/README.md`

4. **Validate Skill Quality**
   - Skill is actionable (not just reference)
   - Includes real examples with MCP tool calls
   - Explains "why" not just "what"
   - Has clear success criteria

### Skills Organization

Skills are domain-organized:

- `discovery-*.md` - Finding logs and understanding structure
- `cost-*.md` - Cost analysis and optimization
- `search-*.md` - Query building and optimization
- `audit-*.md` - Audit indexes and compliance
- `content-*.md` - Content library management
- `admin-*.md` - Administration and configuration

### Skill Template

```markdown
# Skill: [Name]

## Intent
What this skill accomplishes (1-2 sentences)

## Prerequisites
- Knowledge/access requirements

## Context
**Use this skill when:** ...
**Don't use this when:** ...

## Approach
Step-by-step methodology with MCP tool calls

## Query Patterns
Reusable query building blocks

## Examples
Real-world scenarios with solutions

## Common Pitfalls
Mistakes to avoid

## Related Skills
Cross-references

## MCP Tools Used
List of tools with brief purpose

## API References
Links to official docs
```

### Example: Adding Tool to Existing Skill

When adding `new_search_tool` that helps with query optimization:

1. Update `skills/search-optimize-queries.md`:

   ```markdown
   ### New Optimization Pattern

   **MCP Tool:** `new_search_tool`
   ```json
   {
     "parameter": "value"
   }
   ```

   **Use Case:** When you need to...

   ```

2. Add to "MCP Tools Used" section:

   ```markdown
   - `new_search_tool` - Brief description of what it does
   ```

3. Update examples if tool provides better approach

### Example: Creating New Skill

When adding comprehensive field extraction capabilities:

1. Create `skills/admin-field-extraction.md` following template
2. Add entry to `skills/README.md` index table
3. Cross-reference from related skills (e.g., query optimization)

## Session Checklist

At the end of each Claude session:

- [ ] All new tools documented in `docs/mcp-tools-reference.md`
- [ ] Tool count updated in `docs/mcp-tools-reference.md` header
- [ ] Tool count updated in `README.md` if changed significantly
- [ ] **Skills library reviewed and updated** (see Skills Library Maintenance above)
- [ ] Tests written and passing
- [ ] No temporary `.md` files in project root
- [ ] CHANGELOG.md updated with changes
- [ ] `.env.example` updated if new config options added
- [ ] All code follows established patterns
- [ ] Security checklist items verified

## Getting Help

### Sumo Logic API References

- Main API Docs: <https://api.sumologic.com/docs/>
- API Getting Started: <https://help.sumologic.com/docs/api/>
- Search Job API: <https://api.sumologic.com/docs/#tag/searchJobManagement>
- Content API: <https://api.sumologic.com/docs/#tag/contentManagement>

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
