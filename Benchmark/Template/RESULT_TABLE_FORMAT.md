# Result table format and style

Audience: people on GitHub who do not know this project. Use public, searchable MCP server names and persona names (the agency-agents slug) in the header row.


## Header (on every table)
Round id, date, hardware (GPU, VRAM), context window, runs per case (n), baseline round if any.

## Main table: one row per model, one column per case
| Sr | Model | Params (B) | Time (s, sum of case means) | Verified | Ran | write_function | fix_bug | ... |
|---|---|---|---|---|---|---|---|---|

- Cells show verified runs out of 2: `2/2` green, `1/2` amber, `0/2` red.
- Case column header: neutral case name, with the public MCP server and tool names under it, for example
  `Filesystem MCP server (mcp/filesystem)` / `read_file, edit_file`.
- Left columns (Sr to Ran) are frozen; only case columns scroll. Sortable, and filterable by model, minimum
  verified and case.
- A Notes line per failure class (400 BadRequest, no tool call, CPU spill slowness).

## Combo table
| Primary | Passes alone | Remaining cases | Partner | Expected score | Measured score | Est. time (s) | Measured time (s) | Beats best solo? | Beats fastest? |
|---|---|---|---|---|---|---|---|---|---|

Cascade rule: the primary runs all cases; the partner runs only the cases the primary did not fully pass. Combo
time = primary time on all cases + partner time on the remaining ones. A combo wins only if score is at least the
best solo score and time is below that solo's time. Every row needs a real run; predictions are shown separately.

## Files per round
`tables/model-comparison.md` and `.html` (generated from `raw/*.json`), `tables/combos.md`, `responses/`.
