# Session handoff

Sonnet assigns every Codex (GPT-6 Luna) task here, and Codex writes its feedback here. The rules are in [implementation-kickoff-prompt.md](implementation-kickoff-prompt.md).

- Sonnet writes **Current assignment**: everything above its Feedback block.
- Codex reads the assignment, does the task, and fills in only the **Feedback** block. It edits nothing else in this file.
- Before Sonnet writes a new assignment, it moves the finished assignment and its feedback to the top of **History**.
- Haiku commits this file with each step, so the PR for a step records what was asked and what Codex reported.

## Current assignment

- **Step:** none yet
- **Branch:** -
- **Kind:** build | fix 1 | fix 2 | re-scope part N
- **Assigned at:** -
- **Status:** waiting (Sonnet sets `assigned`; Codex sets `in progress`, then `done`, `blocked` or `failed`)

### Task

(The build spec or fix plan: the plan rows in full, the files Codex may touch, the files it must not change, the acceptance command, the tool-call limit, and the fixed instructions from the prompt's SPECS section.)

### Feedback (Codex fills this in)

- **Status:** -
- **Files changed:** -
- **Tests written first:** test names, and the short output of the run that shows them failing before the code
- **Test result after the code:** -
- **Acceptance command result:** -
- **Departures from the plan:** none, or what changed and why
- **Problems or questions for Sonnet:** none, or each one in a line

## History

(Finished assignments with their feedback, newest first.)
