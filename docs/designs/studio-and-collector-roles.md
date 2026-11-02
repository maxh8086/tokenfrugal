# Studio tab and collector role split

*   **Author:** Vaibhav Pavtekar
*   **Status:** Design complete; awaiting egm-review (open questions remain)
*   **Date:** 2026-11-02
*   **Source:** [studio-concepts-brief.md](docs/designs/studio-concepts-brief.md)

--------------------------------------------------------------------------------

## Overview

Content work in tokenfrugal today starts in a Claude or Codex session, or from the command line with `scripts/content_pipeline.py`. There is no place in the tokenfrugal UI to see which content roles exist, which sources work, or what the last run produced.

This design adds a **Studio** tab to the UI (`ui/server.js` plus `ui/index.html`, Node, no dependencies, no build step). From Studio the owner can start four kinds of run:

*   **Collect:** gather public data from one source.
*   **Shortlist:** look at the analyst's ranked topics and pick the ones worth a post. The owner makes the pick; no role does it.
*   **Store:** write collected data to the shared media folder and to Qdrant and Postgres.
*   **Run pipeline:** run the seven content stages (research to executive rewrite) for one slug.

An AI agent can start the same four runs through one MCP tool. A run always goes through the router as a tracked task. Studio never calls a model or a server itself.

Two pieces of groundwork come first. The single `content-analyst` role is split into six collector roles (one per source, three live and three held) plus one analyst role that merges and scores, all named `content-analyst-*`. The store action needs a way to write to Qdrant and Postgres, which are read-only today.

Studio stops at a post draft or a plan for a video, infographic or image. The `media-generator` role writes the first draft and the image plans. Which role writes the video plan is an open question (`kalamanch` today). Making the image or video stays in the ComfyUI tab.

## The Problem

1.  **No view of the content roles.** To know whether Reddit, RSS or YouTube collection works, or when it last ran, the owner reads docs and logs.
2.  **One role does six jobs.** `content-analyst` collects from several sources and also clusters, scores and writes plans. It has more than the recommended 6 tools, so it carries a test exception. Any failure or missing secret hits the whole role.
3.  **The UI cannot start work.** The router is a process started by an MCP client. `ui/server.js` only reads its event log. Its one write path is the MCP restart request file, which has one slot and returns no task id.
4.  **The pipeline has no run identity.** `scripts/content_pipeline.py` decides what to skip by looking up the last finished task for a stage name, not for a content slug. A second topic can skip stages or resume the first topic's messages. The task table has no slug, run id or timestamps, and the event log rotates, so "last run" cannot be reliably shown.
5.  **The seven-stage pipeline has never had a live run.** Studio would sit on top of code that has only been tested offline.

The solution has four parts: a run backend that gives every run an identity and progress, a role split that gives each source its own status, a request-file queue that lets the UI and the MCP tool start runs, and the Studio tab that shows and controls all of it.

## Goals

Each goal has an acceptance condition that a person or a test can check.

1.  **G1. Six collector roles and one analyst role replace `content-analyst`.** The collectors are `content-analyst-reddit-hn`, `-rss`, `-youtube`, `-linkedin`, `-meta` (Instagram and Facebook) and `-x`. The first three are live. The last three are held: each is a role entry with a held flag and a reason, and `dispatch_task` refuses it. The analyst role merges and scores the collectors' output.
    *   *Accept:* preflight and the role loader pass with all seven entries; every live role has at most 6 tools; the 12-tool test exceptions are gone; a `dispatch_task` call for a held role returns a refusal that names the reason; Studio draws the three held roles as greyed cards with that reason.
2.  **G2. Every run has an identity and survives restarts.** A run records slug, action, stage, state, start time, last heartbeat and the task ids it used.
    *   *Accept:* a second slug runs all seven stages and does not reuse the first slug's stages; killing the process mid-stage and starting the run again resumes at the failed stage; "last run" is still correct after the event log rotates.
3.  **G3. One start path for the UI and the agent.** The UI writes a request file; a live router claims it and runs it; an MCP tool `studio_run` calls the same enqueue function.
    *   *Accept:* a UI click and a `studio_run` call create the same run record and the same task shape; with no router running, the UI shows "no router running" within 5 seconds.
4.  **G4. Studio shows the state of each source.** Each card shows role status, last run, estimated YouTube quota, missing-secret warnings, and for held sources a greyed card with the reason.
    *   *Accept:* removing a required secret file shows a warning before any click and never shows the secret value or its path; the quota figure is labelled "estimated" and resets at the Pacific date change.
