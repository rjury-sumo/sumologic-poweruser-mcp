"""Tests for response_filter module."""

import json
import pytest
from src.sumologic_mcp_server.response_filter import (
    find_array_key,
    filter_by_field,
    filter_by_multiple_fields,
    filter_by_custom,
    truncate_response,
    filter_response,
    get_common_search_fields,
)


class TestFindArrayKey:
    """Tests for find_array_key function."""

    def test_common_key_data(self):
        """Test detection of 'data' key."""
        response = {'data': [{'id': 1}], 'count': 1}
        assert find_array_key(response) == 'data'

    def test_common_key_collectors(self):
        """Test detection of 'collectors' key."""
        response = {'collectors': [{'id': 1}], 'metadata': {}}
        assert find_array_key(response) == 'collectors'

    def test_uncommon_key(self):
        """Test detection of uncommon array key."""
        response = {'customArray': [{'id': 1}], 'status': 'ok'}
        assert find_array_key(response) == 'customArray'

    def test_no_array(self):
        """Test response with no array."""
        response = {'status': 'ok', 'count': 0}
        assert find_array_key(response) is None

    def test_empty_array(self):
        """Test response with empty array."""
        response = {'data': [], 'count': 0}
        assert find_array_key(response) == 'data'


class TestFilterByField:
    """Tests for filter_by_field function."""

    def setup_method(self):
        """Set up test data."""
        self.items = [
            {'id': 1, 'name': 'prod-collector', 'description': 'Production'},
            {'id': 2, 'name': 'dev-collector', 'description': 'Development'},
            {'id': 3, 'name': 'staging-collector', 'description': 'Staging'},
            {'id': 4, 'name': 'PROD-backup', 'description': 'Production Backup'},
        ]

    def test_substring_match_case_insensitive(self):
        """Test substring matching (default)."""
        result = filter_by_field(self.items, 'name', 'prod')
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 4

    def test_exact_match_case_insensitive(self):
        """Test exact matching."""
        result = filter_by_field(
            self.items, 'name', 'prod-collector', exact_match=True
        )
        assert len(result) == 1
        assert result[0]['id'] == 1

    def test_case_sensitive(self):
        """Test case-sensitive matching."""
        result = filter_by_field(
            self.items, 'name', 'prod', case_sensitive=True
        )
        assert len(result) == 1
        assert result[0]['id'] == 1

    def test_no_matches(self):
        """Test no matching items."""
        result = filter_by_field(self.items, 'name', 'nonexistent')
        assert len(result) == 0

    def test_field_not_in_items(self):
        """Test filtering on field that doesn't exist."""
        result = filter_by_field(self.items, 'missing_field', 'value')
        assert len(result) == 0


class TestFilterByMultipleFields:
    """Tests for filter_by_multiple_fields function."""

    def setup_method(self):
        """Set up test data."""
        self.items = [
            {'id': 1, 'name': 'security-dashboard', 'description': 'Security metrics'},
            {'id': 2, 'name': 'app-dashboard', 'description': 'Application performance'},
            {'id': 3, 'name': 'infra-dashboard', 'description': 'Security and infrastructure'},
        ]

    def test_search_multiple_fields(self):
        """Test searching across multiple fields."""
        result = filter_by_multiple_fields(
            self.items, 'security', ['name', 'description']
        )
        assert len(result) == 2
        assert result[0]['id'] == 1  # matches in name
        assert result[1]['id'] == 3  # matches in description

    def test_search_single_field(self):
        """Test searching single field."""
        result = filter_by_multiple_fields(
            self.items, 'security', ['name']
        )
        assert len(result) == 1
        assert result[0]['id'] == 1

    def test_case_sensitive_search(self):
        """Test case-sensitive search."""
        result = filter_by_multiple_fields(
            self.items, 'Security', ['name', 'description'], case_sensitive=True
        )
        assert len(result) == 2
        # Only items with capital 'S' in Security

    def test_deduplication(self):
        """Test that items are not duplicated if multiple fields match."""
        items = [
            {'id': 1, 'name': 'test', 'description': 'test description'},
        ]
        result = filter_by_multiple_fields(
            items, 'test', ['name', 'description']
        )
        assert len(result) == 1


class TestFilterByCustom:
    """Tests for filter_by_custom function."""

    def test_custom_filter_function(self):
        """Test custom filter function."""
        items = [
            {'id': 1, 'alive': True},
            {'id': 2, 'alive': False},
            {'id': 3, 'alive': True},
        ]
        result = filter_by_custom(items, lambda x: x.get('alive', False))
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 3

    def test_complex_custom_filter(self):
        """Test complex custom filter."""
        items = [
            {'id': 1, 'count': 100, 'enabled': True},
            {'id': 2, 'count': 50, 'enabled': True},
            {'id': 3, 'count': 150, 'enabled': False},
        ]
        # Filter for enabled items with count > 75
        result = filter_by_custom(
            items,
            lambda x: x.get('enabled', False) and x.get('count', 0) > 75
        )
        assert len(result) == 1
        assert result[0]['id'] == 1


