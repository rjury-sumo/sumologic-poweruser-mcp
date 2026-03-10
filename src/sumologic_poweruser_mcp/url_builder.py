"""
URL builder utilities for Sumo Logic web UI.

Converts API endpoints to web UI URLs and builds URLs for various content types.

Based on:
- Hajime VSCode extension: /Users/rjury/Documents/sumo2024/Hajime/src/commands/openSearchInWeb.ts
- Sumo Logic endpoint documentation: https://www.sumologic.com/help/docs/api/about-apis/getting-started/
"""

from typing import Optional
from urllib.parse import urlencode

# Mapping of API endpoints to UI endpoints per region
# Based on https://www.sumologic.com/help/docs/api/about-apis/getting-started/#sumo-logic-endpoints-by-deployment-and-firewall-security
API_TO_UI_MAPPING = {
    "https://api.sumologic.com": "service.sumologic.com",
    "https://api.au.sumologic.com": "service.au.sumologic.com",
    "https://api.ca.sumologic.com": "service.ca.sumologic.com",
    "https://api.de.sumologic.com": "service.de.sumologic.com",
    "https://api.eu.sumologic.com": "service.eu.sumologic.com",
    "https://api.fed.sumologic.com": "service.fed.sumologic.com",
    "https://api.in.sumologic.com": "service.in.sumologic.com",
    "https://api.jp.sumologic.com": "service.jp.sumologic.com",
    "https://api.kr.sumologic.com": "service.kr.sumologic.com",
    "https://api.us2.sumologic.com": "service.us2.sumologic.com",
}


def get_ui_base_url(api_endpoint: str, subdomain: Optional[str] = None) -> str:
    """
    Convert API endpoint to web UI base URL.

    Args:
        api_endpoint: API endpoint URL (e.g., 'https://api.au.sumologic.com')
        subdomain: Optional custom subdomain (e.g., 'mycompany')

    Returns:
        UI base URL (e.g., 'https://service.au.sumologic.com' or 'https://mycompany.au.sumologic.com')

    Examples:
        >>> get_ui_base_url('https://api.sumologic.com')
        'https://service.sumologic.com'
        >>> get_ui_base_url('https://api.au.sumologic.com')
        'https://service.au.sumologic.com'
        >>> get_ui_base_url('https://api.au.sumologic.com', 'mycompany')
        'https://mycompany.au.sumologic.com'
        >>> get_ui_base_url('https://api.sumologic.com', 'mycompany')
        'https://mycompany.sumologic.com'
    """
    # Remove /api suffix if present
    clean_endpoint = api_endpoint.rstrip("/")
    if clean_endpoint.endswith("/api"):
        clean_endpoint = clean_endpoint[:-4]

    # Look up the standard UI endpoint
    if clean_endpoint in API_TO_UI_MAPPING:
        ui_host = API_TO_UI_MAPPING[clean_endpoint]

        # If subdomain is provided, replace 'service' with the subdomain
        if subdomain:
            if ui_host.startswith("service."):
                # service.au.sumologic.com -> mycompany.au.sumologic.com
                ui_host = subdomain + ui_host[7:]
            else:
                # Shouldn't happen, but handle gracefully
                ui_host = subdomain + "." + ui_host

        return f"https://{ui_host}"

    # Fallback: try to construct from API endpoint
    # https://api.au.sumologic.com -> https://service.au.sumologic.com or https://mycompany.au.sumologic.com
    if "api." in clean_endpoint:
        if subdomain:
            ui_url = clean_endpoint.replace("api.", f"{subdomain}.")
        else:
            ui_url = clean_endpoint.replace("api.", "service.")
        return ui_url

    # If no 'api.' in endpoint, it might already be a UI URL or custom domain
    return clean_endpoint


def build_library_url(
    api_endpoint: str, decimal_content_id: str, subdomain: Optional[str] = None
) -> str:
    """
    Build a web UI URL for a library content item (folder, search, scheduled search, etc.).

    Args:
        api_endpoint: API endpoint URL
        decimal_content_id: Content ID in decimal format
        subdomain: Optional custom subdomain

    Returns:
        Library URL (e.g., 'https://service.au.sumologic.com/library/6181891')
    """
    base_url = get_ui_base_url(api_endpoint, subdomain)
    return f"{base_url}/library/{decimal_content_id}"


def build_dashboard_url(
    api_endpoint: str, dashboard_id: str, subdomain: Optional[str] = None
) -> str:
    """
    Build a web UI URL for a dashboard.

    Dashboards use a long unique ID format, not the standard hex/decimal content ID.

    Args:
        api_endpoint: API endpoint URL
        dashboard_id: Dashboard's unique ID (e.g., '8q1pWfcVqCuWHLCf4nt1RpmtTr9hWOHraSjlcARiEQCB8uvHJlnzHqT3YeAD')
        subdomain: Optional custom subdomain

    Returns:
        Dashboard URL (e.g., 'https://service.au.sumologic.com/dashboard/8q1pWfcVqCuWHLCf4nt1RpmtTr9hWOHraSjlcARiEQCB8uvHJlnzHqT3YeAD')
    """
    base_url = get_ui_base_url(api_endpoint, subdomain)
    return f"{base_url}/dashboard/{dashboard_id}"


def build_search_url(
    api_endpoint: str,
    query: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    subdomain: Optional[str] = None,
) -> str:
    """
    Build a web UI URL to open a log search.

    Args:
        api_endpoint: API endpoint URL
        query: Search query text
        start_time: Start time (e.g., '-1h', '2024-01-01T00:00:00', ISO format)
        end_time: End time (e.g., '-1s', '2024-01-01T23:59:59', ISO format)
        subdomain: Optional custom subdomain

    Returns:
        Search URL with encoded query and time range

    Example:
        >>> build_search_url('https://api.au.sumologic.com', '_sourceCategory=prod/app | count', '-1h', '-1s')
        'https://service.au.sumologic.com/log-search/create?query=...&startTime=-1h&endTime=-1s'
    """
    base_url = get_ui_base_url(api_endpoint, subdomain)

    # Default time range if not provided
    params = {"query": query, "startTime": start_time or "-1h", "endTime": end_time or "-1s"}

    # Build URL with query parameters
    query_string = urlencode(params)
    return f"{base_url}/log-search/create?{query_string}"


def build_metrics_search_url(
    api_endpoint: str,
    query: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    subdomain: Optional[str] = None,
) -> str:
    """
    Build a web UI URL to open a metrics search.

    Args:
        api_endpoint: API endpoint URL
        query: Metrics query text
        start_time: Start time (e.g., '-1h', ISO format)
        end_time: End time (e.g., '-1s', ISO format)
        subdomain: Optional custom subdomain

    Returns:
        Metrics search URL with encoded query and time range
    """
    base_url = get_ui_base_url(api_endpoint, subdomain)

    params = {"query": query, "startTime": start_time or "-1h", "endTime": end_time or "-1s"}

    query_string = urlencode(params)
    return f"{base_url}/metrics/create?{query_string}"
