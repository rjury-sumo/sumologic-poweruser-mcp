#!/usr/bin/env python3
"""Test updated search audit tool with corrected query_type values."""

import asyncio
import json
from src.sumologic_mcp_server.sumologic_mcp_server import run_search_audit_query


async def main():
    print("Testing Updated Search Audit Tool (Corrected)\n")
    print("=" * 80)

    # Test 1: Legacy parameters with wildcard
    print("\n1. Testing legacy parameters with wildcard query_type=Interactive*...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-24h",
            to_time="now",
            query_type="Interactive*",
            user_name="*",
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Legacy parameters work")
            print(f"  Total searches: {data['summary']['total_searches']}")
            print(f"  Total scan GB: {data['summary']['total_scan_gb']:.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)  # Rate limiting

    # Test 2: Scope filters with wildcard
    print("\n2. Testing scope_filters=['query_type=Interactive*']...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-24h",
            to_time="now",
            scope_filters=["query_type=Interactive*"],
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Scope filters work")
            print(f"  Scope filters used: {data['query_parameters']['scope_filters']}")
            print(f"  Total searches: {data['summary']['total_searches']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 3: Multiple scope filters
    print("\n3. Testing multiple scope filters ['query_type=Interactive*', 'analytics_tier=*']...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-24h",
            to_time="now",
            scope_filters=["query_type=Interactive*", "analytics_tier=*"],
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Multiple scope filters work")
            print(f"  Filters: {data['query_parameters']['scope_filters']}")
            print(f"  Total searches: {data['summary']['total_searches']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 4: Where filters only
    print("\n4. Testing where_filters=['execution_duration_ms > 1000']...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-24h",
            to_time="now",
            where_filters=["execution_duration_ms > 1000"],
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Where filters work")
            print(f"  Where filters used: {data['query_parameters']['where_filters']}")
            print(f"  Total searches: {data['summary']['total_searches']}")
            if data['records']:
                first_record = data['records'][0]
                print(f"  First result runtime: {first_record['sum_runtime_minutes']:.2f} minutes")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 5: Combined scope and where filters
    print("\n5. Testing combined scope_filters and where_filters...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-24h",
            to_time="now",
            scope_filters=["query_type=Interactive*"],
            where_filters=["execution_duration_ms > 2000"],
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Combined filters work")
            print(f"  Scope: {data['query_parameters']['scope_filters']}")
            print(f"  Where: {data['query_parameters']['where_filters']}")
            print(f"  Total searches: {data['summary']['total_searches']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 6: Validation - invalid scope field
    print("\n6. Testing validation - invalid scope field...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            scope_filters=["execution_duration_ms=1000"],  # Should fail
            instance="default"
        )
        data = json.loads(result)
        if "error" in data and "not supported as a scope filter" in data['error']:
            print(f"✓ Validation correctly rejected invalid scope field")
            print(f"  Error: {data['error'][:100]}...")
        else:
            print(f"✗ Validation should have failed")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    await asyncio.sleep(2)

    # Test 7: Validation - malformed scope filter
    print("\n7. Testing validation - scope filter without '='...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            scope_filters=["query_type Interactive"],  # Missing =
            instance="default"
        )
        data = json.loads(result)
        if "error" in data and "must be in field=value format" in data['error']:
            print(f"✓ Validation correctly rejected malformed expression")
            print(f"  Error: {data['error'][:100]}...")
        else:
            print(f"✗ Validation should have failed")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    print("\n" + "=" * 80)
    print("Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
