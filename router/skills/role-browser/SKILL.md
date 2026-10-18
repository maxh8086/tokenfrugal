---
name: role-browser
description: Inspect a web page. Snapshot it, check console and network errors. Lighthouse only when asked. Report with evidence.
---

# Browser inspection

Tools: navigate_page, take_snapshot, take_screenshot, list_console_messages, list_network_requests, lighthouse_audit.

1. navigate_page to the URL in the task. If it fails, stop and report the error text.
2. take_snapshot. Prefer it over take_screenshot.
3. list_console_messages. Note each error line.
4. list_network_requests. Note each request with a 4xx or 5xx status.
5. lighthouse_audit only if the task asks for it.
6. If a tool returns nothing, retry it once, then write "no data" for that check.
7. Stop after step 4, or after step 5 if asked.

Output: page title, each console error, each failed request (URL and status), each snapshot finding. Each item needs its tool result.
