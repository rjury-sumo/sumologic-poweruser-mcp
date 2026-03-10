# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Model

This MCP server provides **read-only access** to Sumo Logic APIs. It is designed with the following security principles:

### 1. Read-Only Operations

- All tools perform only GET and search operations
- No write, update, or delete operations are exposed
- Data modification is not possible through this server

### 2. Credential Management

- Credentials are loaded from environment variables only
- Never hardcode credentials in code or commit them to version control
- Use `.env` files for local development (excluded from git)
- Each Sumo Logic instance requires separate credentials

### 3. Rate Limiting

- Built-in rate limiting prevents abuse
- Configurable limits per tool and per minute
- Circuit breaker protection for failing endpoints

### 4. Input Validation

- All user inputs are validated before API calls
- Query length limits prevent resource exhaustion
- Time range validation prevents overly broad searches
- Pagination limits prevent excessive data retrieval

### 5. Error Handling

- Error messages are sanitized to prevent information leakage
- Full error details logged server-side only
- No stack traces or internal paths exposed to clients

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### Where to Report

- **Email**: [your.email@example.com]
- **Subject**: [SECURITY] Sumo Logic MCP Server Vulnerability

### What to Include

1. **Description**: Detailed description of the vulnerability
2. **Impact**: What could an attacker accomplish?
3. **Reproduction**: Step-by-step instructions to reproduce
4. **Proof of Concept**: Code or screenshots (if applicable)
5. **Suggested Fix**: If you have ideas for remediation

### Response Timeline

- **Initial Response**: Within 48 hours
- **Triage & Assessment**: Within 1 week
- **Fix Development**: Depends on severity
  - Critical: 1-3 days
  - High: 1 week
  - Medium: 2 weeks
  - Low: 1 month
- **Public Disclosure**: After fix is released

### What to Expect

1. We will acknowledge receipt of your report
2. We will investigate and assess the severity
3. We will develop and test a fix
4. We will release a patched version
5. We will publicly acknowledge your contribution (if desired)

## Security Best Practices for Users

### Credential Protection

```bash
# DO: Use environment variables
export SUMO_ACCESS_ID="your_id"
export SUMO_ACCESS_KEY="your_key"

# DON'T: Hardcode credentials
# command: ["python", "server.py", "--id", "your_id", "--key", "your_key"]
```

### File Permissions

```bash
# Protect your .env file
chmod 600 .env

# Ensure credentials aren't world-readable
ls -la .env  # Should show -rw------- (600)
```

### Configuration Security

```json
{
  "mcpServers": {
    "sumologic": {
      "command": "uv",
      "args": ["run", "sumologic-poweruser-mcp"],
      "env": {
        "SUMO_ACCESS_ID": "${SUMO_ACCESS_ID}",
        "SUMO_ACCESS_KEY": "${SUMO_ACCESS_KEY}",
        "SUMO_ENDPOINT": "${SUMO_ENDPOINT}"
      }
    }
  }
}
```

### Network Security

- Run the MCP server in a trusted environment only
- Do not expose the server to untrusted networks
- Use firewall rules to restrict access if needed
- Monitor API usage for suspicious patterns

### Audit Logging

- Enable audit logging to track all API operations
- Review logs regularly for unusual activity
- Store logs securely with appropriate retention

### Principle of Least Privilege

- Use Sumo Logic access keys with minimal required permissions
- Create separate access keys for different environments
- Rotate access keys regularly (every 90 days recommended)
- Revoke unused or compromised keys immediately

## Known Limitations

### API Rate Limits

- Sumo Logic API has rate limits per account
- Exceeding limits may result in throttling or errors
- Configure `RATE_LIMIT_PER_MINUTE` appropriately

### Long-Running Searches

- Search jobs may timeout after configured limits
- Very broad time ranges may fail or be slow
- Use specific queries and reasonable time windows

### Data Exposure

- This server provides access to log and metric data
- Ensure Claude/LLM prompts don't request sensitive data
- Review query results for PII or confidential information
- Consider using Sumo Logic's data access controls

## Security Contact

For urgent security issues, contact: [your.email@example.com]

For general questions: [GitHub Issues](https://github.com/yourusername/sumologic-python-mcp/issues)

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers who report valid vulnerabilities.

---

**Last Updated**: 2025-02-25
