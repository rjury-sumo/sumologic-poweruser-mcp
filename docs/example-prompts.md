# Sumo Logic MCP Server - Example Prompts

This document provides example prompts for using the Sumo Logic MCP tools effectively. Each section includes prompts that demonstrate common use cases and best practices.

---

## Search & Query Tools

### Basic Log Search

**Prompt:** "Search logs from the last hour where _sourceCategory contains 'prod/app' and show me error messages"

**What it does:** Uses `search_sumo_logs` to find recent errors in production application logs.

---

**Prompt:** "Find all 5xx errors in the last 24 hours from my Apache logs and count them by status code"

**What it does:** Aggregates HTTP server errors by status code using log search with aggregation.

---

**Prompt:** "Search CloudTrail logs for failed login attempts in the last 6 hours"

**What it does:** Searches AWS CloudTrail logs filtering by event type and status.

---

### Search Performance & Cost Analysis

**Prompt:** "Show me which users are running the most expensive searches in the last week"

**What it does:** Uses `run_search_audit_query` to analyze search usage by user, sorted by data scanned.

---

**Prompt:** "What searches scanned the most data on our Flex tier yesterday?"

**What it does:** Uses `analyze_search_scan_cost` with `breakdown_type='metering'` to find high-cost Flex searches.

---

**Prompt:** "Find all scheduled dashboard searches that scan more than 100GB and show me their scan costs"

**What it does:** Combines `run_search_audit_query` with filters for scheduled searches and high scan volumes.

---

**Prompt:** "Analyze my search costs grouped by user and query for the last 7 days, focusing on Infrequent tier"

**What it does:** Uses `analyze_search_scan_cost` with `analytics_tier_filter='*infrequent*'` and `group_by='user_query'`.

---

### Log Discovery & Exploration

**Prompt:** "I'm getting CloudTrail logs but don't know which partitions they're in. Help me find them."

**What it does:** Uses `explore_log_metadata` with scope containing 'cloudtrail' to discover partitions and source categories.

---

**Prompt:** "What source categories and partitions are available in my Sumo Logic instance?"

**What it does:** Uses `explore_log_metadata` with broad scope to map the log landscape.

---

**Prompt:** "I need to find logs containing 'kubernetes pod failed' but don't know the source category"

**What it does:** Multi-step discovery using `explore_log_metadata` and keyword search to locate relevant logs.

---

## Audit Tools

### User Activity Tracking

**Prompt:** "Show me all login attempts by <john@example.com> in the last 7 days"

**What it does:** Uses `search_audit_events` filtering by `operator_email` and `event_name='UserLogin*'`.

---

**Prompt:** "Who created or modified dashboards in the last 24 hours?"

**What it does:** Uses `search_audit_events` with `source_category='dashboards'` and event filters for create/update.

---

**Prompt:** "Find all failed login attempts in the last week"

**What it does:** Uses `search_audit_events` with `event_name='UserLoginFailure'`.

---

### System Health Monitoring

**Prompt:** "Show me all collectors that went unhealthy in the last 24 hours"

**What it does:** Uses `search_system_events` with `use_case='collector_source_health'`.

---

**Prompt:** "Which monitors are alerting most frequently this week?"

**What it does:** Uses `search_system_events` with `use_case='monitor_alerts'` to identify noisy monitors.

---

**Prompt:** "Show me the timeline of alert state changes for my critical monitors"

**What it does:** Uses `search_system_events` with `use_case='monitor_alert_timeline'`.

---

### Legacy Audit

**Prompt:** "Find all scheduled search alert triggers in the last 48 hours"

**What it does:** Uses `search_legacy_audit` with `use_case='scheduled_search_triggers'`.

---

## Query Examples & Learning

**Prompt:** "Find example queries for analyzing Apache 4xx errors"

**What it does:** Uses `search_query_examples` with `query='apache 4xx errors'`.

---

**Prompt:** "Show me Kubernetes queries for troubleshooting unschedulable pods"

