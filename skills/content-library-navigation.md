# Skill: Navigate and Export Content Library

## Intent

Navigate the Sumo Logic content library to find, inspect, and export dashboards, searches, and folders. Generate shareable URLs for content items.

## Prerequisites

- Access to Sumo Logic content library
- Understanding of library structure (Personal, Global, Admin Recommended, Installed Apps)
- Basic knowledge of content types (Dashboard, Search, Folder)

## Context

**Use this skill when:**

- Looking for existing dashboards or searches
- Exporting content for backup or migration
- Generating shareable links to content
- Discovering pre-built app content
- Understanding folder organization

**Library Structure:**

```
/Library/
├── Personal/           # User's private content
├── Global/             # Organization-wide shared (uses 'data' not 'children')
├── Admin Recommended/  # Admin-curated content (uses 'children')
└── Installed Apps/     # Pre-built app content
```

## Approach

### Phase 1: Discover Content

#### Step 1.1: List Personal Content

Start with your personal folder to see what you've created.

**MCP Tool:** `get_personal_folder`

```json
{
  "include_children": true
}
```

**Returns:**

- Folder metadata
- Children array with your content
- Fast synchronous API (no async job)

#### Step 1.2: Explore Global Shared Content

Browse organization-wide shared content.

**MCP Tool:** `export_global_folder`

```json
{
  "is_admin_mode": false,
  "max_items": 50
}
```

**Important:** Global folder uses `data` array, NOT `children`.

**Use `max_items` for large folders:**

- Without limit: May return >1MB, all content
- With limit: Returns first N items, faster response
- Includes `_metadata` showing truncation info

#### Step 1.3: Check Admin Recommended

Find admin-curated best practices content.

**MCP Tool:** `export_admin_recommended_folder`

```json
{
  "is_admin_mode": false,
  "max_items": 50
}
```

**Important:** Uses `children` array (unlike Global).

#### Step 1.4: Discover Installed Apps

Find pre-built apps like AWS CloudTrail, Kubernetes, Apache.

**Quick List:**

```bash
MCP: list_installed_apps
  filter_name: "AWS"
```

Returns lightweight list of installed apps.

**Full Structure:**

```bash
MCP: export_installed_apps
  is_admin_mode: false
```

Returns complete app folder structure with dashboards and searches.

**Workflow:**

1. Use `list_installed_apps` to check if app exists
2. Use `export_installed_apps` to get full content
3. Navigate to specific dashboards/searches

### Phase 2: Navigate to Specific Content

#### Step 2.1: Navigate by Path

If you know the path:

**MCP Tool:** `get_content_by_path`

```json
{
  "content_path": "/Library/Users/user@company.com/MyDashboards/API Monitoring"
}
```

**Path Formats:**

- Personal: `/Library/Users/{email}/...`
- Global: `/Library/Global/...`
- Admin Recommended: `/Library/Admin Recommended/...`

#### Step 2.2: Navigate by ID

If you have content ID (hex format):

**MCP Tool:** `get_content_path_by_id`

```json
{
  "content_id": "00000000005E5403"
}
```

Returns full path and breadcrumb navigation.

#### Step 2.3: Browse Folder Hierarchy

Navigate folder by folder:

**MCP Tool:** `get_folder_by_id`

```json
{
  "folder_id": "00000000005E5403",
  "include_children": true
}
```

Returns immediate children (folders and content items).

### Phase 3: Search for Content

#### Step 3.1: Search Dashboards

Find dashboards by name or description:

**MCP Tool:** `get_sumo_dashboards`

```json
{
  "filter_name": "API",
  "mode": "allViewableByUser",
  "limit": 100
}
```

**Modes:**

- `allViewableByUser` - All dashboards you can view (default)
- `createdByUser` - Only your dashboards

**Pagination:**

```json
{
  "limit": 100,
  "token": null  // First page
}
```

Response includes `next` token for pagination. Pass as `token` parameter for next page.

**Filtering:**

- `filter_name` - Filter by title (substring match)
- `filter_description` - Filter by description
- `search_term` - Search across title and description

#### Step 3.2: Search Monitors

Find monitors by query:

**MCP Tool:** `search_sumo_monitors`

```json
{
  "query": "name:*api*",
  "limit": 100
}
```

**Query Syntax:**

- Simple text: `"error"` - Matches monitors containing 'error'
- Field search: `"name:*latency*"` - Field-specific search
- Status filter: `"monitorStatus:Critical"` - By status
- Creator filter: `"createdBy:USER_ID"` - By creator

### Phase 4: Export Content

#### Step 4.1: Export Dashboard or Search

Get complete content definition:

**MCP Tool:** `export_content`

```json
{
  "content_id": "00000000005E5403",
  "is_admin_mode": false,
  "max_wait_seconds": 300
}
```

**Returns:**

