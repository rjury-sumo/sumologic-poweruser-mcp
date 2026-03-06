# Skill: Navigating Sumo Logic UI for Search and Investigation

## Intent

Master the Sumo Logic web UI features for efficient log search, investigation, and iterative analysis. This skill focuses on UI-specific techniques that complement programmatic search via MCP tools.

## Prerequisites

- Access to Sumo Logic web interface
- Basic understanding of log search concepts
- Familiarity with browser shortcuts (Cmd/Ctrl+K, Cmd/Ctrl+Click)

## Context

**Use this skill when:**

- Performing interactive log investigation via web UI
- Teaching users how to navigate Sumo Logic UI
- Building queries interactively before saving to dashboards
- Troubleshooting incidents via web interface

**Don't use this when:**

- Automating searches (use MCP tools instead)
- Building programmatic workflows (use API/MCP)
- Batch processing (use search jobs via API)

**Note:** This skill covers UI-only features. For programmatic search using MCP tools, see [Writing Queries](./search-write-queries.md).

## UI Basics

### New UI vs Old UI

Sumo Logic has two web interfaces:

**New UI (Recommended):**

- Modern interface with browser tabs
- Cmd/Ctrl+K for "Go To" quick navigation
- Cmd/Ctrl+Click to open in new tab
- Better performance and usability

**Old UI (Legacy):**

- Single-window interface with internal tabs
- Blue "+" button for new tabs
- Being phased out

**Switching between UIs:**
Settings → Preferences → UI Version

### Opening a New Search

**New UI:**

1. Press `Cmd+K` (Mac) or `Ctrl+K` (Windows)
2. Type "log" to find "Log Search"
3. Press Enter or Cmd/Ctrl+Click for new tab

**Old UI:**

1. Click blue "+" button at top
2. Select "Log Search"

### Search Modes

- **Advanced Mode** (Recommended): Full query syntax with pipe operators
- **Basic Mode**: Simplified UI with limited operators

Switch modes via toggle in search interface.

## Search Interface Features

### Time Range Picker

Located in top-right of search interface.

**Relative Time Ranges:**

- Last 15 minutes, 60 minutes, 24 hours, 7 days
- Custom relative: Type `-6h` for "last 6 hours"
  - `-15m` = last 15 minutes
  - `-1h` = last hour
  - `-7d` = last 7 days
  - `-1w` = last week

**Absolute Time:**

- Click calendar icon to select specific dates/times
- Use for compliance queries or specific incident windows

**Best Practice:**
Use relative time ranges when possible - they're easier to share and reuse.

### Query Editor

**Keyboard Shortcuts:**

- `Enter` or `Return` - Run search
- `Shift+Enter` - Add new line without running
- `Cmd+/` (Mac) or `Ctrl+/` (Windows) - Toggle comment

**Comments:**

```
// Single line comment

/*
Multi-line
comment
*/
```

**Auto-complete:**
Start typing operator names for suggestions (e.g., `| tim` suggests `timeslice`)

### Search Histogram

Visual timeline of log volume over time.

**Features:**

- Click histogram bar - Filter messages tab to that time range
- `Shift+Click` histogram selection - Open new search for that time range
- Color coding by auto-detected log level (ERROR, WARN, INFO, etc.)
- Click log level - Filter messages to that level

**Use Cases:**

- Identify when problem started
- Narrow investigation to specific time window
- Spot anomalies in log volume

## Messages Tab Features

### Field Browser (Left Panel)

Shows all fields available in current search scope.

**Features:**

1. **Search fields** - Type field name to filter field list
2. **Select field** - Check box to add to displayed columns
3. **Click field name** - See top values breakdown (first 100k results)
4. **Field actions:**
   - "Top Values" - Opens new categorical query
   - "Top Values Over Time" - Opens time series query

**Auto-Parsing:**
For JSON logs, all JSON keys appear as fields automatically.

**Field Types:**

- `_metadata` fields (e.g., `_sourceCategory`, `_sourceHost`)
- Auto-parsed fields (e.g., `%"errorCode"` for JSON)
- Admin-parsed fields (pre-extracted at ingestion)

### Message Display

Each message shows:

- Timestamp (`_messageTime`)
- Raw message (`_raw`)
- Metadata values below (category, host, index)

**JSON Message Features:**

- Formatted JSON display by default
- Right-click on JSON key/value for quick actions:
  - Copy Message
  - Parse the selected key
  - Filter by value
  - Add to search
- "View as Raw" - See unformatted JSON

**Message Actions:**

- Hover over message → Click menu (three dots) → Log Message Inspector
- Click metadata value → Add to scope filter
- Down-arrow on metadata → Search surrounding messages

### Log Message Inspector

Detailed view of single log event.

**Opening:**

1. Hover over any message
2. Click three-dot menu on right
3. Select "Log Message Inspector"

**Features:**

- Shows all fields for the event in single panel
- Select field row → Click ellipsis → "Filter Selected Value"
  - Adds filter to query for next iteration
- Copy field names and values
- Navigate between messages

