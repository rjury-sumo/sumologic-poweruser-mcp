#!/bin/bash
# Wrapper script to load .env file and run the MCP server

# Get the directory where this script lives
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Load .env file if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a  # automatically export all variables
    source "$PROJECT_DIR/.env"
    set +a
fi

# Run the MCP server using uv
cd "$PROJECT_DIR"
exec uv run sumologic-poweruser-mcp
