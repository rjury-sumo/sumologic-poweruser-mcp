#!/usr/bin/env python3
"""Test the updated Flex metering breakdown with TB values and no credits."""
import asyncio
import json

from sumologic_poweruser_mcp.sumologic_mcp_server import analyze_search_scan_cost


async def main():
    print("=" * 80)
    print("Test 1: Tier Breakdown (Infrequent) - SHOULD include credits")
    print("=" * 80)

    result1 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="tier",
        group_by="user",
        limit=3
    )

    data1 = json.loads(result1)
    print("\nSummary:")
    print(json.dumps(data1["summary"], indent=2))

    if "total_scan_credits" in data1["summary"]:
        print("\n✅ Credits included for tier breakdown")
    else:
        print("\n❌ ERROR: Credits missing for tier breakdown")

    if data1["records"]:
        print("\nFirst Record:")
        print(json.dumps(data1["records"][0], indent=2))
        if "scan_credits" in data1["records"][0]:
            print("✅ Record includes scan_credits")
        else:
            print("❌ ERROR: Record missing scan_credits")

    print("\n" + "=" * 80)
    print("Test 2: Metering Breakdown (Flex) - Should NOT include credits, SHOULD include TB")
    print("=" * 80)

    result2 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="metering",
        group_by="user",
        limit=3
    )

    data2 = json.loads(result2)
    print("\nSummary:")
    print(json.dumps(data2["summary"], indent=2))

    if "total_scan_credits" in data2["summary"]:
        print("\n❌ ERROR: Credits should NOT be in metering breakdown summary")
    else:
        print("\n✅ Credits correctly excluded from metering breakdown summary")

    if "total_billable_scan_tb" in data2["summary"]:
        print(f"✅ TB value included: {data2['summary']['total_billable_scan_tb']} TB")
    else:
        print("❌ ERROR: TB value missing from summary")

    if "flex_billing_note" in data2["summary"]:
        print(f"✅ Billing note included: {data2['summary']['flex_billing_note']}")
    else:
        print("❌ ERROR: flex_billing_note missing")

    if data2["records"]:
        print("\nFirst Record:")
        print(json.dumps(data2["records"][0], indent=2))

        if "scan_credits" in data2["records"][0]:
            print("❌ ERROR: Record should NOT include scan_credits for metering")
        else:
            print("✅ scan_credits correctly excluded from record")

        if "billable_scan_tb" in data2["records"][0]:
            print(f"✅ Record includes billable_scan_tb: {data2['records'][0]['billable_scan_tb']} TB")
        else:
            print("❌ ERROR: billable_scan_tb missing from record")

    print("\n" + "=" * 80)
    print("Test 3: Auto-detection")
    print("=" * 80)

    result3 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="auto",
        group_by="user",
        limit=3
    )

    data3 = json.loads(result3)

    detected_type = data3["query_parameters"].get("detected_org_type", "Unknown")
    breakdown_used = data3["query_parameters"]["breakdown_type"]

    print(f"\nDetected org type: {detected_type}")
    print(f"Breakdown type used: {breakdown_used}")

    if breakdown_used == "tier" and "total_scan_credits" in data3["summary"]:
        print("✅ Tier breakdown includes credits")
    elif breakdown_used == "metering" and "total_billable_scan_tb" in data3["summary"]:
        print("✅ Metering breakdown includes TB values")
    else:
        print("❌ Auto-detection produced unexpected result")

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