**Use Case:**
Build queries iteratively by selecting fields and values to filter on.

## Iterative Investigation Workflow

### Pattern 1: Start Broad, Narrow Down

1. **Initial search** - Broad scope with keywords

   ```
   _sourceCategory=prod/app error
   ```

2. **Review messages** - Identify patterns in Field Browser

3. **Select interesting fields** - Check boxes for key fields (e.g., `errorCode`, `service`)

4. **Click field in Field Browser** - See top values breakdown

5. **Click value** - Opens new search filtered to that value

   ```
   _sourceCategory=prod/app error
   | json "errorCode" as error_code
   | where error_code = "AccessDenied"
   ```

6. **Repeat** - Continue narrowing scope

### Pattern 2: Explore Time Windows

1. **Run initial search** over large time range (e.g., -24h)

2. **Review histogram** - Identify spike or anomaly

3. **Click histogram bar** - Messages tab shows only that time window

4. **Shift+Click histogram** - Opens new search for that exact time range

5. **Investigate** - Focus on specific time window

### Pattern 3: Pivot to Aggregation

1. **Start with raw logs**

   ```
   _sourceCategory=prod/app error
   ```

2. **Parse fields** using Field Browser or manual parsing

3. **Click field in Field Browser**

4. **Click "Top Values"** - Opens new aggregate search

   ```
   _sourceCategory=prod/app error
   | json "errorCode" as error_code
   | count by error_code
   | sort _count desc
   ```

5. **Or click "Top Values Over Time"** - Opens time series

   ```
   _sourceCategory=prod/app error
   | json "errorCode" as error_code
   | timeslice 5m
   | count by _timeslice, error_code
   | transpose row _timeslice column error_code
   ```

### Pattern 4: Surrounding Messages

When you find an interesting event, view context:

1. **Find message of interest** in Messages tab

2. **Click down-arrow** on metadata value (host, category, etc.)

3. **Select "Search Surrounding Messages"**

4. **Opens new search** showing ±time range around that event

**Use Case:**
Find what happened before/after an error for root cause analysis.

## Aggregates Tab Features

### For Categorical Queries

When query has aggregation (count, sum, etc.) without timeslice:

**View Types:**

- **Table** - Sortable columns, export to CSV
- **Pie Chart** - Proportional distribution
- **Bar Chart** - Horizontal or vertical bars
- **Column Chart** - Vertical bars

**Actions:**

- Click column header - Sort by that column
- Move columns - Drag and drop headers
- Pin column - Right-click header → Pin
- Export - Download results as CSV
- Add to Dashboard - Save panel to dashboard

### For Time Series Queries

When query includes `timeslice`:

**Chart Types:**

- **Line Chart** - Continuous trends
- **Area Chart** - Filled area under line
- **Column Chart** - Discrete time buckets
- **Stacked Charts** - Multiple series stacked

**Display Options:**
Click "Display" tab below chart:

- **Display Type:** Normal, Stacked, Stacked 100%
- **Y-Axis:** Linear, Logarithmic
- **Legend:** Show/hide, position
- **Null value handling:** Zero, Null, Connect

**Use Cases:**

- Line/Area: Continuous metrics (CPU, memory, latency)
- Column: Discrete events (error counts, request counts)
- Stacked: Show composition (error types, status codes)

### Panel Customization

Before adding to dashboard:

1. **Set panel title** - Click "Untitled" to rename

2. **Choose chart type** - Select visualization

3. **Configure display** - Set stack type, colors, etc.

4. **Test time range** - Override dashboard time if needed

5. **Click "Add to Dashboard"** - Save panel

## Advanced UI Techniques

### Auto Log Level Detection

Sumo automatically detects log levels (ERROR, WARN, INFO, DEBUG).

**Features:**

- Histogram colored by log level
- Click level in legend → Filter messages
- `_logLevel` field available for queries

**Use Case:**
Quickly filter to ERROR logs without parsing:

```
_sourceCategory=prod/app
| where _logLevel = "ERROR"
```

### Search Shortcuts

**Right-click JSON field:**

- Parse field - Adds parse operator to query
- Filter by value - Adds where clause
- Add to search - Appends to scope

**Click metadata under message:**

