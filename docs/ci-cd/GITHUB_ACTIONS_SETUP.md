# GitHub Actions Setup

This document explains how to configure GitHub Actions secrets for running integration tests on pull requests.

## Workflow Behavior

The CI workflow has two modes:

### Push Events (Fast Unit Tests)

- **Triggers:** Push to `main` or `develop` branches
- **Tests:** Unit tests only (`tests/test_*.py`)
- **Duration:** ~1-2 minutes
- **Requirements:** No secrets needed
- **Purpose:** Quick validation of basic functionality

### Pull Request Events (Full Integration Tests)

- **Triggers:** Pull requests to `main` or `develop` branches
- **Tests:** Full test suite including integration tests
- **Duration:** ~5-10 minutes
- **Requirements:** Sumo Logic API credentials (see below)
- **Purpose:** Comprehensive testing before merge

## Required Secrets for Pull Requests

Integration tests require access to a Sumo Logic instance. Configure these repository secrets (names match `.env.example`):

| Secret Name | Description | Required | Example |
|-------------|-------------|----------|---------|
| `SUMO_ACCESS_ID` | Sumo Logic Access ID | ✅ Yes | `suABC123...` |
| `SUMO_ACCESS_KEY` | Sumo Logic Access Key | ✅ Yes | `abc123xyz...` |
| `SUMO_ENDPOINT` | Sumo Logic API Endpoint | ✅ Yes | `https://api.us2.sumologic.com` |
| `SUMO_SUBDOMAIN` | Custom subdomain (if configured) | ⚠️ Optional | `mycompany` |

**Note:** Use `SUMO_ENDPOINT` (not `SUMO_API_ENDPOINT`) to match `.env.example` format. The `/api` suffix is added automatically by the client.

## Setting Up Secrets

### Step 1: Create Service Account with Access Key (Recommended)

**⚠️ Important:** Use a dedicated service account with view-only permissions for CI/CD to follow the principle of least privilege.

#### Option A: Service Account (Recommended for Production)

1. Log into your Sumo Logic account as an administrator
2. Go to **Administration** > **Users and Roles** > **Service Accounts**
3. Click **+ Add Service Account**
4. Configure the service account:
   - **Name:** `GitHub Actions CI`
   - **Description:** `Read-only service account for GitHub Actions integration tests`
