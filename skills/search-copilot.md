# Skill: Using Sumo Logic Mo AI Copilot

## Intent

Use Sumo Logic's Mo AI Copilot to generate and refine log search queries using natural language, accelerating investigation workflows and lowering the barrier for users unfamiliar with the Sumo Logic query language.

## Prerequisites

- Access to a Sumo Logic instance with Copilot enabled
- A starting source category or index to give Copilot context
- Log data that is either JSON-structured or has a Field Extraction Rule (FER) applied

## Context

**Use this skill when:**

- You are new to Sumo Logic and want to get started quickly
- You know what you want to find but don't know the exact query syntax
- You want Copilot to suggest next steps during an investigation
- Working with well-structured JSON logs or logs with FERs

**Don't use this when:**

- Your logs are highly unstructured and have no FERs — Copilot will produce less reliable results
- You need to write precise, performance-optimised production queries (review and tune Copilot output manually)
- You require a specific parsing pattern Copilot doesn't know

---

## What is Mo Copilot?

Sumo Logic's **Mo Copilot** is an AI-powered search assistant integrated into the log search UI. It allows users to:

- Ask questions in natural language and get back Sumo Logic query language queries
- Get contextual query suggestions based on current search context
- Accelerate incident resolution by surfacing relevant searches faster
- Remove the barrier of learning a new query language for new users

---

## How to Use Copilot Effectively

### Step 1: Start with a Specific Scope

Copilot works best when you give it a starting context. Begin by setting a `_sourceCategory` or `_index` in the search bar before invoking Copilot.

```
// Before asking Copilot, set scope in the search bar:
_sourceCategory=aws/cloudtrail

// Or:
_index=prod_logs _sourceCategory=prod/app
```

### Step 2: Ask Natural Language Questions

Type your question or intent in plain English. Copilot will generate a query that you can run or refine.

**Example prompts:**

```
"Calculate 95th percentile latency by service and API."
"Count logs by action, url, user. Sort the results."
"Show me the top 10 error codes in the last hour."
"Find all AccessDenied errors by IAM user."
"How many 5xx errors are there per minute?"
```

### Step 3: Use the Suggestions Panel

Copilot's right-side suggestions panel offers contextual next steps based on:
- The current query you're running
- Fields that are present in the result set
- Common follow-up investigation patterns

Always review the suggestions — they often surface useful queries you might not have thought to write.

### Step 4: Review and Refine the Output

Copilot generates queries, but you should always review them before using them in production dashboards or monitors:

- Check that the `_sourceCategory` scope is correct
- Verify field names match what's in your logs
- Add `nodrop` to JSON extractions for optional fields
- Validate performance characteristics (see `search-performance-best-practices`)

---

## Copilot Tips for Best Results

| Tip | Detail |
|---|---|
| Use JSON logs or FER-indexed logs | Copilot works best when fields are well-defined. Auto-parsed JSON or fields created by Field Extraction Rules give Copilot the schema it needs to generate accurate queries. |
| Be specific in your prompt | Vague prompts like "show me errors" produce generic queries. Specific prompts like "count 5xx HTTP errors by URL and group by 15-minute intervals" produce much better output. |
| Start with a scope | Always set `_sourceCategory` or `_index` first so Copilot is grounded in a specific data set. |
| Iterate | Treat Copilot output as a first draft. Edit the query, run it, and ask Copilot for further refinements. |
| Check suggestions panel | The right-side suggestions panel often has useful investigative follow-ups that save time. |

---

## Example Workflow: Investigating Errors with Copilot

1. Set scope in search bar: `_sourceCategory=prod/app`
2. Ask Copilot: "Show me error rate over time by service"
3. Copilot generates a timeslice + count query
4. Run the query and review the histogram
5. See a spike — ask Copilot: "Which error types caused the spike at 14:00?"
6. Copilot generates a breakdown query scoped to that time window
7. Identify root cause and save the investigation queries to your personal library

---

## Limitations

- Copilot is **not a replacement** for understanding the query language — queries should be reviewed and understood before use in production
- Performance characteristics of Copilot-generated queries vary; always check scope and add performance optimisations (keywords, `_index`) as needed
- Copilot may not know about custom Field Extraction Rules or specific partition names in your organisation — you may need to correct these manually
- Complex multi-stage queries with lookups, subqueries, or transactions may require manual refinement

---

## Related Skills

- [Log Search Basics](./search-log-search-basics.md)
- [Search Performance Best Practices](./search-performance-best-practices.md)

## API References

- [Sumo Logic Copilot Documentation](https://help.sumologic.com/docs/search/copilot/)
- [Getting Started with Search](https://help.sumologic.com/docs/search/get-started-with-search/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** SumoLogic Logs Basics Training (August 2025)