5.  **G5. Store writes to files and to Qdrant and Postgres without duplicates.** This needs the write-path piece below.
    *   *Accept:* running Store twice on the same collected data inserts each item once.
6.  **G6. Runs are safe to leave unattended.** An agent may start a long run; progress is readable by polling.
    *   *Accept:* one active Studio run at a time; a start while ComfyUI holds the GPU lease gives a "waiting for GPU" state, not a failure; progress (stage, state, heartbeat age) is readable from one endpoint.
7.  **G7. The seven-stage pipeline gets one live end-to-end run before the Studio pipeline button ships.** This uses local models and the GPU, so it needs its own go-ahead from the owner.
    *   *Accept:* a run on a real topic reaches `07-final.md`; the result is recorded in the handoff.

## Non-Goals

*   **Scheduled collection.** Runs start only from a click or an agent call.
*   **Posting to any social platform.** Studio never publishes outside this machine. The word "publish" is not used on any button, because the UI already has a social-posting page.
*   **Making images or video.** That stays in the ComfyUI tab. Studio only writes the post draft or the plan.
*   **Auto-selecting the shortlist.** The owner picks.
*   **A live log viewer or a live event stream for Studio.** Studio polls one JSON endpoint and links to the existing task view.
*   **Collecting from the held sources.** The LinkedIn, Meta and X roles exist but stay refused until the owner decides on servers, terms and API cost. This design gives them no working tools.
*   **A role named `studio`.** Studio is a tab and an entry in the role and team editor, not a router role.
*   **A new database or ORM.** The run record extends the existing SQLite task store.

## Open Questions

*   **Curator name and alias window.** The analyst role's exact name under `content-analyst-*`, and how long the old `content-analyst` slug resolves as an alias (stored task rows and the `mediahouse` team entry use it).
*   **Who writes the video plan.** Decided: `media-generator` writes the first post draft and the image plans. Not decided: whether `kalamanch` keeps the video plan or `media-generator` takes it too. This reverses the earlier "use `kalamanch`" answer for images and drafts.
*   **Plan file location and format.** Where the plan is saved and in what format, so the ComfyUI tab can read it. Video plans carry the "machine generated" posting note.
*   **RSS feed checks.** Rules for feed URLs typed in the UI: http and https only, no private or local addresses, length cap, a saved list instead of free text at run time.
*   **Write path details.** Write-capable service, write-scoped secret, schema, collection name and dedupe key for Qdrant and Postgres, and whether only the analyst role gets those tools.

## Critical User Journeys (CUJs)

### CUJ 1: Collect from one source

*   **Given**: A router is running in some MCP client. The YouTube secret file exists. No other Studio run is active.
*   **When**: The owner opens Studio, picks the YouTube card, types a topic, and clicks Collect.
*   **Then**: The UI writes one request file. A router claims it within a few seconds and the card shows "running". When the task ends, the card shows the last-run time and result, and the estimated quota figure goes up by 100 per search and 1 per detail call.

### CUJ 2: An agent runs the whole pipeline unattended

*   **Given**: An agent has `studio_run`. ComfyUI holds the GPU lease.
*   **When**: The agent calls `studio_run` with action `pipeline`, a slug and a topic.
*   **Then**: The call returns a run id at once. `studio_status` shows `waiting_gpu`. When the lease is released, the run starts at stage 1 and reports stage, state and heartbeat age on each poll. If the router is killed in stage 4, starting the same slug again resumes at stage 4 and does not rerun stages 1 to 3.

### CUJ 3: Nobody is running a router

*   **Given**: No MCP client has started a router.
*   **When**: The owner clicks Collect.
*   **Then**: The request is written but nobody claims it. After the claim timeout the card shows "no router running", the request file is removed, and no run record is left in `running`.

### CUJ 4: A held source

*   **Given**: `content-analyst-x` has a held flag and a reason.
*   **When**: The owner looks at the X card, or an agent calls `dispatch_task` for that role.
*   **Then**: The card is grey with the reason and has no Collect button. `dispatch_task` returns a refusal that names the reason. No task row is created.

### CUJ 5: From ranked topics to a plan

*   **Given**: The analyst role has written a ranked topic list for the collected data.
*   **When**: The owner picks a topic by hand, types the slug, and runs the pipeline with "use collected data" on. After `07-final.md` exists, the owner asks for an image plan.
*   **Then**: The `media-generator` role writes the image plan into `content/<slug>/`. The ComfyUI tab can open it. Studio does not render anything.

## Technical Plan (Architecture)

### Decided: the UI reads run state from SQLite with `node:sqlite`

