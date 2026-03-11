# Skill: Sumo Logic Dashboards — Overview and Design Patterns

## Intent

Design effective Sumo Logic dashboards by selecting the right dashboard type for the use case, structuring queries correctly for panels, and applying value-driven design patterns across the software management lifecycle.

## Prerequisites

- Ability to write Sumo Logic log and/or metric queries (see `search-log-search-basics`)
- Understanding of aggregation: categorical vs. time series
- Access to a Sumo Logic instance with relevant log data

## Context

**Use this skill when:**

- Creating a new dashboard from scratch
- Choosing which type of dashboard to build for a specific use case
- Structuring queries to work correctly in different panel types
- Presenting business or operational metrics to stakeholders
- Consolidating multiple data sources into a single view

**Don't use this when:**

- You need raw log exploration (use the Search UI directly)
- Real-time alerting is the goal (use Monitors instead)

---

## Dashboard Types by Use Case

Sumo Logic dashboards serve four primary patterns. Choosing the right type at the design stage guides which panels, queries, and interactions to build.

### 1. History / Trend Dashboard

**Purpose:** Show trends and history for key indicators over time.

**Characteristics:**
- Mix of key performance indicators and "golden signals" (latency, traffic, errors, saturation)
- May include environment/service filters
- Includes time-series panels comparing current vs. historical periods
- Often includes `compare with timeshift` for context

**Example uses:** Daily operations overview, SLO reporting, release impact tracking.

### 2. Snapshot / Status Dashboard

**Purpose:** Show current state and real-time status.

**Characteristics:**
- Current counts, rates, and statuses at a glance
- Honeycomb or colour-coded panels to show health states
- Single-value panels for key metrics
- Frequently refreshed or live

**Example uses:** On-call operations wall display, production health check.

### 3. Investigation / Workflow Dashboard

**Purpose:** Enable troubleshooting by providing quick access to key data sets and drill-down paths.

**Characteristics:**
- Filter template variables (e.g., environment, service, host) to scope the view
- Click-through links to related dashboards or Entity Explorer
- Text panels explaining how to use the dashboard
- Linked dashboards for drilling from overview to detail

**Example uses:** Incident investigation, on-call runbooks, security triage.

### 4. Business Process Dashboard

**Purpose:** Consolidate multiple sources into a single view of a business process or transaction.

**Characteristics:**
- Unifies log and metric data from multiple technologies
- Shows end-to-end view of a business service or application stack
- Suitable for business stakeholders, not just engineers
- May include revenue, transaction success rates, customer impact metrics

**Example uses:** Order processing health, payment gateway monitoring, user journey analysis.

---

## Dashboard Value Across the Lifecycle

Dashboard needs change across the software lifecycle:

| Phase | Primary Value |
|---|---|
| **Develop** | Rapid feedback on test results, build success, code quality |
| **Test** | Validation of expected behaviour, performance baseline |
| **Deploy** | Release comparison, canary metrics, rollback triggers |
| **Operate/Maintain** | Ongoing health, SLO tracking, capacity planning |

Design dashboards with the **primary consumer and lifecycle phase** in mind — an operations dashboard is very different from a release comparison dashboard.

---

## Business Process / Technology Domain Patterns

### Business Process Dashboard

Consolidates signals from multiple technologies to show the health of a single business operation.

- Aggregate revenue, transaction counts, error rates across frontend + backend + database
- Useful for communicating business impact during incidents
- Example: "Checkout flow" showing order intake rate, payment success %, fulfilment queue depth

### Technology Domain Dashboard

Focused on a single technology or platform (e.g., AWS CloudTrail, Kubernetes, Apache).

- Can be filtered by environment variables (account, region, namespace)
- Provides rapid domain-specific troubleshooting
- Pre-built app catalog provides immediate time-to-value for most common technologies (AWS, GCP, K8s, Apache, etc.)

---

## The App Catalog

Sumo Logic provides **pre-built apps** with dashboards, saved searches, and content for hundreds of common data sources (AWS, GCP, Azure, Kubernetes, Apache, etc.).

- Access via the App Catalog tab in the UI or at https://help.sumologic.com/docs/integrations/
- Pre-configured queries and dashboards provide immediate time to value
- Installed apps appear under the **Installed Apps** folder in the Library
- Use pre-built apps as a starting point and customise for your environment

---

## Content Library

All dashboards, saved searches, and installed apps are stored in the **Content Library**:

- **Personal** — private content, default save location
- **All** — shared content visible to all users
- **Admin Recommended** — curated, high-value content promoted by administrators
- **Installed Apps** — managed versions of official Sumo Logic apps

**Best practice:** Save high-value dashboards to a shared folder or Admin Recommended to maximise value for your organisation. Create a clear folder hierarchy for curated shared content.

---

## Dashboard Features

### Template Variable Filters

Add filter variables (e.g., `environment`, `service`, `region`) as template variables at the top of the dashboard. Users can change these values to filter all panels simultaneously.

```
// Panel query using a filter variable:
_sourceCategory=prod/app {{environment}} error
| count by service
```

#### Advanced Template Variable Usage

