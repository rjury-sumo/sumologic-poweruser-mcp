#!/usr/bin/env python3
"""
Sumo Logic MCP Server

This server provides read-only access to Sumo Logic APIs through the Model Context Protocol.
It exposes tools for searching logs, querying metrics, and retrieving account information.

Supports multiple Sumo Logic instances with separate credentials.

Usage:
    uvx sumologic-poweruser-mcp
    # or
    python -m sumologic_poweruser_mcp.sumologic_mcp_server

Environment Variables:
    See .env.example for configuration options
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .config import SumoInstanceConfig, get_config
from .exceptions import (
    APIError,
    AuthenticationError,
    InstanceNotFoundError,
    SumoMCPError,
    ValidationError,
)
from .exceptions import (
    TimeoutError as SumoTimeoutError,
)
from .rate_limiter import get_rate_limiter
from .validation import (
    CollectorValidation,
    MonitorSearchValidation,
    validate_instance_name,
    validate_pagination,
    validate_query_input,
    validate_time_range,
)


def _resolve_field_value(value: Any) -> Any:
    """
    Resolve Pydantic Field values to actual values.

    When tools are called directly from Python (not via MCP), Field() objects
    may be passed instead of actual values. This helper extracts the real value.
    """
    from pydantic.fields import FieldInfo

    if isinstance(value, FieldInfo):
        return value.default if hasattr(value, "default") else None
    return value


# Logging will be configured on first access
logger = logging.getLogger(__name__)
audit_logger = logging.getLogger("audit")

# Initialize the MCP server
mcp = FastMCP("Sumo Logic")

# Config and audit logging initialization
_config_initialized = False


def _ensure_config_initialized():
    """Ensure configuration and logging are initialized."""
    global _config_initialized
    if not _config_initialized:
        config = get_config()
        logging.basicConfig(
            level=getattr(logging, config.server_config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        if config.server_config.enable_audit_log:
            audit_handler = logging.FileHandler("sumo_mcp_audit.log")
            audit_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            audit_logger.addHandler(audit_handler)
            audit_logger.setLevel(logging.INFO)

        _config_initialized = True


class SumoLogicClient:
    """Client for interacting with Sumo Logic APIs.

    API Endpoints:
    - Search Jobs: v1
    - Collectors & Sources: v1
    - Users: v1
    - Folders: v2 with /folders/global path
    - Dashboards: v2
    - Metrics: v1 with /metrics/queries path
    - Content, Roles: v2
    - Monitors: v1 search endpoint
    - Partitions: v1
    """

    def __init__(self, instance_config: SumoInstanceConfig, instance_name: str = "default"):
        """Initialize client with instance configuration."""
        self.instance_name = instance_name
        self.access_id = instance_config.access_id
        self.access_key = instance_config.access_key
        self.endpoint = instance_config.endpoint
        self.session = httpx.AsyncClient(
            auth=(instance_config.access_id, instance_config.access_key),
            headers={"Content-Type": "application/json"},
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP session."""
        await self.session.aclose()

    async def _request(
        self, method: str, path: str, api_version: str = "v1", **kwargs
    ) -> Dict[str, Any]:
        """Make an authenticated request to the Sumo Logic API."""
        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path

        # Build full URL with API version
        api_path = f"/api/{api_version}{path}"
        url = urljoin(self.endpoint, api_path)

        try:
            response = await self.session.request(method, url, **kwargs)
            response.raise_for_status()

            # Log successful request for audit
            _ensure_config_initialized()
            config = get_config()
            if config.server_config.enable_audit_log:
                audit_logger.info(
                    f"instance={self.instance_name} method={method} "
                    f"path={api_path} status={response.status_code}"
                )

            return response.json()

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            # Sanitize error message for client
            if status_code == 401:
                logger.error(f"Authentication failed for instance {self.instance_name}")
                raise AuthenticationError(
                    f"Authentication failed for instance '{self.instance_name}'. "
                    "Please check your credentials.",
                    details=f"status_code={status_code}",
                )
            elif status_code == 403:
                logger.error(f"Authorization failed for {self.instance_name}: {path}")
                raise AuthenticationError(
                    "Access denied. Your credentials may not have permission for this operation.",
                    details=f"path={path}",
                )
            elif status_code == 429:
                logger.warning(f"Rate limited by Sumo Logic API: {self.instance_name}")
                raise APIError(
                    "Sumo Logic API rate limit exceeded. Please try again later.", status_code=429
                )
            else:
                logger.error(
                    f"HTTP error {status_code} for {self.instance_name}: {e.response.text}"
                )
                raise APIError(
                    f"Sumo Logic API request failed with status {status_code}",
                    status_code=status_code,
                    details="Check server logs for details",
                )

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout for {self.instance_name}: {str(e)}")
            raise SumoTimeoutError(
                "Request to Sumo Logic API timed out. The query may be too complex or the service may be slow."
            )

        except Exception as e:
            logger.error(f"Request failed for {self.instance_name}: {str(e)}")
            raise APIError(
                "Unexpected error communicating with Sumo Logic API",
                details="Check server logs for details",
            )

    async def search_logs(
        self,
        query: str,
        from_time: str,
        to_time: str,
        timezone_str: str = "UTC",
        by_receipt_time: bool = False,
        max_attempts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a search job and return results.

        Args:
            query: Sumo Logic query string
            from_time: Start time (ISO8601 or epoch milliseconds)
            to_time: End time (ISO8601 or epoch milliseconds)
            timezone_str: Timezone for the query (default: UTC)
            by_receipt_time: If True, use receipt time instead of message time (default: False)
            max_attempts: Maximum polling attempts (default: based on config timeout)

        Returns:
            Dictionary with job_id, state, counts, and results (messages or records)
        """
        from .search_helpers import detect_query_type, parse_relative_time

        if max_attempts is None:
            _ensure_config_initialized()
            config = get_config()
            max_attempts = config.server_config.max_search_timeout // 5

        # Detect query type
        query_type = detect_query_type(query)
        requires_raw_messages = query_type == "messages"

        # Parse relative time if needed
        from_time_parsed = parse_relative_time(from_time)
        to_time_parsed = parse_relative_time(to_time)

        # Create search job
        search_data = {
            "query": query,
            "from": from_time_parsed,
            "to": to_time_parsed,
            "timeZone": timezone_str,
            "byReceiptTime": by_receipt_time,
        }

        # Only add requiresRawMessages if not default (to be compatible with older API versions)
        if not requires_raw_messages:
            search_data["requiresRawMessages"] = False

        job_response = await self._request(
            "POST", "/search/jobs", api_version="v1", json=search_data
        )
        job_id = job_response["id"]

        # Poll for completion
        for attempt in range(max_attempts):
            status_response = await self._request("GET", f"/search/jobs/{job_id}", api_version="v1")
            state = status_response["state"]

            if state == "DONE GATHERING RESULTS":
                # Get results based on query type
                config = get_config()
                max_limit = config.server_config.max_query_limit
                if query_type == "records":
                    results_response = await self._request(
                        "GET",
                        f"/search/jobs/{job_id}/records",
                        api_version="v1",
                        params={"offset": 0, "limit": max_limit},
                    )
                    results_key = "records"
                else:
                    results_response = await self._request(
                        "GET",
                        f"/search/jobs/{job_id}/messages",
                        api_version="v1",
                        params={"offset": 0, "limit": max_limit},
                    )
                    results_key = "messages"

                return {
                    "job_id": job_id,
                    "state": state,
                    "query_type": query_type,
                    "message_count": status_response.get("messageCount", 0),
                    "record_count": status_response.get("recordCount", 0),
                    "results": results_response.get(results_key, []),
                }
            elif state in ["CANCELLED", "FORCE PAUSED"]:
                raise APIError(f"Search job {job_id} was {state.lower()}")

            await asyncio.sleep(5)  # Wait 5 seconds before checking again

        raise SumoTimeoutError(f"Search job {job_id} timed out after {max_attempts * 5} seconds")

    async def get_search_job_records(
        self, job_id: str, offset: int = 0, limit: int = 10000
    ) -> Dict[str, Any]:
        """Get aggregate records from a completed search job.

        Args:
            job_id: Search job ID
            offset: Starting offset for pagination (default: 0)
            limit: Maximum records to return (default: 10000)

        Returns:
            Dictionary with records array
        """
        params = {"offset": offset, "limit": limit}
        return await self._request(
            "GET", f"/search/jobs/{job_id}/records", api_version="v1", params=params
        )

    async def get_search_job_messages(
        self, job_id: str, offset: int = 0, limit: int = 10000
    ) -> Dict[str, Any]:
        """Get raw log messages from a completed search job.

        Args:
            job_id: Search job ID
            offset: Starting offset for pagination (default: 0)
            limit: Maximum messages to return (default: 10000)

        Returns:
            Dictionary with messages array
        """
        params = {"offset": offset, "limit": limit}
        return await self._request(
            "GET", f"/search/jobs/{job_id}/messages", api_version="v1", params=params
        )

    async def get_search_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a search job.

        Args:
            job_id: Search job ID

        Returns:
            Dictionary with job state, counts, and other metadata
        """
        return await self._request("GET", f"/search/jobs/{job_id}", api_version="v1")

    async def create_search_job(
        self,
        query: str,
        from_time: str,
        to_time: str,
        timezone_str: str = "UTC",
        by_receipt_time: bool = False,
    ) -> Dict[str, Any]:
        """Create a search job without waiting for results.

        Args:
            query: Sumo Logic query string
            from_time: Start time (ISO8601, epoch milliseconds, or relative like "-1h")
            to_time: End time (ISO8601, epoch milliseconds, or relative like "now")
            timezone_str: Timezone for the query (default: UTC)
            by_receipt_time: If True, use receipt time instead of message time (default: False)

        Returns:
            Dictionary with job_id and link
        """
        from .search_helpers import detect_query_type, parse_relative_time

        # Detect query type
        query_type = detect_query_type(query)
        requires_raw_messages = query_type == "messages"

        # Parse relative time if needed
        from_time_parsed = parse_relative_time(from_time)
        to_time_parsed = parse_relative_time(to_time)

        # Create search job
        search_data = {
            "query": query,
            "from": from_time_parsed,
            "to": to_time_parsed,
            "timeZone": timezone_str,
            "byReceiptTime": by_receipt_time,
        }

        # Only add requiresRawMessages if not default
        if not requires_raw_messages:
            search_data["requiresRawMessages"] = False

        return await self._request("POST", "/search/jobs", api_version="v1", json=search_data)

    async def delete_search_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a search job.

        Args:
            job_id: Search job ID to delete

        Returns:
            Empty dictionary on success
        """
        return await self._request("DELETE", f"/search/jobs/{job_id}", api_version="v1")

    async def get_collectors(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get list of collectors."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/collectors", api_version="v1", params=params)

    async def get_sources(self, collector_id: int) -> Dict[str, Any]:
        """Get sources for a specific collector."""
        return await self._request("GET", f"/collectors/{collector_id}/sources", api_version="v1")

    async def get_users(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get list of users."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/users", api_version="v1", params=params)

    async def get_folders(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get list of folders."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/folders/global", api_version="v2", params=params)

    async def get_dashboards(
        self,
        limit: int = 100,
        offset: int = 0,
        mode: str = "allViewableByUser",
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get list of dashboards.

        Args:
            limit: Maximum number of results (1-100)
            offset: Pagination offset (deprecated - use token instead)
            mode: Filter mode - 'allViewableByUser' or 'createdByUser'
            token: Pagination token from previous response's 'next' field

        Returns:
            Response with 'dashboards' array and optional 'next' token
        """
        params = {"limit": limit, "mode": mode}

        # Use token-based pagination if provided (preferred)
        if token:
            params["token"] = token
        else:
            # Fall back to offset-based pagination for backward compatibility
            params["offset"] = offset

        return await self._request("GET", "/dashboards", api_version="v2", params=params)

    async def query_metrics(self, query: str, from_time: str, to_time: str) -> Dict[str, Any]:
        """Query metrics."""
        metrics_data = {
            "query": [{"query": query, "rowId": "A"}],
            "startTime": int(
                datetime.fromisoformat(from_time.replace("Z", "+00:00")).timestamp() * 1000
            ),
            "endTime": int(
                datetime.fromisoformat(to_time.replace("Z", "+00:00")).timestamp() * 1000
            ),
            "requestId": f"mcp-{datetime.now().isoformat()}",
            "maxDataPoints": 800,
        }
        return await self._request("POST", "/metrics/queries", api_version="v1", json=metrics_data)

    async def get_content_v2(
        self, content_type: str = "Dashboard", limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Get content using the v2 content API."""
        params = {"type": content_type, "limit": limit, "offset": offset}
        return await self._request("GET", "/content", api_version="v2", params=params)

    async def get_roles_v2(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get roles using the v2 roles API."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/roles", api_version="v2", params=params)

    async def search_monitors(
        self, query: str, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Search for monitors."""
        params = {"query": query, "limit": limit, "token": offset}
        return await self._request("GET", "/monitors/search", api_version="v1", params=params)

    async def get_partitions(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get partitions."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/partitions", api_version="v1", params=params)

    async def list_scheduled_views(
        self, limit: int = 100, token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get list of scheduled views with pagination."""
        params = {"limit": limit}
        if token:
            params["token"] = token
        return await self._request("GET", "/scheduledViews", api_version="v1", params=params)

    # Field Management API methods

    async def list_custom_fields(self) -> Dict[str, Any]:
        """Get list of custom fields defined in the organization."""
        return await self._request("GET", "/fields", api_version="v1")

    async def list_field_extraction_rules(
        self, limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Get list of field extraction rules."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/extractionRules", api_version="v1", params=params)

    async def get_field_extraction_rule(self, rule_id: str) -> Dict[str, Any]:
        """Get a specific field extraction rule by ID."""
        return await self._request("GET", f"/extractionRules/{rule_id}", api_version="v1")

    # Content Library API methods

    async def get_personal_folder(self, include_children: bool = True) -> Dict[str, Any]:
        """Get user's personal folder."""
        params = {} if include_children else {"includeChildren": "false"}
        return await self._request(
            "GET", "/content/folders/personal", api_version="v2", params=params
        )

    async def get_folder_by_id(
        self, folder_id: str, include_children: bool = True
    ) -> Dict[str, Any]:
        """Get folder by ID."""
        params = {} if include_children else {"includeChildren": "false"}
        return await self._request(
            "GET", f"/content/folders/{folder_id}", api_version="v2", params=params
        )

    async def get_content_by_path(self, content_path: str) -> Dict[str, Any]:
        """Get content item by path."""
        params = {"path": content_path}
        return await self._request("GET", "/content/path", api_version="v2", params=params)

    async def get_content_path(self, content_id: str) -> Dict[str, Any]:
        """Get content path by ID."""
        return await self._request("GET", f"/content/{content_id}/path", api_version="v2")

    async def begin_content_export(
        self, content_id: str, is_admin_mode: bool = False
    ) -> Dict[str, Any]:
        """Begin async content export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request(
            "POST", f"/content/{content_id}/export", api_version="v2", params=params
        )

    async def get_content_export_status(self, content_id: str, job_id: str) -> Dict[str, Any]:
        """Get content export job status."""
        return await self._request(
            "GET", f"/content/{content_id}/export/{job_id}/status", api_version="v2"
        )

    async def get_content_export_result(self, content_id: str, job_id: str) -> Dict[str, Any]:
        """Get content export job result."""
        return await self._request(
            "GET", f"/content/{content_id}/export/{job_id}/result", api_version="v2"
        )

    async def begin_global_folder_export(self, is_admin_mode: bool = False) -> Dict[str, Any]:
        """Begin async Global folder export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request(
            "GET", "/content/folders/global", api_version="v2", params=params
        )

    async def get_global_folder_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get Global folder export job status."""
        return await self._request(
            "GET", f"/content/folders/global/{job_id}/status", api_version="v2"
        )

    async def get_global_folder_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get Global folder export job result."""
        return await self._request(
            "GET", f"/content/folders/global/{job_id}/result", api_version="v2"
        )

    async def begin_admin_recommended_export(self, is_admin_mode: bool = False) -> Dict[str, Any]:
        """Begin async Admin Recommended folder export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request(
            "GET", "/content/folders/adminRecommended", api_version="v2", params=params
        )

    async def get_admin_recommended_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get Admin Recommended folder export job status."""
        return await self._request(
            "GET", f"/content/folders/adminRecommended/{job_id}/status", api_version="v2"
        )

    async def get_admin_recommended_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get Admin Recommended folder export job result."""
        return await self._request(
            "GET", f"/content/folders/adminRecommended/{job_id}/result", api_version="v2"
        )

    async def begin_installed_apps_export(self, is_admin_mode: bool = False) -> Dict[str, Any]:
        """Begin async Installed Apps folder export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request(
            "GET", "/content/folders/installedApps", api_version="v2", params=params
        )

    async def get_installed_apps_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get Installed Apps folder export job status."""
        return await self._request(
            "GET", f"/content/folders/installedApps/{job_id}/status", api_version="v2"
        )

    async def get_installed_apps_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get Installed Apps folder export job result."""
        return await self._request(
            "GET", f"/content/folders/installedApps/{job_id}/result", api_version="v2"
        )

    async def list_apps(self) -> Dict[str, Any]:
        """List all installed apps (requires admin permissions in most orgs)."""
        return await self._request("GET", "/apps", api_version="v2")

    # Account Management API methods

    async def get_account_status(self) -> Dict[str, Any]:
        """Get account status including subscription, plan type, and usage."""
        return await self._request("GET", "/account/status", api_version="v1")

    async def get_usage_forecast(self, number_of_days: int) -> Dict[str, Any]:
        """Get usage forecast for specified number of days."""
        params = {"numberOfDays": number_of_days}
        return await self._request("GET", "/account/usageForecast", api_version="v1", params=params)

    async def get_usage_forecast_default(self) -> Dict[str, Any]:
        """Get usage forecast for current contract term (no numberOfDays parameter)."""
        return await self._request("GET", "/account/usageForecast", api_version="v1")

    async def start_usage_export(
        self,
        start_date: str,
        end_date: str,
        group_by: str = "day",
        report_type: str = "standard",
        include_deployment_charge: bool = False,
    ) -> Dict[str, Any]:
        """Start async usage report export job."""
        data = {
            "groupBy": group_by,
            "reportType": report_type,
            "includeDeploymentCharge": include_deployment_charge,
            "startDate": start_date,
            "endDate": end_date,
        }
        return await self._request("POST", "/account/usage/report", api_version="v1", json=data)

    async def get_usage_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get usage export job status."""
        return await self._request(
            "GET", f"/account/usage/report/{job_id}/status", api_version="v1"
        )

    async def get_usage_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get usage export result (download URL when job is complete)."""
        status = await self.get_usage_export_status(job_id)
        if status.get("status") == "Success":
            return status
        else:
            return {"status": status.get("status", "Unknown"), "job_id": job_id}

    async def get_estimated_log_search_usage(
        self, query: str, from_time: int, to_time: int, time_zone: str = "UTC", by_view: bool = True
    ) -> Dict[str, Any]:
        """
        Get estimated data volume that would be scanned for a log search query.

        Args:
            query: Log search query (scope only, e.g., "_sourceCategory=prod/app")
            from_time: Start time in epoch milliseconds
            to_time: End time in epoch milliseconds
            time_zone: Timezone for the search (default: UTC)
            by_view: If True, returns breakdown by partition/view with tier info (default: True)

        Returns:
            Estimated usage with partition/view breakdown if by_view=True
        """
        data = {
            "queryString": query,
            "timeRange": {
                "type": "BeginBoundedTimeRange",
                "from": {"type": "EpochTimeRangeBoundary", "epochMillis": from_time},
                "to": {"type": "EpochTimeRangeBoundary", "epochMillis": to_time},
            },
            "timezone": time_zone,
        }

        endpoint = "/logSearches/estimatedUsageByView" if by_view else "/logSearches/estimatedUsage"
        return await self._request("POST", endpoint, api_version="v1", json=data)


# Client pool - maps instance name to client
clients: Dict[str, SumoLogicClient] = {}


async def get_sumo_client(instance: str = "default") -> SumoLogicClient:
    """Get or create a Sumo Logic client for the specified instance."""
    _ensure_config_initialized()
    config = get_config()
    instance = validate_instance_name(instance)

    if instance not in clients:
        try:
            instance_config = config.get_instance(instance)
            clients[instance] = SumoLogicClient(instance_config, instance)
            logger.info(f"Created client for instance: {instance}")
        except ValueError as e:
            raise InstanceNotFoundError(
                f"Instance '{instance}' not configured. Available: {', '.join(config.list_instances())}",
                details=str(e),
            )

    return clients[instance]


# Helper function to handle tool errors
def handle_tool_error(e: Exception, tool_name: str) -> str:
    """Handle and format tool errors."""
    if isinstance(e, SumoMCPError):
        error_dict = e.to_dict()
        logger.warning(f"Tool {tool_name} error: {error_dict}")
        return json.dumps(error_dict, indent=2)
    else:
        logger.error(f"Unexpected error in {tool_name}: {str(e)}", exc_info=True)
        return json.dumps(
            {
                "error": "An unexpected error occurred",
                "details": "Check server logs for more information",
            },
            indent=2,
        )


# MCP Tools


@mcp.tool()
async def search_sumo_logs(
    query: str = Field(description="Sumo Logic search query"),
    hours_back: int = Field(
        default=1,
        description="Number of hours to search back from now (ignored if from_time/to_time provided)",
    ),
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    time_zone: str = "UTC",
    by_receipt_time: bool = False,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Search Sumo Logic logs using a query. Automatically detects query type and returns appropriate results.

    Query Types:
    - Raw log queries: Return individual log messages
      Example: _sourceCategory=apache/access
    - Aggregate queries: Return aggregated records (count, sum, avg, etc.)
      Example: error | count by _sourceHost

    Time Formats:
    - Relative: "-1h", "-30m", "-24h", "now"
    - ISO8601: "2024-01-15T10:00:00Z"
    - Epoch milliseconds: "1705315200000"

    Use by_receipt_time=true when:
    - Logs are delayed in ingestion
    - Querying very recent data
    - Need to match Sumo UI behavior for recent searches
    """
    try:
        # Rate limiting
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("search_sumo_logs")

        # Validate inputs
        query = validate_query_input(query)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)

        # Determine time range
        if from_time is not None and to_time is not None:
            from_str = from_time
            to_str = to_time
        else:
            # Use hours_back
            hours_back = validate_time_range(hours_back)
            to_time_dt = datetime.now(timezone.utc)
            from_time_dt = to_time_dt - timedelta(hours=hours_back)
            from_str = from_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            to_str = to_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.search_logs(query, from_str, to_str, time_zone, by_receipt_time)

        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "search_sumo_logs")


@mcp.tool()
async def create_sumo_search_job(
    query: str = Field(description="Sumo Logic search query"),
    from_time: str = Field(description="Start time: ISO8601, epoch ms, or relative like '-1h'"),
    to_time: str = Field(description="End time: ISO8601, epoch ms, or relative like 'now'"),
    time_zone: str = "UTC",
    by_receipt_time: bool = False,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Create a search job and return immediately with job ID. Use get_sumo_search_job_status to check progress
    and get_sumo_search_job_results to retrieve results once complete.

    This is useful for:
    - Long-running searches
    - Asynchronous query execution
    - Queries that might take more than a few seconds
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("create_sumo_search_job")

        query = validate_query_input(query)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        job_info = await client.create_search_job(
            query, from_time, to_time, time_zone, by_receipt_time
        )

        return json.dumps(job_info, indent=2)

    except Exception as e:
        return handle_tool_error(e, "create_sumo_search_job")


@mcp.tool()
async def get_sumo_search_job_status(
    job_id: str = Field(description="Search job ID"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get the status of a search job.

    Returns information including:
    - state: Job state (e.g., "DONE GATHERING RESULTS", "GATHERING RESULTS")
    - messageCount: Number of raw messages found
    - recordCount: Number of aggregate records found
    - histogramBuckets: Time distribution of results
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_search_job_status")

        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        status = await client.get_search_job_status(job_id)

        return json.dumps(status, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_sumo_search_job_status")


@mcp.tool()
async def get_sumo_search_job_results(
    job_id: str = Field(description="Search job ID"),
    result_type: str = "auto",
    offset: int = 0,
    limit: int = 1000,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get results from a completed search job. Use 'auto' to automatically detect result type,
    or specify 'messages' for raw logs or 'records' for aggregates.

    Pagination:
    - Use offset and limit to retrieve results in chunks
    - Check messageCount or recordCount in status to know total available
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_search_job_results")

        instance = validate_instance_name(instance)
        limit, offset = validate_pagination(limit, offset)

        client = await get_sumo_client(instance)

        # Determine result type
        if result_type == "auto":
            # Check job status to determine type
            status = await client.get_search_job_status(job_id)
            record_count = status.get("recordCount", 0)

            # If recordCount > 0, it's an aggregate query
            if record_count > 0:
                result_type = "records"
            else:
                result_type = "messages"

        # Get appropriate results
        if result_type == "records":
            results = await client.get_search_job_records(job_id, offset, limit)
        else:
            results = await client.get_search_job_messages(job_id, offset, limit)

        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_sumo_search_job_results")


@mcp.tool()
async def get_sumo_collectors(
    limit: int = Field(default=100, description="Maximum number of results"),
    offset: int = Field(
        default=0, description="Pagination offset for retrieving results beyond the limit"
    ),
    filter_name: Optional[str] = Field(
        default=None, description="Filter collectors by name (substring match, case-insensitive)"
    ),
    filter_alive: Optional[bool] = Field(
        default=None, description="Filter by alive status (true=active, false=inactive)"
    ),
    search_term: Optional[str] = Field(
        default=None, description="Search across name, description, hostName fields"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get list of Sumo Logic collectors with pagination and optional client-side filtering.

    For environments with many collectors, use limit and offset to paginate through results.
    Client-side filtering helps when API returns large result sets (>1MB).
    Use filter_name, filter_alive, or search_term to reduce results.

    Pagination Examples:
        - First 100: limit=100, offset=0
        - Next 100: limit=100, offset=100
        - Collectors 200-299: limit=100, offset=200

    Filtering Examples:
        - filter_name="prod" - Find collectors with "prod" in name
        - filter_alive=True - Only show active collectors
        - search_term="aws" - Search across name, description, hostname

    Returns:
        JSON with collectors array and optional _metadata if filtered
    """
    try:
        from .response_filter import filter_response

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_collectors")

        limit, offset = validate_pagination(limit, offset)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        collectors = await client.get_collectors(limit=limit, offset=offset)

        # Resolve Field values when called directly from Python
        filter_name = _resolve_field_value(filter_name)
        filter_alive = _resolve_field_value(filter_alive)
        search_term = _resolve_field_value(search_term)

        # Apply client-side filtering if requested
        has_filter_name = filter_name is not None and filter_name != ""
        has_filter_alive = filter_alive is not None
        has_search_term = search_term is not None and search_term != ""

        if has_filter_name or has_filter_alive or has_search_term:
            if has_filter_name:
                collectors = filter_response(
                    collectors, field="name", value=filter_name, case_sensitive=False
                )
            elif has_filter_alive:
                collectors = filter_response(
                    collectors, custom_filter=lambda c: c.get("alive", False) == filter_alive
                )
            elif has_search_term:
                collectors = filter_response(
                    collectors,
                    search_term=search_term,
                    search_fields=["name", "description", "hostName"],
                    case_sensitive=False,
                )

        return json.dumps(collectors, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_collectors")


@mcp.tool()
async def get_sumo_sources(
    collector_id: int = Field(description="Collector ID to get sources for"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get sources for a specific Sumo Logic collector.

    Returns configuration details for all sources attached to a collector,
    including source type, category, host name, and collection settings.

    Args:
        collector_id: Numeric collector ID (get from get_sumo_collectors)

    Returns:
        JSON array of source objects containing:
        - id: Source ID
        - name: Source name
        - category: Source category (used in queries)
        - sourceType: Type (e.g., LocalFile, Syslog, HTTP)
        - alive: Collection status (true/false)
        - description: Source description

    Use Cases:
        - **Troubleshoot collection**: Check source configuration and status
        - **Source inventory**: List all sources for a collector
        - **Category discovery**: Find source categories for query building
        - **Monitoring**: Verify sources are alive and collecting
        - **Configuration audit**: Review source settings

    Example Output:
        [{
          "id": 123456,
          "name": "apache_access_logs",
          "category": "prod/apache/access",
          "sourceType": "LocalFile",
          "alive": true
        }]

    Workflow:
        1. Use get_sumo_collectors to list collectors
        2. Use this tool to get sources for a specific collector
        3. Check 'alive' status to verify collection is working
        4. Use 'category' in queries: _sourceCategory=prod/apache/access

    API Reference: https://api.sumologic.com/docs/#operation/getSources
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_sources")

        validation = CollectorValidation(collector_id=collector_id)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        sources = await client.get_sources(validation.collector_id)
        return json.dumps(sources, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_sources")


@mcp.tool()
async def get_sumo_users(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get list of Sumo Logic users in the organization.

    Returns user information including email, first/last name, roles, and status.
    Useful for user management, audit reporting, and access reviews.

    Returns:
        JSON array of user objects containing:
        - id: Unique user identifier
        - firstName/lastName: User's name
        - email: User's email address
        - roleIds: Array of assigned role IDs
        - isActive: Account status (true/false)
        - createdAt/modifiedAt: Timestamps

    Use Cases:
        - **User audit**: List all users for security reviews
        - **Access management**: Identify users and their roles
        - **License management**: Count active vs inactive users
        - **Onboarding/offboarding**: Verify user accounts
        - **Compliance reporting**: Generate user access reports

    Example Output:
        [{
          "id": "00000000001A2B3C",
          "firstName": "John",
          "lastName": "Doe",
          "email": "john.doe@example.com",
          "roleIds": ["00000000001A2B3D"],
          "isActive": true
        }]

    Related Tools:
        - get_sumo_roles_v2: Get role definitions
        - Use together to map users to their permissions

    API Reference: https://api.sumologic.com/docs/#operation/listUsers
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_users")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        users = await client.get_users(limit=limit)
        return json.dumps(users, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_users")


# Content Library Tools (replace old get_sumo_folders)


@mcp.tool()
async def get_personal_folder(
    include_children: bool = True,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get user's personal folder with optional children.

    This is the fastest way to access personal library content as it uses
    a synchronous folder API. Returns folder metadata and optionally its children.
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_personal_folder")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        result = await client.get_personal_folder(include_children)
        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_personal_folder")


@mcp.tool()
async def get_folder_by_id(
    folder_id: str = Field(description="Hex folder ID (16 characters)"),
    include_children: bool = True,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get a specific folder by ID with optional children.

    Use this to navigate folder hierarchy. Returns folder metadata and
    optionally its immediate children (folders and content items).
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_folder_by_id")

        instance = validate_instance_name(instance)
        folder_id = validate_query_input(folder_id)  # Basic validation
        client = await get_sumo_client(instance)

        result = await client.get_folder_by_id(folder_id, include_children)
        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_folder_by_id")


@mcp.tool()
async def get_content_by_path(
    content_path: str = Field(
        description="Full library path (e.g., /Library/Users/user@email.com/MyFolder)"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get content item by its library path.

    Path format: /Library/Users/<email>/path/to/content
    or /Library/Global/path/to/content
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_content_by_path")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        result = await client.get_content_by_path(content_path)
        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_content_by_path")


@mcp.tool()
async def get_content_path_by_id(
    content_id: str = Field(description="Hex content ID"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get the full library path for a content ID.

    Returns the absolute path in the library hierarchy.
    Useful for displaying content location or building breadcrumbs.
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_content_path_by_id")

        instance = validate_instance_name(instance)
        content_id = validate_query_input(content_id)
        client = await get_sumo_client(instance)

        result = await client.get_content_path(content_id)
        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_content_path_by_id")


@mcp.tool()
async def export_content(
    content_id: str = Field(description="Hex content ID to export"),
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Export full content structure (dashboards, searches, etc.) with async job handling.

    This handles the complete async export workflow:
    1. Start export job
    2. Poll for completion (default 5 minutes max)
    3. Return full content structure

    Use this for dashboards, searches, and other content to get their
    complete definition including nested structures, search queries, dashboard panels, etc.

    Set is_admin_mode=true to export with admin permissions (shows more content).
    """
    try:
        from .async_export_helper import poll_export_job

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_content")

        instance = validate_instance_name(instance)
        content_id = validate_query_input(content_id)
        client = await get_sumo_client(instance)

        # Start export job
        job_response = await client.begin_content_export(content_id, is_admin_mode)
        job_id = job_response["id"]

        # Poll for completion
        result = await poll_export_job(
            job_id=job_id,
            content_id=content_id,
            get_status_func=lambda cid, jid: client.get_content_export_status(cid, jid),
            get_result_func=lambda cid, jid: client.get_content_export_result(cid, jid),
            max_wait_seconds=max_wait_seconds,
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_content")


@mcp.tool()
async def export_global_folder(
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    max_items: Optional[int] = Field(
        default=None, description="Maximum number of items to return (truncates large folders)"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Export Global folder contents (async) with optional truncation for large folders.

    IMPORTANT: Global folder uses 'data' array instead of 'children' for its contents.
    This is different from other folders and Admin Recommended.

    Set is_admin_mode=true to see more content (requires admin permissions).
    Use max_items to truncate large folder exports (helps with >1MB responses).

    Args:
        is_admin_mode: Export with admin permissions
        max_wait_seconds: Maximum time to wait for export job
        max_items: Limit number of items returned (e.g., 50 for large folders)
        instance: Sumo Logic instance name
    """
    try:
        from .async_export_helper import poll_folder_export_job
        from .response_filter import truncate_response

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_global_folder")

        instance = validate_instance_name(instance)
        max_items = _resolve_field_value(max_items)
        client = await get_sumo_client(instance)

        # Start export job
        job_response = await client.begin_global_folder_export(is_admin_mode)
        job_id = job_response["id"]

        # Poll for completion
        result = await poll_folder_export_job(
            job_id=job_id,
            folder_type="Global folder",
            get_status_func=lambda jid: client.get_global_folder_export_status(jid),
            get_result_func=lambda jid: client.get_global_folder_export_result(jid),
            max_wait_seconds=max_wait_seconds,
        )

        # Truncate if requested
        if max_items is not None and max_items > 0:
            result, was_truncated = truncate_response(result, max_items=max_items)
            if was_truncated:
                logger.info(f"Truncated Global folder export to {max_items} items")

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_global_folder")


@mcp.tool()
async def export_admin_recommended_folder(
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    max_items: Optional[int] = Field(
        default=None, description="Maximum number of items to return (truncates large folders)"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Export Admin Recommended folder (async) with optional truncation for large folders.

    Returns admin-curated content. Unlike Global folder, this uses 'children' array.
    Set is_admin_mode=true to see more content (requires admin permissions).
    Use max_items to truncate large folder exports (helps with >1MB responses).

    Args:
        is_admin_mode: Export with admin permissions
        max_wait_seconds: Maximum time to wait for export job
        max_items: Limit number of items returned (e.g., 50 for large folders)
        instance: Sumo Logic instance name
    """
    try:
        from .async_export_helper import poll_folder_export_job
        from .response_filter import truncate_response

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_admin_recommended_folder")

        instance = validate_instance_name(instance)
        max_items = _resolve_field_value(max_items)
        client = await get_sumo_client(instance)

        # Start export job
        job_response = await client.begin_admin_recommended_export(is_admin_mode)
        job_id = job_response["id"]

        # Poll for completion
        result = await poll_folder_export_job(
            job_id=job_id,
            folder_type="Admin Recommended folder",
            get_status_func=lambda jid: client.get_admin_recommended_export_status(jid),
            get_result_func=lambda jid: client.get_admin_recommended_export_result(jid),
            max_wait_seconds=max_wait_seconds,
        )

        # Truncate if requested
        if max_items is not None and max_items > 0:
            result, was_truncated = truncate_response(result, max_items=max_items)
            if was_truncated:
                logger.info(f"Truncated Admin Recommended folder export to {max_items} items")

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_admin_recommended_folder")


@mcp.tool()
async def export_installed_apps(
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Export Installed Apps folder to discover pre-built apps available in your Sumo Logic instance.

    This tool lists all installed Sumo Logic apps (e.g., AWS CloudTrail, Apache, Kubernetes, etc.)
    that admins have already set up. Each app folder contains pre-built dashboards, searches,
    and monitors for specific use cases.

    Args:
        is_admin_mode: View as admin to see all apps (default: False, requires admin permissions)
        max_wait_seconds: Maximum seconds to wait for async job (default: 300)
        instance: Sumo Logic instance name (default: 'default')

    Returns:
        JSON with installed apps structure containing:
        - App folders organized by category/technology
        - Each app contains dashboards, searches, monitors
        - Content IDs for accessing specific app components

    Use Cases:
        - **Discover available apps**: See what pre-built content is already installed
        - **Find relevant dashboards**: Locate dashboards for AWS, Kubernetes, Apache, etc.
        - **Log discovery**: After finding logs, discover if there's already an app for them
        - **Use case mapping**: Connect log sources to pre-built monitoring solutions

    App Catalog References:
        - Browse all apps: https://www.sumologic.com/app-catalog
        - Search by keyword: Use app catalog to find apps matching your technology
        - Integration docs: https://www.sumologic.com/help/docs/integrations/

    Example Flow:
        1. Use LogDiscoveryPattern to find logs (e.g., CloudTrail logs)
        2. Use export_installed_apps to see if AWS CloudTrail app is installed
        3. If installed, navigate directly to app dashboards and searches
        4. If not installed, suggest admin install from app catalog

    Notes:
        - Similar async pattern to export_global_folder and export_admin_recommended_folder
        - InstalledApps is a top-level library location like Global and Admin Recommended
        - Each app folder typically contains: Overview dashboard, detailed dashboards, saved searches
        - Apps are pre-configured with optimal queries and visualizations for their technology

    API Reference:
        - https://api.sumologic.com/docs/#operation/getInstalledAppsFolderAsync
    """
    try:
        from .async_export_helper import poll_folder_export_job

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_installed_apps")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Start export job
        job_response = await client.begin_installed_apps_export(is_admin_mode)
        job_id = job_response["id"]

        # Poll for completion
        result = await poll_folder_export_job(
            job_id=job_id,
            folder_type="Installed Apps folder",
            get_status_func=lambda jid: client.get_installed_apps_export_status(jid),
            get_result_func=lambda jid: client.get_installed_apps_export_result(jid),
            max_wait_seconds=max_wait_seconds,
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_installed_apps")


@mcp.tool()
async def list_installed_apps(
    filter_name: Optional[str] = Field(
        default=None, description="Filter apps by name (substring match, case-insensitive)"
    ),
    search_term: Optional[str] = Field(default=None, description="Search app names"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    List all installed Sumo Logic apps with optional filtering (lightweight alternative to export_installed_apps).

    This uses the listAppsV2 endpoint which returns a simplified list of installed apps
    without the full folder structure. Faster than export_installed_apps but may require
    admin permissions in some organizations.

    Client-side filtering helps when many apps are installed.

    Args:
        filter_name: Filter apps by name (e.g., "AWS", "Kubernetes")
        search_term: Search app names
        instance: Sumo Logic instance name (default: 'default')

    Returns:
        JSON array of installed apps with:
        - App UUID
        - App name (e.g., "AWS CloudTrail", "Apache", "Kubernetes")
        - App manifest version
        - Installation info
        - _metadata: Filtering statistics (if filters applied)

    Filtering Examples:
        - filter_name="AWS" - Find all AWS-related apps
        - search_term="kubernetes" - Search for Kubernetes apps

    Use Cases:
        - **Quick discovery**: Faster than exporting full folder structure
        - **App availability check**: See if specific app is installed
        - **Log discovery integration**: Check for relevant apps after finding logs

    Permission Note:
        This endpoint may require admin permissions in some organizations.
        If it fails with permission error, use export_installed_apps instead
        which works with regular user permissions.

    App Discovery Flow:
        1. Phase 1: Use LogDiscoveryPattern to find logs (e.g., 'cloudtrail')
        2. Phase 2: Use list_installed_apps to see if AWS CloudTrail app exists
        3. If found: Use export_installed_apps to get full app structure
        4. If not found: Suggest installation from https://www.sumologic.com/app-catalog

    App Catalog:
        - Browse apps: https://www.sumologic.com/app-catalog
        - Search by keyword: Find apps matching your logs/technology
        - Integration guides: https://www.sumologic.com/help/docs/integrations/

    API Reference:
        - https://api.sumologic.com/docs/#operation/listAppsV2
    """
    try:
        from .response_filter import filter_response

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("list_installed_apps")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # List apps
        result = await client.list_apps()

        # Resolve Field values when called directly from Python
        filter_name = _resolve_field_value(filter_name)
        search_term = _resolve_field_value(search_term)

        # Apply client-side filtering if requested
        has_filter_name = filter_name is not None and filter_name != ""
        has_search_term = search_term is not None and search_term != ""

        if has_filter_name or has_search_term:
            if has_filter_name:
                result = filter_response(
                    result, field="appName", value=filter_name, case_sensitive=False
                )
            elif has_search_term:
                result = filter_response(
                    result, search_term=search_term, search_fields=["appName"], case_sensitive=False
                )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "list_installed_apps")


@mcp.tool()
async def get_sumo_dashboards(
    limit: int = Field(default=100, description="Maximum number of results (1-100)"),
    mode: str = Field(
        default="allViewableByUser",
        description="Filter mode: 'allViewableByUser' or 'createdByUser'",
    ),
    token: Optional[str] = Field(
        default=None, description="Pagination token from previous response's 'next' field"
    ),
    filter_name: Optional[str] = Field(
        default=None, description="Filter dashboards by title (substring match, case-insensitive)"
    ),
    filter_description: Optional[str] = Field(
        default=None, description="Filter dashboards by description (substring match)"
    ),
    search_term: Optional[str] = Field(
        default=None, description="Search across title and description fields"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get list of Sumo Logic dashboards with pagination and filtering.

    Returns dashboard metadata including ID, name, description, and folder location.
    Use this to discover available dashboards before viewing or exporting them.

    Pagination:
        - Use 'token' for cursor-based pagination (recommended)
        - Check response's 'next' field for pagination token
        - Pass token to get next page of results
        - When 'next' is absent, you've reached the end

    Mode Parameter:
        - 'allViewableByUser' (default): All dashboards user can view
        - 'createdByUser': Only dashboards created by the current user

    Client-side filtering helps when API returns large result sets (>1MB).
    Use filter_name, filter_description, or search_term to reduce results.

    Returns:
        JSON array of dashboard objects containing:
        - id: Unique dashboard identifier (for get_content_web_url)
        - title: Dashboard name
        - description: Dashboard description
        - folderId: Parent folder ID
        - createdAt/modifiedAt: Timestamps
        - _metadata: Filtering statistics (if filters applied)

    Use Cases:
        - **Dashboard discovery**: Find dashboards by name or description
        - **URL generation**: Get dashboard IDs for get_content_web_url tool
        - **Content inventory**: List all dashboards in organization
        - **Dashboard search**: Find dashboards matching criteria before opening
        - **Integration**: Identify dashboards to link in external tools

    Example Output:
        [{
          "id": "00000000001A2B3C",
          "title": "AWS CloudTrail Overview",
          "description": "AWS CloudTrail monitoring dashboard",
          "folderId": "00000000001A2B3D"
        }]

    Filtering Examples:
        - filter_name="APITest" - Find dashboards with "APITest" in title
        - search_term="security" - Find "security" in title or description
        - Both filters can be combined for more specific results

    Next Steps:
        - Use get_content_web_url to generate shareable dashboard links
        - Use export_content to get full dashboard definition
        - Use get_content_path_by_id to find dashboard location

    API Reference: https://api.sumologic.com/docs/#operation/listDashboards
    """
    try:
        from .response_filter import filter_response

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_dashboards")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        # Resolve Field values when called directly from Python
        mode = _resolve_field_value(mode)
        token = _resolve_field_value(token)
        filter_name = _resolve_field_value(filter_name)
        filter_description = _resolve_field_value(filter_description)
        search_term = _resolve_field_value(search_term)

        # Validate mode parameter
        if mode not in ["allViewableByUser", "createdByUser"]:
            raise ValidationError(
                f"Invalid mode '{mode}'. Must be 'allViewableByUser' or 'createdByUser'"
            )

        client = await get_sumo_client(instance)
        dashboards = await client.get_dashboards(limit=limit, mode=mode, token=token)

        # Check for None explicitly to handle both MCP calls and direct Python calls
        has_filter_name = filter_name is not None and filter_name != ""
        has_filter_desc = filter_description is not None and filter_description != ""
        has_search_term = search_term is not None and search_term != ""

        if has_filter_name or has_filter_desc or has_search_term:
            if has_filter_name:
                dashboards = filter_response(
                    dashboards, field="title", value=filter_name, case_sensitive=False
                )
            elif has_filter_desc:
                dashboards = filter_response(
                    dashboards, field="description", value=filter_description, case_sensitive=False
                )
            elif has_search_term:
                dashboards = filter_response(
                    dashboards,
                    search_term=search_term,
                    search_fields=["title", "description"],
                    case_sensitive=False,
                )

        return json.dumps(dashboards, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_dashboards")


@mcp.tool()
async def query_sumo_metrics(
    query: str = Field(description="Metrics query (e.g., metric=CPU_User | avg by host)"),
    hours_back: int = Field(default=1, description="Number of hours to query back from now"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Query Sumo Logic metrics.

    Example queries:
    - metric=CPU_User | avg by host
    - metric=Memory_Used | max
    - metric=Disk_Used_Percent | where host="web-server-1"
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("query_sumo_metrics")

        query = validate_query_input(query)
        hours_back = validate_time_range(hours_back)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)

        # Calculate time range
        to_time = datetime.now(timezone.utc)
        from_time = to_time - timedelta(hours=hours_back)

        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.query_metrics(query, from_str, to_str)
        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "query_sumo_metrics")


# get_sumo_content_v2 removed - replaced by get_personal_folder, get_folder_by_id, and export_* tools


@mcp.tool()
async def get_sumo_roles_v2(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """Get list of roles using the v2 Roles API."""
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_roles_v2")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        roles = await client.get_roles_v2(limit=limit)
        return json.dumps(roles, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_roles_v2")


@mcp.tool()
async def search_sumo_monitors(
    query: str = Field(description="Search query for monitors"),
    limit: int = Field(default=100, description="Maximum number of results to return"),
    offset: int = Field(default=0, description="Pagination offset"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Search for monitors and monitor folders using flexible query syntax.

    Monitors are alerting rules that trigger notifications when log or metric conditions are met.
    Use this tool to discover existing monitors, check their status, and find alerting configs.

    Query Syntax:
        - Simple text: 'Test' - Matches monitors containing 'Test' in name/description
        - Field search: 'name:*error*' - Wildcard search in name field
        - Status filter: 'monitorStatus:Normal' - Find monitors by status
        - Creator filter: 'createdBy:000000000000968B' - Find monitors by creator

    Returns:
        JSON array of monitor objects containing:
        - id: Monitor ID
        - name: Monitor name
        - monitorType: Type (Logs, Metrics, SLO)
        - status: Current status (Normal, Critical, Warning, etc.)
        - isDisabled: Whether monitor is disabled
        - triggers: Alert conditions

    Use Cases:
        - **Alert inventory**: List all monitors in organization
        - **Troubleshoot alerts**: Find monitors that may be firing
        - **Monitor discovery**: Search for monitors by name or keyword
        - **Status check**: Find all Critical or Warning monitors
        - **Audit review**: Find monitors created by specific users

    Query Examples:
        - Find error monitors: query="name:*error*"
        - Find critical monitors: query="monitorStatus:Critical"
        - Find all log monitors: query="monitorType:Logs"
        - Find by creator: query="createdBy:USER_ID"

    Monitor Status Values:
        - Normal: No alerts firing
        - Critical: Critical threshold breached
        - Warning: Warning threshold breached
        - Missing Data: No data received

    API Reference: https://api.sumologic.com/docs/#operation/monitorsSearch
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("search_sumo_monitors")

        validation = MonitorSearchValidation(query=query)
        limit, offset = validate_pagination(limit, offset)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        monitors = await client.search_monitors(validation.query, limit, offset)
        return json.dumps(monitors, indent=2)
    except Exception as e:
        return handle_tool_error(e, "search_sumo_monitors")


@mcp.tool()
async def get_sumo_partitions(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get list of Sumo Logic partitions.

    Partitions are data subsets used to improve query performance by pre-filtering logs
    at index time. Understanding partitions helps optimize query performance and costs.

    Returns:
        JSON array of partition objects containing:
        - name: Partition name (used in queries with _index)
        - routingExpression: Filter expression for partition
        - retentionPeriod: Days data is retained
        - isActive: Whether partition is active
        - dataForwardingId: Data forwarding configuration (if any)
        - totalBytes: Total data size in partition

    Use Cases:
        - **Query optimization**: Use _index=partition_name to speed up queries
        - **Data management**: See how data is organized and retained
        - **Cost analysis**: Understand data distribution across partitions
        - **Partition discovery**: Find available partitions for queries
        - **Retention review**: Check retention policies per partition

    Query Performance Tip:
        When querying specific data, use partition index for faster results:
        _index=cloudtrail _sourceCategory=aws/cloudtrail | ...

    Example Output:
        [{
          "name": "cloudtrail",
          "routingExpression": "_sourceCategory=aws/cloudtrail",
          "retentionPeriod": 30,
          "isActive": true,
          "totalBytes": 1073741824
        }]

    Related Concepts:
        - Partitions pre-filter data at index time (fast)
        - Views pre-filter data at query time (slower but more flexible)
        - Use partitions when you frequently query specific data subsets

    API Reference: https://api.sumologic.com/docs/#operation/listPartitions
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_partitions")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        partitions = await client.get_partitions(limit=limit)
        return json.dumps(partitions, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_partitions")


@mcp.tool()
async def list_scheduled_views(
    limit: int = Field(default=100, description="Maximum number of results (1-1000)"),
    token: str = Field(
        default=None, description="Pagination token from previous response's 'next' field"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get list of scheduled views with pagination.

    Scheduled views are pre-aggregated data sets created by admins and power users to
    accelerate reporting queries. Views run every 1 minute, pre-computing stats and
    caching complex parsing/filtering/lookup operations.

    Returns:
        JSON with scheduled views array and optional pagination token:
        - id: View ID
        - indexName: View name (used in queries with _view=name)
        - query: View query definition
        - startTime: View start time
        - retentionPeriod: Retention in days
        - dataForwardingId: Data forwarding config (if any)
        - parsing: Parsing mode
        - reduceOnlyFields: Output schema fields
        - indexedFields: Indexed fields for filtering
        - next: Pagination token for next page (if more results available)

    Use Cases:
        - **Query acceleration**: Find views that pre-aggregate data for your use case
        - **Schema discovery**: See output fields available in each view
        - **Performance optimization**: Replace raw log queries with view queries
        - **View inventory**: List all available scheduled views
        - **Cost optimization**: Views provide 0 scan cost (tiered) or reduced scan (flex)

    Query Performance:
        Views are queried using _view=view_name or _view=pattern* for versioned views.
        Views have 1m timeslice and defined schema - much faster than raw logs for
        aggregate queries over long time ranges (days to weeks).

    Pagination:
        - Check response's 'next' field for pagination token
        - Pass token to get next page of results
        - When 'next' is absent, you've reached the end

    Example Output:
        {
          "data": [{
            "id": "000000000ABC1234",
            "indexName": "apache_status_code_1m_v1",
            "query": "_sourceCategory=apache | parse ... | count by status_code, host | timeslice 1m",
            "startTime": "2024-01-01T00:00:00Z",
            "retentionPeriod": 30,
            "reduceOnlyFields": ["status_code", "host", "_count"]
          }],
          "next": "token_for_next_page"
        }

    View Query Notes:
        - Views use _view=name scope (not keywords)
        - Filter with field=value expressions in scope
        - Views have fixed schema - check reduceOnlyFields
        - Versioned views common: apache_status_code_1m_v1, v2, etc.
        - Query patterns: _view=apache_status_code_1m_*

    CRITICAL Aggregate Column Naming:
        ⚠️ COMMON MISTAKE: Don't use | count in queries against aggregate views!
        - This counts view rows, NOT original events
        - Check reduceOnlyFields for actual aggregate column names
        - Common names: _count, _sum, _avg, _max, _min
        - May be aliased in view definition: requests, total_bytes, avg_latency, etc.
        - Always use sum(), avg(), max(), or min() on the pre-aggregated columns

        Example WRONG: _view=apache_status | count by status_code
        Example RIGHT: _view=apache_status | sum(_count) as requests by status_code

    Common View Patterns:

        1. **Reporting Acceleration (Simple Aggregation)**
           View definition:
           ```
           _sourceCategory=Labs/Apache/Access
           | parse "HTTP/1.1\" * " as status_code
           | timeslice 1m
           | count by status_code, _timeslice
           ```
           Query pattern:
           ```
           _view=apache_status
           | sum(_count) as requests by status_code, _timeslice
           | timeslice 1h  # Re-aggregate 1m to 1h
           | transpose row _timeslice column status_code
           ```

        2. **Caching Heavy Operations (Threat Intelligence, Lookups)**
           View definition (saves threatip + geoip lookups):
           ```
           _sourceCategory=logs/firewall
           | json "httpRequest.clientIp" as src_ip
           | where ispublicip(src_ip)
           | threatip src_ip | where !(isempty(malicious_confidence))
           | timeslice 1m
           | count by _timeslice, src_ip, action, malicious_confidence, actor
           | lookup asn, organization from asn://default on ip=src_ip
           | geoip src_ip
           ```
           Query pattern (fast threat search over weeks):
           ```
           _view=threat_matches_1m
           | sum(_count) by src_ip, country_code, malicious_confidence
           | sort by _sum desc
           ```
           Benefits: Pre-computed threatip/geoip lookups, stores results before they change

    Cost Optimization:
        - Tiered: 0 scan cost for aggregate views, continuous tier cost for raw view ingestion
        - Flex: Scan charges apply but much lower than raw logs due to aggregation
        - Best for: Dashboard panels, scheduled reports, long time range queries

    API Reference: https://api.sumologic.com/docs/#tag/scheduledViewManagement
    Help Reference: https://www.sumologic.com/help/docs/manage/scheduled-views/
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("list_scheduled_views")

        # Validate pagination
        if limit < 1 or limit > 1000:
            raise ValidationError("limit must be between 1 and 1000")
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        result = await client.list_scheduled_views(limit=limit, token=token)
        return json.dumps(result, indent=2)
    except Exception as e:
        return handle_tool_error(e, "list_scheduled_views")


@mcp.tool()
async def list_custom_fields(
    instance: str = Field(default="default", description="Sumo Logic instance name")
) -> str:
    """
    Get list of custom fields defined in the organization.

    Fields can be defined by administrators to enable field names in the UI,
    or through field extraction rules. Returns all custom fields with their
    properties including name, data type, and state.

    Returns:
        List of custom fields with properties:
        - fieldId: Unique identifier
        - fieldName: Name of the field
        - dataType: Field data type (String, Long, Int, Double, Boolean)
        - state: Field state (Enabled, Disabled)
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("list_custom_fields")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)
        fields = await client.list_custom_fields()
        return json.dumps(fields, indent=2)
    except Exception as e:
        return handle_tool_error(e, "list_custom_fields")


@mcp.tool()
async def list_field_extraction_rules(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get list of field extraction rules (FERs) defined in the organization.

    Field extraction rules are created by administrators to simplify query
    experience by pre-parsing fields, or to speed up query performance.
    Pre-parsed fields stored in partitions as indexed data are much faster
    to query than repeating field parsing at search time.

    Returns:
        List of field extraction rules with properties:
        - id: Unique identifier
        - name: Rule name
        - scope: Where the rule applies (e.g., _sourceCategory=prod/app)
        - parseExpression: Regex or parse expression to extract fields
        - enabled: Whether the rule is active
        - createdAt/modifiedAt: Timestamps
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("list_field_extraction_rules")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        rules = await client.list_field_extraction_rules(limit=limit)
        return json.dumps(rules, indent=2)
    except Exception as e:
        return handle_tool_error(e, "list_field_extraction_rules")


@mcp.tool()
async def get_field_extraction_rule(
    rule_id: str = Field(description="Field extraction rule ID"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get a specific field extraction rule by ID.

    Returns detailed information about a field extraction rule including
    its configuration, scope, parse expression, and enabled status.

    Parameters:
        rule_id: The unique identifier of the field extraction rule
        instance: Instance name

    Returns:
        Field extraction rule details:
        - id: Unique identifier
        - name: Rule name
        - scope: Where the rule applies (e.g., _sourceCategory=prod/app)
        - parseExpression: Regex or parse expression to extract fields
        - enabled: Whether the rule is active
        - createdAt/modifiedAt: Timestamps
        - createdBy/modifiedBy: User information
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_field_extraction_rule")

        instance = validate_instance_name(instance)
        rule_id = validate_query_input(rule_id)
        client = await get_sumo_client(instance)

        rule = await client.get_field_extraction_rule(rule_id)
        return json.dumps(rule, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_field_extraction_rule")


@mcp.tool()
async def list_sumo_instances() -> str:
    """List all configured Sumo Logic instances."""
    try:
        _ensure_config_initialized()
        config = get_config()
        instances = config.list_instances()
        return json.dumps({"instances": instances, "count": len(instances)}, indent=2)
    except Exception as e:
        return handle_tool_error(e, "list_sumo_instances")


# Search Audit Tool


@mcp.tool()
async def run_search_audit_query(
    from_time: str = "-24h",
    to_time: str = "now",
    query_type: str = "*",
    user_name: str = "*",
    content_name: str = "*",
    query_filter: str = "*",
    query_regex: str = ".*",
    scope_filters: Optional[list[str]] = None,
    where_filters: Optional[list[str]] = None,
    include_raw_data: bool = False,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Run a search audit query to analyze search usage and performance.

    IMPORTANT: The _view=sumologic_search_usage_per_query special view does NOT support
    keyword/freetext search. You must use field=value scope expressions or | where filters
    to query this view. See scope_filters and where_filters parameters below.

    Aggregates search usage metrics by user, query, query type, and content.
    Calculates data scanned (including Infrequent and Flex tiers), runtime,
    time range, partitions scanned, and result counts.

    Parameters:
        from_time: Start time (relative like '-24h' or ISO8601)
        to_time: End time (relative like 'now' or ISO8601)
        query_type: Filter by query type (* for all, Interactive, Scheduled, etc.)
                    NOTE: This is a legacy parameter. For more precise filtering, use scope_filters instead.
        user_name: Filter by username (* for all, use wildcards like 'john*')
                   NOTE: This is a legacy parameter. For more precise filtering, use scope_filters instead.
        content_name: Filter by content name (* for all)
                      NOTE: This is a legacy parameter. For more precise filtering, use scope_filters instead.
        query_filter: Filter by query text (* for all)
                      NOTE: This is a legacy parameter. For more precise filtering, use scope_filters instead.
        query_regex: Regex pattern to filter queries (default: '.*' for all)
        scope_filters: (NEW) One or more field=value scope keyword expressions for FAST index-level
                      filtering. These are injected into the scope line alongside _view=sumologic_search_usage_per_query.

                      Supported fields: user_name, query_type, content_name, query, analytics_tier,
                                       status_message, session_id, remote_ip

                      Examples:
                        - ["query=*threatip*"] - Find searches using threatip operator
                        - ["user_name=rick@example.com"] - Filter to specific user
                        - ["query_type=Interactive"] - Interactive searches only
                        - ["query_type=int*"] - Glob match on query_type
                        - ["content_name=*Dashboard*"] - Content name contains Dashboard
                        - ["analytics_tier=*infrequent*"] - Searches on Infrequent tier

                      Multiple expressions are AND-combined. Glob wildcards (*) supported.
                      Values with spaces must be quoted.

                      NOTE: scope_filters override the legacy user_name/query_type/content_name/query_filter
                            parameters when provided.

        where_filters: (NEW) One or more | where clause expressions for FLEXIBLE post-pipe filtering.
                      These are slower than scope_filters but support numeric comparisons, regex, and
                      complex logic. Each string should be the expression AFTER "| where" (don't include
                      the pipe or "where" keyword).

                      Supported fields:
                        - Numeric: execution_duration_ms, data_scanned_bytes, data_retrieved_bytes,
                                  scanned_message_count, retrieved_message_count, scanned_partition_count,
                                  query_start_time, query_end_time
                        - Boolean: is_aggregate, is_emulated_search
                        - String: status_message, content_name, query, user_name, query_type, analytics_tier

                      Examples:
                        - ["execution_duration_ms > 30000"] - Searches longer than 30 seconds
                        - ["status_message matches \"*Fail*\""] - Failed searches
                        - ["data_scanned_bytes > 1073741824"] - Scanned more than 1GB
                        - ["is_aggregate = true"] - Aggregate queries only
                        - ["scanned_partition_count > 5"] - Scanned many partitions

                      Multiple expressions are AND-combined (each becomes a separate | where clause).

        include_raw_data: Include raw field data in results (default: False)
        instance: Instance name

    Returns:
        Aggregated search audit results with metrics:
        - searches: Number of searches
        - scan_gb: Total data scanned in GB
        - inf_scan_gb: Infrequent tier data scanned in GB
        - flex_scan_gb: Flex tier data scanned in GB
        - results: Total retrieved message count
        - avg_partitions: Average partitions scanned
        - avg_range_h: Average time range in hours
        - sum_runtime_minutes: Total runtime in minutes
        - avg_runtime_minutes: Average runtime in minutes

    Example queries:
        - All searches in last 24h: (defaults)
        - Interactive searches by user: query_type='Interactive', user_name='john@example.com'
        - Dashboard searches: query_type='Scheduled', content_name='*Dashboard*'
        - Slow failing searches: scope_filters=["user_name=rick@acme.com", "query_type=Interactive"],
                                where_filters=["execution_duration_ms > 60000", "status_message matches \"*Fail*\""]
        - Searches using threatip: scope_filters=["query=*threatip*"]
        - Large scheduled searches: scope_filters=["query_type=Scheduled"],
                                   where_filters=["data_scanned_bytes > 1099511627776"]
        - Expensive searches: query_regex=r'.*\\| count.*' (searches with count operator)

    Reference: https://www.sumologic.com/help/docs/manage/security/audit-indexes/search-audit-index/

    Full field reference for _view=sumologic_search_usage_per_query:
    Scope-filterable: analytics_tier, content_name, query, query_type, remote_ip, session_id, status_message, user_name
    Where-filterable: All above plus content_identifier, data_retrieved_bytes, data_scanned_bytes, execution_duration_ms,
                     is_aggregate, is_emulated_search, query_end_time, query_start_time, retrieved_message_count,
                     scanned_bytes_breakdown, scanned_bytes_breakdown_by_metering_type, scanned_message_count,
                     scanned_partition_count
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("run_search_audit_query")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Validate and build scope filters
        def validate_scope_filters(filters: Optional[list[str]]) -> list[str]:
            """Validate scope filter expressions."""
            if not filters:
                return []

            allowed_fields = {
                "user_name",
                "query_type",
                "content_name",
                "query",
                "analytics_tier",
                "status_message",
                "session_id",
                "remote_ip",
            }

            validated = []
            for f in filters:
                f = f.strip()
                if not f:
                    continue

                # Check for injection attempts
                if "\n" in f or "\r" in f:
                    raise ValidationError("Scope filters cannot contain newlines")
                if "| delete" in f.lower() or "| create" in f.lower() or "| save" in f.lower():
                    raise ValidationError("Scope filters cannot contain write operators")

                # Must contain = sign
                if "=" not in f:
                    raise ValidationError(
                        f"Invalid scope filter '{f}': must be in field=value format"
                    )

                # Extract field name and validate
                field = f.split("=")[0].strip()
                if field not in allowed_fields:
                    raise ValidationError(
                        f"Field '{field}' is not supported as a scope filter. "
                        f"Supported fields: {', '.join(sorted(allowed_fields))}. "
                        f"For other fields use where_filters instead."
                    )

                validated.append(f)

            return validated

        # Validate and build where filters
        def validate_where_filters(filters: Optional[list[str]]) -> list[str]:
            """Validate where filter expressions."""
            if not filters:
                return []

            validated = []
            for f in filters:
                f = f.strip()
                if not f:
                    continue

                # Check for injection attempts
                if "| delete" in f.lower() or "| create" in f.lower() or "| save" in f.lower():
                    raise ValidationError("Where filters cannot contain write operators")

                # Should not start with | or where
                if f.startswith("|") or f.lower().startswith("where "):
                    raise ValidationError(
                        f"Where filter '{f}' should not start with '|' or 'where'. "
                        "Provide only the expression (e.g., 'execution_duration_ms > 30000')"
                    )

                validated.append(f)

            return validated

        # Process scope filters - new filters take precedence over legacy parameters
        validated_scope_filters = validate_scope_filters(scope_filters)

        # Build scope line
        if validated_scope_filters:
            # Use new scope_filters (they override legacy parameters)
            scope_line = "_view=sumologic_search_usage_per_query " + " ".join(
                validated_scope_filters
            )
        else:
            # Use legacy parameters for backward compatibility
            scope_line = f"""_view=sumologic_search_usage_per_query
query_type={query_type}
user_name={user_name}
content_name={content_name}
query={query_filter}"""

        # Process where filters
        validated_where_filters = validate_where_filters(where_filters)
        where_clauses_str = "\n".join(f"| where {f}" for f in validated_where_filters)

        # Build search audit query
        # Structure: scope_line -> where_clauses -> field extractions -> aggregations
        # Note: scope_line is already complete (single line or multi-line based on legacy vs new filters)
        query_parts = [scope_line]

        if where_clauses_str:
            query_parts.append(where_clauses_str)

        # Add the rest of the pipeline (field extractions and aggregations)
        query_parts.append(
            f"""
| ((query_end_time - query_start_time ) /1000 / 60 ) as time_range_m
| json field=scanned_bytes_breakdown "Infrequent" as inf_bytes nodrop
| json field=scanned_bytes_breakdown "Flex" as flex_bytes nodrop
| if (isnull(inf_bytes),0,inf_bytes) as inf_bytes
| if (isnull(flex_bytes),0,flex_bytes) as flex_bytes

| round((data_scanned_bytes /1024/1024/1024) * 10 )/10 as scan_gbytes
| round((inf_bytes/1024/1024/1024) * 10) / 10 as inf_scan_gb
| round((flex_bytes/1024/1024/1024) * 10) / 10 as flex_scan_gb
| execution_duration_ms / ( 1000 * 60) as runtime_minutes

| time_range_m/60 as time_range_h
| count as searches, sum(scan_gbytes) as scan_gb, sum(inf_scan_gb) as inf_scan_gb, sum(flex_scan_gb) as flex_scan_gb, sum(retrieved_message_count) as results, avg(scanned_partition_count) as avg_partitions,
 avg(time_range_h) as avg_range_h, sum(runtime_minutes) as sum_runtime_minutes, avg(runtime_minutes) as avg_runtime_minutes by user_name, query, query_type, content_name, content_identifier | sort query asc
| where query matches /(?i){query_regex}/"""
        )

        # Combine all query parts
        query = "\n".join(query_parts)

        # Create search job
        job_response = await client.create_search_job(
            query=query, from_time=from_time, to_time=to_time, timezone_str="UTC"
        )

        job_id = job_response["id"]

        # Poll for completion with timeout
        max_attempts = 300  # 5 minutes
        for attempt in range(max_attempts):
            await asyncio.sleep(1)

            status = await client.get_search_job_status(job_id)
            state = status["state"]

            if state == "DONE GATHERING RESULTS":
                break
            elif state == "CANCELLED":
                raise APIError("Search job was cancelled")

        # Get records (aggregated results)
        records_response = await client.get_search_job_records(job_id, limit=10000)
        records = records_response.get("records", [])

        # Delete the job
        try:
            await client.delete_search_job(job_id)
        except Exception:  # nosec B110
            pass  # Best effort cleanup - job deletion failure is acceptable

        # Helper to safely convert to int
        def safe_int(value, default=0):
            try:
                return int(float(value)) if value else default
            except (ValueError, TypeError):
                return default

        # Helper to safely convert to float
        def safe_float(value, default=0.0):
            try:
                return float(value) if value else default
            except (ValueError, TypeError):
                return default

        # Format results with summary
        result = {
            "query_parameters": {
                "from_time": from_time,
                "to_time": to_time,
                "query_type": query_type,
                "user_name": user_name,
                "content_name": content_name,
                "query_filter": query_filter,
                "query_regex": query_regex,
                "scope_filters": validated_scope_filters if validated_scope_filters else None,
                "where_filters": validated_where_filters if validated_where_filters else None,
            },
            "summary": {
                "total_records": len(records),
                "total_searches": sum(
                    safe_int(r.get("map", {}).get("searches", 0)) for r in records
                ),
                "total_scan_gb": sum(
                    safe_float(r.get("map", {}).get("scan_gb", 0)) for r in records
                ),
                "total_inf_scan_gb": sum(
                    safe_float(r.get("map", {}).get("inf_scan_gb", 0)) for r in records
                ),
                "total_flex_scan_gb": sum(
                    safe_float(r.get("map", {}).get("flex_scan_gb", 0)) for r in records
                ),
            },
            "records": [],
        }

        # Process records
        for record in records:
            record_map = record.get("map", {})
            processed_record = {
                "user_name": record_map.get("user_name"),
                "query_type": record_map.get("query_type"),
                "content_name": record_map.get("content_name"),
                "content_identifier": record_map.get("content_identifier"),
                "query": record_map.get("query"),
                "searches": safe_int(record_map.get("searches", 0)),
                "scan_gb": safe_float(record_map.get("scan_gb", 0)),
                "inf_scan_gb": safe_float(record_map.get("inf_scan_gb", 0)),
                "flex_scan_gb": safe_float(record_map.get("flex_scan_gb", 0)),
                "results": safe_int(record_map.get("results", 0)),
                "avg_partitions": safe_float(record_map.get("avg_partitions", 0)),
                "avg_range_h": safe_float(record_map.get("avg_range_h", 0)),
                "sum_runtime_minutes": safe_float(record_map.get("sum_runtime_minutes", 0)),
                "avg_runtime_minutes": safe_float(record_map.get("avg_runtime_minutes", 0)),
            }

            if include_raw_data:
                processed_record["_raw"] = record

            result["records"].append(processed_record)

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "run_search_audit_query")


@mcp.tool()
async def analyze_search_scan_cost(
    from_time: str = "-24h",
    to_time: str = "now",
    query_type: str = "*",
    user_name: str = "*",
    content_name: str = "*",
    analytics_tier_filter: str = "*",
    breakdown_type: str = "auto",
    group_by: str = "user_query",
    include_scope_parsing: bool = True,
    scan_credit_rate: float = 0.016,
    min_scan_gb: float = 0.0,
    sort_by: str = "scan_credits",
    limit: int = 100,
    instance: str = "default",
) -> str:
    """
    Analyze search scan costs with detailed tier/metering breakdown for Infrequent and Flex customers.

    This tool is specifically designed for analyzing pay-per-search costs in:
    - Infrequent tier (pay per GB scanned)
    - Flex tier (free ingestion, pay per search scan)

    Parses scanned_bytes_breakdown or scanned_bytes_breakdown_by_metering_type to provide
    detailed scan cost analysis by user, query, scope, and content.

    Parameters:
        from_time: Start time (relative like '-24h' or ISO8601)
        to_time: End time (relative like 'now' or ISO8601)
        query_type: Filter by query type (* for all, Interactive, Scheduled, etc.)
        user_name: Filter by username (* for all)
        content_name: Filter by content name (* for all, use wildcards)
        analytics_tier_filter: Filter by analytics_tier field (* for all, *infrequent*, *flex*, etc.)
        breakdown_type: 'auto' (auto-detect), 'tier' (Continuous/Frequent/Infrequent), or 'metering' (Flex/FlexSecurity/CSE/etc.)
                       **IMPORTANT**: Flex organizations MUST use 'metering' breakdown. Using 'tier' on Flex orgs
                       returns near-zero scan data. Default 'auto' detects organization type automatically.
        group_by: Grouping level - 'user', 'user_query', 'user_scope_query', 'user_content', 'content'
        include_scope_parsing: Extract scope (_index/_view/_datatier) from query text (default: True)
        scan_credit_rate: Credits per GB scanned (default: 0.016 cr/GB = 16 cr/TB). Only used for Infrequent tier
                         (tiered accounts) where 0.016 is the standard rate. For Flex metering breakdown, credits
                         are NOT calculated since rates are highly contract-specific.
        min_scan_gb: Minimum scan GB threshold to include in results (default: 0.0)
        sort_by: Sort field - 'scan_credits', 'total_scan_gb', 'queries', 'billable_scan_gb' (default: scan_credits)
        limit: Maximum number of results (default: 100)
        instance: Instance name

    Breakdown Types:
        - 'auto': Automatically detects organization type (Flex vs Tiered) and selects appropriate breakdown

        - 'tier': Data tier breakdown (for TIERED customers ONLY)
          - Continuous: Always-on analytics tier
          - Frequent: Medium access tier
          - Infrequent: Low-cost, pay-per-search tier
          **WARNING**: Returns near-zero data on Flex organizations!

        - 'metering': Metering type breakdown (for FLEX customers - REQUIRED for accurate data)
          - Flex: Billable log search
          - FlexSecurity: Security logs (not billable for search)
          - Continuous: Legacy continuous tier
          - Frequent: Legacy frequent tier
          - Infrequent: Legacy infrequent tier
          - Security: Legacy security tier (not billable for search)
          - Tracing: Tracing data (not billable for search)

    Group By Options:
        - 'user': Aggregate by user_name only
        - 'user_query': Group by user_name and query text
        - 'user_scope_query': Group by user_name, scope (_index/_view), and query
        - 'user_content': Group by user_name and content_name (for dashboards/scheduled searches)
        - 'content': Group by content_name only (for scheduled search analysis)

    Returns:
        JSON with scan cost analysis including:
        - queries: Number of searches
        - total_scan_gb: Total data scanned across all tiers
        - tier_breakdown: GB scanned per tier (varies by breakdown_type)
        - billable_scan_gb: Billable scan volume in GB (for Flex metering type)
        - billable_scan_tb: Billable scan volume in TB (for Flex metering type)
        - non_billable_scan_gb: Non-billable scan volume (for Flex metering type)
        - scan_credits: Estimated credits (tier breakdown only - Infrequent tier)
        - credits_per_query: Average credits per query (tier breakdown only)

        Note: For Flex metering breakdown, credits are NOT included since rates vary by contract.
        TB values are provided as the primary unit for Flex scan volumes.

    Use Cases:
        1. Infrequent tier cost analysis:
           breakdown_type='tier', analytics_tier_filter='*infrequent*', group_by='user_query'

        2. Flex billable vs non-billable analysis:
           breakdown_type='metering', group_by='user_scope_query'

        3. Expensive dashboard analysis:
           group_by='content', query_type='Scheduled'

        4. User cost ranking:
           group_by='user', sort_by='scan_credits'

    Credit Rate Examples:
        - Infrequent tier: ~0.016 credits/GB (varies by contract)
        - Flex tier: ~0.016-0.02 credits/GB billable scan
        - Adjust scan_credit_rate parameter to match your contract

    Reference: https://www.sumologic.com/help/docs/manage/security/audit-indexes/search-audit-index/
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("analyze_search_scan_cost")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Auto-detect breakdown type if set to 'auto'
        original_breakdown_type = breakdown_type
        detected_org_type = None

        if breakdown_type == "auto":
            try:
                # Get account status to determine if Flex or Tiered
                account_status = await client.get_account_status()
                log_model = account_status.get("logModel", "").lower()

                if log_model == "flex":
                    breakdown_type = "metering"
                    detected_org_type = "Flex"
                else:
                    # Default to tier for Tiered, or unknown org types
                    breakdown_type = "tier"
                    detected_org_type = "Tiered"

            except Exception:
                # If account status check fails, default to metering (safer for Flex orgs)
                breakdown_type = "metering"
                detected_org_type = "Unknown (defaulted to metering)"

        # Validate breakdown_type after auto-detection
        if breakdown_type not in ["tier", "metering"]:
            raise ValueError(
                f"Invalid breakdown_type after auto-detection: {breakdown_type}. Must be 'auto', 'tier', or 'metering'"
            )

        # Build JSON field parsing based on breakdown type
        if breakdown_type == "tier":
            # Parse data tier breakdown
            json_parsing = """| json field=scanned_bytes_breakdown "Continuous" as scan_continuous nodrop
| json field=scanned_bytes_breakdown "Frequent" as scan_frequent nodrop
| json field=scanned_bytes_breakdown "Infrequent" as scan_infrequent nodrop
| if (isnull(scan_continuous),0,scan_continuous) as scan_continuous
| if (isnull(scan_frequent),0,scan_frequent) as scan_frequent
| if (isnull(scan_infrequent),0,scan_infrequent) as scan_infrequent
| scan_continuous + scan_frequent + scan_infrequent as total_scan_bytes"""

            tier_aggregations = "sum(scan_continuous) as scan_continuous, sum(scan_frequent) as scan_frequent, sum(scan_infrequent) as scan_infrequent"

        elif breakdown_type == "metering":
            # Parse metering type breakdown
            json_parsing = """| json field=scanned_bytes_breakdown_by_metering_type "Flex" as scan_flex nodrop
| json field=scanned_bytes_breakdown_by_metering_type "Continuous" as scan_continuous nodrop
| json field=scanned_bytes_breakdown_by_metering_type "Frequent" as scan_frequent nodrop
| json field=scanned_bytes_breakdown_by_metering_type "Infrequent" as scan_infrequent nodrop
| json field=scanned_bytes_breakdown_by_metering_type "FlexSecurity" as scan_flex_security nodrop
| json field=scanned_bytes_breakdown_by_metering_type "Security" as scan_security nodrop
| json field=scanned_bytes_breakdown_by_metering_type "Tracing" as scan_tracing nodrop
| if (isnull(scan_flex),0,scan_flex) as scan_flex
| if (isnull(scan_continuous),0,scan_continuous) as scan_continuous
| if (isnull(scan_frequent),0,scan_frequent) as scan_frequent
| if (isnull(scan_infrequent),0,scan_infrequent) as scan_infrequent
| if (isnull(scan_flex_security),0,scan_flex_security) as scan_flex_security
| if (isnull(scan_security),0,scan_security) as scan_security
| if (isnull(scan_tracing),0,scan_tracing) as scan_tracing
| scan_flex + scan_continuous + scan_frequent + scan_infrequent as billable_scan_bytes
| scan_flex_security + scan_security + scan_tracing as non_billable_scan_bytes
| billable_scan_bytes + non_billable_scan_bytes as total_scan_bytes"""

            tier_aggregations = "sum(scan_flex) as scan_flex, sum(scan_continuous) as scan_continuous, sum(scan_frequent) as scan_frequent, sum(scan_infrequent) as scan_infrequent, sum(scan_flex_security) as scan_flex_security, sum(scan_security) as scan_security, sum(scan_tracing) as scan_tracing, sum(billable_scan_bytes) as billable_scan_bytes, sum(non_billable_scan_bytes) as non_billable_scan_bytes"
        else:
            raise ValueError(
                f"Invalid breakdown_type: {breakdown_type}. Must be 'tier' or 'metering'"
            )

        # Build scope parsing if enabled
        scope_parsing = ""
        if include_scope_parsing:
            scope_parsing = '| parse regex field=query "(?i)(?<scope>(?:_datatier|_index|_view) *= *[a-zA-Z_0-9]+)" nodrop\n| if(isNull(scope),"no_scope",scope) as scope'

        # Build grouping clause based on group_by parameter
        group_fields = []
        if group_by == "user":
            group_fields = ["user_name"]
        elif group_by == "user_query":
            group_fields = ["user_name", "query"]
        elif group_by == "user_scope_query":
            if include_scope_parsing:
                group_fields = ["user_name", "scope", "query"]
            else:
                group_fields = ["user_name", "query"]
        elif group_by == "user_content":
            group_fields = ["user_name", "content_name"]
        elif group_by == "content":
            group_fields = ["content_name", "query_type"]
        else:
            raise ValueError(
                f"Invalid group_by: {group_by}. Must be one of: user, user_query, user_scope_query, user_content, content"
            )

        group_by_clause = ", ".join(group_fields)

        # Build query
        query = f"""_view=sumologic_search_usage_per_query
query_type={query_type}
user_name={user_name}
content_name={content_name}
analytics_tier={analytics_tier_filter}

| ((query_end_time - query_start_time ) /1000 / 60 / 60 / 24 ) as range_days
{json_parsing}
{scope_parsing}

| total_scan_bytes / (1024*1024*1024) as total_scan_gb
| count as queries, sum(total_scan_gb) as total_scan_gb, {tier_aggregations} by {group_by_clause}

| total_scan_gb * {scan_credit_rate} as scan_credits
| scan_credits / queries as credits_per_query
| where total_scan_gb >= {min_scan_gb}
| sort by {sort_by} desc
| limit {limit}"""

        # Create search job
        job_response = await client.create_search_job(
            query=query, from_time=from_time, to_time=to_time, timezone_str="UTC"
        )

        job_id = job_response["id"]

        # Poll for completion with timeout
        max_attempts = 300  # 5 minutes
        for attempt in range(max_attempts):
            await asyncio.sleep(1)

            status = await client.get_search_job_status(job_id)
            state = status["state"]

            if state == "DONE GATHERING RESULTS":
                break
            elif state == "CANCELLED":
                raise APIError("Search job was cancelled")

        # Get records
        records_response = await client.get_search_job_records(job_id, limit=limit)
        records = records_response.get("records", [])

        # Delete the job
        try:
            await client.delete_search_job(job_id)
        except Exception:  # nosec B110
            pass  # Best effort cleanup - job deletion failure is acceptable

        # Helper to safely convert values
        def safe_float(value, default=0.0):
            try:
                return float(value) if value else default
            except (ValueError, TypeError):
                return default

        def safe_int(value, default=0):
            try:
                return int(float(value)) if value else default
            except (ValueError, TypeError):
                return default

        # Format results
        result = {
            "query_parameters": {
                "from_time": from_time,
                "to_time": to_time,
                "query_type": query_type,
                "user_name": user_name,
                "content_name": content_name,
                "analytics_tier_filter": analytics_tier_filter,
                "breakdown_type": breakdown_type,
                "breakdown_type_requested": original_breakdown_type,
                "group_by": group_by,
                "scan_credit_rate": scan_credit_rate,
                "min_scan_gb": min_scan_gb,
            },
            "summary": {
                "total_records": len(records),
                "total_queries": sum(safe_int(r.get("map", {}).get("queries", 0)) for r in records),
                "total_scan_gb": round(
                    sum(safe_float(r.get("map", {}).get("total_scan_gb", 0)) for r in records), 2
                ),
            },
            "records": [],
        }

        # Add organization type detection info if auto-detected
        if detected_org_type:
            result["query_parameters"]["detected_org_type"] = detected_org_type
            result["query_parameters"]["auto_detection_used"] = True

        # Add metering-specific summary if applicable (Flex)
        if breakdown_type == "metering":
            total_billable_gb = round(
                sum(
                    safe_float(r.get("map", {}).get("billable_scan_bytes", 0)) / (1024**3)
                    for r in records
                ),
                2,
            )
            result["summary"]["total_billable_scan_gb"] = total_billable_gb
            result["summary"]["total_billable_scan_tb"] = round(total_billable_gb / 1024, 4)
            result["summary"]["total_non_billable_scan_gb"] = round(
                sum(
                    safe_float(r.get("map", {}).get("non_billable_scan_bytes", 0)) / (1024**3)
                    for r in records
                ),
                2,
            )
            result["summary"]["flex_billing_note"] = (
                "Credits NOT calculated for Flex metering - rates are highly contract-specific. "
                "Contact Sumo Logic for your contracted scan rate."
            )
        else:
            # Only add credits for tier breakdown (Infrequent tier)
            result["summary"]["total_scan_credits"] = round(
                sum(safe_float(r.get("map", {}).get("scan_credits", 0)) for r in records), 2
            )

        # Detect potential Flex org using 'tier' breakdown incorrectly
        if breakdown_type == "tier":
            total_queries = result["summary"]["total_queries"]
            total_scan_gb = result["summary"]["total_scan_gb"]

            # If many queries but suspiciously low scan data, likely Flex org using wrong breakdown
            if total_queries > 1000 and total_scan_gb < 1.0:
                warning = {
                    "type": "POSSIBLE_FLEX_ORG_USING_TIER_BREAKDOWN",
                    "message": (
                        f"WARNING: Found {total_queries} queries but only {total_scan_gb} GB scanned. "
                        "This pattern suggests you may be on a Flex organization using 'tier' breakdown, "
                        "which returns near-zero scan data for Flex logs. "
                        "Please retry with breakdown_type='metering' or 'auto' for accurate Flex scan costs."
                    ),
                    "recommendation": "Use breakdown_type='metering' or 'auto' for Flex organizations",
                    "queries_analyzed": total_queries,
                    "scan_gb_found": total_scan_gb,
                }
                result["warning"] = warning

        # Process records
        for record in records:
            record_map = record.get("map", {})

            processed_record = {
                "queries": safe_int(record_map.get("queries", 0)),
                "total_scan_gb": round(safe_float(record_map.get("total_scan_gb", 0)), 2),
            }

            # Add grouping fields
            for field in group_fields:
                processed_record[field] = record_map.get(field, "")

            # Add tier breakdown (includes credits for Infrequent tier)
            if breakdown_type == "tier":
                processed_record["scan_credits"] = round(
                    safe_float(record_map.get("scan_credits", 0)), 2
                )
                processed_record["credits_per_query"] = round(
                    safe_float(record_map.get("credits_per_query", 0)), 4
                )
                processed_record["tier_breakdown_gb"] = {
                    "continuous": round(
                        safe_float(record_map.get("scan_continuous", 0)) / (1024**3), 2
                    ),
                    "frequent": round(
                        safe_float(record_map.get("scan_frequent", 0)) / (1024**3), 2
                    ),
                    "infrequent": round(
                        safe_float(record_map.get("scan_infrequent", 0)) / (1024**3), 2
                    ),
                }
            elif breakdown_type == "metering":
                # Flex metering - NO credits, add TB values
                billable_gb = round(
                    safe_float(record_map.get("billable_scan_bytes", 0)) / (1024**3), 2
                )
                processed_record["billable_scan_gb"] = billable_gb
                processed_record["billable_scan_tb"] = round(billable_gb / 1024, 4)
                processed_record["non_billable_scan_gb"] = round(
                    safe_float(record_map.get("non_billable_scan_bytes", 0)) / (1024**3), 2
                )
                processed_record["metering_breakdown_gb"] = {
                    "flex": round(safe_float(record_map.get("scan_flex", 0)) / (1024**3), 2),
                    "continuous": round(
                        safe_float(record_map.get("scan_continuous", 0)) / (1024**3), 2
                    ),
                    "frequent": round(
                        safe_float(record_map.get("scan_frequent", 0)) / (1024**3), 2
                    ),
                    "infrequent": round(
                        safe_float(record_map.get("scan_infrequent", 0)) / (1024**3), 2
                    ),
                    "flex_security": round(
                        safe_float(record_map.get("scan_flex_security", 0)) / (1024**3), 2
                    ),
                    "security": round(
                        safe_float(record_map.get("scan_security", 0)) / (1024**3), 2
                    ),
                    "tracing": round(safe_float(record_map.get("scan_tracing", 0)) / (1024**3), 2),
                }

            result["records"].append(processed_record)

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "analyze_search_scan_cost")


# Content ID Utility Tools


@mcp.tool()
async def convert_content_id_hex_to_decimal(
    hex_id: str = Field(description="Hex content ID (e.g., 00000000005E5403)"),
) -> str:
    """
    Convert hex content ID to decimal format for web UI URLs.

    Sumo Logic stores content IDs as 16-character hex strings but the
    web UI uses decimal format in URLs. Use this to generate shareable links.

    Example: 00000000005E5403 → 6181891
    """
    try:
        from .content_id_utils import format_content_id, hex_to_decimal

        decimal_id = hex_to_decimal(hex_id)

        return json.dumps(
            {
                "hex_id": hex_id.upper(),
                "decimal_id": decimal_id,
                "formatted": format_content_id(hex_id),
            },
            indent=2,
        )

    except Exception as e:
        return handle_tool_error(e, "convert_content_id_hex_to_decimal")


@mcp.tool()
async def convert_content_id_decimal_to_hex(
    decimal_id: str = Field(description="Decimal content ID (e.g., 6181891)"),
) -> str:
    """
    Convert decimal content ID to hex format for API calls.

    Use this when you have a content ID from the web UI (decimal)
    and need to call an API (requires hex format).

    Example: 6181891 → 00000000005E5403
    """
    try:
        from .content_id_utils import decimal_to_hex, format_content_id

        hex_id = decimal_to_hex(decimal_id)

        return json.dumps(
            {"hex_id": hex_id, "decimal_id": decimal_id, "formatted": format_content_id(hex_id)},
            indent=2,
        )

    except Exception as e:
        return handle_tool_error(e, "convert_content_id_decimal_to_hex")


@mcp.tool()
async def get_content_web_url(
    content_id: str = Field(description="Content ID (hex or decimal)"),
    content_type: Optional[str] = Field(
        default=None,
        description="Optional: Content type (Dashboard, Search, Folder, etc.) to optimize URL generation",
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Generate web UI URL for a content item.

    Accepts either hex or decimal content ID and generates the appropriate
    web UI URL for the specified instance, with proper handling for different
    content types (dashboards use different URL format than library content).

    For library content (folders, searches, etc.):
        https://service.au.sumologic.com/library/6181891
    For dashboards:
        https://service.au.sumologic.com/dashboard/<dashboard_id>

    If you have a custom subdomain configured, URLs will use that subdomain instead of 'service'.
    """
    try:
        from .content_id_utils import hex_to_decimal, normalize_to_hex
        from .url_builder import build_dashboard_url, build_library_url

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_content_web_url")

        instance = validate_instance_name(instance)

        # Normalize to hex, then convert to decimal for library URLs
        hex_id = normalize_to_hex(content_id)
        decimal_id = hex_to_decimal(hex_id)

        # Get instance configuration
        instance_config = config.get_instance(instance)
        subdomain = instance_config.subdomain

        # Determine if this is a dashboard and get the dashboard ID if needed
        is_dashboard = False
        dashboard_id = None

        if content_type and content_type.lower() == "dashboard":
            is_dashboard = True
        else:
            # Try to fetch content details to determine type
            try:
                client = await get_sumo_client(instance)
                path_result = await client.get_content_path(hex_id)

                # Check if contentType indicates this is a dashboard
                if path_result.get("contentType") == "Dashboard":
                    is_dashboard = True
            except Exception as e:
                # If we can't fetch content details, assume it's library content
                logger.debug(f"Could not fetch content type for {hex_id}: {e}")

        # Generate the appropriate URL
        if is_dashboard:
            # For dashboards, we need the dashboard's unique ID, not the content ID
            # We'll need to get this from the dashboard list or export
            try:
                client = await get_sumo_client(instance)
                # Try to get dashboard details - dashboards have an 'id' field that's different from content ID
                # We'll use export to get the full dashboard details
                from .async_export_helper import poll_export_job

                export_result = await poll_export_job(
                    client, hex_id, is_admin_mode=False, max_wait_seconds=30
                )

                # Extract dashboard ID from export result
                dashboard_id = export_result.get("id")
                if dashboard_id:
                    url = build_dashboard_url(instance_config.endpoint, dashboard_id, subdomain)
                else:
                    # Fallback to library URL if we can't get dashboard ID
                    url = build_library_url(instance_config.endpoint, decimal_id, subdomain)
                    logger.warning(f"Could not get dashboard ID for {hex_id}, using library URL")
            except Exception as e:
                # Fallback to library URL
                logger.warning(f"Error getting dashboard ID: {e}, using library URL")
                url = build_library_url(instance_config.endpoint, decimal_id, subdomain)
        else:
            # Use library URL for all other content types
            url = build_library_url(instance_config.endpoint, decimal_id, subdomain)

        return json.dumps(
            {
                "url": url,
                "hex_id": hex_id,
                "decimal_id": decimal_id,
                "content_type": "Dashboard" if is_dashboard else "Library Content",
                "instance": instance,
            },
            indent=2,
        )

    except Exception as e:
        return handle_tool_error(e, "get_content_web_url")


@mcp.tool()
async def build_search_web_url(
    query: str = Field(description="Sumo Logic search query to open in the web UI"),
    start_time: Optional[str] = Field(
        default=None,
        description="Start time (e.g., '-1h', '-24h', '2024-01-01T00:00:00', ISO format)",
    ),
    end_time: Optional[str] = Field(
        default=None, description="End time (e.g., '-1s', 'now', '2024-01-01T23:59:59', ISO format)"
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Build a web UI URL to open a log search query.

    Creates a URL that opens the Sumo Logic search page with the specified query
    and time range pre-filled. Useful for sharing searches or opening them from
    other tools.

    Example usage:
    - Open a query for the last hour: query='_sourceCategory=prod/app | count', start_time='-1h'
    - Open with absolute time: start_time='2024-01-01T00:00:00', end_time='2024-01-01T23:59:59'
    - Open with relative time: start_time='-24h', end_time='now'

    If you have a custom subdomain configured, URLs will use that subdomain.

    Returns a URL like: https://service.au.sumologic.com/log-search/create?query=...&startTime=-1h&endTime=-1s
    """
    try:
        from .url_builder import build_search_url

        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Get instance configuration
        instance_config = config.get_instance(instance)
        subdomain = instance_config.subdomain

        # Build the search URL
        url = build_search_url(
            instance_config.endpoint,
            query,
            start_time=start_time or "-1h",
            end_time=end_time or "-1s",
            subdomain=subdomain,
        )

        return json.dumps(
            {
                "url": url,
                "query": query,
                "start_time": start_time or "-1h",
                "end_time": end_time or "-1s",
                "instance": instance,
            },
            indent=2,
        )

    except Exception as e:
        return handle_tool_error(e, "build_search_web_url")


# Account Management Tools


@mcp.tool()
async def get_account_status(
    instance: str = Field(default="default", description="Sumo Logic instance name")
) -> str:
    """
    Get account status including subscription, plan type, and usage information.

    Returns account details including:
    - Plan type (Trial, Essentials, Enterprise Operations, etc.)
    - Total credits and usage
    - Subscription period (start/end dates)
    - Account creation date
    - Organization ID

    This is useful for understanding current subscription status and credit usage.

    API Reference: https://api.sumologic.com/docs/#operation/getStatus
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        await limiter.acquire("get_account_status")
        result = await client.get_account_status()

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_account_status")


@mcp.tool()
async def get_usage_forecast(
    number_of_days: Optional[int] = Field(
        default=None,
        description="Number of days to forecast (e.g., 7, 30, 90). If not specified, defaults to current contract term.",
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Get usage forecast for specified number of days.

    Provides projected usage based on recent consumption patterns:
    - Forecasted total credits
    - Forecasted continuous ingest
    - Forecasted frequent ingest
    - Forecasted storage
    - Forecasted metrics ingest

    Useful for capacity planning and predicting credit consumption.

    Args:
        number_of_days: Number of days to forecast (typically 7, 30, or 90).
                       If not provided, defaults to current contract term.

    API Reference: https://api.sumologic.com/docs/#operation/getUsageForecast
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Validate number_of_days if provided
        if number_of_days is not None and (number_of_days < 1 or number_of_days > 365):
            raise ValidationError("number_of_days must be between 1 and 365")

        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        await limiter.acquire("get_usage_forecast")

        # Only pass numberOfDays param if specified by user
        if number_of_days is not None:
            result = await client.get_usage_forecast(number_of_days)
        else:
            # Call without numberOfDays to get contract term default
            result = await client.get_usage_forecast_default()

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_usage_forecast")


@mcp.tool()
async def export_usage_report(
    start_date: str,
    end_date: str,
    group_by: str = "day",
    report_type: str = "standard",
    include_deployment_charge: bool = False,
    max_wait_seconds: int = 300,
    poll_interval_seconds: int = 5,
    instance: str = "default",
) -> str:
    """
    Export detailed usage report for a date range (async operation).

    This starts an async export job, polls for completion, and returns the download URL.
    The download URL is a presigned S3 URL valid for 10 minutes.

    Returns:
    - Download URL for CSV report
    - Job status and timing information
    - Report metadata (date range, grouping)

    The CSV report includes detailed usage breakdowns:
    - Daily/weekly/monthly totals
    - Usage by product line (continuous ingest, frequent ingest, storage, metrics, etc.)
    - Credit consumption details

    Note: The download URL expires after 10 minutes. Download the CSV immediately.

    API Reference: https://api.sumologic.com/docs/#operation/exportUsageReport
    """
    try:
        from .async_export_helper import poll_folder_export_job

        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Validate dates
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValidationError(f"Invalid date format. Use YYYY-MM-DD: {str(e)}")

        # Validate group_by
        if group_by not in ["day", "week", "month"]:
            raise ValidationError("group_by must be 'day', 'week', or 'month'")

        # Validate report_type
        if report_type not in ["standard", "detailed", "childDetailed"]:
            raise ValidationError("report_type must be 'standard', 'detailed', or 'childDetailed'")

        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        # Start export job
        await limiter.acquire("export_usage_report")
        logger.info(f"Starting usage export job: {start_date} to {end_date}")
        start_result = await client.start_usage_export(
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            report_type=report_type,
            include_deployment_charge=include_deployment_charge,
        )

        job_id = start_result.get("jobId")
        if not job_id:
            raise APIError(f"No job ID returned from export start: {start_result}")

        logger.info(f"Export job started: {job_id}")

        # Poll for completion
        async def get_status(jid: str) -> Dict[str, Any]:
            await limiter.acquire("export_usage_report_poll")
            return await client.get_usage_export_status(jid)

        async def get_result(jid: str) -> Dict[str, Any]:
            return await client.get_usage_export_result(jid)

        final_result = await poll_folder_export_job(
            job_id=job_id,
            folder_type="Usage Report",
            get_status_func=get_status,
            get_result_func=get_result,
            max_wait_seconds=max_wait_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

        # Extract download URL (field is reportDownloadURL)
        download_url = final_result.get("reportDownloadURL")

        result = {
            "job_id": job_id,
            "status": final_result.get("status"),
            "download_url": download_url,
            "start_date": start_date,
            "end_date": end_date,
            "group_by": group_by,
            "report_type": report_type,
            "note": "Download URL is valid for 10 minutes. Download the CSV immediately.",
            "instance": instance,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_usage_report")


@mcp.tool()
async def get_estimated_log_search_usage(
    query: str,
    from_time: str = "-1h",
    to_time: str = "now",
    time_zone: str = "UTC",
    by_view: bool = True,
    instance: str = "default",
) -> str:
    """
    Get estimated data volume that would be scanned for a log search query.

    This tool helps you understand the cost of running queries in Infrequent Data Tier
    and Flex tiers where you pay per query based on data scanned.

    Returns detailed breakdown by partition/view including:
    - Total estimated data to scan
    - Per-partition/view breakdown with data tier info (Continuous, Frequent, Infrequent)
    - Metering type information
    - Scan volume in bytes

    Use this before running expensive queries to:
    - Estimate query costs
    - Refine search scope to reduce scanned data
    - Understand which partitions/views contribute to scan volume

    Args:
        query: Log search query (scope only, e.g., "_sourceCategory=prod/app" or "_view=my_view")
        from_time: Start time (ISO8601, epoch ms, or relative like '-1h', '-24h', '-7d')
        to_time: End time (ISO8601, epoch ms, or relative like 'now')
        time_zone: Timezone for the search (default: UTC)
        by_view: If True, returns breakdown by partition/view (default: True, recommended)

    Time Format Examples:
        - Relative: "-1h", "-24h", "-7d", "-1w", "now"
        - ISO: "2024-01-01T00:00:00Z"
        - Epoch ms: "1704067200000"

    API Reference: https://help.sumologic.com/docs/api/log-search-estimated-usage/
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        # Parse time values to epoch milliseconds
        from_epoch = parse_time_to_epoch(from_time)
        to_epoch = parse_time_to_epoch(to_time)

        # Validate time range
        if from_epoch >= to_epoch:
            raise ValidationError("from_time must be before to_time")

        await limiter.acquire("get_estimated_log_search_usage")
        result = await client.get_estimated_log_search_usage(
            query=query,
            from_time=from_epoch,
            to_time=to_epoch,
            time_zone=time_zone,
            by_view=by_view,
        )

        # Enhance response with formatted information
        if by_view and "estimatedUsageDetails" in result:
            # Calculate total from details
            total_bytes = sum(
                detail.get("estimatedDataToScanInBytes", 0)
                for detail in result.get("estimatedUsageDetails", [])
            )
            result["totalEstimatedDataToScanInBytes"] = total_bytes
            result["formatted_total"] = format_bytes(total_bytes)

            # Format each view's usage
            for detail in result.get("estimatedUsageDetails", []):
                bytes_val = detail.get("estimatedDataToScanInBytes", 0)
                detail["formatted_size"] = format_bytes(bytes_val)
                # Rename empty partition name to "sumologic_default"
                if detail.get("viewName") == "":
                    detail["viewName"] = "sumologic_default"

        elif "estimatedDataToScanInBytes" in result:
            bytes_val = result.get("estimatedDataToScanInBytes", 0)
            result["formatted_size"] = format_bytes(bytes_val)

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_estimated_log_search_usage")


def parse_time_to_epoch(time_value: str) -> int:
    """
    Parse time value and convert to epoch milliseconds.

    Supports:
    - ISO format strings: "2024-01-01T00:00:00Z"
    - Epoch milliseconds: "1704067200000"
    - Relative times: "-1h", "-30m", "-2d", "-1w", "now"
    """
    import re
    from datetime import datetime, timedelta

    time_str = str(time_value).strip()

    # Handle "now"
    if time_str.lower() == "now":
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    # Handle relative time formats like "-1h", "-30m", "-2d", "-1w"
    relative_pattern = r"^([+-]?)(\d+)([smhdw])$"
    match = re.match(relative_pattern, time_str.lower())

    if match:
        sign, amount, unit = match.groups()
        amount = int(amount)

        # Default to negative if no sign specified (going back in time)
        if sign != "+":
            amount = -amount

        # Convert unit to timedelta
        unit_map = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}

        if unit in unit_map:
            delta_kwargs = {unit_map[unit]: amount}
            target_time = datetime.now(timezone.utc) + timedelta(**delta_kwargs)
            return int(target_time.timestamp() * 1000)

    # Try to parse as ISO format
    try:
        for fmt in [
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(time_str, fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

        # If none of the formats worked, try parsing as epoch milliseconds
        return int(float(time_str))

    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid time format: {time_value}. "
            "Supported formats: ISO datetime, epoch milliseconds, or relative time (e.g., '-1h', '-30m', '-2d', 'now')"
        )


def format_bytes(bytes_value: int) -> str:
    """Format bytes value to human-readable format."""
    if bytes_value == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(bytes_value)
    unit_index = 0

    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1

    return f"{value:.2f} {units[unit_index]}"


@mcp.tool()
async def explore_log_metadata(
    scope: str = "*",
    from_time: str = "-15m",
    to_time: str = "now",
    time_zone: str = "UTC",
    metadata_fields: str = "_view,_sourceCategory",
    sort_by: str = "_sourceCategory",
    max_results: int = 1000,
    instance: str = "default",
) -> str:
    """
    Explore log metadata to map source categories to partitions (STEP 2 after analyze_data_volume).

    **When to use this tool:**
    - AFTER you've found source categories using analyze_data_volume (which is FREE)
    - When you need to map source categories to partitions (_view, _index)
    - When you need collector/source/host details for specific logs
    - When building scoped queries and need partition info

    **NOT for initial discovery:** Use analyze_data_volume first (no scan cost).
    This tool incurs scan costs, so use short time ranges (-15m default).

    This tool helps you discover:
    - Which partitions/views (_view, _index) contain your logs
    - Collector and source mapping for metadata
    - Message counts per metadata combination
    - Detailed metadata dimensions after initial discovery

    Important for Flex/Infrequent tier accounts where scan volume affects cost.
    Keep time ranges short (-15m recommended) to minimize scan charges.

    Args:
        scope: Log search scope (e.g., "*", "_sourceCategory=*cloudtrail*", "sqlexception", "_index=sumologic_default")
        from_time: Start time (ISO8601, epoch ms, or relative like '-15m', '-1h', '-24h')
        to_time: End time (ISO8601, epoch ms, or relative like 'now')
        time_zone: Timezone for the search (default: UTC)
        metadata_fields: Comma-separated metadata fields to aggregate by (default: "_view,_sourceCategory")
        sort_by: Field to sort results by (default: "_sourceCategory")
        max_results: Maximum results to return (default: 1000)
        instance: Instance name (default: 'default')

    Common Metadata Fields:
        - _view: Partition name (also accessible as _index)
        - _sourceCategory: Source category assigned to logs
        - _collector: Collector name
        - _source: Source name
        - _sourceHost: Source host
        - _sourceName: Source name (alternative)

    Scope Examples:
        - "*" - All logs (use with caution, short time range recommended)
        - "_sourceCategory=*cloudtrail*" - Any CloudTrail source categories
        - "sqlexception" - Keyword search
        - "_dataTier=infrequent _sourceCategory=*k8s*" - K8s logs in infrequent tier
        - "_index=sumologic_default" - All logs in default partition

    Metadata Field Examples:
        - "_view,_sourceCategory" - Basic partition and category mapping (fast)
        - "_view,_sourceCategory,_collector,_source" - Include collector/source info
        - "_view,_sourceCategory,_collector,_source,_sourceName" - Comprehensive mapping (slower)

    Returns:
        Aggregated metadata with message counts, sorted by specified field.
        Results include total unique combinations found and total messages.

    Notes:
        - Keep time range short (<60m) for large instances or many metadata dimensions
        - Infrequent tier searches incur scan charges - scope queries well
        - More metadata fields = higher cardinality = longer query time
        - Results can be filtered/analyzed client-side after retrieval

    Time Format Examples:
        - Relative: "-15m", "-1h", "-24h", "-7d"
        - ISO: "2024-01-01T00:00:00Z"
        - Epoch ms: "1704067200000"
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Validate and parse metadata fields
        fields = [f.strip() for f in metadata_fields.split(",")]
        if not fields:
            raise ValidationError("At least one metadata field must be specified")

        # Validate sort_by is in fields
        if sort_by not in fields:
            raise ValidationError(
                f"sort_by field '{sort_by}' must be one of the metadata fields: {metadata_fields}"
            )

        # Build the query
        # Format: <scope> | count by field1,field2,... | sort field asc | limit N
        group_by_clause = ", ".join(fields)
        query = f"{scope} | count by {group_by_clause} | sort {sort_by} asc | limit {max_results}"

        # Use the existing search_sumo_logs functionality
        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        # Parse time values
        from_epoch = parse_time_to_epoch(from_time)
        to_epoch = parse_time_to_epoch(to_time)

        # Validate time range
        if from_epoch >= to_epoch:
            raise ValidationError("from_time must be before to_time")

        # Create and wait for search job
        await limiter.acquire("explore_log_metadata")
        logger.info(f"Starting metadata exploration: {query}")

        job_result = await client.create_search_job(
            query=query,
            from_time=from_epoch,
            to_time=to_epoch,
            timezone_str=time_zone,
            by_receipt_time=False,
        )

        search_id = job_result.get("id")
        if not search_id:
            raise APIError(f"No search job ID returned: {job_result}")

        # Poll for completion
        max_wait = 300  # 5 minutes
        poll_interval = 2
        max_attempts = max_wait // poll_interval

        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)
            await limiter.acquire("explore_log_metadata_poll")

            status = await client.get_search_job_status(search_id)
            state = status.get("state", "")

            if state == "DONE GATHERING RESULTS":
                # Get results
                await limiter.acquire("explore_log_metadata_results")
                results = await client.get_search_job_records(
                    job_id=search_id, limit=max_results, offset=0
                )

                # Format response
                records = results.get("records", [])
                total_records = len(records)
                total_messages = sum(
                    int(record.get("map", {}).get("_count", 0)) for record in records
                )

                # Build formatted output
                output = {
                    "scope": scope,
                    "metadata_fields": fields,
                    "time_range": {"from": from_time, "to": to_time, "timezone": time_zone},
                    "summary": {
                        "unique_combinations": total_records,
                        "total_messages": total_messages,
                        "truncated": total_records >= max_results,
                    },
                    "metadata": [],
                }

                # Extract and format metadata
                for record in records:
                    record_map = record.get("map", {})

                    # Debug: log the first record's keys to understand field naming
                    if len(output["metadata"]) == 0 and record_map:
                        logger.debug(f"First record keys: {list(record_map.keys())}")

                    metadata_entry = {"count": int(record_map.get("_count", 0))}

                    # Add each metadata field - handle case insensitivity
                    # Sumo returns fields in lowercase typically
                    for field in fields:
                        # Try exact match first
                        value = record_map.get(field)

                        # If not found, try case-insensitive lookup
                        if value is None:
                            # Create case-insensitive lookup
                            field_lower = field.lower()
                            for key in record_map.keys():
                                if key.lower() == field_lower:
                                    value = record_map.get(key)
                                    break

                        # Default to empty string if still not found
                        if value is None:
                            value = ""

                        # Handle empty partition name
                        if field.lower() in ["_view", "_index"] and value == "":
                            value = "sumologic_default"

                        metadata_entry[field] = value

                    output["metadata"].append(metadata_entry)

                return json.dumps(output, indent=2)

            elif state in ["CANCELLED", "FAILED"]:
                raise APIError(f"Search job {state.lower()}: {status}")

        # Timeout
        raise SumoTimeoutError(f"Metadata exploration timed out after {max_wait} seconds")

    except Exception as e:
        return handle_tool_error(e, "explore_log_metadata")


@mcp.tool()
async def analyze_log_volume(
    scope: str = Field(
        description="Search scope expression (e.g., '_index=prod_app_logs', '_sourceCategory=*cloudtrail*')"
    ),
    aggregate_by: list[str] = Field(
        description="List of fields to aggregate by (e.g., ['_sourceCategory'], ['eventname', 'eventsource'])"
    ),
    from_time: str = "-24h",
    to_time: str = "now",
    additional_fields: Optional[list[str]] = None,
    top_n: int = 100,
    include_percentage: bool = True,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Analyze raw log volume using the _size field to understand ingestion drivers.

    This tool helps optimize Infrequent tier usage and partition scoping by identifying
    high-volume log sources and dimensions. Uses the internal _size field to measure
    actual bytes for log events.

    Use Cases:
    1. Find top volume drivers within a partition by metadata:
       scope="_index=prod_app_logs"
       aggregate_by=["_sourceCategory"]

    2. Analyze CloudTrail volume by event type:
       scope="_sourceCategory=*cloudtrail*"
       aggregate_by=["eventname"]

    3. Multi-dimensional analysis with sampling:
       scope="_sourceCategory=apache-access"
       aggregate_by=["status_code", "vhost"]
       additional_fields=["url"]  # Sample URLs with values() operator

    4. Parse and analyze complex logs:
       scope='_sourceCategory=apache-access | parse "..." as field1, field2'
       aggregate_by=["field1"]

    Parameters:
        scope: Search scope - can include parse/json operators for search-time field extraction
        aggregate_by: One or more fields to aggregate _size by (metadata or custom fields)
        from_time: Start time (relative like '-24h' or ISO8601)
        to_time: End time (relative like 'now' or ISO8601)
        additional_fields: Optional fields to sample values from using values() operator
        top_n: Number of top results to return (default: 100)
        include_percentage: Calculate percentage of total volume (default: True)
        instance: Instance name

    Returns:
        Volume analysis with:
        - bytes: Raw byte count
        - mb/gb/tb: Human-readable sizes
        - percentage: % of total volume (if enabled)
        - Additional sampled field values (if specified)

    Examples:
        # Find what source categories drive volume in a partition
        analyze_log_volume(
            scope="_index=prod_app_logs",
            aggregate_by=["_sourceCategory"]
        )

        # Analyze CloudTrail by eventName and eventSource
        analyze_log_volume(
            scope="_sourceCategory=*cloudtrail*",
            aggregate_by=["eventname", "eventsource"],
            additional_fields=["arn"]  # Sample ARNs
        )

        # Parse Apache logs and analyze by status code
        analyze_log_volume(
            scope='_sourceCategory=apache | parse "* * *" as method, url, status',
            aggregate_by=["status", "method"]
        )

    Reference: https://www.sumologic.com/blog/optimize-value-of-cloudtrail-logs-with-infrequent-tier
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("analyze_log_volume")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Build aggregation clause
        agg_fields = ", ".join(aggregate_by)

        # Build additional fields clause using values() operator
        additional_clause = ""
        if additional_fields:
            values_clauses = [f"values({field}) as {field}_samples" for field in additional_fields]
            additional_clause = ", " + ", ".join(values_clauses)

        # Build query
        query = f"""{scope}
| sum(_size) as bytes{additional_clause} by {agg_fields}
| bytes / 1024 / 1024 as mb
| bytes / 1024 / 1024 / 1024 as gb
| bytes / 1024 / 1024 / 1024 / 1024 as tb
| sort by bytes desc
| limit {top_n}"""

        # Create search job
        job_response = await client.create_search_job(
            query=query, from_time=from_time, to_time=to_time, timezone_str="UTC"
        )

        job_id = job_response["id"]

        # Poll for completion
        max_attempts = 300  # 5 minutes
        for attempt in range(max_attempts):
            await asyncio.sleep(1)

            status = await client.get_search_job_status(job_id)
            state = status["state"]

            if state == "DONE GATHERING RESULTS":
                break
            elif state == "CANCELLED":
                raise APIError("Search job was cancelled")

        # Get records
        records_response = await client.get_search_job_records(job_id, limit=top_n)
        records = records_response.get("records", [])

        # Delete the job
        try:
            await client.delete_search_job(job_id)
        except Exception:  # nosec B110
            pass  # Best effort cleanup - job deletion failure is acceptable

        # Calculate total if percentage requested
        total_bytes = 0
        if include_percentage:
            total_bytes = sum(float(r.get("map", {}).get("bytes", 0)) for r in records)

        # Format results
        result = {
            "query_parameters": {
                "scope": scope,
                "aggregate_by": aggregate_by,
                "from_time": from_time,
                "to_time": to_time,
                "additional_fields": additional_fields,
                "top_n": top_n,
            },
            "summary": {
                "total_records": len(records),
                "total_bytes": int(total_bytes),
                "total_gb": round(total_bytes / 1024 / 1024 / 1024, 2) if total_bytes > 0 else 0,
                "total_tb": (
                    round(total_bytes / 1024 / 1024 / 1024 / 1024, 3) if total_bytes > 0 else 0
                ),
            },
            "results": [],
        }

        for record in records:
            record_map = record.get("map", {})

            result_entry = {}

            # Add aggregation fields
            for field in aggregate_by:
                result_entry[field] = record_map.get(field, "")

            # Add volume metrics
            bytes_val = float(record_map.get("bytes", 0))
            result_entry["bytes"] = int(bytes_val)
            result_entry["mb"] = round(float(record_map.get("mb", 0)), 2)
            result_entry["gb"] = round(float(record_map.get("gb", 0)), 3)
            result_entry["tb"] = round(float(record_map.get("tb", 0)), 4)

            if include_percentage and total_bytes > 0:
                result_entry["percentage"] = round((bytes_val / total_bytes) * 100, 2)

            # Add additional sampled fields
            if additional_fields:
                for field in additional_fields:
                    sample_key = f"{field}_samples"
                    result_entry[sample_key] = record_map.get(sample_key, "")

            result["results"].append(result_entry)

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "analyze_log_volume")


@mcp.tool()
async def profile_log_schema(
    scope: str = Field(
        description="Search scope expression (e.g., '_sourceCategory=*cloudtrail*')"
    ),
    from_time: str = "-1h",
    to_time: str = "now",
    mode: str = "summary",
    min_cardinality: int = 0,
    max_cardinality: int = 1000000,
    suggest_candidates: bool = True,
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Profile log schema using the facets operator to discover available fields and their characteristics.

    This tool helps understand log structure before performing volume analysis. The facets operator
    returns metadata about all fields available in the query scope (built-in fields, indexed fields,
    and search-time fields from auto-json or parse statements).

    Use Cases:
    1. Discover what fields exist in a log type:
       scope="_sourceCategory=*cloudtrail*"
       mode="summary"

    2. Find medium-cardinality fields good for volume breakdown:
       scope="_sourceCategory=*cloudtrail*"
       suggest_candidates=True
       min_cardinality=10
       max_cardinality=1000

    3. Get full facets output with value samples:
       scope="_sourceCategory=apache"
       mode="full"

    Parameters:
        scope: Search scope - can include parse/json operators for search-time fields
        from_time: Start time (shorter ranges recommended for facets)
        to_time: End time
        mode: 'summary' returns just field names/types/cardinalities,
              'full' returns all facets data including value samples
        min_cardinality: Filter to fields with at least this many unique values
        max_cardinality: Filter to fields with at most this many unique values
        suggest_candidates: Automatically identify good fields for volume analysis
                           (medium cardinality: 2-1000 unique values, non-system fields)
        instance: Instance name

    Returns:
        Field schema information:
        - fieldName: Name of the field
        - fieldType: Data type (string, long, int, double, boolean)
        - cardinality: Number of unique values (in summary mode)
        - suggested: Boolean indicating if field is good for volume analysis
        - Full facets data in 'full' mode

    Examples:
        # Discover CloudTrail fields
        profile_log_schema(
            scope="_sourceCategory=*cloudtrail*",
            mode="summary"
        )

        # Find good dimensions for Apache log analysis
        profile_log_schema(
            scope="_sourceCategory=apache",
            min_cardinality=2,
            max_cardinality=500,
            suggest_candidates=True
        )

        # Parse and discover fields from custom logs
        profile_log_schema(
            scope='_sourceCategory=app | parse "level=* user=*" as level, user',
            mode="summary"
        )

    Note: Built-in Sumo Logic fields start with underscore (_sourceCategory, _collector, etc.)
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("profile_log_schema")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Build query based on mode
        if mode == "summary":
            query = f"""{scope}
| facets
| count by _fieldName, _fieldType, _fieldCardinality
| sort by _fieldName asc"""
        else:  # full mode
            query = f"""{scope}
| facets"""

        # Create search job
        job_response = await client.create_search_job(
            query=query, from_time=from_time, to_time=to_time, timezone_str="UTC"
        )

        job_id = job_response["id"]

        # Poll for completion
        max_attempts = 300
        for attempt in range(max_attempts):
            await asyncio.sleep(1)

            status = await client.get_search_job_status(job_id)
            state = status["state"]

            if state == "DONE GATHERING RESULTS":
                break
            elif state == "CANCELLED":
                raise APIError("Search job was cancelled")

        # Get records
        records_response = await client.get_search_job_records(job_id, limit=10000)
        records = records_response.get("records", [])

        # Delete the job
        try:
            await client.delete_search_job(job_id)
        except Exception:  # nosec B110
            pass  # Best effort cleanup - job deletion failure is acceptable

        # Format results based on mode
        result = {
            "query_parameters": {
                "scope": scope,
                "from_time": from_time,
                "to_time": to_time,
                "mode": mode,
                "min_cardinality": min_cardinality,
                "max_cardinality": max_cardinality,
            },
            "summary": {"total_fields": len(records)},
        }

        if mode == "summary":
            fields = []
            suggested_fields = []

            for record in records:
                record_map = record.get("map", {})

                field_name = record_map.get("_fieldname", record_map.get("_fieldName", ""))
                field_type = record_map.get("_fieldtype", record_map.get("_fieldType", ""))
                cardinality = int(
                    record_map.get("_fieldcardinality", record_map.get("_fieldCardinality", 0))
                )

                # Apply cardinality filters
                if cardinality < min_cardinality or cardinality > max_cardinality:
                    continue

                field_info = {
                    "fieldName": field_name,
                    "fieldType": field_type,
                    "cardinality": cardinality,
                }

                # Determine if this is a good candidate for volume analysis
                is_suggested = False
                if suggest_candidates:
                    # Good candidates: medium cardinality (2-1000), not system fields
                    # System fields start with _ (except a few exceptions like _raw which we want to exclude)
                    is_system_field = field_name.startswith("_")
                    if not is_system_field and 2 <= cardinality <= 1000:
                        is_suggested = True
                        suggested_fields.append(field_name)

                field_info["suggested_for_analysis"] = is_suggested

                fields.append(field_info)

            result["fields"] = fields
            result["summary"]["filtered_fields"] = len(fields)

            if suggest_candidates:
                result["suggested_analysis_fields"] = suggested_fields
                result["suggestion_rationale"] = (
                    "Suggested fields have medium cardinality (2-1000 unique values) "
                    "and are non-system fields, making them good candidates for _size aggregation analysis."
                )

        else:  # full mode
            result["facets"] = []
            for record in records:
                result["facets"].append(record.get("map", {}))

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "profile_log_schema")


@mcp.tool()
async def analyze_data_volume(
    dimension: str = "sourceCategory",
    from_time: str = "-3h",
    to_time: str = "now",
    time_zone: str = "UTC",
    include_credits: bool = True,
    include_timeshift: bool = False,
    timeshift_days: int = 7,
    timeshift_periods: int = 3,
    sort_by: str = "gbytes",
    limit: int = 100,
    filter_pattern: str = "*",
    instance: str = "default",
) -> str:
    """
    🔍 DISCOVER LOGS by keyword - FREE (no scan cost). Use this FIRST when you don't know where logs are.

    This is the fastest way to find source categories when metadata is unknown. Also used for
    capacity planning, cost analysis, and identifying stopped/new data sources.

    **PRIMARY USE CASE - Log Discovery:**
    Find logs by keyword (e.g., "cloudtrail", "nginx", "kubernetes") with zero scan cost.
    Returns matching source categories with data tier info (Continuous/Infrequent/Flex/CSE).

    Example: filter_pattern="*cloudtrail*" finds aws/cloudtrail, prod/cloudtrail/audit, etc.

    **Discovery Workflow:**
    1. Start with this tool: filter_pattern="*keyword*", from_time="-3h", include_credits=False
    2. If no results: retry with from_time="-24h" or "-7d" (low-volume logs)
    3. Next step: Use explore_log_metadata with found source categories for partition mapping

    Args:
        dimension: Metadata dimension to analyze (default: "sourceCategory")
            - "sourceCategory": Volume by source category (most common for discovery)
            - "collector": Volume by collector
            - "source": Volume by source
            - "sourceHost": Volume by source host
            - "sourceName": Volume by source name
            - "view": Volume by partition/view
        from_time: Start time (default '-3h' for fast discovery, use '-24h' or '-7d' for trends/history)
        to_time: End time (default: 'now')
        time_zone: Timezone (default: 'UTC')
        include_credits: Calculate credits (default: True, set False for discovery)
        include_timeshift: Compare with previous periods (default: False)
        timeshift_days: Days to shift back for comparison (default: 7)
        timeshift_periods: Number of periods to average (default: 3)
        sort_by: Field to sort by (default: 'gbytes', options: 'gbytes', 'events', 'credits')
        limit: Maximum results to return (default: 100)
        filter_pattern: Filter pattern for dimension values (default: '*')
            - Accepts glob patterns (e.g., '*cloudtrail*', '*nginx*', 'aws/*')
            - Wildcards (*) are auto-converted to regex (.*)
            - All matching is case-insensitive (CloudTrail = cloudtrail = CLOUDTRAIL)
            - Advanced: provide regex directly (e.g., '.*trail.*', '^aws/.*', '(prod|dev).*')
        instance: Instance name (default: 'default')

    Returns:
        JSON with aggregated data including:
        - Dimension value (sourceCategory, collector, etc.)
        - Data tier (Continuous, Frequent, Infrequent, CSE, Flex) - critical for cost planning
        - Events count
        - GB ingested
        - Credits consumed (if include_credits=True)
        - Percentage change vs baseline (if include_timeshift=True)
        - State flags: NEW, GONE, COLLECTING (if include_timeshift=True)

    Credit Rates (Standard Tiered):
        - Continuous: 20 credits/GB
        - Frequent: 9 credits/GB
        - Infrequent: 0.4 credits/GB
        - CSE: 25 credits/GB
        Note: Flex customers use different rates

    Use Cases (in priority order):
        - 🔍 LOG DISCOVERY: Find source categories by keyword (FREE - no scan cost)
        - Top consumers: Find which source categories use most ingestion
        - Trend analysis: Detect increases/decreases with timeshift comparison
        - Stopped collection: Identify collectors that stopped sending data
        - New sources: Find newly added data sources
        - Cost analysis: Calculate credits consumed per dimension

    Time Format Examples:
        - Relative: "-1h", "-24h", "-7d", "-30d"
        - ISO: "2024-01-01T00:00:00Z"
        - Epoch ms: "1704067200000"

    Example Queries Generated:
        Basic: Bytes and events by sourceCategory
        With credits: Adds credit calculation
        With timeshift: Compares current vs 21d average (3 x 7d)
    """
    try:
        from .query_patterns import AggregationPatterns, CreditCalculation, TimeshiftPattern

        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Map dimension to source category
        dimension_map = {
            "sourceCategory": "sourcecategory_and_tier_volume",
            "collector": "collector_and_tier_volume",
            "source": "source_and_tier_volume",
            "sourceHost": "sourcehost_and_tier_volume",
            "sourceName": "sourcename_and_tier_volume",
            "view": "view_and_tier_volume",
        }

        if dimension not in dimension_map:
            raise ValidationError(
                f"Invalid dimension '{dimension}'. "
                f"Valid options: {', '.join(dimension_map.keys())}"
            )

        source_category = dimension_map[dimension]

        # Map dimension to field name in parsed data
        field_map = {
            "sourceCategory": "sourceCategory",
            "collector": "collector",
            "source": "source",
            "sourceHost": "sourceHost",
            "sourceName": "sourceName",
            "view": "view",
        }
        field_name = field_map[dimension]

        # Build the query
        query_parts = [
            f"_index=sumologic_volume _sourceCategory={source_category}",
            '| parse regex "(?<data>\\{[^\\{]+\\})" multi',
            f'| json field=data "field","dataTier","sizeInBytes","count" as {field_name}, dataTier, bytes, events',
            "| bytes/1Gi as gbytes",
        ]

        # Add filter if specified (convert glob pattern to case-insensitive regex)
        if filter_pattern != "*":
            # Convert glob wildcard * to regex .* (if present)
            # If user provided glob pattern like *cloudtrail*, convert to .*cloudtrail.*
            regex_pattern = filter_pattern.replace("*", ".*")
            # Use case-insensitive regex with /(?i)pattern/ syntax
            query_parts.append(f"| where {field_name} matches /(?i){regex_pattern}/")

        # Aggregation
        query_parts.append(AggregationPatterns.volume_by_dimension(field_name, include_tier=True))

        # Add credits calculation if requested
        if include_credits:
            query_parts.extend(CreditCalculation.add_credit_calculation())

        # Add timeshift comparison if requested
        if include_timeshift:
            # Add timeshift for gbytes (includes compare operator and state field)
            query_parts.extend(
                TimeshiftPattern.compare_with_timeshift(
                    "gbytes", timeshift_days, timeshift_periods, include_state=True
                )
            )

            # Add timeshift for credits if requested (no compare operator, no state field)
            if include_credits:
                query_parts.extend(
                    TimeshiftPattern.compare_with_timeshift(
                        "credits", timeshift_days, timeshift_periods, include_state=False
                    )
                )

        # Sorting
        query_parts.append(AggregationPatterns.top_n(sort_by, limit=limit, direction="desc"))

        query = "\n".join(query_parts)

        # Execute the query
        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        # Parse time values
        from_epoch = parse_time_to_epoch(from_time)
        to_epoch = parse_time_to_epoch(to_time)

        if from_epoch >= to_epoch:
            raise ValidationError("from_time must be before to_time")

        await limiter.acquire("analyze_data_volume")
        logger.info(f"Starting data volume analysis for dimension: {dimension}")

        # Use search_logs to execute the query
        results = await client.search_logs(
            query=query,
            from_time=str(from_epoch),
            to_time=str(to_epoch),
            timezone_str=time_zone,
            by_receipt_time=False,
        )

        # Format the response
        records = results.get("results", [])

        # Check if no data was found
        if not records:
            return json.dumps(
                {
                    "dimension": dimension,
                    "time_range": {"from": from_time, "to": to_time, "timezone": time_zone},
                    "query_options": {
                        "include_credits": include_credits,
                        "include_timeshift": include_timeshift,
                        "filter_pattern": filter_pattern,
                        "sort_by": sort_by,
                        "limit": limit,
                    },
                    "summary": {
                        "total_records": 0,
                        "message": "No data found in data volume index for the specified time range and filters",
                    },
                    "data": [],
                    "query": query,  # Include the actual query for debugging
                    "recommendations": [
                        "Try a longer time range (e.g., from_time='-7d' or '-30d')",
                        "Verify data is being ingested into this Sumo Logic instance",
                        "Check if this is a production instance with active data collection",
                        "Try removing filter_pattern (use '*') to see all source categories",
                    ],
                },
                indent=2,
            )

        output = {
            "dimension": dimension,
            "time_range": {"from": from_time, "to": to_time, "timezone": time_zone},
            "query_options": {
                "include_credits": include_credits,
                "include_timeshift": include_timeshift,
                "timeshift_config": (
                    {
                        "days": timeshift_days,
                        "periods": timeshift_periods,
                        "total_days": timeshift_days * timeshift_periods,
                    }
                    if include_timeshift
                    else None
                ),
                "sort_by": sort_by,
                "limit": limit,
                "filter_pattern": filter_pattern,
            },
            "summary": {
                "total_records": len(records),
                "query_type": results.get("query_type", "records"),
            },
            "data": [],
        }

        # Extract data from records
        for record in records:
            record_map = record.get("map", {})
            data_entry = {}

            # Extract all fields with case-insensitive matching
            for key, value in record_map.items():
                # Skip internal fields
                if key.startswith("_"):
                    continue
                data_entry[key] = value

            output["data"].append(data_entry)

        return json.dumps(output, indent=2)

    except Exception as e:
        return handle_tool_error(e, "analyze_data_volume")


@mcp.tool()
async def analyze_data_volume_grouped(
    dimension: str = "sourceCategory",
    from_time: str = "-24h",
    to_time: str = "now",
    time_zone: str = "UTC",
    value_filter: str = "*",
    tier_filter: str = "*",
    max_chars: int = 40,
    other_threshold_pct: float = 0.1,
    sort_by: str = "credits",
    limit: int = 100,
    instance: str = "default",
) -> str:
    """
    Advanced data volume analysis with cardinality reduction for large-scale environments.

    This tool is designed for very large Sumo Logic deployments with high cardinality
    (e.g., 5000+ source categories). It reduces cardinality by:
    1. Truncating long dimension values to max_chars
    2. Rolling up small contributors (<other_threshold_pct) into "other"

    This enables effective high-level reporting to understand major drivers of
    credits and GB changes without being overwhelmed by thousands of small sources.

    Args:
        dimension: Metadata dimension to analyze (default: "sourceCategory")
            - "sourceCategory": Volume by source category (most common)
            - "collector": Volume by collector
            - "source": Volume by source
            - "sourceHost": Volume by source host
            - "sourceName": Volume by source name
            - "view": Volume by partition/view
        from_time: Start time (ISO8601, epoch ms, or relative like '-24h', '-7d')
        to_time: End time (default: 'now')
        time_zone: Timezone (default: 'UTC')
        value_filter: Filter pattern for dimension values (default: '*', e.g., '*prod*')
        tier_filter: Data tier filter (default: '*', options: 'Continuous', 'Frequent', 'Infrequent', 'CSE', 'Flex')
        max_chars: Maximum characters for dimension values (default: 40, longer values truncated with '...')
        other_threshold_pct: Percentage threshold for "other" grouping (default: 0.1 = 0.1%)
        sort_by: Field to sort by (default: 'credits', options: 'credits', 'gbytes', 'events')
        limit: Maximum results to return (default: 100)
        instance: Instance name (default: 'default')

    Returns:
        JSON with aggregated ingestion data including:
        - Dimension value (truncated if > max_chars)
        - Data tier
        - Categories count (number of original values rolled into this entry)
        - Events count
        - GB ingested
        - Credits consumed
        - Percentage of total GB (pct_GB)
        - Percentage of total credits (pct_cr)
        - Credits per GB ratio (cr/gb)

    Cardinality Reduction Features:
        1. **Value truncation**: Long values shortened to max_chars with "..." suffix
           Example: "kubernetes/prod/very/long/path/to/service" -> "kubernetes/prod/very/long/path/to/se..."

        2. **Small value rollup**: Values contributing < other_threshold_pct are grouped as "other"
           - Default 0.1% means anything < 0.1% of total GB is rolled into "other"
           - Shows total categories count for rolled-up values
           - Enables focus on major contributors

    Credit Rates:
        - Continuous/Flex: 20 credits/GB
        - Frequent: 9 credits/GB
        - Infrequent: 0.4 credits/GB
        - CSE: 25 credits/GB

    Use Cases:
        - **High-cardinality environments**: Analyze 5000+ source categories effectively
        - **Executive reporting**: Focus on top contributors, hide noise
        - **Cost optimization**: Identify major credit drivers
        - **Trend analysis**: Compare period-over-period for top sources
        - **Tier analysis**: Filter by specific data tiers (Infrequent, Flex, etc.)

    Example Scenarios:
        1. **Top Flex tier consumers (> 1% each):**
           ```
           tier_filter="Flex", other_threshold_pct=1.0, sort_by="credits"
           ```

        2. **Infrequent tier analysis with short names:**
           ```
           tier_filter="Infrequent", max_chars=30, other_threshold_pct=0.5
           ```

        3. **Production source categories only:**
           ```
           value_filter="*prod*", other_threshold_pct=0.2
           ```

    Notes:
        - Large accounts with 1000s of values benefit most from this tool
        - The "other" category shows count of rolled-up sources in categories field
        - Adjust other_threshold_pct based on your environment (0.1% to 1% typical)
        - Uses parse regex for better performance than json operator
        - Results sorted by credits (descending) by default to show top cost drivers

    Time Format Examples:
        - Relative: "-1h", "-24h", "-7d", "-30d"
        - ISO: "2024-01-01T00:00:00Z"
        - Epoch ms: "1704067200000"

    API Reference: https://help.sumologic.com/docs/manage/ingestion-volume/data-volume-index/
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Map dimension to source category
        dimension_map = {
            "sourceCategory": "sourcecategory",
            "collector": "collector",
            "source": "source",
            "sourceHost": "sourcehost",
            "sourceName": "sourcename",
            "view": "view",
        }

        if dimension not in dimension_map:
            raise ValidationError(
                f"Invalid dimension '{dimension}'. "
                f"Valid options: {', '.join(dimension_map.keys())}"
            )

        dimension_lower = dimension_map[dimension]

        # Build the advanced query with parameter substitution
        query = f"""(_index=sumologic_volume) _sourceCategory={dimension_lower}_and_tier_volume
| parse regex "\\{{\\"field\\":\\"(?<value>[^\\"]+)\\",\\"dataTier\\":\\"(?<dataTier>[^\\"]+)\\",\\"sizeInBytes\\":(?<sizeInBytes>[^\\"]+),\\"count\\":(?<count>[^\\"]+)\\}}" multi
| where tolowercase(value) matches tolowercase("{value_filter}")
| where dataTier matches "{tier_filter}"
| sum(count) as events,sum(sizeInBytes) as bytes by dataTier, value,_sourceCategory
| bytes /1024/1024/1024 as gb | sort gb
| parse field=_sourceCategory "*_and_tier_volume" as dimension
| fields -_sourceCategory,bytes
| if (length(value) > {max_chars},concat(substring(value,0,{max_chars}),"..."),value) as value
| count as categories,sum(events) as events,sum(gb) as gbytes by dimension,value,dataTier
| total gbytes as tgb
| total gbytes as tgbs by value,dataTier
| tgbs / tgb as fraction
| if(( fraction * 100 ) > {other_threshold_pct},value,"other" ) as value
| fraction * 100 as percent
| if (dataTier="Frequent",gbytes * 9,gbytes * 20) as credits
| if (dataTier="Infrequent",gbytes * 0.4,credits) as credits
| if (dataTier="CSE",gbytes * 25,credits) as credits
| sum(categories) as categories, sum(credits) as credits, sum(events) as events,sum(gbytes) as gbytes, sum(percent) as pct_GB by dataTier,dimension,value
| credits/gbytes as %"cr/gb"
| sort {sort_by} desc
| total credits as tc | 100 * (credits/tc) as pct_cr | fields -tc
| limit {limit}"""

        # Execute the query
        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        # Parse time values
        from_epoch = parse_time_to_epoch(from_time)
        to_epoch = parse_time_to_epoch(to_time)

        if from_epoch >= to_epoch:
            raise ValidationError("from_time must be before to_time")

        await limiter.acquire("analyze_data_volume_grouped")
        logger.info(f"Starting grouped data volume analysis for dimension: {dimension}")

        # Use search_logs to execute the query
        results = await client.search_logs(
            query=query,
            from_time=str(from_epoch),
            to_time=str(to_epoch),
            timezone_str=time_zone,
            by_receipt_time=False,
        )

        # Format the response
        records = results.get("results", [])

        output = {
            "dimension": dimension,
            "time_range": {"from": from_time, "to": to_time, "timezone": time_zone},
            "query_options": {
                "value_filter": value_filter,
                "tier_filter": tier_filter,
                "max_chars": max_chars,
                "other_threshold_pct": other_threshold_pct,
                "sort_by": sort_by,
                "limit": limit,
            },
            "summary": {
                "total_records": len(records),
                "query_type": results.get("query_type", "records"),
                "note": f"Values < {other_threshold_pct:.1f}% of total GB are grouped as 'other'",
            },
            "data": [],
        }

        # Extract data from records
        for record in records:
            record_map = record.get("map", {})
            data_entry = {}

            # Extract all fields
            for key, value in record_map.items():
                # Skip internal fields
                if key.startswith("_"):
                    continue
                data_entry[key] = value

            output["data"].append(data_entry)

        return json.dumps(output, indent=2)

    except Exception as e:
        return handle_tool_error(e, "analyze_data_volume_grouped")


# MCP Resources


@mcp.resource("sumo://logs/recent-errors")
async def recent_errors() -> str:
    """Get recent error logs from the last hour from default instance."""
    try:
        client = await get_sumo_client("default")

        to_time = datetime.now(timezone.utc)
        from_time = to_time - timedelta(hours=1)

        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.search_logs("error OR ERROR OR Error", from_str, to_str)
        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "recent_errors")


@mcp.resource("sumo://config/collectors")
async def collectors_config() -> str:
    """Get current collector configuration from default instance."""
    try:
        client = await get_sumo_client("default")
        collectors = await client.get_collectors()
        return json.dumps(collectors, indent=2)
    except Exception as e:
        return handle_tool_error(e, "collectors_config")


@mcp.resource("sumo://query-examples")
async def query_examples() -> str:
    """
    Browse sample Sumo Logic query examples from published apps.

    This resource returns a sample of 20 diverse query examples to get started.
    For more targeted searching with filters (app name, use case, keywords, etc.),
    use the search_query_examples tool instead.

    The tool allows filtering by:
    - Application name (Windows, AWS, Kubernetes, etc.)
    - Use case keywords (security, performance, traffic, etc.)
    - Query text keywords (count, timeslice, error, etc.)
    - Query type (Logs or Metrics)
    """
    try:
        from pathlib import Path

        # Load query examples from repo
        query_db_path = Path(__file__).parent.parent.parent / "logs_searches.json"
        query_db_path_gz = Path(__file__).parent.parent.parent / "logs_searches.json.gz"

        # Auto-decompress if only .gz exists
        if not query_db_path.exists() and query_db_path_gz.exists():
            import gzip
            import shutil

            with gzip.open(query_db_path_gz, "rb") as f_in:
                with open(query_db_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info(f"Decompressed {query_db_path_gz} to {query_db_path}")

        if not query_db_path.exists():
            return json.dumps(
                {
                    "error": "Query examples database not found",
                    "expected_path": str(query_db_path),
                    "suggestion": "Ensure logs_searches.json or logs_searches.json.gz is in the repo root directory",
                },
                indent=2,
            )

        # Load and return a sample
        with open(query_db_path) as f:
            all_queries = json.load(f)

        # Get a diverse sample - take every Nth query to get variety
        sample_size = 20
        step = max(1, len(all_queries) // sample_size)
        sample = all_queries[::step][:sample_size]

        # Get list of unique apps for reference
        all_apps = sorted({q.get("app", "") for q in all_queries if q.get("app")})

        return json.dumps(
            {
                "info": "This is a sample of query examples. Use search_query_examples tool for filtered searches.",
                "total_available": len(all_queries),
                "sample_size": len(sample),
                "available_apps": all_apps[:50],  # First 50 apps
                "total_apps": len(all_apps),
                "examples": sample,
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "error": str(e),
                "suggestion": "Use the search_query_examples tool for searching examples",
            },
            indent=2,
        )


# Query Examples Tool (companion to resource above)


@mcp.tool()
async def search_query_examples(
    query: Optional[str] = Field(
        default=None,
        description="Free-text search across all fields (app name, use case, query name, query text). Best for natural queries like 'apache 4xx errors' or 'kubernetes pod scheduling'",
    ),
    app_name: Optional[str] = Field(
        default=None,
        description="Narrow to specific app (e.g., 'Apache', 'AWS', 'Kubernetes'). Also matches 'httpd', 'k8s' aliases",
    ),
    use_case: Optional[str] = Field(
        default=None,
        description="Narrow to use case (e.g., 'security', 'performance', 'latency', 'error')",
    ),
    keywords: Optional[str] = Field(
        default=None,
        description="Search query text for operators/patterns (e.g., 'count by', 'timeslice', 'where status_code')",
    ),
    query_type: Optional[str] = Field(
        default=None, description="Filter by type: 'Logs' or 'Metrics'"
    ),
    match_mode: str = Field(
        default="any",
        description="Match mode: 'any' (score by relevance, default), 'all' (strict AND), 'fuzzy' (relaxed matching)",
    ),
    max_results: int = Field(default=10, description="Maximum number of examples to return (1-50)"),
) -> str:
    """
    Search 11,000+ real Sumo Logic queries from published apps using intelligent scoring.

    **Best Practice:** Use the `query` parameter for natural language searches. It searches across
    app names, use cases, query names, and query text simultaneously, returning results ranked by relevance.

    **Match Modes:**
    - "any" (default): Scores results by how many filters match. More matches = higher ranking.
    - "all": Strict AND - all specified filters must match (may return zero results)
    - "fuzzy": Relaxed matching with auto-fallback if no results found

    **Search Examples:**
    - Natural search: query="apache 4xx errors by server"
    - App-specific: query="kubernetes unschedulable pods"
    - Pattern search: query="count by timeslice" + query_type="Logs"
    - Combined: app_name="AWS", keywords="CloudTrail", use_case="security"

    **Automatic Features:**
    - Tokenizes multi-word searches ("status code 500" → searches "status", "code", "500")
    - Alias matching (k8s→Kubernetes, httpd→Apache, latency→response time)
    - Auto-fallback with relaxation when zero results found
    - Returns relevance scores showing why each result matched

    Returns ranked results with match metadata showing which fields matched.
    """
    try:
        import re
        from pathlib import Path

        # Validate max_results
        max_results = max(1, min(max_results, 50))

        # Load query examples from repo
        query_db_path = Path(__file__).parent.parent.parent / "logs_searches.json"
        query_db_path_gz = Path(__file__).parent.parent.parent / "logs_searches.json.gz"

        # Auto-decompress if only .gz exists
        if not query_db_path.exists() and query_db_path_gz.exists():
            import gzip
            import shutil

            with gzip.open(query_db_path_gz, "rb") as f_in:
                with open(query_db_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info(f"Decompressed {query_db_path_gz} to {query_db_path}")

        if not query_db_path.exists():
            return json.dumps(
                {
                    "error": "Query examples database not found",
                    "expected_path": str(query_db_path),
                    "suggestion": "Ensure logs_searches.json or logs_searches.json.gz is in the repo root directory",
                },
                indent=2,
            )

        # Load queries
        with open(query_db_path) as f:
            all_queries = json.load(f)

        # Technology/app aliases
        aliases = {
            "k8s": "kubernetes",
            "httpd": "apache",
            "apache2": "apache",
            "eks": "kubernetes",
            "gke": "kubernetes",
            "aks": "kubernetes",
            "ec2": "aws",
            "s3": "aws",
            "lambda": "aws",
            "vm": "azure",
            "latency": "response time",
            "timetaken": "response time",
        }

        # Helper: expand aliases
        def expand_aliases(text):
            if not text or not isinstance(text, str):
                return text
            text_lower = text.lower()
            for alias, canonical in aliases.items():
                if alias in text_lower:
                    text_lower = text_lower.replace(alias, canonical)
            return text_lower

        # Helper: tokenize search terms
        def tokenize(text):
            if not text or not isinstance(text, str):
                return []
            # Split on whitespace and common separators, filter empty
            tokens = re.split(r"[\s,;|]+", text.lower())
            return [t for t in tokens if t and len(t) > 1]

        # Score a query against search criteria
        def score_query(q):
            score = 0
            matched_fields = []

            # Free-text query searches everything
            if query and isinstance(query, str):
                query_tokens = tokenize(expand_aliases(query))
                for token in query_tokens:
                    # Search in app name
                    if token in expand_aliases(q.get("app", "")):
                        score += 3
                        matched_fields.append(f"app:{token}")
                    # Search in use case
                    if token in expand_aliases(q.get("use_case", "")):
                        score += 2
                        matched_fields.append(f"use_case:{token}")
                    # Search in search name
                    if token in expand_aliases(q.get("search_name", "")):
                        score += 2
                        matched_fields.append(f"name:{token}")
                    # Search in query text
                    if token in expand_aliases(q.get("search", "")):
                        score += 1
                        matched_fields.append(f"query:{token}")

            # App name filter (with aliases)
            if app_name and isinstance(app_name, str):
                expanded_app = expand_aliases(app_name)
                if expanded_app in expand_aliases(q.get("app", "")):
                    score += 5
                    matched_fields.append("app_filter")

            # Use case filter
            if use_case and isinstance(use_case, str):
                use_case_tokens = tokenize(use_case)
                for token in use_case_tokens:
                    if token in q.get("use_case", "").lower():
                        score += 3
                        matched_fields.append(f"use_case_filter:{token}")

            # Keywords - tokenized search in query text
            if keywords and isinstance(keywords, str):
                keyword_tokens = tokenize(keywords)
                query_text = q.get("search", "").lower()
                for token in keyword_tokens:
                    if token in query_text:
                        score += 2
                        matched_fields.append(f"keyword:{token}")

            # Query type - exact match
            if query_type and isinstance(query_type, str):
                if query_type.lower() == q.get("type", "").lower():
                    score += 1
                    matched_fields.append(f"type:{query_type}")

            return score, matched_fields

        # Score all queries
        scored_results = []
        for q in all_queries:
            score, matched_fields = score_query(q)
            if score > 0:  # Only include if any match
                result = q.copy()
                result["_score"] = score
                result["_matched_on"] = matched_fields
                scored_results.append(result)

        # Handle match modes
        original_count = len(scored_results)
        relaxed_filters = []

        # Ensure match_mode is a string
        match_mode_str = str(match_mode) if match_mode and isinstance(match_mode, str) else "any"

        if match_mode_str == "all":
            # Strict AND - only keep results that matched all specified filters
            filter_count = sum(
                [
                    1 if query and isinstance(query, str) else 0,
                    1 if app_name and isinstance(app_name, str) else 0,
                    1 if use_case and isinstance(use_case, str) else 0,
                    1 if keywords and isinstance(keywords, str) else 0,
                    1 if query_type and isinstance(query_type, str) else 0,
                ]
            )
            if filter_count > 0:
                scored_results = [
                    r for r in scored_results if len(set(r["_matched_on"])) >= filter_count
                ]

        elif match_mode_str == "fuzzy" and len(scored_results) == 0:
            # Auto-fallback: relax most restrictive filter
            if keywords:
                relaxed_filters.append("keywords")
                # Retry without keywords
                scored_results_retry = []
                for q in all_queries:
                    score_retry = 0
                    matched_retry = []
                    # Re-score without keywords
                    if query and isinstance(query, str):
                        query_tokens = tokenize(expand_aliases(query))
                        for token in query_tokens:
                            if token in expand_aliases(q.get("app", "")):
                                score_retry += 3
                                matched_retry.append(f"app:{token}")
                    if app_name and isinstance(app_name, str):
                        if expand_aliases(app_name) in expand_aliases(q.get("app", "")):
                            score_retry += 5
                            matched_retry.append("app_filter")
                    if score_retry > 0:
                        result = q.copy()
                        result["_score"] = score_retry
                        result["_matched_on"] = matched_retry
                        scored_results_retry.append(result)
                scored_results = scored_results_retry

        # Sort by score descending
        scored_results.sort(key=lambda x: x["_score"], reverse=True)

        # Limit results
        results = scored_results[:max_results]

        # Convert params to strings for JSON serialization
        def to_str(val):
            return str(val) if val and isinstance(val, str) else None

        response = {
            "summary": {
                "total_database_size": len(all_queries),
                "matches_found": original_count,
                "returned": len(results),
                "match_mode": match_mode_str,
                "search_params": {
                    "query": to_str(query),
                    "app_name": to_str(app_name),
                    "use_case": to_str(use_case),
                    "keywords": to_str(keywords),
                    "query_type": to_str(query_type),
                },
            },
            "results": results,
        }

        # Add relaxation info if fallback occurred
        if relaxed_filters:
            response["summary"]["relaxed_filters"] = relaxed_filters
            response["summary"][
                "note"
            ] = f"Zero results found. Automatically relaxed filters: {', '.join(relaxed_filters)}"

        # Add helpful suggestions if no results
        if len(scored_results) == 0:
            response["suggestion"] = "No matches found. Try:"
            response["suggestions"] = [
                "Use broader search terms in 'query' parameter",
                "Try match_mode='fuzzy' for auto-fallback",
                "Search by app name only first to see what's available",
                "Use query_type='Logs' or 'Metrics' to narrow by type",
            ]
            # Get sample app names
            sample_apps = sorted({q.get("app", "") for q in all_queries if q.get("app")})[:20]
            response["available_apps_sample"] = sample_apps

        return json.dumps(response, indent=2)

    except Exception as e:
        logger.error(f"Error searching query examples: {str(e)}")
        return json.dumps({"error": str(e)}, indent=2)


# MCP Prompts (keeping original prompts)


@mcp.prompt()
async def analyze_logs_prompt(
    error_type: str = Field(description="Type of error to analyze"),
) -> str:
    """Generate a prompt for analyzing specific types of logs in Sumo Logic."""
    return f"""
You are an expert at analyzing {error_type} logs in Sumo Logic.

To help diagnose issues, please:

1. Search for {error_type}-related errors in the last 24 hours using the search_sumo_logs tool
2. Look for patterns in the error messages, timestamps, and affected hosts
3. Identify the most common error messages and their frequency
4. Check if errors correlate with specific time periods or hosts
5. Provide recommendations for investigation or resolution

Use queries like:
- {error_type} AND (error OR ERROR OR exception OR failed)
- _sourceCategory=*{error_type}* | where level="ERROR"
- {error_type} | timeslice 1h | count by _timeslice, _sourceHost

Analyze the results and provide insights about:
- Error frequency and trends
- Affected systems or components
- Potential root causes
- Recommended next steps for investigation
"""


@mcp.prompt()
async def performance_analysis_prompt() -> str:
    """Generate a prompt for performance analysis using Sumo Logic."""
    return """
You are a performance analysis expert using Sumo Logic data.

To analyze system performance, please:

1. Query recent metrics for key performance indicators:
   - CPU utilization: query_sumo_metrics with "metric=CPU_User | avg by host"
   - Memory usage: query_sumo_metrics with "metric=Memory_Used | avg by host"
   - Disk usage: query_sumo_metrics with "metric=Disk_Used_Percent | avg by host"

2. Search for performance-related log entries:
   - search_sumo_logs with "slow OR timeout OR performance OR latency"
   - search_sumo_logs with "response_time > 1000 OR duration > 5000"

3. Analyze the data to identify:
   - Hosts with high resource utilization
   - Performance trends over time
   - Correlation between metrics and log events
   - Potential bottlenecks or issues

4. Provide recommendations for:
   - Systems that need attention
   - Performance optimization opportunities
   - Monitoring improvements
   - Capacity planning considerations

Present your findings in a clear, actionable format.
"""


# ============================================================================
# Audit Index Search Tools
# ============================================================================


@mcp.tool()
async def search_legacy_audit(
    action: Optional[str] = Field(
        default=None, description="Action filter (e.g., 'login', 'create', 'update')"
    ),
    status: Optional[str] = Field(
        default=None, description="Status filter (e.g., 'SUCCESS', 'FAILURE')"
    ),
    source_category: Optional[str] = Field(
        default=None,
        description="Source category filter (e.g., 'user_activity', 'scheduled_search')",
    ),
    keywords: Optional[str] = Field(default=None, description="Additional keyword search terms"),
    use_case: Optional[str] = Field(
        default=None,
        description="Pre-built use case: 'logins', 'scheduled_search_triggers', 'user_activity', 'content_changes'",
    ),
    aggregate_by: Optional[str] = Field(
        default=None, description="Comma-separated fields to aggregate by (e.g., 'action,status')"
    ),
    hours_back: int = Field(
        default=24,
        description="Number of hours to search back from now (ignored if from_time/to_time provided)",
    ),
    from_time: Optional[str] = Field(
        default=None, description="Start time: ISO8601, epoch ms, or relative like '-1h'"
    ),
    to_time: Optional[str] = Field(
        default=None, description="End time: ISO8601, epoch ms, or relative like 'now'"
    ),
    limit: int = Field(default=100, description="Maximum number of results to return"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Search the legacy Sumo Logic audit index (_index=sumologic_audit).

    **IMPORTANT - Terminology Clarification:**
    This tool searches the audit EVENT index (user actions, logins, system events).
    For analyzing SEARCH QUERY usage/performance, use run_search_audit_query or analyze_search_scan_cost.

    The legacy audit index contains audit events in unstructured text format with varying
    structures depending on event type. This tool helps construct queries for common use cases.

    **Use Cases:**
    - User authentication: action="login", source_category="user_activity"
    - Scheduled search alerts: keywords="triggered", source_category="scheduled_search"
    - Content changes: source_category="content"
    - General user activity: source_category="user_activity"

    **Pre-built Use Cases:**
    Set use_case parameter to one of:
    - "logins": User login events
    - "scheduled_search_triggers": Scheduled search alert triggers
    - "user_activity": General user activity
    - "content_changes": Content creation/modification/deletion

    **Example Events:**
    - Login: "User rjury@sumologic.com successfully logged in via SAML"
    - Alert: "Scheduled search alert triggered [Name=...] [SchSearchId=...][AlertType=...]"

    **Parameters:**
    - action: Filter by action keyword (login, create, update, delete)
    - status: Filter by status (SUCCESS, FAILURE)
    - source_category: Filter by _sourceCategory (user_activity, scheduled_search, content)
    - keywords: Additional keyword search terms
    - use_case: Use a pre-built query pattern
    - aggregate_by: Fields to group by (adds '| count by' operator)
    - limit: Maximum results (default 100)

    **Returns:**
    JSON with query results. If aggregate_by is specified, returns aggregated counts.
    Otherwise returns raw log events (limited by limit parameter).

    **API Reference:**
    https://www.sumologic.com/help/docs/manage/security/audit-indexes/audit-index/
    """
    try:
        from .audit_helpers import build_legacy_audit_query, get_audit_use_case_query

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("search_legacy_audit")

        instance = validate_instance_name(instance)

        # Handle pre-built use case
        if use_case:
            use_case_info = get_audit_use_case_query(use_case)
            if not use_case_info:
                from .audit_helpers import list_audit_use_cases

                available = list_audit_use_cases()
                return json.dumps(
                    {"error": f"Unknown use case: {use_case}", "available_use_cases": available},
                    indent=2,
                )

            # Use the pre-built query as a base, but allow overrides
            query = use_case_info["query_pattern"]
            if keywords:
                query += f" {keywords}"
            if aggregate_by:
                agg_fields = aggregate_by
            else:
                # Use example fields from use case
                agg_fields = ",".join(use_case_info.get("example_fields", []))
                if agg_fields:
                    query += f" | count by {agg_fields} | sort _count | limit {limit}"
        else:
            # Build custom query
            agg_list = aggregate_by.split(",") if aggregate_by else None
            query = build_legacy_audit_query(
                action=action,
                status=status,
                source_category=source_category,
                keywords=keywords,
                aggregate_by=agg_list,
                limit=limit,
            )

        # Execute search using existing search_sumo_logs tool
        client = await get_sumo_client(instance)

        # Determine time range
        if from_time is not None and to_time is not None:
            from_str = from_time
            to_str = to_time
        else:
            hours_back = validate_time_range(hours_back)
            to_time_dt = datetime.now(timezone.utc)
            from_time_dt = to_time_dt - timedelta(hours=hours_back)
            from_str = from_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            to_str = to_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.search_logs(query, from_str, to_str, "UTC", False)

        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "search_legacy_audit")


@mcp.tool()
async def search_audit_events(
    event_name: Optional[str] = Field(
        default=None,
        description="Event name filter (e.g., 'UserLoginSuccess', 'ContentUpdated', 'InsightCreated')",
    ),
    source_category: Optional[str] = Field(
        default=None,
        description="Source category filter (e.g., 'userSessions', 'content', 'cseInsight')",
    ),
    operator_email: Optional[str] = Field(
        default=None, description="Filter by operator email address"
    ),
    keywords: Optional[str] = Field(default=None, description="Additional keyword search terms"),
    extract_fields: Optional[str] = Field(
        default=None,
        description="Comma-separated JSON fields to extract (default: eventName,eventTime,operator.email,operator.id,operator.sourceIp)",
    ),
    aggregate_by: Optional[str] = Field(
        default=None,
        description="Comma-separated fields to aggregate by (e.g., 'eventName,operator_email')",
    ),
    hours_back: int = Field(
        default=24,
        description="Number of hours to search back from now (ignored if from_time/to_time provided)",
    ),
    from_time: Optional[str] = Field(
        default=None, description="Start time: ISO8601, epoch ms, or relative like '-1h'"
    ),
    to_time: Optional[str] = Field(
        default=None, description="End time: ISO8601, epoch ms, or relative like 'now'"
    ),
    limit: int = Field(default=100, description="Maximum number of results to return"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Search the enterprise audit events index (_index=sumologic_audit_events).

    **IMPORTANT - Terminology Clarification:**
    This tool searches the audit EVENT index (user actions, content changes, CSE operations).
    For analyzing SEARCH QUERY usage/performance, use run_search_audit_query or analyze_search_scan_cost.

    The enterprise audit events index contains structured JSON logs for user and system actions
    across all Sumo Logic features. Events are organized by _sourceCategory (feature area).

    **Common Event Categories:**
    - Authentication: UserLoginSuccess, UserLoginFailure, UserLogout, MfaEnabled
    - Content Management: ContentCreated, ContentUpdated, ContentDeleted, ContentMoved
    - Data Collection: CollectorCreated, SourceCreated, SourceUpdated
    - CSE Operations: InsightCreated, InsightUpdated, InsightClosed
    - User Management: UserCreated, UserUpdated, RoleAssigned
    - Monitoring: MonitorCreated, MonitorUpdated, MonitorTriggered

    **Common Source Categories:**
    - userSessions: Authentication events
    - content: Content library operations
    - dashboards: Dashboard operations
    - searches: Saved search operations
    - collectors/sources: Data collection configuration
    - cseInsight/cseSignal/cseRule: Cloud SIEM operations
    - monitors: Monitor and alert operations

    **Key Fields (automatically extracted):**
    - eventName: Type of event
    - eventTime: When the event occurred
    - operator.email: User who performed the action
    - operator.id: User ID
    - operator.sourceIp: Source IP address

    Additional fields vary by event type (e.g., sourceIdentity.collectorName, sourceIdentity.sourceName)

    **Example Queries:**
    - User logins: source_category="userSessions", event_name="UserLoginSuccess"
    - CSE insights: source_category="cseInsight", keywords="InsightUpdated"
    - Content changes by user: operator_email="user@example.com", source_category="content"
    - Top events: aggregate_by="_sourcecategory,eventName"

    **Parameters:**
    - event_name: Filter by event name (can use keyword matching)
    - source_category: Filter by _sourceCategory (feature area)
    - operator_email: Filter by user email
    - keywords: Additional keyword search
    - extract_fields: Custom JSON fields to extract
    - aggregate_by: Fields to group by (adds '| count by' operator)
    - limit: Maximum results (default 100)

    **Returns:**
    JSON with parsed event data including extracted fields. If aggregate_by is specified,
    returns aggregated counts by the specified fields.

    **API Reference:**
    https://www.sumologic.com/help/docs/manage/security/audit-indexes/audit-event-index/
    https://service.sumologic.com/audit/docs/
    """
    try:
        from .audit_helpers import build_enterprise_audit_query

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("search_audit_events")

        instance = validate_instance_name(instance)

        # Parse extract_fields
        extract_list = extract_fields.split(",") if extract_fields else None

        # Parse aggregate_by
        agg_list = aggregate_by.split(",") if aggregate_by else None

        # Build query
        query = build_enterprise_audit_query(
            index="sumologic_audit_events",
            event_name=event_name,
            source_category=source_category,
            operator_email=operator_email,
            keywords=keywords,
            parse_json=True,
            extract_fields=extract_list,
            aggregate_by=agg_list,
            limit=limit,
        )

        # Execute search
        client = await get_sumo_client(instance)

        # Determine time range
        if from_time is not None and to_time is not None:
            from_str = from_time
            to_str = to_time
        else:
            hours_back = validate_time_range(hours_back)
            to_time_dt = datetime.now(timezone.utc)
            from_time_dt = to_time_dt - timedelta(hours=hours_back)
            from_str = from_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            to_str = to_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.search_logs(query, from_str, to_str, "UTC", False)

        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "search_audit_events")


@mcp.tool()
async def search_system_events(
    use_case: Optional[str] = Field(
        default=None,
        description="Pre-built use case: 'collector_source_health', 'monitor_alerts', or 'monitor_alert_timeline'",
    ),
    event_name: Optional[str] = Field(
        default=None, description="Event name filter (e.g., system-specific events)"
    ),
    source_category: Optional[str] = Field(
        default=None, description="Source category filter for system events"
    ),
    keywords: Optional[str] = Field(default=None, description="Additional keyword search terms"),
    extract_fields: Optional[str] = Field(
        default=None,
        description="Comma-separated JSON fields to extract (default: eventName,eventTime,operator.email,operator.id,operator.sourceIp)",
    ),
    aggregate_by: Optional[str] = Field(
        default=None, description="Comma-separated fields to aggregate by"
    ),
    hours_back: int = Field(
        default=24,
        description="Number of hours to search back from now (ignored if from_time/to_time provided)",
    ),
    from_time: Optional[str] = Field(
        default=None, description="Start time: ISO8601, epoch ms, or relative like '-1h'"
    ),
    to_time: Optional[str] = Field(
        default=None, description="End time: ISO8601, epoch ms, or relative like 'now'"
    ),
    limit: int = Field(default=100, description="Maximum number of results to return"),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Search the enterprise system events index (_index=sumologic_system_events).

    **IMPORTANT - Terminology Clarification:**
    This tool searches the system EVENT index (collector health, monitor alerts, system operations).
    For analyzing SEARCH QUERY usage/performance, use run_search_audit_query or analyze_search_scan_cost.

    The enterprise system events index contains structured JSON logs for system-level operations
    and automated processes in Sumo Logic. Similar structure to audit_events but focused on
    system operations rather than user actions.

    **Pre-built Use Cases:**
    Set use_case parameter to:
    - "collector_source_health": Monitor unhealthy collector/source states (ideal for monitors)
      Returns aggregated health events with resource name, error, and tracker ID
    - "monitor_alerts": Analyze monitor alert state changes and frequency
      Returns alert counts by monitor name (excludes Normal states)
    - "monitor_alert_timeline": Timeline view of alert status changes with durations
      Returns chronological alert state changes with duration in minutes

    **Common System Events:**
    - Health-Change events: Collector/source health status changes (healthy/unhealthy)
    - Alert state changes: Monitor alert transitions (Normal, Critical, Warning, etc.)
    - Automated data management operations
    - System-triggered searches and alerts
    - Background processing events
    - System configuration changes

    **Key Fields (automatically extracted):**
    - eventName: Type of system event
    - eventTime: When the event occurred
    - operator.email: System or service account (if applicable)
    - operator.id: System/service account ID
    - operator.sourceIp: Source IP address

    **Example Queries:**
    - System events by type: aggregate_by="eventName"
    - Recent system operations: keywords="system", limit=50
    - Collector health monitoring: use_case="collector_source_health"

    **Parameters:**
    - use_case: Pre-built use case (overrides other parameters)
    - event_name: Filter by event name
    - source_category: Filter by _sourceCategory
    - keywords: Additional keyword search
    - extract_fields: Custom JSON fields to extract
    - aggregate_by: Fields to group by (adds '| count by' operator)
    - limit: Maximum results (default 100)

    **Returns:**
    JSON with parsed system event data. If aggregate_by is specified,
    returns aggregated counts by the specified fields.

    **API Reference:**
    https://www.sumologic.com/help/docs/manage/security/audit-indexes/system-event-index/
    https://service.sumologic.com/audit/docs/#tag/Health-Events-(System)
    """
    try:
        from .audit_helpers import build_enterprise_audit_query, get_system_event_use_case

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("search_system_events")

        instance = validate_instance_name(instance)

        # Handle pre-built use case
        if use_case:
            use_case_info = get_system_event_use_case(use_case)
            if not use_case_info:
                return json.dumps(
                    {
                        "error": f"Unknown use case: {use_case}",
                        "available_use_cases": [
                            "collector_source_health",
                            "monitor_alerts",
                            "monitor_alert_timeline",
                        ],
                    },
                    indent=2,
                )

            # Use the pre-built query
            query = use_case_info["query_pattern"]
            if keywords:
                query += f" {keywords}"
        else:
            # Parse extract_fields
            extract_list = extract_fields.split(",") if extract_fields else None

            # Parse aggregate_by
            agg_list = aggregate_by.split(",") if aggregate_by else None

            # Build query
            query = build_enterprise_audit_query(
                index="sumologic_system_events",
                event_name=event_name,
                source_category=source_category,
                operator_email=None,  # System events may not have operator email
                keywords=keywords,
                parse_json=True,
                extract_fields=extract_list,
                aggregate_by=agg_list,
                limit=limit,
            )

        # Execute search
        client = await get_sumo_client(instance)

        # Determine time range
        if from_time is not None and to_time is not None:
            from_str = from_time
            to_str = to_time
        else:
            hours_back = validate_time_range(hours_back)
            to_time_dt = datetime.now(timezone.utc)
            from_time_dt = to_time_dt - timedelta(hours=hours_back)
            from_str = from_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            to_str = to_time_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.search_logs(query, from_str, to_str, "UTC", False)

        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "search_system_events")


# ============================================================================
# UTILITY TOOLS
# ============================================================================


@mcp.tool()
async def get_skill(
    skill_name: str = Field(
        description="Skill filename without .md extension (e.g., 'search-write-queries', 'discovery-logs-without-metadata')"
    ),
) -> str:
    """
    Get a skill definition from the skills library.

    Skills are reusable knowledge artifacts that describe **how to accomplish specific tasks**
    in the Sumo Logic platform using MCP tools and best practices.

    This tool also supports a **virtual Technical Account Engineer (TAE)** role: use skills
    proactively when users ask architecture questions, design reviews, or "should I use X or Y?"
    questions — not only when performing data tasks.

    **Skill Categories:**
    - `consulting-guide` - Meta-skill: TAE consulting approach, question taxonomy, architecture framework
    - `search-*` - Query writing, optimization, scheduled views, indexes/partitions, Copilot
    - `alerting-*` - Monitors, detection methods, time compare, anomaly detection
    - `dashboards-*` - Dashboard types, panel types, transpose patterns
    - `data-collection-*` - Collection patterns and source category naming
    - `discovery-*` - Finding logs, schemas, partitions, views
    - `cost-*` - Search costs, data volume, credit analysis
    - `audit-*` - Audit indexes, user activity, system health + admin alert templates
    - `content-*` - Content library navigation, URLs
    - `admin-*` - Partition design, FERs, admin alerting, collectors
    - `ui-*` - Interactive UI features

    **All Available Skills (fetch before advising on these topics):**

    Consultation & Architecture:
    - `consulting-guide` - Use for any open-ended, "how should I", or architecture question
      Triggers: "how should I set up X", "what's the best way to Y", "should I use X or Y",
                "architecture review", "design my partitions/alerting/collection"

    Search & Query:
    - `search-log-search-basics` - Core pipeline, metadata fields, parse operators, cardinality reduction
      Triggers: "how does search work", "what is _sourceCategory", "how do I parse", new user questions,
                "logreduce", "logcompare", "normalize field", "high cardinality"
    - `search-write-queries` - Complete 5-phase query construction guide
      Triggers: writing any new Sumo Logic query
    - `search-optimize-queries` - SKEFE framework, bloom filter, query rewriting, search audit
      Triggers: "query is slow", "too expensive", "scans too much", "reduce scan", "performance"
    - `search-subquery` - Subquery patterns: compose/keywords, sneaky save, cat filters, aggregation-as-transaction
      Triggers: "subquery", "compose", "correlate two log sources", "filter parent query", "child query",
                "cross-source correlation", "transactionize alternative", "sneaky save", "cat subquery",
                "join alternative", "compose keywords", "multi-state transaction"
    - `search-indexes-partitions` - Data tiers, finding which partition holds data
      Triggers: "_index=", "_view=", "which partition", "Infrequent tier", "Flex tier", "data tier"
    - `search-optimize-with-views` - Transform slow queries using scheduled views (user guide)
      Triggers: "dashboard is slow", "use a view", "scheduled view query", "sum(_count)"
    - `search-scheduled-views` - Admin view design, Base Camp model, multi-layer architecture
      Triggers: "create a view", "design a view", "view patterns", "multi-layer", "1m view"
    - `search-copilot` - Mo AI Copilot tips and workflow
      Triggers: "Copilot", "Mo", "AI query generation", "natural language query"
    - `ui-navigate-and-search` - Field Browser, Log Inspector, histogram, UI workflow
      Triggers: "Field Browser", "Log Inspector", "histogram", "UI investigation"

    Alerting & Monitoring:
    - `alerting-monitors` - Monitor types (Logs/Metrics/SLO), detection, alert grouping
      Triggers: "create a monitor", "set up an alert", "monitor vs scheduled search",
                "alert grouping", "Anomaly monitor", "SLO"
    - `alerting-time-compare-anomaly` - Dynamic thresholds, time compare, anomaly vs outlier
      Triggers: "anomaly detection", "dynamic threshold", "week-over-week", "compare with timeshift",
                "outlier", "seasonality", "relative alerting"

    Dashboards:
    - `dashboards-overview` - Four dashboard types, App Catalog, template variables, linked dashboards
      Triggers: "what dashboard should I build", "dashboard types", "template variable", "drill-down",
                "linked dashboards", "suggestion list", "variable dropdown", "advanced template variable"
    - `dashboards-panel-types` - Panel types, time series, transpose, honeycomb, heatmap, overrides, JSON editing
      Triggers: "panel type", "time series panel", "transpose", "honeycomb", "geoip map",
                "single value", "chart type", "timeslice required", "heatmap", "bubble chart",
                "scatter chart", "panel override", "dual axis", "JSON panel edit", "mixed chart",
                "timeless dashboard", "cat dashboard", "clickable url", "tourl", "emoji table",
                "transpose without timeslice"

    Data Collection:
    - `data-collection-patterns` - 7 collection patterns, logging standards, processing rules, technical best practices
      Triggers: "how to collect data", "collection architecture", "source category naming",
                "OpenTelemetry", "HTTPS source", "Installed Collector", "C2C", "hosted collector",
                "processing rules", "exclude logs", "mask PII", "logging standard", "log format",
                "timestamp issue", "multiline events", "HTTPS headers", "x-sumo-category"

    Discovery:
    - `discovery-logs-without-metadata` - Multi-phase discovery when metadata unknown (USE THIS FOR "FIND X LOGS")
      Triggers: "find cloudtrail logs", "find nginx logs", "find kubernetes logs", "locate logs",
                "don't know where data is", "find my logs", "what source category", "discover logs",
                "where are the X logs", "help me find", "looking for logs"
    - `discovery-scheduled-views` - Inventory views, understand schemas, versioned view patterns
      Triggers: "what views exist", "find a view", "view schema", "reduceOnlyFields"

    Cost Analysis:
    - `cost-analyze-search-costs` - Flex/Infrequent tier scan cost breakdown by user/query
      Triggers: "high scan costs", "reduce credits", "who is scanning the most", "infrequent cost"

    Audit & Admin Monitoring:
    - `audit-user-activity` - User authentication, content changes, CSE audit events
      Triggers: "who logged in", "audit user", "content changes", "user activity"
    - `audit-system-health` - Collector health, monitor alerts + admin alert templates
      Triggers: "collector unhealthy", "data not arriving", "ingest monitoring",
                "ingest spike alert", "rate limiting alert", "admin alerts setup"
    - `admin-alerting-and-monitoring` - 5 complete admin alert query templates
      Triggers: "set up admin alerting", "ingest spike", "collection stopped", "rate limit alert",
                "scan cost alert", "data volume monitoring", "audit policy"

    Administration & Architecture:
    - `admin-partition-design` - Seven partition design rules, scan reduction analysis
      Triggers: "partition design", "how many partitions", "organise indexes", "scan reduction",
                "monolithic partition", "query rewriting", "CSE partition", "Flex partition"
    - `admin-field-extraction-rules` - FER patterns, histogram/stripe case study (342x speedup)
      Triggers: "field extraction rules", "FER", "index-time field", "parse at ingest",
                "speed up where filter", "stripe pattern", "histogram speedup"
    - `admin-rbac-security` - SAML/SSO, role design, search scope, service accounts, user lifecycle
      Triggers: "set up RBAC", "access control", "SAML", "SSO", "user roles", "search scope",
                "service account", "API key", "installation token", "user lifecycle", "offboard user",
                "who can see what", "restrict data access", "role design", "SAML provisioning"

    Content Management:
    - `content-library-navigation` - Browse and export dashboards/searches, URL generation
      Triggers: "find a dashboard", "export content", "library path", "shareable link"

    **Returns:**
    Full markdown content of the requested skill, or error if not found.
    When skill not found, the error response lists all available skill names.

    **Example:**
    ```
    get_skill("consulting-guide")
    get_skill("search-write-queries")
    get_skill("admin-partition-design")
    ```

    **Skill Index:**
    See `skills/README.md` for complete list with descriptions.
    """
    try:
        # Get the skills directory (relative to this file)
        current_file = Path(__file__)
        skills_dir = current_file.parent.parent.parent / "skills"

        # Construct skill file path
        skill_file = skills_dir / f"{skill_name}.md"

        # Check if skill exists
        if not skill_file.exists():
            # List available skills for helpful error message
            available_skills = []
            if skills_dir.exists():
                available_skills = [
                    f.stem for f in skills_dir.glob("*.md") if f.name != "README.md"
                ]
                available_skills.sort()

            error_response = {
                "error": f"Skill not found: {skill_name}",
                "skills_directory": str(skills_dir),
                "available_skills": available_skills,
                "hint": "Use skill filename without .md extension (e.g., 'search-write-queries')",
            }
            return json.dumps(error_response, indent=2)

        # Read and return skill content
        skill_content = skill_file.read_text(encoding="utf-8")

        return skill_content

    except Exception as e:
        return handle_tool_error(e, "get_skill")


@mcp.tool()
async def describe_log_pipeline(
    scope: str = Field(
        description="Log scope to analyze (e.g., '_sourceCategory=foo/bar', 'collector=myCollector', 'cloudtrail', 'nginx logs')"
    ),
    from_time: str = Field(
        default="-3h",
        description="Start time for metadata discovery (ISO8601, epoch ms, or relative like '-3h', '-24h')",
    ),
    to_time: str = Field(default="now", description="End time (ISO8601, epoch ms, or relative)"),
    max_collectors: int = Field(
        default=20,
        description="Maximum number of collectors to detail (prevents overwhelming output for ephemeral collectors)",
    ),
    instance: str = Field(default="default", description="Sumo Logic instance name"),
) -> str:
    """
    Discover and describe the complete log ingestion pipeline for given log scope.

    This tool orchestrates multiple discovery phases to build a comprehensive view of how logs
    flow into Sumo Logic, including collection configuration, processing rules, field extraction,
    partition routing, and scheduled views.

    **Pipeline Phases Discovered:**

    1. **Collection** - Collector and source configuration
       - Collector details (name, type, category)
       - Source configuration (timestamp parsing, timezone, multiline)
       - Processing rules (include/exclude/mask)
       - Metadata and field assignments

    2. **Field Extraction** - Index-time field extraction rules
       - FER scope and parse expressions
       - Fields created at ingestion

    3. **Partition Routing** - Index assignment and data tier
       - Partition routing expressions
       - Data tier (Continuous/Frequent/Infrequent/Flex/CSE)
       - Retention period

    4. **Scheduled Views** - Pre-aggregated views that may include this data
       - View definitions matching log scope
       - View schemas and indexed fields

    5. **Sample Logs** - Actual log samples and format detection
       - Up to 5 sample log events
       - Log format analysis (JSON, CSV, key-value, unstructured)
       - Parsing operator suggestions

    6. **Installed Apps** - Pre-built apps matching log type
       - Installed Sumo Logic apps with relevant dashboards
       - App recommendations based on log keywords

    **Discovery Process:**

    - If scope is a keyword (e.g., "cloudtrail", "nginx"), discovers matching source categories
    - If scope is metadata (e.g., "_sourceCategory=foo"), uses directly
    - Performs log metadata discovery to find collectors, sources, partitions, fields
    - Gathers collector and source configurations
    - Identifies matching field extraction rules
    - Determines partition routing and retention
    - Finds relevant scheduled views
    - Collects sample log events and analyzes format
    - Searches for installed apps matching log type

    **Parameters:**
    - `scope`: Log identifier (source category, collector, keyword, or metadata filter)
    - `from_time`: Time range for metadata discovery (shorter = faster, longer = more coverage)
    - `to_time`: End time for discovery
    - `max_collectors`: Limit collector details (useful for ephemeral/auto-scaled collectors)
    - `instance`: Instance name

    **Returns:**
    Structured pipeline report in JSON format with sections:
    - `summary`: Quick overview of log pipeline
    - `metadata_discovered`: Source categories, collectors, sources, partitions found
    - `collection`: Collector and source details with configuration
    - `field_extraction`: Matching field extraction rules
    - `partition_routing`: Partition details and routing logic
    - `scheduled_views`: Relevant scheduled views
    - `sample_logs`: Sample log events with format analysis
    - `installed_apps`: Matching installed apps
    - `recommendations`: Suggestions for optimization or investigation

    **Example Use Cases:**

    1. Understand CloudTrail ingestion:
       ```
       scope="cloudtrail"
       ```

    2. Analyze specific source category:
       ```
       scope="_sourceCategory=prod/app/logs"
       ```

    3. Investigate collector configuration:
       ```
       scope="collector=prod-web-servers"
       ```

    4. Find nginx log pipeline with 24h lookback:
       ```
       scope="nginx"
       from_time="-24h"
       ```

    **API References:**
    - Data Volume: https://help.sumologic.com/docs/manage/ingestion-volume/data-volume-index/
    - Collectors: https://api.sumologic.com/docs/#operation/getCollector
    - Sources: https://help.sumologic.com/docs/send-data/use-json-configure-sources/
    - Partitions: https://api.sumologic.com/docs/#operation/listPartitions
    - Field Extraction Rules: https://api.sumologic.com/docs/#operation/listExtractionRules
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("describe_log_pipeline")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        pipeline_report = {
            "summary": {},
            "metadata_discovered": {},
            "collection": {},
            "field_extraction": {},
            "partition_routing": {},
            "scheduled_views": {},
            "sample_logs": {},
            "installed_apps": {},
            "recommendations": [],
        }

        # Phase 1: Resolve scope to source categories if needed
        logger.info(f"Phase 1: Resolving scope '{scope}'")

        # Determine if scope is a keyword search or metadata filter
        is_metadata_scope = any(
            x in scope.lower()
            for x in [
                "_sourcecategory=",
                "_collector=",
                "_source=",
                "_index=",
                "_view=",
                "sourcecategory=",
            ]
        )

        source_categories = []
        dimension = "sourceCategory"

        if is_metadata_scope:
            # Scope is already a metadata filter
            pipeline_report["summary"]["scope_type"] = "metadata_filter"
            pipeline_report["summary"]["original_scope"] = scope

            # Extract dimension if specified
            if "_collector=" in scope.lower() or "collector=" in scope.lower():
                dimension = "collector"
            elif "_source=" in scope.lower():
                dimension = "source"

        else:
            # Scope is a keyword - discover matching source categories
            pipeline_report["summary"]["scope_type"] = "keyword_search"
            pipeline_report["summary"]["search_keyword"] = scope

            # Use analyze_data_volume to find matching source categories
            logger.info(f"Discovering source categories matching keyword: {scope}")

            dv_query = f'_index=* _view=sumologic_volume\n| where dimension="{dimension}"\n| where value matches /{scope}/i\n| sum(sizeInBytes) as bytes by value, tier\n| bytes / 1024 / 1024 / 1024 as gb\n| sort by bytes desc\n| limit 20'

            dv_job = await client.create_search_job(
                query=dv_query, from_time=from_time, to_time=to_time, timezone_str="UTC"
            )
            dv_job_id = dv_job["id"]

            # Poll for completion
            for _ in range(60):
                await asyncio.sleep(2)
                status = await client.get_search_job_status(dv_job_id)
                if status["state"] == "DONE GATHERING RESULTS":
                    break

            dv_results = await client.get_search_job_records(dv_job_id, limit=20)
            dv_records = dv_results.get("records", [])

            # Clean up search job
            try:
                await client.delete_search_job(dv_job_id)
            except Exception:  # noqa: S110  # nosec B110
                pass  # Best effort cleanup - job deletion failure is acceptable

            if not dv_records:
                return json.dumps(
                    {
                        "error": f"No source categories found matching keyword '{scope}'",
                        "suggestion": "Try a different keyword or time range, or use a metadata filter like '_sourceCategory=pattern'",
                    },
                    indent=2,
                )

            for record in dv_records:
                map_data = record.get("map", {})
                value = map_data.get("value", "")
                tier = map_data.get("tier", "")
                gb = map_data.get("gb", 0)

                if dimension == "sourceCategory":
                    source_categories.append(
                        {"sourceCategory": value, "tier": tier, "gb": round(gb, 3)}
                    )

            pipeline_report["metadata_discovered"]["source_categories"] = source_categories
            pipeline_report["summary"][
                "found_source_categories"
            ] = f"{len(source_categories)} categories found"

        # Phase 2: Log metadata discovery
        logger.info("Phase 2: Discovering log metadata")

        # Build metadata scope
        if is_metadata_scope:
            metadata_scope = scope
        else:
            # Use first source category
            if source_categories:
                first_sc = source_categories[0]["sourceCategory"]
                metadata_scope = f"_sourceCategory={first_sc}"
            else:
                metadata_scope = scope

        # Discover metadata: _sourceCategory, _collector, _source, _index
        metadata_query = f"""{metadata_scope}
| count by _sourceCategory, _collector, _source, _view
| sort by _count desc
| limit {max_collectors}"""

        meta_job = await client.create_search_job(
            query=metadata_query, from_time=from_time, to_time=to_time, timezone_str="UTC"
        )
        meta_job_id = meta_job["id"]

        # Poll for completion
        for _ in range(60):
            await asyncio.sleep(2)
            status = await client.get_search_job_status(meta_job_id)
            if status["state"] == "DONE GATHERING RESULTS":
                break

        meta_results = await client.get_search_job_records(meta_job_id, limit=max_collectors)
        meta_records = meta_results.get("records", [])

        # Clean up
        try:
            await client.delete_search_job(meta_job_id)
        except Exception:  # noqa: S110  # nosec B110
            pass  # Best effort cleanup - job deletion failure is acceptable

        collectors_found = set()
        sources_found = set()
        partitions_found = set()
        source_categories_found = set()

        for record in meta_records:
            map_data = record.get("map", {})
            collectors_found.add(map_data.get("_collector", ""))
            sources_found.add(map_data.get("_source", ""))
            partitions_found.add(map_data.get("_view", ""))
            source_categories_found.add(map_data.get("_sourceCategory", ""))

        pipeline_report["metadata_discovered"]["collectors"] = sorted(
            [c for c in collectors_found if c]
        )
        pipeline_report["metadata_discovered"]["sources"] = sorted([s for s in sources_found if s])
        pipeline_report["metadata_discovered"]["partitions"] = sorted(
            [p for p in partitions_found if p]
        )
        pipeline_report["metadata_discovered"]["source_categories_discovered"] = sorted(
            [sc for sc in source_categories_found if sc]
        )

        # Phase 3: Get partition details
        logger.info("Phase 3: Analyzing partition routing")

        partitions_response = await client.get_partitions(limit=100)
        all_partitions = partitions_response.get("data", [])

        matching_partitions = []
        for partition in all_partitions:
            partition_name = partition.get("name", "")
            if partition_name in partitions_found:
                matching_partitions.append(
                    {
                        "name": partition_name,
                        "routingExpression": partition.get("routingExpression", ""),
                        "retentionPeriod": partition.get("retentionPeriod", 0),
                        "isActive": partition.get("isActive", False),
                        "dataForwardingId": partition.get("dataForwardingId"),
                        "totalBytes": partition.get("totalBytes", 0),
                        "analyticsTier": partition.get("analyticsTier", ""),
                    }
                )

        pipeline_report["partition_routing"]["partitions"] = matching_partitions

        # Phase 4: Get collector and source details
        logger.info("Phase 4: Gathering collector and source configuration")

        collectors_response = await client.get_collectors(limit=1000)
        all_collectors = collectors_response.get("collectors", [])

        collector_details = []
        source_details = []

        for collector in all_collectors:
            collector_name = collector.get("name", "")
            if collector_name in collectors_found:
                collector_id = collector.get("id")

                collector_details.append(
                    {
                        "id": collector_id,
                        "name": collector_name,
                        "collectorType": collector.get("collectorType", ""),
                        "category": collector.get("category"),
                        "timeZone": collector.get("timeZone"),
                        "fields": collector.get("fields", {}),
                    }
                )

                # Get sources for this collector
                try:
                    sources_response = await client.get_sources(collector_id)
                    sources = sources_response.get("sources", [])

                    for source in sources:
                        source_name = source.get("name", "")
                        # Only include sources we discovered
                        if source_name in sources_found or len(sources_found) == 0:
                            source_details.append(
                                {
                                    "collector_name": collector_name,
                                    "source_name": source_name,
                                    "sourceType": source.get("sourceType", ""),
                                    "category": source.get("category"),
                                    "timeZone": source.get("timeZone"),
                                    "automaticDateParsing": source.get("automaticDateParsing"),
                                    "multilineProcessingEnabled": source.get(
                                        "multilineProcessingEnabled"
                                    ),
                                    "useAutolineMatching": source.get("useAutolineMatching"),
                                    "forceTimeZone": source.get("forceTimeZone"),
                                    "fields": source.get("fields", {}),
                                    "filters": source.get("filters", []),
                                }
                            )
                except Exception as e:
                    logger.warning(f"Failed to get sources for collector {collector_id}: {e}")

        pipeline_report["collection"]["collectors"] = collector_details
        pipeline_report["collection"]["sources"] = source_details

        # Phase 5: Check field extraction rules
        logger.info("Phase 5: Checking field extraction rules")

        fers_response = await client.list_field_extraction_rules(limit=100)
        all_fers = fers_response.get("data", [])

        matching_fers = []
        for fer in all_fers:
            fer_scope = fer.get("scope", "")
            enabled = fer.get("enabled", False)

            # Check if FER scope might match our logs
            # This is a simple heuristic - could be improved
            matches = False
            for sc in source_categories_found:
                if sc in fer_scope or any(p in fer_scope for p in partitions_found):
                    matches = True
                    break

            if matches or fer_scope == "*":
                matching_fers.append(
                    {
                        "name": fer.get("name", ""),
                        "scope": fer_scope,
                        "parseExpression": fer.get("parseExpression", ""),
                        "enabled": enabled,
                    }
                )

        pipeline_report["field_extraction"]["rules"] = matching_fers

        # Phase 6: Find relevant scheduled views
        logger.info("Phase 6: Finding relevant scheduled views")

        views_response = await client.list_scheduled_views(limit=100)
        all_views = views_response.get("data", [])

        matching_views = []
        for view in all_views:
            view_query = view.get("query", "")

            # Check if view query references our source categories or partitions
            matches = False
            for sc in source_categories_found:
                if sc in view_query:
                    matches = True
                    break

            if not matches:
                for partition in partitions_found:
                    if partition in view_query or f"_index={partition}" in view_query:
                        matches = True
                        break

            if matches:
                matching_views.append(
                    {
                        "indexName": view.get("indexName", ""),
                        "query": view_query,
                        "retentionPeriod": view.get("retentionPeriod", 0),
                        "reduceOnlyFields": view.get("reduceOnlyFields", []),
                        "indexedFields": view.get("indexedFields", []),
                    }
                )

        pipeline_report["scheduled_views"]["views"] = matching_views

        # Phase 7: Get sample log events
        logger.info("Phase 7: Collecting sample log events")

        sample_logs = []
        log_format_analysis = {}

        try:
            # Get 5 sample log messages using the metadata scope
            sample_query = f"{metadata_scope}\n| limit 5"

            sample_job = await client.create_search_job(
                query=sample_query, from_time=from_time, to_time=to_time, timezone_str="UTC"
            )
            sample_job_id = sample_job["id"]

            # Poll for completion (shorter timeout for samples)
            for _ in range(30):
                await asyncio.sleep(1)
                status = await client.get_search_job_status(sample_job_id)
                if status["state"] == "DONE GATHERING RESULTS":
                    break

            # Get raw messages
            sample_results = await client.get_search_job_messages(sample_job_id, limit=5)
            messages = sample_results.get("messages", [])

            # Clean up
            try:
                await client.delete_search_job(sample_job_id)
            except Exception:  # noqa: S110  # nosec B110
                pass  # Best effort cleanup - job deletion failure is acceptable

            # Extract and analyze log samples
            for msg in messages:
                map_data = msg.get("map", {})
                raw_message = map_data.get("_raw", "")

                if raw_message:
                    sample_logs.append(
                        {
                            "raw": raw_message[:500],  # Truncate to 500 chars
                            "timestamp": map_data.get("_messagetime", ""),
                            "sourceCategory": map_data.get("_sourcecategory", ""),
                        }
                    )

            # Simple log format analysis
            if sample_logs:
                first_log = sample_logs[0]["raw"]

                # Detect format
                if first_log.startswith("{"):
                    log_format_analysis["format"] = "JSON"
                    log_format_analysis["suggestion"] = "Use 'json auto' operator for parsing"
                elif "|" in first_log or "\t" in first_log:
                    log_format_analysis["format"] = "Delimited (CSV/TSV)"
                    log_format_analysis["suggestion"] = (
                        "Use 'csv' or 'parse' operator with delimiters"
                    )
                elif "=" in first_log and ("," in first_log or " " in first_log):
                    log_format_analysis["format"] = "Key-Value pairs"
                    log_format_analysis["suggestion"] = (
                        "Use 'keyvalue' operator or parse with key=value pattern"
                    )
                else:
                    log_format_analysis["format"] = "Unstructured text"
                    log_format_analysis["suggestion"] = (
                        "Use 'parse' operator with custom patterns or regex"
                    )

                log_format_analysis["sample_count"] = len(sample_logs)
                log_format_analysis["avg_length"] = sum(len(s["raw"]) for s in sample_logs) // len(
                    sample_logs
                )

        except Exception as e:
            logger.warning(f"Failed to get sample logs: {e}")
            log_format_analysis["error"] = f"Failed to retrieve sample logs: {str(e)}"

        pipeline_report["sample_logs"] = {
            "samples": sample_logs,
            "format_analysis": log_format_analysis,
        }

        # Phase 8: Find matching installed apps
        logger.info("Phase 8: Searching for relevant installed apps")

        matching_apps = []

        try:
            # Search for apps that might match our source categories or keywords
            search_keywords = []

            # Extract keywords from source categories
            for sc in source_categories_found:
                # Split on / and _ to get keywords
                parts = sc.replace("/", " ").replace("_", " ").split()
                search_keywords.extend([p.lower() for p in parts if len(p) > 3])

            # Add original scope if it was a keyword
            if not is_metadata_scope:
                search_keywords.append(scope.lower())

            # Get unique keywords
            search_keywords = list(set(search_keywords))

            # Search for apps matching these keywords
            apps_response = await client.list_apps()
            all_apps = apps_response.get("applications", [])

            for app in all_apps:
                app_name = app.get("name", "").lower()

                # Check if any keyword matches app name
                for keyword in search_keywords:
                    if keyword in app_name or app_name in keyword:
                        matching_apps.append(
                            {
                                "name": app.get("name", ""),
                                "appDefinitionId": app.get("appDefinitionId", ""),
                                "uuid": app.get("uuid", ""),
                                "matched_keyword": keyword,
                            }
                        )
                        break  # Only add once per app

        except Exception as e:
            logger.warning(f"Failed to search installed apps: {e}")
            pipeline_report["installed_apps"] = {"error": f"Failed to search apps: {str(e)}"}
        else:
            pipeline_report["installed_apps"] = {
                "apps": matching_apps,
                "search_keywords": search_keywords,
            }

        # Phase 9: Generate summary and recommendations
        pipeline_report["summary"]["collectors_discovered"] = len(collector_details)
        pipeline_report["summary"]["sources_discovered"] = len(source_details)
        pipeline_report["summary"]["partitions_used"] = len(matching_partitions)
        pipeline_report["summary"]["field_extraction_rules"] = len(matching_fers)
        pipeline_report["summary"]["relevant_scheduled_views"] = len(matching_views)
        pipeline_report["summary"]["sample_logs_collected"] = len(sample_logs)
        pipeline_report["summary"]["matching_apps_found"] = len(matching_apps)

        # Add recommendations
        if len(matching_partitions) > 1:
            pipeline_report["recommendations"].append(
                "Logs are routed to multiple partitions. Review partition routing expressions to ensure optimal data organization."
            )

        if len(matching_fers) == 0:
            pipeline_report["recommendations"].append(
                "No field extraction rules found. Consider adding FERs to pre-parse common fields for better query performance."
            )

        if len(matching_views) > 0:
            pipeline_report["recommendations"].append(
                f"Found {len(matching_views)} scheduled view(s) that may pre-aggregate this data. Use these for faster dashboard queries."
            )

        if len(source_details) > max_collectors:
            pipeline_report["recommendations"].append(
                f"Found more than {max_collectors} sources. Some details were truncated. Increase max_collectors parameter for full details."
            )

        if len(matching_apps) > 0:
            app_names = ", ".join([app["name"] for app in matching_apps[:3]])
            if len(matching_apps) > 3:
                app_names += f" and {len(matching_apps) - 3} more"
            pipeline_report["recommendations"].append(
                f"Found {len(matching_apps)} installed app(s) that may provide pre-built dashboards and searches: {app_names}"
            )

        if sample_logs and log_format_analysis.get("format"):
            pipeline_report["recommendations"].append(
                f"Detected log format: {log_format_analysis['format']}. {log_format_analysis.get('suggestion', '')}"
            )

        return json.dumps(pipeline_report, indent=2)

    except Exception as e:
        return handle_tool_error(e, "describe_log_pipeline")


# Cleanup handler
async def cleanup():
    """Clean up resources when the server shuts down."""
    logger.info("Cleaning up Sumo Logic MCP Server...")
    for instance_name, client in clients.items():
        logger.info(f"Closing client for instance: {instance_name}")
        await client.close()
    clients.clear()


# Initialize on startup
async def initialize():
    """Initialize the Sumo Logic MCP Server."""
    try:
        _ensure_config_initialized()
        config = get_config()
        logger.info("Initializing Sumo Logic MCP Server...")
        logger.info(f"Configured instances: {', '.join(config.list_instances())}")
        logger.info("Server initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize server: {str(e)}")
        raise


# Run the server
def main():
    """Main entry point for the MCP server."""
    try:
        # Initialize
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(initialize())

        logger.info("Starting Sumo Logic MCP Server...")

        # Run the FastMCP server
        mcp.run()

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        raise
    finally:
        # Clean up
        if "loop" in locals():
            loop.run_until_complete(cleanup())
            loop.close()


if __name__ == "__main__":
    main()