`ui/server.js` opens `router/tasks.db` read-only with the built-in `node:sqlite` module and reads the `runs`, `tasks` and `quota` tables. There is no mirror file and no Python helper, so the UI and the router see the same data. Chosen by the owner over a JSON mirror file (can lag the database after a kill) and a Python helper (a process per poll).

What this costs, and how the design handles it:

*   **Node version.** `node:sqlite` needs Node 22.13 or newer to run without a flag, and it may print an "experimental" warning. Older Node has no module at all. The Studio routes check for the module when the UI starts. If it is missing, the Studio tab shows one message ("Studio needs Node 22.13 or newer") and the other tabs are unaffected. `scripts/doctor.py` reports the Node version and the fix command.
*   **Read-only.** The UI never writes to `tasks.db`. It opens the file read-only and writes only request files. The router is the only writer.
*   **Locking.** The database already uses WAL mode with a 30 s timeout, so a read while the router writes does not block either side.
*   **Schema coupling.** The UI now depends on column names in the `runs` and `quota` tables. Both tables are created by the router, and a test in Piece 4 fails if the UI's queries and the router's schema drift apart.

### The pieces

Studio is five changes that build on each other. Build order is 1, 2, 3, 4, 5, with a live pipeline run (G7) between 4 and 5.

**Piece 1. Role split (no UI, backend unchanged).** `router/tf-roles.yaml` replaces `content-analyst` with seven entries: `content-analyst-reddit-hn`, `-rss`, `-youtube`, `-linkedin`, `-meta`, `-x`, plus the analyst role (name open). A role entry may carry `held: "<reason>"`. The loader keeps held roles in the role list so the editor and Studio can show them, and `dispatch_task` refuses them before it creates a task row. Each live collector has at most 6 tools. The analyst role holds the shared Qdrant and Postgres read tools. The `mediahouse` team lists all seven. The old slug resolves to the analyst role for a short window (length open) and logs a warning when used.

**Piece 2. Run backend.** A new module `router/studio.py` holds the run model and the one enqueue function.

*   *Run record.* A `runs` table in the existing `router/tasks.db`: run id, action, slug, topic, state, current stage, started, finished, last heartbeat, error, and the task ids used. The `tasks` table gets an additive `run_id` column, added the same way `trail` was added. States: `queued`, `waiting_gpu`, `running`, `done`, `failed`.
*   *Enqueue.* One function validates the action against a fixed list (`collect`, `store`, `pipeline`, plus `shortlist` read-only), checks the slug against the pattern `content_pipeline.py` already uses, caps the body size, and writes one file per request into a `studio_requests/` folder next to `events.jsonl`. Both the UI route and the MCP tool call this function, so they produce the same request.
*   *Claim.* A poll loop in the router lifespan, next to `reconnect.poll_loop`, claims a request with `os.replace` to a name that carries the router's process id. Only one router wins. The claimer checks that no run is `running` or `waiting_gpu` and, if one is, writes the new request back as `failed: busy`. It then creates the run record.
*   *Execution.* The claimer runs the action as one orchestrating run. For `pipeline` it runs the seven stages in order, in the router process, and records stage and state in the run record after each. It sends a heartbeat for the run on the same 30 s beat that running tasks use. Before each stage that uses a local model it checks the GPU lease and sets `waiting_gpu` instead of failing.
*   *Resume fix.* `store.last_for` gains a `run_id`/slug-scoped lookup, and `scripts/content_pipeline.py` uses it, so a second slug never reuses another slug's stages. The command-line script keeps working and creates a run record too.
*   *Agent tools.* `studio_run(action, slug, topic, …)` returns a run id. `studio_status(run_id)` returns state, stage and heartbeat age. Both are new router tools; adding them does not change the existing tool docstrings.
*   *Quota.* A `quota` table keyed by Pacific calendar day. The router adds 100 per YouTube search call and 1 per detail call when the call finishes. Studio labels the figure "estimated".
*   *Secret check.* A helper reports, for each role, which required secret names have no file. It returns names only. It never returns a value or a path.
*   *RSS feeds.* Typed feed URLs go to a saved list. The saver accepts http and https only, rejects hosts that resolve to private, loopback or link-local addresses, and caps length. Runs read the saved list, not free text. This guards the Studio path. It does not stop a model that is told to fetch another URL, because the RSS tool fetches whatever it is given.

**Piece 3. Write path (Qdrant and Postgres).** A write-capable service and a write-scoped secret, kept apart from the read-only ones. Only the analyst role gets the write tools (open). Each item gets a dedupe key (source, item id) so a resumed Store run inserts it once. This piece needs a security review before any code. If the review blocks it, the Store button is delayed and the rest of Studio ships without it.

