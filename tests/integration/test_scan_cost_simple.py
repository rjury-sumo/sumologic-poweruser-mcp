#!/usr/bin/env python3
"""Simple test of analyze_search_scan_cost tool."""
import asyncio
import json

from sumologic_mcp_server.sumologic_mcp_server import analyze_search_scan_cost


async def main():
    print("Testing Flex metering breakdown...")
    try:
        result = await analyze_search_scan_cost(
            from_time="-7d",
            to_time="now",
            breakdown_type="metering",
            group_by="user",
            scan_credit_rate=0.018,
            sort_by="scan_credits",
            limit=10
        )

        print("Result:")
        print(result)

        result_data = json.loads(result)
        print("\nParsed successfully!")
        print(f"Total records: {result_data.get('summary', {}).get('total_records', 0)}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
