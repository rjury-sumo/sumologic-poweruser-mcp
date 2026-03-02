# Sumo Logic MCP Server - Tools Reference

## Overview
Total Tools: **41**

---

## Search & Query Tools (9)

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

### 7. `explore_log_metadata`
Explore log metadata values for a given scope to discover partitions, source categories, and other metadata dimensions.

**Parameters:**
- `scope` (str, default='*') - Log search scope
- `from_time` (str, default='-15m') - Start time (ISO8601, epoch ms, or relative)
- `to_time` (str, default='now') - End time
- `time_zone` (str, default='UTC') - Timezone
- `metadata_fields` (str, default='_view,_sourceCategory') - Comma-separated metadata fields to aggregate
- `sort_by` (str, default='_sourceCategory') - Field to sort results by
- `max_results` (int, default=1000) - Maximum results to return
- `instance` (str, default='default') - Instance name

**Common Metadata Fields:**
- `_view` / `_index` - Partition name
- `_sourceCategory` - Source category assigned to logs
- `_collector` - Collector name
- `_source` - Source name
- `_sourceHost` - Source host
- `_sourceName` - Source name (alternative)

**Returns:** JSON with metadata combinations and message counts

**Use Cases:**
- Discover which partitions/views contain specific logs
- Map source categories to partitions for query optimization
- Essential for Flex/Infrequent tier accounts to scope queries before incurring scan charges

---

### 8. `analyze_search_scan_cost`
Analyze search scan costs with detailed tier/metering breakdown for Infrequent and Flex customers. Specifically designed for analyzing pay-per-search costs.

**⚠️ IMPORTANT FOR FLEX ORGANIZATIONS**: Flex orgs MUST use `breakdown_type='metering'` or `'auto'` (default). Using `'tier'` returns near-zero scan data for Flex logs.

**Parameters:**
- `from_time` (str, default='-24h') - Start time (relative or ISO8601)
- `to_time` (str, default='now') - End time (relative or ISO8601)
- `query_type` (str, default='*') - Filter by type (Interactive, Scheduled, etc.)
- `user_name` (str, default='*') - Filter by username
- `content_name` (str, default='*') - Filter by content name
- `analytics_tier_filter` (str, default='*') - Filter by analytics_tier (*infrequent*, *flex*, etc.)
- `breakdown_type` (str, default='auto') - 'auto' (auto-detect), 'tier', or 'metering'
- `group_by` (str, default='user_query') - 'user', 'user_query', 'user_scope_query', 'user_content', 'content'
- `include_scope_parsing` (bool, default=True) - Extract scope (_index/_view) from query
- `scan_credit_rate` (float, default=0.016) - Credits per GB scanned (0.016 cr/GB = 16 cr/TB). Only used for Infrequent tier (tiered accounts). Not used for Flex metering breakdown.
- `min_scan_gb` (float, default=0.0) - Minimum scan GB threshold
- `sort_by` (str, default='scan_credits') - Sort field (scan_credits for tier breakdown, billable_scan_gb for metering)
- `limit` (int, default=100) - Max results
- `instance` (str, default='default') - Instance name

**Breakdown Types:**
- **auto** (DEFAULT): Automatically detects organization type (Flex vs Tiered) via account status API and selects appropriate breakdown
- **tier** (Tiered customers ONLY): Continuous, Frequent, Infrequent data tier breakdown. **WARNING**: Returns near-zero data on Flex orgs!
- **metering** (Flex customers - REQUIRED): Flex, FlexSecurity, Continuous, Frequent, Infrequent, Security, Tracing breakdown with billable vs non-billable calculation

**Group By Options:**
- **user**: Aggregate by user_name only
- **user_query**: Group by user_name and query text
- **user_scope_query**: Group by user_name, scope (_index/_view), and query
- **user_content**: Group by user_name and content_name (dashboards/scheduled searches)
- **content**: Group by content_name only (scheduled search analysis)

**Returns:** JSON with scan cost analysis including:

**For Tier Breakdown (Infrequent tier):**
- queries: Number of searches
- total_scan_gb: Total data scanned
- scan_credits: Estimated credits (0.016 cr/GB standard rate)
- credits_per_query: Average credits per query
- tier_breakdown_gb: GB per tier (continuous/frequent/infrequent)