**Piece 4. Studio tab, read-only first.** `ui/server.js` adds `/api/studio/*` routes. They get the same `hostOk` check the ComfyUI routes have, and `/api/studio/` goes in the Node-only route list so ComfyUI proxying cannot capture it. `ui/index.html` adds the tab: one card per collector role (live, running, held with reason, missing-secret warning), last run, estimated quota, the run form (slug, topic, "use collected data"), and the shortlist view. The first release only reads. The `ui-ux-pro-max` skill plans the layout before any UI code.

**Piece 5. Triggers.** The Collect, Store and Run pipeline buttons and the shortlist pick call the same enqueue function through `/api/studio/run`. Order: collect, then pipeline, then store once Piece 3 has passed review. A start while a run is active returns 409. A start while the GPU lease is held by ComfyUI is accepted and shows `waiting_gpu`.

**End state.** After `07-final.md`, `media-generator` writes the first post draft and the image plans. Who writes the video plan is open. Plans go under `content/<slug>/`; the file name and format are open and must be fixed so the ComfyUI tab can read them.

### Data flow

```text
 Studio tab (browser)                 MCP client (Claude / Codex)
        |                                      |
  POST /api/studio/run                   studio_run(...)
        |                                      |
        +-----------> enqueue (validate) <----+
                           |
                 studio_requests/<id>.json
                           |   atomic claim (os.replace)
                           v
              router lifespan poll loop  (a live router)
                           |
          runs table (tasks.db) + tasks.run_id
                           |
        +------------------+------------------+
        |                  |                  |
   collector role     pipeline stages     store (Piece 3)
   (dispatch)         1..7, GPU check     files + Qdrant/Postgres
        |                  |
   quota table        content/<slug>/ files
                           |
        runs / tasks / quota tables  --->  ui/server.js (node:sqlite, read-only)
                                      --->  Studio tab polls /api/studio/state
```

### Risks the plan accepts

*   A run needs a live router. With none, the UI says so; it cannot start one.
*   The Studio tab does not work on Node older than 22.13. It says so and leaves the other tabs alone.
*   An agent can start a long GPU run unattended. The one-active-run rule and the progress endpoint are the only limits.
*   Held roles are real entries. Each must keep its refusal until the owner changes it.

## Alternatives Considered

### Alternative A: Studio as a status board only

*   **Pros**: Smallest change. Studio would show role status, last run and held reasons, and work would still start through `dispatch_task` and `scripts/content_pipeline.py`. No queue, no run backend, no write path. The zoom-out reviewer proposed it as the simplest option.
*   **Cons**: The owner cannot start anything from the UI, and an agent still has no single call that starts a tracked run. The slug resume bug and the missing run identity stay. "Last run" still cannot be shown reliably.
*   **Reason for Rejection**: The owner wants the UI to manage content-role actions and wants agents and the UI to share one start path. A status board meets neither. The plan keeps this option as its first release: Piece 4 is read-only before Piece 5 adds buttons.

### Alternative B: The UI starts a Python process

*   **Pros**: Works with no router running, like the benchmark button. No request queue to build.
*   **Cons**: The run happens outside the MCP router, so it skips the router's task store, GPU lease check, heartbeat and role gating. Two start paths would exist, one for the UI and one for agents. Two reviewers called this the "calls directly" path the owner ruled out.
*   **Reason for Rejection**: It splits the system into two ways to run the same work. The request-file queue costs one thing in return: nothing starts when no router is running. The UI says so.

### Alternative C: A router-side HTTP listener

*   **Pros**: The UI gets a task id back at once and can ask for status directly.
*   **Cons**: A new network surface to secure, on a process that is started by each MCP client. Several routers can run at once, so each needs its own port and the UI has to find the right one.
*   **Reason for Rejection**: The request-file queue reuses a pattern the router already runs (`router/reconnect.py`: atomic claim by process id, polled from the lifespan). It adds no port. The cost is a few seconds of delay and no immediate task id; the run id is created at claim time and shown in the UI.

### Alternative D: Seven separate tasks per pipeline run

*   **Pros**: Each stage is already a task. Resume works at stage level with no new run record. No orchestrating task to keep alive.
*   **Cons**: Nothing groups the seven tasks, so "one run, one status" cannot be shown. An agent or the UI would have to start stage 2 after stage 1 ends, which leaves the order to whichever caller is alive. A killed caller leaves a half-run with nobody to continue it.
*   **Reason for Rejection**: The owner chose one orchestrating task per slug. It gives one state to poll and one place that decides what to resume. The cost is that the run record must keep its own stage progress and heartbeat.

