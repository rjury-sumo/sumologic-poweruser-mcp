#!/usr/bin/env python3
"""Test updated search audit tool with scope_filters and where_filters."""

import asyncio
import json

from src.sumologic_mcp_server.sumologic_mcp_server import run_search_audit_query


async def main():
    print("Testing Updated Search Audit Tool\n")
    print("=" * 80)

    # Test 1: Legacy parameters (backward compatibility)
    print("\n1. Testing legacy parameters (backward compatibility)...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-7d",
            to_time="now",
            query_type="Interactive",
            user_name="*",
            instance="default"
        )
        data = json.loads(result)
        print("✓ Legacy parameters work")
        print(f"  Total searches: {data['summary']['total_searches']}")
        print(f"  Total scan GB: {data['summary']['total_scan_gb']:.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 2: Scope filters only
    print("\n2. Testing scope_filters=['query_type=Interactive']...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-7d",
            to_time="now",
            scope_filters=["query_type=Interactive"],
            instance="default"
        )
        data = json.loads(result)
        print("✓ Scope filters work")
        print(f"  Scope filters used: {data['query_parameters']['scope_filters']}")
        print(f"  Total searches: {data['summary']['total_searches']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 3: Multiple scope filters
    print("\n3. Testing multiple scope filters...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-7d",
            to_time="now",
            scope_filters=["query_type=Interactive", "query=*error*"],
            instance="default"
        )
        data = json.loads(result)
        print("✓ Multiple scope filters work")
        print(f"  Filters: {data['query_parameters']['scope_filters']}")
        print(f"  Total searches: {data['summary']['total_searches']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 4: Where filters only
    print("\n4. Testing where_filters=['execution_duration_ms > 10000']...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-7d",
            to_time="now",
            where_filters=["execution_duration_ms > 10000"],
            instance="default"
        )
        data = json.loads(result)
        print("✓ Where filters work")
        print(f"  Where filters used: {data['query_parameters']['where_filters']}")
        print(f"  Total searches: {data['summary']['total_searches']}")
        if data['records']:
            first_record = data['records'][0]
            print(f"  First result runtime: {first_record['sum_runtime_minutes']:.2f} minutes")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 5: Combined scope and where filters
    print("\n5. Testing combined scope_filters and where_filters...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-7d",
            to_time="now",
            scope_filters=["query_type=Interactive"],
            where_filters=["execution_duration_ms > 5000"],
            instance="default"
        )
        data = json.loads(result)
        print("✓ Combined filters work")
        print(f"  Scope: {data['query_parameters']['scope_filters']}")
        print(f"  Where: {data['query_parameters']['where_filters']}")
        print(f"  Total searches: {data['summary']['total_searches']}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 6: Validation - invalid scope field
    print("\n6. Testing validation - invalid scope field...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            scope_filters=["execution_duration_ms=1000"],  # Should fail - not scope-filterable
            instance="default"
        )
        print("✗ Validation should have failed")
    except Exception as e:
        error_msg = str(e)
        if "not supported as a scope filter" in error_msg:
            print("✓ Validation correctly rejected invalid scope field")
            print(f"  Error: {error_msg[:100]}...")
        else:
            print(f"✗ Unexpected error: {e}")

    # Test 7: Validation - missing equals sign
    print("\n7. Testing validation - scope filter without '='...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            scope_filters=["query_type Interactive"],  # Missing =
            instance="default"
        )
        print("✗ Validation should have failed")
    except Exception as e:
        error_msg = str(e)
        if "must be in field=value format" in error_msg:
            print("✓ Validation correctly rejected malformed expression")
            print(f"  Error: {error_msg[:100]}...")
        else:
            print(f"✗ Unexpected error: {e}")

    # Test 8: Validation - where filter with pipe
    print("\n8. Testing validation - where filter starting with '|'...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            where_filters=["| where execution_duration_ms > 1000"],  # Should fail
            instance="default"
        )
        print("✗ Validation should have failed")
    except Exception as e:
        error_msg = str(e)
        if "should not start with" in error_msg:
            print("✓ Validation correctly rejected malformed where filter")
            print(f"  Error: {error_msg[:100]}...")
        else:
            print(f"✗ Unexpected error: {e}")

    # Test 9: Injection protection
    print("\n9. Testing injection protection...")
    print("-" * 80)
    try:
        result = await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            where_filters=["execution_duration_ms > 1000 | delete *"],  # Should fail
            instance="default"
        )
        print("✗ Injection protection should have blocked this")
    except Exception as e:
        error_msg = str(e)
        if "cannot contain write operators" in error_msg:
            print("✓ Injection protection working")
            print(f"  Blocked: {error_msg[:100]}...")
        else:
            print(f"✗ Unexpected error: {e}")

    print("\n" + "=" * 80)
    print("Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
