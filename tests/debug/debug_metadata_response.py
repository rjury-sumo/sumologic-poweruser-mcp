#!/usr/bin/env python3
"""Debug metadata response to check field names."""
import asyncio
import json

from sumologic_mcp_server.sumologic_mcp_server import explore_log_metadata


async def main():
    """Check raw response to see field names."""
    result = await explore_log_metadata(
        scope="*",
        from_time="-1h",
        to_time="now",
        metadata_fields="_view,_sourceCategory",
        sort_by="_sourceCategory",
        max_results=5,
        instance="default"
    )

    result_dict = json.loads(result)
    print("Full response:")
    print(json.dumps(result_dict, indent=2))

    # Check what fields are actually in the response
    if result_dict.get("metadata"):
        print("\nFirst metadata entry keys:")
        print(list(result_dict["metadata"][0].keys()))


if __name__ == "__main__":
    asyncio.run(main())
