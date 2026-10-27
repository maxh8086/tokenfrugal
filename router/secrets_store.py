"""Docker secret files: the one credential store for tokenfrugal.

Each secret is one file in the secrets directory (default `~/.docker/mcp/secrets`, outside the repo), named exactly
as the secret and holding only its value. docker-compose.yml mounts these files at /run/secrets/NAME. The router reads
them here. Config refers to a secret as `docker-secret:NAME`. Values never go in repo files, logs or chat.
"""
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

SECRETS_DIR = Path(os.getenv("TF_SECRETS_DIR") or Path.home() / ".docker" / "mcp" / "secrets")
REF_PREFIX = "docker-secret:"
NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")  # also keeps names from escaping SECRETS_DIR
GENERATED = {
    "CRAWL4AI_API_TOKEN": lambda: secrets.token_hex(32),
    "SEARXNG_SECRET": lambda: secrets.token_hex(32),
    "NEO4J_AUTH": lambda: "neo4j/" + secrets.token_hex(16),
}


class SecretStoreError(RuntimeError):
    pass


def _path(name: str) -> Path:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise SecretStoreError(f"invalid secret name: {name!r}")
    return SECRETS_DIR / name


def _restrict(path: Path) -> None:
    """Owner-only access where the OS allows it: POSIX mode bits, or a Windows ACL through icacls."""
    try:
        if os.name == "nt":
            user = os.environ.get("USERNAME")
            if user:
                grant = f"{user}:(OI)(CI)F" if path.is_dir() else f"{user}:F"
                subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", grant],
                               capture_output=True, check=False, timeout=20)
        else:
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
    except (OSError, subprocess.SubprocessError):
        pass  # best effort; the directory is still outside the repo


def get(name: str) -> str | None:
    """The stored value, or None if the secret file does not exist."""
    try:
        return _path(name).read_text(encoding="utf-8").rstrip("\r\n")
    except FileNotFoundError:
        return None


def put(name: str, value: str) -> None:
    if not value:
        raise SecretStoreError("empty value")
    path = _path(name)
    SECRETS_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    _restrict(SECRETS_DIR)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:  # value only, no trailing newline
        f.write(value)
    _restrict(path)


def delete(name: str) -> bool:
    try:
        _path(name).unlink()
    except FileNotFoundError:
        return False
    return True


def names() -> list[str]:
    if not SECRETS_DIR.is_dir():
        return []
    return sorted(p.name for p in SECRETS_DIR.iterdir() if p.is_file() and NAME_RE.match(p.name))


def resolve(value: str) -> str:
    """`docker-secret:NAME` -> the stored value. Anything else is returned unchanged.
    A missing secret raises SecretStoreError, so a server never starts with an empty credential by accident."""
    if not isinstance(value, str) or not value.startswith(REF_PREFIX):
        return value
    name = value[len(REF_PREFIX):]
    got = get(name)
    if not got:
        raise SecretStoreError(f"secret '{name}' is not set; write its value to {SECRETS_DIR / name}")
    return got


def resolve_env(env: dict[str, str]) -> dict[str, str]:
    return {k: resolve(v) for k, v in env.items()}


def ensure_generated() -> list[str]:
    """Create the random backend secrets that are missing. Returns the names created (never the values)."""
    created = []
    for name, make in GENERATED.items():
        if get(name) is None:
            put(name, make())
            created.append(name)
    return created


def _cli(argv: list[str]) -> int:
    usage = ("usage: python -m router.secrets_store {set NAME (value on stdin) | get-path NAME | list | "
             "delete NAME | ensure-generated | export-paths}")
    if len(argv) < 1:
        print(usage, file=sys.stderr)
        return 2
    cmd, name = argv[0], (argv[1] if len(argv) > 1 else None)
    try:
        if cmd == "set" and name:  # the value is read from stdin and never echoed
            put(name, sys.stdin.read().rstrip("\r\n"))
            print(f"stored {name}")
        elif cmd == "get-path" and name:  # the file path only; the value is never printed
            path = _path(name)
            if not path.is_file():
                print(f"{name}: not set", file=sys.stderr)
                return 1
            print(path)
        elif cmd == "list":
            print("\n".join(names()) or "(none)")
        elif cmd == "delete" and name:
            print(f"deleted {name}" if delete(name) else f"{name} was not set")
        elif cmd == "ensure-generated" and not name:  # prints the names created, never the values
            print("\n".join(ensure_generated()))
        elif cmd == "export-paths" and not name:  # the one variable the launcher needs for docker compose
            print(f"TF_SECRETS_DIR={SECRETS_DIR}")
        else:
            print(usage, file=sys.stderr)
            return 2
    except SecretStoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
