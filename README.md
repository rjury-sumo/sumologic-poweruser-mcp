# sumologic-poweruser-mcp

## Project Status & Scope

### ⚠️ Experimental & Unsupported

This is an **experimental demonstration project** showcasing MCP capabilities with Sumo Logic APIs.

- ❗ **Not officially supported** by Sumo Logic
- ⚠️ **Use at your own risk** - no warranties or liability
- 🤝 **Community-driven** - forks and enhancement suggestions welcome
- 📝 **Open for contributions** - see [Contributing](#contributing) section

🔐 **Secure, read-only** MCP server for Sumo Logic APIs, written with Claude AI assistance.

This Model Context Protocol (MCP) server gives AI assistants like Claude two complementary capabilities: **secure, read-only access to Sumo Logic APIs** for searching logs, querying metrics, and analysing your environment — and **deep platform expertise** to act as a trusted advisor on architecture, design decisions, and best practices. Use it to run queries, or ask it how you *should* structure your data, alerts, and partitions.

Beyond raw data access, this project ships with a **[Skills Library](skills/)** — 23 structured knowledge files that turn your AI assistant into a **virtual Sumo Logic Technical Account Engineer (TAE)**. Ask for architecture advice, partition design reviews, alerting strategies, or cost optimization guidance, and Claude will draw on the same deep product knowledge a TAE would bring.

> **⚡ Quick Start:** See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide using uv!
>
> **📦 Package Manager:** This project uses [uv](https://github.com/astral-sh/uv) exclusively. See [UV_MIGRATION.md](UV_MIGRATION.md) if migrating from pip/venv.

### 🔒 Read-Only by Design

This MCP server is **intentionally read-only** to minimize risk and showcase safe search/analytics workflows:

- ✅ **Safe for exploration** - No create, update, or delete operations
- 🎯 **Focused scope** - Search, query, and analytics only
- 🚫 **Out of scope** - Write operations dramatically increase risk and complexity
- 🛡️ **Risk mitigation** - Read-only access prevents accidental modifications

**Why read-only?** Adding write capabilities (create/modify/delete) would:

- Introduce significant operational risk to production environments
- Require extensive permission management and validation
- Dramatically increase code complexity and attack surface
- Shift focus from core search/analytics capabilities

### 🎯 Key Use Cases

This MCP server enables **AI-assisted Sumo Logic workflows** for power users and administrators, replacing traditional UI interactions with natural language queries:

**1. Search & Query Assistance**

- Natural language to Sumo Logic query translation
- Query optimization and troubleshooting
- Access to 11,000+ real query examples from published apps

**2. Environment Discovery**

- Discover available log sources, partitions, and metadata
- Identify installed apps and available dashboards
- Profile log schemas and field structures

**3. Advanced Analytics for Administrators**

- **Log Volume Analysis**: Track ingested data volumes and trends over time
- **Cost Optimization**: Analyze search scan costs for Flex/Infrequent tier optimization
- **Search Audit Analysis**: Identify high-scan queries and poorly performing searches
- **Partition Design**: Analyze data distribution to optimize data tiering strategies
- **User Behavior**: Track search patterns and query performance by user
- **Capacity Planning**: Forecast usage and credit consumption

**4. Data Tier Optimization (Infrequent / Flex Customers)**

- Analyze which data should move to Infrequent tier
- Calculate potential cost savings from data tiering
- Design partition strategies based on actual query patterns
- Monitor search scan costs to validate tier decisions

**5. 🎓 Virtual Technical Account Engineer (Architecture & Best Practices)**

Go beyond data queries — get the same calibre of advice a Sumo Logic TAE would provide:

- **Architecture reviews** - "Should I use partitions or scheduled views for this use case?"
- **Design guidance** - "How should I structure my source categories for a Kubernetes environment?"
- **Trade-off analysis** - "Monitors vs scheduled searches — which is right for my alerting needs?"
- **Best-practice audits** - "Review my current approach and flag any anti-patterns"
- **New deployment checklists** - Structured guidance on standing up a new Sumo Logic environment
- **Performance troubleshooting** - Root-cause slow queries and high scan costs
- **Admin monitoring setup** - Complete templates for ingest monitoring, collection health, and rate limiting alerts

The 23-skill [Skills Library](skills/) covers the full Sumo Logic platform — collection, partitions, scheduled views, FERs, alerting, dashboards, cost analysis, and audit indexes. Ask naturally: *"my dashboard is slow, what should I look at?"* and Claude will diagnose the issue and recommend concrete next steps.

These capabilities are particularly valuable for:

- **Administrators** managing large Sumo Logic deployments
- **Power users** building complex queries and dashboards
- **Cost managers** optimizing data tier allocation
- **DevOps teams** investigating production issues via AI assistance

## Features

- ✅ **Read-only operations** - No write/update/delete capabilities
- 🔒 **Multi-instance support** - Connect to multiple Sumo Logic deployments
- 🛡️ **Security hardened** - Input validation, rate limiting, audit logging
- ⚡ **Rate limited** - Configurable per-tool request limits
- 📊 **Comprehensive API coverage** - Logs, metrics, dashboards, monitors, and more
- 🔍 **Audit logging** - Track all API operations
- 🎓 **Virtual TAE Skills Library** - 23 structured knowledge files covering architecture advice, best practices, and platform design guidance across the full Sumo Logic stack

## Available Tools

**Total: 46 MCP Tools + 1 Resource** organized into 12 categories

For complete tool documentation with parameters, examples, and use cases, see **[MCP Tools Reference](docs/mcp-tools-reference.md)**.

### Quick Overview

| Category | Count | Description |
|----------|-------|-------------|
| **Search & Query** | 8 | Log search, job management, metrics, search audit, scan cost analysis, metadata exploration |
| **Query Examples** | 1 tool + 1 resource | Search 1000s of real Sumo Logic queries from published apps |
| **Log Volume Analysis** | 2 | Raw log volume analysis using _size field, schema profiling with facets |
| **Content Library** | 9 | Folder/content access, path operations, export with async job handling, installed apps discovery |
| **Content ID Utilities** | 3 | Hex/decimal conversion, web URL generation |
| **Account Management** | 6 | Account status, usage forecasting, credit analysis, data volume analysis |
| **Collectors & Sources** | 2 | List collectors, get sources |
| **Users & Roles** | 2 | List users, list roles |
| **Dashboards & Monitors** | 2 | List dashboards, search monitors |
| **Field Management** | 3 | Custom fields, field extraction rules |
| **System** | 2 | List partitions, list instances |
| **Utility** | 1 | Skills library access |

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
- `export_installed_apps` - Discover pre-built apps (AWS, Kubernetes, Apache, etc.) already installed
- `list_installed_apps` - Quick list of installed apps (lightweight alternative)
- `get_content_web_url` - Generate shareable content links

**Field Management:**

- `list_custom_fields` - List all custom fields defined in the organization
- `list_field_extraction_rules` - List field extraction rules (FERs) for pre-parsing
- `get_field_extraction_rule` - Get detailed information about a specific FER

**Log Volume Analysis:**

- `analyze_log_volume` - Analyze raw log volume using _size field to optimize Infrequent tier usage
- `profile_log_schema` - Discover available fields and suggest good dimensions for volume analysis using facets operator

**Query Examples:**

- `search_query_examples` - Search through 11,000+ real Sumo Logic queries from 280+ published apps by app name, use case, or keywords
- Resource: `sumo://query-examples` - Browse sample query examples via MCP resources (returns 20 diverse examples)

**Skills Library:**

- `get_skill` - Fetch portable skill definitions (query construction, optimization, discovery workflows, cost analysis)

All tools support an `instance` parameter to target specific Sumo Logic deployments.

📖 **[View Complete Tool Documentation →](docs/mcp-tools-reference.md)**
💡 **[Example Prompts & Use Cases →](docs/example-prompts.md)** - 100+ example prompts showing how to use each tool

## Setup

### Prerequisites

- Python 3.10 or higher (for local installation) OR Docker (for containerized deployment)
- Sumo Logic access ID and access key
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer (for local installation only)

### Option 1: Docker Installation (Recommended for Portability)

**Prerequisites:**

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose (included with Docker Desktop)

**Quick Start:**

```bash
# Clone the repository
git clone https://github.com/yourusername/sumologic-poweruser-mcp.git
cd sumologic-poweruser-mcp

# Create .env file with your credentials
cp .env.example .env
# Edit .env with your actual credentials

# Build and run with Docker Compose
docker compose up -d

# View logs
docker compose logs -f

# Stop the server
docker compose down
```

**Or build manually:**

```bash
# Build the Docker image
docker build -t sumologic-poweruser-mcp .

# Run the container
docker run -it --rm \
  --env-file .env \
  sumologic-poweruser-mcp
```

**Benefits:**

- ✅ No need to install Python or uv
- ✅ Consistent environment across all platforms
- ✅ Easy deployment and portability
- ✅ Isolated from system Python installations

### Option 2: Local Installation with uv

**Install uv:**

If you don't have uv installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

**Install the MCP server:**

```bash
# Clone the repository
git clone https://github.com/yourusername/sumologic-poweruser-mcp.git
cd sumologic-poweruser-mcp

# Install dependencies with uv
uv sync
```

### Configuration

1. **Copy the environment template:**

```bash
cp .env.example .env
```

1. **Edit `.env` with your credentials:**

```bash
# Default instance
SUMO_ACCESS_ID=your_access_id_here
SUMO_ACCESS_KEY=your_access_key_here
SUMO_ENDPOINT=https://api.sumologic.com
# optional subdomain if using UI web url tools
# SUMO_SUBDOMAIN=mycompany

# Optional: Additional instances
SUMO_PROD_ACCESS_ID=your_prod_id
SUMO_PROD_ACCESS_KEY=your_prod_key
SUMO_PROD_ENDPOINT=https://api.us2.sumologic.com

SUMO_STAGING_ACCESS_ID=your_staging_id
SUMO_STAGING_ACCESS_KEY=your_staging_key
SUMO_STAGING_ENDPOINT=https://api.eu.sumologic.com
```

**⚠️ Security Note:** Never commit your `.env` file to version control!

1. **Configure MCP Client**

Choose your MCP client configuration below. You can use either the Docker container or the local uv installation.

### Option A: Claude Desktop (with Docker)

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/absolute/path/to/sumologic-poweruser-mcp/.env",
        "sumologic-poweruser-mcp"
      ]
    }
  }
}
```

Replace `/absolute/path/to/sumologic-poweruser-mcp` with your actual project path.

**Note:** Make sure you've built the Docker image first with `docker build -t sumologic-poweruser-mcp .`

### Option B: Claude Desktop (with uv)

Add to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Option A: Using wrapper script (Recommended - keeps credentials in .env)**

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "python3",
      "args": [
        "/absolute/path/to/sumologic-poweruser-mcp/scripts/run_with_env.py"
      ]
    }
  }
}
```

