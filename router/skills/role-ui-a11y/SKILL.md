---
name: role-ui-a11y
description: Read-only accessibility audit of UI code. Report issues with file and line; do not edit.
---

# UI accessibility check

Read-only. Do not edit files.

Check each component file for:
1. Interactive elements (button, a, input, select) have an accessible name: visible text, `aria-label`, or a linked `<label>`.
2. Images have `alt`. Decorative images use `alt=""`.
3. Form inputs have a label, not only a placeholder.
4. Icon-only buttons have `aria-label`.
5. No `div` or `span` used as a button without role and keyboard handling.
6. Headings go in order (h1, then h2, no skips).
7. Focus styles are not removed (`outline: none` without a replacement).
8. Animations check for reduced motion.

Output: "pass" or one line per issue as `file:line - rule number - problem`. Stop after 30 issues.
