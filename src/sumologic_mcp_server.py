#!/usr/bin/env python3
"""
Sumo Logic MCP Server

This server provides read-only access to Sumo Logic APIs through the Model Context Protocol.
It exposes tools for searching logs, querying metrics, and retrieving account information.

Usage:
    python sumologic_mcp_server.py

Environment Variables Required:
    SUMO_ACCESS_ID: Your Sumo Logic Access ID
    SUMO_ACCESS_KEY: Your Sumo Logic Access Key
    SUMO_ENDPOINT: Your Sumo Logic API base endpoint (e.g., https://api.us2.sumologic.com)
"""

import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP("Sumo Logic")

class SumoLogicClient:
    """Client for interacting with Sumo Logic APIs."""
    
    def __init__(self, access_id: str, access_key: str, endpoint: str):
        self.access_id = access_id
        self.access_key = access_key
        self.endpoint = endpoint.rstrip('/')
        self.session = httpx.AsyncClient(
            auth=(access_id, access_key),
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
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    async def search_logs(self, query: str, from_time: str, to_time: str, timezone: str = "UTC") -> Dict[str, Any]:
        """Create a search job and return results."""
        # Create search job
        search_data = {
            "query": query,
            "from": from_time,
            "to": to_time,
            "timeZone": timezone
        }
        
        job_response = await self._request("POST", "/search/jobs", api_version="v1", json=search_data)
        job_id = job_response["id"]
        
        # Poll for completion
        max_attempts = 60  # 5 minutes max wait
        for attempt in range(max_attempts):
            status_response = await self._request("GET", f"/search/jobs/{job_id}", api_version="v1")
            state = status_response["state"]
            
            if state == "DONE GATHERING RESULTS":
                # Get results
                results_response = await self._request("GET", f"/search/jobs/{job_id}/messages", api_version="v1")
                return {
                    "job_id": job_id,
                    "state": state,
                    "message_count": status_response.get("messageCount", 0),
                    "record_count": status_response.get("recordCount", 0),
                    "results": results_response.get("messages", [])
                }
            elif state in ["CANCELLED", "FORCE PAUSED"]:
                return {"job_id": job_id, "state": state, "error": "Search was cancelled or paused"}
            
            await asyncio.sleep(5)  # Wait 5 seconds before checking again
        
        return {"job_id": job_id, "state": "TIMEOUT", "error": "Search timed out"}

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
        return await self._request("GET", "/content/folders/global", api_version="v1", params=params)

    async def get_dashboards(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get list of dashboards."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/dashboards", api_version="v1", params=params)

    async def query_metrics(self, query: str, from_time: str, to_time: str) -> Dict[str, Any]:
        """Query metrics using the metrics API."""
        metrics_data = {
            "query": [{"query": query, "rowId": "A"}],
            "startTime": int(datetime.fromisoformat(from_time.replace('Z', '+00:00')).timestamp() * 1000),
            "endTime": int(datetime.fromisoformat(to_time.replace('Z', '+00:00')).timestamp() * 1000),
            "requestId": f"mcp-{datetime.now().isoformat()}",
            "maxDataPoints": 800
        }
        return await self._request("POST", "/metrics/results", api_version="v1", json=metrics_data)

    # V2 API endpoints
    async def get_content_v2(self, content_type: str = "Dashboard", limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get content using the v2 content API."""
        params = {
            "type": content_type,
            "limit": limit,
            "offset": offset
        }
        return await self._request("GET", "/content", api_version="v2", params=params)

    async def get_roles_v2(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get roles using the v2 roles API."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/roles", api_version="v2", params=params)

    async def get_monitors_v2(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get monitors using the v2 monitors API."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/monitors", api_version="v2", params=params)

    async def get_partitions_v2(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get partitions using the v2 partitions API."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/partitions", api_version="v2", params=params)

    async def get_lookup_tables_v2(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get lookup tables using the v2 lookup tables API."""
        params = {"limit": limit, "offset": offset}
        return await self._request("GET", "/lookupTables", api_version="v2", params=params)

# Global client instance
sumo_client: Optional[SumoLogicClient] = None

async def get_sumo_client() -> SumoLogicClient:
    """Get or create the Sumo Logic client."""
    global sumo_client
    if sumo_client is None:
        access_id = os.getenv("SUMO_ACCESS_ID")
        access_key = os.getenv("SUMO_ACCESS_KEY")
        endpoint = os.getenv("SUMO_ENDPOINT", "https://api.sumologic.com")
        
        if not access_id or not access_key:
            raise ValueError("SUMO_ACCESS_ID and SUMO_ACCESS_KEY environment variables are required")
        
        sumo_client = SumoLogicClient(access_id, access_key, endpoint)
    
    return sumo_client

# MCP Tools

@mcp.tool()
async def search_sumo_logs(
    query: str = Field(description="Sumo Logic search query"),
    hours_back: int = Field(default=1, description="Number of hours to search back from now"),
    timezone: str = Field(default="UTC", description="Timezone for the search")
) -> str:
    """
    Search Sumo Logic logs using a query.
    
    Example queries:
    - _sourceCategory=apache/access
    - error | count by _sourceHost
    - _sourceCategory=prod/app | where level="ERROR"
    """
    try:
        client = await get_sumo_client()
        
        # Calculate time range
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours_back)
        
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        results = await client.search_logs(query, from_str, to_str, timezone)
        
        return json.dumps(results, indent=2)
    
    except Exception as e:
        return f"Error searching logs: {str(e)}"

@mcp.tool()
async def get_sumo_collectors() -> str:
    """Get list of Sumo Logic collectors."""
    try:
        client = await get_sumo_client()
        collectors = await client.get_collectors()
        return json.dumps(collectors, indent=2)
    except Exception as e:
        return f"Error getting collectors: {str(e)}"

@mcp.tool()
async def get_sumo_sources(collector_id: int = Field(description="Collector ID to get sources for")) -> str:
    """Get sources for a specific Sumo Logic collector."""
    try:
        client = await get_sumo_client()
        sources = await client.get_sources(collector_id)
        return json.dumps(sources, indent=2)
    except Exception as e:
        return f"Error getting sources: {str(e)}"

@mcp.tool()
async def get_sumo_users() -> str:
    """Get list of Sumo Logic users."""
    try:
        client = await get_sumo_client()
        users = await client.get_users()
        return json.dumps(users, indent=2)
    except Exception as e:
        return f"Error getting users: {str(e)}"

@mcp.tool()
async def get_sumo_folders() -> str:
    """Get list of Sumo Logic content folders."""
    try:
        client = await get_sumo_client()
        folders = await client.get_folders()
        return json.dumps(folders, indent=2)
    except Exception as e:
        return f"Error getting folders: {str(e)}"

@mcp.tool()
async def get_sumo_dashboards() -> str:
    """Get list of Sumo Logic dashboards."""
    try:
        client = await get_sumo_client()
        dashboards = await client.get_dashboards()
        return json.dumps(dashboards, indent=2)
    except Exception as e:
        return f"Error getting dashboards: {str(e)}"

@mcp.tool()
async def query_sumo_metrics(
    query: str = Field(description="Metrics query (e.g., metric=CPU_User | avg by host)"),
    hours_back: int = Field(default=1, description="Number of hours to query back from now")
) -> str:
    """
    Query Sumo Logic metrics.
    
    Example queries:
    - metric=CPU_User | avg by host
    - metric=Memory_Used | max
    - metric=Disk_Used_Percent | where host="web-server-1"
    """
    try:
        client = await get_sumo_client()
        
        # Calculate time range
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=hours_back)
        
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        results = await client.query_metrics(query, from_str, to_str)
        return json.dumps(results, indent=2)
    
    except Exception as e:
        return f"Error querying metrics: {str(e)}"

