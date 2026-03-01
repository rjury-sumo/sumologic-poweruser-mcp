#!/usr/bin/env python3
"""Simple test to debug search audit query generation."""

import asyncio
import json
import logging
from src.sumologic_mcp_server.sumologic_mcp_server import run_search_audit_query

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async def main():
    print("Testing search audit with scope filters...\n")

    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            scope_filters=["query_type=Interactive"],
            instance="default"
        )
        print("Success!")
        data = json.loads(result)
        print(f"Total searches: {data.get('summary', {}).get('total_searches', 0)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
