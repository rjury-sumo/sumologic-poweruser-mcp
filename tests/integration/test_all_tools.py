#!/usr/bin/env python3
"""Test all MCP tools for bugs."""
import asyncio
import json

from sumologic_poweruser_mcp.sumologic_mcp_server import (
    create_sumo_search_job,
    get_sumo_collectors,
    get_sumo_dashboards,
    get_sumo_partitions,
    get_sumo_roles_v2,
    get_sumo_search_job_results,
    get_sumo_search_job_status,
    get_sumo_sources,
    get_sumo_users,
    list_sumo_instances,
    query_sumo_metrics,
    search_sumo_logs,
    search_sumo_monitors,
)


async def run_tool_test(name, coro):
    """Test a single tool and report result."""
    try:
        result = await coro
        result_dict = json.loads(result)
        if "error" in result_dict:
            print(f"❌ {name}: {result_dict['error']}")
            return False
        else:
            print(f"✓ {name}: OK")
            return True
    except Exception as e:
        print(f"❌ {name}: {type(e).__name__}: {str(e)}")
        return False


async def main():
    """Run all tests with rate limiting (max 3 API requests per second)."""
    results = []
    delay = 0.4  # 400ms delay = 2.5 requests/sec to stay well under 4 req/sec

    print("Running tests with rate limiting (400ms delay between API calls)...\n")

    # Test 1: list_sumo_instances (no API call)
    results.append(await run_tool_test(
        "list_sumo_instances",
        list_sumo_instances()
    ))

    await asyncio.sleep(delay)

    # Test 2: search_sumo_logs
    results.append(await run_tool_test(
        "search_sumo_logs",
        search_sumo_logs(query="error", hours_back=1, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 3: create_sumo_search_job
    job_result = await create_sumo_search_job(
        query="*", from_time="-1h", to_time="now", instance="default"
    )
    await asyncio.sleep(delay)

    job_dict = json.loads(job_result)
    if "error" not in job_dict:
        job_id = job_dict.get("id")
        print(f"✓ create_sumo_search_job: OK (job_id={job_id})")
        results.append(True)

        await asyncio.sleep(delay)

        # Test 4: get_sumo_search_job_status
        results.append(await run_tool_test(
            "get_sumo_search_job_status",
            get_sumo_search_job_status(job_id=job_id, instance="default")
        ))

        await asyncio.sleep(5)  # Wait for job to complete

        # Test 5: get_sumo_search_job_results
        results.append(await run_tool_test(
            "get_sumo_search_job_results",
            get_sumo_search_job_results(job_id=job_id, result_type="auto", limit=10, instance="default")
        ))
    else:
        print(f"❌ create_sumo_search_job: {job_dict['error']}")
        results.append(False)
        results.append(False)
        results.append(False)

    await asyncio.sleep(delay)

    # Test 6: get_sumo_collectors
    results.append(await run_tool_test(
        "get_sumo_collectors",
        get_sumo_collectors(limit=10, instance="default")
    ))

    await asyncio.sleep(delay)

    # Get a collector ID for source test
    collectors_result = await get_sumo_collectors(limit=1, instance="default")
    await asyncio.sleep(delay)

    collectors_dict = json.loads(collectors_result)
    if "collectors" in collectors_dict and len(collectors_dict["collectors"]) > 0:
        collector_id = collectors_dict["collectors"][0]["id"]
        # Test 7: get_sumo_sources
        results.append(await run_tool_test(
            "get_sumo_sources",
            get_sumo_sources(collector_id=collector_id, instance="default")
        ))
    else:
        print("⚠ get_sumo_sources: SKIPPED (no collectors found)")
        results.append(True)

    await asyncio.sleep(delay)

    # Test 8: get_sumo_users
    results.append(await run_tool_test(
        "get_sumo_users",
        get_sumo_users(limit=10, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 9: get_sumo_folders - SKIP (tool doesn't exist)
    # results.append(await run_tool_test(
    #     "get_sumo_folders",
    #     get_sumo_folders(limit=10, instance="default")
    # ))

    # await asyncio.sleep(delay)

    # Test 10: get_sumo_dashboards
    results.append(await run_tool_test(
        "get_sumo_dashboards",
        get_sumo_dashboards(limit=10, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 11: query_sumo_metrics
    results.append(await run_tool_test(
        "query_sumo_metrics",
        query_sumo_metrics(query="metric=CPU_User", hours_back=1, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 12: get_sumo_content_v2 - SKIP (tool doesn't exist)
    # results.append(await run_tool_test(
    #     "get_sumo_content_v2",
    #     get_sumo_content_v2(content_type="Dashboard", limit=10, instance="default")
    # ))

    await asyncio.sleep(delay)

    # Test 13: get_sumo_roles_v2
    results.append(await run_tool_test(
        "get_sumo_roles_v2",
        get_sumo_roles_v2(limit=10, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 14: search_sumo_monitors
    results.append(await run_tool_test(
        "search_sumo_monitors",
        search_sumo_monitors(query="*", limit=10, offset=0, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 15: get_sumo_partitions
    results.append(await run_tool_test(
        "get_sumo_partitions",
        get_sumo_partitions(limit=10, instance="default")
    ))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"SUMMARY: {passed}/{total} tests passed")
    print(f"{'='*50}")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
