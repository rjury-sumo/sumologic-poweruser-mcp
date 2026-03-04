#!/bin/bash
# Wrapper script to run MCP server in Docker with dynamic path resolution

# Get the directory where this script lives
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Run Docker container with the .env file from project directory
exec docker run -i --rm --env-file "$PROJECT_DIR/.env" sumologic-mcp-server