### Alternative E: Keep one `content-analyst` role, or make only three roles

*   **Pros**: A single role means no split work. Three roles plus a held-sources list would avoid role entries that cannot run.
*   **Cons**: One role keeps the tool-cap exceptions and ties every failure and missing secret together. Three roles plus a list gives a second place to look when checking what exists.
*   **Reason for Rejection**: The owner chose six collector roles, with the three that cannot run held by a flag and a reason. The cost is three role entries that exist but are refused until the owner decides on servers, terms and API cost.

### Alternative F: Write to files only in version 1

*   **Pros**: Files in the shared media folder work today. No new service, no write-scoped secret, no security review, no dedupe rule.
*   **Cons**: Collected data would not reach Qdrant or Postgres, so the analyst role would have nothing to search across runs.
*   **Reason for Rejection**: The owner wants the store action to write to files and to Qdrant and Postgres. To keep the risk apart, the write path is its own piece (Piece 3). If its security review blocks it, the Store button is delayed and everything else ships.

### Alternative G: `kalamanch` writes every plan

*   **Pros**: One role owns the end state, and it already writes the video plan.
*   **Cons**: `kalamanch` is scoped to video. Widening it to infographics and images changes a role that other work depends on.
*   **Reason for Rejection**: The owner moved images and the first draft to `media-generator`. Who writes the video plan is still open.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **Security and privacy.**
    *   Studio POST routes check the host header, cap the body size, accept only the listed actions and a slug that matches the existing pattern, and write only request files.
    *   Secret warnings give names only, never values or file paths.
    *   The write path uses a write-scoped secret that no read-only role can see. It needs a security review before any code (Piece 3).
    *   RSS feed validation covers the Studio path only. It does not stop a model that is told to fetch another URL.
*   **Performance.** A claim takes about 1 s (the poll interval the restart request uses). The UI polls the database every few seconds while a run is active and slower when idle. One active run at a time keeps the GPU use predictable.
*   **Portability.** No hardcoded paths. Studio needs Node 22.13 or newer and says so when missing. Every new role, profile and secret name installs through `scripts/install_profiles.py` and is reported by `scripts/doctor.py`.
*   **Rollout and rollback.** Pieces ship one at a time behind the build order. The old `content-analyst` slug resolves to the analyst role during the alias window, so a rollback of Piece 1 is a revert of `router/tf-roles.yaml` and the profile files. The new `runs` and `quota` tables and the `run_id` column are additive, so older routers ignore them.

### Additional Resources

*   [studio-concepts-brief.md](./docs/designs/studio-concepts-brief.md): the brainstorm brief with reviewer findings.
*   [comfyui-gpu-lease.md](./docs/designs/comfyui-gpu-lease.md): the GPU lease behaviour Studio waits on, and the house style for this document.
*   [content-pipeline.md](./docs/content-pipeline.md) and [content-analyst.md](./docs/content-analyst.md): the current pipeline and the seven-point analyst mission being split.
*   `router/reconnect.py`: the request-file claim pattern Studio copies.

### Future Improvements