5. Click **Save** to create the service account
6. Select the newly created service account
7. Click **+ Add Access Key**
8. Enter key name: `GitHub Actions CI Key`
9. Copy the **Access ID** and **Access Key** (you won't be able to see the key again!)
10. Assign **view-only role** (see Step 1b below)

**📖 Reference:** [Sumo Logic Service Accounts Documentation](https://www.sumologic.com/help/docs/manage/security/service-accounts/)

#### Option B: User Access Key (Alternative)

If service accounts are not available in your plan:

1. Log into your Sumo Logic account
2. Go to **Administration** > **Security** > **Access Keys**
3. Click **+ Add Access Key**
4. Enter name: `GitHub Actions CI`
5. Copy the **Access ID** and **Access Key** (you won't be able to see the key again!)

### Step 1b: Configure View-Only Permissions

**🔒 Critical:** Grant only view permissions, no manage/create/delete capabilities.

1. Go to **Administration** > **Users and Roles** > **Roles**
2. Click **+ Add Role**
3. Configure the role:
   - **Name:** `GitHub Actions View Only`
   - **Description:** `Read-only access for CI/CD integration tests`
4. **Capabilities** - Enable ONLY these view permissions:
   - ✅ **View Collectors**
   - ✅ **View Fields**
   - ✅ **View Field Extraction Rules**
   - ✅ **View Users**
   - ✅ **View Roles**
   - ✅ **View Content**
   - ✅ **View Dashboards**
   - ✅ **View Monitors**
   - ✅ **View Partitions**
   - ✅ **View Scheduled Views**
   - ✅ **View Account Overview**
   - ❌ **NO** Manage/Create/Update/Delete capabilities
5. Click **Save**
6. Assign this role to your service account:
   - Go back to **Service Accounts**
   - Select `GitHub Actions CI` service account
   - Click **Roles** tab
   - Add the `GitHub Actions View Only` role

**Why view-only?** This MCP server is read-only by design. Integration tests only need to read data, not modify it. Limiting permissions reduces security risk if credentials are compromised.

### Step 2: Determine Your API Endpoint

Your API endpoint depends on your Sumo Logic deployment region:

| Region | SUMO_ENDPOINT Value |
|--------|---------------------|
| US1 | `https://api.sumologic.com` |
| US2 | `https://api.us2.sumologic.com` |
| AU | `https://api.au.sumologic.com` |
| EU | `https://api.eu.sumologic.com` |
| JP | `https://api.jp.sumologic.com` |
| CA | `https://api.ca.sumologic.com` |
| DE | `https://api.de.sumologic.com` |
| IN | `https://api.in.sumologic.com` |
| FED | `https://api.fed.sumologic.com` |

**Finding your region:**

- Check your Sumo Logic login URL
- Example: `https://service.us2.sumologic.com` → US2 region → Use `https://api.us2.sumologic.com`
- **Note:** Do NOT include `/api` suffix - it's added automatically

### Step 2b: Determine Your Subdomain (Optional)

If your organization uses a custom subdomain for Sumo Logic UI access:

**Example UI URLs:**

- Default: `https://service.us2.sumologic.com` → No subdomain needed, leave `SUMO_SUBDOMAIN` unset
- Custom: `https://mycompany.us2.sumologic.com` → Set `SUMO_SUBDOMAIN=mycompany`

**When to set SUMO_SUBDOMAIN:**

- Only if you access Sumo Logic at `https://[your-subdomain].[region].sumologic.com`
- Used for generating correct web UI URLs in tool responses
- Leave unset if you use the default `service.xx.sumologic.com` URL

### Step 3: Add Secrets to GitHub Repository

#### For Repository Owners/Admins

1. Go to your GitHub repository
2. Click **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add each required secret:

**Secret 1: SUMO_ACCESS_ID** (Required)

- Name: `SUMO_ACCESS_ID`
- Value: `[paste your Access ID from Step 1]`
- Click **Add secret**

**Secret 2: SUMO_ACCESS_KEY** (Required)

- Name: `SUMO_ACCESS_KEY`
- Value: `[paste your Access Key from Step 1]`
- Click **Add secret**

**Secret 3: SUMO_ENDPOINT** (Required)

- Name: `SUMO_ENDPOINT`
- Value: `[your API endpoint from Step 2, e.g., https://api.us2.sumologic.com]`
- Click **Add secret**

**Secret 4: SUMO_SUBDOMAIN** (Optional)

- Name: `SUMO_SUBDOMAIN`
- Value: `[your subdomain from Step 2b, e.g., mycompany]`
- Click **Add secret**
- **Skip this if:** You use the default `service.xx.sumologic.com` URL

### Step 4: Verify Setup

1. Create a test pull request
2. Go to **Actions** tab in your repository
3. Find your PR's workflow run
4. Check that `integration-tests` job runs successfully
5. Review test output in the job logs

## Security Best Practices

### ✅ Use Service Accounts with View-Only Permissions

**Best Practice:** Always use service accounts instead of user access keys for CI/CD:

**Why Service Accounts?**

- **Purpose-built:** Designed for automation, not human users
- **No MFA conflicts:** Service accounts don't require multi-factor authentication
- **Independent lifecycle:** Not tied to employee accounts (no disruption when team members leave)
- **Audit trail:** Clear separation between human and automated actions
- **Granular control:** Easy to assign minimal permissions without affecting user access

**Required Capabilities:**
Enable ONLY these view permissions (never manage/create/delete):

- View Collectors, Fields, Field Extraction Rules
- View Users, Roles
- View Content, Dashboards, Monitors
- View Partitions, Scheduled Views
- View Account Overview

**🔒 Security Benefits:**

- Minimizes blast radius if credentials are compromised
- Prevents accidental modifications during testing
- Aligns with principle of least privilege
- Supports compliance and audit requirements

**📖 Reference:** [Sumo Logic Service Accounts](https://www.sumologic.com/help/docs/manage/security/service-accounts/)

### Rotate Keys Regularly

- Rotate access keys every 90 days
- Update GitHub secrets when rotating
- Delete old keys from Sumo Logic

### Limit Test Scope

Integration tests should:

- Use read-only operations when possible
- Query small time ranges (e.g., last 1 hour)
- Avoid expensive searches
- Clean up test data (if any writes are added)

## Troubleshooting

### Integration Tests Failing with "Missing Credentials"

**Symptom:** Tests fail with `ValidationError` or "Missing required configuration"

**Solution:**

1. Verify all three secrets are set in GitHub repository
2. Check secret names match exactly (case-sensitive)
3. Ensure secrets have no leading/trailing spaces
4. Re-create secrets if needed

### Integration Tests Failing with "401 Unauthorized"

**Symptom:** Tests fail with `401` or authentication errors

**Solution:**

1. Verify Access ID and Access Key are correct
2. Check that access key is not expired or deleted
3. Ensure user has sufficient permissions
4. Re-generate access key if needed

### Integration Tests Failing with "404 Not Found"

**Symptom:** Tests fail with `404` or endpoint not found

**Solution:**

1. Verify `SUMO_ENDPOINT` matches your Sumo Logic region (see Step 2 table)
2. Ensure endpoint does NOT include `/api` suffix (it's added automatically)
3. Check for typos in the endpoint URL
4. Correct format: `https://api.us2.sumologic.com` (not `https://api.us2.sumologic.com/api`)

### Tests Timing Out

**Symptom:** Tests take too long or timeout

**Solution:**

1. Check Sumo Logic instance performance
2. Verify network connectivity
3. Review test queries for efficiency
4. Consider increasing timeout values in test code

## Workflow Structure

```yaml
# .github/workflows/ci.yml

# Push to main/develop → unit-tests job only
unit-tests:
  if: github.event_name == 'push'
  # No secrets needed
  # Runs: tests/test_*.py (excluding integration/)

# Pull request → integration-tests job
integration-tests:
  if: github.event_name == 'pull_request'
  # Requires secrets
  # Runs: Full test suite with coverage
```

## Testing Locally

To run the same tests locally:

### Unit Tests Only

```bash
# Same as push CI
uv run pytest tests/test_*.py --ignore=tests/integration --ignore=tests/utilities --ignore=tests/debug -v
```

### Full Integration Tests

```bash
# Same as PR CI (requires .env file)
cp .env.example .env
# Edit .env with your credentials
uv run pytest --cov=src --cov-report=xml --cov-report=term -v
```

## Cost Considerations

Integration tests query your Sumo Logic instance:

- **Read-only operations:** No additional cost
- **Search queries:** Small scan costs on Flex/Infrequent tiers
- **Estimated cost per PR:** < 0.1 credits (typically negligible)

**Best practices:**

- Use test data in Continuous tier when possible
- Keep query time ranges small (1 hour)
- Run full tests on PRs only, not every push

## Future Enhancements

Potential improvements to consider:

- [ ] Add test environment with dedicated test data
- [ ] Implement test data mocking for faster tests
- [ ] Add performance benchmarking in CI
- [ ] Create separate workflow for scheduled daily full tests
- [ ] Add integration test results reporting dashboard

---

**Last Updated:** 2026-03-07
**Maintainer:** Project team
