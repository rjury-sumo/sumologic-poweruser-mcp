"""Reusable Sumo Logic query patterns and operators.

This module provides common query patterns used across multiple tools to ensure
consistent behavior, especially for handling edge cases like null values and
division by zero.

Key Patterns:
    - ScopePattern: Build optimized search scopes for partition routing and selectivity
    - TimeshiftPattern: Compare current data with historical baselines
    - NullSafeOperations: Null-safe math operations
    - AggregationPatterns: Common aggregation and sorting patterns
    - CreditCalculation: Sumo Logic credit rate calculations

Usage Example:
    >>> from query_patterns import TimeshiftPattern, AggregationPatterns
    >>> query_parts = ['_index=sumologic_volume']
    >>> query_parts.extend(TimeshiftPattern.compare_with_timeshift('gbytes', days=7, periods=3))
    >>> query_parts.append(AggregationPatterns.top_n('gbytes', limit=100))
"""

import re
from typing import List, Literal, Optional


class ScopePattern:
    """Build optimized search scopes for Sumo Logic queries.

    The scope is the part of the query before the first pipe (|) operator.
    A well-crafted scope is critical for:
    1. Partition routing - limiting metered scan to specific partitions/views
    2. Query performance - increasing selectivity via bloom filters
    3. Cost optimization - reducing scan volume in Flex/Infrequent tiers

    Best Practices:
    - Include partition/view specifier (_index or _view) when possible
    - Use _sourceCategory for implicit partition routing (most common)
    - Add keyword expressions or field=value filters for selectivity
    - Avoid overly broad scopes like '*' or '_dataTier=all' in production

    References:
    - Keyword expressions: https://help.sumologic.com/docs/search/get-started-with-search/build-search/keyword-search-expressions/
    - Query rewriting: https://help.sumologic.com/docs/search/optimize-search-partitions/#what-is-query-rewriting
    """

    # Built-in metadata fields that support partition routing
    METADATA_FIELDS = ["_sourceCategory", "_collector", "_source", "_sourceName", "_sourceHost"]

    # Partition/view specifiers
    PARTITION_FIELDS = ["_index", "_view"]

    @staticmethod
    def build_scope(
        partition: Optional[str] = None,
        metadata: Optional[dict] = None,
        keywords: Optional[List[str]] = None,
        indexed_fields: Optional[dict] = None,
        use_and: bool = True,
    ) -> str:
        """Build a search scope with partition routing and selectivity filters.

        Args:
            partition: Partition or view name (e.g., 'prod_logs', 'sumologic_volume')
                      Can be prefixed with _index= or _view=, or bare name (defaults to _index=)
            metadata: Built-in metadata filters {field: value}
                     e.g., {'_sourceCategory': 'prod/app', '_sourceHost': 'web-*'}
            keywords: Keyword expressions for selectivity
                     e.g., ['error', 'exception', '5xx']
            indexed_fields: Indexed field filters {field: value}
                           e.g., {'status_code': '500', 'user_id': 'abc123'}
            use_and: Use AND between components (default: True), else OR

        Returns:
            Optimized scope string

        Examples:
            >>> ScopePattern.build_scope(partition='prod_logs', keywords=['error', '5xx'])
            '_index=prod_logs error 5xx'

            >>> ScopePattern.build_scope(
            ...     metadata={'_sourceCategory': 'prod/app'},
            ...     keywords=['exception'],
            ...     indexed_fields={'severity': 'ERROR'}
            ... )
            '_sourceCategory="prod/app" AND exception AND severity="ERROR"'
        """
        components = []

        # Add partition/view specifier
        if partition:
            if not partition.startswith("_index=") and not partition.startswith("_view="):
                partition = f"_index={partition}"
            components.append(partition)

        # Add metadata filters
        if metadata:
            for field, value in metadata.items():
                # Validate metadata field
                if field not in ScopePattern.METADATA_FIELDS:
                    # Allow it but it might not route to partitions efficiently
                    pass

                # Quote value if it contains spaces or special chars
                if " " in str(value) or any(c in str(value) for c in ["*", "?", "-", "/"]):
                    components.append(f'{field}="{value}"')
                else:
                    components.append(f"{field}={value}")

        # Add keyword expressions
        if keywords:
            components.extend(keywords)

        # Add indexed field filters
        if indexed_fields:
            for field, value in indexed_fields.items():
                # Quote value if needed
                if " " in str(value) or any(c in str(value) for c in ["*", "?", "-", "/"]):
                    components.append(f'{field}="{value}"')
                else:
                    components.append(f"{field}={value}")

        # Join with AND or OR
        if not components:
            return "*"

        separator = " AND " if use_and else " OR "
        return separator.join(components)

    @staticmethod
    def build_metadata_scope(
        source_category: Optional[str] = None,
        collector: Optional[str] = None,
        source: Optional[str] = None,
        source_name: Optional[str] = None,
        source_host: Optional[str] = None,
        use_and: bool = True,
    ) -> str:
        """Build a scope using built-in metadata fields (simplified API).

        Args:
            source_category: _sourceCategory value (most common, best for routing)
            collector: _collector value
            source: _source value
            source_name: _sourceName value
            source_host: _sourceHost value
            use_and: Use AND between fields (default: True)

        Returns:
            Metadata scope string

        Example:
            >>> ScopePattern.build_metadata_scope(
            ...     source_category='prod/app',
            ...     source_host='web-*'
            ... )
            '_sourceCategory="prod/app" AND _sourceHost="web-*"'
        """
        metadata = {}
        if source_category:
            metadata["_sourceCategory"] = source_category
        if collector:
            metadata["_collector"] = collector
        if source:
            metadata["_source"] = source
        if source_name:
            metadata["_sourceName"] = source_name
        if source_host:
            metadata["_sourceHost"] = source_host

        return ScopePattern.build_scope(metadata=metadata, use_and=use_and)

    @staticmethod
    def extract_scope_from_query(query: str) -> str:
        """Extract the scope portion from a full query (before first |).

        Args:
            query: Full Sumo Logic query

        Returns:
            Scope portion (everything before first pipe)

        Example:
            >>> ScopePattern.extract_scope_from_query('error | count by _sourceHost')
            'error'
        """
        # Find first pipe not inside quotes
        in_quotes = False
        quote_char = None

        for i, char in enumerate(query):
            if char in ['"', "'"]:
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
            elif char == "|" and not in_quotes:
                return query[:i].strip()

        # No pipe found, entire query is scope
        return query.strip()

    @staticmethod
    def analyze_scope(scope: str) -> dict:
        """Analyze a scope string and provide optimization recommendations.

        Args:
            scope: Scope string to analyze

        Returns:
            Dictionary with analysis:
            - has_partition: bool - Has explicit _index or _view
            - has_metadata: bool - Has built-in metadata filter
            - metadata_fields: list - Which metadata fields are used
            - has_keywords: bool - Has keyword expressions
            - is_broad: bool - Scope is very broad (*, _dataTier=all, etc.)
            - recommendations: list - Optimization suggestions

        Example:
            >>> ScopePattern.analyze_scope('error')
            {
                'has_partition': False,
                'has_metadata': False,
                'metadata_fields': [],
                'has_keywords': True,
                'is_broad': False,
                'recommendations': ['Add _sourceCategory or partition to improve routing']
            }
        """
        analysis = {
            "has_partition": False,
            "has_metadata": False,
            "metadata_fields": [],
            "has_keywords": False,
            "is_broad": False,
            "recommendations": [],
        }

        scope_lower = scope.lower()

        # Check for partition/view
        if "_index=" in scope_lower or "_view=" in scope_lower:
            analysis["has_partition"] = True

        # Check for metadata fields
        for field in ScopePattern.METADATA_FIELDS:
            if field.lower() in scope_lower:
                analysis["has_metadata"] = True
                analysis["metadata_fields"].append(field)

        # Check for keywords (simplified - looks for bare words not part of field expressions)
        # This is a heuristic - actual parsing would be complex
        tokens = re.split(r"\s+(?:AND|OR|NOT)\s+|\s+", scope)
        for token in tokens:
            if (
                token
                and "=" not in token
                and not token.startswith("_")
                and token not in ["AND", "OR", "NOT", "(", ")"]
            ):
                analysis["has_keywords"] = True
                break

        # Check if scope is too broad
        if scope.strip() in ["*", ""]:
            analysis["is_broad"] = True
            analysis["recommendations"].append(
                'Scope is "*" - this scans all partitions. Add filters to reduce scan volume.'
            )
        elif "_datatier=all" in scope_lower:
            analysis["is_broad"] = True
            analysis["recommendations"].append(
                "Using _dataTier=all scans all tiers. Consider specifying tier or using metadata filters."
            )

        # Provide recommendations
        if not analysis["has_partition"] and not analysis["has_metadata"]:
            analysis["recommendations"].append(
                "Add _sourceCategory or _index to enable partition routing and reduce scan volume."
            )

        if not analysis["has_keywords"] and not analysis["is_broad"]:
            analysis["recommendations"].append(
                "Consider adding keyword expressions for better selectivity and performance."
            )

        if analysis["has_metadata"] and "_sourceCategory" not in analysis["metadata_fields"]:
            analysis["recommendations"].append(
                "Consider using _sourceCategory as it most commonly maps to partition routing."
            )

        return analysis


