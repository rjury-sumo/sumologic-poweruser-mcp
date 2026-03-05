"""Helper functions and patterns for Sumo Logic audit index searches."""

from typing import Dict, List, Optional, Literal


# Common use case patterns for legacy audit index
LEGACY_AUDIT_USE_CASES = {
    "logins": {
        "description": "User login events",
        "query_pattern": '_index=sumologic_audit action=login | where _sourceCategory="user_activity"',
        "example_fields": ["user", "status", "method"]
    },
    "scheduled_search_triggers": {
        "description": "Scheduled search alert triggers",
        "query_pattern": '_index=sumologic_audit triggered AND _sourceCategory=scheduled_search',
        "example_fields": ["Name", "SchSearchId", "AlertType", "RecordType"]
    },
    "user_activity": {
        "description": "General user activity",
        "query_pattern": '_index=sumologic_audit _sourceCategory="user_activity"',
        "example_fields": ["user", "action", "status"]
    },
    "content_changes": {
        "description": "Content creation/modification/deletion",
        "query_pattern": '_index=sumologic_audit _sourceCategory="content"',
        "example_fields": ["user", "action", "content_type"]
    }
}


# Enterprise audit event name patterns and categories
ENTERPRISE_AUDIT_EVENT_CATEGORIES = {
    "authentication": {
        "description": "User authentication events",
        "example_events": ["UserLoginSuccess", "UserLoginFailure", "UserLogout", "MfaEnabled", "MfaDisabled"],
        "source_categories": ["userSessions", "accessKeys"]
    },
    "content_management": {
        "description": "Content library operations",
        "example_events": ["ContentCreated", "ContentUpdated", "ContentDeleted", "ContentMoved"],
        "source_categories": ["content", "dashboards", "searches"]
    },
    "data_collection": {
        "description": "Collector and source operations",
        "example_events": ["CollectorCreated", "CollectorUpdated", "SourceCreated", "SourceUpdated"],
        "source_categories": ["collectors", "sources"]
    },
    "cse_operations": {
        "description": "Cloud SIEM operations",
        "example_events": ["InsightCreated", "InsightUpdated", "InsightClosed"],
        "source_categories": ["cseInsight", "cseSignal", "cseRule"]
    },
    "user_management": {
        "description": "User and role management",
        "example_events": ["UserCreated", "UserUpdated", "UserDeleted", "RoleAssigned"],
        "source_categories": ["users", "roles"]
    },
    "monitoring": {
        "description": "Monitor and alert operations",
        "example_events": ["MonitorCreated", "MonitorUpdated", "MonitorTriggered"],
        "source_categories": ["monitors"]
    }
}


def build_legacy_audit_query(
    action: Optional[str] = None,
    status: Optional[str] = None,
    source_category: Optional[str] = None,
    keywords: Optional[str] = None,
    aggregate_by: Optional[List[str]] = None,
    limit: int = 100
) -> str:
    """
    Build a query for the legacy audit index (_index=sumologic_audit).

    Args:
        action: Action filter (e.g., "login", "create", "update")
        status: Status filter (e.g., "SUCCESS", "FAILURE")
        source_category: Source category filter (e.g., "user_activity", "scheduled_search")
        keywords: Additional keyword search terms
        aggregate_by: Fields to aggregate by (will add count operator)
        limit: Result limit (default 100)

    Returns:
        Constructed Sumo Logic query string
    """
    query_parts = ["_index=sumologic_audit"]

    if action:
        query_parts.append(f'action={action}')

    if status:
        query_parts.append(f'status={status}')

    if source_category:
        query_parts.append(f'_sourceCategory="{source_category}"')

    if keywords:
        query_parts.append(keywords)

    query = " ".join(query_parts)

    # Add aggregation if specified
    if aggregate_by:
        agg_fields = ", ".join(aggregate_by)
        query += f" | count by {agg_fields} | sort _count | limit {limit}"
    else:
        query += f" | limit {limit}"

    return query


