"""Helper functions for Sumo Logic search job operations and query construction."""

import re
from datetime import datetime, timedelta, timezone
from typing import Literal, List, Dict, Any


def detect_query_type(query: str) -> Literal['messages', 'records']:
    """
    Detect if a Sumo Logic query returns records (aggregates) or messages (raw logs).

    Args:
        query: Sumo Logic search query

    Returns:
        'records' for aggregate queries, 'messages' for raw log queries

    Examples:
        >>> detect_query_type("error | count by _sourceHost")
        'records'
        >>> detect_query_type("_sourceCategory=prod/app")
        'messages'
        >>> detect_query_type("error | timeslice 1h | count")
        'records'
    """
    query_lower = query.lower()

    # Aggregate operators that produce records
    aggregate_keywords = [
        'count',
        'sum',
        'avg',
        'min',
        'max',
        'pct',
        'stddev',
        'first',
        'last',
        'most_recent',
        'least_recent',
        'group by',
        ' by ',  # e.g., "| count by field"
        'timeslice',
    ]

    for keyword in aggregate_keywords:
        if keyword in query_lower:
            return 'records'

    return 'messages'


def parse_relative_time(time_value: str | int) -> int:
    """
    Parse time value and convert to epoch milliseconds.

    Supports:
    - Relative times: "-1h", "-30m", "-2d", "-1w", "now"
    - ISO format strings: "2024-01-01T00:00:00Z"
    - Epoch milliseconds: 1704067200000

    Args:
        time_value: Time specification

    Returns:
        Epoch milliseconds

    Examples:
        >>> parse_relative_time("now")  # doctest: +SKIP
        1708876543000
        >>> parse_relative_time("-1h")  # doctest: +SKIP
        1708872943000
        >>> parse_relative_time("2024-01-01T00:00:00Z")
        1704067200000
    """
    # If it's already an integer (epoch milliseconds), return as-is
    if isinstance(time_value, int):
        return time_value

    # Convert to string for processing
    time_str = str(time_value).strip()

    # Handle "now"
    if time_str.lower() == "now":
        return int(datetime.now(timezone.utc).timestamp() * 1000)

    # Handle relative time formats like "-1h", "-30m", "-2d", "-1w"
    relative_pattern = r'^([+-]?)(\d+)([smhdw])$'
    match = re.match(relative_pattern, time_str.lower())

    if match:
        sign, amount, unit = match.groups()
        amount = int(amount)

        # Default to negative if no sign specified (going back in time)
        if sign != '+':
            amount = -amount

        # Convert unit to timedelta
        unit_map = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days',
            'w': 'weeks'
        }

        if unit in unit_map:
            delta_kwargs = {unit_map[unit]: amount}
            target_time = datetime.now(timezone.utc) + timedelta(**delta_kwargs)
            return int(target_time.timestamp() * 1000)

    # Try to parse as ISO format
    try:
        # Handle various ISO formats
        for fmt in [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]:
            try:
                dt = datetime.strptime(time_str, fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

        # If none of the formats worked, try parsing as epoch milliseconds
        return int(float(time_str))

    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid time format: {time_value}. "
            "Supported formats: ISO datetime (2024-01-01T00:00:00Z), "
            "epoch milliseconds (1704067200000), or "
            "relative time (-1h, -30m, -2d, -1w, now)"
        ) from e


def format_time_range_human(from_ms: int, to_ms: int) -> str:
    """
    Format time range in human-readable format.

    Args:
        from_ms: Start time in epoch milliseconds
        to_ms: End time in epoch milliseconds

    Returns:
        Human-readable time range string

    Examples:
        >>> format_time_range_human(1704067200000, 1704070800000)
        '2024-01-01 00:00:00 to 2024-01-01 01:00:00 (1.0h)'
    """
    from_dt = datetime.fromtimestamp(from_ms / 1000, tz=timezone.utc)
    to_dt = datetime.fromtimestamp(to_ms / 1000, tz=timezone.utc)

    # Calculate duration
    duration_ms = to_ms - from_ms
    duration_hours = duration_ms / (1000 * 60 * 60)

    from_str = from_dt.strftime('%Y-%m-%d %H:%M:%S')
    to_str = to_dt.strftime('%Y-%m-%d %H:%M:%S')

    if duration_hours < 1:
        duration_str = f"{duration_hours * 60:.0f}m"
    elif duration_hours < 24:
        duration_str = f"{duration_hours:.1f}h"
    else:
        duration_str = f"{duration_hours / 24:.1f}d"

    return f"{from_str} to {to_str} ({duration_str})"