class TimeshiftPattern:
    """Handles timeshift comparison with null-safe math.

    The compare with timeshift operator compares current values against historical
    averages. When no historical data exists (new sources, collection gaps, or
    baseline windows with no events), the averaged fields return null rather than 0.

    This class ensures:
    - Null values are properly detected and handled
    - State is tracked (GONE, COLLECTING, NEW)
    - Division by zero is prevented
    - Percentage calculations work correctly for all edge cases

    Edge Cases Handled:
        - GONE: current=null, baseline>0 → State="GONE", pct_change calculated from 0
        - NEW: current>0, baseline=null → State="NEW", pct_change=100%
        - Both null: current=null, baseline=null → State="GONE", pct_change=0%
        - Both zero: current=0, baseline=0 → State="COLLECTING", pct_change=0%
        - Baseline zero only: current>0, baseline=0 → pct_change=100%
    """

    @staticmethod
    def compare_with_timeshift(
        field: str,
        days: int,
        periods: int,
        state_labels: Optional[dict] = None,
        include_state: bool = True,
    ) -> List[str]:
        """Generate timeshift comparison with null guards and percentage calculation.

        Args:
            field: Field name to compare (e.g., 'gbytes', 'credits', 'count')
            days: Days per period for comparison (e.g., 7 for weekly)
            periods: Number of periods to average (e.g., 3 for 3-week average)
            state_labels: Custom labels for states (default: GONE/COLLECTING/NEW)
            include_state: Whether to generate state field (default: True, only for first field)

        Returns:
            List of query operators to append to query

        Example:
            >>> TimeshiftPattern.compare_with_timeshift('gbytes', days=7, periods=3)
            [
                '| compare timeshift 7d 3 avg',
                '| if(isNull(gbytes), "GONE", "COLLECTING") as state',
                '| if(isNull(gbytes), 0, gbytes) as gbytes',
                '| if(isNull(gbytes_21d_avg), "NEW", state) as state',
                '| if(isNull(gbytes_21d_avg), 0, gbytes_21d_avg) as gbytes_21d_avg',
                '| if(gbytes_21d_avg == 0, if(gbytes == 0, 0, 100), ((gbytes - gbytes_21d_avg) / gbytes_21d_avg) * 100) as pct_change_gbytes'
            ]
        """
        total_days = days * periods
        avg_field = f"{field}_{total_days}d_avg"
        labels = state_labels or {"gone": "GONE", "collecting": "COLLECTING", "new": "NEW"}

        operators = []

        # Only add compare operator for first field
        if include_state:
            operators.append(f"| compare timeshift {days}d {periods} avg")

        # Null guards with state detection (only for first field)
        if include_state:
            operators.extend(
                [
                    f'| if(isNull({field}), "{labels["gone"]}", "{labels["collecting"]}") as state',
                    f"| if(isNull({field}), 0, {field}) as {field}",
                    f'| if(isNull({avg_field}), "{labels["new"]}", state) as state',
                ]
            )
        else:
            operators.append(f"| if(isNull({field}), 0, {field}) as {field}")

        # Null guard for averaged field
        operators.append(f"| if(isNull({avg_field}), 0, {avg_field}) as {avg_field}")

        # Null-safe percentage with division-by-zero handling
        operators.append(
            f"| if({avg_field} == 0, if({field} == 0, 0, 100), "
            f"(({field} - {avg_field}) / {avg_field}) * 100) as pct_change_{field}"
        )

        return operators