def build_enterprise_audit_query(
    index: Literal["sumologic_audit_events", "sumologic_system_events"],
    event_name: Optional[str] = None,
    source_category: Optional[str] = None,
    operator_email: Optional[str] = None,
    keywords: Optional[str] = None,
    parse_json: bool = True,
    extract_fields: Optional[List[str]] = None,
    aggregate_by: Optional[List[str]] = None,
    limit: int = 100
) -> str:
    """
    Build a query for enterprise audit indexes (sumologic_audit_events or sumologic_system_events).

    Args:
        index: Which index to query
        event_name: Event name filter (e.g., "UserLoginSuccess", "InsightUpdated")
        source_category: Source category filter (e.g., "userSessions", "cseInsight")
        operator_email: Filter by operator email
        keywords: Additional keyword search terms
        parse_json: Whether to parse JSON fields (default True)
        extract_fields: List of JSON fields to extract (default: common fields)
        aggregate_by: Fields to aggregate by (will add count operator)
        limit: Result limit (default 100)

    Returns:
        Constructed Sumo Logic query string
    """
    query_parts = [f"_index={index}"]

    if source_category:
        query_parts.append(f'_sourceCategory={source_category}')

    if event_name:
        query_parts.append(event_name)

    if keywords:
        query_parts.append(keywords)

    query = " ".join(query_parts)

    # Add JSON parsing for enterprise audit events
    if parse_json:
        if extract_fields is None:
            # Default common fields
            extract_fields = [
                "eventName",
                "eventTime",
                "operator.email",
                "operator.id",
                "operator.sourceIp"
            ]

        fields_str = ", ".join([f'"{field}"' for field in extract_fields])
        field_names = [field.replace(".", "_") for field in extract_fields]
        field_names_str = ", ".join(field_names)

        query += f" | json {fields_str} as {field_names_str} nodrop"

        # Add operator email filter after parsing if specified
        if operator_email:
            query += f' | where operator_email = "{operator_email}"'

    # Add aggregation if specified
    if aggregate_by:
        agg_fields = ", ".join(aggregate_by)
        query += f" | count by {agg_fields} | sort _count | limit {limit}"
    else:
        query += f" | limit {limit}"

    return query


def get_audit_use_case_query(use_case: str) -> Optional[Dict[str, str]]:
    """
    Get a pre-built query for a common audit use case.

    Args:
        use_case: Use case name (e.g., "logins", "scheduled_search_triggers")

    Returns:
        Dictionary with query_pattern, description, and example_fields, or None
    """
    return LEGACY_AUDIT_USE_CASES.get(use_case)


def get_event_category_info(category: str) -> Optional[Dict[str, any]]:
    """
    Get information about an enterprise audit event category.

    Args:
        category: Category name (e.g., "authentication", "cse_operations")

    Returns:
        Dictionary with description, example_events, and source_categories, or None
    """
    return ENTERPRISE_AUDIT_EVENT_CATEGORIES.get(category)


def list_audit_use_cases() -> List[str]:
    """Return list of available legacy audit use case names."""
    return list(LEGACY_AUDIT_USE_CASES.keys())


def list_event_categories() -> List[str]:
    """Return list of available enterprise audit event categories."""
    return list(ENTERPRISE_AUDIT_EVENT_CATEGORIES.keys())


