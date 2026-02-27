#!/usr/bin/env python3
"""Test field management tools."""

import asyncio
import json
from src.sumologic_mcp_server.sumologic_mcp_server import (
    list_custom_fields,
    list_field_extraction_rules,
    get_field_extraction_rule
)


async def main():
    print("Testing Field Management Tools\n")
    print("=" * 80)

    # Test 1: List custom fields
    print("\n1. Testing list_custom_fields...")
    print("-" * 80)
    try:
        result = await list_custom_fields(instance="default")
        data = json.loads(result)
        print(f"✓ Found {len(data.get('data', []))} custom fields")
        if data.get('data'):
            print(f"  Example field: {data['data'][0].get('fieldName', 'N/A')}")
    except Exception as e:
        print(f"✗ Error: {e}")

    # Test 2: List field extraction rules
    print("\n2. Testing list_field_extraction_rules...")
    print("-" * 80)
    try:
        result = await list_field_extraction_rules(limit=10, instance="default")
        data = json.loads(result)
        rules = data.get('data', [])
        print(f"✓ Found {len(rules)} field extraction rules")
        if rules:
            first_rule = rules[0]
            print(f"  Example rule: {first_rule.get('name', 'N/A')}")
            print(f"  Rule ID: {first_rule.get('id', 'N/A')}")

            # Test 3: Get specific FER by ID
            rule_id = first_rule.get('id')
            if rule_id:
                print(f"\n3. Testing get_field_extraction_rule for ID: {rule_id}...")
                print("-" * 80)
                try:
                    rule_result = await get_field_extraction_rule(rule_id=rule_id, instance="default")
                    rule_data = json.loads(rule_result)
                    print(f"✓ Retrieved FER: {rule_data.get('name', 'N/A')}")
                    print(f"  Enabled: {rule_data.get('enabled', False)}")
                    print(f"  Scope: {rule_data.get('scope', 'N/A')}")
                except Exception as e:
                    print(f"✗ Error: {e}")
        else:
            print("  No rules found, skipping get_field_extraction_rule test")
    except Exception as e:
        print(f"✗ Error: {e}")

    print("\n" + "=" * 80)
    print("Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
