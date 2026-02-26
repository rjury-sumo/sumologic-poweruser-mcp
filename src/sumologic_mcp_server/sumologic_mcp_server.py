#!/usr/bin/env python3
"""
Sumo Logic MCP Server

This server provides read-only access to Sumo Logic APIs through the Model Context Protocol.
It exposes tools for searching logs, querying metrics, and retrieving account information.

Supports multiple Sumo Logic instances with separate credentials.

Usage:
    uvx sumologic-mcp-server
    # or
    python -m sumologic_mcp_server.sumologic_mcp_server

Environment Variables:
    See .env.example for configuration options
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from .config import get_config, SumoInstanceConfig
from .exceptions import (
    APIError,
    AuthenticationError,
    InstanceNotFoundError,
    SumoMCPError,
    TimeoutError as SumoTimeoutError,
    ValidationError,
)
from .rate_limiter import get_rate_limiter
from .validation import (
    validate_instance_name,
    validate_pagination,
    validate_query_input,
    validate_time_range,
    CollectorValidation,
    ContentTypeValidation,
    MonitorSearchValidation,
)

# Logging will be configured on first access
logger = logging.getLogger(__name__)
audit_logger = logging.getLogger('audit')

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
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        if config.server_config.enable_audit_log:
            audit_handler = logging.FileHandler('sumo_mcp_audit.log')
            audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
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
            timeout=30.0
        )

    async def close(self):
        """Close the HTTP session."""
        await self.session.aclose()

    async def _request(self, method: str, path: str, api_version: str = "v1", **kwargs) -> Dict[str, Any]:
        """Make an authenticated request to the Sumo Logic API."""
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path

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
                    details=f"status_code={status_code}"
                )
            elif status_code == 403:
                logger.error(f"Authorization failed for {self.instance_name}: {path}")
                raise AuthenticationError(
                    f"Access denied. Your credentials may not have permission for this operation.",
                    details=f"path={path}"
                )
            elif status_code == 429:
                logger.warning(f"Rate limited by Sumo Logic API: {self.instance_name}")
                raise APIError(
                    "Sumo Logic API rate limit exceeded. Please try again later.",
                    status_code=429
                )
            else:
                logger.error(f"HTTP error {status_code} for {self.instance_name}: {e.response.text}")
                raise APIError(
                    f"Sumo Logic API request failed with status {status_code}",
                    status_code=status_code,
                    details="Check server logs for details"
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
                details="Check server logs for details"
            )

    async def search_logs(
        self,
        query: str,
        from_time: str,
        to_time: str,
        timezone_str: str = "UTC",
        by_receipt_time: bool = False,
        max_attempts: Optional[int] = None
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
            "byReceiptTime": by_receipt_time
        }

        # Only add requiresRawMessages if not default (to be compatible with older API versions)
        if not requires_raw_messages:
            search_data["requiresRawMessages"] = False

        job_response = await self._request("POST", "/search/jobs", api_version="v1", json=search_data)
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
                        params={"offset": 0, "limit": max_limit}
                    )
                    results_key = "records"
                else:
                    results_response = await self._request(
                        "GET",
                        f"/search/jobs/{job_id}/messages",
                        api_version="v1",
                        params={"offset": 0, "limit": max_limit}
                    )
                    results_key = "messages"

                return {
                    "job_id": job_id,
                    "state": state,
                    "query_type": query_type,
                    "message_count": status_response.get("messageCount", 0),
                    "record_count": status_response.get("recordCount", 0),
                    "results": results_response.get(results_key, [])
                }
            elif state in ["CANCELLED", "FORCE PAUSED"]:
                raise APIError(f"Search job {job_id} was {state.lower()}")

            await asyncio.sleep(5)  # Wait 5 seconds before checking again

        raise SumoTimeoutError(
            f"Search job {job_id} timed out after {max_attempts * 5} seconds"
        )

    async def get_search_job_records(
        self,
        job_id: str,
        offset: int = 0,
        limit: int = 10000
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
            "GET",
            f"/search/jobs/{job_id}/records",
            api_version="v1",
            params=params
        )

    async def get_search_job_messages(
        self,
        job_id: str,
        offset: int = 0,
        limit: int = 10000
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
            "GET",
            f"/search/jobs/{job_id}/messages",
            api_version="v1",
            params=params
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
        by_receipt_time: bool = False
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
            "byReceiptTime": by_receipt_time
        }

        # Only add requiresRawMessages if not default
        if not requires_raw_messages:
            search_data["requiresRawMessages"] = False

        return await self._request("POST", "/search/jobs", api_version="v1", json=search_data)

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

    async def get_dashboards(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get list of dashboards."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/dashboards", api_version="v2", params=params)

    async def query_metrics(self, query: str, from_time: str, to_time: str) -> Dict[str, Any]:
        """Query metrics."""
        metrics_data = {
            "query": [{"query": query, "rowId": "A"}],
            "startTime": int(datetime.fromisoformat(from_time.replace('Z', '+00:00')).timestamp() * 1000),
            "endTime": int(datetime.fromisoformat(to_time.replace('Z', '+00:00')).timestamp() * 1000),
            "requestId": f"mcp-{datetime.now().isoformat()}",
            "maxDataPoints": 800
        }
        return await self._request("POST", "/metrics/queries", api_version="v1", json=metrics_data)

    async def get_content_v2(self, content_type: str = "Dashboard", limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get content using the v2 content API."""
        params = {"type": content_type, "limit": limit, "offset": offset}
        return await self._request("GET", "/content", api_version="v2", params=params)

    async def get_roles_v2(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get roles using the v2 roles API."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/roles", api_version="v2", params=params)

    async def search_monitors(self, query: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Search for monitors."""
        params = {"query": query, "limit": limit, "token": offset}
        return await self._request("GET", "/monitors/search", api_version="v1", params=params)

    async def get_partitions(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get partitions."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/partitions", api_version="v1", params=params)

    # Content Library API methods

    async def get_personal_folder(self, include_children: bool = True) -> Dict[str, Any]:
        """Get user's personal folder."""
        params = {} if include_children else {"includeChildren": "false"}
        return await self._request("GET", "/content/folders/personal", api_version="v2", params=params)

    async def get_folder_by_id(self, folder_id: str, include_children: bool = True) -> Dict[str, Any]:
        """Get folder by ID."""
        params = {} if include_children else {"includeChildren": "false"}
        return await self._request("GET", f"/content/folders/{folder_id}", api_version="v2", params=params)

    async def get_content_by_path(self, content_path: str) -> Dict[str, Any]:
        """Get content item by path."""
        params = {"path": content_path}
        return await self._request("GET", "/content/path", api_version="v2", params=params)

    async def get_content_path(self, content_id: str) -> Dict[str, Any]:
        """Get content path by ID."""
        return await self._request("GET", f"/content/{content_id}/path", api_version="v2")

    async def begin_content_export(self, content_id: str, is_admin_mode: bool = False) -> Dict[str, Any]:
        """Begin async content export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request("POST", f"/content/{content_id}/export", api_version="v2", params=params)

    async def get_content_export_status(self, content_id: str, job_id: str) -> Dict[str, Any]:
        """Get content export job status."""
        return await self._request("GET", f"/content/{content_id}/export/{job_id}/status", api_version="v2")

    async def get_content_export_result(self, content_id: str, job_id: str) -> Dict[str, Any]:
        """Get content export job result."""
        return await self._request("GET", f"/content/{content_id}/export/{job_id}/result", api_version="v2")

    async def begin_global_folder_export(self, is_admin_mode: bool = False) -> Dict[str, Any]:
        """Begin async Global folder export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request("GET", "/content/folders/global", api_version="v2", params=params)

    async def get_global_folder_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get Global folder export job status."""
        return await self._request("GET", f"/content/folders/global/{job_id}/status", api_version="v2")

    async def get_global_folder_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get Global folder export job result."""
        return await self._request("GET", f"/content/folders/global/{job_id}/result", api_version="v2")

    async def begin_admin_recommended_export(self, is_admin_mode: bool = False) -> Dict[str, Any]:
        """Begin async Admin Recommended folder export."""
        params = {"isAdminMode": str(is_admin_mode).lower()} if is_admin_mode else {}
        return await self._request("GET", "/content/folders/adminRecommended", api_version="v2", params=params)

    async def get_admin_recommended_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get Admin Recommended folder export job status."""
        return await self._request("GET", f"/content/folders/adminRecommended/{job_id}/status", api_version="v2")

    async def get_admin_recommended_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get Admin Recommended folder export job result."""
        return await self._request("GET", f"/content/folders/adminRecommended/{job_id}/result", api_version="v2")

    # Account Management API methods

    async def get_account_status(self) -> Dict[str, Any]:
        """Get account status including subscription, plan type, and usage."""
        return await self._request("GET", "/account/status", api_version="v1")

    async def get_usage_forecast(self, number_of_days: int) -> Dict[str, Any]:
        """Get usage forecast for specified number of days."""
        params = {"numberOfDays": number_of_days}
        return await self._request("GET", "/account/usageForecast", api_version="v1", params=params)

    async def start_usage_export(
        self,
        start_date: str,
        end_date: str,
        group_by: str = "day",
        report_type: str = "standard",
        include_deployment_charge: bool = False
    ) -> Dict[str, Any]:
        """Start async usage report export job."""
        data = {
            "groupBy": group_by,
            "reportType": report_type,
            "includeDeploymentCharge": include_deployment_charge,
            "startDate": start_date,
            "endDate": end_date
        }
        return await self._request("POST", "/account/usage/report", api_version="v1", json=data)

    async def get_usage_export_status(self, job_id: str) -> Dict[str, Any]:
        """Get usage export job status."""
        return await self._request("GET", f"/account/usage/report/{job_id}/status", api_version="v1")

    async def get_usage_export_result(self, job_id: str) -> Dict[str, Any]:
        """Get usage export result (download URL when job is complete)."""
        status = await self.get_usage_export_status(job_id)
        if status.get("status") == "Success":
            return status
        else:
            return {"status": status.get("status", "Unknown"), "job_id": job_id}

    async def get_estimated_log_search_usage(
        self,
        query: str,
        from_time: int,
        to_time: int,
        time_zone: str = "UTC",
        by_view: bool = True
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
                "from": {
                    "type": "EpochTimeRangeBoundary",
                    "epochMillis": from_time
                },
                "to": {
                    "type": "EpochTimeRangeBoundary",
                    "epochMillis": to_time
                }
            },
            "timezone": time_zone
        }

        endpoint = "/logSearches/estimatedUsageByView" if by_view else "/logSearches/estimatedUsage"
        return await self._request("POST", endpoint, api_version="v1", json=data)


