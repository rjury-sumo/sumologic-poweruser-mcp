#!/usr/bin/env python3
"""Test data volume analysis tool."""
import asyncio
import json
from sumologic_mcp_server.sumologic_mcp_server import analyze_data_volume


async def main():
    """Test the data volume analysis tool."""
    print("Testing analyze_data_volume...\n")

    # Test 1: Basic analysis by sourceCategory (last 24 hours)
    print("Test 1: Basic sourceCategory analysis (last 24h, with credits)")
    result = await analyze_data_volume(
        dimension="sourceCategory",
        from_time="-24h",
        to_time="now",
        include_credits=True,
        include_timeshift=False,
        sort_by="gbytes",
        limit=10,
        instance="default"
    )

    result_dict = json.loads(result)

    if "error" in result_dict:
        print(f"❌ Error: {result_dict['error']}")
        return False

    print("✓ Success!")
    print(f"  Dimension: {result_dict.get('dimension')}")
    print(f"  Total records: {result_dict.get('summary', {}).get('total_records', 0)}")

    # Show first few entries
    data = result_dict.get("data", [])
    if data:
        print("\n  Sample entries (top consumers):")
        for entry in data[:3]:
            sc = entry.get("sourceCategory", "N/A")
            tier = entry.get("dataTier", "N/A")
            gb = entry.get("gbytes", "0")
            events = entry.get("events", "0")
            credits = entry.get("credits", "N/A")
            print(f"    - {sc} ({tier}): {gb} GB, {events} events, {credits} credits")

    print("\n" + "="*70)

    # Test 2: Collector analysis with timeshift
    print("\nTest 2: Collector analysis with timeshift comparison (7d x 3 periods)")
    result2 = await analyze_data_volume(
        dimension="collector",
        from_time="-24h",
        to_time="now",
        include_credits=True,
        include_timeshift=True,
        timeshift_days=7,
        timeshift_periods=3,
        sort_by="credits",
        limit=5,
        instance="default"
    )

    result2_dict = json.loads(result2)

    if "error" in result2_dict:
        print(f"❌ Error: {result2_dict['error']}")
        return False

    print("✓ Success!")
    print(f"  Total records: {result2_dict.get('summary', {}).get('total_records', 0)}")

    data2 = result2_dict.get("data", [])
    if data2:
        print("\n  Sample entries with trend analysis:")
        for entry in data2[:2]:
            coll = entry.get("collector", "N/A")
            state = entry.get("state", "N/A")
            gb = entry.get("gbytes", "0")
            pct = entry.get("pct_increase_gb", "N/A")
            print(f"    - {coll}: {gb} GB, {pct}% change, state: {state}")

    print("\n" + "="*70)

    # Test 3: View/partition analysis
    print("\nTest 3: View/partition analysis (last 7 days)")
    result3 = await analyze_data_volume(
        dimension="view",
        from_time="-7d",
        to_time="now",
        include_credits=True,
        include_timeshift=False,
        sort_by="gbytes",
        limit=5,
        instance="default"
    )

    result3_dict = json.loads(result3)

    if "error" in result3_dict:
        print(f"❌ Error: {result3_dict['error']}")
        return False

    print("✓ Success!")
    print(f"  Total records: {result3_dict.get('summary', {}).get('total_records', 0)}")

    print("\n" + "="*70)
    print("\n✓ All tests completed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
