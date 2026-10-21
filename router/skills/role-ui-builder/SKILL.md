---
name: role-ui-builder
description: Build or change UI components, layout, polish, style, motion, or patch a review finding. Pick the section that matches your role.
---

# UI builder

Use only the section that matches your role name. Do not do other sections.

Rules for every section:
- Read the spec and the target file once. Do not read the whole project.
- Use only the tokens in the tokens file (CSS variables). No raw hex colours, px spacing, or font sizes in components.
- No placeholder text, no TODO, no "...". Write complete files.
- Keep unrelated code unchanged.
- Run run_tests on the changed folder. Stop when it passes.

## ui-components
Build components on the project's component library (shadcn/Radix). Keep accessible names, labels and keyboard support. Do not add new dependencies.

## ui-layout
Build the grid and page structure with Tailwind utilities. Mobile first. Use one breakpoint set. No fixed widths on containers.

## ui-polish
Change only spacing, borders, shadows and radius, using token values. Do not change layout or colours.

## ui-style
Apply the one chosen aesthetic from the spec. Do not mix in other styles.

## ui-motion
Add motion only when the spec asks for it. Use one animation library. Respect reduced-motion preference. Do not animate layout-changing properties.

## ui-patch
You receive a review finding and the file. Change only the lines the finding names. Return a diff-only fix. Run run_tests once.

Output: files changed, one line per change, test result.
