#!/usr/bin/env python3
"""Test estimated log search usage tool."""
import asyncio
import json

from sumologic_mcp_server.sumologic_mcp_server import get_estimated_log_search_usage


async def main():
    """Test the estimated usage tool."""
    print("Testing get_estimated_log_search_usage...\n")

    # Test 1: Simple query with last 1 hour
    print("Test 1: Estimate usage for _sourceCategory=* (last 1 hour)")
    result = await get_estimated_log_search_usage(
        query="_sourceCategory=*",
        from_time="-1h",
        to_time="now",
        time_zone="UTC",
        by_view=True,
        instance="default"
    )

    result_dict = json.loads(result)

    if "error" in result_dict:
        print(f"❌ Error: {result_dict['error']}")
        return False

    print("✓ Success!")
    print(f"  Total estimated: {result_dict.get('formatted_total', 'N/A')}")
    print(f"  Run by receipt time: {result_dict.get('runByReceiptTime', 'N/A')}")

    if "estimatedUsageDetails" in result_dict:
        print(f"  Partitions/Views found: {len(result_dict['estimatedUsageDetails'])}")
        print("\n  Breakdown:")
        for detail in result_dict["estimatedUsageDetails"][:5]:  # Show first 5
            view_name = detail.get("viewName", "unknown")
            size = detail.get("formatted_size", "N/A")
            data_tier = detail.get("dataTier", "N/A")
            metering_tier = detail.get("meteringTier", "N/A")
            print(f"    - {view_name}: {size} ({data_tier}/{metering_tier})")

        if len(result_dict["estimatedUsageDetails"]) > 5:
            print(f"    ... and {len(result_dict['estimatedUsageDetails']) - 5} more")

    print("\n" + "="*60)

    # Test 2: Query with specific source category, last 24 hours
    print("\nTest 2: Estimate usage for specific view (last 24 hours)")
    result2 = await get_estimated_log_search_usage(
        query="_view=sumologic*",
        from_time="-24h",
        to_time="now",
        by_view=True,
        instance="default"
    )

    result2_dict = json.loads(result2)

    if "error" in result2_dict:
        print(f"❌ Error: {result2_dict['error']}")
        return False

    print("✓ Success!")
    print(f"  Total estimated: {result2_dict.get('formatted_total', 'N/A')}")

    if "estimatedUsageDetails" in result2_dict:
        print(f"  Partitions/Views found: {len(result2_dict['estimatedUsageDetails'])}")

    print("\n" + "="*60)
    print("\n✓ All tests passed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
