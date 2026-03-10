#!/usr/bin/env python3
"""
Documentation Verification Script

Verifies that docs/mcp-tools-reference.md is synchronized with implemented tools.
Catches documentation drift early by comparing tool counts and names.

Usage:
    python scripts/verify_docs.py

Exit Codes:
    0 - Documentation is in sync
    1 - Mismatch detected (counts or names differ)
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def get_tools_from_code() -> List[str]:
    """
    Extract tool names from source code by finding @mcp.tool() decorators.

    Returns:
        List of tool function names
    """
    code_path = get_project_root() / "src" / "sumologic_poweruser_mcp" / "sumologic_poweruser_mcp.py"

    if not code_path.exists():
        print(f"❌ Error: Could not find {code_path}")
        sys.exit(1)

    code = code_path.read_text()

    # Find @mcp.tool() followed by async def function_name
    pattern = r'@mcp\.tool\(\)\s*\n\s*async def (\w+)\('
    matches = re.findall(pattern, code, re.MULTILINE)

    return sorted(matches)


def get_tools_from_docs() -> Tuple[int, List[str]]:
    """
    Extract tool information from documentation.

    Returns:
        Tuple of (documented_count_from_header, list_of_tool_names)
    """
    docs_path = get_project_root() / "docs" / "mcp-tools-reference.md"

    if not docs_path.exists():
        print(f"❌ Error: Could not find {docs_path}")
        sys.exit(1)

    docs = docs_path.read_text()

    # Get tool count from header
    header_match = re.search(r'Total Tools:\s*\*\*(\d+)\*\*', docs)
    header_count = int(header_match.group(1)) if header_match else 0

    # Get tool names from ### N. `tool_name` entries
    pattern = r'### \d+\. `(\w+)`'
    tool_names = re.findall(pattern, docs)

    return header_count, sorted(tool_names)


def compare_tools(code_tools: List[str], doc_tools: List[str]) -> bool:
    """
    Compare tool lists and report differences.

    Returns:
        True if tools match, False if differences found
    """
    code_set = set(code_tools)
    doc_set = set(doc_tools)

    missing_from_docs = code_set - doc_set
    extra_in_docs = doc_set - code_set

    all_match = True

    if missing_from_docs:
        print("\n❌ Tools implemented but NOT documented:")
        for tool in sorted(missing_from_docs):
            print(f"   - {tool}")
        all_match = False

    if extra_in_docs:
        print("\n❌ Tools documented but NOT implemented:")
        for tool in sorted(extra_in_docs):
            print(f"   - {tool}")
        all_match = False

    return all_match


def main():
    """Main verification logic."""
    print("🔍 Verifying documentation synchronization...\n")

    # Get tools from code
    code_tools = get_tools_from_code()
    code_count = len(code_tools)
    print(f"📝 Tools in code: {code_count}")

    # Get tools from documentation
    doc_header_count, doc_tools = get_tools_from_docs()
    doc_count = len(doc_tools)
    print(f"📚 Tools documented: {doc_count}")
    print(f"📊 Tool count in header: {doc_header_count}")

    # Check header count
    if doc_header_count != code_count:
        print(f"\n❌ Header count mismatch!")
        print(f"   Header says: {doc_header_count} tools")
        print(f"   Actually: {code_count} tools implemented")
        print(f"   Action: Update 'Total Tools: **{code_count}**' in docs/mcp-tools-reference.md")

    # Check tool counts match
    if code_count != doc_count:
        print(f"\n❌ Tool count mismatch!")
        print(f"   Code: {code_count} tools")
        print(f"   Docs: {doc_count} documented")

    # Compare tool names
    tools_match = compare_tools(code_tools, doc_tools)

    # Final verdict
    print("\n" + "=" * 60)
    if code_count == doc_count == doc_header_count and tools_match:
        print("✅ Documentation is in sync!")
        print(f"   {code_count} tools implemented and documented correctly")
        print("=" * 60)
        return 0
    else:
        print("❌ Documentation is OUT OF SYNC!")
        print("   Please update docs/mcp-tools-reference.md")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
