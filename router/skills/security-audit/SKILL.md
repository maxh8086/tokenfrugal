---
name: security-audit
description: Security audit checklist for code or config. Each finding gets a CWE-style label, the location, an exploit condition, and a fix.
---

# Security audit

Tools: list_directory, read_file, search_files, ast-grep, python refactoring helpers. Check the named scope only.

1. Use ast-grep to find sinks: subprocess/os.system, eval/exec, SQL string building, open() with user paths, requests to user URLs.
2. read_file each hit and trace the input back to its source.
3. Classes: injection (shell, SQL, template, path traversal, SSRF); missing authn/authz or trusted client identity; secrets in source, logs or defaults; unsafe deserialisation or dynamic import; debug flags, permissive CORS, world-writable paths.

Format: `file:line - class - exploit condition - fix`. Mark "unverified" when you could not trace input to the sink. Never claim a vulnerability you have not traced.
