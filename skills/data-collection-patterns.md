# Skill: Sumo Logic Data Collection Patterns

## Intent

Understand the common patterns for onboarding log and metrics data to Sumo Logic — including installed collectors, HTTPS sources, hosted/cloud sources, Cloud-to-Cloud (C2C), OpenTelemetry, and pipeline-based collection — to choose the right approach for a given environment.

## Prerequisites

- Admin or operator access to a Sumo Logic instance
- Understanding of the environment where logs originate (cloud, on-prem, SaaS, containers)

## Context

**Use this skill when:**

- Onboarding a new data source for the first time
- Choosing between collection methods for a specific environment
- Troubleshooting collection problems (no data arriving)
- Architecting a new log collection strategy for an organisation

**Don't use this when:**

- Querying data that is already ingested (use search skills)
- Managing individual source configuration details (refer to product documentation for specifics)

---

## What Data Can Sumo Logic Ingest?

Sumo Logic is a **unified flexible platform** capable of ingesting:

- **Any source**: on-premises, cloud, legacy infrastructure, SaaS applications
- **Any telemetry type**: logs, metrics, distributed traces (MELT)
- **Any format**: structured JSON, semi-structured, unstructured text, syslog, binary encoded
- **Any collection method**: installed agent, open source agents, cloud provider integrations, HTTPS

All data types use the same query analytics approach — you can correlate logs, metrics, and traces in a single investigation.

---

## Reference Architecture

The Sumo Logic collection architecture has these layers:

```
Data Sources
  ↓
Integrations (File, Syslog, Fluentd, Lambda, AWS S3/Cloudwatch, Azure, OTEL, C2C)
  ↓
Sources (Local HTTPS, Cloud, OTLP C2C)
  ↓
Collectors (Installed Collector, Cloud Hosted Collectors, C2C Framework)
  ↓
Processing (Rules, Rate Limiter, Ingest Budgets)
  ↓
Indexing (Keywords, Metadata, Field Extraction, Partitions, Live Tail)
  ↓
Search and Analytics
```

---

## Collection Pattern 1: Installed Collector (Agent)

**Best for:** On-premises hosts, VMs, containers where you need to collect local files, syslog, or host metrics per instance.

**How it works:** A Java agent is installed on each host. It reads local log files, syslog streams, or metric sources and forwards data to Sumo Logic.

**Use cases:**
- Local log files (`/var/log/app.log`)
- Windows Event Logs
- Syslog on port 514
- Host metrics (CPU, memory, disk)

**Considerations:**
- Requires agent installation and management on each host
- Best for environments where you control the host OS
- Can use a **Remote Installed Collector** pattern where one collector reads from multiple remote hosts via SSH or Windows Remote — useful when network restrictions prevent one-per-host

---

## Collection Pattern 2: HTTPS Source (Most Common)

**Best for:** Any system that can make an outbound HTTPS POST — by far the most common modern pattern.

**How it works:** Sumo Logic provides an HTTPS endpoint URL. Your application, function, or pipeline POSTs log data to this URL. No agent required on the source system.

**Common senders:**
- AWS Lambda functions (log forwarding)
- AWS Kinesis Firehose
- Fluentd / Fluent Bit
- Logstash
- NxLogger
- Docker log driver
- Custom application code

**Use cases:**
- Serverless functions
- Container log pipelines
- SaaS and cloud-native applications
- Any system that can make HTTP requests

**Considerations:**
- Very flexible — any language or platform can use HTTPS POST
- Centralized pipeline approach: aggregate logs from many sources to a single central Fluentd/Logstash, then forward to Sumo Logic from there

---

## Collection Pattern 3: Hosted Sources (Cloud Integrations)

**Best for:** Cloud platform logs and events managed by the cloud provider.

**How it works:** Sumo Logic hosts a source that pulls data from cloud storage or event streams. No agent required.

**Common types:**
- **AWS S3** — reads log files written to S3 (CloudTrail, ELB, VPC Flow Logs, S3 access logs)
- **AWS CloudWatch** — subscribes to CloudWatch Log Groups
- **AWS Kinesis** — reads from Kinesis Data Streams or Firehose
- **Azure Event Hub** — reads from Azure Event Hub streams
- **GCP** — reads from GCP logging exports

**Use cases:**
- AWS CloudTrail audit logs
- VPC Flow Logs
- S3 access logs
- Azure Activity Logs
- GCP audit logs

**Considerations:**
- Low operational overhead — Sumo manages the polling/subscription
- Latency depends on how frequently the cloud provider writes to the source (S3 can have minutes of delay)

---

## Collection Pattern 4: Cloud-to-Cloud (C2C) Framework

**Best for:** SaaS APIs and cloud services where Sumo Logic hosts a function that polls the vendor API.

**How it works:** Sumo Logic hosts and manages a polling function that authenticates to a third-party API and pulls data on a schedule. No infrastructure required on your side.

