# Prompt: start fresh with new tools

Attach this file, `README.md` and `RESULT_TABLE_FORMAT.md`, then paste the text between the lines.

---
Start a new benchmark round that tests new or replacement MCP tools with the same models.

Tools to test (fill in): <public MCP server name, repo or image, tool names>
Replaces or adds to: <current server used by that case>

1. Create a round with `new_round.py`, named after the tool (e.g. `20261101-fetch-replacement`). Do not touch older rounds.
2. Add the tool as a Docker MCP profile entry or native server in a copy of the profile, pinned by digest. Ask me
   before installing images or editing `gateway/personas.yaml`.
3. Add or adjust only the cases that exercise the new tool, in a round-specific cases file. Keep the existing 16
   cases unchanged so scores stay comparable.
4. Run the models that scored at least 1/2 on the matching case in the baseline round, plus any I name. Same
   context, quantization and n=2.
5. Report per case and model: old tool vs new tool, verified runs and time. Column headers use the public server
   name and tool names.
6. Conclude only from measured results: which tool and model works, and which model to recommend when one fails.
   Show me the diff; do not push.
---
