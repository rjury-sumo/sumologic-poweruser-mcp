"""Helper functions for Sumo Logic search job operations."""

import re
from datetime import datetime, timedelta, timezone
from typing import Literal


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
