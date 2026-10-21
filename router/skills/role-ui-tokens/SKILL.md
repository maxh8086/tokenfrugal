---
name: role-ui-tokens
description: Write the design tokens file (ui-tokens) or check that components use tokens instead of raw values (ui-tokens-check). Pick the section that matches your role.
---

# UI tokens

Use only the section that matches your role name.

## ui-tokens
Write one CSS file with three layers:
1. Primitive: raw values (palette, spacing scale, type scale, radius, shadow).
2. Semantic: names by purpose (`--color-surface`, `--color-text`, `--space-card`). Point to primitives.
3. Component: optional names for one component (`--button-radius`). Point to semantic.

Rules:
- Use `var(--...)` references only. No hard values below the primitive layer.
- Keep the spec's scale. Do not add extra steps.
- Write the complete file in one call.

Output: tokens file path, count of each layer.

## ui-tokens-check
Read-only. Search the component files for:
- hex colours (`#` followed by 3 to 8 hex digits)
- `rgb(` or `hsl(` literals
- px values for spacing, font size or radius outside the tokens file

Report each hit as file:line and the raw value. Do not edit files.

Output: "pass" with zero hits, or a list of hits.