**Examples:**
- Okta logs
- Salesforce
- Slack audit logs
- GitHub audit logs
- Crowdstrike
- Many security and SaaS platforms

**Use cases:**
- SaaS security and audit events
- Identity provider activity
- DevOps platform events

**Considerations:**
- Sumo Logic manages all infrastructure
- You only need to provide API credentials
- Check the C2C catalog for supported sources

---

## Collection Pattern 5: OpenTelemetry (OTEL)

**Best for:** Modern cloud-native applications requiring unified logs, metrics, and traces from a single open-source agent.

**How it works:** The Sumo Logic OpenTelemetry distribution (or any OTLP-compatible agent) collects logs, metrics, and traces and sends them via the OTLP protocol to a Sumo Logic OTLP source.

**Advantages:**
- One agent for all telemetry types (logs, metrics, traces)
- Vendor-neutral open standard
- Rich automatic instrumentation for many languages and frameworks
- Native Kubernetes metadata enrichment

**Use cases:**
- Kubernetes-native applications
- Microservices requiring distributed tracing
- Environments standardising on OpenTelemetry

---

## Collection Pattern 6: Pipeline / Centralized Syslog

**Best for:** Environments with many sources that need central aggregation before sending to Sumo Logic.

**How it works:** A central aggregation system (Fluentd, Logstash, NxLogger, syslog server, Docker log driver) collects from many sources, then forwards the aggregated stream to a single Sumo Logic HTTPS source.

**Use cases:**
- Large-scale syslog environments
- Container environments with Docker log drivers
- Environments where each host cannot connect directly to the internet

**Considerations:**
- The central aggregation layer adds a potential single point of failure
- Provides a good place to apply filtering, transformation, or enrichment before ingestion

---

## Collection Pattern 7: Remote Installed Collector

**Best for:** Network-restricted environments where you cannot install an agent on every host.

**How it works:** A single installed collector on a jump host uses SSH (Linux) or Windows Remote Management to read log files from remote hosts.

**Considerations:**
- Useful where network security policies prevent direct outbound connections from every host
- More complex to configure and maintain than per-host collectors
- Limited scalability compared to HTTPS-based patterns

---

## Choosing a Collection Pattern

| Environment | Recommended Pattern |
|---|---|
| On-premises VMs / bare metal | Installed Collector |
| AWS Lambda / serverless | HTTPS Source (Lambda → Sumo) or AWS C2C |
| AWS CloudTrail / S3 logs | Hosted AWS S3 Source or C2C |
| Azure / GCP cloud logs | Hosted Azure / GCP Source |
| SaaS APIs (Okta, Salesforce, Slack) | Cloud-to-Cloud (C2C) |
| Kubernetes / containerised apps | OpenTelemetry |
| Centralised logging (Fluentd, Logstash) | HTTPS Source from pipeline |
| Network-restricted on-premises | Remote Installed Collector |
| Custom applications | HTTPS Source |

---

## Setting Source Category Best Practices

The `_sourceCategory` value you set on a source is the primary way to scope searches and route data to partitions. Good source category naming is critical:

```
// Recommended hierarchical naming convention:
environment/technology/application
prod/aws/cloudtrail
prod/kubernetes/myapp
dev/apache/access
```

- Use lowercase and `/` separators
- Include environment prefix (`prod`, `dev`, `staging`)
- Begin with the least-descriptive, highest-level grouping and get more specific with each component
- Be specific enough to distinguish sources
- Use wildcards in queries: `_sourceCategory=prod/aws/*`

**Source category serves three purposes simultaneously:**
1. **Search scoping** — efficiently define the scope of your search with `_sourceCategory=Networking/Firewall/*`
2. **Partition routing** — route data to specific partitions using source category in the routing expression
3. **RBAC** — restrict role access with search scope filters like `_sourceCategory=security/*`

---

## Logging Standards — Foundation for Value

Establishing a logging standard for your environment is a prerequisite for good Sumo Logic use. Define this before ingesting at scale:

