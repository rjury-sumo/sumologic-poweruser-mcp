#!/usr/bin/env python3
"""Debug estimated usage response."""
import asyncio
import json
from sumologic_mcp_server.sumologic_mcp_server import get_estimated_log_search_usage


async def main():
    """Check raw response."""
    result = await get_estimated_log_search_usage(
        query="_sourceCategory=*",
        from_time="-1h",
        to_time="now",
        by_view=True,
        instance="default"
    )

    result_dict = json.loads(result)
    print("Full response:")
    print(json.dumps(result_dict, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
