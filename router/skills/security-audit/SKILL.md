---
name: security-audit
description: Security audit checklist for code or config. Each finding gets a CWE-style label, the location, an exploit condition, and a fix.
---

# Security audit

Check the named scope only. Work through these classes:

1. Injection: shell, SQL, template, path traversal, SSRF in outbound URLs.
2. Authentication and authorisation: missing checks, trust of client-supplied identity or role.
3. Secrets: keys, tokens or passwords in source, logs, error messages or defaults.
4. Unsafe deserialisation, eval, or dynamic imports from untrusted input.
5. Dependencies and config: debug flags on, permissive CORS, world-writable paths.

Format: `file:line - class - exploit condition - fix`. Mark a finding "unverified" when you could not trace the input to the sink. Do not claim a vulnerability you have not traced.