# V2 API Tools

@mcp.tool()
async def get_sumo_content_v2(
    content_type: str = Field(default="Dashboard", description="Type of content (Dashboard, Search, Folder, etc.)"),
    limit: int = Field(default=100, description="Maximum number of items to return")
) -> str:
    """Get content using the v2 Content API. Supports Dashboard, Search, Folder, and other content types."""
    try:
        client = await get_sumo_client()
        content = await client.get_content_v2(content_type, limit)
        return json.dumps(content, indent=2)
    except Exception as e:
        return f"Error getting content: {str(e)}"

@mcp.tool()
async def get_sumo_roles_v2() -> str:
    """Get list of roles using the v2 Roles API."""
    try:
        client = await get_sumo_client()
        roles = await client.get_roles_v2()
        return json.dumps(roles, indent=2)
    except Exception as e:
        return f"Error getting roles: {str(e)}"

@mcp.tool()
async def get_sumo_monitors_v2() -> str:
    """Get list of monitors using the v2 Monitors API."""
    try:
        client = await get_sumo_client()
        monitors = await client.get_monitors_v2()
        return json.dumps(monitors, indent=2)
    except Exception as e:
        return f"Error getting monitors: {str(e)}"

@mcp.tool()
async def get_sumo_partitions_v2() -> str:
    """Get list of partitions using the v2 Partitions API."""
    try:
        client = await get_sumo_client()
        partitions = await client.get_partitions_v2()
        return json.dumps(partitions, indent=2)
    except Exception as e:
        return f"Error getting partitions: {str(e)}"

@mcp.tool()
async def get_sumo_lookup_tables_v2() -> str:
    """Get list of lookup tables using the v2 Lookup Tables API."""
    try:
        client = await get_sumo_client()
        lookup_tables = await client.get_lookup_tables_v2()
        return json.dumps(lookup_tables, indent=2)
    except Exception as e:
        return f"Error getting lookup tables: {str(e)}"

# MCP Resources

@mcp.resource("sumo://logs/recent-errors")
async def recent_errors() -> str:
    """Get recent error logs from the last hour."""
    try:
        client = await get_sumo_client()
        
        to_time = datetime.utcnow()
        from_time = to_time - timedelta(hours=1)
        
        from_str = from_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        to_str = to_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        results = await client.search_logs("error OR ERROR OR Error", from_str, to_str)
        return json.dumps(results, indent=2)
    
    except Exception as e:
        return f"Error getting recent errors: {str(e)}"

@mcp.resource("sumo://config/collectors")
async def collectors_config() -> str:
    """Get current collector configuration."""
    try:
        client = await get_sumo_client()
        collectors = await client.get_collectors()
        return json.dumps(collectors, indent=2)
    except Exception as e:
        return f"Error getting collector config: {str(e)}"

# MCP Prompts

@mcp.prompt()
async def analyze_logs_prompt(
    error_type: str = Field(description="Type of error to analyze (e.g., 'database', 'api', 'authentication')")
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
    global sumo_client
    if sumo_client:
        await sumo_client.close()

# Initialize client on startup
async def initialize_client():
    """Initialize the Sumo Logic client and test connection."""
    try:
        client = await get_sumo_client()
        logger.info("Sumo Logic MCP Server initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Sumo Logic client: {str(e)}")
        raise

# Run the server
def main():
    try:
        # Test connection on startup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(initialize_client())
        
        logger.info("Sumo Logic MCP Server starting...")
        
        # Run the FastMCP server (this is synchronous)
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise
    finally:
        # Clean up
        if 'loop' in locals():
            loop.run_until_complete(cleanup())
            loop.close()

if __name__ == "__main__":
    main()