- Complete structure including:
  - Dashboard: All panels, queries, layouts, time ranges
  - Search: Query, time range, parsing logic
  - Folder: Children and metadata

**Use Cases:**

- Backup important content
- Migrate content between orgs
- Inspect query details in dashboards
- Understand panel configuration

**Async Operation:**

- Creates export job
- Polls for completion (default 300s max)
- Returns final result

### Phase 5: Generate Shareable URLs

#### Step 5.1: Content Web URL

Generate URL to open content in browser:

**MCP Tool:** `get_content_web_url`

```json
{
  "content_id": "00000000005E5403",
  "content_type": "Dashboard"
}
```

**Content ID Formats:**

- Accepts hex: `"00000000005E5403"`
- Accepts decimal: `"6181891"`
- Auto-detects format

**URL Formats:**

- Dashboards: `https://service.au.sumologic.com/dashboard/{id}`
- Library content: `https://service.au.sumologic.com/library/{id}`
- Custom subdomain: `https://mycompany.au.sumologic.com/...`

**Returns:**

```json
{
  "url": "https://service.au.sumologic.com/dashboard/abc123",
  "hex_id": "00000000005E5403",
  "decimal_id": "6181891",
  "content_type": "Dashboard"
}
```

#### Step 5.2: Search Query URL

Generate URL to open search with pre-filled query:

**MCP Tool:** `build_search_web_url`

```json
{
  "query": "_index=prod_logs error | count by service",
  "start_time": "-1h",
  "end_time": "-1s"
}
```

**Time Formats:**

- Relative: `"-1h"`, `"-24h"`, `"-7d"`
- ISO8601: `"2024-01-01T00:00:00"`
- Specific: `"now"`, `"-1s"`

**Use Cases:**

- Share searches in Slack/email
- Create bookmarks for common queries
- Generate links from automation
- Document queries in runbooks

## Query Patterns

### Content Discovery Pattern

```
1. List top-level folders (Personal, Global, Admin Recommended)
2. Browse children of interesting folders
3. Filter by content type or name
4. Export content for details
```

### Dashboard Search Pattern

```
1. Search dashboards by keyword
2. Apply mode filter (all vs created by me)
3. Paginate through results if >100
4. Get web URL for sharing
```

### App Discovery Pattern

```
1. List installed apps with filter
2. If app found, export full structure
3. Navigate to specific dashboards/searches
4. Export individual content items for queries
```

## Examples

### Example 1: Find and Share AWS CloudTrail Dashboard

**Step 1:** Check if AWS CloudTrail app is installed

```bash
MCP: list_installed_apps
  filter_name: "CloudTrail"
```

**Result:** AWS CloudTrail app found

**Step 2:** Export app structure

```bash
MCP: export_installed_apps
```

**Step 3:** Navigate structure to find dashboard

```json
{
  "name": "AWS CloudTrail",
  "children": [
    {
      "name": "CloudTrail - Overview",
      "contentType": "Dashboard",
      "id": "00000000ABC123"
    }
  ]
}
```

**Step 4:** Generate shareable URL

```bash
MCP: get_content_web_url
  content_id: "00000000ABC123"
  content_type: "Dashboard"
```

**Result:** `https://service.au.sumologic.com/dashboard/xyz789`

### Example 2: Find Your Dashboards Created Last Week

**Step 1:** List dashboards you created

```bash
MCP: get_sumo_dashboards
  mode: "createdByUser"
  limit: 100
```

**Step 2:** Filter results by creation date (client-side)
Parse `createdAt` field, filter to last 7 days

**Step 3:** Export specific dashboard

```bash
MCP: export_content
  content_id: "{dashboard_id}"
```

### Example 3: Backup All Personal Content

**Step 1:** Get personal folder

```bash
MCP: get_personal_folder
  include_children: true
```

**Step 2:** Iterate through children
For each content item:

- If type is Dashboard or Search, export it
- If type is Folder, recursively get folder children

**Step 3:** Export each item

```bash
MCP: export_content
  content_id: "{item_id}"
```

**Step 4:** Save exports to local files
Store JSON for backup or migration.

### Example 4: Create Search Link for Runbook

**Scenario:** Document emergency query in runbook.

**Query:**

```
_index=prod_logs _sourceCategory=prod/api error "status_code"="5"
| timeslice 5m
| count by _timeslice, service
| where _count > 100
```

**Generate URL:**

```bash
MCP: build_search_web_url
  query: "{query above}"
  start_time: "-1h"
  end_time: "-1s"
```

**Result:**

```
https://service.au.sumologic.com/log-search/create?query=...&startTime=-1h&endTime=-1s
```

**Add to runbook:**

```markdown
## High Error Rate Investigation

1. Open [error rate query](https://service.au...)
2. Check if specific service is affected
3. Correlate with deployment times
```

### Example 5: Paginate Through Large Dashboard List

**Step 1:** Get first page

