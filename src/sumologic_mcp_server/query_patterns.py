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

from typing import List, Optional, Literal, Union
import re


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
    METADATA_FIELDS = ['_sourceCategory', '_collector', '_source', '_sourceName', '_sourceHost']

    # Partition/view specifiers
    PARTITION_FIELDS = ['_index', '_view']

    @staticmethod
    def build_scope(
        partition: Optional[str] = None,
        metadata: Optional[dict] = None,
        keywords: Optional[List[str]] = None,
        indexed_fields: Optional[dict] = None,
        use_and: bool = True
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
            if not partition.startswith('_index=') and not partition.startswith('_view='):
                partition = f'_index={partition}'
            components.append(partition)

        # Add metadata filters
        if metadata:
            for field, value in metadata.items():
                # Validate metadata field
                if field not in ScopePattern.METADATA_FIELDS:
                    # Allow it but it might not route to partitions efficiently
                    pass

                # Quote value if it contains spaces or special chars
                if ' ' in str(value) or any(c in str(value) for c in ['*', '?', '-', '/']):
                    components.append(f'{field}="{value}"')
                else:
                    components.append(f'{field}={value}')

        # Add keyword expressions
        if keywords:
            components.extend(keywords)

        # Add indexed field filters
        if indexed_fields:
            for field, value in indexed_fields.items():
                # Quote value if needed
                if ' ' in str(value) or any(c in str(value) for c in ['*', '?', '-', '/']):
                    components.append(f'{field}="{value}"')
                else:
                    components.append(f'{field}={value}')

        # Join with AND or OR
        if not components:
            return '*'

        separator = ' AND ' if use_and else ' OR '
        return separator.join(components)

    @staticmethod
    def build_metadata_scope(
        source_category: Optional[str] = None,
        collector: Optional[str] = None,
        source: Optional[str] = None,
        source_name: Optional[str] = None,
        source_host: Optional[str] = None,
        use_and: bool = True
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
            metadata['_sourceCategory'] = source_category
        if collector:
            metadata['_collector'] = collector
        if source:
            metadata['_source'] = source
        if source_name:
            metadata['_sourceName'] = source_name
        if source_host:
            metadata['_sourceHost'] = source_host

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
            elif char == '|' and not in_quotes:
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
            'has_partition': False,
            'has_metadata': False,
            'metadata_fields': [],
            'has_keywords': False,
            'is_broad': False,
            'recommendations': []
        }

        scope_lower = scope.lower()

        # Check for partition/view
        if '_index=' in scope_lower or '_view=' in scope_lower:
            analysis['has_partition'] = True

        # Check for metadata fields
        for field in ScopePattern.METADATA_FIELDS:
            if field.lower() in scope_lower:
                analysis['has_metadata'] = True
                analysis['metadata_fields'].append(field)

        # Check for keywords (simplified - looks for bare words not part of field expressions)
        # This is a heuristic - actual parsing would be complex
        tokens = re.split(r'\s+(?:AND|OR|NOT)\s+|\s+', scope)
        for token in tokens:
            if token and not '=' in token and not token.startswith('_') and token not in ['AND', 'OR', 'NOT', '(', ')']:
                analysis['has_keywords'] = True
                break

        # Check if scope is too broad
        if scope.strip() in ['*', '']:
            analysis['is_broad'] = True
            analysis['recommendations'].append('Scope is "*" - this scans all partitions. Add filters to reduce scan volume.')
        elif '_datatier=all' in scope_lower:
            analysis['is_broad'] = True
            analysis['recommendations'].append('Using _dataTier=all scans all tiers. Consider specifying tier or using metadata filters.')

        # Provide recommendations
        if not analysis['has_partition'] and not analysis['has_metadata']:
            analysis['recommendations'].append('Add _sourceCategory or _index to enable partition routing and reduce scan volume.')

        if not analysis['has_keywords'] and not analysis['is_broad']:
            analysis['recommendations'].append('Consider adding keyword expressions for better selectivity and performance.')

        if analysis['has_metadata'] and '_sourceCategory' not in analysis['metadata_fields']:
            analysis['recommendations'].append('Consider using _sourceCategory as it most commonly maps to partition routing.')

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
        include_state: bool = True
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
            operators.append(f'| compare timeshift {days}d {periods} avg')

        # Null guards with state detection (only for first field)
        if include_state:
            operators.extend([
                f'| if(isNull({field}), "{labels["gone"]}", "{labels["collecting"]}") as state',
                f'| if(isNull({field}), 0, {field}) as {field}',
                f'| if(isNull({avg_field}), "{labels["new"]}", state) as state',
            ])
        else:
            operators.append(f'| if(isNull({field}), 0, {field}) as {field}')

        # Null guard for averaged field
        operators.append(f'| if(isNull({avg_field}), 0, {avg_field}) as {avg_field}')

        # Null-safe percentage with division-by-zero handling
        operators.append(
            f'| if({avg_field} == 0, if({field} == 0, 0, 100), '
            f'(({field} - {avg_field}) / {avg_field}) * 100) as pct_change_{field}'
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
        multiply_by: Optional[float] = None
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
            f'| if(isNull({numerator}) or isNull({denominator}), {null_result}, '
            f'if({denominator} == 0, {div_zero_result}, {division})) as {result_field}'
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
        return f'| if(isNull({field}), {default_value}, {field}) as {field}'

    @staticmethod
    def percentage_change(
        current: str,
        baseline: str,
        result_field: str = "pct_change"
    ) -> str:
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
            f'| if({baseline} == 0, if({current} == 0, 0, 100), '
            f'(({current} - {baseline}) / {baseline}) * 100) as {result_field}'
        )


class AggregationPatterns:
    """Common aggregation and sorting patterns for Sumo Logic queries."""

    @staticmethod
    def volume_by_dimension(
        dimension: str,
        include_tier: bool = True,
        additional_dimensions: Optional[List[str]] = None
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
            group_by.append('dataTier')
        group_by.append(dimension)
        if additional_dimensions:
            group_by.extend(additional_dimensions)

        group_by_str = ', '.join(group_by)
        return f'| sum(events) as events, sum(gbytes) as gbytes by {group_by_str}'

    @staticmethod
    def top_n(
        sort_field: str,
        limit: int = 100,
        direction: Literal["asc", "desc"] = "desc"
    ) -> str:
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
        return f'| sort {sort_field} {direction} | limit {limit}'

    @staticmethod
    def timeslice_aggregation(
        interval: str,
        fields: List[str],
        group_by: Optional[List[str]] = None
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
        fields_str = ', '.join(fields)
        group_by_list = ['_timeslice']
        if group_by:
            group_by_list.extend(group_by)
        group_by_str = ', '.join(group_by_list)

        return f'| timeslice {interval} | {fields_str} by {group_by_str}'


class CreditCalculation:
    """Sumo Logic credit rate calculations for different data tiers.

    Credit rates vary by pricing model:
    - Standard Tiered: Different rates per tier
    - Flex: Usage-based pricing
    - CSE: Security-specific pricing

    Note: Rates are subject to change. Verify current rates in Sumo Logic documentation.
    """

    # Standard tiered credit rates (credits per GB)
    STANDARD_RATES = {
        'Continuous': 20,
        'Frequent': 9,
        'Infrequent': 0.4,
        'CSE': 25
    }

    @staticmethod
    def add_credit_calculation(
        data_field: str = 'gbytes',
        tier_field: str = 'dataTier',
        credit_field: str = 'credits',
        rates: Optional[dict] = None
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
            f'| {data_field} * credit_rate as {credit_field}'
        ]

        return operators
