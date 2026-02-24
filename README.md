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

### Log & Metric Analysis
- `search_sumo_logs` - Search logs with Sumo Logic query language
- `query_sumo_metrics` - Query metrics with aggregations

### Configuration & Resources
- `get_sumo_collectors` - List data collectors
- `get_sumo_sources` - Get sources for a collector
- `get_sumo_users` - List users
- `get_sumo_folders` - List content folders
- `get_sumo_dashboards` - List dashboards
- `get_sumo_partitions` - List partitions
- `get_sumo_roles_v2` - List roles
- `get_sumo_content_v2` - Get content by type

### Monitoring
- `search_sumo_monitors` - Search monitors and monitor folders

### Multi-Instance
- `list_sumo_instances` - List all configured instances

All tools support an `instance` parameter to target specific Sumo Logic deployments.

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

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "uv",
      "args": ["--directory", "/path/to/sumologic-python-mcp", "run", "sumologic-mcp-server"],
      "env": {}
    }
  }
}
```

The server will automatically load credentials from your `.env` file.

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

```
Search Sumo Logic logs for errors in the last hour:
query: error | count by _sourceHost
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