- **Metadata standards**: agreed source category taxonomy, source names, collector naming
- **One format per source category**: a source category should define one log format, not multiple variants
- **Log levels**: well-defined values (`info`, `error`, `warn`, `debug`, `trace`) — do not log `debug` or `trace` in production
- **PII policy**: define what personal data is acceptable/not acceptable in logs; mask or hash PII using processing rules before ingest
- **Ownership fields**: define what metadata identifies business dimensions (owner, product, service, environment)
- **Field naming conventions**: standardise field names for common concepts (e.g., `user_id` not `userid`/`user`/`userId`)
- **Log size**: keep events below 64KB (Sumo's maximum event size); larger events may need to be split or summarised
- **Security/data classification**: map log categories to any security or data classification standards you have

---

## Technical Best Practices for Log Ingestion

### Timestamp Handling

Correct timestamp parsing is critical. Sumo parses `_messagetime` from the log event; if parsing fails, it defaults to receipt time, causing ingest lag:

```
// Detect timestamp/timezone issues on a source
_sourcecategory=prod/*
| _format as tz_format
| _receipttime - _messagetime as lag_ms
| lag_ms / (1000 * 60) as lag_m
| values(tz_format) as tz_formats, min(lag_m) as min_lag, avg(lag_m) as avg_lag, max(lag_m) as max_lag by _collector, _source, _sourcecategory
| sort avg_lag
| if(avg_lag < 0, "ERROR - future timestamp!", "OK") as status
| if(avg_lag > 5, "WARN - high lag source", status) as status
| if(avg_lag > 60, "ERROR - Very high lag time on source ingestion", status) as status
```

### Multiline Events

Some sources emit log events that span multiple lines (Java stack traces, JSON blocks). Configure multiline parsing at the source level to ensure one event = one log record.

### HTTPS Metadata Headers (for Pipeline Collection)

When POSTing logs via HTTPS from a shared pipeline (Fluentd, Logstash, etc.), use these headers to set correct metadata context per stream:

| Header | Purpose |
|---|---|
| `X-Sumo-Category` | Sets `_sourceCategory` for this batch |
| `X-Sumo-Host` | Sets `_sourceHost` for this batch |
| `X-Sumo-Fields` | Sets custom fields as `key=value` pairs |

This is critical for shared pipelines where one HTTPS endpoint receives logs from many sources — use headers to preserve the original source context.

### Authentication: Access Tokens vs. Access Keys

- **Use installation tokens** (not access keys) to register installed collectors — they are not tied to a user account and can only be used to register a collector, not to access data
- **Use dedicated service account users** with restricted roles for API automation — never use a personal user's API keys in automated systems

### Kubernetes Collection

Use **Sumo Logic's native Kubernetes collection** (the Sumo OTel Helm chart), not a generic Fluentd or Logstash plugin. The native collection:
- Reduces cost per event by **>50%** through smarter batching
- Automatically creates key metadata fields (namespace, pod, container, etc.)
- Supports logs, metrics, and traces from a single deployment

---

## Processing Rules — Reduce and Transform Before Ingest

Processing rules are applied at the source level before data is stored. They are your primary tool for **reducing ingest volume** and **masking PII**.

**Types of processing rules:**

| Type | Effect |
|---|---|
| **Include** | Keep ONLY events matching a whole-line regex |
| **Exclude** | Drop events matching a whole-line regex |
| **Mask** | Replace matched text with `#####` (good for PII like credit card numbers) |
| **Hash** | Replace matched text with a hash (consistent anonymisation) |
| **Archive** | Forward matching events to AWS S3 archive instead of ingesting |

**Key differences: Installed vs. Hosted collector rules:**

| Factor | Installed Collector | Hosted Collector |
|---|---|---|
| Where evaluated | Client-side (on the host) | Sumo cloud-side |
| Bandwidth reduction | Yes — filtered data is not sent | No — data is sent then filtered |
| Counts toward throttle/budget | No (filtered before send) | Yes (at full original size) |
| CPU cost | Uses host CPU | No host CPU |

**Include/Exclude regex rules:**
- Rules must be RE2-compliant
- The regex must match the **entire message** from start to end
- For multiline messages, add `(?s)` modifiers: `(?s).*EventCode = 5156.*(?s)`
- Multiple rules are OR-combined for includes/excludes
- Non-capturing groups: `(?:abc|efg|xyz)` for alternatives

```
// Exclude all DEBUG events in production
.*[0-9] \[DEBUG\].*

// Exclude Windows Event Code 5156 (multiline)
(?s).*EventCode = 5156.*(?s)
```

**Important:** Excluded data is **permanently gone** — it cannot be recovered from Sumo. Archive rules write to S3 first, allowing future re-ingest if needed. Use mask/hash for PII instead of exclude when you may need the field structure later.

---

## MCP Tools Used

- `get_sumo_collectors` — List installed collectors and their status
- `get_sumo_sources` — List sources for a specific collector
- `search_system_events` with `use_case="collector_source_health"` — Find unhealthy collectors or sources
- `explore_log_metadata` — Verify data is arriving and check source categories

## Related Skills

- [Log Search Basics](./search-log-search-basics.md)
- [Indexes and Partitions](./search-indexes-partitions.md)

## API References

- [Installed Collector](https://help.sumologic.com/docs/send-data/installed-collectors/)
- [HTTPS Source](https://help.sumologic.com/docs/send-data/hosted-collectors/http-source/)
- [Cloud-to-Cloud Sources](https://help.sumologic.com/docs/send-data/hosted-collectors/cloud-to-cloud-integration-framework/)
- [OpenTelemetry](https://help.sumologic.com/docs/send-data/opentelemetry-collector/)
- [AWS Sources](https://help.sumologic.com/docs/send-data/hosted-collectors/amazon-aws/)

---

**Version:** 1.1.0
**Last Updated:** 2026-03-11
**Source:** SumoLogic Logs Basics Training (August 2025); CIP Onboarding Sessions I & II
