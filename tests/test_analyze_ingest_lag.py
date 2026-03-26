"""Unit tests for analyze_ingest_lag tool."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sumologic_poweruser_mcp.sumologic_mcp_server import analyze_ingest_lag


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock()
    config.server_config.rate_limit_per_minute = 60
    return config


DONE_STATUS = {"state": "DONE GATHERING RESULTS"}


class TestAnalyzeIngestLagSummaryMode:
    """Tests for analyze_ingest_lag in summary mode."""

    @pytest.mark.asyncio
    async def test_summary_mode_basic(self, mock_config):
        """Test summary mode returns expected structure."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-123"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "_sourcecategory": "aws/cloudtrail",
                            "_collector": "aws-collector",
                            "_source": "cloudtrail-src",
                            "avg_lag_minutes": "45.3",
                            "max_lag_minutes": "120.7",
                            "events": "500",
                        }
                    }
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=aws/*",
                from_time="-3h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="summary",
                top_n=50,
                instance="default",
            )
            result = json.loads(result_str)

            assert "query_parameters" in result
            assert "summary" in result
            assert "results" in result
            assert "interpretation" in result
            assert "recommendations" in result

            assert result["query_parameters"]["query_mode"] == "summary"
            assert result["query_parameters"]["by_receipt_time"] is True
            assert result["summary"]["total_records"] == 1

            row = result["results"][0]
            assert row["_sourceCategory"] == "aws/cloudtrail"
            assert row["_collector"] == "aws-collector"
            assert row["avg_lag_minutes"] == 45.3
            assert row["max_lag_minutes"] == 120.7
            assert row["events"] == 500

    @pytest.mark.asyncio
    async def test_summary_mode_high_lag_recommendations(self, mock_config):
        """Test that high lag (>60min) triggers appropriate recommendations."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-high-lag"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "_sourcecategory": "aws/s3/access",
                            "_collector": "hosted",
                            "_source": "s3-source",
                            "avg_lag_minutes": "180.0",
                            "max_lag_minutes": "360.0",
                            "events": "100",
                        }
                    }
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=aws/s3/*",
                from_time="-6h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="summary",
                top_n=50,
                instance="default",
            )
            result = json.loads(result_str)

            # High lag (360 min = 6 hours) should trigger high-lag interpretation
            assert len(result["interpretation"]) > 0
            assert len(result["recommendations"]) > 0
            interp_text = " ".join(result["interpretation"])
            assert "HIGH LAG" in interp_text or "SEVERE" in interp_text
            # Should mention data volume check
            recs_text = " ".join(result["recommendations"])
            assert "analyze_data_volume_grouped" in recs_text
            assert "get_sumo_collectors" in recs_text

    @pytest.mark.asyncio
    async def test_summary_mode_severe_lag_over_24h(self, mock_config):
        """Test that >24h lag triggers SNS notification recommendation."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-severe"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "_sourcecategory": "aws/cloudtrail",
                            "_collector": "hosted",
                            "_source": "ct-src",
                            "avg_lag_minutes": "2000.0",
                            "max_lag_minutes": "2880.0",  # 48 hours
                            "events": "200",
                        }
                    }
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=aws/cloudtrail*",
                from_time="-48h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="summary",
                top_n=50,
                instance="default",
            )
            result = json.loads(result_str)

            interp_text = " ".join(result["interpretation"])
            recs_text = " ".join(result["recommendations"])
            assert "SEVERE" in interp_text
            assert "SNS" in interp_text or "SNS" in recs_text
            assert "analyze_data_volume_grouped" in recs_text

    @pytest.mark.asyncio
    async def test_summary_mode_no_results_interpretation(self, mock_config):
        """Test that empty results produce a healthy interpretation message."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-empty"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {"records": []}
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=app/healthy",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="summary",
                top_n=50,
                instance="default",
            )
            result = json.loads(result_str)

            assert result["summary"]["total_records"] == 0
            assert len(result["interpretation"]) == 1
            assert (
                "healthy" in result["interpretation"][0].lower()
                or "no results" in result["interpretation"][0].lower()
            )


class TestAnalyzeIngestLagDistributionMode:
    """Tests for analyze_ingest_lag in distribution mode."""

    @pytest.mark.asyncio
    async def test_distribution_mode_basic(self, mock_config):
        """Test distribution mode returns percentile fields."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-dist"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "_sourcecategory": "app/nginx",
                            "min_lag_minutes": "1.2",
                            "max_lag_minutes": "30.5",
                            "_pct_25": "2.1",
                            "_pct_50": "5.3",
                            "_pct_75": "18.7",
                        }
                    }
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=app/nginx",
                from_time="-3h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="distribution",
                top_n=50,
                instance="default",
            )
            result = json.loads(result_str)

            assert result["query_parameters"]["query_mode"] == "distribution"
            assert result["summary"]["total_records"] == 1

            row = result["results"][0]
            assert "_sourceCategory" in row
            assert "min_lag_minutes" in row
            assert "max_lag_minutes" in row
            assert "pct25_lag_minutes" in row
            assert "pct50_lag_minutes" in row
            assert "pct75_lag_minutes" in row
            assert row["pct50_lag_minutes"] == 5.3

    @pytest.mark.asyncio
    async def test_distribution_mode_negative_lag_detection(self, mock_config):
        """Test that negative min_lag triggers timezone misconfiguration interpretation."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-neg"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "_sourcecategory": "app/windows",
                            "min_lag_minutes": "-120.0",  # future timestamps
                            "max_lag_minutes": "5.0",
                            "_pct_25": "-60.0",
                            "_pct_50": "-30.0",
                            "_pct_75": "1.0",
                        }
                    }
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=app/windows",
                from_time="-3h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="distribution",
                top_n=50,
                instance="default",
            )
            result = json.loads(result_str)

            interp_text = " ".join(result["interpretation"])
            recs_text = " ".join(result["recommendations"])
            assert "NEGATIVE" in interp_text
            assert "timezone" in interp_text.lower() or "timezone" in recs_text.lower()
            assert "get_sumo_collectors" in recs_text
            assert "format_debug" in recs_text


class TestAnalyzeIngestLagFormatDebugMode:
    """Tests for analyze_ingest_lag in format_debug mode."""

    @pytest.mark.asyncio
    async def test_format_debug_mode_basic(self, mock_config):
        """Test format_debug mode fetches messages and returns _format fields."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-fmt"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_messages.return_value = {
                "messages": [
                    {
                        "map": {
                            "_messagetime": "1711447530000",
                            "_receipttime": "1711447590000",
                            "lag_minutes": "1.0",
                            "_sourcecategory": "app/nginx",
                            "_collector": "linux-collector",
                            "_source": "nginx-src",
                            "timestampFormat": "t:full,o:0,l:24,p:yyyy-MM-dd HH:mm:ss,SSS",
                            "_raw": "2024-03-26 10:05:30,000 INFO starting up",
                        }
                    },
                    {
                        "map": {
                            "_messagetime": "1711447530000",
                            "_receipttime": "1711447590000",
                            "lag_minutes": "1.0",
                            "_sourcecategory": "app/nginx",
                            "_collector": "linux-collector",
                            "_source": "nginx-src",
                            "timestampFormat": "t:fail,o:0,l:0,p:",
                            "_raw": "no timestamp here",
                        }
                    },
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=app/nginx",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="format_debug",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            assert result["query_parameters"]["query_mode"] == "format_debug"
            assert result["summary"]["total_records"] == 2

            row = result["results"][0]
            assert "timestampFormat" in row
            assert "_raw" in row
            assert "lag_minutes" in row

            # fail format should trigger interpretation
            interp_text = " ".join(result["interpretation"])
            assert "t:fail" in interp_text or "fail" in interp_text.lower()
            recs_text = " ".join(result["recommendations"])
            assert (
                "custom timestamp format" in recs_text.lower()
                or "timestamp format" in recs_text.lower()
            )

    @pytest.mark.asyncio
    async def test_format_debug_uses_messages_not_records(self, mock_config):
        """Confirm format_debug calls get_search_job_messages, not get_search_job_records."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-msg"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_messages.return_value = {"messages": []}
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            await analyze_ingest_lag(
                scope="_sourceCategory=test",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="format_debug",
                top_n=20,
                instance="default",
            )

            mock_client.get_search_job_messages.assert_called_once()
            mock_client.get_search_job_records.assert_not_called()


class TestAnalyzeIngestLagValidation:
    """Tests for parameter validation in analyze_ingest_lag."""

    @pytest.mark.asyncio
    async def test_invalid_query_mode_returns_error(self, mock_config):
        """Test that an invalid query_mode returns an error JSON."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()
            mock_get_client.return_value = AsyncMock()

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=test",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="invalid_mode",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)
            assert "error" in result

    @pytest.mark.asyncio
    async def test_search_job_uses_by_receipt_time(self, mock_config):
        """Verify create_search_job is called with by_receipt_time=True."""
        with patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            mock_client = AsyncMock()
            mock_client.create_search_job.return_value = {"id": "job-brt"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {"records": []}
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            await analyze_ingest_lag(
                scope="_sourceCategory=test",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                query_mode="summary",
                top_n=20,
                instance="default",
            )

            call_kwargs = mock_client.create_search_job.call_args
            assert call_kwargs.kwargs.get("by_receipt_time") is True
