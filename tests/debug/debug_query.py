#!/usr/bin/env python3
"""Debug: print the exact query being generated."""

# Simulate the query construction
scope_filters = ["query_type=Interactive"]
query_regex = ".*"

validated_scope_filters = scope_filters

# Build scope line
if validated_scope_filters:
    scope_line = "_view=sumologic_search_usage_per_query " + " ".join(validated_scope_filters)
else:
    scope_line = """_view=sumologic_search_usage_per_query
query_type=*
user_name=*
content_name=*
query=*"""

query_parts = [scope_line]

# Add the rest
query_parts.append("""
| ((query_end_time - query_start_time ) /1000 / 60 ) as time_range_m
| json field=scanned_bytes_breakdown "Infrequent" as inf_bytes nodrop
| json field=scanned_bytes_breakdown "Flex" as flex_bytes nodrop
| if (isnull(inf_bytes),0,inf_bytes) as inf_bytes
| if (isnull(flex_bytes),0,flex_bytes) as flex_bytes

| round((data_scanned_bytes /1024/1024/1024) * 10 )/10 as scan_gbytes
| round((inf_bytes/1024/1024/1024) * 10) / 10 as inf_scan_gb
| round((flex_bytes/1024/1024/1024) * 10) / 10 as flex_scan_gb
| execution_duration_ms / ( 1000 * 60) as runtime_minutes

| time_range_m/60 as time_range_h
| count as searches, sum(scan_gbytes) as scan_gb, sum(inf_scan_gb) as inf_scan_gb, sum(flex_scan_gb) as flex_scan_gb, sum(retrieved_message_count) as results, avg(scanned_partition_count) as avg_partitions,
 avg(time_range_h) as avg_range_h, sum(runtime_minutes) as sum_runtime_minutes, avg(runtime_minutes) as avg_runtime_minutes by user_name, query, query_type, content_name, content_identifier | sort query asc
| where query matches /(?i){query_regex}/""")

query = "\n".join(query_parts)

print("="*80)
print("GENERATED QUERY:")
print("="*80)
print(query)
print("="*80)
