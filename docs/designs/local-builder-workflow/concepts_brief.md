# Concepts brief: Sonnet plans and challenges, local models build

Date: 2026-10-27. Status: brainstorm approved by the user. Nothing implemented beyond the EGM plugin install and the global CLAUDE.md section.

## Goal

A feature gets a design that a fresh reviewer has challenged. Local models then build it in small, checked tasks. Cloud tokens go to design and review. Local models do routine work.

## Decisions

1. **Trigger scope:** feature-sized only. A task is feature-sized when it touches more than one module, adds an interface, schema or config, or has an unclear requirement. Other tasks go straight to `plan_add`.
2. **Planner and challenger:** Sonnet for both. Reviews use the EGM default: six Goldfish lenses (`egm-design`, `egm-codebase-details`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`, `egm-structural`) plus the `egm-synthesizer`, each a fresh subagent. The user may reduce this later to two lenses plus one synthesizer. Fallback when fresh subagents are unavailable: Sonnet self-review with a checklist, marked "unreviewed".
3. **Haiku's role:** keeps tracking as well as the fallback role. Status must match `plan_add`; if the two disagree, `plan_add` wins.
4. **Task handoff:** exact file paths, one acceptance command, what must not change, and a tool-call limit. A task that fails twice goes to the Haiku fallback.
5. **Done means:** the project's test command passes and a git sha or finished task id is recorded.
6. **Repo exception:** the tokenfrugal repo keeps Haiku subagents for execution, not the tokenfrugal MCP.
7. **Default location:** global `~/.claude/CLAUDE.md`, section "Planning and challenge workflow (EGM)".

## Risks

- Cloud cost: each design runs seven fresh Claude subagents (six lenses plus the synthesizer) under the default. Small tasks would cost more to review than to build, which is why the trigger is feature-sized only.
- Local model quality: qwen3-4b loops and times out on tasks such as slugify. The pilot measures first-pass rate before the workflow scales.
- Same-family review: Sonnet plans and challenges. An Opus challenger is the alternative if reviews miss problems.
- Status duplication: Haiku tracks and `plan_add` tracks. Mitigated by making `plan_add` the source of truth.

## Pilot

One feature in a non-tokenfrugal project, chosen from that project's handoff open items. Measure how many local tasks pass on the first attempt. The result decides whether the workflow scales.

## Pinned plugin

EGM is pinned to commit `b3a3595956759bf7f024af2ff061b2e0b44b438e4c` in `C:\Users\vaibh\Downloads\Projects\elephant-goldfish-model`, registered as marketplace `egm`, installed as `egm@egm` at user scope.
