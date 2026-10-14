"""OS-native secret store (Windows Credential Manager, macOS Keychain, Linux Secret Service) via `keyring`.

Values never go in repo files, logs or chat. Config refers to a secret by name, either as `keyring:NAME`
in a native server's env block or as a known name such as `llm-api-key`. Names are kept in a small index
(gateway/secret_names.json, gitignored) because keyring cannot list entries on every backend.
"""
import json
import os
import secrets
import sys
from pathlib import Path

import keyring
from keyring.backends import fail, null

SERVICE = "tokenfrugal"
INDEX_FILE = Path(os.getenv("TOKENFRUGAL_SECRET_INDEX", Path(__file__).parent / "secret_names.json"))
REF_PREFIX = "keyring:"


class SecretStoreError(RuntimeError):
    pass


def _backend():
    kr = keyring.get_keyring()
    if isinstance(kr, (fail.Keyring, null.Keyring)):
        raise SecretStoreError(f"no usable OS secret store ({type(kr).__name__}); install a backend or run in a desktop session")
    return kr


def _index() -> list[str]:
    try:
        return sorted(set(json.loads(INDEX_FILE.read_text(encoding="utf-8"))))
    except (OSError, ValueError):
        return []


def _save_index(names: list[str]) -> None:
    INDEX_FILE.write_text(json.dumps(sorted(set(names)), indent=2), encoding="utf-8")


def get(name: str) -> str | None:
    """The stored value, or None if the name is unknown. Raises SecretStoreError if no store is usable."""
    _backend()
    return keyring.get_password(SERVICE, name)


def put(name: str, value: str) -> None:
    if not value:
        raise SecretStoreError("empty value")
    _backend()
    keyring.set_password(SERVICE, name, value)
    _save_index(_index() + [name])


def delete(name: str) -> bool:
    _backend()
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        return False
    _save_index([n for n in _index() if n != name])
    return True


def names() -> list[str]:
    return _index()


def resolve(value: str) -> str:
    """`keyring:NAME` -> the stored value. Anything else is returned unchanged.
    A missing secret raises SecretStoreError, so a server never starts with an empty credential by accident."""
    if not isinstance(value, str) or not value.startswith(REF_PREFIX):
        return value
    name = value[len(REF_PREFIX):]
    got = get(name)
    if got is None:
        raise SecretStoreError(f"secret '{name}' is not set; run: python -m gateway.secrets_store set {name}")
    return got


def resolve_env(env: dict[str, str]) -> dict[str, str]:
    return {k: resolve(v) for k, v in env.items()}


# Backend secrets that docker-compose and the launcher read from the process environment.
# Used to be lines in ~/.docker/mcp/mcp.env; the store is now the source of truth.
ENV_NAMES = ("CRAWL4AI_API_TOKEN", "SEARXNG_SECRET", "SONARQUBE_TOKEN", "SONARQUBE_ORG", "NEO4J_AUTH")
GENERATED = {
    "CRAWL4AI_API_TOKEN": lambda: secrets.token_hex(32),
    "SEARXNG_SECRET": lambda: secrets.token_hex(32),
    "NEO4J_AUTH": lambda: "neo4j/" + secrets.token_hex(16),
}


def ensure_generated() -> list[str]:
    """Create the random backend secrets that are missing. Returns the names created (never the values)."""
    created = []
    for name, make in GENERATED.items():
        if get(name) is None:
            put(name, make())
            created.append(name)
    return created


def export_env() -> dict[str, str]:
    """Values of ENV_NAMES that are set in the store. Only the launcher and gateway process call this."""
    out = {}
    for name in ENV_NAMES:
        try:
            value = get(name)
        except SecretStoreError:
            continue
        if value:
            out[name] = value
    return out


def _cli(argv: list[str]) -> int:
    import getpass
    usage = ("usage: python -m gateway.secrets_store {set NAME | get-status NAME | list | delete NAME | "
             "ensure-generated | export-env}")
    if len(argv) < 1:
        print(usage, file=sys.stderr)
        return 2
    cmd, name = argv[0], (argv[1] if len(argv) > 1 else None)
    try:
        if cmd == "set" and name:
            value = getpass.getpass(f"value for {name} (hidden): ")
            put(name, value)
            print(f"stored {name}")
        elif cmd == "get-status" and name:  # reports presence only; the value is never printed
            print(f"{name}: {'set' if get(name) else 'not set'}")
        elif cmd == "list":
            print("\n".join(names()) or "(none)")
        elif cmd == "delete" and name:
            print(f"deleted {name}" if delete(name) else f"{name} was not set")
        elif cmd == "ensure-generated" and not name:  # prints the names created, never the values
            print("\n".join(ensure_generated()))
        elif cmd == "export-env" and not name:  # NAME=value lines for the launcher to capture; do not echo them
            for k, v in export_env().items():
                print(f"{k}={v}")
        else:
            print(usage, file=sys.stderr)
            return 2
    except SecretStoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
