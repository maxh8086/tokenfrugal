---
name: planning
description: Turn a feature or fix into a tracked plan. Creates the plan in the tokenfrugal plan store and a GitHub issue with a task checklist, then links each task to its branch, PR, and verification.
---

# Planning (SDLC)

Use this when a request spans more than one task. The local plan store (`plan_add`) is the source of truth for the gateway. The GitHub issue is the public record. Keep them in step.

## 1. Plan locally

- Break the request into tasks. Each task should fit one tokenfrugal dispatch.
- Call `plan_add` with the tasks and their dependencies.

## 2. Create one GitHub issue per plan

- Title: `Plan: <short goal>`.
- Body: goal, acceptance criteria, then a task checklist, one line per plan task:
  `- [ ] #<plan task id> <task title>`
- Create it with `gh issue create --repo maxh8086/tokenfrugal --title ... --body-file <file>`.
- Write the issue number back into the plan (`plan_update_from` or a note on the first task).

## 3. Work each task

- One branch per task: `fix/<slug>` or `feat/<slug>`, from `main`.
- Dispatch with `dispatch_task(..., plan_id=<id>)`. Verify the result yourself: `git diff`, then the offline tests.
- Commit with the human author only. No Co-Authored-By trailer and no "generated with" footer.
- Post progress as an issue comment: `gh issue comment <n> --body "..."`, with the commit sha or the finished task id.

## 4. Close the loop

- Mark a plan task `done` only with evidence: a real git sha or a finished gateway task id.
- Tick its checkbox in the issue body once evidence exists.
- PRs reference the issue with `Refs #<n>`. Use `Closes #<n>` only when the whole plan is done.

## Not yet decided

- A GitHub Actions workflow that checks issue links, runs the offline tests, and ticks checkboxes on merge. Add it only after the manual flow has run once.
- A GitHub Projects board, if you want status columns.
