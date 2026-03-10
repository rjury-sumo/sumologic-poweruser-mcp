# Quick Start Guide: Claude Code (VSCode Extension)

This guide will help you set up the Sumo Logic MCP server with Claude Code in VSCode in under 5 minutes.

## Prerequisites

- ✅ Visual Studio Code installed
- ✅ Claude Code extension installed in VSCode
- ✅ Python 3.10 or higher
- ✅ `uv` package manager installed
- ✅ Sumo Logic access ID and access key

## Step 1: Install uv

If you don't have `uv` installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

Verify installation:

```bash
uv --version
```

## Step 2: Clone and Install

```bash
# Clone the repository
git clone https://github.com/rjury-sumo/sumologic-poweruser-mcp.git
cd sumologic-python-mcp

# Install dependencies
uv sync
```

## Step 3: Configure Credentials

Create your `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your Sumo Logic credentials:

```bash
# Required: Default instance
SUMO_ACCESS_ID=your_access_id_here
SUMO_ACCESS_KEY=your_access_key_here
SUMO_ENDPOINT=https://api.sumologic.com

# Optional: Add subdomain for web URL generation
# SUMO_SUBDOMAIN=mycompany

# Optional: Additional instances
# SUMO_PROD_ACCESS_ID=your_prod_id
# SUMO_PROD_ACCESS_KEY=your_prod_key
# SUMO_PROD_ENDPOINT=https://api.us2.sumologic.com
```

**Finding Your Credentials:**

1. Log in to Sumo Logic
2. Go to **Administration** → **Security** → **Access Keys**
3. Create a new access key or use an existing one
4. Copy the Access ID and Access Key

**Finding Your Endpoint:**

- Check your Sumo Logic URL: `https://service.sumologic.com`
- Map to API endpoint:
  - `sumologic.com` → `https://api.sumologic.com`
  - `us2.sumologic.com` → `https://api.us2.sumologic.com`
  - `eu.sumologic.com` → `https://api.eu.sumologic.com`
  - `au.sumologic.com` → `https://api.au.sumologic.com`
  - See full list: <https://help.sumologic.com/docs/api/getting-started/#sumo-logic-endpoints>

## Step 4: Make Wrapper Script Executable

```bash
chmod +x scripts/run-with-env.sh
```

## Step 5: Test the Server

Verify the server starts correctly:

```bash
# Test with uv
uv run sumologic-mcp-server

# You should see output like:
# Configured instances: default
# Validating credentials for instance: default...
# Successfully validated credentials for instance: default
# MCP server started successfully
```

Press `Ctrl+C` to stop the test server.

## Step 6: Configure Claude Code in VSCode

**IMPORTANT:** Claude Code uses the Claude CLI for MCP server configuration, not `.vscode/mcp.json` files. The CLI approach is more reliable and avoids common configuration issues.

**Note about .env files:** The MCP server code does NOT automatically load `.env` files. You must explicitly pass environment variables using the `env` parameter in the configuration.

### Method A: Using Claude CLI with Explicit Credentials (Working Method)

Replace `/path/to/sumologic-python-mcp` with your actual path and update the credentials:

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp add-json sumologic \
  '{"command":"uv","args":["run","--directory","/path/to/sumologic-python-mcp","sumologic-mcp-server"],"env":{"SUMO_ACCESS_ID":"your_access_id","SUMO_ACCESS_KEY":"your_access_key","SUMO_ENDPOINT":"https://api.au.sumologic.com","SUMO_SUBDOMAIN":"your_subdomain"}}' \
  -s user
```

**Finding Your Path:**

```bash
# Run this in your project directory
pwd
# Example output: /Users/yourname/Documents/sumologic-python-mcp
```

**Verify Configuration:**

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp list
```

You should see output like:

```
sumologic: uv run ... - ✓ Connected
```

**Restart VSCode Completely:**

- Quit VSCode fully (Cmd+Q / Ctrl+Q)
- Reopen VSCode

> **Note:** A simple window reload is **not enough**. You must fully quit and restart VSCode.

