#!/usr/bin/env python3
"""Test analyze_search_scan_cost tool."""
import asyncio
import json
from sumologic_mcp_server.sumologic_mcp_server import analyze_search_scan_cost


async def main():
    print("=" * 80)
    print("Testing analyze_search_scan_cost Tool")
    print("=" * 80)

    # Test 1: Infrequent tier analysis by user
    print("\n" + "=" * 80)
    print("Test 1: Infrequent tier scan cost analysis - user ranking")
    print("=" * 80)
    try:
        result = await analyze_search_scan_cost(
            from_time="-7d",
            to_time="now",
            analytics_tier_filter="*infrequent*",
            breakdown_type="tier",
            group_by="user",
            scan_credit_rate=0.016,
            sort_by="scan_credits",
            limit=10
        )

        result_data = json.loads(result)
        print(f"\nQuery Parameters:")
        print(json.dumps(result_data["query_parameters"], indent=2))

        print(f"\nSummary:")
        print(json.dumps(result_data["summary"], indent=2))

        print(f"\nTop 5 Users by Scan Cost:")
        for i, record in enumerate(result_data["records"][:5], 1):
            print(f"{i}. {record['user_name']}:")
            print(f"   - Queries: {record['queries']}")
            print(f"   - Total Scan: {record['total_scan_gb']} GB")
            print(f"   - Credits: {record['scan_credits']}")
            print(f"   - Credits/Query: {record['credits_per_query']}")
            if 'tier_breakdown_gb' in record:
                print(f"   - Tier Breakdown: {record['tier_breakdown_gb']}")

        print("\n✅ Test 1 PASSED")
    except Exception as e:
        print(f"\n❌ Test 1 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: User + Query breakdown for Infrequent tier
    print("\n" + "=" * 80)
    print("Test 2: Infrequent tier - expensive queries by user")
    print("=" * 80)
    try:
        result = await analyze_search_scan_cost(
            from_time="-24h",
            to_time="now",
            analytics_tier_filter="*infrequent*",
            breakdown_type="tier",
            group_by="user_query",
            min_scan_gb=1.0,  # Only queries scanning > 1GB
            scan_credit_rate=0.016,
            sort_by="scan_credits",
            limit=10
        )

        result_data = json.loads(result)
        print(f"\nSummary:")
        print(json.dumps(result_data["summary"], indent=2))

        print(f"\nTop 5 Expensive Queries:")
        for i, record in enumerate(result_data["records"][:5], 1):
            query_preview = record['query'][:80] + "..." if len(record['query']) > 80 else record['query']
            print(f"{i}. User: {record['user_name']}")
            print(f"   Query: {query_preview}")
            print(f"   - Executions: {record['queries']}")
            print(f"   - Total Scan: {record['total_scan_gb']} GB")
            print(f"   - Credits: {record['scan_credits']}")
            print(f"   - Infrequent Tier: {record['tier_breakdown_gb']['infrequent']} GB")

        print("\n✅ Test 2 PASSED")
    except Exception as e:
        print(f"\n❌ Test 2 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Flex metering breakdown
    print("\n" + "=" * 80)
    print("Test 3: Flex billable vs non-billable scan analysis")
    print("=" * 80)
    try:
        result = await analyze_search_scan_cost(
            from_time="-7d",
            to_time="now",
            breakdown_type="metering",
            group_by="user",
            scan_credit_rate=0.018,  # Flex rate
            sort_by="billable_scan_gb",
            limit=10
        )

        result_data = json.loads(result)
        print(f"\nSummary:")
        print(json.dumps(result_data["summary"], indent=2))

        print(f"\nTop 5 Users by Billable Scan:")
        for i, record in enumerate(result_data["records"][:5], 1):
            print(f"{i}. {record['user_name']}:")
            print(f"   - Queries: {record['queries']}")
            print(f"   - Billable Scan: {record.get('billable_scan_gb', 0)} GB")
            print(f"   - Non-Billable Scan: {record.get('non_billable_scan_gb', 0)} GB")
            print(f"   - Total Scan: {record['total_scan_gb']} GB")
            print(f"   - Credits: {record['scan_credits']}")
            if 'metering_breakdown_gb' in record:
                print(f"   - Metering Breakdown:")
                for key, val in record['metering_breakdown_gb'].items():
                    if val > 0:
                        print(f"     - {key}: {val} GB")

        print("\n✅ Test 3 PASSED")
    except Exception as e:
        print(f"\n❌ Test 3 FAILED: {e}")
        import traceback
        traceback.print_exc()

    # Test 4: Scheduled searches/dashboards cost analysis
    print("\n" + "=" * 80)
    print("Test 4: Expensive scheduled searches/dashboards")
    print("=" * 80)
    try:
        result = await analyze_search_scan_cost(
            from_time="-7d",
            to_time="now",
            query_type="Scheduled",
            breakdown_type="tier",
            group_by="content",
            include_scope_parsing=False,
            min_scan_gb=0.5,
            scan_credit_rate=0.016,
            sort_by="scan_credits",
            limit=10
        )

        result_data = json.loads(result)
        print(f"\nSummary:")
        print(json.dumps(result_data["summary"], indent=2))

        print(f"\nTop 5 Expensive Content Items:")
        for i, record in enumerate(result_data["records"][:5], 1):
            print(f"{i}. {record['content_name']} ({record['query_type']})")
            print(f"   - Executions: {record['queries']}")
            print(f"   - Total Scan: {record['total_scan_gb']} GB")
            print(f"   - Credits: {record['scan_credits']}")
            print(f"   - Credits/Execution: {record['credits_per_query']}")

        print("\n✅ Test 4 PASSED")
    except Exception as e:
        print(f"\n❌ Test 4 FAILED: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
