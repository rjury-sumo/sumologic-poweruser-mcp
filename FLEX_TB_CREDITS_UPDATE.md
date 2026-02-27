# Flex TB Units and Credits Update Summary

## Changes Made

Updated the `analyze_search_scan_cost` tool to properly handle Flex vs Tiered organizations with different unit displays and credit calculations.

### 1. TB Values Added for Flex Metering Breakdown

**Summary Level:**
- Added `total_billable_scan_tb` field (billable_scan_gb / 1024)
- Rounded to 4 decimal places for precision

**Record Level:**
- Added `billable_scan_tb` field for each record
- TB is now the PRIMARY unit for Flex scan volumes

### 2. Credits Removed for Flex Metering

**Summary Level:**
- `total_scan_credits` is NOT included for `breakdown_type='metering'`
- Added `flex_billing_note` explaining why credits aren't calculated:
  ```
  "Credits NOT calculated for Flex metering - rates are highly contract-specific.
  Contact Sumo Logic for your contracted scan rate."
  ```

**Record Level:**
- `scan_credits` and `credits_per_query` are NOT included for metering breakdown
- These fields are ONLY present for tier breakdown (Infrequent tier)

### 3. Credits Retained for Tier Breakdown (Infrequent)

**No changes for tiered accounts:**
- `scan_credits` and `credits_per_query` still calculated using 0.016 cr/GB (16 cr/TB)
- This is the standard rate for Infrequent tier on tiered accounts
- Calculation remains: `total_scan_gb * scan_credit_rate`

### 4. Updated Documentation

**Parameter Description (`scan_credit_rate`):**
```
Credits per GB scanned (default: 0.016 cr/GB = 16 cr/TB). Only used for Infrequent tier
(tiered accounts) where 0.016 is the standard rate. For Flex metering breakdown, credits
are NOT calculated since rates are highly contract-specific.
```

**Returns Section:**
- Clearly separated returns for Tier vs Metering breakdown
- Highlighted that `billable_scan_tb` is the primary unit for Flex
- Noted that credits are NOT included for Flex

**Updated files:**
- [src/sumologic_mcp_server/sumologic_mcp_server.py](src/sumologic_mcp_server/sumologic_mcp_server.py) - Tool implementation
- [docs/mcp-tools-reference.md](docs/mcp-tools-reference.md) - User documentation

## Example Outputs

### Tier Breakdown (Infrequent - Tiered Org)

**Summary:**
```json
{
  "summary": {
    "total_records": 2,
    "total_queries": 79795,
    "total_scan_gb": 0.14,
    "total_scan_credits": 0.0
  }
}
```

**Record:**
```json
{
  "queries": 79778,
  "total_scan_gb": 0.12,
  "scan_credits": 0.0,
  "credits_per_query": 0.0,
  "tier_breakdown_gb": {
    "continuous": 0.12,
    "frequent": 0.0,
    "infrequent": 0.0
  }
}
```

### Metering Breakdown (Flex Org)

**Summary:**
```json
{
  "summary": {
    "total_records": 2,
    "total_queries": 79794,
    "total_scan_gb": 0.14,
    "total_billable_scan_gb": 0.14,
    "total_billable_scan_tb": 0.0001,
    "total_non_billable_scan_gb": 0.0,
    "flex_billing_note": "Credits NOT calculated for Flex metering - rates are highly contract-specific. Contact Sumo Logic for your contracted scan rate."
  }
}
```

**Record:**
```json
{
  "queries": 79777,
  "total_scan_gb": 0.12,
  "billable_scan_gb": 0.12,
  "billable_scan_tb": 0.0001,
  "non_billable_scan_gb": 0.0,
  "metering_breakdown_gb": {
    "flex": 0.0,
    "continuous": 0.12,
    "frequent": 0.0,
    "infrequent": 0.0,
    "flex_security": 0.0,
    "security": 0.0,
    "tracing": 0.0
  }
}
```

## Key Differences

| Feature | Tier Breakdown (Infrequent) | Metering Breakdown (Flex) |
|---------|----------------------------|---------------------------|
| **Primary Unit** | GB | **TB** |
| **Credits Calculated** | ✅ Yes (0.016 cr/GB standard) | ❌ No (contract-specific) |
| **TB Field** | ❌ No | ✅ Yes (`billable_scan_tb`) |
| **Billing Note** | ❌ No | ✅ Yes (explains no credits) |
| **Use Case** | Infrequent tier cost estimation | Flex scan volume tracking |

## Test Results

Created [test_flex_updates.py](test_flex_updates.py) with comprehensive validation:

✅ **Test 1 (Tier)**: Credits included, no TB field
✅ **Test 2 (Metering)**: TB included, no credits, billing note present
✅ **Test 3 (Auto-detect)**: Correctly applies tier/metering based on org type

## Migration Guide

**For Flex organizations:**
- Use `billable_scan_tb` as your primary metric (not GB)
- Do NOT rely on credits field - it won't be present
- Read `flex_billing_note` for billing information
- Contact Sumo Logic for your specific contracted scan rate

**For Tiered organizations (Infrequent tier):**
- No changes - credits still calculated at 0.016 cr/GB
- Continue using `scan_credits` for cost estimation

**For users parsing the response:**
- Check `breakdown_type` in response to know which fields are available
- Flex metering: Look for `billable_scan_tb` and `flex_billing_note`
- Tier breakdown: Look for `scan_credits` and `credits_per_query`

## Why These Changes?

1. **TB is more meaningful for Flex**: Flex scan volumes are typically measured in TB, not GB
2. **Credits are contract-specific**: Flex scan rates vary widely by contract, making generic credit calculations misleading
3. **Clarity**: Separating tier vs metering outputs prevents confusion about what metrics are authoritative
4. **Standards compliance**: 0.016 cr/GB (16 cr/TB) is the actual standard rate for Infrequent tier, so those credits are meaningful

## Summary

The tool now provides:
- **Accurate, contract-appropriate metrics** for both Tiered and Flex organizations
- **Clear differentiation** between estimated credits (Tiered/Infrequent) and unmeasured costs (Flex)
- **TB-scale visibility** for Flex scan volumes
- **Transparent messaging** about why credits aren't calculated for Flex
