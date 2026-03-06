#!/usr/bin/env python3
"""Test new content library MCP tools."""
import asyncio
import json

from sumologic_mcp_server.sumologic_mcp_server import (
    convert_content_id_decimal_to_hex,
    convert_content_id_hex_to_decimal,
    get_content_by_path,
    get_content_path_by_id,
    get_content_web_url,
    get_folder_by_id,
    get_personal_folder,
)


async def run_tool_test(name, coro):
    """Test a single tool and report result."""
    print(f"\nTesting {name}...")
    try:
        result = await coro
        result_dict = json.loads(result)
        if "error" in result_dict:
            print(f"❌ {name}: {result_dict['error']}")
            return False
        else:
            print(f"✓ {name}: OK")
            # Print first 200 chars of result
            result_preview = json.dumps(result_dict, indent=2)[:200]
            print(f"  Preview: {result_preview}...")
            return True
    except Exception as e:
        print(f"❌ {name}: {type(e).__name__}: {str(e)}")
        return False


async def main():
    """Run tests for content library tools."""
    results = []

    print("="*60)
    print("Content Library Tools Test Suite")
    print("="*60)

    # Test 1: ID Conversion - Hex to Decimal
    results.append(await run_tool_test(
        "convert_content_id_hex_to_decimal",
        convert_content_id_hex_to_decimal(hex_id="00000000005E5403")
    ))

    await asyncio.sleep(0.5)

    # Test 2: ID Conversion - Decimal to Hex
    results.append(await run_tool_test(
        "convert_content_id_decimal_to_hex",
        convert_content_id_decimal_to_hex(decimal_id="6181891")
    ))

    await asyncio.sleep(0.5)

    # Test 3: Get Web URL
    results.append(await run_tool_test(
        "get_content_web_url",
        get_content_web_url(content_id="00000000005E5403", instance="default")
    ))

    await asyncio.sleep(0.5)

    # Test 4: Get Personal Folder (with children)
    results.append(await run_tool_test(
        "get_personal_folder (with children)",
        get_personal_folder(include_children=True, instance="default")
    ))

    await asyncio.sleep(0.5)

    # Test 5: Get Personal Folder (without children)
    results.append(await run_tool_test(
        "get_personal_folder (no children)",
        get_personal_folder(include_children=False, instance="default")
    ))

    await asyncio.sleep(0.5)

    # Get personal folder to find a folder ID for testing
    personal_result = await get_personal_folder(include_children=True, instance="default")
    personal_data = json.loads(personal_result)

    if "error" not in personal_data and "id" in personal_data:
        folder_id = personal_data["id"]

        await asyncio.sleep(0.5)

        # Test 6: Get Folder by ID
        results.append(await run_tool_test(
            f"get_folder_by_id ({folder_id})",
            get_folder_by_id(folder_id=folder_id, include_children=True, instance="default")
        ))

        await asyncio.sleep(0.5)

        # Test 7: Get Content Path by ID
        results.append(await run_tool_test(
            f"get_content_path_by_id ({folder_id})",
            get_content_path_by_id(content_id=folder_id, instance="default")
        ))

        # If we have children, test getting one by path
        if "children" in personal_data and len(personal_data["children"]) > 0:
            # Get the path of the first child
            first_child = personal_data["children"][0]
            if "id" in first_child:
                await asyncio.sleep(0.5)

                path_result = await get_content_path_by_id(content_id=first_child["id"], instance="default")
                path_data = json.loads(path_result)

                if "error" not in path_data and "path" in path_data:
                    content_path = path_data["path"]

                    await asyncio.sleep(0.5)

                    # Test 8: Get Content by Path
                    results.append(await run_tool_test(
                        f"get_content_by_path ({content_path})",
                        get_content_by_path(content_path=content_path, instance="default")
                    ))

    # Note: export_content, export_global_folder, and export_admin_recommended_folder
    # are not tested here as they take a long time (async jobs) and may not be
    # available in all instances. They should be tested manually.

    print("\n" + "="*60)
    print(f"Test Summary: {sum(results)}/{len(results)} tests passed")
    print("="*60)

    print("\nNote: Long-running export tools not tested:")
    print("  - export_content")
    print("  - export_global_folder")
    print("  - export_admin_recommended_folder")
    print("These should be tested manually as they take 10+ seconds each.")

    return sum(results) == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
