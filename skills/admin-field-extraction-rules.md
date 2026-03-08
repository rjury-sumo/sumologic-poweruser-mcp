# Skill: Field Extraction Rules (FERs) for Administrators

## Intent

Create and manage Field Extraction Rules (FERs) to pre-parse fields at ingest time, dramatically improving search performance, simplifying query syntax for users, and enabling complex routing logic — including the histogram/stripe pattern for defeating slow numeric `where` comparisons.

## Prerequisites

- Sumo Logic administrator access (Manage Data → Logs → Field Extraction Rules)
- Understanding of the log formats you want to extract from
- Familiarity with Sumo Logic parse and regex syntax

## Context

**Use this skill when:**

- High-value log sources (CloudTrail, Apache, K8s) are being queried frequently with search-time parsing
- Users are writing `| json "field" | where field = "value"` — FERs can eliminate the parse step
- Numeric `where` comparisons are making searches slow (use histogram/stripe pattern)
- Partition routing depends on field values that need to be computed at ingest time
- A log format is hard to parse (e.g., multi-line, complex regex) — pre-parse once, not on every search

**Don't use this when:**

- The log source is rarely queried — FER overhead may not be worth the benefit
- Fields are needed only occasionally — search-time parsing is fine for ad-hoc analysis
- You need fields from 100% of a very high-volume source — consider selective extraction

---

## What Are Field Extraction Rules?

Field Extraction Rules (FERs) are configured by administrators to **parse fields from log events at ingest time**. The extracted field values are stored in the index alongside the raw log text.

**Impact:** FER fields can be used in query scope (before the first `|`) just like metadata fields. This uses the bloom filter for retrieval — typically **5x–10x faster** than search-time parsing for the same field.

```
// Without FER — parse at search time (slower):
_sourceCategory=aws/cloudtrail
| json "eventName" as eventname
| where eventname = "ConsoleLogin"

// With FER — use pre-extracted field in scope (5-10x faster):
_sourceCategory=aws/cloudtrail eventname=ConsoleLogin
```

---

## FER Patterns

### Pattern 1: Speed — Pre-Parse JSON Fields

JSON logs are auto-parsed at search time, but pre-parsing commonly queried fields with a FER stores them in the index for faster access.

**Best for:** High-query-volume JSON sources like CloudTrail, application logs, Kubernetes events.

```
// FER scope: _sourceCategory=aws/cloudtrail*
// FER parse expression extracts key fields:
| json "eventName" as eventname
| json "eventSource" as eventsource
| json "userIdentity.arn" as userarn
| json "errorCode" as errorcode
| json "recipientAccountId" as accountid
```

Users can now query: `_sourceCategory=aws/cloudtrail* eventname=AccessDenied` — no search-time parse needed.

### Pattern 2: Convenience + Speed — Pre-Parse Complex Formats

Some log formats require complex regex parsing. Pre-parsing these fields once at ingest saves every user from having to write (and get right) the same complex regex.

**Best for:** Apache/nginx access logs, custom log formats with fixed delimiters, multi-value formats.

```
// FER scope: _sourceCategory=*apache/access*
// Apache Common Log Format parse:
| parse "* * * [*] \"* * *\" * *" as src_ip, ident, user, time, method, url, protocol, status_code, bytes
```

Users can now query: `_sourceCategory=*apache/access* status_code=404` — no regex parsing at query time.

### Pattern 3: Routing Support — Compute Tag Fields for Partition Routing

FERs can compute derived field values used to route logs to different partitions. This keeps partition scope expressions simple while enabling complex routing logic.

**Best for:** Tiering logs by severity, routing checkout vs. general web traffic to different cost tiers.

```
// FER scope: _sourceCategory=*nginx*
// Compute routing tier based on status code and URL:
| parse "\"* * *\" *" as method, url, protocol, status_code
| "" as tier
| if(status_code < 400, "infrequent", "continuous") as tier
| if(url matches "*checkout*", "continuous", tier) as tier
| if(url matches "*payment*", "continuous", tier) as tier

// Partitions then use simple scope:
// nginx_cont:   _sourceCategory=*nginx* tier=continuous
// nginx_infreq: _sourceCategory=*nginx* tier=infrequent
```

### Pattern 4: Integration-Injected Fields

Some Sumo Logic integrations (Kubernetes Observability, installed collector on AWS EC2) automatically add metadata fields to log events via HTTP headers (`x-sumo-fields`). These behave like FER fields — stored in index, usable in scope.

**Important:** New fields must be **enabled by an admin** in **Manage Data → Logs → Fields** — otherwise they are silently dropped and not available for querying.

```
// Kubernetes Observability injects: cluster, namespace, pod, service, pod labels
_sourceCategory=kubernetes/* container=cashdesk cluster=prod

// AWS EC2 installed collector injects: instanceid, instancetype, accountid, region
_sourceCategory=linux/* instanceid=i-1234567890
```

---

## Case Study: The Histogram/Stripe Pattern — Defeating the "Where-Wolf"

### The Problem

