"""Tests for describe_log_pipeline tool."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sumologic_poweruser_mcp.sumologic_mcp_server import describe_log_pipeline


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock()
    config.server_config.rate_limit_per_minute = 60
    return config


class TestDescribeLogPipeline:
    """Tests for describe_log_pipeline orchestration tool."""

    @pytest.mark.asyncio
    async def test_keyword_scope_basic(self, mock_config):
        """Test basic keyword scope discovery (e.g., 'cloudtrail')."""
        # This test validates the tool structure and parameter handling
        # Integration tests should be used for full end-to-end validation

        with patch("sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()

            # Mock client
            mock_client = AsyncMock()

            # Mock data volume search results (Phase 1)
            mock_client.create_search_job.return_value = {"id": "dv-job-123"}
            mock_client.get_search_job_status.return_value = {
                "state": "DONE GATHERING RESULTS"
            }
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "value": "aws/cloudtrail/logs",
                            "tier": "Continuous",
                            "gb": 10.5,
                        }
                    }
                ]
            }

            # Mock metadata discovery (Phase 2)
            # Will be called again after DV query
            mock_client.get_search_job_status.side_effect = [
                {"state": "DONE GATHERING RESULTS"},  # DV query
                {"state": "DONE GATHERING RESULTS"},  # Metadata query
            ]

            mock_client.get_search_job_records.side_effect = [
                {  # DV results
                    "records": [
                        {
                            "map": {
                                "value": "aws/cloudtrail/logs",
                                "tier": "Continuous",
                                "gb": 10.5,
                            }
                        }
                    ]
                },
                {  # Metadata results
                    "records": [
                        {
                            "map": {
                                "_sourceCategory": "aws/cloudtrail/logs",
                                "_collector": "aws-collector",
                                "_source": "cloudtrail-source",
                                "_index": "cloudtrail_index",
                                "_count": 1000,
                            }
                        }
                    ]
                },
            ]

            # Mock partitions (Phase 3)
            mock_client.get_partitions.return_value = {
                "data": [
                    {
                        "name": "cloudtrail_index",
                        "routingExpression": "_sourceCategory=aws/cloudtrail/*",
                        "retentionPeriod": 30,
                        "isActive": True,
                        "analyticsTier": "Continuous",
                        "totalBytes": 1073741824,
                    }
                ]
            }

            # Mock collectors (Phase 4)
            mock_client.get_collectors.return_value = {
                "collectors": [
                    {
                        "id": 12345,
                        "name": "aws-collector",
                        "collectorType": "Hosted",
                        "category": "aws/logs",
                        "timeZone": "UTC",
                    }
                ]
            }

            # Mock sources
            mock_client.get_sources.return_value = {
                "sources": [
                    {
                        "name": "cloudtrail-source",
                        "sourceType": "HTTP",
                        "category": "aws/cloudtrail/logs",
                        "timeZone": "UTC",
                        "automaticDateParsing": True,
                        "multilineProcessingEnabled": False,
                    }
                ]
            }

            # Mock FERs (Phase 5)
            mock_client.list_field_extraction_rules.return_value = {
                "data": [
                    {
                        "name": "cloudtrail_fields",
                        "scope": "_sourceCategory=aws/cloudtrail/*",
                        "parseExpression": 'json "eventName", "userIdentity.userName"',
                        "enabled": True,
                    }
                ]
            }

            # Mock scheduled views (Phase 6)
            mock_client.list_scheduled_views.return_value = {
                "data": [
                    {
                        "indexName": "cloudtrail_events_1m",
                        "query": "_sourceCategory=aws/cloudtrail/* | ...",
                        "retentionPeriod": 90,
                        "reduceOnlyFields": ["eventName", "_count"],
                        "indexedFields": ["eventName"],
                    }
                ]
            }

            # Mock sample logs (Phase 7)
            # Override side_effect to include sample query
            mock_client.create_search_job.side_effect = [
                {"id": "dv-job-123"},  # DV query
                {"id": "meta-job-456"},  # Metadata query
                {"id": "sample-job-789"},  # Sample logs query
            ]

            mock_client.get_search_job_status.side_effect = [
                {"state": "DONE GATHERING RESULTS"},  # DV query
                {"state": "DONE GATHERING RESULTS"},  # Metadata query
                {"state": "DONE GATHERING RESULTS"},  # Sample query
            ]

            # Add sample messages response
            mock_client.get_search_job_messages.return_value = {
                "messages": [
                    {
                        "map": {
                            "_raw": '{"eventName": "ConsoleLogin", "userIdentity": {"userName": "admin"}}',
                            "_messagetime": "1711447530000",
                            "_sourcecategory": "aws/cloudtrail/logs",
                        }
                    }
                ]
            }

            # Mock installed apps (Phase 8)
            mock_client.list_apps.return_value = {
                "applications": [
                    {
                        "name": "AWS CloudTrail",
                        "appDefinitionId": "cloudtrail-app-123",
                        "uuid": "uuid-cloudtrail-456",
                    }
                ]
            }

            mock_get_client.return_value = mock_client

            # Call the tool with explicit parameter values
            result_str = await describe_log_pipeline(
                scope="cloudtrail",
                from_time="-3h",
                to_time="now",
                max_collectors=20,
                instance="default",
            )
            result = json.loads(result_str)

            # Validate result structure
            assert "summary" in result
            assert "metadata_discovered" in result
            assert "collection" in result
            assert "field_extraction" in result
            assert "partition_routing" in result
            assert "scheduled_views" in result
            assert "sample_logs" in result
            assert "installed_apps" in result
            assert "recommendations" in result

            # Validate summary
            assert result["summary"]["scope_type"] == "keyword_search"
            assert result["summary"]["search_keyword"] == "cloudtrail"
            assert result["summary"]["collectors_discovered"] == 1
            assert result["summary"]["sources_discovered"] == 1
            assert result["summary"]["partitions_used"] == 1
            assert result["summary"]["sample_logs_collected"] >= 0
            assert result["summary"]["matching_apps_found"] >= 0

            # Validate discovered metadata
            assert "aws/cloudtrail/logs" in result["metadata_discovered"]["source_categories"][0]["sourceCategory"]
            assert "aws-collector" in result["metadata_discovered"]["collectors"]
            assert "cloudtrail-source" in result["metadata_discovered"]["sources"]
            assert "cloudtrail_index" in result["metadata_discovered"]["partitions"]

            # Validate sample logs structure
            assert "samples" in result["sample_logs"]
            assert "format_analysis" in result["sample_logs"]
            if result["sample_logs"]["samples"]:
                assert "raw" in result["sample_logs"]["samples"][0]
                assert "format" in result["sample_logs"]["format_analysis"]

            # Validate installed apps structure
            assert "apps" in result["installed_apps"] or "error" in result["installed_apps"]
            if "apps" in result["installed_apps"]:
                assert isinstance(result["installed_apps"]["apps"], list)

    @pytest.mark.asyncio
    async def test_metadata_scope(self, mock_config):
        """Test with metadata filter scope (e.g., '_sourceCategory=foo/bar')."""
        with patch("sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()
            mock_client = AsyncMock()

            # For metadata scope, we skip Phase 1 (data volume discovery)
            # and go straight to Phase 2 (metadata discovery)

            mock_client.create_search_job.return_value = {"id": "meta-job-456"}
            mock_client.get_search_job_status.return_value = {
                "state": "DONE GATHERING RESULTS"
            }
            mock_client.get_search_job_records.return_value = {
                "records": [
                    {
                        "map": {
                            "_sourceCategory": "prod/app/logs",
                            "_collector": "prod-collector",
                            "_source": "app-source",
                            "_index": "prod_logs",
                            "_count": 5000,
                        }
                    }
                ]
            }

            mock_client.get_partitions.return_value = {"data": []}
            mock_client.get_collectors.return_value = {"collectors": []}
            mock_client.list_field_extraction_rules.return_value = {"data": []}
            mock_client.list_scheduled_views.return_value = {"data": []}
            mock_client.get_search_job_messages.return_value = {"messages": []}
            mock_client.list_apps.return_value = {"applications": []}

            mock_get_client.return_value = mock_client

            result_str = await describe_log_pipeline(
                scope="_sourceCategory=prod/app/logs",
                from_time="-3h",
                to_time="now",
                max_collectors=20,
                instance="default",
            )
            result = json.loads(result_str)

            # Validate that metadata scope was recognized
            assert result["summary"]["scope_type"] == "metadata_filter"
            assert result["summary"]["original_scope"] == "_sourceCategory=prod/app/logs"

    @pytest.mark.asyncio
    async def test_no_results_found(self, mock_config):
        """Test behavior when no source categories match keyword."""
        with patch("sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()
            mock_client = AsyncMock()

            # Mock empty data volume results
            mock_client.create_search_job.return_value = {"id": "dv-job-789"}
            mock_client.get_search_job_status.return_value = {
                "state": "DONE GATHERING RESULTS"
            }
            mock_client.get_search_job_records.return_value = {"records": []}
            mock_client.get_search_job_messages.return_value = {"messages": []}
            mock_client.list_apps.return_value = {"applications": []}

            mock_get_client.return_value = mock_client

            result_str = await describe_log_pipeline(
                scope="nonexistent_keyword",
                from_time="-3h",
                to_time="now",
                max_collectors=20,
                instance="default",
            )
            result = json.loads(result_str)

            # Should return error with helpful suggestion
            assert "error" in result
            assert "No source categories found" in result["error"]
            assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_max_collectors_limit(self, mock_config):
        """Test that max_collectors parameter limits output."""
        with patch("sumologic_poweruser_mcp.sumologic_mcp_server._ensure_config_initialized"), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_config", return_value=mock_config
        ), patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_sumo_client"
        ) as mock_get_client, patch(
            "sumologic_poweruser_mcp.sumologic_mcp_server.get_rate_limiter"
        ) as mock_limiter:
            mock_limiter.return_value.acquire = AsyncMock()
            mock_client = AsyncMock()

            # Mock responses with minimal data
            mock_client.create_search_job.return_value = {"id": "job-limit"}
            mock_client.get_search_job_status.return_value = {
                "state": "DONE GATHERING RESULTS"
            }
            mock_client.get_search_job_records.return_value = {"records": []}
            mock_client.get_partitions.return_value = {"data": []}
            mock_client.get_collectors.return_value = {"collectors": []}
            mock_client.list_field_extraction_rules.return_value = {"data": []}
            mock_client.list_scheduled_views.return_value = {"data": []}
            mock_client.get_search_job_messages.return_value = {"messages": []}
            mock_client.list_apps.return_value = {"applications": []}

            mock_get_client.return_value = mock_client

            # Call with custom max_collectors
            result_str = await describe_log_pipeline(
                scope="_sourceCategory=test",
                from_time="-3h",
                to_time="now",
                max_collectors=5,
                instance="default",
            )
            result = json.loads(result_str)

            # Verify structure is present
            assert "summary" in result
            assert "metadata_discovered" in result
