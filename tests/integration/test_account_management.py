#!/usr/bin/env python3
"""Test account management tools."""
import asyncio
import json
from sumologic_mcp_server.sumologic_mcp_server import (
    get_account_status,
    get_usage_forecast,
    export_usage_report,
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
            # Print key fields for verification
            if name == "get_account_status":
                print(f"  Plan: {result_dict.get('planType', 'N/A')}")
                print(f"  Org ID: {result_dict.get('organizationId', 'N/A')}")
            elif name == "get_usage_forecast":
                print(f"  Forecasted Credits: {result_dict.get('forecastedTotalCredits', 'N/A')}")
            elif name == "export_usage_report":
                print(f"  Job ID: {result_dict.get('job_id', 'N/A')}")
                print(f"  Status: {result_dict.get('status', 'N/A')}")
                if result_dict.get('download_url'):
                    print(f"  Download URL: {result_dict['download_url'][:80]}...")
            return True
    except Exception as e:
        print(f"❌ {name}: {type(e).__name__}: {str(e)}")
        return False


async def main():
    """Run all account management tests."""
    results = []
    delay = 0.4  # 400ms delay to stay under rate limits

    print("Testing account management tools...\\n")

    # Test 1: get_account_status
    print("Test 1: get_account_status")
    results.append(await run_tool_test(
        "get_account_status",
        get_account_status(instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 2: get_usage_forecast (7 days)
    print("\\nTest 2: get_usage_forecast (7 days)")
    results.append(await run_tool_test(
        "get_usage_forecast",
        get_usage_forecast(number_of_days=7, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 3: get_usage_forecast (30 days)
    print("\\nTest 3: get_usage_forecast (30 days)")
    results.append(await run_tool_test(
        "get_usage_forecast",
        get_usage_forecast(number_of_days=30, instance="default")
    ))

    await asyncio.sleep(delay)

    # Test 4: export_usage_report (last 7 days)
    print("\\nTest 4: export_usage_report (last 7 days)")
    from datetime import datetime, timedelta
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    results.append(await run_tool_test(
        "export_usage_report",
        export_usage_report(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            group_by="day",
            report_type="standard",
            instance="default"
        )
    ))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\\n{'='*50}")
    print(f"SUMMARY: {passed}/{total} tests passed")
    print(f"{'='*50}")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
