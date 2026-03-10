#!/usr/bin/env python3
"""Unit tests for get_usage_forecast tool."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from sumologic_poweruser_mcp.sumologic_mcp_server import get_usage_forecast


@pytest.fixture
def mock_client():
    """Create a mock SumoLogicClient."""
    client = MagicMock()
    client.get_usage_forecast = AsyncMock(
        return_value={
            "forecastedTotalCredits": 1000.0,
            "forecastedContinuousIngest": 500.0,
            "forecastedFrequentIngest": 300.0,
            "forecastedStorage": 150.0,
            "forecastedMetricsIngest": 50.0,
        }
    )
    client.get_usage_forecast_default = AsyncMock(
        return_value={
            "forecastedTotalCredits": 5000.0,  # Different for contract term
            "forecastedContinuousIngest": 2500.0,
            "forecastedFrequentIngest": 1500.0,
            "forecastedStorage": 750.0,
            "forecastedMetricsIngest": 250.0,
        }
    )
    return client


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock()
    config.server_config.rate_limit_per_minute = 60
    return config


@pytest.mark.asyncio
async def test_usage_forecast_with_explicit_days(mock_client, mock_config):
    """Test get_usage_forecast with explicit number_of_days parameter."""
    with patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client",
        return_value=mock_client,
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
    ) as mock_limiter:
        mock_limiter.return_value.acquire = AsyncMock()

        # Call with 7 days
        result = await get_usage_forecast(number_of_days=7, instance="default")

        # Verify the correct API method was called
        mock_client.get_usage_forecast.assert_called_once_with(7)
        mock_client.get_usage_forecast_default.assert_not_called()

        # Verify result
        result_dict = json.loads(result)
        assert result_dict["forecastedTotalCredits"] == 1000.0
        assert "error" not in result_dict


@pytest.mark.asyncio
async def test_usage_forecast_without_days_default_contract_term(mock_client, mock_config):
    """Test get_usage_forecast without number_of_days (should use contract term default)."""
    with patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client",
        return_value=mock_client,
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
    ) as mock_limiter:
        mock_limiter.return_value.acquire = AsyncMock()

        # Call with number_of_days=None (explicit contract term default)
        result = await get_usage_forecast(number_of_days=None, instance="default")

        # Verify the default API method was called
        mock_client.get_usage_forecast.assert_not_called()
        mock_client.get_usage_forecast_default.assert_called_once()

        # Verify result shows contract term forecast (higher values)
        result_dict = json.loads(result)
        assert result_dict["forecastedTotalCredits"] == 5000.0
        assert "error" not in result_dict


@pytest.mark.asyncio
async def test_usage_forecast_validates_days_range(mock_client, mock_config):
    """Test that number_of_days is validated to be between 1 and 365."""
    with patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client",
        return_value=mock_client,
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
    ) as mock_limiter:
        mock_limiter.return_value.acquire = AsyncMock()

        # Test with 0 days (invalid)
        result = await get_usage_forecast(number_of_days=0, instance="default")
        result_dict = json.loads(result)
        assert "error" in result_dict
        assert "between 1 and 365" in result_dict["error"]

        # Test with 366 days (invalid)
        result = await get_usage_forecast(number_of_days=366, instance="default")
        result_dict = json.loads(result)
        assert "error" in result_dict
        assert "between 1 and 365" in result_dict["error"]

        # Verify API was never called for invalid inputs
        mock_client.get_usage_forecast.assert_not_called()
        mock_client.get_usage_forecast_default.assert_not_called()


@pytest.mark.asyncio
async def test_usage_forecast_with_30_days(mock_client, mock_config):
    """Test get_usage_forecast with 30 days."""
    with patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client",
        return_value=mock_client,
    ), patch(
        "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
    ) as mock_limiter:
        mock_limiter.return_value.acquire = AsyncMock()

        # Call with 30 days
        result = await get_usage_forecast(number_of_days=30, instance="default")

        # Verify the correct API method was called with 30
        mock_client.get_usage_forecast.assert_called_once_with(30)
        mock_client.get_usage_forecast_default.assert_not_called()

        # Verify result
        result_dict = json.loads(result)
        assert "forecastedTotalCredits" in result_dict
        assert "error" not in result_dict
