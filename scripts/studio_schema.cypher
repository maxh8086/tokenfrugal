// Studio store schema (docs/designs/studio-write-path.md). Owner runs this once against the plan-store Neo4j.
// The router never runs DDL. 384 dimensions = all-MiniLM-L6-v2 (fastembed), the model in maxh8086/qdrant-mcp:1.

CREATE CONSTRAINT studio_item_key IF NOT EXISTS
  FOR (i:StudioItem) REQUIRE i.key IS UNIQUE;

CREATE VECTOR INDEX studio_item_vec IF NOT EXISTS
  FOR (i:StudioItem) ON (i.embedding)
  OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};
