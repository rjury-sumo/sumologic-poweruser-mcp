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

### Time Range

Dashboards have a global time range control. Individual panels can override with a fixed time range if needed.

### Drill-Down Workflows

- **Entity Explorer**: available from many chart panels — opens related logs, metrics, or traces for the selected entity
- **Linked Dashboards**: configure panels to navigate to another dashboard when clicked, passing context (e.g., service name)
- **Clickable URLs**: add URL columns in table panels to link to external systems (Jira, PagerDuty, etc.)

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

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** SumoLogic Logs Basics Training (August 2025)
