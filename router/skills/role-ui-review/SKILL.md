---
name: role-ui-review
description: Review a running page in the browser. Lighthouse scores, console errors, screenshot critique. Pick the section that matches your role.
---

# UI review

Use only the section that matches your role name. Read-only: do not change files.

## ui-review-lighthouse
1. navigate_page to the URL from the task.
2. lighthouse_audit.
3. Report the four scores (performance, accessibility, best practices, SEO).
4. List each failing audit with its name and value.

Output: scores, then failing audits, one line each.

## ui-review-console
1. navigate_page to the URL from the task.
2. list_console_messages. Keep errors and warnings only.
3. take_snapshot and check the page has a heading, a main landmark, and no empty interactive elements.

Output: "pass" or the console errors and DOM problems, one line each.

## ui-vision-review
1. navigate_page to the URL from the task.
2. take_screenshot.
3. Describe what is visible against the spec: layout, hierarchy, contrast, spacing. Quote only the parts that differ from the spec.

This review is advisory. It never blocks a publish.

Output: up to 5 findings, one line each.
