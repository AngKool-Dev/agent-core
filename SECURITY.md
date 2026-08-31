# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.0   | ✅        |

## Security Model

ARGUS enforces a security-first execution model:

```
MODEL → CAPABILITY ROUTER → SECURITY POLICY → ALLOW/ASK/DENY → EXECUTION
```

Key security guarantees:
- **DENY** cannot execute
- **ASK** requires human approval
- Approval scope cannot expand
- Sandbox remains authoritative
- MCP cannot bypass security
- Provider fallback cannot bypass security
- Recovery cannot bypass security
- UX cannot bypass security
- Replay cannot execute
- Secrets cannot enter persisted model-visible state

## Reporting a Vulnerability

To report a security vulnerability in ARGUS:

1. **Do NOT** open a public GitHub issue for security vulnerabilities.
2. **Do NOT** include actual secrets, credentials, or exploit details in public communications.
3. Contact the maintainers directly via the repository's security advisory feature or private communication channel.

When reporting, please include:
- Description of the vulnerability
- Steps to reproduce (without exposing sensitive data)
- Potential impact assessment
- Suggested fix (if any)

## Security Audit

ARGUS undergoes regular security audits including:
- Secret scanning of release artifacts
- Red-team testing against the security architecture
- Dependency vulnerability scanning
- Code review for security-sensitive paths

## Responsible Disclosure

We follow responsible disclosure practices. Please allow reasonable time for fixes before public disclosure.
