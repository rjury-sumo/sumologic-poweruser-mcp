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


def _make_summary_record(sc, collector, source, avg, max_lag, events="500"):
    return {
        "map": {
            "_sourcecategory": sc,
            "_collector": collector,
            "_source": source,
            "avg_lag_minutes": str(avg),
            "max_lag_minutes": str(max_lag),
            "events": events,
        }
    }


class TestAnalyzeIngestLagSummaryMode:
    """Tests for analyze_ingest_lag in summary mode."""

    @pytest.mark.asyncio
    async def test_summary_mode_basic(self, mock_config):
        """Test summary mode returns expected structure with priority tags."""
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
                    _make_summary_record(
                        "aws/cloudtrail", "aws-collector", "cloudtrail-src", "45.3", "120.7"
                    )
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=aws/*",
                from_time="-3h",
                to_time="now",
                lag_threshold_minutes=15.0,
                min_events=100,
                query_mode="summary",
                top_n=20,
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
            assert result["query_parameters"]["min_events"] == 100
            assert result["summary"]["total_records"] == 1
            assert result["summary"]["min_events_filter"] == 100
            assert "high_priority_sources" in result["summary"]

            row = result["results"][0]
            assert row["_sourceCategory"] == "aws/cloudtrail"
            assert row["avg_lag_minutes"] == 45.3
            assert row["max_lag_minutes"] == 120.7
            assert row["events"] == 500
            assert row["priority"] == "high"

    @pytest.mark.asyncio
    async def test_summary_query_includes_min_events_filter(self, mock_config):
        """Confirm the emitted query contains the min_events WHERE clause."""
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
            mock_client.create_search_job.return_value = {"id": "job-qcheck"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {"records": []}
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=test",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                min_events=200,
                query_mode="summary",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)
            assert "where events >= 200" in result["query_parameters"]["query"]

    @pytest.mark.asyncio
    async def test_top3_get_high_priority_rest_get_low(self, mock_config):
        """Results beyond position 3 are tagged priority=low."""
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
            mock_client.create_search_job.return_value = {"id": "job-pri"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            # 5 results — top 3 high, bottom 2 low
            mock_client.get_search_job_records.return_value = {
                "records": [
                    _make_summary_record(f"aws/src{i}", "col", f"src{i}", 10, 200 - i * 10)
                    for i in range(5)
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="*",
                from_time="-3h",
                to_time="now",
                lag_threshold_minutes=15.0,
                min_events=100,
                query_mode="summary",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            priorities = [r["priority"] for r in result["results"]]
            assert priorities[:3] == ["high", "high", "high"]
            assert priorities[3:] == ["low", "low"]

            assert result["summary"]["high_priority_sources"] == 3
            # interpretation should mention the count split
            interp_text = " ".join(result["interpretation"])
            assert "5" in interp_text
            assert "2" in interp_text  # 2 low-priority

    @pytest.mark.asyncio
    async def test_summary_mode_severe_lag_recommendations_reference_worst_source(
        self, mock_config
    ):
        """Severe-lag recommendations should name the worst source category."""
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
                    _make_summary_record("aws/cloudtrail", "hosted-col", "ct-src", "2000", "2880")
                ]
            }
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=aws/cloudtrail*",
                from_time="-48h",
                to_time="now",
                lag_threshold_minutes=15.0,
                min_events=100,
                query_mode="summary",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            interp_text = " ".join(result["interpretation"])
            recs_text = " ".join(result["recommendations"])
            assert "SEVERE" in interp_text
            assert "aws/cloudtrail" in interp_text
            assert "analyze_data_volume_grouped" in recs_text
            assert "aws/cloudtrail" in recs_text
            assert "get_sumo_collectors" in recs_text

    @pytest.mark.asyncio
    async def test_summary_mode_no_results_interpretation(self, mock_config):
        """Empty results produce a healthy interpretation message."""
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
                min_events=100,
                query_mode="summary",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            assert result["summary"]["total_records"] == 0
            assert result["summary"]["high_priority_sources"] == 0
            interp = result["interpretation"][0].lower()
            assert "healthy" in interp or "no results" in interp


class TestAnalyzeIngestLagDistributionMode:
    """Tests for analyze_ingest_lag in distribution mode."""

    @pytest.mark.asyncio
    async def test_distribution_mode_includes_events_and_priority(self, mock_config):
        """Distribution mode result rows include events count and priority tag."""
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
                            "events": "350",
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
                min_events=100,
                query_mode="distribution",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            row = result["results"][0]
            assert "events" in row
            assert row["events"] == 350
            assert row["priority"] == "high"
            assert "pct50_lag_minutes" in row

    @pytest.mark.asyncio
    async def test_distribution_query_includes_events_and_min_events_filter(self, mock_config):
        """Distribution query must include count as events and the min_events WHERE clause."""
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
            mock_client.create_search_job.return_value = {"id": "job-dq"}
            mock_client.get_search_job_status.return_value = DONE_STATUS
            mock_client.get_search_job_records.return_value = {"records": []}
            mock_client.delete_search_job.return_value = {}
            mock_get_client.return_value = mock_client

            result_str = await analyze_ingest_lag(
                scope="_sourceCategory=test",
                from_time="-1h",
                to_time="now",
                lag_threshold_minutes=15.0,
                min_events=150,
                query_mode="distribution",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)
            query = result["query_parameters"]["query"]
            assert "count as events" in query
            assert "where events >= 150" in query

    @pytest.mark.asyncio
    async def test_distribution_mode_negative_lag_names_sources(self, mock_config):
        """Negative lag interpretation should name the affected source categories."""
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
                            "events": "800",
                            "min_lag_minutes": "-120.0",
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
                min_events=100,
                query_mode="distribution",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            interp_text = " ".join(result["interpretation"])
            recs_text = " ".join(result["recommendations"])
            assert "NEGATIVE" in interp_text
            assert "app/windows" in interp_text
            assert "get_sumo_collectors" in recs_text
            assert "format_debug" in recs_text


class TestAnalyzeIngestLagFormatDebugMode:
    """Tests for analyze_ingest_lag in format_debug mode."""

    @pytest.mark.asyncio
    async def test_format_debug_mode_basic(self, mock_config):
        """format_debug returns _format rows; t:fail triggers recommendation."""
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
                min_events=100,
                query_mode="format_debug",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)

            assert result["summary"]["total_records"] == 2
            row = result["results"][0]
            assert "timestampFormat" in row
            assert "_raw" in row

            interp_text = " ".join(result["interpretation"])
            recs_text = " ".join(result["recommendations"])
            assert "t:fail" in interp_text or "fail" in interp_text.lower()
            assert (
                "custom timestamp format" in recs_text.lower()
                or "timestamp format" in recs_text.lower()
            )

    @pytest.mark.asyncio
    async def test_format_debug_uses_messages_not_records(self, mock_config):
        """format_debug must call get_search_job_messages, not get_search_job_records."""
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
                min_events=100,
                query_mode="format_debug",
                top_n=20,
                instance="default",
            )

            mock_client.get_search_job_messages.assert_called_once()
            mock_client.get_search_job_records.assert_not_called()


class TestAnalyzeIngestLagValidation:
    """Tests for parameter validation."""

    @pytest.mark.asyncio
    async def test_invalid_query_mode_returns_error(self, mock_config):
        """Invalid query_mode returns an error JSON."""
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
                min_events=100,
                query_mode="invalid_mode",
                top_n=20,
                instance="default",
            )
            result = json.loads(result_str)
            assert "error" in result

    @pytest.mark.asyncio
    async def test_search_job_uses_by_receipt_time(self, mock_config):
        """create_search_job must be called with by_receipt_time=True."""
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
                min_events=100,
                query_mode="summary",
                top_n=20,
                instance="default",
            )

            call_kwargs = mock_client.create_search_job.call_args
            assert call_kwargs.kwargs.get("by_receipt_time") is True