```bash
MCP: get_sumo_dashboards
  limit: 100
  token: null
```

**Response:**

```json
{
  "dashboards": [...],
  "next": "pagination_token_abc123"
}
```

**Step 2:** Get next page

```bash
MCP: get_sumo_dashboards
  limit: 100
  token: "pagination_token_abc123"
```

**Step 3:** Repeat until `next` is absent (end of results)

## Common Pitfalls

### Pitfall 1: Confusing Global Folder Structure

**Problem:** Expecting `children` array in Global folder

**Solution:** Global folder uses `data` array, Admin Recommended uses `children`

### Pitfall 2: Large Folder Exports Timing Out

**Problem:** Exporting Global folder with 200+ items causes timeout or >1MB response

**Solution:** Use `max_items` parameter:

```json
{
  "max_items": 50
}
```

Returns first 50 items with `_metadata` indicating truncation.

### Pitfall 3: Wrong Content ID Format for URLs

**Problem:** Using hex ID when decimal expected

**Solution:** Use `get_content_web_url` which auto-detects format, or convert:

```bash
MCP: convert_content_id_hex_to_decimal
  hex_id: "00000000005E5403"
```

### Pitfall 4: Not Using Dashboard Filter for Large Orgs

**Problem:** Fetching all 500+ dashboards when looking for specific ones

**Solution:** Use `filter_name` or `search_term`:

```json
{
  "filter_name": "API",
  "limit": 20
}
```

### Pitfall 5: Exporting When List is Sufficient

**Problem:** Exporting full dashboard just to get name/description

**Solution:** Use `get_sumo_dashboards` for metadata, only export for full structure

## Content ID Utilities

### Convert Hex to Decimal

```bash
MCP: convert_content_id_hex_to_decimal
  hex_id: "00000000005E5403"
```

Returns: `6181891`

### Convert Decimal to Hex

```bash
MCP: convert_content_id_decimal_to_hex
  decimal_id: "6181891"
```

Returns: `00000000005E5403`

### When to Convert

- **Hex to Decimal:** For web URLs (UI uses decimal)
- **Decimal to Hex:** For API calls (API uses hex)
- **get_content_web_url:** Auto-converts, no manual conversion needed

## Best Practices

### Discovery

1. Start with `list_installed_apps` - check for pre-built content first
2. Use `max_items` for large folder exports to avoid timeouts
3. Use dashboard filters to narrow results before fetching all

### Navigation

1. Use `get_content_by_path` when you know the path
2. Use `get_folder_by_id` to navigate hierarchically
3. Leverage breadcrumbs from `get_content_path_by_id`

### Export

1. Export only what you need - full exports are async and slower
2. Use `is_admin_mode=true` only when necessary (shows more content but requires permissions)
3. Increase `max_wait_seconds` for very large content exports

### URLs

1. Use `get_content_web_url` for shareable links (handles dashboard vs library URLs)
2. Use `build_search_web_url` for query links in documentation
3. Configure `SUMO_SUBDOMAIN` in `.env` for custom subdomain URLs

### Performance

1. Dashboard pagination: Use `token` for >100 dashboards
2. Folder size: Use `max_items` for folders >100 items
3. Caching: Store exported content locally to avoid repeated async exports

## Related Skills

- [Log Discovery](./discovery-logs-without-metadata.md) - Find logs before creating searches
- [Search Optimization](./search-optimize-queries.md) - Optimize queries found in dashboards
- [Search Cost Analysis](./cost-analyze-search-costs.md) - Analyze dashboard query costs

## MCP Tools Used

- `get_personal_folder` - Access personal content (fast)
- `export_global_folder` - Browse global shared content (async)
- `export_admin_recommended_folder` - Browse admin content (async)
- `export_installed_apps` - Discover pre-built apps (async)
- `list_installed_apps` - Quick app availability check
- `get_content_by_path` - Navigate by path
- `get_content_path_by_id` - Get path from ID
- `get_folder_by_id` - Browse folder hierarchy
- `get_sumo_dashboards` - Search/list dashboards
- `search_sumo_monitors` - Search monitors
- `export_content` - Export full content structure (async)
- `get_content_web_url` - Generate shareable URLs
- `build_search_web_url` - Generate search query URLs
- `convert_content_id_hex_to_decimal` - ID conversion
- `convert_content_id_decimal_to_hex` - ID conversion

## API References

- [Content Management API](https://api.sumologic.com/docs/#tag/contentManagement)
- [Dashboard API](https://api.sumologic.com/docs/#tag/dashboardManagement)
- [Folder API](https://api.sumologic.com/docs/#tag/folderManagement)
- [App Catalog](https://www.sumologic.com/app-catalog)

---

**Version:** 1.0.0
**Domain:** Content Management
**Complexity:** Beginner to Intermediate
**Estimated Time:** 15-30 minutes to navigate and export content
