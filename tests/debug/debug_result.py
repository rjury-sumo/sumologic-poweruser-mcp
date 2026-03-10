#!/usr/bin/env python3
"""Debug: check what is actually returned."""

import asyncio
import json

from src.sumologic_poweruser_mcp.sumologic_poweruser_mcp import run_search_audit_query


async def main():
    result = await run_search_audit_query(
        from_time="-1h",
        to_time="now",
        scope_filters=["query_type=Interactive"],
        instance="default"
    )

    print("="*80)
    print("RAW RESULT:")
    print("="*80)
    print(result)
    print("="*80)

    try:
        data = json.loads(result)
        print("\nPARSED JSON:")
        print(json.dumps(data, indent=2)[:500])
    except:
        print("\nNot valid JSON")

if __name__ == "__main__":
    asyncio.run(main())
