# Sumo Logic Skills Library

This directory contains portable skill definitions that encapsulate the knowledge and patterns developed in the sumologic-python-mcp project. These skills can be used with Claude Code, other LLMs, or agentic solutions.

## What are Skills?

Skills are reusable knowledge artifacts that describe **how to accomplish specific tasks** in the Sumo Logic platform. They capture:

- **Intent**: What the skill achieves
- **Context**: When to use it
- **Approach**: Step-by-step methodology
- **Patterns**: Query patterns, API calls, best practices
- **Examples**: Real-world scenarios
- **Pitfalls**: Common mistakes to avoid

## Skills Organization

Skills are organized by domain:

### Search & Query (`search-*.md`, `ui-*.md`)

- **Log search basics**: Core pipeline, metadata fields, parse operators
- **Writing queries**: Complete 5-phase construction guide
- **Query optimization**: Performance and cost optimization (SKEFE framework, bloom filter, query rewriting)
- **Scheduled views**: Admin view design and creation patterns
- **Optimize with views**: Transform slow queries using scheduled views
- **Indexes and partitions**: Data tiers, finding data locations
- **Mo Copilot**: AI-assisted query generation
- **UI navigation**: Interactive investigation techniques

### Alerting (`alerting-*.md`)

- Monitor types and design (Logs, Metrics, SLO)
- Time compare and anomaly detection
- Alert grouping and notification variables

### Dashboards (`dashboards-*.md`)

- Dashboard design patterns (four types)
- Panel types and query patterns (categorical, time series, honeycomb, map)

### Data Collection (`data-collection-*.md`)

- 7 collection patterns and selection guide
- Source category naming conventions

### Data Discovery (`discovery-*.md`)

- Finding logs without knowing metadata
- Schema profiling
- Partition discovery
- Scheduled view inventory
- Field exploration

### Cost Analysis (`cost-*.md`)

- Search scan cost analysis
- Data volume analysis
- Credit calculation
- Usage forecasting

### Audit & Compliance (`audit-*.md`)

- Searching audit indexes
- User activity tracking
- System health monitoring + admin alert templates
- Compliance reporting

### Content Management (`content-*.md`)

- Library navigation
- Dashboard management
- Content export
- URL generation

### Administration (`admin-*.md`)

- Collector management
- User and role management
- Field extraction rules (FER patterns, histogram/stripe)
- Partition design (7 rules, scan reduction analysis)
- Admin alerting foundation (ingest, rate limiting, scan cost alerts)
- RBAC and security architecture (SAML, capabilities, search scope, service accounts, user lifecycle)

### Data Collection (`data-collection-*.md`)

- 7 collection patterns and selection guide
- Source category naming conventions and logging standards
- Processing rules (include/exclude/mask/archive)
- Technical best practices (timestamps, multiline, HTTPS headers)
- Kubernetes native collection

## Using Skills

### With Claude Code

