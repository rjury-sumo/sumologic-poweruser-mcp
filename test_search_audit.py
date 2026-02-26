#!/usr/bin/env python3
"""Test search audit MCP tool."""
import asyncio
import json
from sumologic_mcp_server.sumologic_mcp_server import run_search_audit_query


async def test_search_audit():
    """Test search audit query."""
    print("="*60)
    print("Testing Search Audit Query")
    print("="*60)

    print("\nRunning search audit for last 24 hours...")
    print("This may take 30-60 seconds to complete...\n")

    try:
        # Run search audit with defaults (last 24h, all users, all types)
        result = await run_search_audit_query(
            from_time="-24h",
            to_time="now",
            query_type="*",
            user_name="*",
            content_name="*",
            query_filter="*",
            query_regex=".*",
            include_raw_data=False,
            instance="default"
        )

        result_dict = json.loads(result)

        if "error" in result_dict:
            print(f"❌ Search audit failed: {result_dict['error']}")
            return False

        print("✓ Search audit completed successfully!\n")

        # Display summary
        summary = result_dict.get("summary", {})
        print("Summary:")
        print(f"  Total records: {summary.get('total_records', 0)}")
        print(f"  Total searches: {summary.get('total_searches', 0)}")
        print(f"  Total data scanned: {summary.get('total_scan_gb', 0):.2f} GB")
        print(f"  Infrequent tier: {summary.get('total_inf_scan_gb', 0):.2f} GB")
        print(f"  Flex tier: {summary.get('total_flex_scan_gb', 0):.2f} GB")

        # Display top 5 records
        records = result_dict.get("records", [])
        if records:
            print(f"\nTop {min(5, len(records))} search patterns:")
            print("-" * 60)
            for i, record in enumerate(records[:5], 1):
                print(f"\n{i}. User: {record.get('user_name')}")
                print(f"   Type: {record.get('query_type')}")
                print(f"   Searches: {record.get('searches')}")
                print(f"   Data scanned: {record.get('scan_gb', 0):.2f} GB")
                print(f"   Avg runtime: {record.get('avg_runtime_minutes', 0):.2f} min")
                query = record.get('query', '')
                if len(query) > 80:
                    query = query[:77] + "..."
                print(f"   Query: {query}")

        return True

    except Exception as e:
        print(f"❌ Test failed: {type(e).__name__}: {str(e)}")
        return False


async def main():
    success = await test_search_audit()
    print("\n" + "="*60)
    if success:
        print("✓ Search audit test PASSED")
    else:
        print("❌ Search audit test FAILED")
    print("="*60)
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
