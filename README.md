# sumologic-python-mcp

🔐 **Secure, read-only** MCP server for Sumo Logic APIs, written with Claude AI assistance.

This Model Context Protocol (MCP) server provides secure, read-only access to Sumo Logic APIs, enabling AI assistants like Claude to search logs, query metrics, and retrieve account information across multiple Sumo Logic instances.

> **⚡ Quick Start:** See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide using uv!
>
> **📦 Package Manager:** This project uses [uv](https://github.com/astral-sh/uv) exclusively. See [UV_MIGRATION.md](UV_MIGRATION.md) if migrating from pip/venv.

## Features

- ✅ **Read-only operations** - No write/update/delete capabilities
- 🔒 **Multi-instance support** - Connect to multiple Sumo Logic deployments
- 🛡️ **Security hardened** - Input validation, rate limiting, audit logging
- ⚡ **Rate limited** - Configurable per-tool request limits
- 📊 **Comprehensive API coverage** - Logs, metrics, dashboards, monitors, and more
- 🔍 **Audit logging** - Track all API operations

## Available Tools

**Total: 32 MCP Tools** organized into 8 categories

For complete tool documentation with parameters, examples, and use cases, see **[MCP Tools Reference](docs/mcp-tools-reference.md)**.

### Quick Overview

| Category | Count | Description |
|----------|-------|-------------|
| **Search & Query** | 8 | Log search, job management, metrics, search audit, scan cost analysis, metadata exploration |
| **Content Library** | 7 | Folder/content access, path operations, export with async job handling |
| **Content ID Utilities** | 3 | Hex/decimal conversion, web URL generation |
| **Account Management** | 6 | Account status, usage forecasting, credit analysis, data volume analysis |
| **Collectors & Sources** | 2 | List collectors, get sources |
| **Users & Roles** | 2 | List users, list roles |
| **Dashboards & Monitors** | 2 | List dashboards, search monitors |
| **System** | 2 | List partitions, list instances |

### Featured Tools

**Log Search & Analysis:**
- `search_sumo_logs` - Intelligent search with auto query-type detection
- `explore_log_metadata` - Discover partitions, source categories, and metadata mappings
- `run_search_audit_query` - Analyze search usage patterns
- `analyze_search_scan_cost` - Analyze pay-per-search costs for Infrequent/Flex tiers with billable breakdown

**Data Volume & Cost Analysis:**
- `analyze_data_volume` - Standard volume analysis with timeshift comparison
- `analyze_data_volume_grouped` - Advanced analysis with cardinality reduction for large environments (5000+ sources)
- `get_estimated_log_search_usage` - Estimate scan costs before running queries

**Account Management:**
- `get_account_status` - Account and subscription information
- `get_usage_forecast` - Predict future usage and credits
- `export_usage_report` - Detailed usage reports with CSV export

**Content Library:**
- `get_personal_folder` - Fast access to user's content library
- `export_content` - Full content export with async job polling
- `get_content_web_url` - Generate shareable content links

All tools support an `instance` parameter to target specific Sumo Logic deployments.

📖 **[View Complete Tool Documentation →](docs/mcp-tools-reference.md)**

## Setup

### Prerequisites

- Python 3.10 or higher
- Sumo Logic access ID and access key
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer

### Install uv

If you don't have uv installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/sumologic-python-mcp.git
cd sumologic-python-mcp

# Install dependencies with uv
uv sync
```

### Configuration

1. **Copy the environment template:**

```bash
cp .env.example .env
```

2. **Edit `.env` with your credentials:**

```bash
# Default instance
SUMO_ACCESS_ID=your_access_id_here
SUMO_ACCESS_KEY=your_access_key_here
SUMO_ENDPOINT=https://api.sumologic.com

# Optional: Additional instances
SUMO_PROD_ACCESS_ID=your_prod_id
SUMO_PROD_ACCESS_KEY=your_prod_key
SUMO_PROD_ENDPOINT=https://api.us2.sumologic.com

SUMO_STAGING_ACCESS_ID=your_staging_id
SUMO_STAGING_ACCESS_KEY=your_staging_key
SUMO_STAGING_ENDPOINT=https://api.eu.sumologic.com
```

**⚠️ Security Note:** Never commit your `.env` file to version control!

3. **Configure Claude Desktop**

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Option A: Using wrapper script (Recommended - keeps credentials in .env)**

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "/absolute/path/to/sumologic-python-mcp/scripts/run-with-env.sh",
      "args": []
    }
  }
}
```

Replace `/absolute/path/to/sumologic-python-mcp` with your actual project path. The wrapper script will load credentials from your `.env` file.

**Option B: Specify credentials directly in config**

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/sumologic-python-mcp", "run", "sumologic-mcp-server"],
      "env": {
        "SUMO_ACCESS_ID": "your_access_id",
        "SUMO_ACCESS_KEY": "your_access_key",
        "SUMO_ENDPOINT": "https://api.sumologic.com"
      }
    }
  }
}
```

**⚠️ Security Note:** Option A is more secure as credentials stay in `.env` instead of the config file.

4. **Restart Claude Desktop**

The MCP server will start automatically when Claude Desktop launches.

## Configuration Options

Set these in your `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_QUERY_LIMIT` | 1000 | Maximum results per query |
| `MAX_SEARCH_TIMEOUT` | 300 | Max search timeout (seconds) |
| `RATE_LIMIT_PER_MINUTE` | 60 | Requests per minute per tool |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `ENABLE_AUDIT_LOG` | true | Enable audit logging to `sumo_mcp_audit.log` |

## Usage Examples

### Basic Log Search

The `search_sumo_logs` tool automatically detects whether your query returns raw messages or aggregate records:

```
# Raw log search - returns individual log messages
query: _sourceCategory=apache/access | where status_code=500

