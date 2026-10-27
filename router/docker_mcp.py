"""Docker MCP Toolkit helpers: gateway argv, profile loading, and catalog parameters.

A catalog entry may declare `params` for its Docker profile:
    params: {config: {"server.key": "value"}, secrets: {NAME: "docker-secret:NAME"}}
`config` values go to `docker mcp profile config <profile> --set key=value`; `secrets` go to the Docker
secret store via `docker mcp secret set NAME` (value on stdin, never on the command line). Any value may be a
`docker-secret:NAME` reference, read from its secret file by secrets_store.resolve() before it is handed to docker.
"""
import shutil
import subprocess
from pathlib import Path

import yaml

from . import secrets_store


class DockerMcpError(RuntimeError):
    pass


def docker_bin() -> str:
    path = shutil.which("docker")
    if not path:
        raise DockerMcpError("docker was not found on PATH; install Docker Desktop with the MCP Toolkit "
                             "(run: python scripts/doctor.py)")
    return path


# Profiles whose backend keeps state between tool calls (a browser tab, for example). Without --long-lived the
# gateway tears the backend down after each call, so a navigate is lost before the next call reads the page.
STATEFUL_PROFILES = frozenset({"browser"})


def gateway_argv(profile: str, cpus: str = "1", memory: str = "2Gb", docker: str | None = None) -> list[str]:
    argv = [docker or docker_bin(), "mcp", "gateway", "run", "--profile", profile, "--cpus", str(cpus), "--memory", memory]
    if profile in STATEFUL_PROFILES:
        argv.append("--long-lived")
    return argv


def profile_text(path: Path, workspace: str) -> str:
    """Profile YAML with the __WORKSPACE__ placeholder replaced by the workspace path."""
    return Path(path).read_text(encoding="utf-8").replace("__WORKSPACE__", workspace)


def load_profile(path: Path, workspace: str) -> dict:
    doc = yaml.safe_load(profile_text(path, workspace))
    if not isinstance(doc, dict) or "servers" not in doc:
        raise DockerMcpError(f"{path}: not a Docker MCP profile (missing 'servers')")
    return doc


def split_params(params: dict | None) -> tuple[dict, dict]:
    params = params or {}
    return dict(params.get("config") or {}), dict(params.get("secrets") or {})


def param_commands(profile: str, params: dict | None, docker: str | None = None) -> list[tuple[list[str], str | None]]:
    """(argv, stdin) pairs that push the declared parameters into Docker. docker-secret: refs are resolved here."""
    config, secrets = split_params(params)
    if not config and not secrets:
        return []
    docker = docker or docker_bin()
    cmds: list[tuple[list[str], str | None]] = []
    if config:
        argv = [docker, "mcp", "profile", "config", profile]
        for k, v in config.items():
            argv += ["--set", f"{k}={secrets_store.resolve(str(v))}"]
        cmds.append((argv, None))
    for name, ref in secrets.items():
        if not str(ref).startswith(secrets_store.REF_PREFIX):
            raise DockerMcpError(f"secret '{name}' must be a docker-secret: reference, not a literal value")
        cmds.append(([docker, "mcp", "secret", "set", name], secrets_store.resolve(ref)))
    return cmds


def apply_params(profile: str, params: dict | None) -> None:
    for argv, stdin in param_commands(profile, params):
        try:
            r = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=60)
        except FileNotFoundError as e:
            raise DockerMcpError(f"docker not runnable: {e}") from None
        if r.returncode:
            raise DockerMcpError(f"{' '.join(argv[1:4])} failed: {(r.stderr or r.stdout).strip()[:200]}")