class NullSafeOperations:
    """Null-safe mathematical operations for Sumo Logic queries.

    Sumo Logic returns null for many edge cases:
    - Missing fields in parsed data
    - Division by zero
    - Math operations involving null values
    - Timeshift comparisons with no historical data

    These helpers ensure predictable behavior in all cases.
    """

    @staticmethod
    def safe_divide(
        numerator: str,
        denominator: str,
        result_field: str,
        null_result: str = "0",
        div_zero_result: str = "0",
        multiply_by: Optional[float] = None,
    ) -> str:
        """Division with null and zero guards.

        Args:
            numerator: Field or expression for numerator
            denominator: Field or expression for denominator
            result_field: Name for result field
            null_result: Value when either input is null (default: "0")
            div_zero_result: Value when denominator is zero (default: "0")
            multiply_by: Optional multiplier (e.g., 100 for percentage)

        Returns:
            Query operator for null-safe division

        Example:
            >>> NullSafeOperations.safe_divide('bytes', 'seconds', 'bytes_per_sec')
            '| if(isNull(bytes) or isNull(seconds), 0, if(seconds == 0, 0, bytes / seconds)) as bytes_per_sec'
        """
        division = f"{numerator} / {denominator}"
        if multiply_by:
            division = f"({division}) * {multiply_by}"

        return (
            f"| if(isNull({numerator}) or isNull({denominator}), {null_result}, "
            f"if({denominator} == 0, {div_zero_result}, {division})) as {result_field}"
        )

    @staticmethod
    def coalesce(field: str, default_value: str = "0") -> str:
        """Convert nulls to default value.

        Args:
            field: Field name to check for null
            default_value: Value to use if null (default: "0")

        Returns:
            Query operator to replace nulls

        Example:
            >>> NullSafeOperations.coalesce('bytes', '0')
            '| if(isNull(bytes), 0, bytes) as bytes'
        """
        return f"| if(isNull({field}), {default_value}, {field}) as {field}"

    @staticmethod
    def percentage_change(current: str, baseline: str, result_field: str = "pct_change") -> str:
        """Calculate percentage change with null/zero safety.

        Logic:
        - baseline=0, current=0 → 0% (no change, both silent)
        - baseline=0, current>0 → 100% (new data appeared)
        - baseline>0, current=0 → -100% (data disappeared)
        - otherwise → ((current - baseline) / baseline) * 100

        Args:
            current: Current value field
            baseline: Baseline value field
            result_field: Name for percentage field (default: "pct_change")

        Returns:
            Query operator for percentage calculation

        Example:
            >>> NullSafeOperations.percentage_change('gbytes', 'gbytes_avg', 'pct_increase')
            '| if(gbytes_avg == 0, if(gbytes == 0, 0, 100), ((gbytes - gbytes_avg) / gbytes_avg) * 100) as pct_increase'
        """
        return (
            f"| if({baseline} == 0, if({current} == 0, 0, 100), "
            f"(({current} - {baseline}) / {baseline}) * 100) as {result_field}"
        )


