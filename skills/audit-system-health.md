# Skill: Monitor System Health via Audit Indexes

## Intent

Monitor Sumo Logic system health using audit indexes to track collector/source health, monitor alerts, and system operations. Build proactive alerts for infrastructure issues.

## Prerequisites

- Access to system events index (_index=sumologic_system_events)
- Understanding of collector/source architecture
- Basic knowledge of monitor alert lifecycle

## Context

**Use this skill when:**

- Building health monitoring for collectors and sources
- Tracking monitor alert patterns and alert fatigue
- Investigating system-level issues
- Creating operational dashboards

**Primary Use Cases:**

1. **Collector/Source Health Monitoring** - Detect unhealthy data collection
2. **Monitor Alert Analysis** - Identify noisy or frequently alerting monitors
3. **Alert Timeline Tracking** - Understand alert patterns over time

## Approach

### Use Case 1: Collector and Source Health Monitoring

#### Purpose

Create alerts when collectors or sources become unhealthy, enabling proactive remediation before data loss.

#### Pattern

```
_index=sumologic_system_events "Health-Change" unhealthy
| json field=_raw "status"
| json "eventType", "resourceIdentity.id" as eventType, resourceId
| json field=_raw "details.error" as error
| json field=_raw "details.trackerId" as trackerid
| json field=_raw "resourceIdentity.name" as resource_name
| max(_messagetime) as _messagetime, count by trackerid, error, resource_name, eventtype
```

#### MCP Tool

```bash
MCP: search_system_events
  use_case: "collector_source_health"
  from_time: "-1h"
  limit: 100
```

#### Result Fields

- `resource_name` - Collector or source name (use as alert grouping)
- `error` - Error message
- `trackerid` - Unique identifier for tracking
- `eventtype` - Type of health event

#### Creating a Monitor

1. Use the query above as monitor query
2. Set alert condition: `_count > 0`
3. **Critical:** Use `resource_name` as alert grouping
   - One alert per unhealthy collector/source
   - Prevents alert storm if multiple resources fail

4. Optional: Filter noisy errors

   ```
   | where !(error IN ("timeout connecting to endpoint", "transient network error"))
   ```

#### Best Practices

- Run every 15-30 minutes
- Alert on ANY unhealthy state (count > 0)
- Route to ops team notification channel
- Include trackerid in alert for support correlation

### Use Case 2: Monitor Alert Analysis

#### Purpose

Identify monitors that alert frequently (potential false positives or alert fatigue).

#### Pattern

```
_index=sumologic_system_events _sourceCategory=alerts
| json field=_raw "details.monitorInfo.monitorId" as monitorid
| json field=_raw "details.name" as eventname
| json field=_raw "resourceIdentity.name" as name
| json field=_raw "details.alertingGroup.previousState" as previousstatus
| json field=_raw "details.alertingGroup.currentState" as status
| timeslice 1h
| where status !="Normal"
| count by name
| sort -_count
```

#### MCP Tool

```bash
MCP: search_system_events
  use_case: "monitor_alerts"
  from_time: "-7d"
```

#### Analysis Questions

- Which monitors have >100 alerts in 7 days? (Likely noisy)
- Are alerts evenly distributed or in bursts?
- Do alerts correlate with deployments or system changes?

#### Remediation Actions

1. **High alert count (>100/week):**
   - Review alert thresholds (too sensitive?)
   - Check if alerting on expected behavior
   - Consider adding filters or increasing threshold

2. **Burst patterns:**
   - May indicate real issues during specific times
   - Keep monitor, investigate root cause

3. **Steady noise:**
   - Likely false positive
   - Adjust or disable monitor

### Use Case 3: Alert Timeline and Duration

#### Purpose

Understand alert lifecycle: when alerts fire, how long they last, what state transitions occur.

#### Pattern

```
_index=sumologic_system_events _sourceCategory=alerts
| json field=_raw "details.monitorInfo.monitorId" as monitorid
| json field=_raw "details.alertDuration" as duration nodrop
| if (isnull(duration),"0",duration) as duration
| replace(duration," ms","") as duration
| round(duration / 1000 / 60) as duration_min
| json field=_raw "resourceIdentity.name" as name
| json field=_raw "resourceIdentity.id" as resourceid
| json field=_raw "details.monitorInfo.monitorPath" as path
| json field=_raw "details.alertingGroup.previousState" as previousstatus
| json field=_raw "details.alertingGroup.currentState" as status
| _messagetime as time
| count by time, status, path, resourceid, name, duration_min
| fields -_count
| sort time
```

#### MCP Tool

```bash
MCP: search_system_events
  use_case: "monitor_alert_timeline"
  from_time: "-24h"
```

#### Result Fields

- `time` - When state change occurred
- `status` - Current alert state (Normal, Critical, Warning, etc.)
- `previousstatus` - Previous state
- `duration_min` - How long alert lasted (in minutes)
- `path` - Monitor path in library
- `resourceid` - Use to build URL to monitor

#### Analysis Use Cases

1. **Alert Duration Analysis:**
   - Short durations (<5 min): Flapping alerts, increase wait time
   - Long durations (>4 hours): Real issues or stale alerts

2. **State Transition Patterns:**
   - Normal → Critical → Normal: Expected alert lifecycle
   - Rapid transitions: Flapping, adjust thresholds
   - Critical → Critical: Different time series firing

3. **Time-Based Patterns:**
   - Alerts at specific times: Scheduled jobs, batch processing
   - Business hours only: User-driven load
   - Random: Likely infrastructure issues

## Query Patterns

### Health Event Pattern

```
_index=sumologic_system_events "Health-Change" {health_state}
| json extraction for relevant fields
| aggregate by resource_name (for alert grouping)
| filter optional noise
```

