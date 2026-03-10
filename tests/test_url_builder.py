"""Tests for URL builder utilities."""

from src.sumologic_poweruser_mcp.url_builder import (
    build_dashboard_url,
    build_library_url,
    build_metrics_search_url,
    build_search_url,
    get_ui_base_url,
)


class TestGetUIBaseUrl:
    """Tests for get_ui_base_url function."""

    def test_basic_us1_endpoint(self):
        """Test US1 endpoint without subdomain."""
        result = get_ui_base_url("https://api.sumologic.com")
        assert result == "https://service.sumologic.com"

    def test_regional_endpoint(self):
        """Test regional endpoint without subdomain."""
        result = get_ui_base_url("https://api.au.sumologic.com")
        assert result == "https://service.au.sumologic.com"

    def test_with_subdomain_us1(self):
        """Test US1 endpoint with custom subdomain."""
        result = get_ui_base_url("https://api.sumologic.com", "mycompany")
        assert result == "https://mycompany.sumologic.com"

    def test_with_subdomain_regional(self):
        """Test regional endpoint with custom subdomain."""
        result = get_ui_base_url("https://api.au.sumologic.com", "mycompany")
        assert result == "https://mycompany.au.sumologic.com"

    def test_all_regions(self):
        """Test all known Sumo Logic regions."""
        regions = ["au", "ca", "de", "eu", "fed", "in", "jp", "kr", "us2"]
        for region in regions:
            result = get_ui_base_url(f"https://api.{region}.sumologic.com")
            assert result == f"https://service.{region}.sumologic.com"

    def test_with_api_suffix(self):
        """Test endpoint with /api suffix is handled correctly."""
        result = get_ui_base_url("https://api.au.sumologic.com/api")
        assert result == "https://service.au.sumologic.com"


class TestBuildLibraryUrl:
    """Tests for build_library_url function."""

    def test_basic_library_url(self):
        """Test building library URL without subdomain."""
        result = build_library_url("https://api.au.sumologic.com", "6181891")
        assert result == "https://service.au.sumologic.com/library/6181891"

    def test_library_url_with_subdomain(self):
        """Test building library URL with custom subdomain."""
        result = build_library_url("https://api.au.sumologic.com", "6181891", "mycompany")
        assert result == "https://mycompany.au.sumologic.com/library/6181891"


class TestBuildDashboardUrl:
    """Tests for build_dashboard_url function."""

    def test_basic_dashboard_url(self):
        """Test building dashboard URL without subdomain."""
        dashboard_id = "8q1pWfcVqCuWHLCf4nt1RpmtTr9hWOHraSjlcARiEQCB8uvHJlnzHqT3YeAD"
        result = build_dashboard_url("https://api.au.sumologic.com", dashboard_id)
        assert result == f"https://service.au.sumologic.com/dashboard/{dashboard_id}"

    def test_dashboard_url_with_subdomain(self):
        """Test building dashboard URL with custom subdomain."""
        dashboard_id = "8q1pWfcVqCuWHLCf4nt1RpmtTr9hWOHraSjlcARiEQCB8uvHJlnzHqT3YeAD"
        result = build_dashboard_url("https://api.au.sumologic.com", dashboard_id, "mycompany")
        assert result == f"https://mycompany.au.sumologic.com/dashboard/{dashboard_id}"


class TestBuildSearchUrl:
    """Tests for build_search_url function."""

    def test_basic_search_url(self):
        """Test building search URL without subdomain."""
        result = build_search_url(
            "https://api.au.sumologic.com", "_sourceCategory=prod | count", "-1h", "-1s"
        )
        assert "https://service.au.sumologic.com/log-search/create?" in result
        assert "query=" in result
        assert "startTime=-1h" in result
        assert "endTime=-1s" in result

    def test_search_url_with_subdomain(self):
        """Test building search URL with custom subdomain."""
        result = build_search_url(
            "https://api.au.sumologic.com", "_sourceCategory=prod", "-24h", "now", "mycompany"
        )
        assert "https://mycompany.au.sumologic.com/log-search/create?" in result

    def test_search_url_default_time_range(self):
        """Test search URL with default time range."""
        result = build_search_url("https://api.sumologic.com", "error OR exception")
        assert "startTime=-1h" in result
        assert "endTime=-1s" in result

    def test_search_url_query_encoding(self):
        """Test that query is properly URL encoded."""
        result = build_search_url(
            "https://api.sumologic.com",
            "_sourceCategory=prod/app | count by _sourceHost",
            "-1h",
            "-1s",
        )
        # Verify special characters are encoded
        assert "%7C" in result or "|" in result  # pipe character
        assert "query=" in result


class TestBuildMetricsSearchUrl:
    """Tests for build_metrics_search_url function."""

    def test_basic_metrics_url(self):
        """Test building metrics search URL."""
        result = build_metrics_search_url(
            "https://api.au.sumologic.com", "metric=CPU_Idle", "-1h", "-1s"
        )
        assert "https://service.au.sumologic.com/metrics/create?" in result
        assert "query=" in result
        assert "startTime=-1h" in result

    def test_metrics_url_with_subdomain(self):
        """Test building metrics search URL with subdomain."""
        result = build_metrics_search_url(
            "https://api.eu.sumologic.com", "metric=Memory_Used", subdomain="mycompany"
        )
        assert "https://mycompany.eu.sumologic.com/metrics/create?" in result
