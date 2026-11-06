# Studio write path (Piece 3): design and security review

Status: **approved by the owner** (design only, Neo4j as the single store). Piece 3 code may start now, in the order of steps 24 to 26 of `docs/designs/studio-and-collector-roles.md`. Decided after approval: the embedding model is `all-MiniLM-L6-v2` (384 dimensions, already in `maxh8086/qdrant-mcp:1`). The Neo4j password is read from the secret file through `NEO4J_AUTH_FILE`.

Scope: the `studio_run(action="store")` action. It takes the collector and analyst output already written under the media workspace and writes each item once. Out of scope: the Store button in the UI (Piece 5).

## Current state (verified in the repo)

- `neo4j` (`neo4j:5-community`, loopback port 7697, profile `plan`) already runs for the plan store. It uses the secret `NEO4J_AUTH`. `router/plan.py` already creates unique constraints (`CREATE CONSTRAINT task_id ... REQUIRE t.id IS UNIQUE`) and uses `MERGE`.
- `docker-compose.yml` marks the `NEO4J_AUTH` wiring as BLOCKED: the image is not verified to read the auth value from a file. Any store write depends on fixing that first.
- `qdrant` and `mcp-qdrant` (read-only) exist for the content analyst. Nothing writes to Qdrant today. `mcp-postgres` reads a read-only `DATABASE_URI`. Nothing writes to Postgres today.

## Decision: one store, Neo4j (proposed by the owner)

The owner proposed Neo4j in place of separate Qdrant and Postgres writes. This note adopts that. Items, dedupe and vectors all go to one database, which removes the two-store write order and the partial-write case.

What Neo4j needs to hold:

- **Items and dedupe:** a `StudioItem` node per collected item, with a unique constraint on one key property.
- **Vector search:** a vector index on the item's embedding (Neo4j 5.11+ supports vector indexes in Community; **verify on the installed 5.x image**).

What it replaces:

| Was (earlier draft) | Now |
| --- | --- |
| Postgres `studio.items`, composite primary key | `StudioItem` node, unique `key` property |
| Qdrant `studio_items`, uuid5 point id | Vector index `studio_item_vec` on `StudioItem.embedding` |
| Two write secrets (`TF_QDRANT_WRITE_KEY`, `TF_STORE_DATABASE_URI`) | Reuse the existing Neo4j credential path (see Security below) |

## Data model

```cypher
CREATE CONSTRAINT studio_item_key IF NOT EXISTS
  FOR (i:StudioItem) REQUIRE i.key IS UNIQUE;
CREATE VECTOR INDEX studio_item_vec IF NOT EXISTS
  FOR (i:StudioItem) ON (i.embedding)
  OPTIONS {indexConfig: {`vector.dimensions`: $dims, `vector.similarity_function`: 'cosine'}};
```

- `key` = `source + "|" + item_id`. One property with a unique constraint is the dedupe key. Community Edition does not offer composite node-key constraints, so the key is a single computed string.
- Other properties: `source` (reddit, hn, rss, youtube), `item_id`, `title` (max 500), `url` (max 2048), `body` (max 20000), `collected_at`, `run_id` (router run id, for tracing only).
- The owner runs the constraint and index script (`scripts/studio_schema.cypher`) once. The router never runs DDL.
- `$dims` = 384, for `all-MiniLM-L6-v2` (fastembed; the same model `mcp-qdrant` already uses, so vectors match the analyst's search).

Write:

```cypher
UNWIND $items AS it
MERGE (i:StudioItem {key: it.key})
ON CREATE SET i.source = it.source, i.item_id = it.item_id, i.title = it.title,
              i.url = it.url, i.body = it.body, i.collected_at = datetime(), i.run_id = $run_id,
              i.embedding = it.embedding
RETURN count(i)
```

`MERGE` on the unique key means a repeated store inserts nothing new. `ON CREATE` keeps the first copy, so a repeat cannot overwrite it.

## Write order and failure

1. Validate the whole batch before any write. Refuse the batch on the first invalid item. Report the item index only, never its content.
2. Write the batch in one transaction. Neo4j rolls back the whole batch on failure, so there is no partial state to repair.
3. A resumed store run repeats steps 1 and 2 for the same files. The unique key makes it insert nothing new.

## Security

- **Who writes: the router, not a model role.** `studio.store()` runs in router code. It reads the collector and analyst files, validates each item against a fixed schema, and runs parameterised Cypher. No model role gets a write tool. Collected text is untrusted (Reddit, HN, RSS, YouTube) and can carry prompt injection. A model holding a write tool could be steered into writing arbitrary graph data.
- **Credential:** Neo4j Community has no per-database or per-label access control. The store writes with the same credential the plan store uses. A separate Neo4j user with a narrower role is possible but does not restrict which nodes it can touch. The mitigation is that only router code uses it, and the router validates every field.
- **Injection:** all values are passed as parameters. No string concatenation into Cypher. No DDL from the router.
- **Limits:** max 500 items per store run (`STUDIO_STORE_MAX_ITEMS`). Field length limits as above. Longer text is refused, not truncated. Only the schema's fields are written, never the collector's whole output. Source must be one of the four known sources.
- **Secrets:** names only in status and doctor output, as today. Store errors never echo a value or a record body.
- **Loopback:** the Neo4j port stays bound to 127.0.0.1.

## Acceptance (step 26)

- `tests/test_store_idempotence.py`: store the same batch twice against a fake Neo4j session that enforces the unique key, and assert one node per key. Hold the real driver out of the unit test.
- Live check against the real Neo4j: store twice, count `StudioItem` nodes, expect one per key. Not verified until the owner runs it. This also needs the `NEO4J_AUTH` wiring fixed (BLOCKED above).

## Open questions for the owner

1. **Confirm Neo4j as the only store** (this note's design). It removes Postgres and Qdrant from the write path.
2. **Embedding model (decided):** `all-MiniLM-L6-v2`, 384 dimensions. The analyst's search tool still reads from Qdrant until a Neo4j vector query replaces it, a read-path change to scope in Piece 4 or 5.
3. **Neo4j password (decided):** set `NEO4J_AUTH_FILE: /run/secrets/NEO4J_AUTH` in `docker-compose.yml` and remove the BLOCKED comment. The image's entrypoint reads it. The secret file must hold `neo4j/<password>`. The password applies only on first initialisation, so the existing `ts-mcp_neo4j_data` volume keeps its current password.
4. **Separate Neo4j user for the store?** Recommended only if you want credential isolation. It does not restrict node access on Community.

Nothing in this note has been run. The vector index support on the installed image and the `NEO4J_AUTH_FILE` fix are unverified until run. The embedding choice is decided.