*   **Scheduled collection**, once manual runs have been used enough to trust.
*   **Turning on a held source** (LinkedIn, Meta, X) once the owner decides on servers, terms and cost.
*   **A live progress stream** for Studio, if polling proves too slow.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Build order: Piece 1, Piece 2, Piece 3, Piece 4, the live pipeline run (G7, needs the owner's GPU go-ahead), Piece 5. Each piece ends with its acceptance command and must pass the full offline suite (`PYTHONPATH=. python -m unittest discover -s tests -t . -q`) before the next starts. Execution is done by Haiku subagents against a written spec per task. The orchestrator reviews each diff and runs the checks. Pieces 1 and 3 can start in parallel only if they touch no shared file. They both touch `router/mcp_catalog.yaml`, so they run one after the other. Tokenfrugal MCP is not used for this repository.

### Piece 1. Role split

Acceptance: the tests below pass, `python -m router.preflight` (or the project's preflight entry) passes, and `list_roles` shows the seven new names under `mediahouse`.

#### 1. `router/tf-roles.yaml` (Modify)

*   **Type / Scope**: Role and team configuration.
*   **Proposed Changes**: Replace the `content-analyst` entry with `content-analyst-reddit-hn`, `-rss`, `-youtube`, `-linkedin`, `-meta`, `-x` and the analyst role (name from the open question). Live collectors list at most 6 tools. The analyst role lists the shared Qdrant and Postgres read tools. The three held roles carry `held: "<reason>"`. `mediahouse` lists all seven. An alias map entry sends the old `content-analyst` slug to the analyst role for the alias window. Follow the tf-roles change checklist (tool cap 6, skill text under 1200 characters, `scripts/gen_db_profiles.py` first where it applies).

#### 2. `router/config.py` (Modify)

*   **Type / Scope**: Role loader (`load_tf_roles`, `resolve_role`).
*   **Proposed Changes**: Accept the `held` key, keep held roles in the loaded role set, and resolve the old slug through the alias map with a logged warning. Roles with `held` skip the tool-count and profile checks.

#### 3. `router/server.py` (Modify)

*   **Type / Scope**: `dispatch_task`.
*   **Proposed Changes**: Before creating a task row, return a short refusal that names the held reason when the resolved role is held. No row is created. (Other `server.py` changes for Piece 2 are listed there.)

#### 4. `router/preflight.py` (Modify)

*   **Type / Scope**: Startup checks.
*   **Proposed Changes**: Skip profile and tool checks for held roles. Keep the checks for live roles.

#### 5. `router/events.py` (Modify)

*   **Type / Scope**: `write_roles`, which exports `router/roles.json`.
*   **Proposed Changes**: Include `held` and its reason for each role, so the UI reads it from one place.

#### 6. `profiles/content-analyst.yaml` (Delete after alias window) and new `profiles/content-analyst-reddit-hn.yaml`, `profiles/content-analyst-rss.yaml`, `profiles/content-analyst-youtube.yaml`, `profiles/content-analyst-curator.yaml` (Create; curator file name follows the final role name)

*   **Type / Scope**: Docker MCP profiles with the `__WORKSPACE__` and `__MEDIA__` placeholders.
*   **Proposed Changes**: Split the current profile by source. Each collector gets only its own server and the shared media mount. The analyst profile gets the Qdrant and Postgres read servers. Held roles get no profile.

#### 7. `router/mcp_catalog.yaml` (Modify)

*   **Type / Scope**: Catalog of MCP servers and their allowlists.
*   **Proposed Changes**: Rename references from `content-analyst` to the new roles and move each tool to the role that uses it.

#### 8. `router/skills/role-content-analyst/SKILL.md` (Delete after alias window) and new `router/skills/role-content-analyst-reddit-hn/SKILL.md`, `-rss/SKILL.md`, `-youtube/SKILL.md`, `-curator/SKILL.md` (Create)

*   **Type / Scope**: Role skill text, each under 1200 characters.
*   **Proposed Changes**: One source each. The curator skill carries the merge, scoring, ranking and brief-writing parts of the current seven-point mission.

#### 9. `router/media_workspace.py` and `router/profile_sync.py` (Modify)

*   **Type / Scope**: Shared media folder wiring.
*   **Proposed Changes**: Update the role-name lists (media_workspace docstring and any mount list) so the new profiles get the `__MEDIA__` mount.

#### 10. `scripts/tf_roles_ui.py` (Modify)

*   **Type / Scope**: Role and team editor.
*   **Proposed Changes**: Show held roles with their reason as read-only, and add the Studio entry the owner asked for. Studio is an editor entry, not a router role.

#### 11. Tests (Modify): `tests/test_preflight.py`, `tests/test_router.py`, `tests/test_media_workspace.py`, `tests/test_teams.py`, `tests/test_tf_roles_skills.py`, `tests/test_role_contracts.py`

*   **Type / Scope**: Existing unit tests that name `content-analyst`.
*   **Proposed Changes**: Replace the name with the new role list. Remove the 12-tool exception for the old role. Assert at most 6 tools for every live role, `mediahouse` lists the seven names, and every old reference either resolves through the alias or is gone.

#### 12. `tests/test_held_roles.py` (Create)

*   **Type / Scope**: Unit test.
*   **Proposed Changes**: A `dispatch_task` call for each held role returns the refusal text with the reason and creates no task row. The old slug resolves to the analyst role and logs a warning.

#### 13. `docs/content-analyst.md`, `docs/technical.md`, `docs/content-pipeline.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: Describe the split, the held roles, the alias window and the new profile names. `docs/technical.md` lines about the shared media folder name the new roles.

### Piece 2. Run backend

Acceptance: the Studio tests below pass, a pipeline run for a second slug does not reuse the first slug's stages, and `studio_status` returns state for a killed-and-restarted run.

#### 14. `router/studio.py` (Create)

*   **Type / Scope**: Python module.
*   **Proposed Changes**: `enqueue(action, params)` validates and writes one request file. `claim_once()` claims a file with `os.replace`, checks that no run is active, creates the run record and executes it. `poll_loop()` calls `claim_once` every second. The executor runs `collect`, `store` and `pipeline` as one orchestrating run, records stage and state, sets `waiting_gpu` while the GPU lease is held, and expires an unclaimed request after the claim timeout. Also holds the saved RSS feed list with the validation rules, and the secret-presence report.

#### 15. `router/store.py` (Modify)

*   **Type / Scope**: SQLite task store.
*   **Proposed Changes**: Add the `runs` table and the `quota` table to `_db()`, an additive `run_id` column on `tasks`, run helpers (create, update stage, beat, finish, list, get), and a slug- and run-scoped version of `last_for`. `sweep_stale` also fails runs whose heartbeat stopped.

#### 16. `router/server.py` (Modify)

*   **Type / Scope**: Router lifespan and tools.
*   **Proposed Changes**: Start `studio.poll_loop` next to `reconnect.poll_loop` and cancel it on exit. Add `studio_run` and `studio_status` tools. `router/server.py` is a heavily used file, so these changes stay in the lifespan and two new tool functions.

#### 17. `router/loop.py` (Modify)

*   **Type / Scope**: Tool-calling loop. It has uncommitted changes from other work, so this edit is made on top of them.
*   **Proposed Changes**: After a YouTube search or detail call finishes, call the quota recorder. No other behaviour changes.

#### 18. `router/secrets_store.py` (Modify)

*   **Type / Scope**: Secret file helper.
*   **Proposed Changes**: Add a function that reports which of a given list of secret names have no file. It returns names only.

#### 19. `router/config.py` (Modify)

*   **Type / Scope**: Settings.
*   **Proposed Changes**: Add the request folder path, claim timeout and RSS limits as settings with defaults, so none are hard-coded elsewhere.

#### 20. `scripts/content_pipeline.py` (Modify)

*   **Type / Scope**: Command-line pipeline runner.
*   **Proposed Changes**: Use the run-scoped lookup so finished stages are matched to the slug, and create a run record so command-line and Studio runs look the same. Keep `--confirm` and the slug pattern.

#### 21. Tests (Create): `tests/test_studio_runs.py`, `tests/test_studio_queue.py`, `tests/test_studio_quota.py`, `tests/test_studio_feeds.py`; (Modify): `tests/test_content_pipeline.py`, `tests/test_content_stages.py`

*   **Type / Scope**: Unit tests.
*   **Proposed Changes**: Runs: a second slug runs all seven stages; a kill and restart resumes at the failed stage; last run survives `events.jsonl` rotation. Queue: two claimers, one wins; a second start is refused while a run is active; a start while the GPU lease is held shows `waiting_gpu`; an unclaimed request expires. Quota: 100 per search, 1 per detail, reset at the Pacific date change, labelled estimated. Feeds: non-http schemes, private and loopback hosts and over-long URLs are rejected. A UI start and a `studio_run` call create the same run shape. Secret warning never contains a value or path.

#### 22. `docs/content-pipeline.md` and `docs/technical.md` (Modify)

*   **Type / Scope**: Documentation.
*   **Proposed Changes**: Document run states, the request folder, `studio_run` and `studio_status`, and the slug-scoped resume.

### Piece 3. Write path (needs the security review first)

Acceptance: the review document is approved by the owner, then running Store twice on the same data inserts each item once.

#### 23. `docs/designs/studio-write-path.md` (Create)

*   **Type / Scope**: Design note and security review record.
*   **Proposed Changes**: Fixes what the open question leaves undecided: the write-capable service, the write-scoped secret name, the Postgres schema, the Qdrant collection name and the dedupe key (source, item id). No code in Piece 3 starts until the owner approves this note.

#### 24. `docker-compose.yml`, `router/mcp_catalog.yaml`, `profiles/content-analyst-curator.yaml` (Modify)

*   **Type / Scope**: Service, catalog and profile.
*   **Proposed Changes**: Add the write-capable service under the `tokenfrugal` compose project, a write-only catalog entry, and give only the analyst role the write tools.

#### 25. `router/secrets_store.py` and `scripts/doctor.py` (Modify)

*   **Type / Scope**: Secrets and checks.
*   **Proposed Changes**: Register the write-scoped secret name and report whether it exists, names only.

#### 26. `tests/test_store_idempotence.py` (Create)

*   **Type / Scope**: Test against a temporary database.
*   **Proposed Changes**: Store twice, assert one row per dedupe key. A live check against the real stores is part of the Verification Plan.

### Piece 4. Studio tab, read-only

Acceptance: the tab renders cards from a seeded database, shows the Node-version message when `node:sqlite` is missing, and the contract test passes.

#### 27. `docs/designs/studio-ui-plan.md` (Create)

*   **Type / Scope**: UI plan written with the `ui-ux-pro-max` skill before any UI code.
*   **Proposed Changes**: Layout of the cards, run form, shortlist view, greyed held cards and the states (idle, running, waiting for GPU, no router running, failed). Also checks contrast and phone width.

#### 28. `ui/server.js` (Modify)

*   **Type / Scope**: Node server.
*   **Proposed Changes**: Add `/api/studio/` to `NODE_API`. Add `GET /api/studio/state` (reads `runs`, `tasks`, `quota` and `roles.json` read-only with `node:sqlite`), `GET` and `POST /api/studio/feeds`. All Studio routes call `hostOk`. If `node:sqlite` cannot load, state returns a clear "needs Node 22.13" message.

#### 29. `ui/index.html` (Modify)

*   **Type / Scope**: Browser page.
*   **Proposed Changes**: Add the Studio tab per the UI plan. Read-only in this piece.

#### 30. `scripts/doctor.py` (Modify)

*   **Type / Scope**: Environment checker.
*   **Proposed Changes**: Report the Node version and the fix command when it is older than 22.13.

#### 31. `tests/test_studio_ui_contract.py` (Create)

*   **Type / Scope**: Python test that starts `ui/server.js` against a temporary database.
*   **Proposed Changes**: A bad Host header gives 403, a bad slug 400, and the UI's queries match the router's `runs` and `quota` columns.

### Live pipeline run (G7)

#### 32. `handoff.md` (Modify)

*   **Type / Scope**: Handoff notes.
*   **Proposed Changes**: Record the result of the first live seven-stage run on a real topic. This run uses local models and the GPU, so it starts only after the owner's separate go-ahead.

### Piece 5. Triggers

Acceptance: a UI click and a `studio_run` call create the same run shape; a second start while a run is active gives 409; a start while the GPU lease is held is accepted and shows `waiting_gpu`.

#### 33. `ui/server.js` (Modify)

*   **Type / Scope**: Node server.
*   **Proposed Changes**: Add `POST /api/studio/run`. It validates action and slug, caps the body, calls the host check, returns 409 when a run is active (read from the database), and writes the request file. It returns the request id; the run id appears once a router claims it.

#### 34. `ui/index.html` (Modify)

*   **Type / Scope**: Browser page.
*   **Proposed Changes**: Enable Collect, Run pipeline and the shortlist pick. Store is enabled only after Piece 3 has passed review. Button text avoids the word "publish".

#### 35. `tests/test_studio_ui_contract.py` (Modify)

*   **Type / Scope**: Contract test.
*   **Proposed Changes**: A second start returns 409; a start with the GPU lease held returns accepted; a start with no router leaves a request that expires and no run in `running`.

### Plan file for the end state (after the open questions are answered)

#### 36. `tf-roles.yaml` media-generator entry, `profiles/media-generator.yaml`, and `router/skills/kalamanch/` (Modify)

*   **Type / Scope**: Role contract for the post draft and plans.
*   **Proposed Changes**: Give `media-generator` the first-draft and image-plan contract and the plan file location and format. If `kalamanch` keeps the video plan, widen its skill only as far as the open question decides. Video plans carry the "machine generated" posting note.

### Verification Plan

*   **Compilation/Build**: None; the project has no build step. `node --check ui/server.js` for syntax.
*   **Unit Tests**: `PYTHONPATH=. python -m unittest discover -s tests -t . -q` after every piece. The flaky live-API Haiku test (`tests/test_haiku_toolcalls.py`) is known to fail 2 or 3 of 9 and is ignored.
*   **Static Analysis & Linting**: the project's existing lint pass (`router/lint.py` / `scripts/doctor.py`). The new modules must pass it.
*   **Test Coverage Requirement**: Every acceptance condition in Goals G1 to G7 maps to at least one named test above, except G5's live check and G7, which are live.
*   **E2E/Integration**:
    *   `python scripts/doctor.py` shows the Node version and the write secret names only.
    *   `python scripts/smoke.py` for the collector roles that have live servers.
    *   A live seven-stage pipeline run on a real topic that reaches `07-final.md`. It needs the owner's GPU go-ahead.
    *   A live Store run twice against the real Qdrant and Postgres after the Piece 3 review.
    *   A manual click-through of the Studio tab in the browser pane at desktop and phone width.

--------------------------------------------------------------------------------

*Drafted with EGM*
