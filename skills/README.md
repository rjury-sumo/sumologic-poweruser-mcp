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

### Search & Query (`search-*.md`)
- Log search techniques
- Query optimization
- Metrics querying
- Search cost analysis

### Data Discovery (`discovery-*.md`)
- Finding logs without knowing metadata
- Schema profiling
- Partition discovery
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

| Skill | Category | Description |
|-------|----------|-------------|
| [Log Discovery](./discovery-logs-without-metadata.md) | Discovery | Find logs when you don't know metadata |
| [Search Cost Analysis](./cost-analyze-search-costs.md) | Cost | Analyze Flex/Infrequent tier search costs |
| [Data Volume Analysis](./cost-analyze-data-volume.md) | Cost | Track ingestion and identify cost drivers |
| [Query Optimization](./search-optimize-queries.md) | Search | Build efficient, cost-effective queries |
| [Audit User Activity](./audit-user-activity.md) | Audit | Track authentication and user actions |
| [Monitor System Health](./audit-system-health.md) | Audit | Monitor collectors and alerts |
| [Navigate Content Library](./content-library-navigation.md) | Content | Browse and export dashboards/searches |
| [Generate Web URLs](./content-generate-urls.md) | Content | Create shareable links to content |
| [Manage Collectors](./admin-collector-management.md) | Admin | List and inspect collectors/sources |
| [Field Extraction](./admin-field-extraction.md) | Admin | Work with custom fields and FERs |

## Maintenance

When adding new tools or capabilities to the MCP server:

1. **Update existing skills** if the tool enhances an existing capability
2. **Create new skills** for entirely new capabilities
3. **Add cross-references** between related skills
4. **Update the index** in this README

See [CLAUDE.md](../CLAUDE.md) for developer guidelines on keeping skills synchronized with code.

---

**Version:** 1.0.0
**Last Updated:** 2026-03-05
**Maintained by:** sumologic-python-mcp project