**What it does:** Uses `search_query_examples` with `app_name='Kubernetes'` and `keywords='unschedulable pods'`.

---

**Prompt:** "I need examples of log queries that use the timeslice operator"

**What it does:** Uses `search_query_examples` with `keywords='timeslice'`.

---

**Prompt:** "Find security-related queries for AWS CloudTrail"

**What it does:** Uses `search_query_examples` with `app_name='AWS'`, `keywords='CloudTrail'`, `use_case='security'`.

---

## Content Library Navigation

### Finding Content

**Prompt:** "Show me what's in my personal folder"

**What it does:** Uses `get_personal_folder` to list your personal library content.

---

**Prompt:** "List all installed apps in my Sumo Logic instance"

**What it does:** Uses `list_installed_apps` or `export_installed_apps` to discover pre-built apps.

---

**Prompt:** "Is there an AWS CloudTrail app already installed?"

**What it does:** Uses `list_installed_apps` with `filter_name='CloudTrail'`.

---

**Prompt:** "Show me the Global folder content but limit to first 50 items"

**What it does:** Uses `export_global_folder` with `max_items=50` for large folder preview.

---

### Exporting Content

**Prompt:** "Export the complete definition of dashboard ID 00000000005E5403"

**What it does:** Uses `export_content` to get full dashboard JSON including panels and queries.

---

**Prompt:** "Get the search query definition for content at /Library/Users/user@example.com/MySearch"

**What it does:** Uses `get_content_by_path` then `export_content` to retrieve complete search definition.

---

### Generating URLs

**Prompt:** "Generate a shareable URL for dashboard 00000000005E5403"

**What it does:** Uses `get_content_web_url` to create a browser-friendly URL.

---

**Prompt:** "Create a URL for this query: _sourceCategory=prod/app error | count by host"

**What it does:** Uses `build_search_web_url` to generate a pre-filled search URL.

---

**Prompt:** "I need a link to open this search for the last 7 days: _index=cloudtrail eventName=AssumeRole"

**What it does:** Uses `build_search_web_url` with `start_time='-7d'`.

---

## Log Volume Analysis

**Prompt:** "What are my top 10 source categories by ingestion volume in the last 24 hours?"

**What it does:** Uses `analyze_data_volume` with `dimension='sourceCategory'`, `limit=10`, `sort_by='gbytes'`.

---

**Prompt:** "Show me which CloudTrail event types are consuming the most storage"

**What it does:** Uses `analyze_log_volume` with `scope='_sourceCategory=*cloudtrail*'` and `aggregate_by=['eventname']`.

---

**Prompt:** "What fields are available in my Apache access logs and which would be good for volume analysis?"

**What it does:** Uses `profile_log_schema` with `scope='_sourceCategory=apache*'` to discover schema.

---

**Prompt:** "Find collectors that stopped sending data in the last week"

**What it does:** Uses `analyze_data_volume` with `dimension='collector'`, `include_timeshift=True`, filtering for state='GONE'.

---

**Prompt:** "Which production source categories have increased ingestion by more than 50% compared to last week?"

**What it does:** Uses `analyze_data_volume` with `value_filter='*prod*'`, `include_timeshift=True`, `timeshift_days=7`.

---

## Dashboards & Monitors

**Prompt:** "List all dashboards I created"

**What it does:** Uses `get_sumo_dashboards` with `mode='createdByUser'`.

---

**Prompt:** "Find dashboards with 'AWS' in the title"

**What it does:** Uses `get_sumo_dashboards` with `filter_name='AWS'`.

---

**Prompt:** "Show me all monitors that have 'error' in the name"

**What it does:** Uses `search_sumo_monitors` with `query='name:*error*'`.

---

**Prompt:** "Which monitors are currently in Critical state?"

**What it does:** Uses `search_sumo_monitors` with `query='monitorStatus:Critical'`.

---

## Field Management & Configuration

**Prompt:** "What custom fields are configured in my organization?"

**What it does:** Uses `list_custom_fields` to show all custom field definitions.

