"""Generate profiles/db-*.yaml (Docker MCP profiles) and profiles/dbhub/*.toml for the database roles.

One profile per role or level, each exposing at most 6 tools and no destructive ones (drop/delete/rename).
Dev roles write only to the scratch databases started from docker-compose.yml (127.0.0.1, reached through
host.docker.internal). Admin roles are read-only. SQL engines share the bytebase/dbhub image; admin profiles
mount a TOML with `readonly = true` (dbhub dropped its --readonly flag). The scratch password below is a
throwaway test value for the compose containers, never a real credential.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"
SCRATCH_PW = "tf_scratch_pw"  # must match the docker-compose.yml defaults
MSSQL_PW = "tf_Scratch_pw1"  # SQL Server demands a complex password; must match db-mssql in docker-compose.yml
HOST = "host.docker.internal"
MAX_TOOLS = 6
FORBIDDEN = ("drop", "delete", "rename", "remove", "truncate", "flush")  # no allowlist may contain these

IMAGES = {
    "dbhub": "bytebase/dbhub@sha256:ce8d2c76be9ca98cb36b28ac9cabd4d8a71abaae3939ecfe43e85ec00d0d57b4",
    "mongo": "mcp/mongodb@sha256:7ea2f40b6e1f704f386354d7eaa97776de6ca19e48133916c08e1bd9ee0c0086",
    "redis": "mcp/redis@sha256:e886a7e9990a084a20d46adcea8e7c89d539271f1b453ffabdce4c3f96f27fa0",
    "elastic": "mcp/elasticsearch@sha256:9c978b8277e32be0229e0c2f5c631e4106dd1c9c955ec361814588688582bcfd",
    "oracle": "mcp/oracle@sha256:1e73b1423220b9b49d904e031af9df5df5f2631686328b8136663eb9bd5f3957",
}

# SQL engines served by dbhub: DSN against the scratch container (oracle has no live scratch container).
DSN = {
    "postgres": f"postgres://tf:{SCRATCH_PW}@{HOST}:5432/tf_scratch?sslmode=disable",
    "mysql": f"mysql://root:{SCRATCH_PW}@{HOST}:3306/tf_scratch",
    "mssql": f"sqlserver://sa:{MSSQL_PW}@{HOST}:1433/master?sslmode=disable",
    "oracle": f"oracle://tf:{SCRATCH_PW}@{HOST}:1521/FREEPDB1?sslmode=disable",
}
SQL_TOOLS = {"dev": ["execute_sql", "search_objects"], "admin": ["execute_sql", "search_objects"]}

# profile id -> (engine, kind, tools). `kind` is dev (writes scratch only) or admin (read-only).
ROLES: dict[str, tuple[str, str, list[str]]] = {}
for _e in DSN:
    for _k in ("dev", "admin"):
        ROLES[f"db-{_e}-{_k}"] = (_e, _k, SQL_TOOLS[_k])
ROLES.update({
    "db-elastic-dev": ("elastic", "dev", ["esql", "get_mappings", "list_indices", "search"]),
    "db-elastic-admin": ("elastic", "admin", ["esql", "get_mappings", "get_shards", "list_indices", "search"]),
    "db-mongo-dev-l1": ("mongo", "dev", ["find", "aggregate", "count", "collection-schema", "explain", "list-collections"]),
    "db-mongo-dev-l2": ("mongo", "dev", ["insert-many", "update-many", "create-collection", "create-index", "find", "collection-schema"]),
    "db-mongo-admin-l1": ("mongo", "admin", ["list-databases", "list-collections", "collection-schema", "collection-indexes", "db-stats", "collection-storage-size"]),
    "db-mongo-admin-l2": ("mongo", "admin", ["explain", "find", "aggregate", "count", "mongodb-logs", "collection-indexes"]),
    "db-redis-dev-l1": ("redis", "dev", ["scan_keys", "get", "set", "hgetall", "hset", "lrange"]),
    "db-redis-dev-l2": ("redis", "dev", ["scan_keys", "lpush", "sadd", "expire", "json_get", "json_set"]),
    "db-redis-dev-l3": ("redis", "dev", ["create_vector_index_hash", "set_vector_in_hash", "hybrid_search", "search_redis_documents", "get_indexed_keys_number", "scan_keys"]),
    "db-redis-admin-l1": ("redis", "admin", ["info", "dbsize", "client_list", "scan_keys", "get_indexes", "get_index_info"]),
})
# Oracle MCP (read-only by design) replaces dbhub for oracle admin: 6 read-only tools.
ORACLE_ADMIN_TOOLS: list[str] = []  # filled when the live tool list is verified; dbhub covers oracle until then


def _env(pairs: dict) -> list:
    return [{"name": k, "value": v} for k, v in pairs.items()]


def _server(name: str, image: str, desc: str, tools: list[str], env: dict | None = None,
            command: list[str] | None = None, volumes: list[str] | None = None) -> dict:
    snap = {"name": name, "type": "server", "image": image, "description": desc, "title": name, "remote": {}}
    if command:
        snap["command"] = command
    if volumes:
        snap["volumes"] = volumes
    if env:
        snap["env"] = _env(env)
    return {"type": "image", "secrets": "default", "tools": list(tools), "image": image, "snapshot": {"server": snap}}


def toml_for(engine: str, kind: str) -> str:
    ro = "true" if kind == "admin" else "false"
    return (f'[[sources]]\nid = "default"\ndsn = "{DSN[engine]}"\n\n'
            f'[[tools]]\nname = "execute_sql"\nsource = "default"\nreadonly = {ro}\n\n'
            f'[[tools]]\nname = "search_objects"\nsource = "default"\n')


def build(pid: str) -> dict:
    engine, kind, tools = ROLES[pid]
    if engine in DSN:
        rel = f"dbhub/{engine}-{kind}.toml"
        srv = _server("dbhub", IMAGES["dbhub"], f"DBHub SQL access ({engine}, {kind})", tools,
                      command=["--transport", "stdio", "--config", "/dbhub.toml"],
                      volumes=[f"__REPO__/profiles/{rel}:/dbhub.toml:ro"])
    elif engine == "mongo":
        env = {"MDB_MCP_CONNECTION_STRING": f"mongodb://{HOST}:27017/tf_scratch"}
        if kind == "admin":
            env["MDB_MCP_READ_ONLY"] = "true"
        srv = _server("mongodb", IMAGES["mongo"], f"MongoDB ({kind})", tools, env)
    elif engine == "redis":
        env = {"REDIS_HOST": HOST, "REDIS_PORT": "6379"}
        srv = _server("redis", IMAGES["redis"], f"Redis ({kind})", tools, env)
    else:  # elastic
        env = {"ES_URL": f"http://{HOST}:9200"}
        srv = _server("elasticsearch", IMAGES["elastic"], f"Elasticsearch ({kind})", tools, env, command=["stdio"])
    return {"version": 1, "id": pid, "name": pid, "secrets": {"default": {"provider": "docker-desktop-store"}},
            "servers": [srv]}


def main() -> None:
    (PROFILES / "dbhub").mkdir(exist_ok=True)
    for engine in DSN:
        for kind in ("dev", "admin"):
            (PROFILES / "dbhub" / f"{engine}-{kind}.toml").write_text(toml_for(engine, kind), encoding="utf-8")
    for pid in ROLES:
        out = PROFILES / f"{pid}.yaml"
        out.write_text(yaml.safe_dump(build(pid), sort_keys=False, width=120), encoding="utf-8")
        print("wrote", out.name)


if __name__ == "__main__":
    main()
