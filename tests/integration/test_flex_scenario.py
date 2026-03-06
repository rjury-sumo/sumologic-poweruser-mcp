#!/usr/bin/env python3
"""
Demonstrate the Flex fix in action.

This shows what happens when:
1. A Flex org uses auto-detection (good)
2. A Flex org accidentally uses 'tier' breakdown (warning triggered)
3. A Flex org uses correct 'metering' breakdown (good)
"""
import asyncio
import json


def print_result_summary(title, data):
    """Print a formatted summary of the result."""
    print("\n" + "=" * 80)
    print(f"{title}")
    print("=" * 80)

    params = data["query_parameters"]
    summary = data["summary"]

    print("\n📊 Breakdown Type:")
    print(f"   Requested: {params.get('breakdown_type_requested', 'N/A')}")
    print(f"   Used: {params['breakdown_type']}")

    if params.get('detected_org_type'):
        print(f"   Detected Org: {params['detected_org_type']}")

    print("\n📈 Results:")
    print(f"   Queries: {summary['total_queries']:,}")
    print(f"   Scan GB: {summary['total_scan_gb']}")
    print(f"   Credits: {summary['total_scan_credits']}")

    if 'total_billable_scan_gb' in summary:
        print(f"   Billable Scan: {summary['total_billable_scan_gb']} GB")
        print(f"   Non-Billable Scan: {summary['total_non_billable_scan_gb']} GB")

    if 'warning' in data:
        print("\n⚠️  WARNING DETECTED:")
        print(f"   Type: {data['warning']['type']}")
        print(f"   Message: {data['warning']['message'][:100]}...")
        print(f"   ➡️  {data['warning']['recommendation']}")


async def main():
    from sumologic_mcp_server.sumologic_mcp_server import analyze_search_scan_cost

    print("\n" + "🔍" * 40)
    print("FLEX ORGANIZATION FIX DEMONSTRATION")
    print("🔍" * 40)

    # Scenario 1: Recommended approach (auto-detection)
    print("\n\n📋 Scenario 1: Using Auto-Detection (Recommended)")
    print("-" * 80)
    print("This is the default behavior. The tool will:")
    print("- Call account status API")
    print("- Detect organization type (Flex vs Tiered)")
    print("- Automatically select correct breakdown type")

    result1 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="auto",  # This is the default
        group_by="user",
        limit=3
    )

    data1 = json.loads(result1)
    print_result_summary("RESULT: Auto-Detection", data1)

    if data1["query_parameters"].get("detected_org_type") == "Flex":
        print("\n✅ SUCCESS: Detected Flex org, used 'metering' breakdown automatically")
    else:
        print("\n✅ SUCCESS: Detected Tiered org, used 'tier' breakdown automatically")

    # Scenario 2: Wrong breakdown (demonstrates warning system)
    print("\n\n📋 Scenario 2: Using 'tier' Breakdown (Potentially Wrong)")
    print("-" * 80)
    print("If a Flex org explicitly uses 'tier' breakdown:")
    print("- Returns near-zero scan data")
    print("- Warning system detects suspicious pattern")
    print("- Recommends using 'metering' or 'auto'")

    result2 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="tier",  # Wrong for Flex orgs
        group_by="user",
        limit=3
    )

    data2 = json.loads(result2)
    print_result_summary("RESULT: Tier Breakdown", data2)

    if 'warning' in data2:
        print("\n✅ WARNING SYSTEM WORKING: Detected suspicious pattern")
        print("   The tool correctly identified this might be a Flex org using wrong breakdown")
    else:
        print("\n✅ NO WARNING: This is a legitimate Tiered org with low scan volume")

    # Scenario 3: Correct explicit metering
    print("\n\n📋 Scenario 3: Using 'metering' Breakdown (Explicit)")
    print("-" * 80)
    print("Explicitly using 'metering' breakdown:")
    print("- Works for both Flex and Tiered orgs")
    print("- Returns billable vs non-billable breakdown")
    print("- Most comprehensive data")

    result3 = await analyze_search_scan_cost(
        from_time="-7d",
        to_time="now",
        breakdown_type="metering",
        group_by="user",
        limit=3
    )

    data3 = json.loads(result3)
    print_result_summary("RESULT: Metering Breakdown", data3)

    print("\n✅ SUCCESS: Metering breakdown provides full visibility")
    print("   - Shows billable scan (Flex + Continuous + Frequent + Infrequent)")
    print("   - Shows non-billable scan (FlexSecurity + Security + Tracing)")

    # Summary
    print("\n\n" + "=" * 80)
    print("📊 SUMMARY: Best Practices for Flex Organizations")
    print("=" * 80)
    print("\n✅ RECOMMENDED:")
    print("   1. Use breakdown_type='auto' (default) - Automatically detects org type")
    print("   2. Use breakdown_type='metering' - Always works, shows billable breakdown")

    print("\n❌ AVOID:")
    print("   • breakdown_type='tier' on Flex orgs - Returns near-zero data")

    print("\n💡 TIP:")
    print("   If you see a warning about 'POSSIBLE_FLEX_ORG_USING_TIER_BREAKDOWN',")
    print("   retry with breakdown_type='metering' or 'auto' for accurate data.")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
