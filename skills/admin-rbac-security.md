# Skill: Sumo Logic RBAC and Security Architecture

## Intent

Design and implement Sumo Logic's access control model — covering authentication (SAML/SSO), role-based access control (capabilities and search scope), user lifecycle management, service account patterns, and API key security.

## Prerequisites

- Sumo Logic administrator access
- Understanding of your organisation's identity provider (IDP) if using SAML
- Clarity on which user groups need what data access and capabilities

## Context

**Use this skill when:**

- Designing the initial access control structure for a new Sumo Logic deployment
- Setting up SAML/SSO integration
- Creating role tiers for different user types
- Configuring search scope restrictions to limit data visibility
- Setting up service accounts for API automation
- Managing user lifecycle (onboarding, offboarding, role changes)
- Troubleshooting access issues ("user can't see X data", "user can't create monitors")

**Don't use this when:**

- Configuring data collection sources (see `data-collection-patterns`)
- Setting up alerting (see `alerting-monitors`)

---

## Sumo Logic Security Architecture — Three Layers

Access control in Sumo Logic is built from three independent layers. All three must be configured correctly for a user to access the right data with the right capabilities:

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: AUTHENTICATION                                     │
│  Who are you? (User/password or SAML/SSO)                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: RBAC — CAPABILITIES                               │
│  What can you do? (Create monitors, manage users, etc.)     │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: RBAC — SEARCH SCOPE                               │
│  What data can you see? (_sourceCategory=prod/*, etc.)      │
└─────────────────────────────────────────────────────────────┘
```

Users can belong to **one or more roles**, each of which has both capabilities and a search scope. The effective access is the union of all assigned roles.

---

## Layer 1: Authentication

### User/Password vs. SAML

| Factor | User/Password | SAML/SSO |
|---|---|---|
| Security | Lower (shared credentials) | Higher (centralised IDP) |
| Management | Manual | Automated via IDP |
| MFA | Optional | Enforced by IDP |
| Recommended | No | **Yes** |

### SAML Configuration Options

- **Mandatory SAML**: all users must log in via SAML. Can configure an **allow-list** of specific users who can still use username/password (for emergency admin access when IDP is down)
- **On-demand provisioning**: Sumo Logic creates a user account on first SAML login — no pre-provisioning required
- **SAML role provisioning attribute**: the IDP can pass a role attribute at login; Sumo Logic assigns the matching role(s). Requires matching role names between Sumo and the IDP directory
- **Subdomain**: configure a named subdomain (`myco.us2.service.sumologic.com`) to enable:
  - SP-initiated login (redirect to IDP from the login page)
  - Stable bookmarks for users
  - SSO login URL: `https://service.sumologic.com/sumo/saml/login/<subdomain>`

### SAML Role Provisioning

With SAML role provisioning, when a user logs in, the IDP passes their group/role names via an attribute. Sumo Logic assigns the matching Sumo roles. This enables:
- Automated role assignment when users join/leave IDP groups
- No manual role management in Sumo Logic

**Requirement:** Role names in Sumo Logic must match exactly the values in the IDP attribute.

---

## Layer 2: RBAC — Capabilities

Capabilities define what actions a role can perform. Configure at **Admin → Users and Roles → Roles**.

### Standard Role Tiers

Design your capability tiers before creating users. A typical layered structure:

| Role Tier | Key Capabilities | Typical Users |
|---|---|---|
| **Admin** | All capabilities, full `*` search scope | Sumo administrators |
| **Power User** | Deploy/manage collection, create content and alerts, limited admin tasks | Senior engineers, DevOps leads |
| **User** | Run searches, view configuration, create personal alerts | Developers, analysts, SREs |
| **Restricted User** | Very limited view/search only | Read-only stakeholders |

### Common Capabilities Reference

- View/Manage Collection — view or modify collectors and sources
- View/Manage Users and Roles — user administration
- Manage Partitions — create and modify data partitions
- View/Create Dashboards, Monitors, Scheduled Searches
- View/Manage Field Extraction Rules
- Share/Manage Content — share searches and dashboards with others
- Manage Ingest Budgets — configure ingest budget limits

---

## Layer 3: RBAC — Search Scope

The search scope on a role restricts which log data a user in that role can see. It is a filter applied to all searches made by users with that role.

### Scope Syntax

```
// Allow access to all production data:
_sourceCategory=prod/*

// Allow access to security data only:
_sourceCategory=security/*

// Restrict to a specific environment and business unit:
_sourceCategory=prod/payments/*

// Negate — exclude specific restricted data:
!(_sourceCategory=*restricted*)
!(_sourceCategory=pii/*)
```

### Design Principles

- Use **high-level wildcard patterns** to reduce management overhead as new sources are added
- Scope by **environment** (`prod/*`, `dev/*`) for environment-separation
- Scope by **business unit** (`*/payments/*`) for data segmentation
- Use **negation** to exclude specific sensitive categories from otherwise broad roles
- Multiple roles are **unioned** — a user in two roles sees the union of both scopes

### Example Scope Design

```
Admins:           * (all data)
Power Users:      _sourceCategory=prod/* OR _sourceCategory=dev/*
Security Team:    _sourceCategory=*/security/* OR _sourceCategory=*/cloudtrail/*
App Team A:       _sourceCategory=prod/app-a/*
App Team B:       _sourceCategory=prod/app-b/*
Restricted User:  _sourceCategory=prod/public-metrics/*
```

---

## Service Accounts and API Users

### Why Service Accounts?

A user's API key inherits **all capabilities and search scope** of that user's roles. Personal user API keys should never be used in automated systems because:
- If the user leaves, the key becomes invalid
- Personal keys often have broader permissions than automation needs
- Rotation is harder when tied to a person

### Service Account Recipe

1. **Create a dedicated user** with a team email address (e.g., `sumo-api-svc@acme.com`, `sre-automation@acme.com`). Use an address that the team can access for notifications.

2. **Define required permissions** — determine the minimum search scope and capabilities needed for the automation. Common examples:
   - Search-only account: no capabilities, restricted scope (`_sourceCategory=nothing` if pure API consumer)
   - Alert manager: capability to create/manage monitors only
   - Content deployer: capability to create dashboards and scheduled searches

3. **Create a dedicated role** with only the minimum required capabilities and search scope.

4. **If SAML is mandatory**: add the service account user to the SAML allow-list so it can log in with username/password to generate API keys. You can remove from the allow-list after initial setup for extra security.

5. **Log in as the service account** to create persistent content (dashboards, monitors, scheduled searches) and to generate access keys with descriptive names.

6. **Follow API key best practices**:
   - Store keys in a secrets manager, never in code
   - Rotate keys regularly
   - Name keys descriptively (e.g., `terraform-prod-deploy`, `pagerduty-webhook`)

### Access Tokens vs. Access Keys

| Type | Use Case | Bound To |
|---|---|---|
| **Installation Token** | Register installed collectors | Not a user — collector registration only |
| **Access Key (API Key)** | API automation, Terraform | A specific user account |

**Best practice for collectors:** Use **installation tokens** (not access keys) to register installed collectors. Installation tokens:
- Are not associated with any user account
- Cannot be used to access data or make API calls
- Are revocable without affecting user accounts
- Are the recommended method per Sumo Logic security guidance

---

## User Lifecycle Management

### When a User Leaves the Organisation

Two options: **disable** or **delete**.

| Action | Effect on Schedules | Recommended? |
|---|---|---|
| **Disable** | Stops all their scheduled searches, alerts, and dashboard refreshes | Only if temporary |
| **Delete + Transfer** | Content is transferred to another user; schedules continue running | **Yes — always preferred for departures** |

**Recommendation:** When offboarding, delete the user and **transfer their content to the team account or account owner**. This ensures that all monitors, scheduled searches, and dashboards continue to run without interruption.

The user/roles API supports bulk automation of user management for organisations using directory sync or HR system integration.

---

## MCP Tools Used

- `get_sumo_users` — List all users and their role assignments
- `get_sumo_roles_v2` — List all roles and their configurations
- `search_audit_events` with `source_category="userSessions"` — Audit login activity
- `search_audit_events` with `event_name="UserCreated"` or `event_name="RoleAssigned"` — Track user management events

## Related Skills

- [Admin Alerting and Monitoring](./admin-alerting-and-monitoring.md) — admin setup prerequisites
- [Data Collection Patterns](./data-collection-patterns.md) — access tokens for collectors
- [Consulting Guide](./consulting-guide.md) — RBAC design questions

## API References

- [Users API](https://api.sumologic.com/docs/#tag/userManagement)
- [Roles API](https://api.sumologic.com/docs/#tag/roleManagement)
- [SAML Configuration](https://help.sumologic.com/docs/manage/security/saml/)
- [Access Keys](https://help.sumologic.com/docs/manage/security/access-keys/)
- [Installation Tokens](https://help.sumologic.com/docs/manage/security/installation-tokens/)
- [Metadata Naming Conventions](https://help.sumologic.com/docs/send-data/reference-information/metadata-naming-conventions/)

---

**Version:** 1.0.0
**Last Updated:** 2026-03-11
**Source:** CIP Onboarding Sessions I & II (Sumo Logic Customer Success)
**Domain:** Security & Access Control
**Complexity:** Admin-level