class AggregationPatterns:
    """Common aggregation and sorting patterns for Sumo Logic queries."""

    @staticmethod
    def volume_by_dimension(
        dimension: str, include_tier: bool = True, additional_dimensions: Optional[List[str]] = None
    ) -> str:
        """Standard volume aggregation pattern.

        Args:
            dimension: Primary dimension to group by (e.g., 'sourceCategory', 'collector')
            include_tier: Include dataTier in grouping (default: True)
            additional_dimensions: Additional fields to group by

        Returns:
            Query operator for volume aggregation

        Example:
            >>> AggregationPatterns.volume_by_dimension('sourceCategory')
            '| sum(events) as events, sum(gbytes) as gbytes by dataTier, sourceCategory'
        """
        group_by = []
        if include_tier:
            group_by.append("dataTier")
        group_by.append(dimension)
        if additional_dimensions:
            group_by.extend(additional_dimensions)

        group_by_str = ", ".join(group_by)
        return f"| sum(events) as events, sum(gbytes) as gbytes by {group_by_str}"

    @staticmethod
    def top_n(sort_field: str, limit: int = 100, direction: Literal["asc", "desc"] = "desc") -> str:
        """Top N results pattern.

        Args:
            sort_field: Field to sort by
            limit: Maximum number of results (default: 100)
            direction: Sort direction (default: "desc")

        Returns:
            Query operator for sorting and limiting

        Example:
            >>> AggregationPatterns.top_n('gbytes', limit=50)
            '| sort gbytes desc | limit 50'
        """
        return f"| sort {sort_field} {direction} | limit {limit}"

    @staticmethod
    def timeslice_aggregation(
        interval: str, fields: List[str], group_by: Optional[List[str]] = None
    ) -> str:
        """Timeslice aggregation pattern.

        Args:
            interval: Timeslice interval (e.g., '1h', '15m', '1d')
            fields: Fields to aggregate (e.g., ['sum(bytes) as bytes', 'count as events'])
            group_by: Optional additional grouping fields

        Returns:
            Query operator for timeslice aggregation

        Example:
            >>> AggregationPatterns.timeslice_aggregation('1h', ['sum(bytes) as bytes'])
            '| timeslice 1h | sum(bytes) as bytes by _timeslice'
        """
        fields_str = ", ".join(fields)
        group_by_list = ["_timeslice"]
        if group_by:
            group_by_list.extend(group_by)
        group_by_str = ", ".join(group_by_list)

        return f"| timeslice {interval} | {fields_str} by {group_by_str}"


class CreditCalculation:
    """Sumo Logic credit rate calculations for different data tiers.

    Credit rates vary by pricing model:
    - Standard Tiered: Different rates per tier
    - Flex: Usage-based pricing
    - CSE: Security-specific pricing

    Note: Rates are subject to change. Verify current rates in Sumo Logic documentation.
    """

    # Standard tiered credit rates (credits per GB)
    STANDARD_RATES = {"Continuous": 20, "Frequent": 9, "Infrequent": 0.4, "CSE": 25}

    @staticmethod
    def add_credit_calculation(
        data_field: str = "gbytes",
        tier_field: str = "dataTier",
        credit_field: str = "credits",
        rates: Optional[dict] = None,
    ) -> List[str]:
        """Add credit calculation based on data tier.

        Args:
            data_field: Field containing data volume in GB (default: 'gbytes')
            tier_field: Field containing tier name (default: 'dataTier')
            credit_field: Name for credits field (default: 'credits')
            rates: Custom rate dictionary (default: STANDARD_RATES)

        Returns:
            List of query operators for credit calculation

        Example:
            >>> CreditCalculation.add_credit_calculation()
            [
                '| 20 as credit_rate',
                '| if(dataTier = "CSE", 25, credit_rate) as credit_rate',
                '| if(dataTier = "Infrequent", 0.4, credit_rate) as credit_rate',
                '| if(dataTier = "Frequent", 9, credit_rate) as credit_rate',
                '| gbytes * credit_rate as credits'
            ]
        """
        rates = rates or CreditCalculation.STANDARD_RATES

        operators = [
            f'| {rates["Continuous"]} as credit_rate',
            f'| if({tier_field} = "CSE", {rates["CSE"]}, credit_rate) as credit_rate',
            f'| if({tier_field} = "Infrequent", {rates["Infrequent"]}, credit_rate) as credit_rate',
            f'| if({tier_field} = "Frequent", {rates["Frequent"]}, credit_rate) as credit_rate',
            f"| {data_field} * credit_rate as {credit_field}",
        ]

        return operators


