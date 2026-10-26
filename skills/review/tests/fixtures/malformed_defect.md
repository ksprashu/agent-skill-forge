# [DEFECT-999] [P1: High] Insecure Logging of Authentication Secrets

## Description
User passwords are logged in plain text during authentication failures instead of being redacted.

## Blast Radius
Credentials leak into centralized observability and monitoring logs, enabling unauthorized account takeover by any internal user with read access to log streams.

## Drop-in Remediation
```python
# Before:
logger.warning(f"Authentication failed for user {username} with password {password}")

# After:
logger.warning(f"Authentication failed for user {username} [REDACTED]")
```