---

**Prompt:** "Show me all field extraction rules and their scope"

**What it does:** Uses `list_field_extraction_rules` to list FERs with scopes and parse expressions.

---

**Prompt:** "What fields are being extracted for _sourceCategory=prod/app logs?"

**What it does:** Uses `list_field_extraction_rules` then filters by scope.

---

## Collectors & Sources

**Prompt:** "List all collectors in my environment"

**What it does:** Uses `get_sumo_collectors`.

---

**Prompt:** "Show me only active collectors with 'prod' in the name"

**What it does:** Uses `get_sumo_collectors` with `filter_name='prod'` and `filter_alive=True`.

---

**Prompt:** "What sources are configured on collector ID 123456?"

**What it does:** Uses `get_sumo_sources` with `collector_id=123456`.

---

## Partitions & Views

**Prompt:** "What partitions exist in my Sumo Logic instance?"

**What it does:** Uses `get_sumo_partitions` to list all partitions with retention and routing info.

---

**Prompt:** "Show me all scheduled views and their schemas"

**What it does:** Uses `list_scheduled_views` to discover pre-aggregated views with field definitions.

---

**Prompt:** "Find scheduled views that might help accelerate my Apache dashboard queries"

**What it does:** Uses `list_scheduled_views` then searches for views with 'apache' in the index name.

---

## Account Management & Usage

**Prompt:** "What's my current subscription plan and credit usage?"

**What it does:** Uses `get_account_status` to show plan type, credits, and subscription dates.

---

**Prompt:** "Forecast my usage for the next 30 days"

**What it does:** Uses `get_usage_forecast` with `number_of_days=30`.

---

**Prompt:** "How much data would this query scan: _sourceCategory=prod/app error"

**What it does:** Uses `get_estimated_log_search_usage` to estimate scan volume before running expensive query.

---

**Prompt:** "Export my usage report for January 2024 grouped by day"

**What it does:** Uses `export_usage_report` with `start_date='2024-01-01'`, `end_date='2024-01-31'`, `group_by='day'`.

---

## Advanced Multi-Tool Workflows

### Complete Log Discovery Workflow

**Prompt:** "I'm seeing errors for a service called 'payment-api' but don't know where the logs are or how to query them. Help me find and analyze these logs."

**What it does:**

1. Uses `explore_log_metadata` to find partitions/source categories
2. Uses `search_sumo_logs` to sample logs
3. Uses `profile_log_schema` to discover fields
4. Uses `search_query_examples` to find relevant query patterns
5. Builds optimized queries for the use case

---

### Cost Optimization Analysis

**Prompt:** "I need to reduce my Flex tier search costs. Show me which users and queries are most expensive, and recommend optimizations."

**What it does:**

1. Uses `analyze_search_scan_cost` with `breakdown_type='metering'` and `group_by='user_query'`
2. Uses `get_estimated_log_search_usage` to test query optimizations
3. Uses `list_scheduled_views` to find pre-aggregated alternatives
4. Provides recommendations for scope optimization

---

### Capacity Planning

**Prompt:** "Analyze my data ingestion trends over the last 30 days and predict future capacity needs"

**What it does:**

1. Uses `analyze_data_volume` with `include_timeshift=True` to show trends
2. Uses `get_usage_forecast` to project future usage
3. Uses `analyze_data_volume_grouped` to identify top growth drivers
4. Provides capacity planning recommendations

---

### Security Audit

**Prompt:** "Generate a security audit report showing all failed login attempts, content changes by admins, and monitor status changes in the last 7 days"

**What it does:**

1. Uses `search_audit_events` for failed logins
2. Uses `search_audit_events` for content changes by specific admin users
3. Uses `search_system_events` for monitor alerts
4. Compiles comprehensive security report

---

### Dashboard Performance Investigation

**Prompt:** "My dashboard is loading slowly. Analyze the queries it's using and find ways to speed them up."

**What it does:**

