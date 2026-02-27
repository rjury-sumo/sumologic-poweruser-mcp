#!/usr/bin/env python3
"""Test auto-detection of Flex vs Tiered org in analyze_search_scan_cost."""
import asyncio
import json
from sumologic_mcp_server.sumologic_mcp_server import analyze_search_scan_cost


async def main():
    print("=" * 80)
    print("Test 1: Auto-detection (default)")
    print("=" * 80)

    result = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        group_by="user",
        limit=5
    )

    data = json.loads(result)
    print("\nQuery Parameters:")
    print(json.dumps(data["query_parameters"], indent=2))

    print("\nSummary:")
    print(json.dumps(data["summary"], indent=2))

    if "warning" in data:
        print("\n⚠️  WARNING DETECTED:")
        print(json.dumps(data["warning"], indent=2))

    print("\n" + "=" * 80)
    print("Test 2: Explicit 'tier' on Tiered org (should work)")
    print("=" * 80)

    result2 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="tier",
        group_by="user",
        limit=5
    )

    data2 = json.loads(result2)
    print("\nQuery Parameters:")
    print(json.dumps(data2["query_parameters"], indent=2))

    print("\nSummary:")
    print(json.dumps(data2["summary"], indent=2))

    if "warning" in data2:
        print("\n⚠️  WARNING DETECTED:")
        print(json.dumps(data2["warning"], indent=2))

    print("\n" + "=" * 80)
    print("Test 3: Explicit 'metering' (should work on any org)")
    print("=" * 80)

    result3 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="metering",
        group_by="user",
        limit=5
    )

    data3 = json.loads(result3)
    print("\nQuery Parameters:")
    print(json.dumps(data3["query_parameters"], indent=2))

    print("\nSummary:")
    print(json.dumps(data3["summary"], indent=2))

    if "billable_scan_gb" in data3["summary"]:
        print(f"\n✅ Metering breakdown includes billable scan: {data3['summary']['total_billable_scan_gb']} GB")

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
