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

- **Writing queries**: Complete 5-phase construction guide
- **Query optimization**: Performance and cost optimization with views
- **UI navigation**: Interactive investigation techniques
- Metrics querying
- Search cost analysis

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
- System health monitoring
- Compliance reporting

### Content Management (`content-*.md`)

- Library navigation
- Dashboard management
- Content export
- URL generation

### Administration (`admin-*.md`)

- Collector management
- User and role management
- Field extraction rules
- Partition configuration

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

| Skill | Category | Description | MCP Tools |
|-------|----------|-------------|-----------|
| [Log Discovery](./discovery-logs-without-metadata.md) | Discovery | Find logs when you don't know metadata | Yes |
| [Scheduled Views Discovery](./discovery-scheduled-views.md) | Discovery | Find and understand scheduled views | Yes |
| [Search Cost Analysis](./cost-analyze-search-costs.md) | Cost | Analyze Flex/Infrequent tier search costs | Yes |
| [Data Volume Analysis](./cost-analyze-data-volume.md) | Cost | Track ingestion and identify cost drivers | Yes |
| **[Writing Queries](./search-write-queries.md)** | **Search** | **Complete query construction guide (5 phases)** | **Yes** |
| [Query Optimization](./search-optimize-queries.md) | Search | Build efficient, cost-effective queries | Yes |
| [Optimize with Views](./search-optimize-with-views.md) | Search | Transform slow queries using scheduled views | Yes |
| **[UI Navigation](./ui-navigate-and-search.md)** | **Search** | **Interactive UI features for investigation** | **No** |
| [Audit User Activity](./audit-user-activity.md) | Audit | Track authentication and user actions | Yes |
| [Monitor System Health](./audit-system-health.md) | Audit | Monitor collectors and alerts | Yes |
| [Navigate Content Library](./content-library-navigation.md) | Content | Browse and export dashboards/searches | Yes |
| [Generate Web URLs](./content-generate-urls.md) | Content | Create shareable links to content | Yes |
| [Manage Collectors](./admin-collector-management.md) | Admin | List and inspect collectors/sources | Yes |
| [Field Extraction](./admin-field-extraction.md) | Admin | Work with custom fields and FERs | Yes |

## Maintenance

When adding new tools or capabilities to the MCP server:

1. **Update existing skills** if the tool enhances an existing capability
2. **Create new skills** for entirely new capabilities
3. **Add cross-references** between related skills
4. **Update the index** in this README

See [CLAUDE.md](../CLAUDE.md) for developer guidelines on keeping skills synchronized with code.

## Skill Summaries

### Core Query Skills

**[Writing Queries](./search-write-queries.md)** - Start here for query construction

- 5-phase pattern: Scope → Parse → Filter → Aggregate → Format
- Complete examples for each phase
- Dashboard panel patterns
- Integrates with MCP tools

**[UI Navigation](./ui-navigate-and-search.md)** - Interactive investigation

- Field Browser and Log Message Inspector
- Iterative workflow patterns
- Histogram and auto log level features
- UI-only (no MCP tools)

**[Query Optimization](./search-optimize-queries.md)** - Make queries faster and cheaper

- Scope optimization techniques
- Cost reduction strategies (10x-100x improvements)
- Anti-patterns to avoid
- Uses MCP tools for analysis

**[Optimize with Views](./search-optimize-with-views.md)** - Transform slow queries to use scheduled views

- Replace raw log queries with pre-aggregated view queries
- Achieve 10x-100x performance improvements
- Dramatically reduce scan costs (especially Flex/Infrequent)
- Patterns for direct replacement, re-aggregation, dimension collapsing

**Combined Workflow:**

1. Use **UI Navigation** to explore and build queries interactively
2. Apply **Writing Queries** patterns for proper structure
3. Optimize with **Query Optimization** techniques
4. If slow/expensive: Use **Optimize with Views** to find scheduled view alternatives
5. Execute via MCP tools for automation

### Discovery Skills

**[Scheduled Views Discovery](./discovery-scheduled-views.md)** - Find and understand scheduled views

- Inventory all available views in organization
- Understand view schemas and field availability
- Match views to use cases
- Query patterns for versioned views
- Cost optimization opportunities

---

**Version:** 1.1.0
**Last Updated:** 2026-03-06
**Maintained by:** sumologic-python-mcp project