Numeric comparisons in `where` clauses cannot use the bloom filter — they are computed at runtime against every retrieved event. For large log sources, this is very slow:

```
// Slow — every retrieved event is parsed and compared at compute time:
_sourceCategory=web/iis
| parse "time-taken=*" as time_taken
| where time_taken > 30000
// Runtime: 5m 42s for -60m on large IIS log set
```

There is no way to put a numeric comparison like `time_taken > 30000` in the scope — the bloom filter only works on text tokens, not numeric values.

### The Solution: Pre-Compute a Categorical "Stripe" Field

Add a FER that computes a categorical string field representing performance bands. The string field values **can** be used in the bloom filter, enabling retrieval-time filtering.

```
// Add to FER on _sourceCategory=web/iis:
// (after parsing time_taken from the raw log)
| "" as stripe
| if(timetaken >= 5000, "Jgt5000", stripe) as stripe
| if(timetaken >= 2000 and timetaken < 5000, "Ilt5000", stripe) as stripe
| if(timetaken >= 1000 and timetaken < 2000, "Hlt2000", stripe) as stripe
| if(timetaken >= 500  and timetaken < 1000, "Glt1000", stripe) as stripe
| if(timetaken >= 200  and timetaken < 500,  "Flt500",  stripe) as stripe
| if(timetaken >= 100  and timetaken < 200,  "Elt200",  stripe) as stripe
| if(timetaken >= 50   and timetaken < 100,  "Dlt100",  stripe) as stripe
| if(timetaken >= 20   and timetaken < 50,   "Clt50",   stripe) as stripe
| if(timetaken >= 10   and timetaken < 20,   "Blt20",   stripe) as stripe
| if(timetaken >= 0    and timetaken < 10,   "Alt10",   stripe) as stripe
```

The prefix letters (`A`–`J`) ensure alphabetical ordering corresponds to numeric ordering, making the field browser easy to read.

### Using the Stripe Field in Queries

```
// Fast — only events with stripe matching Jgt5000 are retrieved:
_sourceCategory=web/iis stripe=Jgt5000
| count by url

// Fast — retrieve all responses over 2 seconds (J, I, H bands):
_sourceCategory=web/iis (stripe=Jgt5000 OR stripe=Ilt5000 OR stripe=Hlt2000)
| avg(timetaken) by url | sort _avg desc
```

### Performance Improvement

In testing: a query that took **5 minutes 42 seconds** with `where time_taken > 30000` ran in **1 second** using the stripe field — a **342x speedup**.

The reason: only a small fraction of requests (e.g., < 1%) are in the `Jgt5000` band. The bloom filter retrieves only those events, eliminating 99%+ of the data from compute processing.

---

## FER Administration Tips

| Tip | Detail |
|---|---|
| Extract only what is queried | Don't extract every field — focus on fields that users regularly query in scope. Unused FER fields waste ingest processing. |
| FER scope is critical | Use the most specific scope possible (`_sourceCategory=aws/cloudtrail*`) to avoid applying expensive parsing to logs that don't need it. |
| New fields need enabling | After creating a FER that extracts a new field name, go to Manage Data → Logs → Fields and enable that field — otherwise it is silently dropped. |
| Test before production | Run your FER parse expression as a regular log search against recent data to validate it extracts correctly before enabling as a FER. |
| Order of FERs matters | Multiple FERs can apply to the same log event. They are applied in the order listed. |
| `nodrop` for optional fields | If a field is not present in all events, the FER should use `nodrop` on optional extractions to avoid discarding non-matching events. |

---

## FER vs. Search-Time Parsing: Performance Comparison

| Method | Speed | Flexibility | When to Use |
|---|---|---|---|
| FER (index-time) | 5x–10x faster | Fixed at ingest | Frequently queried fields, high-volume sources |
| Search-time parse | Baseline | Fully flexible | Rare queries, ad-hoc investigation, evolving schemas |
| Auto-JSON mode | Slower than FER | Automatic | JSON logs without FER (adds search overhead) |

The general principle: the faster the field, the less flexible it is. FER fields are fixed at ingest. For exploration and one-off queries, search-time parsing is fine. For production dashboards, monitors, and high-frequency queries, FERs pay back their setup cost quickly.

---

## MCP Tools Used

- `list_field_extraction_rules` — List all configured FERs
- `get_field_extraction_rule` — Get a specific FER's definition
- `list_custom_fields` — List all enabled custom fields
- `search_sumo_logs` — Test FER parse expressions interactively before creating the rule

## Related Skills

- [Search Performance Best Practices](./search-performance-best-practices.md)
- [Partition Design](./admin-partition-design.md)
- [Log Search Basics](./search-log-search-basics.md)

## API References

- [Field Extraction Rules API](https://api.sumologic.com/docs/#tag/fieldExtractionRuleManagement)
- [Field Extraction Rules Docs](https://help.sumologic.com/docs/manage/field-extractions/)
- [Fields Management](https://help.sumologic.com/docs/manage/fields/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-09
**Source:** Sumo Logic Architecture For Log Search Performance (February 2025)
