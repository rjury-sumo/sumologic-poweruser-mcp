# Skill: Sumo Logic Subquery Patterns

## Intent

Use subqueries to correlate data across two log sources, pass dynamic filter lists between queries, cache enrichment lookups, and solve multi-state transaction problems that aggregation or join operators can't handle at scale.

## Prerequisites

- Comfortable writing Sumo Logic aggregate queries (see `search-log-search-basics`)
- Understanding of the `count by`, `compose`, and `lookup` operators
- Familiarity with the search pipeline (scope → parse → filter → aggregate)

## Context

**Use this skill when:**

- You need to filter one log source based on results from another (e.g., malicious IPs found in security logs → filter web access logs)
- You have two log sources that share a common identifier (A has X+Y, B has Y+Z — use Y as the link)
- You want to use a lookup table as a dynamic parameter source for a dashboard query
- You need to cache expensive enrichment (threatip, geoip) for use in the same query

**Don't use this when:**

- A simple `where` clause or metadata scope filter is sufficient
- You need very high-cardinality correlation — use the **aggregation-as-transaction** pattern instead (memory-safe, scales larger)
- You need a SQL-style full join with all rows from both sides

---

## How Subquery Works

A subquery is a **child query** embedded inside a **parent query**. The child runs first and its output is used to filter the parent.

```
<parent scope>
| where [subquery: <child query> | compose <field>]
```

Or in search syntax (before the first pipe):

```
<parent scope> [subquery: <child query> | compose <field> keywords]
| rest of parent query...
```

**Execution order:**
1. Child query runs first and produces its results
2. Results are passed to the parent via `compose` as a filter expression
3. Parent query runs with that filter applied

---

## The `compose` and `compose keywords` Operators

`compose` is the bridge between child and parent. It converts a table of results into a filter expression.

| Suffix | What it returns | How used in parent |
|---|---|---|
| `\| count by ip \| compose ip` | `(ip="1.2.3.4" OR ip="5.6.7.8" OR ...)` | `where` clause subquery; or search syntax if field is indexed |
| `\| count by ip \| compose ip keywords` | `("1.2.3.4" OR "5.6.7.8" OR ...)` | Search syntax (before first `\|`) only — very fast, uses bloom filter |

**Rule:** Use `compose keywords` when the field values are plain text that can be matched as keywords in the raw log. Use `compose field` when you need to match a parsed field in a `where` clause.

---

## Syntax Pattern 1: Search Expression (Before the Pipe)

Filter the parent scope **before any parsing**. This is the fastest pattern because it applies the bloom filter at the scan phase.

```
// Find web access logs for IPs that appeared in threat intelligence
_sourceCategory=prod/web/access
[subquery:
  _sourceCategory=security/threat
  | json "ip_address" as ip
  | count by ip
  | compose ip keywords
]
| parse "* - - [*] \"* * *\" * *" as src_ip, time, method, url, protocol, status, bytes
| count by src_ip, url
```

**Requirements for search expression syntax:**
- Use `compose <field> keywords` — returns bare keyword values
- The field values must appear as raw text in the parent logs

---

## Syntax Pattern 2: Where Clause (After the Pipe)

Filter inside a `where` clause. More flexible but slower because it applies after parsing.

```
// Find CloudTrail events for users who had failed logins
_sourceCategory=aws/cloudtrail
| json "userIdentity.userName" as user_name
| where user_name in [subquery:
    _sourceCategory=auth/login failure
    | json "username" as user_name
    | count by user_name
    | compose user_name
  ]
| count by user_name, eventName
```

**When to use where-clause subquery:**
- The filter field is **not** a raw keyword (e.g., it must be parsed first)
- You need to match against a parsed/transformed field in the parent

---

## Subquery with `cat` (Lookup Table as Dynamic Filter)

Combine a lookup table with a subquery to give users a **flexible parameter filter** in dashboards. The lookup table maps friendly names to technical values that can be used as filters.

```
// Dashboard panel: filter by region using a lookup table
_sourceCategory=prod/app
[subquery:
  cat /Library/Shared/Lookups/region_accounts
  | where region matches "{{region}}"
  | count by account_id
  | compose account_id keywords
]
| json "accountId" as account_id
| count by account_id, service
```

**Use cases:**
- Map friendly names (regions, environments, teams) to internal identifiers
- Filter by multiple account IDs, namespaces, or hostnames from a maintained list
- Enable "All Production Accounts" or similar group filters via lookup table rows

**Recipe:**
1. Create a lookup table with columns for the display name and the technical filter value
2. In the subquery: `cat /path/to/lookup | where name matches "{{var}}" | count by tech_value | compose tech_value keywords`
3. Pass the result as the scope filter to the parent query

---

## The Sneaky Subquery Save (Advanced)

Sometimes you need to both **filter** a parent query AND **enrich** it with data from the child query. The standard `compose` pattern only filters — it doesn't pass the child's data columns to the parent.

The solution: save the child results to a **temporary lookup** inside the subquery, then reference it in the parent with `lookup`.

**Important:** Only works with v1 (legacy) lookups. v2 lookups are not fast enough for runtime creation and same-query reference.

```
// Pattern: save child data to temp lookup, then lookup in parent
<parent scope>
| where not [subquery:
    <child query>
    | save /temp/my_temp_lookup
    | "WILLNOTMATCH" as m
    | count by m
    | compose m keywords
  ]
| <rest of parent query>
| lookup * from /temp/my_temp_lookup on <join_key>=<join_key>
```

**How it works at runtime:**

