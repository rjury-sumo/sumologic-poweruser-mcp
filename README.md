# sumologic-python-mcp
Example MCP experiments for Sumo Logic APIs, mostly written by Claude !

## Available Tools


## Setup

```
# Create a virtual environment
python -m venv sumo-mcp-env
source sumo-mcp-env/bin/activate  # On Windows: sumo-mcp-env\Scripts\activate

# Install required packages
pip install fastmcp httpx pydantic
```

Create env file:
```
export SUMO_ACCESS_ID="your_access_id_here"
export SUMO_ACCESS_KEY="your_access_key_here"
export SUMO_ENDPOINT="https://api.sumologic.com"  # Adjust for your deployment
```

Setup MCP
Add the following to your Claude Desktop configuration file:
Mac: ~/Library/Application Support/Claude/claude_desktop_config.json
Windows: %APPDATA%\Claude\claude_desktop_config.json

```
{
  "mcpServers": {
    "sumologic": {
      "command": "python",
      "args": ["/path/to/your/sumologic_mcp_server.py"],
      "env": {
        "SUMO_ACCESS_ID": "your_access_id_here",
        "SUMO_ACCESS_KEY": "your_access_key_here",
        "SUMO_ENDPOINT": "https://api.sumologic.com"
      }
    }
  }
}
```