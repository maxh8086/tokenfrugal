# Studio tab and collector role split

* **Author:** Vaibhav Pavtekar
* **Date:** 2026-11-02
* **Status:** Brainstorm brief, not a design. Nothing is built.

## Overview

Split the single `content-analyst` role into per-source collector roles, then add a "Studio" tab to the tokenfrugal UI (`ui/server.js`, Node, no dependencies, no build step). In Studio the owner starts a collect, a shortlist of popular niche topics, an internal store, or a run of the whole content pipeline for one slug. An AI agent may start the same actions through one MCP tool. Every run is a tracked, resumable router task. Studio ends at a post draft or a plan for a video, infographic or image. Rendering stays in the ComfyUI tab.

Live collectors: Reddit and Hacker News, RSS, YouTube. LinkedIn, Instagram and Facebook, and X show as greyed cards that say why they are not collected. Collection is manual only; there is no schedule.

## Analysis

Six reviewers (design, codebase details, zoom-out, comprehension, implementation readiness, structure) read the concept against the code. Findings, worst first. Line references are in the reviewers' report and need re-checking when the design is written.

**Blockers**

1. **The UI cannot start a router task today.** The router is a stdio process started by a client such as Claude or Codex. `ui/server.js` only reads `events.jsonl`; its one way to talk to a router is the restart request file. A click does nothing if no client has started a router. Three ways out, each with a cost:
   * A request-file queue like the restart one: needs a live router, no task id comes back.
   * A router-side HTTP listener: new surface to secure.
   * The UI starts `python -m scripts.studio_run <action>`, as the benchmark button does: works with no router, but it is a second process outside the MCP router. Two reviewers called this the "calls directly" path the owner ruled out.
2. **The pipeline has no run unit and a resume bug.** `scripts/content_pipeline.py` finds finished stages by stage name, not by content slug, so a second topic can skip stages or resume the first topic's messages (one reviewer inferred this from call sites; confirm in `router/store.py`). The task table has no run id, slug or timestamps, and the event trail rotates, so "last run per role" cannot be derived.
3. **"Store internally" has no write path.** Qdrant runs read-only and Postgres uses a SELECT-only role. Writing to either needs a new service or credential and a security review, which contradicts "backend unchanged". Writing files to the shared media folder works today.
4. **The split leaves the analysis with no owner.** The analyst mission also clusters topics, scores momentum, writes ideas and calendars. Per-source collectors cannot do that. Five reviewers converged on collectors plus one analyst/curator role that merges, scores and holds the shared Qdrant and Postgres tools. The fate of the `content-analyst` slug (stored task rows and `mediahouse` team entry use it) is undecided.
5. **The verbs are undefined.** "Shortlist" is in no doc and overlaps analyst clustering and scoring. How a shortlisted item becomes a pipeline topic and slug is undefined.
6. **The end state has no producer.** The seven stages end at `07-final.md`, a 60-second executive script. No stage or role makes a "post draft" or a "video/infographic/image plan".

**Major risks**

* An agent calling "run pipeline" can spend GPU time unattended. Needs a confirm gate or a limit.
* Two clicks, or a click plus an agent call, can start the same stage twice. Needs one active run and a per-slug lock. Pipeline stages use local models, so they hit the ComfyUI GPU lease.
* Role data, "not collected" reasons, quota and secret presence need one source of truth (`tf-roles.yaml`, exported to `roles.json`), not a copy in the page. Held sources must be refused by `dispatch_task`, not just greyed out.
* YouTube quota has no counter. It can only be an estimate counted in the router and stored per Pacific day.
* Secret warnings must report presence only, never values or paths.
* Studio POST routes need the host check (today only the ComfyUI routes have it), a body cap, enumerated actions and a slug pattern. `/api/studio/` must be added to the Node-only route list so ComfyUI proxying cannot capture it.
* The existing seven-stage pipeline has never had a live run. Studio would sit on top of it.
* The `ui-ux-pro-max` design step required by the handoff is not yet done.
* "Publish" collides with the existing social-posting page. Use another word on the button.

## Goals vs. Non-Goals

* **In-Scope Goals:** split `content-analyst` into live per-source collectors plus an analyst/curator, held sources as data entries with a reason; a run backend with slug-scoped resume; one shared enqueue path for the UI and one MCP tool; a Studio tab with cards, last run, held reasons, secret warnings, estimated YouTube quota; manual triggers for collect, whole pipeline, then shortlist.
* **Out-of-Scope Non-Goals:** scheduled collection; posting to any social platform; image and video rendering (ComfyUI tab); Qdrant and Postgres writes until a write path is approved; a live log viewer; SSE for Studio; placeholder roles for held sources.

## Key Decisions & Staging for Next Steps

Decided by the owner: manual trigger only, from the UI or an agent through MCP; greyed cards with the reason for unavailable sources; rendering stays in the ComfyUI tab; the split is done first; no build step and no dependencies (phone support left to the designer; plain responsive layout).