Replace `/absolute/path/to/sumologic-poweruser-mcp` with your actual project path. The wrapper script will load credentials from your `.env` file.

> **Note for macOS users**: Using `python3` with `run_with_env.py` is more reliable than the shell script on macOS due to permission restrictions.

**Option B: Specify credentials directly in config**

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/sumologic-poweruser-mcp", "run", "sumologic-poweruser-mcp"],
      "env": {
        "SUMO_ACCESS_ID": "your_access_id",
        "SUMO_ACCESS_KEY": "your_access_key",
        "SUMO_ENDPOINT": "https://api.sumologic.com"
      }
    }
  }
}
```

**⚠️ Security Note:** Option A (wrapper script) is more secure as credentials stay in `.env` instead of the config file.

**Restart Claude Desktop**

The MCP server will start automatically when Claude Desktop launches.

### Option C: Claude Code (VSCode Extension)

> **📖 Quick Start:** See [QUICKSTART-CLAUDE-CODE.md](QUICKSTART-CLAUDE-CODE.md) for detailed setup instructions.

**IMPORTANT:** Claude Code uses the Claude CLI for MCP server configuration. The CLI approach is more reliable than `.vscode/mcp.json` files.

**Note:** The MCP server code does NOT automatically load `.env` files. You must explicitly pass environment variables using the `env` parameter.

**Method 1: Using Claude CLI with Explicit Credentials (Working Method)**

```bash
# Replace /path/to/sumologic-poweruser-mcp with your actual path (use pwd)
# Update credentials with your actual values
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp add-json sumologic \
  '{"command":"uv","args":["run","--directory","/path/to/sumologic-poweruser-mcp","sumologic-poweruser-mcp"],"env":{"SUMO_ACCESS_ID":"your_access_id","SUMO_ACCESS_KEY":"your_access_key","SUMO_ENDPOINT":"https://api.au.sumologic.com","SUMO_SUBDOMAIN":"your_subdomain"}}' \
  -s user
