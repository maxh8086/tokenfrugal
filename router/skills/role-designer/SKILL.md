---
name: role-designer
description: Build or inspect a Penpot design. Overview first, check the API before running code, export to verify.
---

# Designer

Tools: high_level_overview, penpot_api_info, execute_code, export_shape.

1. high_level_overview to see the file, pages and shapes. If it returns nothing, stop and report that.
2. penpot_api_info for the call you need. Never guess an API name.
3. execute_code with one small change or read at a time.
4. If execute_code errors, fix one thing and retry once. If it fails again, stop and report the error line.
5. export_shape on each shape you changed or inspected.
6. Compare the export with the task. Report match or mismatch.

Change only the shapes the task names.

Output: shapes changed, export result per shape, any error line.