class TestTruncateResponse:
    """Tests for truncate_response function."""

    def test_truncate_by_item_count(self):
        """Test truncation by item count."""
        response = {
            'data': [{'id': i} for i in range(100)],
            'count': 100
        }
        result, was_truncated = truncate_response(response, max_items=10)

        assert was_truncated
        assert len(result['data']) == 10
        assert result['_metadata']['original_count'] == 100
        assert result['_metadata']['returned_count'] == 10

    def test_truncate_by_bytes(self):
        """Test truncation by byte size."""
        response = {
            'data': [{'id': i, 'data': 'x' * 1000} for i in range(100)]
        }
        result, was_truncated = truncate_response(response, max_bytes=10000)

        assert was_truncated
        assert len(json.dumps(result)) <= 10000

    def test_no_truncation_needed(self):
        """Test when no truncation is needed."""
        response = {'data': [{'id': 1}, {'id': 2}]}
        result, was_truncated = truncate_response(response, max_items=10)

        assert not was_truncated
        assert len(result['data']) == 2

    def test_no_array_key(self):
        """Test truncation with no array key."""
        response = {'status': 'ok'}
        result, was_truncated = truncate_response(response, max_items=10)

        assert not was_truncated
        assert result == response


class TestFilterResponse:
    """Tests for filter_response function."""

    def setup_method(self):
        """Set up test data."""
        self.response = {
            'collectors': [
                {'id': 1, 'name': 'prod-collector', 'alive': True},
                {'id': 2, 'name': 'dev-collector', 'alive': False},
                {'id': 3, 'name': 'staging-collector', 'alive': True},
                {'id': 4, 'name': 'prod-backup', 'alive': True},
            ],
            'totalCount': 4
        }

    def test_filter_by_field(self):
        """Test filtering by single field."""
        result = filter_response(
            self.response,
            field='name',
            value='prod'
        )

        assert len(result['collectors']) == 2
        assert result['_metadata']['original_count'] == 4
        assert result['_metadata']['filtered_count'] == 2
        assert result['_metadata']['was_filtered']

    def test_filter_by_search_term(self):
        """Test filtering by search term."""
        result = filter_response(
            self.response,
            search_term='prod',
            search_fields=['name']
        )

        assert len(result['collectors']) == 2

    def test_custom_filter(self):
        """Test custom filter function."""
        result = filter_response(
            self.response,
            custom_filter=lambda c: c.get('alive', False)
        )

        assert len(result['collectors']) == 3

    def test_filter_with_max_items(self):
        """Test filtering with item limit."""
        result = filter_response(
            self.response,
            field='alive',
            value='true',
            max_items=2
        )

        assert result['_metadata']['filtered_count'] == 3
        assert result['_metadata']['returned_count'] == 2
        assert result['_metadata']['was_truncated']

    def test_no_filter_applied(self):
        """Test with no filter specified."""
        result = filter_response(self.response)

        # No filtering, but metadata is added
        assert len(result['collectors']) == 4
        assert not result['_metadata']['was_filtered']


class TestGetCommonSearchFields:
    """Tests for get_common_search_fields function."""

    def test_collectors_fields(self):
        """Test common fields for collectors."""
        fields = get_common_search_fields('collectors')
        assert 'name' in fields
        assert 'description' in fields
        assert 'hostName' in fields

    def test_dashboards_fields(self):
        """Test common fields for dashboards."""
        fields = get_common_search_fields('dashboards')
        assert 'name' in fields
        assert 'description' in fields

    def test_unknown_type_fallback(self):
        """Test fallback for unknown types."""
        fields = get_common_search_fields('unknown')
        assert 'name' in fields
        assert 'description' in fields


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_realistic_collector_filtering(self):
        """Test realistic collector filtering scenario."""
        # Simulate large collector response
        response = {
            'collectors': [
                {
                    'id': i,
                    'name': f'{"prod" if i % 3 == 0 else "dev"}-collector-{i}',
                    'description': f'Collector {i}',
                    'alive': i % 2 == 0,
                    'collectorType': 'Installed'
                }
                for i in range(500)
            ]
        }

        # Filter for production collectors that are alive
        result = filter_response(
            response,
            custom_filter=lambda c: 'prod' in c['name'] and c['alive'],
            max_items=50
        )

        assert result['_metadata']['original_count'] == 500
        assert result['_metadata']['returned_count'] <= 50
        # Verify all returned items match criteria
        for collector in result['collectors']:
            assert 'prod' in collector['name']
            assert collector['alive']

    def test_dashboard_search_with_truncation(self):
        """Test dashboard search with size limits."""
        response = {
            'data': [
                {
                    'id': i,
                    'name': f'Dashboard {i}',
                    'description': 'Security' if i < 100 else 'Performance'
                }
                for i in range(1000)
            ]
        }

        result = filter_response(
            response,
            search_term='Security',
            search_fields=['name', 'description'],
            max_items=25
        )

        assert result['_metadata']['filtered_count'] == 100
        assert result['_metadata']['returned_count'] == 25
