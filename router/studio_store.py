"""Studio write path: validate collected items and write each one once to Neo4j (docs/designs/studio-write-path.md).

Nothing here is reachable from a model role. The router calls write_items() with items it has validated.
Refusals never echo item content: they name the item's index and the rule it broke.
"""
import os

SOURCES = ("reddit", "hn", "rss", "youtube")
EMBED_DIMS = 384  # all-MiniLM-L6-v2
MAX_ITEMS = int(os.getenv("STUDIO_STORE_MAX_ITEMS", "500"))
LIMITS = {"title": 500, "url": 2048, "body": 20000, "item_id": 200}

# One statement per batch. MERGE on the unique key means a repeat store inserts nothing new,
# and ON CREATE keeps the first copy, so a repeat cannot overwrite it.
WRITE_CYPHER = """
UNWIND $items AS it
MERGE (i:StudioItem {key: it.key})
ON CREATE SET i.source = it.source, i.item_id = it.item_id, i.title = it.title,
              i.url = it.url, i.body = it.body, i.embedding = it.embedding,
              i.collected_at = datetime(), i.run_id = $run_id
RETURN count(i) AS n
"""


class StoreRefused(Exception):
    """Raised with a message that names an item index and a rule, never the item's content."""


def make_key(source: str, item_id: str) -> str:
    return f"{source}|{item_id}"


def validate_items(items: list) -> list[dict]:
    """Return clean rows ready for WRITE_CYPHER. Refuse the whole batch on the first bad item."""
    if not isinstance(items, list) or not items:
        raise StoreRefused("store needs a non-empty list of items")
    if len(items) > MAX_ITEMS:
        raise StoreRefused(f"store takes at most {MAX_ITEMS} items per run")
    rows = []
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            raise StoreRefused(f"item {idx}: not an object")
        source = it.get("source")
        if source not in SOURCES:
            raise StoreRefused(f"item {idx}: unknown source")
        item_id = it.get("item_id")
        if not isinstance(item_id, str) or not item_id.strip() or len(item_id) > LIMITS["item_id"]:
            raise StoreRefused(f"item {idx}: item_id missing or too long")
        row = {"source": source, "item_id": item_id, "key": make_key(source, item_id)}
        for field in ("title", "url", "body"):
            value = it.get(field, "")
            if value is None:
                value = ""
            if not isinstance(value, str):
                raise StoreRefused(f"item {idx}: {field} is not text")
            if len(value) > LIMITS[field]:
                raise StoreRefused(f"item {idx}: {field} is over {LIMITS[field]} characters")
            row[field] = value
        if not row["title"].strip():
            raise StoreRefused(f"item {idx}: title is empty")
        emb = it.get("embedding")
        if not isinstance(emb, list) or len(emb) != EMBED_DIMS:
            raise StoreRefused(f"item {idx}: embedding must have {EMBED_DIMS} numbers")
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in emb):
            raise StoreRefused(f"item {idx}: embedding has a non-number")
        row["embedding"] = [float(x) for x in emb]
        rows.append(row)
    keys = [r["key"] for r in rows]
    if len(set(keys)) != len(keys):
        raise StoreRefused("batch has the same item twice")
    return rows


def write_items(run_write, items: list, run_id: int | None) -> int:
    """Validate, then write in one transaction through run_write(cypher, params) -> int.

    run_write is the router's Neo4j transaction wrapper in production and a fake in tests.
    Returns the number of items the statement reported (MERGE counts each item once, new or existing).
    """
    rows = validate_items(items)
    return int(run_write(WRITE_CYPHER, {"items": rows, "run_id": run_id}))
