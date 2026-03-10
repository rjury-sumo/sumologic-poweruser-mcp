#!/usr/bin/env python3
"""Test legacy parameters work."""

import asyncio
import json

from src.sumologic_poweruser_mcp.sumologic_poweruser_mcp import run_search_audit_query


async def main():
    print("Testing LEGACY parameters (should work)...")
    result = await run_search_audit_query(
        from_time="-1h",
        to_time="now",
        query_type="*",
        user_name="*",
        instance="default"
    )

    data = json.loads(result)
    if "error" in data:
        print(f"ERROR: {data['error']}")
    else:
        print(f"SUCCESS: Found {data.get('summary', {}).get('total_searches', 0)} searches")

if __name__ == "__main__":
    asyncio.run(main())
