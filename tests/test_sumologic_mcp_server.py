"""Basic tests for Sumo Logic MCP Server."""

import pytest
from unittest.mock import AsyncMock, patch
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sumologic_mcp_server import SumoLogicClient, get_sumo_client


class TestSumoLogicClient:
    """Test cases for SumoLogicClient."""
    
    def test_client_initialization(self):
        """Test client initialization with valid parameters."""
        client = SumoLogicClient("test_id", "test_key", "https://api.sumologic.com")
        assert client.access_id == "test_id"
        assert client.access_key == "test_key"
        assert client.endpoint == "https://api.sumologic.com"
    
    def test_endpoint_trailing_slash_removal(self):
        """Test that trailing slash is removed from endpoint."""
        client = SumoLogicClient("test_id", "test_key", "https://api.sumologic.com/")
        assert client.endpoint == "https://api.sumologic.com"


class TestClientInitialization:
    """Test cases for client initialization functions."""
    
    @patch.dict(os.environ, {
        'SUMO_ACCESS_ID': 'test_id',
        'SUMO_ACCESS_KEY': 'test_key',
        'SUMO_ENDPOINT': 'https://api.sumologic.com'
    })
    async def test_get_sumo_client_with_env_vars(self):
        """Test getting client with environment variables set."""
        # Reset global client
        import sumologic_mcp_server
        sumologic_mcp_server.sumo_client = None
        
        client = await get_sumo_client()
        assert client.access_id == "test_id"
        assert client.access_key == "test_key"
        assert client.endpoint == "https://api.sumologic.com"
    
    async def test_get_sumo_client_missing_env_vars(self):
        """Test getting client with missing environment variables."""
        # Reset global client
        import sumologic_mcp_server
        sumologic_mcp_server.sumo_client = None
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="SUMO_ACCESS_ID and SUMO_ACCESS_KEY environment variables are required"):
                await get_sumo_client()


if __name__ == "__main__":
    pytest.main([__file__])