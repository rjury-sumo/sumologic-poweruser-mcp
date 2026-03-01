#!/usr/bin/env python3
"""
Test the improved search_query_examples tool with scoring and relevance ranking.
"""

import asyncio
import json
from src.sumologic_mcp_server.sumologic_mcp_server import search_query_examples


async def test_natural_language_search():
    """Test free-text query parameter."""
    print("=" * 80)
    print("TEST 1: Natural Language Search (query parameter)")
    print("=" * 80)

    # Test 1a: Apache errors
    print("\n1a. query='apache 4xx errors':")
    result = await search_query_examples(query="apache 4xx errors", max_results=3)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    print(f"   Top result: {data['results'][0]['search_name'] if data['results'] else 'None'}")
    print(f"   Matched on: {data['results'][0]['_matched_on'][:3] if data['results'] else 'None'}")
    print(f"   Score: {data['results'][0]['_score'] if data['results'] else 0}")

    # Test 1b: Kubernetes scheduling
    print("\n1b. query='kubernetes unschedulable pods':")
    result = await search_query_examples(query="kubernetes unschedulable pods", max_results=3)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    if data['results']:
        print(f"   Top result: {data['results'][0]['search_name']}")
        print(f"   Score: {data['results'][0]['_score']}")

    # Test 1c: CloudTrail
    print("\n1c. query='cloudtrail security events':")
    result = await search_query_examples(query="cloudtrail security events", max_results=3)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    if data['results']:
        print(f"   Top result: {data['results'][0]['app']}")


async def test_alias_matching():
    """Test technology aliases."""
    print("\n" + "=" * 80)
    print("TEST 2: Alias Matching")
    print("=" * 80)

    # k8s -> kubernetes
    print("\n2a. query='k8s pod status':")
    result = await search_query_examples(query="k8s pod status", max_results=3)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    if data['results']:
        print(f"   Found Kubernetes results: {any('kubernetes' in r['app'].lower() for r in data['results'])}")

    # httpd -> apache
    print("\n2b. app_name='httpd':")
    result = await search_query_examples(app_name="httpd", max_results=3)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    if data['results']:
        print(f"   Found Apache results: {any('apache' in r['app'].lower() for r in data['results'])}")


async def test_tokenized_keywords():
    """Test multi-word keyword search."""
    print("\n" + "=" * 80)
    print("TEST 3: Tokenized Keyword Search")
    print("=" * 80)

    # Multi-word keywords
    print("\n3a. keywords='status_code bytes':")
    result = await search_query_examples(keywords="status_code bytes", max_results=5)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    print(f"   Returns queries with either or both terms: {len(data['results']) > 0}")

    # Pattern search
    print("\n3b. keywords='count by timeslice':")
    result = await search_query_examples(keywords="count by timeslice", max_results=5)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")


async def test_scoring_vs_and_logic():
    """Test scoring (any) vs AND logic (all)."""
    print("\n" + "=" * 80)
    print("TEST 4: Scoring vs AND Logic")
    print("=" * 80)

    # Scoring mode (default)
    print("\n4a. match_mode='any' (default): app_name='Apache' + keywords='error':")
    result = await search_query_examples(
        app_name="Apache",
        keywords="error",
        match_mode="any",
        max_results=5
    )
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    print(f"   Top score: {data['results'][0]['_score'] if data['results'] else 0}")
    print(f"   Results with scoring: YES" if data['results'] else "   No results")

    # Strict AND mode
    print("\n4b. match_mode='all': app_name='Apache' + keywords='unschedulable':")
    result = await search_query_examples(
        app_name="Apache",
        keywords="unschedulable",
        match_mode="all",
        max_results=5
    )
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    print(f"   Strict AND may return zero: {len(data['results']) == 0}")


async def test_combined_search():
    """Test combining query + filters."""
    print("\n" + "=" * 80)
    print("TEST 5: Combined Search (query + filters)")
    print("=" * 80)

    print("\n5a. query='latency' + query_type='Logs':")
    result = await search_query_examples(
        query="latency",
        query_type="Logs",
        max_results=5
    )
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    if data['results']:
        print(f"   All Logs type: {all(r['type'] == 'Logs' for r in data['results'])}")

    print("\n5b. query='error' + app_name='AWS' + use_case='security':")
    result = await search_query_examples(
        query="error",
        app_name="AWS",
        use_case="security",
        max_results=5
    )
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    if data['results']:
        print(f"   Top result app: {data['results'][0]['app']}")
        print(f"   Relevance score: {data['results'][0]['_score']}")


async def test_no_results_handling():
    """Test zero results with suggestions."""
    print("\n" + "=" * 80)
    print("TEST 6: No Results Handling")
    print("=" * 80)

    print("\n6a. Nonsense search:")
    result = await search_query_examples(query="xyzabc123impossible", max_results=5)
    data = json.loads(result)
    print(f"   Matches: {data['summary']['matches_found']}")
    print(f"   Has suggestions: {'suggestions' in data}")
    if 'available_apps_sample' in data:
        print(f"   Sample apps provided: {len(data['available_apps_sample'])} apps")


async def test_match_metadata():
    """Test that results include match metadata."""
    print("\n" + "=" * 80)
    print("TEST 7: Match Metadata (_matched_on)")
    print("=" * 80)

    print("\n7a. query='windows security':")
    result = await search_query_examples(query="windows security", max_results=3)
    data = json.loads(result)
    if data['results']:
        for i, r in enumerate(data['results'][:2]):
            print(f"\n   Result {i+1}:")
            print(f"   - Name: {r['search_name']}")
            print(f"   - Score: {r['_score']}")
            print(f"   - Matched on: {', '.join(r['_matched_on'][:5])}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("TESTING IMPROVED SEARCH WITH SCORING & RELEVANCE")
    print("=" * 80)

    try:
        await test_natural_language_search()
        await test_alias_matching()
        await test_tokenized_keywords()
        await test_scoring_vs_and_logic()
        await test_combined_search()
        await test_no_results_handling()
        await test_match_metadata()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETED")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
