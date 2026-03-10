# Quick Start Guide - Sumo Logic MCP Server

Get up and running in 5 minutes with uv!

> **📖 Using Claude Code (VSCode)?** See [QUICKSTART-CLAUDE-CODE.md](QUICKSTART-CLAUDE-CODE.md) for VSCode-specific setup instructions.

This guide covers Claude Desktop and Cline extension setup.

## 1. Install uv (if needed)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

## 2. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/rjury-sumo/sumologic-poweruser-mcp.git
cd sumologic-poweruser-mcp

# Install all dependencies (uv handles virtualenv automatically)
uv sync
```

## 3. Configure Credentials

### Get Access Credentials

**🔒 Recommended: Use Service Account with View-Only Permissions**

For production use, create a dedicated service account:

1. Go to **Administration** > **Users and Roles** > **Service Accounts**
2. Create new service account: `MCP Server` or `AI Assistant`
3. Generate access key for the service account
4. Assign a role with **view-only permissions** (no manage/create/delete)
   - View Collectors, Fields, Users, Content, Dashboards, etc.
   - See [docs/GITHUB_ACTIONS_SETUP.md](docs/GITHUB_ACTIONS_SETUP.md) for detailed permission list

**Why service accounts?**

- Purpose-built for automation
- No MFA conflicts
- Independent from user accounts
- Minimal permissions reduce security risk

**📖 Reference:** [Sumo Logic Service Accounts](https://www.sumologic.com/help/docs/manage/security/service-accounts/)

**Alternative:** If service accounts are not available, use a user access key from **Administration** > **Security** > **Access Keys**.

### Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Sumo Logic credentials
# (Use your favorite editor: nano, vim, code, etc.)
nano .env
```

**Minimum configuration in `.env`:**

```bash
SUMO_ACCESS_ID=your_service_account_access_id_here
SUMO_ACCESS_KEY=your_service_account_access_key_here
SUMO_ENDPOINT=https://api.sumologic.com
```

**Optional: Add multiple instances:**

```bash
# Production
SUMO_PROD_ACCESS_ID=your_prod_id
SUMO_PROD_ACCESS_KEY=your_prod_key
SUMO_PROD_ENDPOINT=https://api.us2.sumologic.com

# Staging
SUMO_STAGING_ACCESS_ID=your_staging_id
SUMO_STAGING_ACCESS_KEY=your_staging_key
SUMO_STAGING_ENDPOINT=https://api.eu.sumologic.com
```

## 4. Configure Claude Desktop

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

> **Note for macOS users**: Using `python3` with `run_with_env.py` is more reliable than the shell script on macOS due to permission restrictions.

**Option B: Direct credentials (less secure)**

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/sumologic-poweruser-mcp",
        "run",
        "sumologic-poweruser-mcp"
      ],
      "env": {
        "SUMO_ACCESS_ID": "your_access_id",
        "SUMO_ACCESS_KEY": "your_access_key",
        "SUMO_ENDPOINT": "https://api.sumologic.com"
      }
    }
  }
}
```

**Important:** Replace `/absolute/path/to/sumologic-poweruser-mcp` with the actual full path to your cloned repository.

## 5. Restart Claude Desktop

Close and reopen Claude Desktop. The MCP server will start automatically.

## 6. Test It

Ask Claude:

```
Can you list the configured Sumo Logic instances?
```

Or:

```
Search my Sumo Logic logs for errors in the last hour
```

## Troubleshooting

### Can't find uv command

Make sure uv is in your PATH:

```bash
# Add to ~/.bashrc, ~/.zshrc, or equivalent
export PATH="$HOME/.cargo/bin:$PATH"
```

Then restart your terminal or run:

```bash
source ~/.bashrc  # or ~/.zshrc
```

### Invalid credentials

1. Check your `.env` file has the correct credentials
2. Make sure there are no extra spaces or quotes
3. Verify your Sumo Logic endpoint matches your deployment region
4. Test your credentials manually: <https://help.sumologic.com/docs/api/>

### Claude Desktop can't find the server

1. Make sure the path in `claude_desktop_config.json` is absolute (not relative)
2. Check that `uv sync` completed successfully
3. Try running manually: `uv run sumologic-poweruser-mcp` to see error messages
4. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`

### Permission denied on .env

Set proper permissions:

```bash
chmod 600 .env
```

## Development Mode

Want to modify the code? Here's how:

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Format code
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/
```

## Next Steps

- 📖 **[View All Tools](docs/mcp-tools-reference.md)** - Complete tool documentation
- 📚 **[README.md](README.md)** - Full project documentation
- 🔒 **[SECURITY.md](SECURITY.md)** - Security best practices
- 💻 **[QUICKSTART-CLAUDE-CODE.md](QUICKSTART-CLAUDE-CODE.md)** - VSCode/Claude Code setup

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/yourusername/sumologic-python-mcp/issues)
- **Security:** See [SECURITY.md](SECURITY.md)
- **Sumo Logic API:** [API Documentation](https://help.sumologic.com/docs/api/)

---

**Happy querying!** 🔍