| What happens | Result |
|---|---|
| Child runs, saves lookup | Lookup populated with enrichment data |
| `compose m keywords` returns `"WILLNOTMATCH"` | Parent filter: `not "WILLNOTMATCH"` — always true |
| Parent processes all events | Because `not "WILLNOTMATCH"` matches everything |
| `lookup *` enriches parent results | Child data columns are now available in parent |

**Real example: merging CSE insight comments into an insight status report**

```
(_index=sumologic_audit_events _sourcecategory=cseinsight*
 OR
 _index=sumologic_system_events _sourcecategory=cseinsight*)
| 1 as always_true
| where [subquery:
    (_index=sumologic_audit_events _sourcecategory=cseinsight*)
    | json field=_raw "insightComment.body" as comment
    | json field=_raw "insightComment.insightReadableId" as insightid
    | values(comment) as comments, count by insightid
    | save /temp/insightcomments
    | 1 as always_true | count by always_true | compose always_true
  ]
| json field=_raw "insightIdentity.readableId" as insightid
| json field=_raw "insight.status" as status
| max(_messagetime) as _messagetime, first(status) as status by insightid
| lookup comments from /temp/insightcomments on insightid=insightid
```

---

## Subquery Tips and Advanced Techniques

### Use `as` Aliases Inside Subqueries

```
| json "ip_address" | ip_address as c_ip | count by c_ip | compose c_ip
```

Renaming is useful when the field name in the child differs from what you need in the parent filter.

### Compose Multiple Fields

```
| compose src_ip,dst_ip
```

This creates: `(src_ip="a" AND dst_ip="b") OR (src_ip="c" AND dst_ip="d") OR ...`

### Different Time Range in Child

The child query can use a different time range than the parent:

```
[subquery from=(-15m):
  _sourceCategory=security/alerts
  | json "ip" as threat_ip
  | count by threat_ip
  | compose threat_ip keywords
]
```

Use this when the child data is more recent or less recent than the parent — for example, build a threat list from the last 15 minutes and apply it to a parent query running over 24 hours.

### Nested Subqueries

Subqueries can be nested inside other subqueries. Use sparingly — each nesting layer adds query complexity and potential for performance issues.

---

## Aggregation as an Alternative to `transactionize`

The `transactionize`, `transaction`, `join`, and `merge` operators all have strict **memory and event limits** and are slow at scale. For high-cardinality transaction correlation, use the **aggregation pattern** instead.

### Aggregation Pattern for Multi-State Transactions

Combine two or more log sources in one query using OR, then use conditional aggregation to correlate states by a shared ID:

```
(_sourceCategory=prod/app/checkout "Payment in progress"
 OR _sourceCategory=prod/app/checkout "Payment processed successfully"
 OR _sourceCategory=prod/app/checkout "Payment failed")
| json field=_raw "log" nodrop
| parse field=log "* trace_id=*" as event_desc, trace_id nodrop
| parse regex field=event_desc "(?<stage>Payment in progress|Payment processed successfully|Payment failed)" nodrop
| if(stage="Payment in progress", _messagetime, 9999999999999) as started
| if(stage matches "Payment processed successfully|Payment failed", _messagetime, -1) as ended
| if(stage matches "(?i)Payment processed successfully", 1, 0) as success
| if(stage matches "*failed*", 1, 0) as fail
| max(success) as success, max(fail) as fail, min(started) as started, max(ended) as ended by trace_id
| where started > 0 and success = 1
| (ended - started) / 1000 as duration_seconds
```

**Steps:**
1. Use OR to include all log sets in one query
2. Use `parse nodrop` to get all required fields (different logs have different fields)
3. Use `if(isempty(field1), field2, field1) as id` to merge two versions of an ID field
4. Use numeric `if` to mark states as 1/0 flags
5. Aggregate with `max(flag)` to detect final state
6. Use `min/max(_messagetime)` to compute start/end times for durations
7. Apply `where` after aggregation to detect complete/incomplete transactions

**Tip:** Use `values(field)` to merge a non-null value from two log sources into one column per ID — useful when field X only exists in log type A and is empty in log type B.

---

## When to Use Which Correlation Pattern

| Use Case | Recommended Pattern |
|---|---|
| Filter parent by dynamic list from child | Subquery (compose keywords) |
| Enrich parent with child data columns | Sneaky subquery save + lookup |
| Correlate multi-state transactions, high cardinality | Aggregation pattern (OR + parse nodrop + conditional if) |
| Join two sources with many-to-many relationship | Subquery (compose) or aggregation |
| SQL-style join with strict memory | `join` operator (small data only, has limits) |
| Merge multi-event rows into one row per entity | `transactionize` + `merge` (small data only) |

---

## MCP Tools Used

- `search_sumo_logs` — Test subquery patterns interactively
- `search_query_examples` — Find example subquery patterns in the query library

## Related Skills

- [Log Search Basics](./search-log-search-basics.md) — Pipeline fundamentals, compose operator
- [Search Optimization](./search-optimize-queries.md) — When to avoid subquery for performance
- [Dashboards Overview](./dashboards-overview.md) — Template variables used in cat-based subqueries

## API References

- [Subquery Operator](https://help.sumologic.com/docs/search/subqueries/)
- [Compose Operator](https://help.sumologic.com/docs/search/search-query-language/search-operators/compose/)
- [Lookup Tables](https://help.sumologic.com/docs/search/lookup-tables/)
- [Save Operator](https://help.sumologic.com/docs/search/search-query-language/search-operators/save/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-11
**Source:** CIP Subquery Secrets Playbook; Sumo Logic Advanced Topics Workshop (2025/2026)
**Domain:** Search & Query
**Complexity:** Advanced
