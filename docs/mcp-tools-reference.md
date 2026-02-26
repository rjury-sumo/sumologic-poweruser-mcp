# Sumo Logic MCP Server - Tools Reference

## Overview
Total Tools: **28**

---

## Search & Query Tools (6)

### 1. `search_sumo_logs`
Search Sumo Logic logs using a query. Automatically detects query type (raw messages or aggregated records) and returns appropriate results.

**Parameters:**
- `query` (str) - Sumo Logic search query
- `hours_back` (int, default=1) - Number of hours to search back
- `from_time` (str, optional) - Start time (ISO8601, epoch ms, or relative like '-1h')
- `to_time` (str, optional) - End time (ISO8601, epoch ms, or relative like 'now')
- `time_zone` (str, default='UTC') - Timezone for search
- `by_receipt_time` (bool, default=False) - Use receipt time instead of message time
- `instance` (str, default='default') - Instance name

**Returns:** Job ID, state, query type, message/record counts, and results array

---

### 2. `create_sumo_search_job`
Create a search job and return immediately with job ID. Use for long-running searches.

**Parameters:**
- `query` (str) - Sumo Logic search query
- `from_time` (str) - Start time
- `to_time` (str) - End time
- `time_zone` (str, default='UTC') - Timezone
- `by_receipt_time` (bool, default=False) - Use receipt time
- `instance` (str, default='default') - Instance name

**Returns:** Job ID and link

---

### 3. `get_sumo_search_job_status`
Get the status of a search job.

**Parameters:**
- `job_id` (str) - Search job ID
- `instance` (str, default='default') - Instance name

**Returns:** Job state, message count, record count, histogram buckets

---

### 4. `get_sumo_search_job_results`
Get results from a completed search job. Auto-detects result type (messages or records).

**Parameters:**
- `job_id` (str) - Search job ID
- `result_type` (str, default='auto') - Result type: 'auto', 'messages', or 'records'
- `offset` (int, default=0) - Pagination offset
- `limit` (int, default=1000) - Maximum results (1-10000)
- `instance` (str, default='default') - Instance name

**Returns:** Array of messages or records

---

### 5. `query_sumo_metrics`
Query Sumo Logic metrics.

**Parameters:**
- `query` (str) - Metrics query (e.g., "metric=CPU_User | avg by host")
- `hours_back` (int, default=1) - Hours to query back
- `instance` (str, default='default') - Instance name

**Returns:** Metrics query results with time series data

---

### 6. `run_search_audit_query`
Run a search audit query to analyze search usage and performance. Queries the special `_view=sumologic_search_usage_per_query` index.

**Parameters:**
- `from_time` (str, default='-24h') - Start time (relative or ISO8601)
- `to_time` (str, default='now') - End time (relative or ISO8601)
- `query_type` (str, default='*') - Filter by type (Interactive, Scheduled, Monitors, etc.)
- `user_name` (str, default='*') - Filter by username (wildcards supported)
- `content_name` (str, default='*') - Filter by content name
- `query_filter` (str, default='*') - Filter by query text
- `query_regex` (str, default='.*') - Regex pattern to filter queries
- `include_raw_data` (bool, default=False) - Include raw field data
- `instance` (str, default='default') - Instance name

**Returns:** Aggregated search metrics with:
- Total searches, data scanned (GB), Infrequent/Flex tier breakdown
- Results count, avg partitions scanned, avg time range
- Runtime statistics (total and average in minutes)
- Grouped by user, query, query type, content name

**Example Use Cases:**
- All searches in last 24h: (use defaults)
- Interactive searches by user: `query_type='Interactive'`, `user_name='john@example.com'`
- Dashboard searches: `query_type='Scheduled'`, `content_name='*Dashboard*'`
- Expensive searches: `query_regex='.*\\| count.*'`