**For Metering Breakdown (Flex):**
- queries: Number of searches
- total_scan_gb: Total data scanned
- billable_scan_gb: Billable scan volume in GB
- **billable_scan_tb**: Billable scan volume in TB (primary unit for Flex)
- non_billable_scan_gb: Non-billable scan volume
- metering_breakdown_gb: GB per metering type
- flex_billing_note: Note that credits are NOT calculated (contract-specific)

**Both:**
- detected_org_type: Organization type if auto-detected (Flex/Tiered)
- warning: Alert if using 'tier' breakdown on suspected Flex org

**Use Cases:**
1. **Auto-detect and analyze** (RECOMMENDED): `breakdown_type='auto'` (default)
2. **Infrequent tier cost analysis**: `analytics_tier_filter='*infrequent*'`, `group_by='user_query'`
3. **Flex billable scan analysis**: `breakdown_type='metering'`, `group_by='user_scope_query'`
4. **Expensive dashboard analysis**: `group_by='content'`, `query_type='Scheduled'`
5. **User scan ranking**: `group_by='user'`, `sort_by='billable_scan_gb'` (Flex) or `'scan_credits'` (Tiered)

**Important Notes:**
- **Infrequent tier**: Credits calculated using 0.016 cr/GB (16 cr/TB) standard rate
- **Flex tier**: Credits NOT calculated - rates vary by contract. Use TB values for cost estimation.