# Query Construction Helpers

def build_scope_expression(
    source_category: str | None = None,
    index: str | None = None,
    view: str | None = None,
    keywords: List[str] | None = None,
    additional_metadata: Dict[str, str] | None = None
) -> str:
    """
    Build a Sumo Logic scope expression from components.

    Args:
        source_category: Source category filter (e.g., "prod/app", "*cloudtrail*")
        index: Index/partition filter (also known as _view or _index)
        view: View filter (alias for index)
        keywords: List of keywords to include in scope
        additional_metadata: Additional metadata filters (e.g., {"_sourceHost": "server1"})

    Returns:
        Formatted scope expression

    Examples:
        >>> build_scope_expression(source_category="prod/app", keywords=["error"])
        '_sourceCategory=prod/app error'
        >>> build_scope_expression(index="cloudtrail", keywords=["errorCode", "AccessDenied"])
        '_index=cloudtrail errorCode AccessDenied'
        >>> build_scope_expression(
        ...     source_category="*aws*",
        ...     additional_metadata={"_sourceHost": "server1"}
        ... )
        '_sourceCategory=*aws* _sourceHost=server1'
    """
    parts = []

    # Add source category if provided
    if source_category:
        parts.append(f"_sourceCategory={source_category}")

    # Add index/view if provided (index takes precedence)
    idx = index or view
    if idx:
        parts.append(f"_index={idx}")

    # Add additional metadata filters
    if additional_metadata:
        for key, value in additional_metadata.items():
            parts.append(f"{key}={value}")

    # Add keywords
    if keywords:
        parts.extend(keywords)

    return " ".join(parts)


def suggest_scope_from_discovery(metadata_results: Dict[str, Any]) -> str:
    """
    Suggest optimal scope expression based on discovery/exploration results.

    Args:
        metadata_results: Results from explore_log_metadata tool

    Returns:
        Suggested scope expression

    Examples:
        >>> results = {
        ...     "aggregates": [
        ...         {"_view": "cloudtrail", "_sourceCategory": "aws/cloudtrail", "count": 1000},
        ...         {"_view": "default", "_sourceCategory": "app/logs", "count": 100}
        ...     ]
        ... }
        >>> suggest_scope_from_discovery(results)
        '_index=cloudtrail _sourceCategory=aws/cloudtrail'
    """
    # Extract first/highest volume result
    if "aggregates" in metadata_results and metadata_results["aggregates"]:
        first = metadata_results["aggregates"][0]
        parts = []

        if "_view" in first and first["_view"]:
            parts.append(f"_index={first['_view']}")

        if "_sourceCategory" in first and first["_sourceCategory"]:
            parts.append(f"_sourceCategory={first['_sourceCategory']}")

        return " ".join(parts) if parts else "*"

    return "*"


def get_operator_category_info() -> Dict[str, List[str]]:
    """
    Get categorized list of Sumo Logic search operators.

    Returns:
        Dictionary mapping category to list of operators

    Categories based on https://help.sumologic.com/docs/search/search-cheat-sheets/log-operators/
    """
    return {
        "parsing": [
            "parse", "parse regex", "parse anchor", "json", "xml", "csv",
            "keyvalue", "split", "extract"
        ],
        "filtering": [
            "where", "matches", "in", "not in", "contains", "startswith", "endswith"
        ],
        "aggregation": [
            "count", "sum", "avg", "min", "max", "pct", "stddev",
            "first", "last", "most_recent", "least_recent",
            "count_distinct", "count_frequent"
        ],
        "time_series": [
            "timeslice", "transpose", "rollingstd", "smooth", "predict"
        ],
        "grouping": [
            "group by", "by"
        ],
        "formatting": [
            "fields", "format", "concat", "substring", "toLowerCase", "toUpperCase",
            "trim", "replace", "urlencode", "urldecode"
        ],
        "math": [
            "abs", "ceil", "floor", "round", "sqrt", "pow", "exp", "log"
        ],
        "conditional": [
            "if", "isEmpty", "isNull", "isBlank", "isNumeric", "isValidIP"
        ],
        "lookup": [
            "lookup", "cat", "save", "lookupContains"
        ],
        "geo": [
            "geoip", "latitude", "longitude"
        ],
        "time": [
            "formatDate", "parseDate", "now", "toMillis"
        ],
        "sorting": [
            "sort", "top", "topk"
        ],
        "other": [
            "limit", "dedup", "join", "merge", "compare", "outlier", "fillmissing"
        ]
    }