# Aggregate search - returns summarized records
query: error | count by _sourceHost

# Time formats
from_time: "-1h"      # Relative time (1 hour ago)
to_time: "now"        # Current time
from_time: "2024-01-15T10:00:00Z"  # ISO8601
to_time: "1705315200000"           # Epoch milliseconds
```

### Query Types

**Messages (Raw Logs)**: Queries that return individual log entries
- Example: `_sourceCategory=prod/app`
- Example: `error | where severity="high"`
- Returns: Array of log messages with timestamps and metadata

**Records (Aggregates)**: Queries with aggregation operators
- Example: `error | count by _sourceHost`
- Example: `* | timeslice 1h | count by _timeslice`
- Example: `metric | avg, sum, min, max by dimension`
- Returns: Array of aggregate records with computed values

### Advanced Search: byReceiptTime

Use `by_receipt_time=true` for:
- Very recent logs (last few minutes)
- Delayed log ingestion scenarios
- Matching Sumo Logic UI behavior for recent searches

```
query: error
from_time: "-5m"
to_time: "now"
by_receipt_time: true
```

### Asynchronous Search Jobs

For long-running queries, use the job management tools:

```
# 1. Create a search job (returns immediately)
create_sumo_search_job:
  query: "* | timeslice 1h | count by _timeslice, _sourceHost"
  from_time: "-24h"
  to_time: "now"
# Returns: {"id": "ABC123...", "link": "..."}

# 2. Check status
get_sumo_search_job_status:
  job_id: "ABC123..."
# Returns: {"state": "DONE GATHERING RESULTS", "recordCount": 1500, ...}

# 3. Get results (with pagination)
get_sumo_search_job_results:
  job_id: "ABC123..."
  result_type: "auto"  # or "messages" or "records"
  offset: 0
  limit: 1000
```

### Query Metrics

```
Get CPU utilization by host for the last 6 hours:
metric=CPU_User | avg by host
hours_back: 6
```

### Multi-Instance Usage

```
Search logs in production instance:
query: _sourceCategory=prod/app
instance: prod
```

### List Available Instances

```
Use the list_sumo_instances tool to see all configured instances.
```

## Security Best Practices

### ✅ DO

- ✅ Use environment variables for credentials (`.env` file)
- ✅ Set file permissions on `.env`: `chmod 600 .env`
- ✅ Create separate access keys per environment (prod, staging, dev)
- ✅ Use Sumo Logic access keys with minimal required permissions
- ✅ Rotate access keys regularly (every 90 days recommended)
- ✅ Monitor audit logs for suspicious activity
- ✅ Keep dependencies up to date

### ❌ DON'T

- ❌ Hardcode credentials in config files
- ❌ Commit `.env` files to version control
- ❌ Share access keys between environments
- ❌ Use admin-level access keys for read-only operations
- ❌ Ignore rate limits or error messages

### Security Features

1. **Read-Only Operations** - No write, update, or delete capabilities
2. **Input Validation** - All user inputs validated before API calls
3. **Rate Limiting** - Configurable per-tool limits prevent abuse
4. **Audit Logging** - All API requests logged to `sumo_mcp_audit.log`
5. **Error Sanitization** - No internal details exposed in error messages
6. **Credential Validation** - Credentials validated on startup

See [SECURITY.md](SECURITY.md) for detailed security information.

## Development

### Install Development Dependencies

```bash
# Sync all dependencies including dev
uv sync --all-extras
```

### Run Tests

```bash
uv run pytest
```

### Run with Coverage

```bash
uv run pytest --cov=src --cov-report=html
```

### Linting and Formatting

```bash
# Format code
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/

