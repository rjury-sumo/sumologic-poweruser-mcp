"""Basic tests for Sumo Logic MCP Server."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from sumologic_mcp_server.sumologic_mcp_server import SumoLogicClient, get_sumo_client, clients
from sumologic_mcp_server.config import SumoInstanceConfig, reset_config


class TestSumoLogicClient:
    """Test cases for SumoLogicClient."""

    def test_client_initialization(self):
        """Test client initialization with valid parameters."""
        config = SumoInstanceConfig(
            access_id="test_id",
            access_key="test_key",
            endpoint="https://api.sumologic.com"
        )
        client = SumoLogicClient(config, "test")
        assert client.access_id == "test_id"
        assert client.access_key == "test_key"
        assert client.endpoint == "https://api.sumologic.com"
        assert client.instance_name == "test"

    def test_endpoint_trailing_slash_removal(self):
        """Test that trailing slash is removed from endpoint."""
        config = SumoInstanceConfig(
            access_id="test_id",
            access_key="test_key",
            endpoint="https://api.sumologic.com/"
        )
        client = SumoLogicClient(config, "test")
        assert client.endpoint == "https://api.sumologic.com"


class TestClientInitialization:
    """Test cases for client initialization functions - uses real env vars."""

    def setup_method(self):
        """Reset state before each test."""
        clients.clear()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not os.getenv("SUMO_ACCESS_ID"), reason="Requires SUMO_ACCESS_ID env var")
    async def test_get_sumo_client_with_env_vars(self):
        """Test getting client with environment variables set (uses real creds)."""
        clients.clear()

        client = await get_sumo_client('default')
        assert client.access_id is not None
        assert client.access_key is not None
        assert client.endpoint is not None
        assert client.instance_name == "default"

    @pytest.mark.asyncio
    async def test_get_sumo_client_missing_env_vars(self):
        """Test getting client with missing environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            reset_config()
            clients.clear()

            from sumologic_mcp_server.exceptions import InstanceNotFoundError

            with pytest.raises(Exception):  # Will raise either ValueError or InstanceNotFoundError
                await get_sumo_client('default')


class TestConfig:
    """Test cases for configuration."""

    def setup_method(self):
        """Reset state before each test."""
        reset_config()

    @patch.dict(os.environ, {
        'SUMO_ACCESS_ID': 'test_id',
        'SUMO_ACCESS_KEY': 'test_key',
        'SUMO_ENDPOINT': 'https://api.sumologic.com'
    }, clear=True)
    def test_config_loads_default_instance(self):
        """Test that config loads default instance from env vars."""
        from sumologic_mcp_server.config import get_config
        reset_config()

        config = get_config()
        assert 'default' in config.list_instances()

        instance = config.get_instance('default')
        assert instance.access_id == "test_id"
        assert instance.access_key == "test_key"

    @patch.dict(os.environ, {
        'SUMO_ACCESS_ID': 'default_id',
        'SUMO_ACCESS_KEY': 'default_key',
        'SUMO_STAGING_ACCESS_ID': 'staging_id',
        'SUMO_STAGING_ACCESS_KEY': 'staging_key',
        'SUMO_STAGING_ENDPOINT': 'https://api.eu.sumologic.com'
    }, clear=True)
    def test_config_loads_multiple_instances(self):
        """Test that config loads multiple instances."""
        from sumologic_mcp_server.config import get_config
        reset_config()

        config = get_config()
        instances = config.list_instances()

        assert 'default' in instances
        assert 'staging' in instances
        assert len(instances) >= 2


class TestValidation:
    """Test cases for input validation."""

    def test_query_validation(self):
        """Test query validation."""
        from sumologic_mcp_server.validation import validate_query_input
        from sumologic_mcp_server.exceptions import ValidationError

        # Valid query
        assert validate_query_input("error | count") == "error | count"

        # Empty query
        with pytest.raises(ValidationError):
            validate_query_input("")

        # Query with null bytes
        with pytest.raises(ValidationError):
            validate_query_input("test\x00query")

    def test_time_range_validation(self):
        """Test time range validation."""
        from sumologic_mcp_server.validation import validate_time_range
        from sumologic_mcp_server.exceptions import ValidationError

        # Valid ranges
        assert validate_time_range(1) == 1
        assert validate_time_range(24) == 24

        # Invalid ranges
        with pytest.raises(ValidationError):
            validate_time_range(-1)

        with pytest.raises(ValidationError):
            validate_time_range(10000)  # More than 1 year

    def test_pagination_validation(self):
        """Test pagination validation."""
        from sumologic_mcp_server.validation import validate_pagination
        from sumologic_mcp_server.exceptions import ValidationError

        # Valid pagination
        limit, offset = validate_pagination(100, 0)
        assert limit == 100
        assert offset == 0

        # Invalid limit
        with pytest.raises(ValidationError):
            validate_pagination(2000, 0)  # Exceeds max

        # Invalid offset
        with pytest.raises(ValidationError):
            validate_pagination(100, -1)


class TestRateLimiter:
    """Test cases for rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test that rate limiter allows requests within limit."""
        from sumologic_mcp_server.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=5)

        # Should allow 5 requests
        for _ in range(5):
            await limiter.acquire("test_tool")

        stats = limiter.get_stats("test_tool")
        assert stats["current_requests"] == 5
        assert stats["remaining"] == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks excess requests."""
        from sumologic_mcp_server.rate_limiter import RateLimiter, RateLimitError

        limiter = RateLimiter(requests_per_minute=2)

        # Use up the limit
        await limiter.acquire("test_tool")
        await limiter.acquire("test_tool")

        # Next request should be blocked
        with pytest.raises(RateLimitError):
            await limiter.acquire("test_tool")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