1. Uses `export_content` to get dashboard definition and extract queries
2. Uses `run_search_audit_query` to analyze query performance history
3. Uses `get_estimated_log_search_usage` to check scan volumes
4. Uses `list_scheduled_views` to find view alternatives
5. Provides optimization recommendations with estimated improvements

---

### App Discovery & Installation Planning

**Prompt:** "I just started collecting Kubernetes logs. What pre-built apps are available, and what dashboards do they have?"

**What it does:**

1. Uses `list_installed_apps` with `filter_name='Kubernetes'` to check installation
2. Uses `export_installed_apps` to explore app structure
3. Uses `export_content` to preview dashboard definitions
4. Provides app catalog link if not installed

---

## Skills Library Access

**Prompt:** "Show me the best practices for writing Sumo Logic queries"

**What it does:** Uses `get_skill` with `skill_name='search-write-queries'` to load the 5-phase query construction pattern.

---

**Prompt:** "How do I optimize slow and expensive queries?"

**What it does:** Uses `get_skill` with `skill_name='search-optimize-queries'` for optimization techniques.

---

**Prompt:** "What's the workflow for finding logs when I don't know the metadata?"

**What it does:** Uses `get_skill` with `skill_name='discovery-logs-without-metadata'` for multi-phase discovery approach.

---

**Prompt:** "How do scheduled views work and when should I use them?"

**What it does:** Uses `get_skill` with `skill_name='search-optimize-with-views'` for view optimization patterns.

---

## Tips for Effective Prompts

### Be Specific About Time Ranges

- ✅ "Show me errors in the last 2 hours"
- ✅ "Analyze data volume from January 1-7, 2024"
- ❌ "Show me recent errors"

### Include Relevant Filters

- ✅ "Find failed logins for user <john@example.com>"
- ✅ "List collectors with 'prod' in the name that are active"
- ❌ "Show me collectors"

### Specify What You Want to See

- ✅ "Show me the top 10 source categories by GB ingested"
- ✅ "Export the dashboard and show me the query definitions"
- ❌ "Get some dashboard info"

### Combine Goals Clearly

- ✅ "Find CloudTrail logs, show me the fields available, and give me example queries for security use cases"
- ❌ "Help with CloudTrail"

### Use Natural Language

- ✅ "Which queries scanned the most data yesterday?"
- ✅ "Are there any collectors that stopped working?"
- You don't need to memorize tool names or parameters

---

## Common Use Case Scenarios

### "I'm New to Sumo Logic"

1. "What instances are configured?" → `list_sumo_instances`
2. "Show me my personal folder" → `get_personal_folder`
3. "What apps are installed?" → `list_installed_apps`
4. "Find example queries for [my technology]" → `search_query_examples`

### "I Need to Find Logs"

1. "I'm looking for logs from [service/app]" → Multi-step discovery workflow
2. "What partitions exist?" → `get_sumo_partitions`
3. "What source categories are available?" → `explore_log_metadata`

### "I Need to Reduce Costs"

1. "Show me expensive searches" → `analyze_search_scan_cost`
2. "What scheduled views are available?" → `list_scheduled_views`
3. "Estimate query cost before running" → `get_estimated_log_search_usage`
4. "What's driving my ingestion costs?" → `analyze_data_volume_grouped`

### "I Need to Troubleshoot"

1. "Why is my dashboard slow?" → Export dashboard, analyze queries
2. "Are my collectors healthy?" → `search_system_events` with health use case
3. "Which monitors are noisy?" → `search_system_events` with monitor use case
4. "Who changed this content?" → `search_audit_events`

### "I Need to Build Queries"

1. "Show me best practices" → `get_skill` for search-write-queries
2. "Find similar queries" → `search_query_examples`
3. "What fields are available?" → `profile_log_schema`
4. "Give me examples for [use case]" → `search_query_examples` with filters

---

**Version:** 1.0
**Last Updated:** 2026-03-06
**Related:** [MCP Tools Reference](mcp-tools-reference.md), [Skills Library](../skills/README.md)