Skills can be referenced in Claude Code via the [Skills documentation](https://code.claude.com/docs/en/skills).

### With Other LLMs

Copy the relevant skill markdown file and provide it as context to your LLM.

### In Automation

Extract the patterns and examples from skills to build automated workflows.

## Skill Template

Each skill follows this structure:

```markdown
# Skill: [Name]

## Intent
What this skill accomplishes

## Prerequisites
- Knowledge requirements
- Access requirements
- Configuration needs

## Context
When to use this skill vs alternatives

## Approach
Step-by-step methodology

## Query Patterns
Reusable query building blocks

## Examples
Real-world scenarios with solutions

## Common Pitfalls
Mistakes to avoid

## Related Skills
Links to complementary skills

## API References
Links to official documentation
```

## Skill Index

### Meta-Skills (Start Here)

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| **[Consulting Guide — Virtual TAE](./consulting-guide.md)** | **Meta** | **Architecture framework, question taxonomy, trade-off tables, TAE consulting approach** | **Yes** |

### Search & Query

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| **[Log Search Basics](./search-log-search-basics.md)** | **Search** | **Core pipeline, metadata fields, parse operators, cardinality reduction** | **No** |
| **[Writing Queries](./search-write-queries.md)** | **Search** | **Complete query construction guide (5 phases)** | **Yes** |
| [Query Optimization](./search-optimize-queries.md) | Search | SKEFE framework, bloom filter, query rewriting, search audit | Yes |
| **[Result Size Optimization](./search-result-size-optimization.md)** | **Search** | **Managing API limits (1MB), cardinality reduction, limit/topk patterns, "others" grouping** | **Yes** |
| **[Subquery Patterns](./search-subquery.md)** | **Search** | **compose/keywords, sneaky save, cat filters, aggregation-as-transaction** | **No** |
| [Scheduled Views — Admin Design](./search-scheduled-views.md) | Search | View patterns, creation, multi-layer architecture | Yes |
| [Optimize with Views — User Guide](./search-optimize-with-views.md) | Search | Transform slow queries using scheduled views | Yes |
| [Indexes and Partitions](./search-indexes-partitions.md) | Search | Data tiers, finding which partition holds your data | No |
| [Mo AI Copilot](./search-copilot.md) | Search | Natural language query generation tips | No |
| **[UI Navigation](./ui-navigate-and-search.md)** | **Search** | **Interactive UI features for investigation** | **No** |

### Alerting & Dashboards

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Monitors](./alerting-monitors.md) | Alerting | Monitor types, detection methods, alert grouping | Yes |
| [Time Compare & Anomaly](./alerting-time-compare-anomaly.md) | Alerting | Dynamic threshold alerting, anomaly vs outlier | Yes |
| [Dashboard Design](./dashboards-overview.md) | Dashboards | Four dashboard types, App Catalog, template variables, linked dashboards | Yes |
| **[Panel Types & Patterns](./dashboards-panel-types.md)** | **Dashboards** | **Categorical, time series, honeycomb, heatmap, box plot, sankey, tracing panels, mixed queries, overrides, JSON config, timeless dashboards** | **No** |

### Data Collection

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Collection Patterns](./data-collection-patterns.md) | Collection | 7 patterns, selection guide, source category naming | Yes |

### Ingest Health

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| **[Ingest Lag Diagnosis](./data-ingest-lag-diagnosis.md)** | **Ingest** | **Detect/triage lag and timestamp parsing issues via _receipttime vs _messagetime** | **Yes** |

### Discovery

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Log Discovery](./discovery-logs-without-metadata.md) | Discovery | Find logs when you don't know metadata | Yes |
| [Scheduled Views Discovery](./discovery-scheduled-views.md) | Discovery | Find and understand scheduled views | Yes |

### Cost Analysis

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Search Cost Analysis](./cost-analyze-search-costs.md) | Cost | Analyze Flex/Infrequent tier search costs | Yes |
| [Data Volume Analysis](./cost-analyze-data-volume.md) | Cost | Track ingestion and identify cost drivers | Yes |

### Audit & Compliance

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Audit User Activity](./audit-user-activity.md) | Audit | Track authentication and user actions | Yes |
| [Monitor System Health](./audit-system-health.md) | Audit | Collector health + admin alert templates | Yes |

### Content Management

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Navigate Content Library](./content-library-navigation.md) | Content | Browse and export dashboards/searches | Yes |
| [Generate Web URLs](./content-generate-urls.md) | Content | Create shareable links to content | Yes |

### Administration

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Manage Collectors](./admin-collector-management.md) | Admin | List and inspect collectors/sources | Yes |
| [Field Extraction](./admin-field-extraction.md) | Admin | Work with custom fields and FERs (legacy) | Yes |
| **[Field Extraction Rules](./admin-field-extraction-rules.md)** | **Admin** | **FER patterns, histogram/stripe case study (342x speedup)** | **Yes** |
| **[Partition Design](./admin-partition-design.md)** | **Admin** | **7 rules, scan reduction analysis, CSE/Flex considerations** | **Yes** |
| **[Admin Alerting & Monitoring](./admin-alerting-and-monitoring.md)** | **Admin** | **5 alert templates: ingest, collection, rate limit, scan cost, health; governance checklist** | **Yes** |
| **[RBAC & Security Architecture](./admin-rbac-security.md)** | **Admin** | **SAML/SSO, role design, search scope, service accounts, user lifecycle** | **Yes** |