class LogDiscoveryPattern:
    """Multi-phase log discovery helper for finding and understanding logs.

    This class helps users discover logs in their Sumo Logic environment when they
    don't know the exact metadata, partitions, or log structure. It provides a
    systematic approach to log discovery in two main phases:

    Phase 1: Metadata Discovery
        - Find source categories matching a pattern (via data volume analysis)
        - Discover related metadata (partition, collector, source, etc.)
        - Analyze search patterns from other users (via search audit)

    Phase 2: Log Structure Analysis
        - Sample logs with/without auto-parse to understand fields
        - Identify log format (JSON, syslog, custom, etc.)
        - Determine indexed fields vs. search-time fields
        - Provide parsing recommendations

    Use Cases:
        - New user: Doesn't know what metadata fields or partitions exist
        - Developer: Knows service name but not matching _sourceCategory
        - Troubleshooter: Needs to find logs related to specific application/host
        - Query builder: Understanding log structure to write effective queries

    References:
        - Metadata fields: https://help.sumologic.com/docs/search/get-started-with-search/search-basics/built-in-metadata/
        - Auto-parse: https://help.sumologic.com/docs/search/get-started-with-search/build-search/dynamic-parsing/
    """

    # Built-in metadata fields available in all logs
    BUILTIN_METADATA = [
        "_sourceCategory",
        "_collector",
        "_source",
        "_sourceName",
        "_sourceHost",
        "_messageTime",
        "_receiptTime",
        "_blockId",
        "_raw",
    ]

    # Additional tier/partition metadata
    TIER_METADATA = ["_dataTier", "_index", "_view"]

    @staticmethod
    def build_metadata_discovery_query(
        search_pattern: str, time_range: str = "-60m", use_volume_index: bool = True
    ) -> dict:
        """Build queries for Phase 1: Discovering metadata.

        Args:
            search_pattern: Pattern to search for (e.g., 'foo', '*cloudtrail*', 'prod-*')
            time_range: Time range for discovery (default: '-60m' for recent logs)
            use_volume_index: Use data volume index (faster, less scan) vs. search audit

        Returns:
            Dictionary with recommended queries and descriptions.

        Example:
            >>> LogDiscoveryPattern.build_metadata_discovery_query('cloudtrail')
        """
        queries = {}

        # Query 1: Use data volume index to find matching source categories
        if use_volume_index:
            queries["volume_query"] = (
                f"_index=sumologic_volume _sourceCategory=sourcecategory_and_tier_volume "
                f'| parse regex "(?<data>\\{{[^\\{{]+\\}})" multi '
                f'| json field=data "field","dataTier","sizeInBytes","count" as sourceCategory, dataTier, bytes, events '
                f"| where sourceCategory matches /{search_pattern}/i "
                f"| sum(events) as events, sum(bytes) as bytes by dataTier, sourceCategory "
                f"| sort events desc | limit 50"
            )
            queries["volume_query_description"] = (
                f"Find source categories matching '{search_pattern}' (case-insensitive)"
            )

        # Query 2: Template for metadata discovery
        queries["metadata_query_template"] = (
            "{scope} | count by _index, _view, _collector, _source, _sourceName, _sourceHost, _dataTier | sort _count desc | limit 100"
        )
        queries["metadata_query_description"] = "Discover partitions and related metadata"

        # Query 3: Search audit
        queries["search_audit_query"] = (
            f"_view=sumologic_search_usage_per_query | where query_text matches /{search_pattern}/i "
            f"| fields query_text, query_user, total_events_returned | sort total_events_returned desc | limit 20"
        )
        queries["search_audit_query_description"] = (
            f"Find queries by other users mentioning '{search_pattern}'"
        )

        return queries

    @staticmethod
    def build_usecase_query_recommendations(
        log_format: str,
        detected_fields: List[str],
        use_case: Optional[str] = None,
        has_query_library: bool = True,
    ) -> dict:
        """Build Phase 3: Use-case based query recommendations.

        After discovering metadata (Phase 1) and log structure (Phase 2), help users
        build queries based on common use cases by leveraging the query examples library.

        Args:
            log_format: Detected log format ('json', 'syslog', 'custom', etc.)
            detected_fields: List of fields found in logs
            use_case: Optional use case hint (e.g., 'error', 'security', 'performance')
            has_query_library: Whether query examples library is available (default: True)

        Returns:
            Dictionary with query building recommendations:
            - query_library_searches: Searches to run against query examples
            - common_patterns: Generic patterns applicable to this log type
            - field_based_queries: Queries based on detected fields
            - setup_instructions: How to set up query library if not available

        Example:
            >>> LogDiscoveryPattern.build_usecase_query_recommendations(
            ...     log_format='json',
            ...     detected_fields=['status_code', 'user_id', 'response_time'],
            ...     use_case='error'
            ... )
            {
                'query_library_searches': [
                    {'query': 'error status_code', 'description': '...'},
                    ...
                ]
            }
        """
        recommendations = {
            "log_format": log_format,
            "detected_fields": detected_fields,
            "use_case": use_case,
            "has_query_library": has_query_library,
            "query_library_searches": [],
            "common_patterns": [],
            "field_based_queries": [],
            "setup_instructions": None,
        }

        # Phase 3A: Query library searches (if available)
        if has_query_library:
            # Build searches based on use case and log format
            if use_case:
                recommendations["query_library_searches"].append(
                    {
                        "tool": "search_query_examples",
                        "parameters": {"query": use_case, "match_mode": "any", "max_results": 10},
                        "description": f"Search query library for '{use_case}' use cases",
                        "why": f"Find example queries related to {use_case} that you can adapt to your logs",
                    }
                )

            # Search by detected field names (common patterns)
            common_fields = {
                "status_code": "HTTP status code queries (4xx, 5xx errors)",
                "response_time": "Performance and latency queries",
                "user_id": "User activity and authentication queries",
                "error": "Error detection and alerting queries",
                "host": "Host/server monitoring queries",
                "pod": "Kubernetes pod queries",
                "namespace": "Kubernetes namespace queries",
                "source_ip": "Network security queries",
                "cloudtrail": "AWS CloudTrail security queries",
            }

            for field in detected_fields:
                field_lower = field.lower()
                for pattern, description in common_fields.items():
                    if pattern in field_lower:
                        recommendations["query_library_searches"].append(
                            {
                                "tool": "search_query_examples",
                                "parameters": {
                                    "keywords": field,
                                    "match_mode": "any",
                                    "max_results": 5,
                                },
                                "description": f"Search for queries using '{field}' field",
                                "why": description,
                            }
                        )
                        break

            # Search by log format
            format_searches = {
                "json": {
                    "query": "json parse",
                    "description": "Find JSON parsing and auto-parse examples",
                },
                "syslog": {"query": "syslog parse", "description": "Find syslog parsing patterns"},
                "cloudtrail": {
                    "app_name": "AWS",
                    "keywords": "CloudTrail",
                    "description": "Find AWS CloudTrail query examples",
                },
            }

            if log_format in format_searches:
                search_params = format_searches[log_format].copy()
                description = search_params.pop("description")
                recommendations["query_library_searches"].append(
                    {
                        "tool": "search_query_examples",
                        "parameters": {**search_params, "max_results": 5},
                        "description": description,
                        "why": f"Learn how to query {log_format} formatted logs",
                    }
                )

        else:
            # Provide setup instructions
            recommendations["setup_instructions"] = {
                "message": (
                    "Query examples library not available. To enable 11,000+ example queries:"
                ),
                "steps": [
                    "1. Download query examples from GitHub releases",
                    "2. Extract sumologic_query_examples.json.gz to data/ directory",
                    "3. Restart MCP server",
                    "4. Use search_query_examples tool to find relevant queries",
                ],
                "documentation": "See README.md for detailed setup instructions",
                "benefit": "Access real-world query examples from 280+ Sumo Logic apps",
            }

        # Phase 3B: Common query patterns (always available, no library needed)

        # Base patterns by use case
        if use_case:
            use_case_patterns = {
                "error": [
                    {
                        "pattern": "{scope} error OR exception OR fail | count by _sourceHost",
                        "description": "Count errors by host",
                        "operators": ["count by"],
                    },
                    {
                        "pattern": "{scope} (error OR exception) | timeslice 1h | count by _timeslice",
                        "description": "Error trend over time",
                        "operators": ["timeslice", "count by"],
                    },
                ],
                "performance": [
                    {
                        "pattern": '{scope} | parse "response_time=*ms" as response_time | avg(response_time), max(response_time), pct(response_time, 95)',
                        "description": "Response time statistics (avg, max, p95)",
                        "operators": ["parse", "avg", "max", "pct"],
                    }
                ],
                "security": [
                    {
                        "pattern": "{scope} (failed OR denied OR unauthorized) | count by user, _sourceHost",
                        "description": "Failed authentication attempts by user and host",
                        "operators": ["count by"],
                    }
                ],
            }

            if use_case.lower() in use_case_patterns:
                recommendations["common_patterns"].extend(use_case_patterns[use_case.lower()])

        # Field-based query suggestions
        for field in detected_fields:
            field_lower = field.lower()

            # HTTP status codes
            if "status" in field_lower and "code" in field_lower:
                recommendations["field_based_queries"].append(
                    {
                        "field": field,
                        "queries": [
                            {
                                "pattern": f"{{scope}} | where {field} >= 400 | count by {field}, _sourceHost",
                                "description": "Count 4xx/5xx errors by status code and host",
                                "use_case": "error",
                            },
                            {
                                "pattern": f"{{scope}} | where {field} >= 500 | timeslice 5m | count by _timeslice",
                                "description": "Track 5xx errors over time",
                                "use_case": "error",
                            },
                        ],
                    }
                )

            # Response time / latency
            if any(term in field_lower for term in ["response", "latency", "duration", "time"]):
                if field_lower not in ["_messagetime", "_receipttime"]:
                    recommendations["field_based_queries"].append(
                        {
                            "field": field,
                            "queries": [
                                {
                                    "pattern": f"{{scope}} | avg({field}), max({field}), pct({field}, 95) by _sourceHost",
                                    "description": "Performance metrics: avg, max, p95",
                                    "use_case": "performance",
                                },
                                {
                                    "pattern": f"{{scope}} | where {field} > <threshold> | count by _sourceHost",
                                    "description": "Find slow requests (replace <threshold>)",
                                    "use_case": "performance",
                                },
                            ],
                        }
                    )

            # User fields
            if "user" in field_lower or "account" in field_lower:
                recommendations["field_based_queries"].append(
                    {
                        "field": field,
                        "queries": [
                            {
                                "pattern": f"{{scope}} | count by {field} | sort _count desc | limit 20",
                                "description": "Top users by activity",
                                "use_case": "audit",
                            }
                        ],
                    }
                )

        # Generic patterns applicable to all logs
        recommendations["common_patterns"].extend(
            [
                {
                    "pattern": "{scope} | count by _sourceHost",
                    "description": "Message volume by host",
                    "operators": ["count by"],
                    "use_case": "general",
                },
                {
                    "pattern": "{scope} | timeslice 1h | count by _timeslice",
                    "description": "Message volume over time",
                    "operators": ["timeslice", "count by"],
                    "use_case": "general",
                },
            ]
        )

        # Add note about {scope} placeholder
        recommendations["note"] = (
            "Replace {scope} in patterns with your actual search scope "
            "(e.g., _sourceCategory=prod/app or _index=prod_logs)"
        )

        return recommendations

    @staticmethod
    def generate_complete_workflow(
        initial_hint: str, context: str = "service", use_case: Optional[str] = None
    ) -> dict:
        """Generate complete 3-phase log discovery workflow.

        This extends the discovery workflow to include all three phases:
        - Phase 1: Metadata discovery
        - Phase 2: Log structure analysis
        - Phase 3: Use-case based query building

        Args:
            initial_hint: User's starting point (e.g., 'api-gateway')
            context: What the hint represents ('service', 'host', 'application')
            use_case: Optional use case for Phase 3 (e.g., 'error', 'performance')

        Returns:
            Complete workflow with all three phases

        Example:
            >>> LogDiscoveryPattern.generate_complete_workflow(
            ...     'api-gateway',
            ...     'service',
            ...     use_case='error'
            ... )
        """
        workflow = {
            "initial_hint": initial_hint,
            "context": context,
            "use_case": use_case,
            "phases": {
                "phase1": "Metadata Discovery",
                "phase2": "Log Structure Analysis",
                "phase3": "Use-Case Query Building",
            },
            "estimated_time_minutes": 15,
            "steps": [],
        }

        # Phase 1: Metadata Discovery
        workflow["steps"].extend(
            [
                {
                    "phase": 1,
                    "step": 1,
                    "action": "Find matching source categories",
                    "tool": "analyze_data_volume or custom query",
                    "method": "data_volume_search",
                    "pattern": f"*{initial_hint}*",
                },
                {
                    "phase": 1,
                    "step": 2,
                    "action": "Discover partitions and metadata",
                    "tool": "explore_log_metadata or custom query",
                    "method": "metadata_exploration",
                },
            ]
        )

        # Phase 2: Log Structure
        workflow["steps"].extend(
            [
                {
                    "phase": 2,
                    "step": 3,
                    "action": "Sample logs without auto-parse",
                    "tool": "search_sumo_logs",
                    "method": "log_sampling",
                    "note": "Shows indexed fields only",
                },
                {
                    "phase": 2,
                    "step": 4,
                    "action": "Sample logs with auto-parse",
                    "tool": "search_sumo_logs",
                    "method": "log_sampling",
                    "note": "Shows all fields including JSON",
                },
                {
                    "phase": 2,
                    "step": 5,
                    "action": "Detect log format",
                    "method": "format_detection",
                    "note": "Identify JSON, syslog, or custom format",
                },
            ]
        )

        # Phase 3: Use-Case Query Building
        workflow["steps"].extend(
            [
                {
                    "phase": 3,
                    "step": 6,
                    "action": "Search query examples library",
                    "tool": "search_query_examples",
                    "method": "query_library_search",
                    "note": "Find relevant examples from 11,000+ real queries",
                },
                {
                    "phase": 3,
                    "step": 7,
                    "action": "Build queries based on use case and fields",
                    "method": "query_construction",
                    "note": "Combine scope, operators, and field filters",
                },
            ]
        )

        workflow["tips"] = [
            "Phase 1: Start with data volume index to find source categories",
            "Phase 2: Compare fields with/without auto-parse to identify indexed fields",
            "Phase 3: Use search_query_examples tool to find relevant patterns",
            "Query library: Extract sumologic_query_examples.json.gz to enable 11,000+ examples",
            "Build scope using ScopePattern.build_scope() for optimal performance",
        ]

        return workflow

    @staticmethod
    def recommend_apps(
        discovered_metadata: dict, detected_fields: Optional[List[str]] = None
    ) -> dict:
        """Recommend Sumo Logic apps based on discovered logs.

        After discovering logs (Phase 1/2), suggest relevant pre-built apps that
        may already be installed or available for installation.

        Args:
            discovered_metadata: Metadata from Phase 1 (source categories, collectors, etc.)
                Should include keys like 'sourceCategory', 'collector', 'source'
            detected_fields: Optional list of detected fields from Phase 2

        Returns:
            Dictionary with app recommendations:
            - likely_apps: Apps that probably match based on metadata/fields
            - check_tools: Tools to run to verify if apps are installed
            - installation_links: Links to app catalog for uninstalled apps
            - next_steps: Recommended actions

        Example:
            >>> LogDiscoveryPattern.recommend_apps(
            ...     discovered_metadata={'sourceCategory': 'prod/cloudtrail'},
            ...     detected_fields=['eventName', 'eventSource', 'awsRegion']
            ... )
            {
                'likely_apps': ['AWS CloudTrail', 'AWS Security'],
                'check_tools': {...},
                ...
            }
        """
        recommendations = {
            "likely_apps": [],
            "app_matches": [],
            "check_tools": [],
            "installation_links": {
                "app_catalog": "https://www.sumologic.com/app-catalog",
                "integrations_docs": "https://www.sumologic.com/help/docs/integrations/",
            },
            "next_steps": [],
        }

        # Build search pattern from metadata
        metadata_str = str(discovered_metadata).lower()

        # AWS Services
        aws_services = {
            "cloudtrail": {
                "app": "AWS CloudTrail",
                "fields": ["eventName", "eventSource", "awsRegion", "userIdentity"],
                "catalog_search": "AWS CloudTrail",
                "use_cases": [
                    "Security auditing",
                    "Compliance monitoring",
                    "User activity tracking",
                ],
            },
            "cloudwatch": {
                "app": "AWS CloudWatch",
                "fields": ["logGroup", "logStream"],
                "catalog_search": "AWS CloudWatch",
                "use_cases": ["Log aggregation", "Metric monitoring"],
            },
            "elb": {
                "app": "AWS Elastic Load Balancer",
                "fields": ["elb", "target_ip", "target_port"],
                "catalog_search": "AWS ELB",
                "use_cases": ["Load balancer monitoring", "Request analytics"],
            },
            "vpc": {
                "app": "AWS VPC Flow Logs",
                "fields": ["srcaddr", "dstaddr", "srcport", "dstport", "protocol"],
                "catalog_search": "AWS VPC",
                "use_cases": ["Network security", "Traffic analysis"],
            },
            "lambda": {
                "app": "AWS Lambda",
                "fields": ["requestId", "duration", "billed_duration"],
                "catalog_search": "AWS Lambda",
                "use_cases": ["Serverless monitoring", "Performance analysis"],
            },
        }

        # Kubernetes
        k8s_indicators = {
            "kubernetes": {
                "app": "Kubernetes",
                "fields": ["pod", "namespace", "container", "node"],
                "catalog_search": "Kubernetes",
                "use_cases": ["Container orchestration", "Pod monitoring", "Cluster health"],
            },
            "k8s": {
                "app": "Kubernetes",
                "fields": ["pod", "namespace"],
                "catalog_search": "Kubernetes",
                "use_cases": ["Container monitoring"],
            },
        }

        # Web Servers
        web_servers = {
            "apache": {
                "app": "Apache",
                "fields": ["status_code", "method", "request_uri", "user_agent"],
                "catalog_search": "Apache",
                "use_cases": ["Web server monitoring", "Access log analysis"],
            },
            "nginx": {
                "app": "Nginx",
                "fields": ["status", "request", "http_user_agent"],
                "catalog_search": "Nginx",
                "use_cases": ["Web server monitoring", "Reverse proxy analytics"],
            },
            "iis": {
                "app": "Microsoft IIS",
                "fields": ["cs-method", "cs-uri-stem", "sc-status"],
                "catalog_search": "IIS",
                "use_cases": ["Windows web server monitoring"],
            },
        }

        # Databases
        databases = {
            "mysql": {
                "app": "MySQL",
                "fields": ["query_time", "lock_time", "rows_sent"],
                "catalog_search": "MySQL",
                "use_cases": ["Database performance", "Query analysis"],
            },
            "postgres": {
                "app": "PostgreSQL",
                "fields": ["duration", "statement"],
                "catalog_search": "PostgreSQL",
                "use_cases": ["Database monitoring", "Query performance"],
            },
        }

        # Security
        security_apps = {
            "palo alto": {
                "app": "Palo Alto Networks",
                "fields": ["threat_id", "category", "severity"],
                "catalog_search": "Palo Alto",
                "use_cases": ["Firewall monitoring", "Threat detection"],
            },
            "cisco": {
                "app": "Cisco Networks",
                "fields": ["facility", "severity", "mnemonic"],
                "catalog_search": "Cisco",
                "use_cases": ["Network device monitoring"],
            },
        }

        # Check all app categories
        all_apps = {**aws_services, **k8s_indicators, **web_servers, **databases, **security_apps}

        for pattern, app_info in all_apps.items():
            matched = False
            match_reasons = []

            # Check metadata
            if pattern in metadata_str:
                matched = True
                match_reasons.append(f"Metadata contains '{pattern}'")

            # Check fields
            if detected_fields:
                field_matches = []
                for field in app_info.get("fields", []):
                    if any(field.lower() in df.lower() for df in detected_fields):
                        field_matches.append(field)

                if field_matches:
                    matched = True
                    match_reasons.append(f"Fields match: {', '.join(field_matches)}")

            if matched:
                app_match = {
                    "app_name": app_info["app"],
                    "confidence": "high" if len(match_reasons) > 1 else "medium",
                    "match_reasons": match_reasons,
                    "use_cases": app_info.get("use_cases", []),
                    "catalog_search": app_info["catalog_search"],
                }
                recommendations["likely_apps"].append(app_info["app"])
                recommendations["app_matches"].append(app_match)

        # Add tools to check if apps are installed
        if recommendations["likely_apps"]:
            recommendations["check_tools"] = [
                {
                    "tool": "list_installed_apps",
                    "description": "Quick check for installed apps (may require admin permissions)",
                    "fallback": "Use export_installed_apps if permission denied",
                },
                {
                    "tool": "export_installed_apps",
                    "description": "Get full InstalledApps folder structure",
                    "works_for": "All users (no special permissions required)",
                },
            ]

            # Add next steps
            recommendations["next_steps"] = [
                {
                    "step": 1,
                    "action": "Check if apps are installed",
                    "tools": ["list_installed_apps", "export_installed_apps"],
                    "why": "Discover if recommended apps are already available",
                },
                {
                    "step": 2,
                    "action": "If apps are installed",
                    "tools": ["export_installed_apps"],
                    "why": "Navigate to pre-built dashboards and searches for instant value",
                },
                {
                    "step": 3,
                    "action": "If apps are NOT installed",
                    "recommendation": (
                        "Search app catalog for recommended apps:\n"
                        f"- App Catalog: {recommendations['installation_links']['app_catalog']}\n"
                        f"- Search keywords: {', '.join([m['catalog_search'] for m in recommendations['app_matches']])}\n"
                        "- Contact admin to install missing apps"
                    ),
                },
            ]
        else:
            recommendations["next_steps"] = [
                {
                    "message": "No strong app matches found based on metadata/fields",
                    "suggestion": (
                        "Try:\n"
                        "1. Search app catalog by technology: https://www.sumologic.com/app-catalog\n"
                        "2. Browse integrations docs: https://www.sumologic.com/help/docs/integrations/\n"
                        "3. Use search_query_examples tool to find relevant query patterns"
                    ),
                }
            ]

        return recommendations