# Common system event patterns
SYSTEM_EVENT_USE_CASES = {
    "collector_source_health": {
        "description": "Monitor collector and source health events (unhealthy states)",
        "query_pattern": """_index=sumologic_system_events "Health-Change" unhealthy
| json field=_raw "status"
| json "eventType", "resourceIdentity.id" as eventType, resourceId
| json field=_raw "details.error" as error
| json field=_raw "details.trackerId" as trackerid
| json field=_raw "resourceIdentity.name" as resource_name
| max(_messagetime) as _messagetime, count by trackerid, error, resource_name, eventtype""",
        "use_for": "Scheduled search alert or monitor for unhealthy collectors/sources",
        "notes": [
            "Use resource_name as alertgroup for one alert per resource",
            "Can filter with: | where resource_name matches /regex/",
            "Can exclude chatty events with: | where !(error IN (...))",
            "See docs: https://service.au.sumologic.com/audit/docs/#tag/Health-Events-(System)"
        ]
    },
    "monitor_alerts": {
        "description": "Analyze monitor alert state changes and alert frequency",
        "query_pattern": """_index=sumologic_system_events _sourceCategory=alerts
| json field=_raw "details.monitorInfo.monitorId" as monitorid
| json field=_raw "details.name" as eventname
| json field=_raw "subsystem"
| json field=_raw "resourceIdentity.name" as name
| json field=_raw "resourceIdentity.id" as resourceid
| json field=_raw "details.alertingGroup.previousState" as previousstatus
| json field=_raw "details.alertingGroup.currentState" as status
| json field=_raw "details.alertingGroup.triggerValue" as value
| json field=_raw "details.alertingGroup.timeSeriesKey" as timeseries nodrop
| if (isempty(timeseries),"group",timeseries) as timeseries
| timeslice | where status !="Normal"
| count by name | sort _count""",
        "use_for": "Analyze monitor alert patterns and identify most frequently alerting monitors",
        "notes": [
            "Shows alert state changes (non-Normal states)",
            "Aggregates by monitor name to find highest alert counts",
            "Use timeslice for time-based analysis",
            "Filter by monitorid for specific monitor",
            "See docs: https://service.au.sumologic.com/audit/docs/#tag/Alerts-(System)"
        ]
    },
    "monitor_alert_timeline": {
        "description": "Timeline view of monitor alert status changes with duration",
        "query_pattern": """_index=sumologic_system_events _sourceCategory=alerts
| json field=_raw "details.monitorInfo.monitorId" as monitorid
| json field=_raw "details.name" as eventname
| json field=_raw "details.monitorInfo.triggerGranularity" as granularity
| json field=_raw "details.alertDuration" as duration nodrop
| if (isnull(duration),"0",duration) as duration
| replace(duration," ms","") as duration
| round(duration / 1000) as duration
| json field=_raw "subsystem"
| json field=_raw "resourceIdentity.name" as name
| json field=_raw "resourceIdentity.id" as resourceid
| json field=_raw "details.monitorInfo.monitorPath" as path
| json field=_raw "details.alertingGroup.previousState" as previousstatus
| json field=_raw "details.alertingGroup.currentState" as status
| json field=_raw "details.alertingGroup.triggerValue" as value
| json field=_raw "details.alertingGroup.timeSeriesKey" as timeseries nodrop
| if (isempty(timeseries),"group",timeseries) as timeseries
| replace(timeseries,/_violations=.+/,"") as timeseries
| _messagetime as time
| count by time, status, path, resourceid, name, timeseries, granularity, duration | fields -_count
| sort time
| formatdate(time,"yyyy-MM-dd hh:mm:ss ZZZZ") as time
| ceil(duration / 60) as duration_min | fields -duration""",
        "use_for": "View monitor alert timeline with status changes and alert durations",
        "notes": [
            "Shows chronological timeline of alert state changes",
            "Includes alert duration in minutes",
            "Shows monitor path, granularity, and time series grouping",
            "Useful for understanding alert patterns over time",
            "Can filter by specific monitors in scope",
            "resourceid can be used to build URLs to alerts",
            "See docs: https://service.au.sumologic.com/audit/docs/#tag/Alerts-(System)"
        ]
    }
}


def get_system_event_use_case(use_case: str) -> Optional[Dict[str, any]]:
    """
    Get a pre-built query for a common system event use case.

    Args:
        use_case: Use case name (e.g., "collector_source_health")

    Returns:
        Dictionary with query_pattern, description, and notes, or None
    """
    return SYSTEM_EVENT_USE_CASES.get(use_case)


def format_audit_help() -> str:
    """
    Generate help text for audit index searches.

    Returns:
        Formatted help string with use cases and event categories
    """
    help_text = ["# Sumo Logic Audit Index Help\n"]

    help_text.append("## Legacy Audit Index Use Cases (_index=sumologic_audit)\n")
    for use_case, info in LEGACY_AUDIT_USE_CASES.items():
        help_text.append(f"### {use_case}")
        help_text.append(f"Description: {info['description']}")
        help_text.append(f"Example fields: {', '.join(info['example_fields'])}\n")

    help_text.append("\n## Enterprise Audit Event Categories\n")
    for category, info in ENTERPRISE_AUDIT_EVENT_CATEGORIES.items():
        help_text.append(f"### {category}")
        help_text.append(f"Description: {info['description']}")
        help_text.append(f"Source categories: {', '.join(info['source_categories'])}")
        help_text.append(f"Example events: {', '.join(info['example_events'][:3])}\n")

    return "\n".join(help_text)