Decided 2026-11-02 (open question 1): a Studio click reaches the router through a request-file queue, modelled on the MCP restart request. One file per run, atomic claim by a live router, polled from the router lifespan. The UI must show "no router running" when nobody claims a request. Tasks need a heartbeat so `sweep_stale` does not fail a long run.

Decided 2026-11-02 (open question 3): a seventh, collector-neutral analyst/curator role merges the collectors' output, scores it, writes the brief and holds the shared Qdrant and Postgres read tools. The collectors stay at 6 tools or fewer. Still open: the name of that role, and how long the old `content-analyst` slug resolves as an alias.

Decided 2026-11-02 (open question 2): one "run whole pipeline" is a single orchestrating router task per slug. Consequence for the design: the task must record its own per-stage progress (slug, stage, state) so a failure resumes at the failed stage, and it must send a heartbeat. The slug-scoped resume bug in `content_pipeline.py` still has to be fixed.

Decided 2026-11-02 (open question 4): "store internally" writes to the shared media folder and also to Qdrant and Postgres in version 1. This adds a write path that does not exist today: a write-capable Qdrant/Postgres service or image, a second, write-scoped credential and secret, a security review, and an idempotence rule (schema, collection name, dedupe key) so a resumed run never double-inserts. It contradicts "backend unchanged" in the handoff, so the split (Phase 1) and the write path become separate pieces with their own acceptance commands, and the write path has to land before the Studio store button.

Decided 2026-11-02 (open question 7): the existing `kalamanch` role turns `07-final.md` into the post draft or the video/infographic/image plan. Open: `kalamanch` is scoped to the video pipeline today, so its contract and skill must be widened to infographics and images, and the plan file's location and format must be fixed so the ComfyUI tab can read it. Plans for video should carry the "machine generated" posting note from the ComfyUI licence checklist.

Decided 2026-11-02 (remaining open questions):
* **Shortlist (5):** the owner shortlists by hand from the analyst/curator output. Studio shows the ranked output and lets the owner pick; no role auto-selects. Reading input for the ranking stays with the curator role.
* **Topic and slug (6):** the owner decides each time and types them. Whether stage 1 uses the collected data is still the owner's call per run, so the run form needs a "use collected data" choice.
* **Agent-started GPU runs (8):** allowed to run unattended. Progress is tracked periodically, so the run backend must publish progress (stage, state, heartbeat) that an agent or the owner can poll, and the lease check must still return a "waiting for GPU" state instead of failing.
* **Live pipeline run (9):** accepted as a prerequisite. The seven-stage pipeline gets a live end-to-end run before the Studio pipeline button. It uses local models and the GPU, so it needs its own go-ahead.
* **Quota (10):** an estimated counter, kept in the router and stored per Pacific day, labelled "estimated".
* **Inputs (12):** topics, niche list and RSS feed URLs are typed in the UI. The RSS tool fetches any URL it is given, so typed feeds need server-side checks (http and https only, no private or local addresses, length cap) and a saved list rather than a free text box at run time.
* **New role names (3):** the new roles use the `content-analyst-*` prefix (for example `content-analyst-reddit-hn`, `-rss`, `-youtube`, and a curator). Still open: the exact curator name and how long the old `content-analyst` slug resolves as an alias.
* **Role editor (11):** Studio is a tab and an entry in the role and team editor (`scripts/tf_roles_ui`), not a router role. The run backend has no role named `studio`; the orchestrating run is a task of the backend, started by the request-file queue.

Proposed staging (reviewers agreed on the order):

1. **Phase 1, role split, no UI.** Three live collectors plus an analyst/curator, at most 6 tools each, 12-tool exceptions removed, an alias window for `content-analyst`.
2. **Phase 2, run backend, no UI.** Fix slug-scoped resume, add a runs table, one enqueue function behind one `studio_run` MCP tool, quota counter, secret-presence check, one active run at a time.
3. **Phase 3, Studio tab.** Read-only first, then triggers: collect, whole pipeline, then shortlist.

Open questions for the owner (the first three block the design):

1. How does a click reach a router, and is "does nothing without a client" acceptable?
2. Is a pipeline run one orchestrating task or seven tasks, and what does resume mean?
3. Add an analyst/curator role? What happens to the `content-analyst` slug and for how long?
4. Does collect write to files or to the stores? Is a Qdrant or Postgres write path in scope?
5. What does shortlist read, with what criteria, and who owns it?
6. Where do the pipeline topic and slug come from, and does stage 1 use the collected data?
7. What produces the post draft or media plan: a new stage, `kalamanch`, or a file brief? How does the ComfyUI tab consume it?
8. May an agent start long GPU runs unattended, and with what limit?
9. Must the existing seven-stage pipeline have a live end-to-end run first?
10. Quota: an estimated local counter, or nothing in version 1?
11. Is Studio part of the role and team editor (`scripts/tf_roles_ui`) or separate?
12. Are topics, niche list and RSS feeds fixed config or typed in the UI? (RSS feed URLs typed in the UI are an egress risk.)

Simplest alternative the zoom-out reviewer raised: keep `dispatch_task` and `scripts/content_pipeline.py` as the way to start work, and make Studio a status board until it has been used.