- Adds metadata filter to current search (doesn't open new tab)
- Example: Clicking `_sourceCategory=prod/app` adds to scope

**Field Browser quick actions:**

- Top Values - Categorical breakdown
- Top Values Over Time - Time series chart

### Multi-Tab Investigation

**Workflow:**

1. Keep initial broad search in one tab
2. Open narrower searches in new tabs (Shift+Click histogram)
3. Compare results across tabs
4. Cmd/Ctrl+Click links to open in background tabs

**Use Case:**
Compare error rates across different services or time periods simultaneously.

### Dashboard Template Variables in UI

When viewing dashboards with filters (template variables):

**Syntax in queries:**

```
_sourceCategory=prod/{{service}}
```

**In Dashboard UI:**

- Filter input at top of dashboard
- Type value or select from dropdown
- All panels update dynamically

**Creating filters:**
Dashboard → Create new variable → Set name and type

## Common UI Workflows

### Workflow 1: Troubleshoot Application Error

1. **Open Log Search** (Cmd+K → "log")
2. **Start broad:**

   ```
   _sourceCategory=prod/app error exception
   ```

3. **Review histogram** - Identify when errors started
4. **Click spike** in histogram
5. **Review messages** - Identify error pattern
6. **Select fields** in Field Browser (errorCode, service, etc.)
7. **Click errorCode** → See breakdown
8. **Click specific error** → Opens filtered search
9. **Use Log Message Inspector** → Find additional context
10. **Create aggregate** → Count by service
11. **Save to dashboard** → For ongoing monitoring

### Workflow 2: Build Dashboard Panel

1. **Open Log Search**
2. **Determine query type:**
   - Categorical: Count/stats without time
   - Time Series: Include timeslice
3. **Build query** using iterative techniques
4. **Switch to Aggregates tab**
5. **Choose chart type** (pie, bar, line, etc.)
6. **Configure display** (stacked, colors, legend)
7. **Set panel title**
8. **Click "Add to Dashboard"**
9. **Select target dashboard**

### Workflow 3: Root Cause Analysis

1. **Start with alert** or symptom query
2. **Identify timeframe** from histogram
3. **Shift+Click histogram** → Open time-focused search
4. **Review Field Browser** → Find relevant fields
5. **Click fields** → Identify anomalies in top values
6. **Use surrounding messages** → Find events before/after
7. **Cross-reference:**
   - Open new tab for related logs (e.g., load balancer)
   - Compare timelines across services
8. **Iterate** until root cause identified

## UI Pitfalls to Avoid

### Pitfall 1: Not Using Field Browser

**Problem:** Manually typing field names, making errors
**Solution:** Use Field Browser to see available fields and auto-populate queries

### Pitfall 2: Running Queries Over Too-Long Time Ranges

**Problem:** Slow queries, timeouts, high scan costs
**Solution:**

- Start with -15m or -1h for exploration
- Expand time range only after narrowing scope
- Use histogram to identify relevant time windows

### Pitfall 3: Not Leveraging Auto Log Level

**Problem:** Complex parsing to extract log level
**Solution:** Use `_logLevel` field or histogram filtering

### Pitfall 4: Ignoring Histogram Signals

**Problem:** Missing obvious patterns visible in histogram
**Solution:**

- Always review histogram before diving into messages
- Look for spikes, gaps, or pattern changes
- Use histogram to narrow time range

### Pitfall 5: Not Using Multi-Tab Workflow

**Problem:** Losing context when pivoting to new searches
**Solution:**

- Keep initial search tab open
- Use Shift+Click or Cmd/Ctrl+Click for new tabs
- Compare results across tabs

### Pitfall 6: Forgetting to Save Searches

**Problem:** Rebuilding complex queries repeatedly
**Solution:**

- Save searches to personal folder
- Add to dashboards for reuse
- Share with team via content library

## Relationship to MCP Tools

**UI is best for:**

- Interactive exploration and investigation
- Building queries iteratively
- Learning log structure and fields
- Visualizing results in real-time

**MCP tools are best for:**

- Automated searches and monitoring
- Programmatic workflows
- Batch processing
- Integration with external systems

**Combined approach:**

1. Use UI to build and test query
2. Save query to content library
3. Reference saved search in MCP tool workflows
4. Or: Export dashboard and automate updates via MCP

**Example:**
Build query in UI:

```
_sourceCategory=prod/app error
| json "errorCode" as error_code
| count by error_code
```

Execute via MCP tool:

```json
{
  "tool": "search_sumo_logs",
  "query": "_sourceCategory=prod/app error | json \"errorCode\" as error_code | count by error_code",
  "hours_back": 1
}
```

## Related Skills

- [Writing Queries](./search-write-queries.md) - Query construction patterns (works with UI and MCP)
- [Query Optimization](./search-optimize-queries.md) - Make queries faster
- [Content Library Navigation](./content-library-navigation.md) - Save and organize searches
- [Search Cost Analysis](./cost-analyze-search-costs.md) - Understand query costs

## UI References

- [Sumo Logic UI Overview](https://help.sumologic.com/docs/get-started/sumo-logic-ui/)
- [Search Page Features](https://help.sumologic.com/docs/search/get-started-with-search/search-page/)
- [Field Browser](https://help.sumologic.com/docs/search/get-started-with-search/search-page/field-browser/)
- [Log Message Inspector](https://help.sumologic.com/docs/search/get-started-with-search/search-page/log-message-inspector/)
- [View JSON Logs](https://help.sumologic.com/docs/search/get-started-with-search/search-basics/view-search-results-json-logs/)
- [Search Surrounding Messages](https://help.sumologic.com/docs/search/get-started-with-search/search-basics/search-surrounding-messages/)
- [Auto Log Level](https://help.sumologic.com/docs/search/get-started-with-search/search-page/log-level/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-06
**MCP Tools:** None (UI-only skill)