### Data Collection

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| **[Collection Patterns](./data-collection-patterns.md)** | **Collection** | **7 patterns, logging standards, processing rules, technical best practices** | **Yes** |

## Maintenance

When adding new tools or capabilities to the MCP server:

1. **Update existing skills** if the tool enhances an existing capability
2. **Create new skills** for entirely new capabilities
3. **Add cross-references** between related skills
4. **Update the index** in this README

See [CLAUDE.md](../CLAUDE.md) for developer guidelines on keeping skills synchronized with code.

## Skill Summaries

### Entry Point

**[Consulting Guide — Virtual TAE](./consulting-guide.md)** - Start here for advice, design, and architecture questions

- Question taxonomy: maps 10+ common question types to the right skill(s)
- Four-layer architecture framework (Collection → Partitions → Acceleration → Monitoring)
- Key trade-off tables: monitors vs scheduled search, anomaly vs outlier, Continuous vs Infrequent, partition vs no partition
- Decision frameworks for: alerting setup, data collection, cost reduction, partition design
- MCP tools for context gathering before advising
- First steps checklist for new deployments

### Core Query Skills

**[Log Search Basics](./search-log-search-basics.md)** - Start here for query fundamentals

- Five-phase pipeline: Scope → Parse → Filter → Aggregate → Format
- Metadata fields: `_sourceCategory`, `_index`/`_view`, `_collector`, `_source`, `_sourceHost`
- Parse operators: `parse`, `parse regex`, `json`, `nodrop`
- Useful for onboarding and reference

**[Writing Queries](./search-write-queries.md)** - Complete query construction guide

- 5-phase pattern with examples for each phase
- Dashboard panel patterns
- Integrates with MCP tools

**[UI Navigation](./ui-navigate-and-search.md)** - Interactive investigation

- Field Browser and Log Message Inspector
- Iterative workflow patterns
- Histogram and auto log level features
- UI-only (no MCP tools)

**[Query Optimization](./search-optimize-queries.md)** - Make queries faster and cheaper

- SKEFE framework (SourceCategory, Keywords, Extracted Fields, Filter Early)
- Platform engine optimisations: bloom filter tokenisation, query rewriting, push-down, pushdown hack
- Anti-patterns to avoid; search audit measurement queries
- 10x–100x improvement potential

**[Result Size Optimization](./search-result-size-optimization.md)** - Manage API limits and token costs

- 1MB API response limit management for Claude and MCP integrations
- 7 reduction strategies: top-N, topk, limit on scope, "others" grouping, substring truncation, time sampling, metadata pre-filtering
- Cardinality reduction patterns with two-level aggregation
- Decision tree for choosing right strategy
- Performance benchmarks: limit on line 1 = 20x faster, 100x less scan
- MCP tool integration best practices

**[Optimize with Views — User Guide](./search-optimize-with-views.md)** - Transform slow queries to use scheduled views

- Replace raw log queries with pre-aggregated view queries
- 10x–100x performance improvements, dramatic scan cost reduction
- Patterns: direct replacement, re-aggregation, dimension collapsing, weighted averages
- Admin reference: view design patterns and multi-layer architecture

**[Scheduled Views — Admin Design](./search-scheduled-views.md)** - Admin view creation guide

- "Base Camp" mental model for multi-layer views
- Pattern 1: Aggregate reporting (apache_status example)
- Pattern 2: Caching heavy compute (threat intel + geoip)
- Multi-layer architecture (1m → 1h → 1d)

**[Subquery Patterns](./search-subquery.md)** - Correlate data across sources