def get_common_query_patterns() -> Dict[str, str]:
    """
    Get common Sumo Logic query patterns with examples.

    Returns:
        Dictionary mapping pattern name to example query
    """
    return {
        "raw_logs": "_sourceCategory=prod/app error",

        "parse_json_explicit": """_sourceCategory=prod/app
| json field=_raw "errorCode" as error_code
| json field=_raw "errorMessage" as error_msg""",

        "parse_tab_separated": """_sourceCategory=cloudfront
| parse "*\\t*\\t*\\t*" as field1, field2, field3, field4""",

        "parse_regex": """_sourceCategory=app/logs
| parse regex "(?<timestamp>\\d{4}-\\d{2}-\\d{2}) (?<level>\\w+) (?<message>.*)"
""",

        "categorical_count": """_sourceCategory=prod/app error
| json "errorCode" as code
| count by code
| sort _count desc""",

        "categorical_top_values": """_sourceCategory=prod/app error
| json "errorCode" as code
| count by code
| top 10 code by _count""",

        "time_series_simple": """_sourceCategory=prod/app error
| timeslice 5m
| count by _timeslice""",

        "time_series_by_field": """_sourceCategory=prod/app error
| json "errorCode" as code
| timeslice 5m
| count by _timeslice, code
| transpose row _timeslice column code""",

        "filtering_where": """_sourceCategory=prod/app
| json "status" as status_code
| where status_code >= 400 and status_code < 500""",

        "filtering_matches": """_sourceCategory=prod/app
| json "errorCode" as error
| where error matches "*Limit*" or error matches "*Exceeded*" """,

        "aggregation_stats": """_sourceCategory=prod/app
| json "duration" as duration_ms
| avg(duration_ms) as avg_duration,
  max(duration_ms) as max_duration,
  pct(duration_ms, 95) as p95_duration""",

        "time_compare": """_sourceCategory=prod/app
| timeslice 1h
| count by _timeslice
| compare with timeshift 24h""",

        "geo_location": """_sourceCategory=web/access
| parse "* * *" as method, path, client_ip
| geoip client_ip
| count by latitude, longitude, country_name"""
    }


def validate_query_structure(query: str) -> Dict[str, Any]:
    """
    Validate and analyze Sumo Logic query structure.

    Args:
        query: Sumo Logic search query

    Returns:
        Dictionary with validation results and warnings

    Examples:
        >>> validate_query_structure("_sourceCategory=prod error | count")
        {
            'is_valid': True,
            'has_scope': True,
            'has_aggregation': True,
            'query_type': 'records',
            'warnings': []
        }
    """
    result = {
        "is_valid": True,
        "has_scope": False,
        "has_parse": False,
        "has_filter": False,
        "has_aggregation": False,
        "query_type": detect_query_type(query),
        "warnings": [],
        "suggestions": []
    }

    query_lower = query.lower()

    # Check for scope (metadata or keywords before first pipe)
    first_pipe = query.find("|")
    scope_part = query[:first_pipe] if first_pipe > 0 else query

    if "_sourcecategory" in scope_part.lower() or "_index" in scope_part.lower():
        result["has_scope"] = True
    elif scope_part.strip() and scope_part.strip() != "*":
        result["has_scope"] = True
    else:
        result["warnings"].append("Query has no specific scope - may scan all data")
        result["suggestions"].append("Add _sourceCategory or _index to limit scan volume")

    # Check for parsing
    parse_operators = ["json", "parse", "csv", "xml", "keyvalue"]
    if any(op in query_lower for op in parse_operators):
        result["has_parse"] = True

    # Check for filtering
    if "where" in query_lower or "matches" in query_lower:
        result["has_filter"] = True

    # Check for aggregation
    if result["query_type"] == "records":
        result["has_aggregation"] = True

    # Additional validation
    if result["query_type"] == "records" and not result["has_scope"]:
        result["warnings"].append(
            "Aggregate query without scope may be expensive on large data sets"
        )

    return result