**Reference:** [Search Audit Index Docs](https://www.sumologic.com/help/docs/manage/security/audit-indexes/search-audit-index/)

---

## Content Library Tools (7)

### 7. `get_personal_folder`
Get user's personal folder with optional children. Fast synchronous access to personal library.

**Parameters:**
- `include_children` (bool, default=True) - Include child items
- `instance` (str, default='default') - Instance name

**Returns:** Folder metadata and children array

**Use Cases:**
- Access user's personal library root
- List personal content quickly

---

### 8. `get_folder_by_id`
Get a specific folder by ID with optional children. Navigate folder hierarchy.

**Parameters:**
- `folder_id` (str) - Hex folder ID (16 characters)
- `include_children` (bool, default=True) - Include children
- `instance` (str, default='default') - Instance name

**Returns:** Folder metadata and immediate children

**Use Cases:**
- Navigate multi-level folder structures
- Browse folder contents

---

### 9. `get_content_by_path`
Get content item by its library path.

**Parameters:**
- `content_path` (str) - Full library path (e.g., "/Library/Users/user@email.com/MyFolder")
- `instance` (str, default='default') - Instance name

**Returns:** Content item metadata

**Use Cases:**
- Access content by known path
- Validate path exists

---

### 10. `get_content_path_by_id`
Get the full library path for a content ID.

**Parameters:**
- `content_id` (str) - Hex content ID
- `instance` (str, default='default') - Instance name

**Returns:** Full path and path items array

**Use Cases:**
- Display content location
- Build breadcrumb navigation

---

### 11. `export_content`
Export full content structure (dashboards, searches, etc.) with async job handling.

**Parameters:**
- `content_id` (str) - Hex content ID to export
- `is_admin_mode` (bool, default=False) - Use admin permissions
- `max_wait_seconds` (int, default=300) - Max polling time
- `instance` (str, default='default') - Instance name

**Returns:** Complete content structure including nested elements, queries, panels, etc.

**Use Cases:**
- Get complete dashboard definition
- Export searches with all details
- Backup content
- Deep inspection of content

---

### 12. `export_global_folder`
Export Global folder contents (async). **IMPORTANT:** Uses 'data' array instead of 'children'.

**Parameters:**
- `is_admin_mode` (bool, default=False) - Use admin mode
- `max_wait_seconds` (int, default=300) - Max polling time
- `instance` (str, default='default') - Instance name

**Returns:** Global folder with 'data' array containing children

**Use Cases:**
- List global/shared content
- Discover organization-wide content

---

### 13. `export_admin_recommended_folder`
Export Admin Recommended folder (async). Uses 'children' array (unlike Global folder).

**Parameters:**
- `is_admin_mode` (bool, default=False) - Use admin mode
- `max_wait_seconds` (int, default=300) - Max polling time
- `instance` (str, default='default') - Instance name

**Returns:** Admin Recommended folder with 'children' array

**Use Cases:**
- Access admin-curated content
- Discover best practices content

---

## Content ID Utilities (3)

### 14. `convert_content_id_hex_to_decimal`
Convert hex content ID to decimal format for web UI URLs.

**Parameters:**
- `hex_id` (str) - Hex content ID (e.g., "00000000005E5403")

**Returns:** Hex ID, decimal ID, and formatted string

**Example:** `00000000005E5403` → `6181891`

**Use Cases:**
- Generate web UI URLs
- Display user-friendly IDs

---

### 15. `convert_content_id_decimal_to_hex`
Convert decimal content ID to hex format for API calls.

**Parameters:**
- `decimal_id` (str) - Decimal content ID (e.g., "6181891")

**Returns:** Hex ID, decimal ID, and formatted string

**Example:** `6181891` → `00000000005E5403`

**Use Cases:**
- Convert web UI IDs to API format
- Normalize ID input

---

### 16. `get_content_web_url`
Generate web UI URL for a content item.

**Parameters:**
- `content_id` (str) - Content ID (hex or decimal)
- `instance` (str, default='default') - Instance name

**Returns:** URL, hex ID, decimal ID, instance

**Example:** `https://instance.sumologic.com/library/6181891`

**Use Cases:**
- Share content links
- Open content in browser
- Generate shareable URLs

---

## Collectors & Sources Tools (2)

### 17. `get_sumo_collectors`
Get list of Sumo Logic collectors.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of collector objects

---

### 18. `get_sumo_sources`
Get sources for a specific Sumo Logic collector.

**Parameters:**
- `collector_id` (int) - Collector ID
- `instance` (str, default='default') - Instance name

**Returns:** Array of source objects for the collector

---

## Users & Roles Tools (2)

### 19. `get_sumo_users`
Get list of Sumo Logic users.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of user objects

---

### 20. `get_sumo_roles_v2`
Get list of roles using the v2 Roles API.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of role objects

---

## Dashboards & Monitors Tools (2)

### 21. `get_sumo_dashboards`
Get list of Sumo Logic dashboards.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of dashboard objects

---

### 22. `search_sumo_monitors`
Search for monitors and monitor folders.

**Parameters:**
- `query` (str) - Search query (e.g., "Test", "name:*error*")
- `limit` (int, default=100) - Maximum results
- `offset` (int, default=0) - Pagination offset
- `instance` (str, default='default') - Instance name

**Returns:** Array of matching monitors

**Query Examples:**
- `'Test'` - Search for monitors containing 'Test'
- `'createdBy:000000000000968B'` - Search by creator ID
- `'monitorStatus:Normal'` - Search by status
- `'name:*error*'` - Search monitors with 'error' in name

---

## System Tools (2)

### 23. `get_sumo_partitions`
Get list of partitions.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of partition objects

---

### 24. `list_sumo_instances`
List all configured Sumo Logic instances.

**Parameters:** None

**Returns:** Array of instance names and count

---

## Account Management Tools (3)

### 25. `get_account_status`
Get account status including subscription, plan type, and usage information.

**Parameters:**
- `instance` (str, default='default') - Instance name

**Returns:** Account details including:
- Plan type (Trial, Essentials, Enterprise Operations, etc.)
- Total credits and usage
- Subscription period (start/end dates)
- Account creation date
- Organization ID

**API Reference:** https://api.sumologic.com/docs/#operation/getStatus

---

### 26. `get_usage_forecast`
Get usage forecast for specified number of days based on recent consumption patterns.

**Parameters:**
- `number_of_days` (int) - Number of days to forecast (1-365, typically 7, 30, or 90)
- `instance` (str, default='default') - Instance name

**Returns:** Forecasted usage including:
- Forecasted total credits
- Forecasted continuous ingest
- Forecasted frequent ingest
- Forecasted storage
- Forecasted metrics ingest

**API Reference:** https://api.sumologic.com/docs/#operation/getUsageForecast

---

### 27. `export_usage_report`
Export detailed usage report for a date range (async operation). Returns download URL for CSV report.

**Parameters:**
- `start_date` (str) - Start date in YYYY-MM-DD format
- `end_date` (str) - End date in YYYY-MM-DD format
- `group_by` (str, default='day') - Grouping period: 'day', 'week', or 'month'
- `report_type` (str, default='standard') - Report type: 'standard', 'detailed', or 'childDetailed'
- `include_deployment_charge` (bool, default=False) - Include deployment charges for child orgs
- `max_wait_seconds` (int, default=300) - Maximum seconds to wait for export completion
- `poll_interval_seconds` (int, default=5) - Seconds between status checks
- `instance` (str, default='default') - Instance name

**Returns:** Job status and S3 presigned download URL (valid for 10 minutes)

**Notes:**
- This is an async operation that polls for completion
- Download URL expires after 10 minutes
- CSV includes daily/weekly/monthly usage breakdowns by product line

**API Reference:** https://api.sumologic.com/docs/#operation/exportUsageReport

---

### 28. `get_estimated_log_search_usage`
Get estimated data volume that would be scanned for a log search query in Infrequent Data Tier and Flex.

**Parameters:**
- `query` (str) - Log search query/scope (e.g., "_sourceCategory=prod/app" or "_view=my_view")
- `from_time` (str, default='-1h') - Start time (ISO8601, epoch ms, or relative like '-1h', '-24h', '-7d')
- `to_time` (str, default='now') - End time (ISO8601, epoch ms, or relative like 'now')
- `time_zone` (str, default='UTC') - Timezone for the search
- `by_view` (bool, default=True) - If True, returns breakdown by partition/view (recommended)
- `instance` (str, default='default') - Instance name

**Returns:** Detailed breakdown including:
- Total estimated data to scan (formatted)
- Per-partition/view breakdown with:
  - Data tier info (Continuous, Frequent, Infrequent)
  - Metering tier information
  - Scan volume in bytes
- Run by receipt time flag
- Interval time type

**Use Cases:**
- Estimate query costs before running expensive queries in Infrequent/Flex tiers
- Refine search scope to reduce scanned data
- Understand which partitions/views contribute to scan volume
- Budget planning for per-query pricing models

**Time Format Examples:**
- Relative: "-1h", "-24h", "-7d", "-1w", "now"
- ISO: "2024-01-01T00:00:00Z"
- Epoch ms: "1704067200000"

**Notes:**
- In Infrequent Data Tier and Flex, you pay per query based on data scanned
- Use this endpoint to estimate costs before running queries
- The `by_view=True` option provides detailed partition/view breakdown
- Empty partition names are displayed as "sumologic_default"

**API Reference:** https://help.sumologic.com/docs/api/log-search-estimated-usage/

---

## Tool Categories Summary

| Category | Count | Tools |
|----------|-------|-------|
| **Search & Query** | 6 | Search logs, create jobs, get status/results, query metrics, search audit |
| **Content Library** | 7 | Personal/folder access, path operations, content export |
| **Content ID Utilities** | 3 | Hex/decimal conversion, web URL generation |
| **Account Management** | 4 | Account status, usage forecast, usage report export, estimated log search usage |
| **Collectors & Sources** | 2 | List collectors, get sources |
| **Users & Roles** | 2 | List users, list roles |
| **Dashboards & Monitors** | 2 | List dashboards, search monitors |
| **System** | 2 | List partitions, list instances |

---

## Notes

### Rate Limiting
- All tools respect the configured rate limit (default: 4 requests/second)
- Rate limiting is enforced per tool call

### Instance Configuration
- All tools support multi-instance configuration
- Default instance is 'default'
- Configure instances via environment variables (see `.env.example`)

### Async Export Jobs
- Export tools (`export_content`, `export_global_folder`, `export_admin_recommended_folder`, `export_usage_report`) use async job pattern
- Default timeout: 300 seconds (5 minutes)
- Default poll interval: 2 seconds (content exports) or 5 seconds (usage reports)
- Usage report downloads expire after 10 minutes

### Content Library Quirks
- **Personal folder**: Fast synchronous API, returns children directly
- **Global folder**: Async export, uses `data` array (NOT `children`)
- **Admin Recommended**: Async export, uses `children` array
- **isAdminMode flag**: Changes content scope/visibility

---

**Version:** 1.3
**Last Updated:** 2026-02-26
**Total Tools:** 28
