#!/usr/bin/env python3
"""Verify usage export includes download URL."""
import asyncio
import json
from datetime import datetime, timedelta

from sumologic_mcp_server.sumologic_mcp_server import export_usage_report


async def main():
    """Run a single export and check for download URL."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    print(f"Exporting usage report from {start_date} to {end_date}...")

    result = await export_usage_report(
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        group_by="day",
        report_type="standard",
        instance="default"
    )

    result_dict = json.loads(result)
    print("\nExport Result:")
    print(json.dumps(result_dict, indent=2))

    if "download_url" in result_dict and result_dict["download_url"]:
        print("\n✓ Download URL present and valid")
        print(f"  URL: {result_dict['download_url'][:80]}...")
    else:
        print("\n⚠ Warning: No download URL in result")


if __name__ == "__main__":
    asyncio.run(main())
