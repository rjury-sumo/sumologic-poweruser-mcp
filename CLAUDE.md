# Claude Development Guidelines

## Project Structure

```
src/sumologic_poweruser_mcp/
  sumologic_poweruser_mcp.py  # MCP server + SumoLogicClient + all @mcp.tool() defs
  config.py / validation.py / exceptions.py / rate_limiter.py
  async_export_helper.py / content_id_utils.py / url_builder.py
  search_helpers.py / query_patterns.py
tests/              # test_*.py mirroring src/ + integration/
docs/
  mcp-tools-reference.md  # ** PRIMARY TOOL DOCUMENTATION **
  development/            # Dev notes (not project root)
skills/             # Skill definitions (use get_skill MCP tool to fetch)
```

## Core Principles

1. **Read-Only** — NEVER implement write/update/delete. POST only for async job creation.
2. **Centralized API** — ALL Sumo Logic calls go through `SumoLogicClient`. Never direct HTTP in tools.
3. **Multi-Instance** — All tools accept `instance` param (default=`'default'`). Use `get_config()` / `get_sumo_client(instance)`.
4. **Security** — Validate all inputs (`validation.py`), apply rate limiting (`get_rate_limiter()`), audit log when enabled.

## Skills Reference

Use `get_skill` MCP tool to fetch dynamically. Full index: `skills/README.md`.

| Trigger / Question | Skill File |
|--------------------|-----------|
| Open-ended / architecture / "how should I" | `consulting-guide.md` |
| New to search, metadata fields, parse operators | `search-log-search-basics.md` |
| Writing queries | `search-write-queries.md` |
| Slow queries, scan cost, "too expensive" | `search-optimize-queries.md` |
| Large result sets, API limits, high cardinality | `search-result-size-optimization.md` |
| Partitions, `_index=`, `_view=`, data tiers | `search-indexes-partitions.md` |
| Querying scheduled views | `search-optimize-with-views.md` |
| Designing / creating scheduled views | `search-scheduled-views.md` |
| Mo Copilot / AI query generation | `search-copilot.md` |
| UI-based investigation | `ui-navigate-and-search.md` |
| Monitors, alerts, "how do I alert on X" | `alerting-monitors.md` |
| Anomaly detection, dynamic thresholds, timeshift | `alerting-time-compare-anomaly.md` |
| Dashboard design / types | `dashboards-overview.md` |
| Panel types, time series, honeycomb, transpose | `dashboards-panel-types.md` |
| Collection architecture, source categories | `data-collection-patterns.md` |
| Finding logs without metadata | `discovery-logs-without-metadata.md` |
| Discovering scheduled views | `discovery-scheduled-views.md` |
| Search scan costs, credits, "why expensive" | `cost-analyze-search-costs.md` |
| Audit index, user activity, login tracking | `audit-user-activity.md` |
| Collector health, ingest monitoring, admin alerts | `audit-system-health.md` |
| Admin alerting setup, data volume monitoring | `admin-alerting-and-monitoring.md` |
| Partition design / strategy | `admin-partition-design.md` |
| FERs, index-time fields, parse at ingest | `admin-field-extraction-rules.md` |
| Content library, exporting dashboards | `content-library-navigation.md` |

## Adding a New MCP Tool — Exact Sequence

1. **Plan** — Review API docs, check for existing similar tools.
2. **Add API method to `SumoLogicClient`** — `async def get_X(self, ...) -> Dict[str, Any]` using `self._request()`.
3. **Implement `@mcp.tool()`** — Follow the standard pattern:
   ```python
   @mcp.tool()
   async def tool_name(param: str = Field(...), instance: str = Field(default='default', ...)) -> str:
       try:
           _ensure_config_initialized()
           config = get_config()
           limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
           await limiter.acquire("tool_name")
           instance = validate_instance_name(instance)
           param = validate_query_input(param)
           client = await get_sumo_client(instance)
           result = await client.get_X(param)
           return json.dumps(result, indent=2)
       except Exception as e:
           return handle_tool_error(e, "tool_name")
   ```
4. **MANDATORY: Update `docs/mcp-tools-reference.md`** — Add entry with: number, name, description, Parameters, Returns, Use Cases, Example, API Reference. Update tool count in header and README.md.
5. **Write tests** — Use CI-compatible mock pattern (see Testing section).
6. **Validate** — `uv run pytest -v`, `uv run black src/ tests/`, `uv run ruff check src/ tests/ --fix`, `uv run bandit -r src/`.
7. **Update docs** — README.md (if significant), CHANGELOG.md, `docs/development/` (if complex).

