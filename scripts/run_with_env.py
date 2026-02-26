#!/usr/bin/env python3
"""Wrapper script to load .env file and run the MCP server."""

import os
import sys
from pathlib import Path
import subprocess

# Get project directory (parent of scripts/)
project_dir = Path(__file__).parent.parent

# Load .env file if it exists
env_file = project_dir / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key.strip()] = value

# Run the MCP server using uv
os.chdir(project_dir)
result = subprocess.run(
    ["uv", "run", "sumologic-mcp-server"],
    env=os.environ
)
sys.exit(result.returncode)