```

**Method 2: Using Shell Wrapper to Load .env (Alternative)**

To keep credentials in your `.env` file, use the wrapper script:

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp add-json sumologic \
  '{"command":"python3","args":["/path/to/sumologic-poweruser-mcp/scripts/run_with_env.py"]}' \
  -s user
```

**Verify Configuration:**

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp list
```

You should see: `sumologic: uv run ... - ✓ Connected`

**Restart VSCode:** Quit completely (Cmd+Q / Ctrl+Q) and reopen.

**Troubleshooting:**

- Check logs: View → Output → "Claude VSCode" dropdown
- List servers: `node ~/.vscode/.../cli.js mcp list`
- Remove server: `node ~/.vscode/.../cli.js mcp remove sumologic`

**Claude Code MCP References:**

- [Connect Claude Code to tools via MCP - Official Docs](https://docs.claude.com/en/docs/claude-code/mcp)
- [Configuring MCP Tools in Claude Code - The Better Way](https://scottspence.com/posts/configuring-mcp-tools-in-claude-code-the-better-way)
- [How to Extend Claude Code with MCP Guide](https://dev.to/anthropic/how-to-extend-claude-code-with-mcp-secure-project-file-control-guide)

### Option D: Cline Extension

For Cline users, Docker or uv configurations work similarly. See the [QUICKSTART.md](QUICKSTART.md) for detailed configuration.

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

### Search Query Examples

Search 11,000+ real Sumo Logic queries from 280+ published apps using intelligent scoring and relevance ranking.

**Note:** The query examples database is included as `logs_searches.json.gz` (2.9MB compressed). It will automatically decompress on first use to `logs_searches.json` (13MB).

**Search Features:**

- 🎯 **Natural language search** - Just describe what you want: "apache 4xx errors by server"
- 🏆 **Relevance scoring** - Results ranked by how well they match your criteria
- 🔤 **Tokenized search** - Multi-word searches automatically split and match
- 🏷️ **Technology aliases** - k8s→Kubernetes, httpd→Apache, eks→Kubernetes
- 📊 **Match metadata** - See exactly why each result matched
- 🔄 **Smart fallback** - Auto-relaxes filters when no results found

**Examples:**

```bash
# Natural language search (RECOMMENDED)
search_query_examples:
  query: "apache 4xx errors by server"
  max_results: 5
