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
git clone https://github.com/yourusername/sumologic-python-mcp.git
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
  - See full list: https://help.sumologic.com/docs/api/getting-started/#sumo-logic-endpoints

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

Claude Code uses a dedicated MCP configuration file, not VSCode settings.

### Method A: Using Environment File (Recommended - More Secure)

1. **Open MCP Configuration**
   - Press `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P` (Windows/Linux)
   - Type: `MCP: Open User Configuration`
   - Press Enter

   This creates/opens `~/.claude.json`

2. **Add Configuration**

   Replace `/absolute/path/to/sumologic-python-mcp` with your actual path:

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

   **Finding Your Absolute Path:**
   ```bash
   # Run this in your project directory
   pwd
   # Copy the output and use it in the config above
   ```

### Method B: Direct Configuration (Credentials in Config File)

Alternatively, specify credentials directly in `~/.claude.json`:

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/sumologic-python-mcp",
        "run",
        "sumologic-mcp-server"
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

### Method C: Project-Level Configuration

For project-specific MCP servers, create `.mcp.json` in your project root:

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

**⚠️ Security Note:**
- Method A (wrapper script) is most secure - credentials stay in `.env` (git-ignored)
- Avoid committing `.mcp.json` files with credentials to version control
- User config (`~/.claude.json`) is safer than project config for credentials

## Step 7: Activate the MCP Server

1. **Save the configuration file** (Cmd+S / Ctrl+S)

2. **Reload VSCode Window**
   - Open Command Palette: `Cmd+Shift+P` (macOS) or `Ctrl+Shift+P` (Windows/Linux)
   - Type: `Developer: Reload Window`
   - Press Enter

   **Note:** A simple window reload is sometimes not enough. If MCP servers don't load, fully restart VSCode (quit and reopen).

3. **Verify Server Status**

   **Method 1: Check with Claude Code**
   - Open a Claude Code chat
   - Type: `/mcp`
   - This shows connected MCP servers and their status
   - Look for **"sumologic"** in the list

   **Method 2: Check Status Bar**
   - Look at the **bottom-right status bar** in VSCode
   - You should see an MCP indicator (if available)
   - Click it to view MCP server status

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
- ✅ Check absolute path is correct in `~/.claude.json` or `.mcp.json`
- ✅ Ensure `.env` file exists and has correct credentials
- ✅ Verify wrapper script is executable: `ls -la scripts/run-with-env.sh`
- ✅ Try fully restarting VSCode (not just reload window)

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

Update `~/.claude.json`:
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

2. **Use instances in queries:**

```
Search logs in production:
query: "error"
instance: "prod"

Get staging account status:
instance: "staging"
```

3. **List available instances:**

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

**Support:**
- Review logs in VSCode Output → "Claude Code"
- Check `.env` file has correct credentials
- Verify server starts: `uv run sumologic-mcp-server`
- Enable debug logging: `LOG_LEVEL=DEBUG` in `.env`

---

**Built with 🤖 assistance from Claude Code**
