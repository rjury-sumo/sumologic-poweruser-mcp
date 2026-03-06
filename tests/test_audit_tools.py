"""Tests for audit index search tools."""

import pytest

from src.sumologic_mcp_server.audit_helpers import (
    build_enterprise_audit_query,
    build_legacy_audit_query,
    get_audit_use_case_query,
    get_system_event_use_case,
    list_audit_use_cases,
    list_event_categories,
)


class TestLegacyAuditQueryBuilder:
    """Tests for legacy audit index query builder."""

    def test_basic_query(self):
        """Test basic query with no filters."""
        query = build_legacy_audit_query()
        assert "_index=sumologic_audit" in query
        assert "| limit 100" in query

    def test_action_filter(self):
        """Test with action filter."""
        query = build_legacy_audit_query(action="login")
        assert "action=login" in query

    def test_status_filter(self):
        """Test with status filter."""
        query = build_legacy_audit_query(status="SUCCESS")
        assert "status=SUCCESS" in query

    def test_source_category_filter(self):
        """Test with source category filter."""
        query = build_legacy_audit_query(source_category="user_activity")
        assert '_sourceCategory="user_activity"' in query

    def test_keywords(self):
        """Test with keywords."""
        query = build_legacy_audit_query(keywords="triggered")
        assert "triggered" in query

    def test_aggregation(self):
        """Test with aggregation."""
        query = build_legacy_audit_query(aggregate_by=["action", "status"])
        assert "| count by action, status" in query
        assert "| sort _count" in query

    def test_custom_limit(self):
        """Test with custom limit."""
        query = build_legacy_audit_query(limit=50)
        assert "| limit 50" in query


class TestEnterpriseAuditQueryBuilder:
    """Tests for enterprise audit index query builder."""

    def test_basic_audit_events_query(self):
        """Test basic audit events query."""
        query = build_enterprise_audit_query(index="sumologic_audit_events")
        assert "_index=sumologic_audit_events" in query
        assert "| json" in query
        assert "| limit 100" in query

    def test_basic_system_events_query(self):
        """Test basic system events query."""
        query = build_enterprise_audit_query(index="sumologic_system_events")
        assert "_index=sumologic_system_events" in query

    def test_event_name_filter(self):
        """Test with event name filter."""
        query = build_enterprise_audit_query(
            index="sumologic_audit_events", event_name="UserLoginSuccess"
        )
        assert "UserLoginSuccess" in query

    def test_source_category_filter(self):
        """Test with source category filter."""
        query = build_enterprise_audit_query(
            index="sumologic_audit_events", source_category="userSessions"
        )
        assert "_sourceCategory=userSessions" in query

    def test_operator_email_filter(self):
        """Test with operator email filter."""
        query = build_enterprise_audit_query(
            index="sumologic_audit_events", operator_email="user@example.com"
        )
        assert '| where operator_email = "user@example.com"' in query

    def test_json_parsing(self):
        """Test JSON field extraction."""
        query = build_enterprise_audit_query(index="sumologic_audit_events", parse_json=True)
        assert "| json" in query
        assert "eventName" in query
        assert "operator.email" in query

    def test_custom_extract_fields(self):
        """Test custom field extraction."""
        query = build_enterprise_audit_query(
            index="sumologic_audit_events", extract_fields=["customField1", "customField2"]
        )
        assert "customField1" in query
        assert "customField2" in query

    def test_aggregation(self):
        """Test with aggregation."""
        query = build_enterprise_audit_query(
            index="sumologic_audit_events", aggregate_by=["eventName", "operator_email"]
        )
        assert "| count by eventName, operator_email" in query


class TestUseCaseHelpers:
    """Tests for use case helper functions."""

    def test_list_audit_use_cases(self):
        """Test listing legacy audit use cases."""
        use_cases = list_audit_use_cases()
        assert "logins" in use_cases
        assert "scheduled_search_triggers" in use_cases
        assert "user_activity" in use_cases
        assert "content_changes" in use_cases

    def test_get_audit_use_case_query(self):
        """Test getting audit use case query."""
        use_case = get_audit_use_case_query("logins")
        assert use_case is not None
        assert "query_pattern" in use_case
        assert "description" in use_case
        assert "example_fields" in use_case
        assert "login" in use_case["query_pattern"].lower()

    def test_get_invalid_audit_use_case(self):
        """Test getting invalid use case."""
        use_case = get_audit_use_case_query("invalid_use_case")
        assert use_case is None

    def test_list_event_categories(self):
        """Test listing enterprise audit event categories."""
        categories = list_event_categories()
        assert "authentication" in categories
        assert "content_management" in categories
        assert "cse_operations" in categories

    def test_get_system_event_use_case(self):
        """Test getting system event use case."""
        use_case = get_system_event_use_case("collector_source_health")
        assert use_case is not None
        assert "query_pattern" in use_case
        assert "description" in use_case
        assert "notes" in use_case
        assert "Health-Change" in use_case["query_pattern"]

    def test_get_monitor_alerts_use_case(self):
        """Test monitor alerts use case."""
        use_case = get_system_event_use_case("monitor_alerts")
        assert use_case is not None
        assert "_sourceCategory=alerts" in use_case["query_pattern"]
        assert "count by name" in use_case["query_pattern"]

    def test_get_monitor_alert_timeline_use_case(self):
        """Test monitor alert timeline use case."""
        use_case = get_system_event_use_case("monitor_alert_timeline")
        assert use_case is not None
        assert "_sourceCategory=alerts" in use_case["query_pattern"]
        assert "alertDuration" in use_case["query_pattern"]
        assert "formatdate" in use_case["query_pattern"]

    def test_get_invalid_system_event_use_case(self):
        """Test getting invalid system event use case."""
        use_case = get_system_event_use_case("invalid_use_case")
        assert use_case is None


class TestQueryPatterns:
    """Tests for pre-built query patterns."""

    def test_logins_use_case_pattern(self):
        """Test logins use case pattern."""
        use_case = get_audit_use_case_query("logins")
        pattern = use_case["query_pattern"]
        assert "_index=sumologic_audit" in pattern
        assert "action=login" in pattern
        assert "_sourceCategory" in pattern

    def test_scheduled_search_triggers_pattern(self):
        """Test scheduled search triggers pattern."""
        use_case = get_audit_use_case_query("scheduled_search_triggers")
        pattern = use_case["query_pattern"]
        assert "triggered" in pattern
        assert "scheduled_search" in pattern

    def test_collector_health_pattern(self):
        """Test collector health pattern."""
        use_case = get_system_event_use_case("collector_source_health")
        pattern = use_case["query_pattern"]
        assert "Health-Change" in pattern
        assert "unhealthy" in pattern
        assert "resourceIdentity.name" in pattern
        assert "max(_messagetime)" in pattern

    def test_monitor_alerts_pattern(self):
        """Test monitor alerts pattern."""
        use_case = get_system_event_use_case("monitor_alerts")
        pattern = use_case["query_pattern"]
        assert "details.monitorInfo.monitorId" in pattern
        assert "currentState" in pattern
        assert 'where status !="Normal"' in pattern

    def test_monitor_timeline_pattern(self):
        """Test monitor alert timeline pattern."""
        use_case = get_system_event_use_case("monitor_alert_timeline")
        pattern = use_case["query_pattern"]
        assert "alertDuration" in pattern
        assert "formatdate" in pattern
        assert "duration_min" in pattern
        assert "sort time" in pattern


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
