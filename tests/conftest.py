"""Pytest configuration and fixtures."""

import os
from pathlib import Path
import pytest


def pytest_configure(config):
    """Load environment variables from .env file before running tests."""
    # Find .env file in project root
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"

    if env_file.exists():
        # Load .env file
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith("#"):
                    # Parse KEY=VALUE
                    if "=" in line:
                        key, value = line.split("=", 1)
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value


@pytest.fixture(autouse=True)
async def cleanup_clients():
    """Clean up clients after each test to prevent event loop issues."""
    yield
    # Clean up any clients created during the test
    from sumologic_mcp_server.sumologic_mcp_server import clients
    from sumologic_mcp_server.config import reset_config

    for client in clients.values():
        if hasattr(client, 'session') and client.session:
            await client.session.aclose()
    clients.clear()
    # Reset config so it reloads from env vars for next test
    reset_config()
