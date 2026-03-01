#!/usr/bin/env python3
"""Test log volume analysis and schema profiling tools."""

import asyncio
import json
from src.sumologic_mcp_server.sumologic_mcp_server import (
    analyze_log_volume,
    profile_log_schema
)


async def main():
    print("Testing Log Volume and Schema Profiling Tools\n")
    print("=" * 80)

    # Test 1: Profile CloudTrail schema to discover fields
    print("\n1. Testing profile_log_schema for CloudTrail logs...")
    print("-" * 80)
    try:
        result = await profile_log_schema(
            scope="_sourceCategory=*cloudtrail*",
            from_time="-1h",
            to_time="now",
            mode="summary",
            suggest_candidates=True,
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Schema profiling works")
            print(f"  Total fields: {data['summary']['total_fields']}")
            print(f"  Filtered fields: {data['summary'].get('filtered_fields', 'N/A')}")
            if 'suggested_analysis_fields' in data:
                suggested = data['suggested_analysis_fields'][:5]
                print(f"  Suggested fields for analysis: {', '.join(suggested)}")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 2: Analyze CloudTrail volume by eventname
    print("\n2. Testing analyze_log_volume for CloudTrail by eventname...")
    print("-" * 80)
    try:
        result = await analyze_log_volume(
            scope="_sourceCategory=*cloudtrail*",
            aggregate_by=["eventname"],
            from_time="-24h",
            to_time="now",
            top_n=10,
            include_percentage=True,
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Volume analysis works")
            print(f"  Total records: {data['summary']['total_records']}")
            print(f"  Total volume: {data['summary']['total_gb']} GB")
            if data['results']:
                top = data['results'][0]
                print(f"  Top event: {top.get('eventname', 'N/A')} - {top.get('gb', 0)} GB ({top.get('percentage', 0)}%)")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 3: Multi-dimensional analysis with additional fields
    print("\n3. Testing multi-dimensional analysis with additional_fields...")
    print("-" * 80)
    try:
        result = await analyze_log_volume(
            scope="_sourceCategory=*cloudtrail*",
            aggregate_by=["eventname", "eventsource"],
            additional_fields=["awsregion"],  # Simpler field name
            from_time="-24h",
            to_time="now",
            top_n=5,
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Multi-dimensional analysis works")
            print(f"  Total records: {data['summary']['total_records']}")
            if data['results']:
                top = data['results'][0]
                print(f"  Top: {top.get('eventname', 'N/A')} / {top.get('eventsource', 'N/A')}")
                print(f"       {top.get('gb', 0)} GB")
                if 'awsregion_samples' in top:
                    samples = str(top.get('awsregion_samples', ''))[:100]
                    print(f"       Region samples: {samples}...")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 4: Analyze volume by metadata within a partition
    print("\n4. Testing volume analysis by query_type within search audit...")
    print("-" * 80)
    try:
        result = await analyze_log_volume(
            scope="_view=sumologic_search_usage_per_query",
            aggregate_by=["query_type"],
            from_time="-24h",
            to_time="now",
            top_n=10,
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Metadata volume analysis works")
            print(f"  Total records: {data['summary']['total_records']}")
            print(f"  Total volume: {data['summary']['total_gb']} GB")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 5: Full facets mode
    print("\n5. Testing profile_log_schema in 'full' mode...")
    print("-" * 80)
    try:
        result = await profile_log_schema(
            scope="_sourceCategory=*cloudtrail*",
            from_time="-10m",  # Short time for facets
            to_time="now",
            mode="full",
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"✗ Error: {data['error']}")
        else:
            print(f"✓ Full facets mode works")
            print(f"  Total facet records: {len(data.get('facets', []))}")
            if data.get('facets'):
                # Show first facet record sample
                first_facet = data['facets'][0]
                print(f"  Sample facet fields: {', '.join(list(first_facet.keys())[:5])}...")
    except Exception as e:
        print(f"✗ Error: {e}")

    await asyncio.sleep(2)

    # Test 6: Parse and analyze custom logs
    print("\n6. Testing with parse statement (simulated Apache logs)...")
    print("-" * 80)
    try:
        # This will likely fail unless there are actual apache logs, but tests the syntax
        result = await analyze_log_volume(
            scope='_sourceCategory=apache* | parse "HTTP/1.1\" * " as status_code',
            aggregate_by=["status_code"],
            from_time="-24h",
            to_time="now",
            top_n=10,
            instance="default"
        )
        data = json.loads(result)
        if "error" in data:
            print(f"ℹ Expected (no apache logs): {data['error'][:80]}...")
        else:
            print(f"✓ Parse statement analysis works")
            print(f"  Total records: {data['summary']['total_records']}")
    except Exception as e:
        print(f"ℹ Expected error (no apache logs): {str(e)[:80]}...")

    print("\n" + "=" * 80)
    print("Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