# Type checking
uv run mypy src/

# Security scan
uv run bandit -r src/
```

### Running Locally for Testing

```bash
# Create .env file with your credentials first
cp .env.example .env
# Edit .env with your actual credentials

# Run the server
uv run sumologic-mcp-server

# Or use Python module directly
uv run python -m sumologic_mcp_server.sumologic_mcp_server
```

## Architecture

```
sumologic-python-mcp/
├── src/sumologic_mcp_server/
│   ├── __init__.py
│   ├── sumologic_mcp_server.py  # Main server and MCP tools
│   ├── config.py                 # Configuration management
│   ├── exceptions.py             # Custom exception classes
│   ├── validation.py             # Input validation models
│   └── rate_limiter.py           # Rate limiting implementation
├── tests/
│   └── test_sumologic_mcp_server.py
├── .env.example                  # Configuration template
├── .gitignore
├── SECURITY.md                   # Security policy
├── LICENSE
├── README.md
└── pyproject.toml
```

## Troubleshooting

### Authentication Errors

**Problem:** `Authentication failed for instance 'default'`

**Solution:**
1. Verify credentials in `.env` file
2. Check that access ID and key are correct
3. Ensure endpoint matches your Sumo Logic deployment
4. Verify access key has not expired

### Rate Limit Errors

**Problem:** `Rate limit exceeded for search_sumo_logs`

**Solution:**
1. Wait for the rate limit window to reset
2. Reduce query frequency
3. Increase `RATE_LIMIT_PER_MINUTE` in `.env` if appropriate
4. Check Sumo Logic API rate limits for your account

### Search Timeouts

**Problem:** `Search job timed out after X seconds`

**Solution:**
1. Use more specific queries with filters
2. Reduce time range (use fewer hours_back)
3. Increase `MAX_SEARCH_TIMEOUT` in `.env`
4. Check Sumo Logic query performance

### Instance Not Found

**Problem:** `Instance 'prod' not configured`

**Solution:**
1. Check `.env` file for `SUMO_PROD_ACCESS_ID` and related variables
2. Verify environment variable names follow pattern: `SUMO_<NAME>_ACCESS_ID`
3. Use `list_sumo_instances` tool to see configured instances

### Server Won't Start

**Problem:** Server fails to initialize

**Solution:**
1. Check logs for specific error messages
2. Verify all required environment variables are set
3. Test credentials manually with Sumo Logic API
4. Ensure Python 3.10+ is installed
5. Reinstall dependencies: `uv pip install -e .`

## Contributing

Contributions are welcome! Please:

1. Read [SECURITY.md](SECURITY.md) for security guidelines
2. Follow the existing code style (Black, Ruff)
3. Add tests for new features
4. Update documentation as needed

## API Documentation

For Sumo Logic API documentation, see:
- [Sumo Logic API Documentation](https://help.sumologic.com/docs/api/)
- [Search Job API](https://help.sumologic.com/docs/api/search-job/)
- [Metrics Query API](https://help.sumologic.com/docs/api/metrics-queries/)

For MCP protocol documentation, see:
- [Model Context Protocol](https://modelcontextprotocol.io/)

## License

See [LICENSE](LICENSE) file for details.

## Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/sumologic-python-mcp/issues)
- **Security:** See [SECURITY.md](SECURITY.md) for vulnerability reporting

## Acknowledgments

This project was created with assistance from Claude (Anthropic) and uses:
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [httpx](https://www.python-httpx.org/) - HTTP client
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

**Built with 🤖 assistance from Claude Code**
