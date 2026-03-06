#!/usr/bin/env python3
"""
Test script for query examples tool and resource.
"""

import asyncio
import json

from src.sumologic_mcp_server.sumologic_mcp_server import query_examples, search_query_examples


async def test_tool():
    """Test the search_query_examples tool."""
    print("=" * 80)
    print("Testing search_query_examples TOOL")
    print("=" * 80)

    # Test 1: Search by app name
    print("\n1. Search for Windows queries:")
    result = await search_query_examples(app_name="Windows", max_results=3)
    data = json.loads(result)
    print(f"   Found {data.get('summary', {}).get('matches_found', 0)} matches")
    print(f"   Returned {data.get('summary', {}).get('returned', 0)} examples")
    if data.get('examples'):
        print(f"   First example: {data['examples'][0]['search_name']}")

    # Test 2: Search by keywords
    print("\n2. Search for 'count by' patterns:")
    result = await search_query_examples(keywords="count by", max_results=5)
    data = json.loads(result)
    print(f"   Found {data['summary']['matches_found']} matches")
    print(f"   Returned {data['summary']['returned']} examples")

    # Test 3: Search by use case
    print("\n3. Search for security-related queries:")
    result = await search_query_examples(use_case="security", max_results=3)
    data = json.loads(result)
    print(f"   Found {data['summary']['matches_found']} matches")
    print(f"   Returned {data['summary']['returned']} examples")

    # Test 4: Combined filters
    print("\n4. Search AWS + CloudTrail:")
    result = await search_query_examples(app_name="AWS", keywords="CloudTrail", max_results=2)
    data = json.loads(result)
    print(f"   Found {data.get('summary', {}).get('matches_found', 0)} matches")
    print(f"   Returned {data.get('summary', {}).get('returned', 0)} examples")
    if data.get('examples'):
        print(f"   First example app: {data['examples'][0]['app']}")


async def test_resource():
    """Test the query_examples resource."""
    print("\n" + "=" * 80)
    print("Testing query_examples RESOURCE")
    print("=" * 80)

    # Get sample of query examples
    print("\n1. Get sample of query examples:")
    result = await query_examples()
    data = json.loads(result)
    print(f"   Total available: {data.get('total_available', 'N/A')}")
    print(f"   Sample size: {data.get('sample_size', 'N/A')}")
    print(f"   Total apps available: {data.get('total_apps', 'N/A')}")
    if data.get('available_apps'):
        print(f"   First few apps: {', '.join(data['available_apps'][:5])}")


async def main():
    """Run all tests."""
    print("\nTesting Query Examples Implementation")
    print("=" * 80)

    try:
        await test_tool()
        await test_resource()

        print("\n" + "=" * 80)
        print("✅ All tests completed successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