- `compose` vs `compose keywords` — how results are passed to parent
- Search expression syntax (before `|`) vs where-clause syntax — performance trade-off
- Subquery with `cat` — lookup table as flexible dashboard filter
- Sneaky subquery save — cache enrichment data for lookup in parent (v1 lookups only)
- Aggregation-as-transaction — scale-friendly alternative to `transactionize`/`join`

**Combined Query Workflow:**

1. Use **UI Navigation** to explore and build queries interactively
2. Apply **Log Search Basics** and **Writing Queries** for proper structure
3. Use **Subquery Patterns** for cross-source correlation
4. Optimize with **Query Optimization** techniques (SKEFE + platform features)
5. If slow/expensive: Use **Optimize with Views** to find scheduled view alternatives
6. If admin: Design new views using **Scheduled Views — Admin Design**
7. Execute via MCP tools for automation

### Alerting Skills

**[Monitors](./alerting-monitors.md)** - Build production-grade alerting

- Monitor types: Logs, Metrics, SLO
- Detection: Static, Anomaly, Outlier
- Alert grouping, `{{ResultsJson.field}}` notification variables
- Alert List and Alert Response Page

**[Time Compare & Anomaly](./alerting-time-compare-anomaly.md)** - Dynamic threshold alerting

- `compare with timeshift` patterns for weekly-cyclic traffic
- Anomaly vs Outlier: when to use each
- Per-entity comparison; dashboard time compare panels

### Dashboard Skills

**[Dashboard Design](./dashboards-overview.md)** - Four dashboard types

- History, Snapshot, Investigation, Business dashboards
- App Catalog, Content Library, template variables, drill-down features
- Advanced template variables (keywords, timeslice, column switching, multi-use)
- Suggestion lists from queries/views/lookup tables
- Linked dashboards with context-passing via template variables

**[Panel Types & Patterns](./dashboards-panel-types.md)** - Panel implementation guide

- Categorical (pie/bar/table — no timeslice needed)
- Time series (requires `timeslice` + `transpose` for multi-series)
- Transpose without timeslice — high-density grouped stacked bar
- Single value, honeycomb, map (`geoip`), text panels
- Heatmap, Bubble/Scatter panel types
- Timeless dashboards with `cat` (state table pattern)
- Clickable URL columns (`tourl`, `urlencode`, `concat`)
- Panel overrides (color, dual-axis, mixed chart types)
- JSON panel editing — advanced config options

### Admin Skills

**[Partition Design](./admin-partition-design.md)** - Seven rules of good partition design

- Consistent metadata field across all partitions (enables query rewriting)
- Use-case grouping, simple names, keep default partition < 10% of ingest
- Scan reduction analysis: 5x–1100x improvement possible
- CSE/Flex partition considerations

**[Field Extraction Rules](./admin-field-extraction-rules.md)** - FER patterns and case studies

- Pattern 1: Speed — pre-parse JSON fields (5–10x faster)
- Pattern 2: Convenience — pre-parse complex formats (Apache, IIS)
- Pattern 3: Routing — compute tag fields for partition routing
- Histogram/stripe case study: 342x speedup on numeric `where` comparisons

**[Admin Alerting & Monitoring](./admin-alerting-and-monitoring.md)** - Operational alerting foundation

- Enable audit policies (audit index, data volume index, search audit)
- Alert 1: Ingest spike/drop (time compare 7d 3 avg, credits-based)
- Alert 2: Collection stop (GONE/COLLECTING state detection)
- Alert 3: Rate limiting (`_index=sumologic_audit "rate limit"`)
- Alert 4: High infrequent scan credits
- Alert 5: Unhealthy collection events (system events index)
- Data volume scheduled view for large organisations

### Discovery Skills

**[Scheduled Views Discovery](./discovery-scheduled-views.md)** - Find and understand scheduled views

- Inventory all available views with `list_scheduled_views`
- Understand view schemas (`reduceOnlyFields`, `indexedFields`)
- Match views to use cases; query versioned views with wildcards

---

**Version:** 2.4.0
**Last Updated:** 2026-03-12
**Maintained by:** sumologic-python-mcp project

**Changelog v2.0:**

