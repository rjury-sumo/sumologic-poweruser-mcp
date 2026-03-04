"""
Response filtering utilities for handling large API responses.

This module provides client-side filtering for Sumo Logic API responses
that may exceed MCP size limits. It auto-detects array keys and supports
filtering by various criteria.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, Callable

logger = logging.getLogger(__name__)


def find_array_key(response: Dict[str, Any]) -> Optional[str]:
    """
    Auto-detect the array key in a Sumo Logic API response.

    Sumo Logic APIs return arrays with various top-level key names:
    - 'data' (most common)
    - 'collectors'
    - 'sources'
    - 'dashboards'
    - 'users'
    - 'monitors'
    - 'fields'
    - 'rules'
    etc.

    Args:
        response: API response dictionary

    Returns:
        Name of the array key, or None if no array found
    """
    # Check for common keys first (performance optimization)
    # Order matters - most common first for performance
    common_keys = ['data', 'dashboards', 'collectors', 'sources', 'users',
                   'monitors', 'fields', 'rules', 'partitions', 'roles']

    for key in common_keys:
        if key in response and isinstance(response[key], list):
            return key

    # Fall back to scanning all keys
    for key, value in response.items():
        if isinstance(value, list) and len(value) > 0:
            return key

    return None


def filter_by_field(
    items: List[Dict[str, Any]],
    field: str,
    value: str,
    case_sensitive: bool = False,
    exact_match: bool = False
) -> List[Dict[str, Any]]:
    """
    Filter array items by a field value.

    Args:
        items: List of items to filter
        field: Field name to filter on (e.g., 'name', 'id', 'description')
        value: Value to match
        case_sensitive: Whether to perform case-sensitive matching
        exact_match: Whether to require exact match (vs substring)

    Returns:
        Filtered list of items
    """
    if not items:
        return []

    filtered = []
    search_value = value if case_sensitive else value.lower()

    for item in items:
        if field not in item:
            continue

        item_value = str(item[field])
        compare_value = item_value if case_sensitive else item_value.lower()

        if exact_match:
            if compare_value == search_value:
                filtered.append(item)
        else:
            if search_value in compare_value:
                filtered.append(item)

    return filtered


def filter_by_multiple_fields(
    items: List[Dict[str, Any]],
    search_term: str,
    fields: List[str],
    case_sensitive: bool = False
) -> List[Dict[str, Any]]:
    """
    Filter items by searching across multiple fields.

    Useful for open-ended search where user might be looking for
    a term in name, description, or other text fields.

    Args:
        items: List of items to filter
        search_term: Term to search for
        fields: List of field names to search in
        case_sensitive: Whether to perform case-sensitive matching

    Returns:
        Filtered list of items (deduplicated)
    """
    if not items:
        return []

    filtered = []
    seen_ids = set()
    search_value = search_term if case_sensitive else search_term.lower()

    for item in items:
        # Use 'id' field for deduplication if available
        item_id = item.get('id', id(item))
        if item_id in seen_ids:
            continue

        # Check if search term appears in any of the specified fields
        for field in fields:
            if field not in item:
                continue

            item_value = str(item[field])
            compare_value = item_value if case_sensitive else item_value.lower()

            if search_value in compare_value:
                filtered.append(item)
                seen_ids.add(item_id)
                break  # Found match, no need to check other fields

    return filtered


def filter_by_custom(
    items: List[Dict[str, Any]],
    filter_fn: Callable[[Dict[str, Any]], bool]
) -> List[Dict[str, Any]]:
    """
    Filter items using a custom filter function.

    Args:
        items: List of items to filter
        filter_fn: Function that takes an item and returns True to include it

    Returns:
        Filtered list of items
    """
    return [item for item in items if filter_fn(item)]


def truncate_response(
    response: Dict[str, Any],
    max_items: Optional[int] = None,
    max_bytes: Optional[int] = None
) -> tuple[Dict[str, Any], bool]:
    """
    Truncate response to stay within size limits.

    Args:
        response: API response dictionary
        max_items: Maximum number of items to include in array
        max_bytes: Maximum response size in bytes

    Returns:
        Tuple of (truncated_response, was_truncated)
    """
    array_key = find_array_key(response)

    if not array_key:
        # No array found, return as-is
        return response, False

    items = response[array_key]
    original_count = len(items)
    was_truncated = False

    # Apply item limit if specified
    if max_items and len(items) > max_items:
        items = items[:max_items]
        was_truncated = True

    # Build truncated response
    truncated = response.copy()
    truncated[array_key] = items

    # Apply byte limit if specified
    if max_bytes:
        while len(json.dumps(truncated)) > max_bytes and len(items) > 0:
            items = items[:len(items) // 2]  # Binary search approach
            truncated[array_key] = items
            was_truncated = True

    # Add metadata about truncation
    if was_truncated:
        truncated['_metadata'] = truncated.get('_metadata', {})
        truncated['_metadata']['truncated'] = True
        truncated['_metadata']['original_count'] = original_count
        truncated['_metadata']['returned_count'] = len(items)
        truncated['_metadata']['array_key'] = array_key

    return truncated, was_truncated


def filter_response(
    response: Dict[str, Any],
    field: Optional[str] = None,
    value: Optional[str] = None,
    search_term: Optional[str] = None,
    search_fields: Optional[List[str]] = None,
    case_sensitive: bool = False,
    exact_match: bool = False,
    max_items: Optional[int] = None,
    max_bytes: Optional[int] = None,
    custom_filter: Optional[Callable[[Dict[str, Any]], bool]] = None
) -> Dict[str, Any]:
    """
    Comprehensive filtering function for API responses.

    This is the main entry point for filtering large responses.
    Auto-detects array key and applies requested filtering.

    Args:
        response: API response dictionary
        field: Single field to filter on (requires value)
        value: Value to match for field filter
        search_term: Term to search for across multiple fields (requires search_fields)
        search_fields: List of fields to search in
        case_sensitive: Whether to perform case-sensitive matching
        exact_match: Whether to require exact match for field filter
        max_items: Maximum items to return (applied after filtering)
        max_bytes: Maximum response size in bytes
        custom_filter: Custom filter function

    Returns:
        Filtered response dictionary with metadata

    Examples:
        # Filter collectors by name
        filtered = filter_response(response, field='name', value='prod')

        # Search dashboards by term in name or description
        filtered = filter_response(
            response,
            search_term='security',
            search_fields=['name', 'description']
        )

        # Custom filter for active collectors
        filtered = filter_response(
            response,
            custom_filter=lambda c: c.get('alive', False)
        )
    """
    # Find the array key
    array_key = find_array_key(response)

    if not array_key:
        logger.warning("No array found in response, returning as-is")
        return response

    items = response[array_key]
    original_count = len(items)

    # Apply filtering
    if custom_filter:
        items = filter_by_custom(items, custom_filter)
    elif field and value:
        items = filter_by_field(items, field, value, case_sensitive, exact_match)
    elif search_term and search_fields:
        items = filter_by_multiple_fields(items, search_term, search_fields, case_sensitive)

    # Build filtered response
    filtered = response.copy()
    filtered[array_key] = items
    filtered_count = len(items)

    # Apply size limits
    if max_items or max_bytes:
        filtered, was_truncated = truncate_response(filtered, max_items, max_bytes)
        final_count = len(filtered[array_key])
    else:
        final_count = filtered_count
        was_truncated = False

    # Add metadata
    filtered['_metadata'] = {
        'array_key': array_key,
        'original_count': original_count,
        'filtered_count': filtered_count,
        'returned_count': final_count,
        'was_filtered': filtered_count < original_count,
        'was_truncated': was_truncated
    }

    if field and value:
        filtered['_metadata']['filter'] = {
            'field': field,
            'value': value,
            'case_sensitive': case_sensitive,
            'exact_match': exact_match
        }
    elif search_term and search_fields:
        filtered['_metadata']['filter'] = {
            'search_term': search_term,
            'search_fields': search_fields,
            'case_sensitive': case_sensitive
        }

    logger.info(
        f"Filtered response: {original_count} -> {filtered_count} -> {final_count} items "
        f"(array_key='{array_key}')"
    )

    return filtered


def get_common_search_fields(array_key: str) -> List[str]:
    """
    Get common search fields for a given array type.

    Returns sensible defaults for search_fields based on the
    detected array key name.

    Args:
        array_key: The array key name (e.g., 'collectors', 'dashboards')

    Returns:
        List of field names to search
    """
    field_map = {
        'collectors': ['name', 'description', 'hostName'],
        'sources': ['name', 'description', 'category'],
        'dashboards': ['name', 'description'],
        'users': ['firstName', 'lastName', 'email'],
        'monitors': ['name', 'description'],
        'fields': ['fieldName'],
        'rules': ['name', 'scope'],
        'partitions': ['name'],
        'roles': ['name', 'description'],
        'data': ['name', 'title', 'description'],  # Generic fallback
    }

    return field_map.get(array_key, ['name', 'description'])