### Alert Analysis Pattern

```
_index=sumologic_system_events _sourceCategory=alerts
| json extraction for alert fields
| filter: where status != "Normal" (focus on active alerts)
| aggregate: count by monitor name or time
| sort by frequency or time
```

### Alert Timeline Pattern

```
_index=sumologic_system_events _sourceCategory=alerts
| json extraction including duration
| convert duration to minutes
| preserve time ordering with sort by time
| include state transition (previous → current)
```

## Examples

### Example 1: Create Collector Health Monitor

**Goal:** Alert when any collector or source becomes unhealthy.

**Step 1:** Test query

```bash
MCP: search_system_events
  use_case: "collector_source_health"
  from_time: "-1h"
```

**Step 2:** Create scheduled search or monitor

- **Name:** "Collector/Source Health Monitor"
- **Query:** Use returned query
- **Schedule:** Every 15 minutes
- **Alert Condition:** `_count > 0` (any unhealthy state)
- **Alert Grouping:** `resource_name`
- **Notification:** Ops team Slack/PagerDuty

**Step 3:** Configure notification payload

```
Alert: Collector/Source Unhealthy
Resource: {{resource_name}}
Error: {{error}}
Tracker ID: {{trackerid}}
Time: {{_messagetime}}
```

**Result:** One alert per unhealthy resource, no alert storms.

### Example 2: Identify Top 10 Noisy Monitors

**Goal:** Find monitors with highest alert frequency for review.

```bash
MCP: search_system_events
  use_case: "monitor_alerts"
  from_time: "-30d"
```

**Analysis:** Sort results by `_count` descending

**Example Output:**

```
1. "API Latency p99 > 500ms" - 847 alerts (28/day)
2. "Error Rate > 1%" - 623 alerts (21/day)
3. "Disk Usage > 80%" - 412 alerts (14/day)
```

**Actions:**

1. **Monitor #1:** 28 alerts/day is very high
   - Review if 500ms threshold is too sensitive
   - Check if latency spikes are real vs normal variation
   - Consider moving threshold to 750ms or adding smoothing

2. **Monitor #2:** Error rate monitor
   - Validate if 1% is appropriate threshold
   - Check if specific services drive errors
   - May need error type filtering

3. **Monitor #3:** Disk usage
   - Likely legitimate if disks near capacity
   - If frequent, may need automated cleanup or scaling

### Example 3: Analyze Alert Duration Patterns

**Goal:** Understand how long alerts typically last.

```bash
MCP: search_system_events
  use_case: "monitor_alert_timeline"
  from_time: "-7d"
```

**Analysis:** Group alerts by `duration_min` ranges

- <5 min: Flapping or transient
- 5-60 min: Short-lived issues
- 1-4 hours: Sustained issues
- >4 hours: Long-running problems or stale alerts

**Example Insight:**
Monitor "Database Connection Pool" has 50 alerts, all <2 minutes duration.

- **Diagnosis:** Flapping alert
- **Fix:** Increase wait time from 0 to 5 minutes, or adjust threshold

## Common Pitfalls

### Pitfall 1: Not Using Alert Grouping

**Problem:** One unhealthy collector generates 96 alerts/day (every 15 min check)

**Solution:** Use `resource_name` as alert grouping field - creates one alert per resource, updated on each run

### Pitfall 2: Alerting on Normal State

**Problem:** Including Normal transitions in alert analysis

**Solution:** Always filter `where status != "Normal"` to focus on active alerts

### Pitfall 3: Ignoring Duration for Flapping Detection

**Problem:** Not using duration_min to identify flapping

**Solution:** Filter for `duration_min < 5` to find rapid on/off alerts

### Pitfall 4: Alert Fatigue from High-Frequency Monitors

**Problem:** Running health checks every 1 minute

**Solution:** 15-minute interval is sufficient for most health monitoring

## Best Practices

### Health Monitoring

1. **Alert Grouping:** Always use resource_name
2. **Frequency:** 15-30 minutes is optimal
3. **Noise Filtering:** Exclude known transient errors
4. **Escalation:** Start with info, escalate to critical if persistent

### Alert Analysis

1. **Time Range:** Use 7-30 days for pattern detection
2. **Thresholds:** >20 alerts/day warrants review
3. **Correlation:** Compare with deployment/change times
4. **Action:** Set review SLA (e.g., any monitor >50 alerts/week reviewed within 3 days)

### Dashboard Creation

1. **Real-Time:** Current unhealthy collectors (last 1h)
2. **Trends:** Alert count by monitor over time (7d, 1h timeslice)
3. **Duration:** Histogram of alert durations
4. **Top N:** Top 10 most frequently alerting monitors

## Related Skills

- [User Activity Audit](./audit-user-activity.md) - Audit user actions
- [Search Cost Analysis](./cost-analyze-search-costs.md) - Analyze scheduled search costs
- [Content Library](./content-library-navigation.md) - Navigate to monitors

## MCP Tools Used

- `search_system_events` - Primary tool with use_case patterns
- `get_content_web_url` - Generate URLs to monitors using resourceid
- `search_audit_events` - For monitor configuration changes

## API References

- [System Event Index](https://help.sumologic.com/docs/manage/security/audit-indexes/system-event-index/)
- [Health Events API](https://service.au.sumologic.com/audit/docs/#tag/Health-Events-(System))
- [Alerts API](https://service.au.sumologic.com/audit/docs/#tag/Alerts-(System))
- [Monitors](https://help.sumologic.com/docs/alerts/monitors/)

---

**Version:** 1.0.0
**Domain:** System Operations & Monitoring
**Complexity:** Intermediate
**Estimated Time:** 30 minutes to set up basic health monitoring
