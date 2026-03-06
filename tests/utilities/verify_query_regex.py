#!/usr/bin/env python3
"""Verify that query_regex is properly interpolated."""

import asyncio

from src.sumologic_mcp_server.sumologic_mcp_server import run_search_audit_query


async def main():
    # Enable file writing to see the query

    # Patch to write query to file
    original_create = None
    captured_query = None

    async def capture_query(self, query, from_time, to_time, timezone_str="UTC"):
        nonlocal captured_query
        captured_query = query
        raise Exception("Captured query successfully")

    # Monkey patch
    from src.sumologic_mcp_server.sumologic_mcp_server import SumoLogicClient
    original_create = SumoLogicClient.create_search_job
    SumoLogicClient.create_search_job = capture_query

    try:
        await run_search_audit_query(
            from_time="-1h",
            to_time="now",
            query_regex="foo.+bar",
            scope_filters=["query_type=Interactive*"],
            instance="default"
        )
    except:
        pass

    # Restore
    SumoLogicClient.create_search_job = original_create

    if captured_query:
        print("CAPTURED QUERY:")
        print("=" * 80)
        print(captured_query)
        print("=" * 80)

        # Check if query_regex was interpolated
        if "{query_regex}" in captured_query:
            print("\n❌ ERROR: query_regex was NOT interpolated!")
        elif "foo.+bar" in captured_query:
            print("\n✓ SUCCESS: query_regex was properly interpolated")
        else:
            print("\n⚠ WARNING: Could not find expected pattern")

if __name__ == "__main__":
    asyncio.run(main())