**Modifying existing tools:** Update code → update `docs/mcp-tools-reference.md` → update tests → CHANGELOG.md.

## File Organization

| Code Type | Location |
|-----------|----------|
| MCP tools + SumoLogicClient | `sumologic_poweruser_mcp.py` |
| Validation | `validation.py` |
| Configuration | `config.py` |
| URL generation | `url_builder.py` |
| Content ID conversion | `content_id_utils.py` |
| Search helpers | `search_helpers.py` |
| Query patterns | `query_patterns.py` |
| Async job polling | `async_export_helper.py` |
| Tests | `tests/test_*.py` |
| Dev notes | `docs/development/` (never project root) |

## Anti-Patterns — DO NOT

1. Create `.md` files in project root — use `docs/development/`
2. Add tools without updating `docs/mcp-tools-reference.md`
3. Make direct HTTP calls in tool functions — add to `SumoLogicClient`
4. Skip input validation
5. Hardcode API endpoints/URLs — use `config.py` / `url_builder.py`
6. Create separate tool files — all tools in `sumologic_poweruser_mcp.py`
7. Omit rate limiting — every tool must `await limiter.acquire("tool_name")`
8. Return raw Python objects — always `return json.dumps(result, indent=2)`

## Code Quality

```bash
uv run black src/ tests/          # format (CI enforced)
uv run ruff check src/ tests/ --fix  # lint
uv run bandit -r src/             # security scan
uv run pytest -v                  # tests
```

**Key rules:**
- Never bare `except:` — use `except Exception:  # noqa: S110`
- B904 (exception chaining) globally ignored for API errors — intentional
- B007 (unused loop var) globally ignored — polling loops are common
- B008 (Field() in defaults) globally ignored — required for FastMCP

## Testing — CI-Compatible Pattern

**CRITICAL:** Tests must work without `.env`. Mock all initialization.

**Required mocks for every MCP tool test:**
- [ ] `mock_config` fixture: `config = MagicMock(); config.server_config.rate_limit_per_minute = 60`
- [ ] `_ensure_config_initialized` patched
- [ ] `get_config` patched → returns `mock_config`
- [ ] `get_sumo_client` patched → returns `AsyncMock()`
- [ ] `get_rate_limiter` patched → `.acquire = AsyncMock()`
- [ ] All parameters passed as explicit values (NOT `Field()` objects)
- [ ] All async client methods use `AsyncMock()`

**Reference implementations:** `tests/test_usage_forecast.py`, `tests/test_describe_log_pipeline.py`

**Patch target prefix:** `sumologic_poweruser_mcp.sumologic_mcp_server.`

## Skills Library Maintenance

After adding/modifying tools, update related skills:
- Add tool to "MCP Tools Used" section of relevant skill(s)
- Add new patterns/examples if tool enables better approaches
- Create new skill (`skills/<domain>-<topic>.md`) for entirely new capability areas
- Update `skills/README.md` index when creating new skills

Skill file naming: `discovery-*.md`, `search-*.md`, `cost-*.md`, `audit-*.md`, `admin-*.md`, `content-*.md`, `alerting-*.md`, `dashboards-*.md`

## Session Checklist

- [ ] New tools documented in `docs/mcp-tools-reference.md` (count updated)
- [ ] README.md tool count updated if changed significantly
- [ ] Skills library reviewed and updated
- [ ] Tests written and passing (`uv run pytest -v`)
- [ ] No temporary `.md` files in project root
- [ ] CHANGELOG.md updated
- [ ] `.env.example` updated if new config options added
- [ ] `uv run black`, `ruff`, `bandit` all pass

## Pre-Commit Checklist

**Code:** `black` → `ruff` → `bandit` → `pytest` all pass. No bare `except:`.

**Tests:** `mock_config` fixture used. All 4 initializers mocked. Explicit parameter values. `AsyncMock` for async methods. Verified without `.env`.

**Security:** Inputs validated. No hardcoded credentials. Rate limiting applied. Read-only only. Config from `.env`.

## Git Commits

Format: `<type>: <description>` — types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

## API References

- API Docs: <https://api.sumologic.com/docs/>
- Search Job API: <https://api.sumologic.com/docs/#tag/searchJobManagement>
- Content API: <https://api.sumologic.com/docs/#tag/contentManagement>
- Architecture patterns: `.PATTERNS.md`

---
**Last Updated:** 2026-03-26 | **Version:** 1.2.0