# Returns: 1,133 matches, scored and ranked by relevance

# Kubernetes scheduling issues
search_query_examples:
  query: "k8s unschedulable pods"
  max_results: 5
# Aliases work: k8s → kubernetes

# Pattern + technology
search_query_examples:
  query: "count by timeslice"
  app_name: "AWS"
  query_type: "Logs"
# Combines natural search with filters

# Multi-word keyword search
search_query_examples:
  keywords: "status_code bytes"
  max_results: 10
# Finds queries containing either "status_code" OR "bytes"

# Strict AND mode (all filters must match)
search_query_examples:
  app_name: "Apache"
  use_case: "performance"
  match_mode: "all"
# Only returns queries matching ALL criteria

# Fuzzy mode with auto-fallback
search_query_examples:
  app_name: "Windows"
  keywords: "error"
  match_mode: "fuzzy"
# If no results, automatically relaxes filters
```

**Match Modes:**

- `any` (default) - Scores by relevance, more matches = higher rank
- `all` - Strict AND, all filters must match
- `fuzzy` - Auto-relaxes filters if zero results

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

### For Contributors and AI Assistants

**📖 Essential Reading for Development:**

- **[CLAUDE.md](CLAUDE.md)** - Development guidelines for Claude/AI-assisted development
- **[.PATTERNS.md](.PATTERNS.md)** - Architecture patterns and coding standards
- **[docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - Quick lookup for common tasks

**⚠️ Critical Rule:** Always update `docs/mcp-tools-reference.md` when adding/modifying tools!

### Install Development Dependencies

```bash
# Sync all dependencies including dev
uv sync --all-extras
```

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_module.py -v

# Run unit tests only (fast, no API credentials needed)
uv run pytest tests/test_*.py --ignore=tests/integration --ignore=tests/utilities --ignore=tests/debug -v
```

