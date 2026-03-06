# Flex Organization Fix for analyze_search_scan_cost

## Problem Statement

The `analyze_search_scan_cost` tool was defaulting to `breakdown_type='tier'`, which returns near-zero scan data for Flex organizations. Flex organizations require `breakdown_type='metering'` to correctly surface billable Flex scan volumes.

## Solution Implemented

Implemented **auto-detection** with multiple safety mechanisms to prevent Flex organizations from getting zero data:

### 1. Changed Default Behavior

- **Before**: `breakdown_type='tier'` (default)
- **After**: `breakdown_type='auto'` (default)

### 2. Auto-Detection Logic

When `breakdown_type='auto'` is selected (default):

1. Calls `get_account_status()` API to check the `logModel` field
2. If `logModel == "flex"` → uses `breakdown_type='metering'`
3. If `logModel == "Tiered"` → uses `breakdown_type='tier'`
4. If API call fails → defaults to `'metering'` (safer for Flex orgs)

### 3. Enhanced Warnings

Detects suspicious patterns indicating Flex org using wrong breakdown:

- If `breakdown_type='tier'` AND `total_queries > 1000` AND `total_scan_gb < 1.0`
- Returns warning in response:

```json
{
  "warning": {
    "type": "POSSIBLE_FLEX_ORG_USING_TIER_BREAKDOWN",
    "message": "WARNING: Found 79750 queries but only 0.09 GB scanned...",
    "recommendation": "Use breakdown_type='metering' or 'auto' for Flex organizations",
    "queries_analyzed": 79750,
    "scan_gb_found": 0.09
  }
}
```

### 4. Transparent Metadata

Response now includes detection information:

```json
{
  "query_parameters": {
    "breakdown_type": "tier",
    "breakdown_type_requested": "auto",
    "detected_org_type": "Tiered",
    "auto_detection_used": true
  }
}
```

### 5. Updated Documentation

- Added prominent warning in docstring about Flex requirements
- Updated [docs/mcp-tools-reference.md](docs/mcp-tools-reference.md) with warning banner
- Changed breakdown type descriptions to clearly indicate limitations

## Code Changes

### Files Modified

1. **src/sumologic_mcp_server/sumologic_mcp_server.py** (lines 1470-1810)
   - Changed default parameter from `'tier'` to `'auto'`
   - Added auto-detection logic after client initialization
   - Added warning detection for suspicious scan patterns
   - Enhanced response metadata with detection info

2. **docs/mcp-tools-reference.md** (lines 108-161)
   - Added warning banner for Flex organizations
   - Updated default value and parameter descriptions
   - Added auto-detection documentation
   - Updated use cases

## Test Results

Created [test_auto_detection.py](test_auto_detection.py) to verify functionality:

### Test 1: Auto-detection (default)

✅ **PASS** - Detected organization as "Tiered", used tier breakdown

- Warning triggered correctly (79,750 queries but only 0.09 GB scanned)

### Test 2: Explicit 'tier'

✅ **PASS** - Used tier breakdown as requested

- Warning triggered correctly for suspicious pattern

### Test 3: Explicit 'metering'

✅ **PASS** - Used metering breakdown, includes billable/non-billable fields

## Benefits

1. **Prevents Zero Data Issue**: Flex orgs automatically get correct breakdown by default
2. **Transparent**: Users can see what detection occurred and override if needed
3. **Backward Compatible**: Explicit `breakdown_type='tier'` or `'metering'` still works
4. **Safety Net**: Warning system catches cases where auto-detection might be wrong
5. **Fail-Safe**: If account status API fails, defaults to `'metering'` (safer for Flex)

## Usage Examples

### Recommended (Auto-detect)

```python
result = await analyze_search_scan_cost(
    from_time="-7d",
    group_by="user"
    # breakdown_type defaults to 'auto'
)
```

### Flex Organization (Explicit)

```python
result = await analyze_search_scan_cost(
    from_time="-7d",
    breakdown_type="metering",
    group_by="user_scope_query"
)
```

### Tiered Organization with Infrequent Tier

```python
result = await analyze_search_scan_cost(
    from_time="-7d",
    breakdown_type="tier",  # or 'auto' works too
    analytics_tier_filter="*infrequent*",
    group_by="user_query"
)
```

## Migration Guide

**For existing users:**

- No action required - default behavior now auto-detects
- Existing scripts with explicit `breakdown_type='tier'` or `'metering'` continue to work
- Check for `warning` field in response to detect potential misconfigurations

**For Flex organizations:**

- Remove explicit `breakdown_type='tier'` from your code (or change to `'auto'`)
- Use `breakdown_type='metering'` or `'auto'` for accurate scan data

## Summary

This fix ensures Flex organizations get accurate scan cost data by default, while maintaining backward compatibility and providing clear warnings when configurations might be incorrect. The auto-detection mechanism uses the official account status API to make intelligent decisions about which breakdown type to use.
