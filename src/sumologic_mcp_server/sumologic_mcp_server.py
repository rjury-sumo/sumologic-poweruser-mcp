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
        max_attempts: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a search job and return results."""
        if max_attempts is None:
            _ensure_config_initialized()
            config = get_config()
            max_attempts = config.server_config.max_search_timeout // 5

        # Create search job
        search_data = {
            "query": query,
            "from": from_time,
            "to": to_time,
            "timeZone": timezone_str
        }

        job_response = await self._request("POST", "/search/jobs", api_version="v1", json=search_data)
        job_id = job_response["id"]

        # Poll for completion
        for attempt in range(max_attempts):
            status_response = await self._request("GET", f"/search/jobs/{job_id}", api_version="v1")
            state = status_response["state"]

            if state == "DONE GATHERING RESULTS":
                # Get results
                results_response = await self._request(
                    "GET",
                    f"/search/jobs/{job_id}/messages",
                    api_version="v1"
                )
                return {
                    "job_id": job_id,
                    "state": state,
                    "message_count": status_response.get("messageCount", 0),
                    "record_count": status_response.get("recordCount", 0),
                    "results": results_response.get("messages", [])
                }
            elif state in ["CANCELLED", "FORCE PAUSED"]:
                raise APIError(f"Search job {job_id} was {state.lower()}")

            await asyncio.sleep(5)  # Wait 5 seconds before checking again

        raise SumoTimeoutError(
            f"Search job {job_id} timed out after {max_attempts * 5} seconds"
        )

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
    hours_back: int = Field(default=1, description="Number of hours to search back from now"),
    timezone_param: str = Field(default="UTC", description="Timezone for the search", alias="timezone"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """
    Search Sumo Logic logs using a query.

    Example queries:
    - _sourceCategory=apache/access
    - error | count by _sourceHost
    - _sourceCategory=prod/app | where level="ERROR"
    """
    try:
        # Rate limiting
        _ensure_config_initialized()
        config = get_config()
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("search_sumo_logs")

        # Validate inputs
        query = validate_query_input(query)
        hours_back = validate_time_range(hours_back)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)

        # Calculate time range
        to_time = datetime.now(timezone.utc)
        from_time = to_time - timedelta(hours=hours_back)

        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        results = await client.search_logs(query, from_str, to_str, timezone_param)

        return json.dumps(results, indent=2)

    except Exception as e:
        return handle_tool_error(e, "search_sumo_logs")


@mcp.tool()
async def get_sumo_collectors(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of Sumo Logic collectors."""
    try:
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
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_users")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        users = await client.get_users(limit=limit)
        return json.dumps(users, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_users")


@mcp.tool()
async def get_sumo_folders(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of Sumo Logic content folders."""
    try:
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_folders")

        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        folders = await client.get_folders(limit=limit)
        return json.dumps(folders, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_folders")


@mcp.tool()
async def get_sumo_dashboards(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of Sumo Logic dashboards."""
    try:
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


@mcp.tool()
async def get_sumo_content_v2(
    content_type: str = Field(default="Dashboard", description="Type of content"),
    limit: int = Field(default=100, description="Maximum number of items to return"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get content using the v2 Content API. Supports Dashboard, Search, Folder, and other content types."""
    try:
        limiter = get_rate_limiter(config.server_config.rate_limit_per_minute)
        await limiter.acquire("get_sumo_content_v2")

        validation = ContentTypeValidation(content_type=content_type)
        limit, _ = validate_pagination(limit, 0)
        instance = validate_instance_name(instance)

        client = await get_sumo_client(instance)
        content = await client.get_content_v2(validation.content_type, limit)
        return json.dumps(content, indent=2)
    except Exception as e:
        return handle_tool_error(e, "get_sumo_content_v2")


@mcp.tool()
async def get_sumo_roles_v2(
    limit: int = Field(default=100, description="Maximum number of results"),
    instance: str = Field(default='default', description="Sumo Logic instance name")
) -> str:
    """Get list of roles using the v2 Roles API."""
    try:
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
        instances = config.list_instances()
        return json.dumps({
            "instances": instances,
            "count": len(instances)
        }, indent=2)
    except Exception as e:
        return handle_tool_error(e, "list_sumo_instances")


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
