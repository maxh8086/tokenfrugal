# Haiku fallback log (from Market-Scanner, ui-rollout, 2026-10-11)

Each entry records one time the builder role failed and Claude fell back to a Haiku subagent. Every entry has the task, the dispatch IDs, the reason for the fallback, the root cause (RCA), and the proposed fix. RCAs marked **hypothesis** are not yet verified.

## F-1: builder LoopError on text tool calls

- **Task:** narrow the invented-label guard test in `tests/test_ui_stocks_page.py`, then a one-line edit to the same file.
- **Dispatches:** `fcaf64ba93`, `1843234d17` (resume_task on it, same error), `5648e10123` (re-scoped to one line). Each returned `LoopError: you wrote a tool call as text`.
- **Why fallback:** the rule allows Haiku only after one resume plus one re-scope. Both failed.
- **RCA (hypothesis):** the builder model writes the tool call as plain text instead of using the tool-calling interface. `resume_task` may replay the same conversation, which would reproduce the output. Not confirmed; check whether resume keeps the original prompt and tool schema.
- **Proposed fix:**
  1. On `LoopError`, retry as a fresh `dispatch_task` with a compact prompt instead of `resume_task`.
  2. Check whether the builder's chat template enables tool calling for its model. If not, route single-line edits elsewhere.
  3. Return a structured error (`error_class: tool_format`) so the caller can decide the next step.

## F-2: builder sandbox cannot see the Market-Scanner repo

- **Task:** edit `ui/wireframes/strategy.html` in Market-Scanner.
- **Dispatches:** `b4cf7bee84` and `0feeb620b3`. Both failed on the path. A separate dispatch timed out (see F-3).
- **Why fallback:** the builder could not reach the target file.
- **RCA (confirmed in part):** the builder sandbox path is `/workspace/tokenfrugal/Market-Scanner`, which does not contain `ui/wireframes/`. Earlier in the session the builder also wrote to `/workspace/tokenfrugal/ui/...` instead of the repo, and that file stayed unchanged. The mapping from host path to sandbox path is not validated before the task runs.
- **Proposed fix:**
  1. Check that each task's target path exists in the sandbox before dispatch, and fail fast with the resolved path.
  2. Return the host-to-sandbox mapping in the dispatch reply.
  3. Mount or sync the project being worked on, or refuse paths outside the mount.

## F-3: dispatch timeout on a large file

- **Task:** align the Stocks list and Stock detail screens in `ui/wireframes/strategy.html` (630 KB, inline mock data).
- **Dispatches:** one timed out during the wireframe step.
- **Why fallback:** the timeout, plus F-2 path failures on the retries, left no working builder run.
- **RCA (hypothesis):** the task gave no line ranges for a 630 KB single-file HTML, which does not fit the 16k-32k local context. The gateway timed out instead of returning a bounded error.
- **Proposed fix:** for files over about 100 KB, the dispatch should pass line ranges or a grep-located section list. The gateway should reject oversized single-file inputs with a clear message.

## F-4: plan_add dependency IDs

- **Task:** add plan tasks with dependencies.
- **Symptom:** `plan_add` with depends `[1]` failed with "unknown dependencies". The real task ID was 45.
- **RCA (hypothesis):** the caller guessed sequence numbers. Dependencies appear to need the server's task IDs.
- **Proposed fix:** return the assigned IDs from `plan_add`, and accept dependencies by label as well as ID.

## Rule for callers (proposed)

Claude reports every Haiku fallback to this file: the task, the dispatch IDs, the error class, the RCA (marked as hypothesis if unverified), and the proposed fix. Fallbacks are not hidden.