Template variables can go anywhere in a query that produces valid query syntax — not just in `where matches "{{var}}"` clauses.

```
// Use as a keyword expression in scope (very fast — bloom filter):
_sourceCategory=prod/app {{service_name}}

// Variable timeslice interval:
| timeslice {{interval}}
| count by _timeslice

// Switch the breakdown column dynamically:
| count by {{breakdown_field}}

// Same variable more than once in a query:
_sourceCategory=prod/{{env}} "{{env}}"
| count by host
```

**Default values:** Use `*` as default for keyword-based variables (matches all). Use `// ignoreme` as a comment-style default to effectively disable the filter when nothing is selected.

**Note:** In search templates (not dashboards), use `{{{var}}}` (triple braces) for advanced use cases involving punctuation.

#### Template Variable Source Types

Each dashboard template variable has a `sourceDefinition` that controls where its dropdown values come from:

| Source Type | How Values Are Populated | Best For |
|---|---|---|
| `LogQueryVariableSourceDefinition` | Live query against log data — specify `query` and `field` | Dynamic values that change (services, hosts, namespaces) |
| `CsvVariableSourceDefinition` | Static comma-separated list | Fixed option sets (timeslice intervals like `5m,15m,1h`; environments like `prod,staging,dev`) |
| `cat`-based lookup source | Query from a lookup table: `cat /path/lookup \| count by field \| sort field asc` | Managed lists maintained by admins (account IDs, environment groups) |

**Example static CSV variable** (for a timeslice interval picker):
```
Variable name: interval
Default: 5m
Values: 5m,15m,1h,6h,1d
```

Used in panel queries as: `| timeslice {{interval}} | count by _timeslice`

**Example dynamic query variable** (for a namespace picker from live data):
```
Variable name: namespace
Query: _sourceCategory=prod/k8s | json "namespace" | count by namespace | sort namespace asc
Field: namespace
```

**Tip:** Use `allowMultiSelect: false` for variables used in scopes (keywords/metadata). Multi-select only works reliably in `where matches` clauses. Use `includeAllOption: true` to add an "All" entry that passes `*`.

#### Suggestion Lists for Dashboard Variables

Dashboard variable dropdowns can be populated from:
- A **static list** of values (e.g., `prod`, `staging`, `dev`)
- A **dynamic query** against live data, a scheduled view, or a lookup table

This makes it easy for users to select valid values rather than typing free text — especially valuable for high-cardinality dimensions like account IDs, namespace names, or region codes.

#### Template Variables in Panel Titles and Series Aliases

`{{var}}` syntax works beyond query strings:
- **Panel titles**: `Error Rate — {{service}}` — title updates when the user changes the variable
- **Series alias overrides** (in the Overrides tab): `{{_collector}} - {{_devname}}` — used in metrics panels to give each time series a meaningful label combining two dimensions

#### Dashboard URL Deep Linking

You can share a dashboard with specific template variable values pre-filled using URL parameters:

```
https://service.sumologic.com/ui/#/dashboardv2/?variables=errorCode:AccessDenied;keywords:s3
```

Format: `?variables=name:value;name2:value2` (semicolon-separated, no spaces). This enables linking from alerts, Slack messages, or runbooks directly to a pre-scoped dashboard view.

---

### Time Range

Dashboards have a global time range control. Individual panels can override with a fixed time range if needed.

### Drill-Down Workflows

- **Entity Explorer**: available from many chart panels — opens related logs, metrics, or traces for the selected entity
- **Linked Dashboards**: configure panels to navigate to another dashboard when clicked, passing context as template variable values. To set up: build template variables in target dashboard → create panels that group by the variable name → enable "linked dashboards" on the panel → users click a series to open the linked dashboard with that value in context
- **Clickable URLs**: use `tourl`, `urlencode`, and `concat` operators to build clickable links in table panels that open external systems (Jira, PagerDuty), other Sumo dashboards, or new search windows with time range pre-filled (see `dashboards-panel-types` for query patterns)

### Text Panels

Add Markdown text panels to provide:
- Instructions for how to use the dashboard
- Context about what the data represents
- Links to runbooks or related resources

Text panels transform an investigation dashboard into a true guided workflow.

---

## MCP Tools Used

- `get_sumo_dashboards` — List and search existing dashboards
- `export_content` — Export a dashboard's full definition
- `get_content_by_path` — Navigate to a dashboard by library path
- `get_content_web_url` — Generate a shareable URL for a dashboard

## Related Skills

- [Dashboard Panel Types](./dashboards-panel-types.md)
- [Log Search Basics](./search-log-search-basics.md)
- [Alerting — Monitors](./alerting-monitors.md)

## API References

- [Dashboards API](https://api.sumologic.com/docs/#tag/dashboardManagement)
- [App Catalog](https://help.sumologic.com/docs/integrations/)
- [Content Library](https://help.sumologic.com/docs/get-started/library/)

---

**Version:** 1.2.0
**Last Updated:** 2026-03-12
**Source:** SumoLogic Logs Basics Training (August 2025); Sumo Logic Advanced Topics Workshop (2025/2026); Sumo Logic Dashboard Cookbooks (2026)