### Run with Coverage

```bash
uv run pytest --cov=src --cov-report=html
```

### GitHub Actions CI/CD

The project uses GitHub Actions with two test strategies:

- **Push to main/develop**: Fast unit tests only (~1-2 minutes)
- **Pull requests**: Full integration tests with API access (~5-10 minutes)

**Setting up integration tests for PRs:** See [docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md) for instructions on configuring repository secrets for Sumo Logic API access.

### Development Workflow

1. Review [CLAUDE.md](CLAUDE.md) for guidelines and patterns
2. Copy [docs/development/.CHECKLIST_TEMPLATE.md](docs/development/.CHECKLIST_TEMPLATE.md) for your feature
3. Implement following patterns from [.PATTERNS.md](.PATTERNS.md)
4. **Update `docs/mcp-tools-reference.md`** (mandatory for new/modified tools)
5. Write tests and verify they pass
6. Update CHANGELOG.md

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
uv run sumologic-poweruser-mcp

# Or use Python module directly
uv run python -m sumologic_poweruser_mcp.sumologic_poweruser_mcp
```

## Skills Library — Virtual TAE

The `skills/` directory contains **23 structured knowledge files** that transform your AI assistant into a **virtual Sumo Logic Technical Account Engineer**. Skills cover not just *how to use tools*, but deep platform expertise: architecture decisions, partition design, alerting strategy, cost optimization, and operational best practices.

### Virtual TAE Capabilities

Ask naturally — Claude will identify the right skill and provide expert guidance:

| You ask... | Claude consults... |
|---|---|
| *"My queries are slow, what should I check?"* | `search-optimize-queries` — SKEFE framework, bloom filter rules, push-down patterns |
| *"Should I use monitors or scheduled searches?"* | `alerting-monitors` + `consulting-guide` — trade-off table and recommendation |
| *"How should I design my partitions?"* | `admin-partition-design` — seven design rules, scan reduction analysis |
| *"My dashboard is slow"* | `search-optimize-with-views` — scheduled view transformation patterns |
| *"How do I alert on ingest drops?"* | `admin-alerting-and-monitoring` — 5 complete alert query templates |
| *"How should I structure source categories?"* | `data-collection-patterns` + `consulting-guide` — naming conventions and architecture |
| *"What's the difference between anomaly and outlier detection?"* | `alerting-time-compare-anomaly` — comparison table and use-case guide |
| *"Review my Sumo Logic architecture"* | `consulting-guide` — four-layer framework and structured review |

### Available Skills (23 total)

| Category | Skills |
|----------|--------|
| **🎯 Consulting & Architecture** | `consulting-guide` (entry point — start here for advice) |
| **🔍 Search & Query** | `search-write-queries`, `search-optimize-queries`, `search-indexes-partitions`, `search-optimize-with-views`, `search-scheduled-views`, `search-log-search-basics`, `search-copilot` |
| **🔔 Alerting & Monitoring** | `alerting-monitors`, `alerting-time-compare-anomaly` |
| **📊 Dashboards** | `dashboards-overview`, `dashboards-panel-types` |
| **📥 Data Collection** | `data-collection-patterns` |
| **🗂️ Discovery** | `discovery-logs-without-metadata`, `discovery-scheduled-views` |
| **💰 Cost Analysis** | `cost-analyze-search-costs`, `cost-analyze-data-volume` |
| **🔎 Audit** | `audit-user-activity`, `audit-system-health` |
| **⚙️ Administration** | `admin-partition-design`, `admin-field-extraction-rules`, `admin-alerting-and-monitoring` |
| **📚 Content** | `content-library-navigation` |

📖 **[View Complete Skills Index →](skills/README.md)**

### Using Skills

**With the MCP Server:**
Use the `get_skill` tool to fetch skills dynamically:

```
get_skill("consulting-guide")        # Start here for architecture advice
get_skill("search-optimize-queries") # Query performance and cost
get_skill("admin-partition-design")  # Partition strategy guidance
```

**With Claude Code / Claude Desktop:**
Skills are automatically loaded when referenced in [CLAUDE.md](CLAUDE.md) — Claude proactively consults the right skill based on your question without you having to ask.

**Standalone:**
Copy any skill markdown file and provide it as context to your AI assistant for portable, reusable expertise.

### Skill Format

Each skill includes:

- **Intent** - What the skill accomplishes
- **Prerequisites** - Required knowledge/access
- **Context** - When to use it (and when not to)
- **Approach** - Step-by-step methodology with MCP tool calls
- **Query Patterns** - Reusable code snippets
- **Examples** - Real-world scenarios
- **Common Pitfalls** - Mistakes to avoid
- **Related Skills** - Cross-references

## Architecture

```
sumologic-poweruser-mcp/
├── src/sumologic_poweruser_mcp/
│   ├── __init__.py
│   ├── sumologic_poweruser_mcp.py  # Main server and MCP tools
│   ├── config.py                 # Configuration management
│   ├── exceptions.py             # Custom exception classes
│   ├── validation.py             # Input validation models
│   ├── rate_limiter.py           # Rate limiting implementation
│   ├── query_patterns.py         # Reusable Sumo query patterns
│   ├── search_helpers.py         # Search utility functions
│   ├── content_id_utils.py       # Content ID manipulation
│   └── async_export_helper.py    # Async job polling helpers
├── skills/                       # Portable skill definitions
│   ├── README.md                 # Skills index and documentation
│   ├── search-*.md               # Query writing and optimization skills
│   ├── discovery-*.md            # Log discovery workflows
│   ├── cost-*.md                 # Cost analysis skills
│   ├── audit-*.md                # Audit index skills
│   ├── content-*.md              # Content library skills
│   ├── admin-*.md                # Administration skills
│   └── ui-*.md                   # UI navigation skills
├── tests/
│   ├── integration/              # Integration tests
│   ├── utilities/                # Unit tests for helpers
│   └── debug/                    # Debug test scripts
├── docs/
│   ├── mcp-tools-reference.md    # Complete tool documentation
│   └── development/              # Development notes
├── .env.example                  # Configuration template
├── .gitignore
├── CLAUDE.md                     # Development guidelines
├── SECURITY.md                   # Security policy
├── LICENSE
├── README.md
└── pyproject.toml
```

### Query Patterns Library

The `query_patterns.py` module provides reusable Sumo Logic query patterns that ensure consistent behavior across tools, especially for edge cases like null handling and division by zero.

**Key Pattern Classes:**

- **`ScopePattern`** - Build optimized search scopes for partition routing and query performance
  - `build_scope()` - Construct scopes with partition, metadata, keywords, and indexed fields
  - `build_metadata_scope()` - Simplified API for metadata-only scopes
  - `extract_scope_from_query()` - Extract scope from full query string
  - `analyze_scope()` - Analyze scope and provide optimization recommendations
  - Critical for minimizing metered scan volume in Flex/Infrequent tiers

- **`TimeshiftPattern`** - Compare current data with historical baselines using `compare with timeshift`
  - Handles null values from missing historical data
  - Detects states: GONE (stopped collection), NEW (newly appeared), COLLECTING (active)
  - Safe division preventing null results from zero baselines

- **`NullSafeOperations`** - Null-safe mathematical operations
  - `safe_divide()` - Division with null and zero guards
  - `coalesce()` - Convert nulls to default values
  - `percentage_change()` - Calculate % change with edge case handling

- **`AggregationPatterns`** - Common aggregation and sorting
  - `volume_by_dimension()` - Standard volume aggregation
  - `top_n()` - Top results with sorting
  - `timeslice_aggregation()` - Time-series aggregations

- **`CreditCalculation`** - Sumo Logic credit rate calculations
  - Standard tiered pricing (Continuous: 20, Frequent: 9, Infrequent: 0.4, CSE: 25 credits/GB)
  - Customizable rates for different pricing models

- **`LogDiscoveryPattern`** - Complete 3-phase log discovery workflow with app recommendations
  - `build_metadata_discovery_query()` - Phase 1: Find source categories, partitions, metadata
  - `build_usecase_query_recommendations()` - Phase 3: Query recommendations based on use case and fields
  - `recommend_apps()` - Suggest relevant Sumo Logic apps based on discovered logs
  - `generate_complete_workflow()` - End-to-end discovery workflow
  - **Phase 1:** Metadata discovery (data volume index, metadata exploration, search audit)
  - **Phase 2:** Log structure analysis (sampling, field detection, format analysis)
  - **Phase 3:** Use-case based query building with `search_query_examples` integration
  - **App Discovery:** Recommends pre-built apps (AWS CloudTrail, Kubernetes, Apache, etc.)
  - Integrates with `export_installed_apps` and `list_installed_apps` tools
  - Leverages query examples library (11,000+ real queries) for relevant patterns
  - Provides links to app catalog and integration docs
  - Helps users discover logs from scratch and build effective queries

**Usage Examples:**

```python
from query_patterns import ScopePattern, TimeshiftPattern, AggregationPatterns, CreditCalculation, LogDiscoveryPattern