- Added 12 new skills from Sumo Logic training materials (August 2025 + February 2025)
- New skills: log-search-basics, indexes-partitions, copilot, scheduled-views (admin), alerting-monitors, alerting-time-compare-anomaly, dashboards-overview, dashboards-panel-types, data-collection-patterns, admin-partition-design, admin-field-extraction-rules, admin-alerting-and-monitoring
- Enhanced search-optimize-queries.md: added Platform Engine Optimisations + Search Audit sections (v2.1)
- Enhanced search-optimize-with-views.md: added Admin Reference view architecture patterns
- Enhanced audit-system-health.md: added admin audit policy setup + 5 alert templates (v1.1)
- Sources: SumoLogic Logs Basics Training (August 2025); Sumo Logic Architecture For Log Search Performance (February 2025); Admin Indexes, Apps and Alerts Playbook (Sumo Logic Customer Success)

**Changelog v2.1:**

- Added `consulting-guide.md` — virtual TAE meta-skill with question taxonomy, four-layer architecture framework, and trade-off tables
- Updated CLAUDE.md Skills Reference with all 22 skills and trigger conditions
- Updated `get_skill` MCP tool description with all skills and trigger phrases

**Changelog v2.2:**

- Incorporated CIP Onboarding Sessions I & II playbook content
- Updated `consulting-guide.md` (v1.1): Focus Check, Customer Maturity Stages, RBAC section, deployment checklist
- Updated `data-collection-patterns.md` (v1.1): Logging Standards, Processing Rules, HTTPS headers, Kubernetes native collection
- Updated `alerting-monitors.md` (v1.1): SLOs section
- Updated `admin-alerting-and-monitoring.md` (v1.1): Admin Setup Checklist / governance
- Updated `search-log-search-basics.md` (v1.1): Three Phases, Advanced Operators, Ingest Lag Detection
- New: `admin-rbac-security.md` (v1.0) — SAML, RBAC architecture, service accounts, user lifecycle

**Changelog v2.3:**

- Incorporated CIP Subquery Secrets Playbook and Sumo Logic Advanced Topics Workshop
- New: `search-subquery.md` (v1.0) — comprehensive subquery skill: compose/keywords, search vs where syntax, cat filters, sneaky subquery save, aggregation-as-transaction pattern
- Updated `dashboards-panel-types.md` (v1.1): heatmap, bubble/scatter, transpose without timeslice, timeless dashboards, clickable URLs, emoji bars, panel overrides, JSON editing
- Updated `dashboards-overview.md` (v1.1): advanced template variables, suggestion lists, linked dashboards detail
- Updated `search-log-search-basics.md` (v1.2): expanded LogReduce/LogCompare, logreduce field=, logreduce optimize, cardinality reduction patterns, outlier operator
- Sources: CIP Subquery Secrets Playbook; Sumo Logic Advanced Topics Workshop (2025/2026)

**Changelog v2.4:**

- Incorporated Sumo Logic Dashboard Cookbooks I–IV (Categorical/Honeycomb, Time Series, Advanced Analytics, Advanced Techniques)
- Updated `dashboards-panel-types.md` (v1.2): box plot (`boxAndWhisker`) with pct() query pattern, sankey/transaction flow panel, distributed tracing panels (TracesListPanel, ServiceMapPanel, `_trace_spans` span analytics), mixed logs+metrics panels with override JSON, text panel background color patterns, detailed SVP/HoneyComb/table conditional formatting JSON, per-panel query properties (outputCardinalityLimit, parseMode, timeSource)
- Updated `dashboards-overview.md` (v1.2): template variable sourceDefinition types (LogQuery, CSV, cat-based lookup), dashboard URL deep linking format, `{{var}}` in panel titles and series alias overrides
- Updated `search-log-search-basics.md` (v1.3): smooth operator with sort-first requirement, predict with AR/linear model detail, outlier configurable parameters, multiple pct() percentiles in one call, count_distinct, geo average workaround for live dashboard 1000-group limit
- Sources: Sumo Logic Dashboard Cookbooks I–IV (2026)
