# Persona routing plan

Status: planning. Last updated 2026-10-12.

A persona is a bundle of local model, skills and tools:

| Layer | What it is | Where it lives today |
| --- | --- | --- |
| Local model | `builder` (`qwen2.5-coder-yarn:3b`) or `thinker` (`llama3.2:3b-16k`), or a per-persona tag | `router/agents.yaml` `models`, `persona_models` |
| Skill | A `SKILL.md` attached to a persona | `persona_skills` (only `planning`, on the shepherd) |
| Tools | Allowlist per role, from Docker MCP profiles and native servers | `roles` in `router/agents.yaml` |

## Routing

- **Haiku is the router.** Haiku sees the task, picks a persona slug from `list_roles`, writes the isolated spec and acceptance criteria, and reviews the reply. Routing stays deterministic inside a persona.
- **The gateway validates.** An unknown slug is rejected with a short error. Requested tools must be on the persona's allowlist.
- **Fallback.** After one `resume_task` and one re-scope, Haiku does the task itself (CLAUDE.md, Haiku fallback).

## Gap to close

Routing is static today. The role comes from `divisions` and `overrides`, and Haiku does not choose a persona at runtime.

1. `dispatch_task` accepts an explicit persona slug from Haiku. Change in `router/config.py` and `router/server.py`.
2. Each persona gets an explicit skill list, not only the shepherd. Start with the entries in `persona_models`.
3. Log the chosen persona, model and tools per task, so routing can be checked against `bench/` results.

## Laya as a routing aid (not the router)

`convaiinnovations/laya` is an encoder classifier (ModernBERT-large, about 0.4B parameters, Apache 2.0). It answers typed choice, score and yes/no questions and never generates text. It cannot be a persona's local model and cannot call tools.

Possible roles, to be decided by measurement:

- **Persona pick as a choice question.** Score each candidate slug for a task. Runs without Ollama.
- **Escalate gate.** Decide when a task goes to Haiku instead of the local model.

Constraints from the model card, all self-reported:

- English root checkpoint takes 512 tokens. Multilingual takes 1,024 by default, 8,192 with `max_len=8192`.
- Banking77 is 0.425 and trails other models on high-option questions. Our persona set has about 40 slugs, so it is high-option.
- The card says the model ships overconfident (ECE 0.081 after per-domain temperature fitting).
- `action.act_probability` has no usable signal, so the escalate gate needs a different signal.

Adoption rule: laya is used only if it clearly beats the keyword baseline on our labels and stays within the 75%-of-best rule from `Benchmark/persona-model-selection.md`. Haiku stays the router either way.

## Evaluation (next step)

1. Label about 100 tasks with the correct persona slug, drawn from the agency-agents divisions in `router/agents.yaml`. Store as JSONL rows with `task` and `persona`.
2. Produce predictions from each router as JSONL rows with `persona`: keyword baseline, Haiku, and laya (if adopted for testing).
3. Score with `scripts/persona_routing_eval.py`:

   ```bash
   .venv/Scripts/python.exe scripts/persona_routing_eval.py --labels scratchpad/routing/labels.jsonl --predictions scratchpad/routing/haiku.jsonl
   ```

   Exit code 2 means some labels name slugs not in `agents.yaml`. Fix the labels before scoring.

## Open questions

- What "laya" means in the user's own setup (a second orchestrator or only a classifier). Currently treated as a classifier aid only.
- Whether `dispatch_task` should reject a persona whose model is not loaded, or load it.
