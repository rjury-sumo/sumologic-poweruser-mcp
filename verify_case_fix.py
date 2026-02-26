#!/usr/bin/env python3
"""Verify case-insensitive field matching."""

# Simulate the field matching logic
def test_case_insensitive_lookup():
    """Test that case-insensitive field lookup works."""

    # Simulate a response from Sumo Logic where fields come back in lowercase
    record_map = {
        "_count": "100",
        "_view": "sumologic_audit",
        "_sourcecategory": "audit/logs",  # Note: lowercase!
        "_collector": "MyCollector",
        "_source": "MySource"
    }

    # Fields requested by user (mixed case)
    fields = ["_view", "_sourceCategory", "_collector", "_source"]

    result = {}

    for field in fields:
        # Try exact match first
        value = record_map.get(field)

        # If not found, try case-insensitive lookup
        if value is None:
            field_lower = field.lower()
            for key in record_map.keys():
                if key.lower() == field_lower:
                    value = record_map.get(key)
                    print(f"  Matched '{field}' to '{key}' via case-insensitive lookup")
                    break

        # Default to empty string if still not found
        if value is None:
            value = ""

        result[field] = value

    print("\nOriginal record_map keys:", list(record_map.keys()))
    print("Requested fields:", fields)
    print("\nExtracted values:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Verify
    assert result["_view"] == "sumologic_audit", "_view should match"
    assert result["_sourceCategory"] == "audit/logs", "_sourceCategory should match via case-insensitive lookup"
    assert result["_collector"] == "MyCollector", "_collector should match"
    assert result["_source"] == "MySource", "_source should match"

    print("\n✓ All assertions passed! Case-insensitive matching works correctly.")


if __name__ == "__main__":
    test_case_insensitive_lookup()
