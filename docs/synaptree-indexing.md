# Synaptree indexing: how it works, what failed, and how to keep it current

Status: draft, 2026-11-07. Owner: whoever runs the Claude Code sessions for this repo.

## 1. What the index is

`synaptree` is the MCP server named in `CLAUDE.md` (section "Code intelligence"). It keeps a code graph of the project `tokenfrugal`. Claude and the delegated roles use it for `search_graph`, `trace_path`, `get_architecture` and `get_code_snippet`. The graph is only as current as the last index run.

## 2. What the index covers

- Project name: `tokenfrugal`.
- Root the server stores: `/workspace/tokenfrugal`. This is a path on the server, not a Windows path. The server cannot read `C:\...` paths.
- Last full index (2026-11-07): 258,209 nodes across 18,785 files. Before the refresh it held 149,837 nodes across 13,777 files, last synced 28 days earlier.

## 3. What went wrong in the first attempt

Three separate problems were mixed together. Only one of them was a real failure.

1. **Windows path rejected (real failure).** Calling `index_repository` with `C:/Users/vaibh/Downloads/Projects/tokenfrugal` returned `root_path is not a directory: /app/C:/Users/...`. The server prefixes its own `/app` to any path it is given, so a Windows path can never work. Use the server's own root, `/workspace/tokenfrugal`.
2. **Output overflow (not a failure of the index).** The second call with `/workspace/tokenfrugal` returned a 3.5 MB log. The tool saved it to a file instead of showing it. The index had already been refreshed: a later `index_status` showed `last_sync` as today and the counts above. The error text looked like a failure, but the index was updated.
3. **Stale counts earlier in the session (explained by 1 and 2).** The first `index_status` check showed 28 days of age because nothing had refreshed the index since that date. This was never a bug in the index, only a missed refresh.

## 4. The rule

`CLAUDE.md` says: "Re-index after merges." Nothing currently does this automatically, so it depends on someone remembering. The index is therefore stale after most merges.

## 5. Proposed fix

Make the re-index a step that runs after each merge to `main`, and make it check its own result.

1. **After every PR merge to `main`:** run `index_repository` with `project = "tokenfrugal"` and `root_path = "/workspace/tokenfrugal"`. Do not pass a Windows path.
2. **Check the result:** call `index_status` and confirm `last_sync` is from the last few minutes and `nodes` is not lower than before. If `nodes` drops, stop and report it.
3. **Do not read the full `index_repository` output.** It can exceed the tool limit. Only the `index_status` check is needed.
4. **Automate it later:** a post-merge hook or CI job that calls the server is the durable version. It needs the server's HTTP or CLI interface, which is not confirmed. Until that is checked, the manual steps above are the process.

## 6. Limits to know about

- The index reflects `/workspace/tokenfrugal`. Worktrees such as `.claude/worktrees/media-generator-multiformat-tasks-8dc153` are not covered unless that path is mounted on the server. CLAUDE.md asks for the main checkout, not a worktree, for this reason.
- Index coverage of the media-generator render engine is not verified. A search for `media-generator` / `disk-gate` returned only router files and vendored code, so the render-engine modules may not be in the graph. The generated structure document in `docs/structure/PROJECT-STRUCTURE.md` reads the source directly and does not depend on the index.

## 7. Open items

- Confirm the server's indexing interface for a post-merge hook (section 5, step 4).
- Confirm whether `docker/media-generator/render-engine` is in the indexed files.