**Reference:** [Search Audit Index Docs](https://www.sumologic.com/help/docs/manage/security/audit-indexes/search-audit-index/)

---

## Query Examples Tools (1)

### 9. `search_query_examples`
Search through 11,000+ real Sumo Logic queries from 280+ published apps using intelligent scoring and relevance ranking.

**Parameters:**
- `query` (str, optional) - Natural language search (e.g., "apache 4xx errors by server")
- `app_name` (str, optional) - Filter by app name (e.g., "Apache", "AWS", "Kubernetes")
- `use_case` (str, optional) - Filter by use case (e.g., "performance", "security", "errors")
- `query_type` (str, optional) - Filter by query type: "Logs" or "Metrics"
- `keywords` (str, optional) - Search for specific keywords in queries
- `max_results` (int, default=10) - Maximum number of results (1-100)
- `match_mode` (str, default='any') - Matching mode: 'any', 'all', or 'fuzzy'

**Search Features:**
- Natural language search with relevance scoring
- Tokenized multi-word search
- Technology aliases (k8s→Kubernetes, httpd→Apache)
- Match metadata showing why each result matched
- Smart fallback that relaxes filters when no results found

**Match Modes:**
- `any` (default) - Scores by relevance, more matches = higher rank
- `all` - Strict AND, all filters must match
- `fuzzy` - Auto-relaxes filters if zero results

**Returns:** Array of matching queries with scores, match metadata, and query details

**Use Cases:**
- Find example queries for specific technologies or use cases
- Learn query patterns and best practices
- Discover queries for monitoring specific applications

**Resource:** Also available via `sumo://query-examples` resource (returns 20 diverse examples)

---

## Log Volume Analysis Tools (2)

### 10. `analyze_log_volume`
Analyze raw log volume using the _size field to understand ingestion drivers and optimize Infrequent tier usage.

**Parameters:**
- `scope` (str) - Search scope expression (e.g., '_index=prod_app_logs', '_sourceCategory=*cloudtrail*')
- `aggregate_by` (list[str]) - List of fields to aggregate by (e.g., ['_sourceCategory'], ['eventname', 'eventsource'])
- `from_time` (str, default='-24h') - Start time
- `to_time` (str, default='now') - End time
- `additional_fields` (list[str], optional) - Optional fields to sample values from using values() operator
- `top_n` (int, default=100) - Maximum results to return
- `include_percentage` (bool, default=True) - Include percentage of total
- `instance` (str, default='default') - Instance name

**Returns:** Volume analysis with GB/MB breakdown, event counts, and percentages

**Use Cases:**
- Find top volume drivers within a partition by metadata
- Analyze CloudTrail volume by event type
- Multi-dimensional analysis with sampling
- Parse and analyze complex logs

---

### 11. `profile_log_schema`
Discover available fields and suggest good dimensions for volume analysis using the facets operator.

**Parameters:**
- `scope` (str) - Search scope expression
- `from_time` (str, default='-15m') - Start time (keep short for better performance)
- `to_time` (str, default='now') - End time
- `max_facets` (int, default=20) - Maximum number of fields to discover
- `instance` (str, default='default') - Instance name

**Returns:** Discovered fields with cardinality estimates and suggestions for good aggregate_by dimensions

**Use Cases:**
- Discover what fields are available in logs before analyzing volume
- Identify high-cardinality fields that may not work well for aggregation
- Find good candidate fields for volume analysis

---

## Content Library Tools (10)

### 12. `get_personal_folder`
Get user's personal folder with optional children. Fast synchronous access to personal library.

**Parameters:**
- `include_children` (bool, default=True) - Include child items
- `instance` (str, default='default') - Instance name

**Returns:** Folder metadata and children array

**Use Cases:**
- Access user's personal library root
- List personal content quickly

---

### 13. `get_folder_by_id`
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

### 14. `get_content_by_path`
Get content item by its library path.

**Parameters:**
- `content_path` (str) - Full library path (e.g., "/Library/Users/user@email.com/MyFolder")
- `instance` (str, default='default') - Instance name

**Returns:** Content item metadata

**Use Cases:**
- Access content by known path
- Validate path exists

---

### 15. `get_content_path_by_id`
Get the full library path for a content ID.

**Parameters:**
- `content_id` (str) - Hex content ID
- `instance` (str, default='default') - Instance name

**Returns:** Full path and path items array

**Use Cases:**
- Display content location
- Build breadcrumb navigation

---

### 16. `export_content`
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

### 17. `export_global_folder`
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

### 18. `export_admin_recommended_folder`
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

### 19. `export_installed_apps`
Export Installed Apps folder to discover pre-built apps available in your Sumo Logic instance (async).

**Parameters:**
- `is_admin_mode` (bool, default=False) - View as admin to see all apps
- `max_wait_seconds` (int, default=300) - Maximum seconds to wait for async job
- `instance` (str, default='default') - Instance name

**Returns:** JSON with installed apps structure containing:
- App folders organized by category/technology
- Each app contains dashboards, searches, monitors
- Content IDs for accessing specific app components

**Use Cases:**
- **Discover available apps**: See what pre-built content is already installed
- **Find relevant dashboards**: Locate dashboards for AWS, Kubernetes, Apache, etc.
- **Log discovery integration**: After finding logs, discover if there's already an app for them
- **Use case mapping**: Connect log sources to pre-built monitoring solutions

**App Catalog References:**
- Browse all apps: https://www.sumologic.com/app-catalog
- Search by keyword: Use app catalog to find apps matching your technology
- Integration docs: https://www.sumologic.com/help/docs/integrations/

**Example Flow:**
1. Use LogDiscoveryPattern to find logs (e.g., CloudTrail logs)
2. Use export_installed_apps to see if AWS CloudTrail app is installed
3. If installed, navigate directly to app dashboards and searches
4. If not installed, suggest admin install from app catalog

**Notes:**
- Similar async pattern to export_global_folder and export_admin_recommended_folder
- InstalledApps is a top-level library location like Global and Admin Recommended
- Each app folder typically contains: Overview dashboard, detailed dashboards, saved searches
- Apps are pre-configured with optimal queries and visualizations for their technology

**API Reference:** https://api.sumologic.com/docs/#operation/getInstalledAppsFolderAsync

---

### 20. `list_installed_apps`
List all installed Sumo Logic apps (lightweight alternative to export_installed_apps).

**Parameters:**
- `instance` (str, default='default') - Instance name

**Returns:** JSON array of installed apps with:
- App UUID
- App name (e.g., "AWS CloudTrail", "Apache", "Kubernetes")
- App manifest version
- Installation info

**Use Cases:**
- **Quick discovery**: Faster than exporting full folder structure
- **App availability check**: See if specific app is installed
- **Log discovery integration**: Check for relevant apps after finding logs

**Permission Note:**
This endpoint may require admin permissions in some organizations. If it fails with permission error, use export_installed_apps instead which works with regular user permissions.

**App Discovery Flow:**
1. Phase 1: Use LogDiscoveryPattern to find logs (e.g., 'cloudtrail')
2. Phase 2: Use list_installed_apps to see if AWS CloudTrail app exists
3. If found: Use export_installed_apps to get full app structure
4. If not found: Suggest installation from https://www.sumologic.com/app-catalog

**App Catalog:**
- Browse apps: https://www.sumologic.com/app-catalog
- Search by keyword: Find apps matching your logs/technology
- Integration guides: https://www.sumologic.com/help/docs/integrations/

**API Reference:** https://api.sumologic.com/docs/#operation/listAppsV2

---

## Content ID Utilities (3)

### 21. `convert_content_id_hex_to_decimal`
Convert hex content ID to decimal format for web UI URLs.

**Parameters:**
- `hex_id` (str) - Hex content ID (e.g., "00000000005E5403")

**Returns:** Hex ID, decimal ID, and formatted string

**Example:** `00000000005E5403` → `6181891`

**Use Cases:**
- Generate web UI URLs
- Display user-friendly IDs

---

### 22. `convert_content_id_decimal_to_hex`
Convert decimal content ID to hex format for API calls.

**Parameters:**
- `decimal_id` (str) - Decimal content ID (e.g., "6181891")

**Returns:** Hex ID, decimal ID, and formatted string

**Example:** `6181891` → `00000000005E5403`

**Use Cases:**
- Convert web UI IDs to API format
- Normalize ID input

---

### 23. `get_content_web_url`
Generate web UI URL for a content item with proper handling for different content types.

**Parameters:**
- `content_id` (str) - Content ID (hex or decimal)
- `content_type` (str, optional) - Content type (Dashboard, Search, Folder, etc.) to optimize URL generation
- `instance` (str, default='default') - Instance name

**Returns:** URL, hex ID, decimal ID, content type, instance

**URL Formats:**
- Library content (folders, searches, etc.): `https://service.au.sumologic.com/library/6181891`
- Dashboards: `https://service.au.sumologic.com/dashboard/<dashboard_id>`
- Custom subdomain: `https://mycompany.au.sumologic.com/library/6181891`

**Use Cases:**
- Share content links with correct URL format
- Open content in browser
- Generate shareable URLs for folders, searches, dashboards
- Automatically handles dashboard vs library content URLs

**Notes:**
- If subdomain is configured in `.env` (e.g., `SUMO_SUBDOMAIN=mycompany`), URLs will use custom subdomain
- Tool automatically detects if content is a dashboard and uses appropriate URL format
- For dashboards, fetches the dashboard ID needed for proper URL generation

---

### 24. `build_search_web_url`
Build a web UI URL to open a log search query with pre-filled query and time range.

**Parameters:**
- `query` (str) - Sumo Logic search query to open
- `start_time` (str, optional, default='-1h') - Start time (e.g., '-1h', '-24h', '2024-01-01T00:00:00', ISO format)
- `end_time` (str, optional, default='-1s') - End time (e.g., '-1s', 'now', '2024-01-01T23:59:59', ISO format)
- `instance` (str, default='default') - Instance name

**Returns:** URL, query, start_time, end_time, instance

**Example:** `https://service.au.sumologic.com/log-search/create?query=...&startTime=-1h&endTime=-1s`

**Use Cases:**
- Share search queries with team members
- Open searches from other tools (Slack, email, documentation)
- Create bookmarks for frequently-used searches
- Generate URLs for saved search queries

**Time Range Examples:**
- Last hour: `start_time='-1h', end_time='-1s'`
- Last 24 hours: `start_time='-24h', end_time='now'`
- Specific date range: `start_time='2024-01-01T00:00:00', end_time='2024-01-01T23:59:59'`

---

## Field Management Tools (3)

### 25. `list_custom_fields`
List all custom fields defined in the organization.

**Parameters:**
- `instance` (str, default='default') - Instance name

**Returns:** Array of custom field objects with:
- Field name and key
- Data type
- Field ID

**Use Cases:**
- Discover available custom fields for query building
- Audit custom field usage

---

### 26. `list_field_extraction_rules`
List all field extraction rules (FERs) for pre-parsing logs.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of FER objects with:
- Rule name and scope
- Parse expression
- Enabled status

**Use Cases:**
- Audit FER configuration
- Discover which fields are extracted at ingest time

---

### 27. `get_field_extraction_rule`
Get detailed information about a specific field extraction rule.

**Parameters:**
- `rule_id` (str) - FER ID
- `instance` (str, default='default') - Instance name

**Returns:** Complete FER details including:
- Parse expression
- Scope filter
- Field list
- Enabled status

**Use Cases:**
- Inspect FER configuration
- Debug field extraction issues

---

## Collectors & Sources Tools (2)

### 28. `get_sumo_collectors`
Get list of Sumo Logic collectors.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of collector objects

---

### 29. `get_sumo_sources`
Get sources for a specific Sumo Logic collector.

**Parameters:**
- `collector_id` (int) - Collector ID
- `instance` (str, default='default') - Instance name

**Returns:** Array of source objects for the collector

---

## Users & Roles Tools (2)

### 30. `get_sumo_users`
Get list of Sumo Logic users.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of user objects

---

### 31. `get_sumo_roles_v2`
Get list of roles using the v2 Roles API.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of role objects

---

## Dashboards & Monitors Tools (2)

### 32. `get_sumo_dashboards`
Get list of Sumo Logic dashboards.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of dashboard objects

---

### 33. `search_sumo_monitors`
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

### 34. `get_sumo_partitions`
Get list of partitions.

**Parameters:**
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Returns:** Array of partition objects

---

### 35. `list_sumo_instances`
List all configured Sumo Logic instances.

**Parameters:** None

**Returns:** Array of instance names and count

---

## Account Management Tools (6)

### 36. `get_account_status`
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

### 37. `get_usage_forecast`
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

### 38. `export_usage_report`
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

### 39. `get_estimated_log_search_usage`
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

### 40. `analyze_data_volume`
Analyze data volume ingestion from the Sumo Logic Data Volume Index for capacity planning and cost analysis.

**Parameters:**
- `dimension` (str, default='sourceCategory') - Metadata dimension to analyze
- `from_time` (str, default='-24h') - Start time (ISO8601, epoch ms, or relative)
- `to_time` (str, default='now') - End time
- `time_zone` (str, default='UTC') - Timezone
- `include_credits` (bool, default=True) - Calculate credits based on tier rates
- `include_timeshift` (bool, default=False) - Compare with previous periods
- `timeshift_days` (int, default=7) - Days to shift back for comparison
- `timeshift_periods` (int, default=3) - Number of periods to average
- `sort_by` (str, default='gbytes') - Sort field (gbytes, events, credits)
- `limit` (int, default=100) - Maximum results
- `filter_pattern` (str, default='*') - Filter pattern for dimension values
- `instance` (str, default='default') - Instance name

**Dimension Options:**
- `sourceCategory` - Volume by source category (most common)
- `collector` - Volume by collector
- `source` - Volume by source
- `sourceHost` - Volume by source host
- `sourceName` - Volume by source name
- `view` - Volume by partition/view

**Returns:** JSON with:
- Dimension value (e.g., sourceCategory, collector)
- Data tier (Continuous, Frequent, Infrequent, CSE)
- Events count
- GB ingested
- Credits consumed (if include_credits=True)
- Percentage change vs baseline (if include_timeshift=True)
- State flags: NEW, GONE, COLLECTING (if include_timeshift=True)

**Credit Rates (Standard Tiered):**
- Continuous: 20 credits/GB
- Frequent: 9 credits/GB
- Infrequent: 0.4 credits/GB
- CSE: 25 credits/GB
- Note: Flex customers use different rates

**Use Cases:**
- **Top consumers**: Find which source categories use most ingestion
- **Trend analysis**: Detect increases/decreases with timeshift comparison
- **Stopped collection**: Identify collectors that stopped sending data (state=GONE)
- **New sources**: Find newly added data sources (state=NEW)
- **Cost analysis**: Calculate credits consumed per dimension
- **Capacity planning**: Predict future ingestion needs

**Example Scenarios:**

1. **Find top 10 source categories by ingestion:**
   ```
   dimension="sourceCategory", from_time="-24h", sort_by="gbytes", limit=10
   ```

2. **Detect collectors with increasing ingestion (>50%):**
   ```
   dimension="collector", include_timeshift=True, timeshift_days=7, timeshift_periods=3
   Filter results where pct_increase_gb > 50
   ```

3. **Find stopped collectors:**
   ```
   dimension="collector", include_timeshift=True
   Filter results where state="GONE"
   ```

**Implementation Details:**
- Uses centralized query patterns from `query_patterns.py` module
- Timeshift pattern includes null-safe math and division-by-zero handling
- Ensures accurate detection of GONE/NEW/COLLECTING states even with missing historical data
- Query patterns are unit tested and shared across multiple tools

**Notes:**
- Queries the `sumologic_volume` index with dimension-specific source categories
- Uses `parse regex multi` for JSON array parsing
- Timeshift comparison helps detect anomalies and trends
- Infrequent tier data may take longer to appear in volume index
- Large accounts with 1000s of values may need shorter time ranges to avoid query memory issues

**Null Handling:**
When `include_timeshift=True`, the tool handles edge cases properly:
- **GONE detection**: Sources with no current data (null → 0) but with historical baseline are marked state="GONE"
- **NEW detection**: Sources with current data but no historical baseline (null → 0) are marked state="NEW"
- **Division by zero**: When baseline=0, percentage change is 100% if current>0, or 0% if current=0
- This ensures stopped/low collection scenarios are detected correctly

**Time Format Examples:**
- Relative: "-1h", "-24h", "-7d", "-30d"
- ISO: "2024-01-01T00:00:00Z"
- Epoch ms: "1704067200000"

**API Reference:** https://help.sumologic.com/docs/manage/ingestion-volume/data-volume-index/

---

### 41. `analyze_data_volume_grouped`
Advanced data volume analysis with cardinality reduction for large-scale environments (5000+ source categories).

**Parameters:**
- `dimension` (str, default='sourceCategory') - Metadata dimension
- `from_time` (str, default='-24h') - Start time
- `to_time` (str, default='now') - End time
- `time_zone` (str, default='UTC') - Timezone
- `value_filter` (str, default='*') - Filter pattern (e.g., '*prod*')
- `tier_filter` (str, default='*') - Data tier filter (Continuous, Frequent, Infrequent, CSE, Flex)
- `max_chars` (int, default=40) - Max characters for values (longer truncated with '...')
- `other_threshold_pct` (float, default=0.1) - Rollup threshold percentage (0.1 = 0.1%)
- `sort_by` (str, default='credits') - Sort field (credits, gbytes, events)
- `limit` (int, default=100) - Maximum results
- `instance` (str, default='default') - Instance name

**Cardinality Reduction Features:**

1. **Value Truncation:**
   - Long values shortened to `max_chars` with "..." suffix
   - Example: "kubernetes/prod/very/long/path/service" → "kubernetes/prod/very/long/path/se..."

2. **Small Value Rollup:**
   - Values < `other_threshold_pct` of total GB grouped as "other"
   - Shows count of rolled-up sources in `categories` field
   - Default 0.1% means anything < 0.1% rolls into "other"

**Returns:** JSON with:
- `dataTier` - Data tier name
- `dimension` - Dimension type (e.g., "sourcecategory")
- `value` - Dimension value (truncated or "other")
- `categories` - Count of original values in this entry
- `events` - Total events count
- `gbytes` - Total GB ingested
- `credits` - Total credits consumed
- `pct_GB` - Percentage of total GB
- `pct_cr` - Percentage of total credits
- `cr/gb` - Credits per GB ratio

**Use Cases:**
- **High-cardinality environments**: Effectively analyze 5000+ source categories
- **Executive reporting**: Focus on top contributors (>1%), hide noise
- **Cost optimization**: Identify major credit drivers
- **Tier analysis**: Filter to specific tiers (Flex, Infrequent, etc.)
- **Pattern analysis**: Filter by value patterns (*prod*, *k8s*, etc.)

**Example Scenarios:**

1. **Top Flex tier consumers (>1% each):**
   ```
   tier_filter="Flex", other_threshold_pct=1.0, sort_by="credits"
   ```

2. **Infrequent tier with short names:**
   ```
   tier_filter="Infrequent", max_chars=30, other_threshold_pct=0.5
   ```

3. **Production sources only:**
   ```
   value_filter="*prod*", other_threshold_pct=0.2
   ```

4. **Kubernetes sources, top 20:**
   ```
   value_filter="*k8s*", limit=20, other_threshold_pct=0.5
   ```

**Example Output:**
```json
{
  "dataTier": "Flex",
  "dimension": "sourcecategory",
  "value": "kubernetes/prod/dependency/operator/depe...",
  "categories": "1",
  "credits": "308.82458405569196",
  "events": "21091665",
  "gbytes": "15.441229202784598",
  "pct_GB": "28.820305167502596",
  "cr/gb": "20",
  "pct_cr": "27.90802384892889"
}
```

**Notes:**
- Designed for very large deployments (1000s of dimension values)
- The "other" entry aggregates all small contributors
- `categories` field shows how many sources rolled into each entry
- Uses optimized parse regex for better performance
- Adjust `other_threshold_pct` based on environment size (0.1%-1% typical)
- Results sorted descending by credits to show top cost drivers first

**Comparison with `analyze_data_volume`:**
- `analyze_data_volume`: Detailed view, all values, supports timeshift
- `analyze_data_volume_grouped`: High-level view, reduces cardinality, better for large environments

**API Reference:** https://help.sumologic.com/docs/manage/ingestion-volume/data-volume-index/

---

## Tool Categories Summary

| Category | Count | Tools |
|----------|-------|-------|
| **Search & Query** | 9 | Search logs, job management, query metrics, search audit, scan cost analysis, metadata exploration |
| **Query Examples** | 1 | Search 11,000+ queries from published apps |
| **Log Volume Analysis** | 2 | Raw log volume analysis with _size field, schema profiling with facets |
| **Content Library** | 7 | Folder access, path operations, content export with async jobs |
| **Content ID Utilities** | 3 | Hex/decimal conversion, web URL generation |
| **Field Management** | 3 | Custom fields, field extraction rules |
| **Collectors & Sources** | 2 | List collectors, get sources |
| **Users & Roles** | 2 | List users, list roles |
| **Dashboards & Monitors** | 2 | List dashboards, search monitors |
| **System** | 2 | List partitions, list instances |
| **Account Management** | 6 | Account status, usage forecast, usage report, estimated usage, data volume analysis |

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
- Export tools (`export_content`, `export_global_folder`, `export_admin_recommended_folder`, `export_installed_apps`, `export_usage_report`) use async job pattern
- Default timeout: 300 seconds (5 minutes)
- Default poll interval: 2 seconds (content exports) or 5 seconds (usage reports)
- Usage report downloads expire after 10 minutes

### Content Library Quirks
- **Personal folder**: Fast synchronous API, returns children directly
- **Global folder**: Async export, uses `data` array (NOT `children`)
- **Admin Recommended**: Async export, uses `children` array
- **isAdminMode flag**: Changes content scope/visibility

---

**Version:** 1.7
**Last Updated:** 2026-03-02
**Total Tools:** 40

---

## Query Patterns Library Reference

The `query_patterns.py` module provides reusable Sumo Logic query building blocks used across multiple MCP tools.

### ScopePattern

Build and analyze search scopes for optimal partition routing and query performance.

**Methods:**
- `build_scope(partition, metadata, keywords, indexed_fields, use_and)` - Construct complete scope
- `build_metadata_scope(source_category, collector, source, source_name, source_host)` - Simplified metadata scope
- `extract_scope_from_query(query)` - Parse scope from full query
- `analyze_scope(scope)` - Analyze and provide optimization recommendations

**Example:**
```python
from query_patterns import ScopePattern

# Build optimized scope
scope = ScopePattern.build_scope(
    partition='prod_logs',
    metadata={'_sourceCategory': 'prod/app'},
    keywords=['error', '5xx']
)
# Result: '_index=prod_logs AND _sourceCategory="prod/app" AND error AND 5xx'

# Analyze existing scope
analysis = ScopePattern.analyze_scope('error')
# Returns: {'has_partition': False, 'recommendations': ['Add _sourceCategory...']}
```

### LogDiscoveryPattern

Complete 3-phase log discovery workflow for users who don't know metadata, partitions, log structure, or query patterns.

**Phase 1: Metadata Discovery**
- `build_metadata_discovery_query(search_pattern, time_range, use_volume_index)` - Generate discovery queries
- Find source categories via data volume index (fast, no scan charge)
- Discover partitions, collectors, sources for known source category
- Search audit for queries by other users

**Phase 2: Log Structure Analysis** (template provided)
- Sample logs with/without auto-parse to identify fields
- Detect log format (JSON, syslog, custom)
- Distinguish indexed fields from search-time fields

**Phase 3: Use-Case Query Building**
- `build_usecase_query_recommendations(log_format, detected_fields, use_case, has_query_library)` - Get query recommendations
- Integrates with `search_query_examples` tool (11,000+ real queries)
- Returns query library searches based on use case and detected fields
- Provides common patterns for errors, performance, security use cases
- Field-specific query suggestions (status_code, response_time, user_id, etc.)
- Setup instructions if query library not available

**Complete Workflow:**
- `generate_complete_workflow(initial_hint, context, use_case)` - End-to-end discovery workflow

**Example - Phase 1:**
```python
from query_patterns import LogDiscoveryPattern

# Discover logs for 'cloudtrail' service
queries = LogDiscoveryPattern.build_metadata_discovery_query('cloudtrail')
# Returns: volume_query, metadata_query_template, search_audit_query
```

**Example - Phase 3:**
```python
# Get query recommendations for error use case
recommendations = LogDiscoveryPattern.build_usecase_query_recommendations(
    log_format='json',
    detected_fields=['status_code', 'user_id', 'response_time'],
    use_case='error',
    has_query_library=True
)

# Returns:
# - query_library_searches: [
#     {'tool': 'search_query_examples', 'parameters': {'query': 'error'}, ...},
#     {'tool': 'search_query_examples', 'parameters': {'keywords': 'status_code'}, ...}
#   ]
# - common_patterns: Generic error patterns
# - field_based_queries: Queries using status_code, response_time
# - setup_instructions: How to enable query library (if not available)
```

**Use Cases:**
- Developer knows service name but not _sourceCategory
- User doesn't know which partition/view logs are in
- Need to understand log structure and available fields
- Want to find relevant query examples for specific use case
- Building queries from scratch without prior Sumo experience

**Query Library Integration:**
- Phase 3 leverages `search_query_examples` tool for relevant patterns
- Extract `sumologic_query_examples.json.gz` to enable 11,000+ examples
- Automatic fallback with setup instructions if library unavailable

### TimeshiftPattern

Compare current data with historical baselines using `compare with timeshift` operator.

**Features:**
- Null-safe math for missing historical data
- Division-by-zero guards
- State detection: GONE (stopped), NEW (new source), COLLECTING (active)

**Example:**
```python
from query_patterns import TimeshiftPattern

# Add timeshift comparison
operators = TimeshiftPattern.compare_with_timeshift('gbytes', days=7, periods=3)
# Generates: compare operator, null guards, state detection, percentage calc
```

### NullSafeOperations

Null-safe mathematical operations for edge cases.

**Methods:**
- `safe_divide(numerator, denominator, result_field)` - Division with null/zero guards
- `coalesce(field, default_value)` - Convert nulls to defaults
- `percentage_change(current, baseline, result_field)` - Calculate % change safely

### AggregationPatterns

Common aggregation and sorting patterns.

**Methods:**
- `volume_by_dimension(dimension, include_tier)` - Standard volume aggregation
- `top_n(sort_field, limit, direction)` - Top N results
- `timeslice_aggregation(interval, fields, group_by)` - Time-series aggregations

### CreditCalculation

Sumo Logic credit rate calculations for cost analysis.

**Standard Rates (credits/GB):**
- Continuous: 20
- Frequent: 9
- Infrequent: 0.4
- CSE: 25

**Methods:**
- `add_credit_calculation(data_field, tier_field, credit_field, rates)` - Calculate credits

**Example:**
```python
from query_patterns import CreditCalculation

operators = CreditCalculation.add_credit_calculation()
# Generates tier-based credit calculation operators
```

### Integration Example

Combine multiple patterns for complex queries:

```python
from query_patterns import ScopePattern, AggregationPatterns, CreditCalculation, TimeshiftPattern

# Build complete volume analysis query
query_parts = []
query_parts.append(ScopePattern.build_metadata_scope(source_category='prod/*'))
query_parts.append(AggregationPatterns.volume_by_dimension('sourceCategory'))
query_parts.extend(CreditCalculation.add_credit_calculation())
query_parts.extend(TimeshiftPattern.compare_with_timeshift('gbytes', days=7, periods=3))
query_parts.append(AggregationPatterns.top_n('gbytes', limit=100))

query = '\n'.join(query_parts)
```

**Benefits:**
- Centralized, tested query logic
- Consistent null handling and edge case management
- Easy to maintain and extend
- Self-documenting with clear APIs

