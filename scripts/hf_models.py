#!/usr/bin/env python3
"""Push, pull and check the quantized model files under models/ against private Hugging Face repos.

Subcommands:
  push   [--only SLUG ...]                 upload local model files (skips files already present with the same size)
  pull   [--models-dir DIR] [--only SLUG ...]  download missing or wrong-size files into DIR
  status                                    read-only comparison of local files and remote repos

Token: env HF_TOKEN, else the HUGGINGFACE key in <repo>/.env. The token is never printed.
Repo root: the parent of this script's folder, or env TF_REPO_ROOT.
Exit codes: 0 ok, 1 failure, 2 config or token error.
"""
import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

# huggingface_hub reads HF_HUB_OFFLINE at import time, so clear the value before importing it.
if os.environ.get("HF_HUB_OFFLINE") == "1":
    del os.environ["HF_HUB_OFFLINE"]

REPO_ROOT = Path(os.environ.get("TF_REPO_ROOT") or Path(__file__).resolve().parent.parent)
MANIFEST = Path(__file__).resolve().parent / "hf_models.json"
MARKER = ".hf_pulled.json"
TOKEN_MISSING = "HF token missing: set HUGGINGFACE in .env"


class ConfigError(Exception):
    pass


def _env_file_value(path: Path, key: str) -> str:
    """Read KEY=value from a .env file by hand. Handles BOM and CRLF; strips matching quotes."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            return v
    return ""


def _token() -> str:
    tok = os.environ.get("HF_TOKEN", "").strip()
    if not tok:
        tok = _env_file_value(REPO_ROOT / ".env", "HUGGINGFACE")
    if not tok:
        raise ConfigError(TOKEN_MISSING)
    return tok


def _manifest() -> list[dict]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return data["repos"]


def _select(repos: list[dict], only: list[str] | None) -> list[dict]:
    if not only:
        return repos
    known = {r["slug"] for r in repos}
    bad = [s for s in only if s not in known]
    if bad:
        raise ConfigError("unknown slug: " + ", ".join(bad))
    return [r for r in repos if r["slug"] in only]


def _models_dir(arg: str | None = None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("TF_MODELS_DIR")
    return Path(env) if env else REPO_ROOT / "models"


def _hub():
    try:
        import huggingface_hub  # noqa: F401
        from huggingface_hub import HfApi, create_repo, hf_hub_download, upload_file
        from huggingface_hub.utils import RepositoryNotFoundError
    except ImportError as e:
        raise SystemExit(f"error: huggingface_hub not installed ({e})")
    return HfApi, create_repo, hf_hub_download, upload_file, RepositoryNotFoundError


def _owner(api, token: str) -> str:
    return api.whoami(token=token)["name"]


def _remote_sizes(api, repo_id: str, token: str, not_found) -> dict[str, int]:
    """basename -> size for files in the remote repo. Empty dict when the repo does not exist yet."""
    try:
        info = api.model_info(repo_id, files_metadata=True, token=token)
    except not_found:
        return {}
    return {s.rfilename: int(s.size or 0) for s in (info.siblings or [])}


def _readme(repo: dict, local_sizes: dict[str, tuple[str, int]]) -> bytes:
    lines = [
        f"# tokenfrugal-{repo['slug']}",
        "",
        f"- slug: {repo['slug']}",
        f"- source: {repo['source']}",
        f"- license: {repo['license']}",
        "",
        "## Files",
        "",
    ]
    for base, (rel, size) in local_sizes.items():
        lines.append(f"- {base}: {size} bytes (models/{rel})")
    lines += ["", "Private mirror for tokenfrugal. Pull with scripts/hf_models.py pull.", ""]
    return "\n".join(lines).encode("utf-8")


def _file_map(repo: dict) -> dict[str, str]:
    """basename -> manifest path (relative to models/)."""
    return {Path(p).name: p for p in repo["files"]}


def cmd_push(args) -> int:
    HfApi, create_repo, _, upload_file, not_found = _hub()
    token = _token()
    api = HfApi(token=token)
    owner = _owner(api, token)
    models = _models_dir()
    rc = 0
    for repo in _select(_manifest(), args.only):
        repo_id = f"{owner}/tokenfrugal-{repo['slug']}"
        local = {}
        missing = []
        for rel in repo["files"]:
            p = models / rel
            if p.is_file():
                local[Path(rel).name] = (rel, p.stat().st_size)
            else:
                missing.append(rel)
        if missing:
            for rel in missing:
                print(f"error: {repo['slug']}: local file missing: models/{rel}")
            print(f"error: {repo['slug']}: skipped (fix the missing files first)")
            rc = 1
            continue
        try:
            create_repo(repo_id, private=True, exist_ok=True, token=token)
            print(f"repo {repo_id} (private)")
            remote = _remote_sizes(api, repo_id, token, not_found)
            for base, (rel, size) in local.items():
                if remote.get(base) == size:
                    print(f"  skip {base} (remote size matches, {size} bytes)")
                    continue
                print(f"  upload {base} ({size} bytes)")
                upload_file(path_or_fileobj=str(models / rel), path_in_repo=base, repo_id=repo_id,
                            repo_type="model", commit_message=f"Upload {base}", token=token)
            readme = _readme(repo, local)
            if remote.get("README.md") != len(readme):
                print("  upload README.md")
                upload_file(path_or_fileobj=readme, path_in_repo="README.md", repo_id=repo_id,
                            repo_type="model", commit_message="Update README", token=token)
            else:
                print("  skip README.md (unchanged size)")
        except Exception as e:  # noqa: BLE001 - report and continue with the next repo
            print(f"error: {repo['slug']}: {type(e).__name__}: {str(e)[:200]}")
            rc = 1
    return rc


def cmd_pull(args) -> int:
    HfApi, _, hf_hub_download, _, not_found = _hub()
    token = _token()
    api = HfApi(token=token)
    owner = _owner(api, token)
    models = _models_dir(args.models_dir)
    models.mkdir(parents=True, exist_ok=True)
    all_repos = _manifest()
    selected = _select(all_repos, args.only)
    full_run = {r["slug"] for r in selected} == {r["slug"] for r in all_repos}
    pulled: dict[str, dict] = {}
    rc = 0
    for repo in selected:
        repo_id = f"{owner}/tokenfrugal-{repo['slug']}"
        try:
            remote = _remote_sizes(api, repo_id, token, not_found)
            files: dict[str, int] = {}
            ok = True
            for base, rel in _file_map(repo).items():
                want = remote.get(base)
                if want is None:
                    print(f"error: {repo['slug']}: {base} not found in {repo_id}")
                    ok = False
                    break
                dest_dir = models / Path(rel).parent
                dest = dest_dir / base
                if dest.is_file() and dest.stat().st_size == want:
                    print(f"  skip {rel} (present, {want} bytes)")
                else:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    print(f"  download {rel} ({want} bytes)")
                    hf_hub_download(repo_id=repo_id, filename=base, local_dir=str(dest_dir), token=token)
                got = dest.stat().st_size if dest.is_file() else -1
                if got != want:
                    print(f"error: {repo['slug']}: size mismatch for {rel}: local {got}, remote {want}")
                    ok = False
                    break
                files[rel] = got
            if ok:
                pulled[repo["slug"]] = {"repo_id": repo_id, "files": files}
                print(f"ok {repo['slug']}")
            else:
                rc = 1
        except Exception as e:  # noqa: BLE001
            print(f"error: {repo['slug']}: {type(e).__name__}: {str(e)[:200]}")
            rc = 1
    if rc == 0 and full_run:
        _write_marker(models, pulled)
        print(f"wrote {models / MARKER}")
    elif rc == 0:
        print("partial pull (--only): marker not written; run pull without --only to record all repos")
    return rc


def _write_marker(models: Path, repos: dict) -> None:
    doc = {"repos": repos, "pulled_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    tmp = models / (MARKER + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    os.replace(tmp, models / MARKER)


def cmd_status(args) -> int:
    HfApi, _, _, _, not_found = _hub()
    token = _token()
    api = HfApi(token=token)
    owner = _owner(api, token)
    models = _models_dir()
    rc = 0
    for repo in _manifest():
        repo_id = f"{owner}/tokenfrugal-{repo['slug']}"
        try:
            remote = _remote_sizes(api, repo_id, token, not_found)
            remote_note = "" if remote else " (repo not found or empty)"
        except Exception as e:  # noqa: BLE001
            remote, remote_note = {}, f" (remote error: {type(e).__name__})"
            rc = 1
        print(f"{repo['slug']} -> {repo_id}{remote_note}")
        for rel in repo["files"]:
            base = Path(rel).name
            p = models / rel
            r_size = remote.get(base)
            l_size = p.stat().st_size if p.is_file() else None
            match = r_size is not None and l_size == r_size
            print(f"  {rel}: remote={'yes' if r_size is not None else 'no'}"
                  f" local={'yes' if l_size is not None else 'no'}"
                  f" sizes={'match' if match else 'differ'}"
                  f" (remote {r_size if r_size is not None else '-'}, local {l_size if l_size is not None else '-'})")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_push = sub.add_parser("push", help="upload local model files to private repos")
    p_push.add_argument("--only", nargs="+", metavar="SLUG")
    p_pull = sub.add_parser("pull", help="download model files into models/")
    p_pull.add_argument("--models-dir", metavar="DIR")
    p_pull.add_argument("--only", nargs="+", metavar="SLUG")
    sub.add_parser("status", help="read-only comparison of local and remote files")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "push":
            return cmd_push(args)
        if args.cmd == "pull":
            return cmd_pull(args)
        return cmd_status(args)
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