# Example 1: Build an optimized scope
scope = ScopePattern.build_scope(
    partition='prod_logs',
    metadata={'_sourceCategory': 'prod/app'},
    keywords=['error', '5xx'],
    indexed_fields={'severity': 'ERROR'}
)
# Result: '_index=prod_logs AND _sourceCategory="prod/app" AND error AND 5xx AND severity=ERROR'

# Example 2: Analyze existing scope for optimization
analysis = ScopePattern.analyze_scope('error')
# Returns recommendations like: 'Add _sourceCategory or _index to enable partition routing'

# Example 3: Phase 1 - Discover logs when you don't know the metadata
queries = LogDiscoveryPattern.build_metadata_discovery_query('cloudtrail')
# Returns queries to find matching source categories, partitions, and related metadata
# Use volume_query to search data volume index (fast, no scan charge)
# Use metadata_query_template after finding source category
# Use search_audit_query to see what other users have searched

# Example 4: Phase 3 - Get query recommendations based on use case
recommendations = LogDiscoveryPattern.build_usecase_query_recommendations(
    log_format='json',
    detected_fields=['status_code', 'user_id', 'response_time'],
    use_case='error',
    has_query_library=True
)
# Returns query_library_searches (searches for search_query_examples tool)
# Returns common_patterns (generic patterns for this use case)
# Returns field_based_queries (queries leveraging detected fields)
# Includes setup instructions if query library not available

# Example 5: Build a complete volume analysis query
query_parts = [ScopePattern.build_metadata_scope(source_category='prod/*')]
query_parts.append(AggregationPatterns.volume_by_dimension('sourceCategory'))
query_parts.extend(CreditCalculation.add_credit_calculation())
query_parts.extend(TimeshiftPattern.compare_with_timeshift('gbytes', days=7, periods=3))
query_parts.append(AggregationPatterns.top_n('gbytes', limit=100))
```

These patterns centralize complex query logic, making it easier to:

- Fix bugs in one place and have fixes propagate everywhere
- Ensure consistent null handling across all timeshift queries
- Write unit tests for query generation
- Document query patterns with clear examples

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

- **Issues:** [GitHub Issues](https://github.com/yourusername/sumologic-poweruser-mcp/issues)
- **Security:** See [SECURITY.md](SECURITY.md) for vulnerability reporting

## Acknowledgments

This project was created with assistance from Claude (Anthropic) and uses:

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [httpx](https://www.python-httpx.org/) - HTTP client
- [Pydantic](https://docs.pydantic.dev/) - Data validation

---

**Built with 🤖 assistance from Claude Code**