# Client pool - maps instance name to client
clients: Dict[str, SumoLogicClient] = {}


async def get_sumo_client(instance: str = 'default') -> SumoLogicClient:
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
                details=str(e)
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
        return json.dumps({
            "error": "An unexpected error occurred",
            "details": "Check server logs for more information"
        }, indent=2)


# MCP Tools

@mcp.tool()
async def search_sumo_logs(
    query: str = Field(description="Sumo Logic search query"),
    hours_back: int = Field(default=1, description="Number of hours to search back from now (ignored if from_time/to_time provided)"),
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    time_zone: str = "UTC",
    by_receipt_time: bool = False,
    instance: str = Field(default='default', description="Sumo Logic instance name")
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

        results = await client.search_logs(
            query,
            from_str,
            to_str,
            time_zone,
            by_receipt_time
        )

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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
            query,
            from_time,
            to_time,
            time_zone,
            by_receipt_time
        )

        return json.dumps(job_info, indent=2)

    except Exception as e:
        return handle_tool_error(e, "create_sumo_search_job")


@mcp.tool()
async def get_sumo_search_job_status(
    job_id: str = Field(description="Search job ID"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
            message_count = status.get("messageCount", 0)

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
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of Sumo Logic collectors."""
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_collectors")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        collectors = await client.get_collectors(limit=limit)
        return json.dumps(collectors, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_collectors")


@mcp.tool()
async def get_sumo_sources(
    collector_id: int = Field(description="Collector ID to get sources for"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get sources for a specific Sumo Logic collector."""
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of Sumo Logic users."""
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    content_path: str = Field(description="Full library path (e.g., /Library/Users/user@email.com/MyFolder)"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
        job_id = job_response['id']

        # Poll for completion
        result = await poll_export_job(
            job_id=job_id,
            content_id=content_id,
            get_status_func=lambda cid, jid: client.get_content_export_status(cid, jid),
            get_result_func=lambda cid, jid: client.get_content_export_result(cid, jid),
            max_wait_seconds=max_wait_seconds
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_content")


@mcp.tool()
async def export_global_folder(
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Export Global folder contents (async).

    IMPORTANT: Global folder uses 'data' array instead of 'children' for its contents.
    This is different from other folders and Admin Recommended.

    Set is_admin_mode=true to see more content (requires admin permissions).
    """
    try:
        from .async_export_helper import poll_folder_export_job

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_global_folder")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Start export job
        job_response = await client.begin_global_folder_export(is_admin_mode)
        job_id = job_response['id']

        # Poll for completion
        result = await poll_folder_export_job(
            job_id=job_id,
            folder_type="Global folder",
            get_status_func=lambda jid: client.get_global_folder_export_status(jid),
            get_result_func=lambda jid: client.get_global_folder_export_result(jid),
            max_wait_seconds=max_wait_seconds
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_global_folder")


@mcp.tool()
async def export_admin_recommended_folder(
    is_admin_mode: bool = False,
    max_wait_seconds: int = 300,
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Export Admin Recommended folder (async).

    Returns admin-curated content. Unlike Global folder, this uses 'children' array.
    Set is_admin_mode=true to see more content (requires admin permissions).
    """
    try:
        from .async_export_helper import poll_folder_export_job

        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("export_admin_recommended_folder")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Start export job
        job_response = await client.begin_admin_recommended_export(is_admin_mode)
        job_id = job_response['id']

        # Poll for completion
        result = await poll_folder_export_job(
            job_id=job_id,
            folder_type="Admin Recommended folder",
            get_status_func=lambda jid: client.get_admin_recommended_export_status(jid),
            get_result_func=lambda jid: client.get_admin_recommended_export_result(jid),
            max_wait_seconds=max_wait_seconds
        )

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "export_admin_recommended_folder")


@mcp.tool()
async def get_sumo_dashboards(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of Sumo Logic dashboards."""
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_dashboards")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        dashboards = await client.get_dashboards(limit=limit)
        return json.dumps(dashboards, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_dashboards")


@mcp.tool()
async def query_sumo_metrics(
    query: str = Field(description="Metrics query (e.g., metric=CPU_User | avg by host)"),
    hours_back: int = Field(default=1, description="Number of hours to query back from now"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Search for monitors and monitor folders.

    Query examples:
    - 'Test' - Search for monitors containing 'Test'
    - 'createdBy:000000000000968B' - Search by creator ID
    - 'monitorStatus:Normal' - Search by status
    - 'name:*error*' - Search monitors with 'error' in name
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
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of partitions."""
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
async def list_sumo_instances() -> str:
    """List all configured Sumo Logic instances."""
    try:
        _ensure_config_initialized()
        config = get_config()
        instances = config.list_instances()
        return json.dumps({
            "instances": instances,
            "count": len(instances)
        }, indent=2)
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
    include_raw_data: bool = False,
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Run a search audit query to analyze search usage and performance.

    Search audit queries the special index _view=sumologic_search_usage_per_query
    to provide insights into search patterns, data scanned, execution time, etc.

    Aggregates search usage metrics by user, query, query type, and content.
    Calculates data scanned (including Infrequent and Flex tiers), runtime,
    time range, partitions scanned, and result counts.

    Parameters:
        from_time: Start time (relative like '-24h' or ISO8601)
        to_time: End time (relative like 'now' or ISO8601)
        query_type: Filter by query type (* for all, Interactive, Scheduled, etc.)
        user_name: Filter by username (* for all, use wildcards like 'john*')
        content_name: Filter by content name (* for all)
        query_filter: Filter by query text (* for all)
        query_regex: Regex pattern to filter queries (default: '.*' for all)
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
        - Expensive searches: query_regex='.*\| count.*' (searches with count operator)

    Reference: https://www.sumologic.com/help/docs/manage/security/audit-indexes/search-audit-index/
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("run_search_audit_query")

        instance = validate_instance_name(instance)
        client = await get_sumo_client(instance)

        # Build search audit query
        query = f"""_view=sumologic_search_usage_per_query
query_type={query_type}
user_name={user_name}
content_name={content_name}
query={query_filter}

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

        # Create search job
        job_response = await client.create_search_job(
            query=query,
            from_time=from_time,
            to_time=to_time,
            timezone_str="UTC"
        )

        job_id = job_response['id']

        # Poll for completion with timeout
        max_attempts = 300  # 5 minutes
        for attempt in range(max_attempts):
            await asyncio.sleep(1)

            status = await client.get_search_job_status(job_id)
            state = status['state']

            if state == 'DONE GATHERING RESULTS':
                break
            elif state == 'CANCELLED':
                raise APIError("Search job was cancelled")

        # Get records (aggregated results)
        records_response = await client.get_search_job_records(job_id, limit=10000)
        records = records_response.get('records', [])

        # Delete the job
        try:
            await client.delete_search_job(job_id)
        except:
            pass  # Best effort cleanup

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
                "query_regex": query_regex
            },
            "summary": {
                "total_records": len(records),
                "total_searches": sum(safe_int(r.get('map', {}).get('searches', 0)) for r in records),
                "total_scan_gb": sum(safe_float(r.get('map', {}).get('scan_gb', 0)) for r in records),
                "total_inf_scan_gb": sum(safe_float(r.get('map', {}).get('inf_scan_gb', 0)) for r in records),
                "total_flex_scan_gb": sum(safe_float(r.get('map', {}).get('flex_scan_gb', 0)) for r in records),
            },
            "records": []
        }

        # Process records
        for record in records:
            record_map = record.get('map', {})
            processed_record = {
                "user_name": record_map.get('user_name'),
                "query_type": record_map.get('query_type'),
                "content_name": record_map.get('content_name'),
                "content_identifier": record_map.get('content_identifier'),
                "query": record_map.get('query'),
                "searches": safe_int(record_map.get('searches', 0)),
                "scan_gb": safe_float(record_map.get('scan_gb', 0)),
                "inf_scan_gb": safe_float(record_map.get('inf_scan_gb', 0)),
                "flex_scan_gb": safe_float(record_map.get('flex_scan_gb', 0)),
                "results": safe_int(record_map.get('results', 0)),
                "avg_partitions": safe_float(record_map.get('avg_partitions', 0)),
                "avg_range_h": safe_float(record_map.get('avg_range_h', 0)),
                "sum_runtime_minutes": safe_float(record_map.get('sum_runtime_minutes', 0)),
                "avg_runtime_minutes": safe_float(record_map.get('avg_runtime_minutes', 0)),
            }

            if include_raw_data:
                processed_record['_raw'] = record

            result["records"].append(processed_record)

        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_tool_error(e, "run_search_audit_query")


# Content ID Utility Tools

@mcp.tool()
async def convert_content_id_hex_to_decimal(
    hex_id: str = Field(description="Hex content ID (e.g., 00000000005E5403)")
) -> str:
    """
    Convert hex content ID to decimal format for web UI URLs.

    Sumo Logic stores content IDs as 16-character hex strings but the
    web UI uses decimal format in URLs. Use this to generate shareable links.

    Example: 00000000005E5403 → 6181891
    """
    try:
        from .content_id_utils import hex_to_decimal, format_content_id

        decimal_id = hex_to_decimal(hex_id)

        return json.dumps({
            "hex_id": hex_id.upper(),
            "decimal_id": decimal_id,
            "formatted": format_content_id(hex_id)
        }, indent=2)

    except Exception as e:
        return handle_tool_error(e, "convert_content_id_hex_to_decimal")


@mcp.tool()
async def convert_content_id_decimal_to_hex(
    decimal_id: str = Field(description="Decimal content ID (e.g., 6181891)")
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

        return json.dumps({
            "hex_id": hex_id,
            "decimal_id": decimal_id,
            "formatted": format_content_id(hex_id)
        }, indent=2)

    except Exception as e:
        return handle_tool_error(e, "convert_content_id_decimal_to_hex")


@mcp.tool()
async def get_content_web_url(
    content_id: str = Field(description="Content ID (hex or decimal)"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Generate web UI URL for a content item.

    Accepts either hex or decimal content ID and generates the appropriate
    web UI URL for the specified instance.

    Returns a URL like: https://instance.sumologic.com/library/6181891
    """
    try:
        from .content_id_utils import hex_to_decimal, is_valid_hex_id, normalize_to_hex

        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Normalize to hex, then convert to decimal for URL
        hex_id = normalize_to_hex(content_id)
        decimal_id = hex_to_decimal(hex_id)

        # Get instance endpoint
        instance_config = config.get_instance(instance)
        base_url = instance_config.endpoint.rstrip('/')

        # Remove /api suffix if present
        if base_url.endswith('/api'):
            base_url = base_url[:-4]

        # Construct library URL
        url = f"{base_url}/library/{decimal_id}"

        return json.dumps({
            "url": url,
            "hex_id": hex_id,
            "decimal_id": decimal_id,
            "instance": instance
        }, indent=2)

    except Exception as e:
        return handle_tool_error(e, "get_content_web_url")


# Account Management Tools

@mcp.tool()
async def get_account_status(
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
    number_of_days: int = Field(description="Number of days to forecast (e.g., 7, 30, 90)"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
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
        number_of_days: Number of days to forecast (typically 7, 30, or 90)

    API Reference: https://api.sumologic.com/docs/#operation/getUsageForecast
    """
    try:
        _ensure_config_initialized()
        config = get_config()
        instance = validate_instance_name(instance)

        # Validate number_of_days
        if number_of_days < 1 or number_of_days > 365:
            raise ValidationError("number_of_days must be between 1 and 365")

        client = await get_sumo_client(instance)
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)

        await limiter.acquire("get_usage_forecast")
        result = await client.get_usage_forecast(number_of_days)

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
    instance: str = 'default'
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
            include_deployment_charge=include_deployment_charge
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
            poll_interval_seconds=poll_interval_seconds
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
            "instance": instance
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
    instance: str = 'default'
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
            by_view=by_view
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
    relative_pattern = r'^([+-]?)(\d+)([smhdw])$'
    match = re.match(relative_pattern, time_str.lower())

    if match:
        sign, amount, unit = match.groups()
        amount = int(amount)

        # Default to negative if no sign specified (going back in time)
        if sign != '+':
            amount = -amount

        # Convert unit to timedelta
        unit_map = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days',
            'w': 'weeks'
        }

        if unit in unit_map:
            delta_kwargs = {unit_map[unit]: amount}
            target_time = datetime.now(timezone.utc) + timedelta(**delta_kwargs)
            return int(target_time.timestamp() * 1000)

    # Try to parse as ISO format
    try:
        for fmt in [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
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

    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
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
    instance: str = 'default'
) -> str:
    """
    Explore log metadata values for a given scope to help build efficient queries.

    This tool helps you discover:
    - Which partitions/views (_view, _index) contain your logs
    - What source categories (_sourceCategory) exist in your scope
    - Mapping of collectors, sources, and other metadata dimensions
    - Message counts per metadata combination

    Use this to learn your log structure before building queries, especially important
    for Flex/Infrequent tier accounts where scan volume affects cost.

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
            raise ValidationError(f"sort_by field '{sort_by}' must be one of the metadata fields: {metadata_fields}")

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
            by_receipt_time=False
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
                    job_id=search_id,
                    limit=max_results,
                    offset=0
                )

                # Format response
                records = results.get("records", [])
                total_records = len(records)
                total_messages = sum(
                    int(record.get("map", {}).get("_count", 0))
                    for record in records
                )

                # Build formatted output
                output = {
                    "scope": scope,
                    "metadata_fields": fields,
                    "time_range": {
                        "from": from_time,
                        "to": to_time,
                        "timezone": time_zone
                    },
                    "summary": {
                        "unique_combinations": total_records,
                        "total_messages": total_messages,
                        "truncated": total_records >= max_results
                    },
                    "metadata": []
                }

                # Extract and format metadata
                for record in records:
                    record_map = record.get("map", {})

                    # Debug: log the first record's keys to understand field naming
                    if len(output["metadata"]) == 0 and record_map:
                        logger.debug(f"First record keys: {list(record_map.keys())}")

                    metadata_entry = {
                        "count": int(record_map.get("_count", 0))
                    }

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


# MCP Resources

@mcp.resource("sumo://logs/recent-errors")
async def recent_errors() -> str:
    """Get recent error logs from the last hour from default instance."""
    try:
        client = await get_sumo_client('default')

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
        client = await get_sumo_client('default')
        collectors = await client.get_collectors()
        return json.dumps(collectors, indent=2)
    except Exception as e:
        return handle_tool_error(e, "collectors_config")


# MCP Prompts (keeping original prompts)

@mcp.prompt()
async def analyze_logs_prompt(
    error_type: str = Field(description="Type of error to analyze")
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
        if 'loop' in locals():
            loop.run_until_complete(cleanup())
            loop.close()


if __name__ == "__main__":
    main()