### Method B: Using Shell Wrapper to Load .env (Alternative)

If you want to keep credentials in your `.env` file, use the wrapper script:

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp add-json sumologic \
  '{"command":"python3","args":["/path/to/sumologic-python-mcp/scripts/run_with_env.py"]}' \
  -s user
```

This Python wrapper loads the `.env` file before starting the server.

**⚠️ Security Note:**

- Method A stores credentials in the MCP configuration
- Method B keeps credentials in `.env` file (more secure)
- Never commit files containing credentials

### Troubleshooting CLI Configuration

**Remove Existing Configuration:**

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp remove sumologic
```

**List All MCP Servers:**

```bash
node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp list
```

**Check Logs:**

1. Open VSCode Output panel (View → Output)
2. Select "Claude VSCode" from dropdown
3. Look for server startup messages and errors

## Step 7: Verify MCP Server

After restarting VSCode, verify the server is working:

1. **Check Server Status**

   Open a Claude Code chat and type:

   ```
   /mcp
   ```

   You should see **"sumologic"** listed as a connected MCP server.

2. **Alternative: Check Output Panel**
   - View → Output
   - Select **"Claude Code"** from dropdown
   - Look for sumologic server startup messages

## Step 8: Test with Claude

Open Claude Code and try these commands:

**Test 1: List Available Tools**

```
List all available Sumo Logic MCP tools
```

**Test 2: Search Logs**

```
Search Sumo Logic logs for "error" in the last hour
```

**Test 3: Get Account Status**

```
Get my Sumo Logic account status
```

**Test 4: List Instances**

```
What Sumo Logic instances are configured?
```

## Troubleshooting

### Issue: MCP Server Not Starting

**Check Logs:**

1. Open **Output** panel in VSCode (View → Output)
2. Select **"Claude Code"** from the dropdown
3. Look for error messages related to "sumologic"

**Common Causes:**

- ✅ Verify `uv` is installed: `uv --version`
- ✅ Check absolute path is correct in CLI command
- ✅ Ensure `.env` file exists and has correct credentials
- ✅ Verify server was added with CLI: `node ~/.vscode/extensions/anthropic.claude-code-*/resources/claude-code/cli.js mcp list`
- ✅ Try fully restarting VSCode (quit and reopen, not just reload window)

### Issue: "Command not found: uv"

**Solution 1: Add uv to PATH**

```bash
# Add to ~/.zshrc or ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"

# Reload shell
source ~/.zshrc  # or source ~/.bashrc
```

**Solution 2: Use absolute path to uv**

Find uv location:

```bash
which uv
# Output: /Users/yourname/.local/bin/uv
```

Update `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "/Users/yourname/.local/bin/uv",
      "args": [
        "--directory",
        "/absolute/path/to/sumologic-python-mcp",
        "run",
        "sumologic-mcp-server"
      ]
    }
  }
}
```

### Issue: Authentication Errors

**Symptoms:**

- "Authentication failed for instance 'default'"
- "Invalid credentials"
- "401 Unauthorized"

**Solutions:**

1. Verify credentials in `.env` file
2. Check access ID and access key are correct (no extra spaces)
3. Ensure endpoint matches your Sumo Logic deployment
4. Test credentials manually:

   ```bash
   curl -u "ACCESS_ID:ACCESS_KEY" https://api.sumologic.com/api/v1/account/status
   ```

5. Verify access key hasn't expired in Sumo Logic UI

### Issue: Permission Denied

**Error:** `Permission denied: scripts/run-with-env.sh`

**Solution:**

```bash
chmod +x scripts/run-with-env.sh
```

### Issue: Server Starts But No Tools Available

**Check:**

1. Verify server logs show successful startup
2. In Claude Code chat, type `/mcp` to see if "sumologic" appears
3. Try reloading window: Command Palette → `Developer: Reload Window`
4. Restart VSCode completely (quit and reopen)
5. Check tool count when asking Claude: "List all available Sumo Logic MCP tools"

**Debug Mode:**
Edit `.env` and add:

