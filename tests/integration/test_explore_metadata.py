#!/usr/bin/env python3
"""Test explore log metadata tool."""
import asyncio
import json

from sumologic_mcp_server.sumologic_mcp_server import explore_log_metadata


async def main():
    """Test the metadata exploration tool."""
    print("Testing explore_log_metadata...\n")

    # Test 1: Basic exploration - partition and source category
    print("Test 1: Explore metadata for all logs (last 15 minutes)")
    print("Fields: _view, _sourceCategory")
    result = await explore_log_metadata(
        scope="*",
        from_time="-15m",
        to_time="now",
        metadata_fields="_view,_sourceCategory",
        sort_by="_sourceCategory",
        max_results=50,
        instance="default"
    )

    result_dict = json.loads(result)

    if "error" in result_dict:
        print(f"❌ Error: {result_dict['error']}")
        return False

    print("✓ Success!")
    summary = result_dict.get("summary", {})
    print(f"  Unique combinations: {summary.get('unique_combinations', 0)}")
    print(f"  Total messages: {summary.get('total_messages', 0)}")
    print(f"  Truncated: {summary.get('truncated', False)}")

    # Show first 5 entries
    metadata = result_dict.get("metadata", [])
    if metadata:
        print("\n  Sample entries:")
        for entry in metadata[:5]:
            view = entry.get("_view", "N/A")
            cat = entry.get("_sourceCategory", "N/A")
            count = entry.get("count", 0)
            print(f"    - {view} | {cat}: {count:,} messages")
        if len(metadata) > 5:
            print(f"    ... and {len(metadata) - 5} more")

    print("\n" + "="*70)

    # Test 2: More detailed exploration with collector and source
    print("\nTest 2: Explore with collector and source (last 30 minutes)")
    print("Fields: _view, _sourceCategory, _collector, _source")
    result2 = await explore_log_metadata(
        scope="_sourceCategory=*",
        from_time="-30m",
        to_time="now",
        metadata_fields="_view,_sourceCategory,_collector,_source",
        sort_by="_sourceCategory",
        max_results=100,
        instance="default"
    )

    result2_dict = json.loads(result2)

    if "error" in result2_dict:
        print(f"❌ Error: {result2_dict['error']}")
        return False

    print("✓ Success!")
    summary2 = result2_dict.get("summary", {})
    print(f"  Unique combinations: {summary2.get('unique_combinations', 0)}")
    print(f"  Total messages: {summary2.get('total_messages', 0)}")

    # Show first 3 entries with all fields
    metadata2 = result2_dict.get("metadata", [])
    if metadata2:
        print("\n  Sample entries (showing all fields):")
        for entry in metadata2[:3]:
            view = entry.get("_view", "N/A")
            cat = entry.get("_sourceCategory", "N/A")
            collector = entry.get("_collector", "N/A")
            source = entry.get("_source", "N/A")
            count = entry.get("count", 0)
            print(f"    View: {view}")
            print(f"    Category: {cat}")
            print(f"    Collector: {collector}")
            print(f"    Source: {source}")
            print(f"    Messages: {count:,}")
            print()

    print("="*70)

    # Test 3: Specific scope - sumologic system views
    print("\nTest 3: Explore sumologic system logs (last 1 hour)")
    print("Fields: _view, _sourceCategory")
    result3 = await explore_log_metadata(
        scope="_view=sumologic*",
        from_time="-1h",
        to_time="now",
        metadata_fields="_view,_sourceCategory",
        sort_by="_view",
        max_results=50,
        instance="default"
    )

    result3_dict = json.loads(result3)

    if "error" in result3_dict:
        print(f"❌ Error: {result3_dict['error']}")
        return False

    print("✓ Success!")
    summary3 = result3_dict.get("summary", {})
    print(f"  Unique combinations: {summary3.get('unique_combinations', 0)}")
    print(f"  Total messages: {summary3.get('total_messages', 0)}")

    print("\n" + "="*70)
    print("\n✓ All tests passed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