```bash
LOG_LEVEL=DEBUG
```

Then check VSCode Output panel (Claude Code) for detailed logs.

## Multi-Instance Configuration

To connect to multiple Sumo Logic environments (prod, staging, dev):

1. **Add instances to `.env`:**

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

1. **Use instances in queries:**

```
Search logs in production:
query: "error"
instance: "prod"

Get staging account status:
instance: "staging"
```

1. **List available instances:**

```
What Sumo Logic instances are configured?
```

## Configuration Options

Customize behavior in `.env`:

```bash
# Performance
MAX_QUERY_LIMIT=1000              # Max results per query
MAX_SEARCH_TIMEOUT=300            # Max search timeout (seconds)
RATE_LIMIT_PER_MINUTE=60          # Requests per minute per tool

# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENABLE_AUDIT_LOG=true             # Log all API operations to file

# Web UI Integration (optional)
SUMO_SUBDOMAIN=mycompany          # For generating web UI URLs
```

## Next Steps

- 📖 **[View All Tools](docs/mcp-tools-reference.md)** - Complete tool documentation
- 🔒 **[Security Guide](SECURITY.md)** - Security best practices
- 🚀 **[Main README](README.md)** - Full project documentation
- 🤝 **[Contributing](CLAUDE.md)** - Development guidelines

## Example Workflows

### Workflow 1: Investigate Errors

```
1. Search for recent errors:
   "Search Sumo Logic logs for 'error' in the last 2 hours"

2. Analyze error patterns:
   "Count errors by source host"

3. Get specific error details:
   "Show me the full log messages for status code 500"
```

### Workflow 2: Cost Analysis

```
1. Get account status:
   "Get my Sumo Logic account status"

2. Analyze data volume:
   "Analyze data volume by source category for the last 7 days"

3. Calculate search costs:
   "Analyze search scan costs for the last 24 hours"
```

### Workflow 3: Content Discovery

```
1. List installed apps:
   "What Sumo Logic apps are installed?"

2. Get personal folder:
   "Show my personal folder contents"

3. Generate shareable link:
   "Get the web URL for content ID 0000000012345678"
```

## Common Commands

**Log Search:**

- `search_sumo_logs` - Search logs with auto query-type detection
- `create_sumo_search_job` - Create async search job for long queries
- `get_sumo_search_job_results` - Get results from async job

**Account Management:**

- `get_account_status` - Account and subscription info
- `get_usage_forecast` - Predict future usage and credits
- `export_usage_report` - Detailed usage reports with CSV

**Content Library:**

- `get_personal_folder` - Your personal content library
- `export_content` - Full content export with async polling
- `list_installed_apps` - Discover pre-built apps

**Data Analysis:**

- `analyze_data_volume` - Volume analysis with timeshift comparison
- `analyze_search_scan_cost` - Analyze pay-per-search costs
- `run_search_audit_query` - Analyze search usage patterns

## Getting Help

**Resources:**

- 📚 Documentation: [docs/mcp-tools-reference.md](docs/mcp-tools-reference.md)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/sumologic-python-mcp/issues)
- 🔒 Security: [SECURITY.md](SECURITY.md)
- 💬 Ask Claude: "How do I use the Sumo Logic MCP server?"

**Claude Code MCP References:**

- [Connect Claude Code to tools via MCP - Official Docs](https://docs.claude.com/en/docs/claude-code/mcp)
- [Configuring MCP Tools in Claude Code - The Better Way](https://scottspence.com/posts/configuring-mcp-tools-in-claude-code-the-better-way)
- [How to Extend Claude Code with MCP Guide](https://dev.to/anthropic/how-to-extend-claude-code-with-mcp-secure-project-file-control-guide)

**Support:**

- Review logs in VSCode Output → "Claude Code"
- Check `.env` file has correct credentials
- Verify server starts: `uv run sumologic-mcp-server`
- Enable debug logging: `LOG_LEVEL=DEBUG` in `.env`

---

**Built with 🤖 assistance from Claude Code**
