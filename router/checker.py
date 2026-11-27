"""Deterministic checks on a repo after a delegated change: git status, patch applicability, lint and acceptance command.
Reads git and the filesystem only; no model calls."""
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from router import config
from router.lint import check_python
from router.workspace import Workspace, accept_env

MAX_BASELINE_BYTES = 200 * 1024 * 1024

@dataclass(frozen=True)
class Baseline:
    kind: Literal["git-tree", "hash"]
    tree: str | None
    files: dict[str, str | None]
    partial: bool

    @classmethod
    def from_json(cls, data: dict) -> "Baseline":
        return cls(data["kind"], data.get("tree"), data.get("files", {}), data.get("partial", False))

@dataclass(frozen=True)
class Changes:
    changed: tuple[str, ...]
    task_changed: tuple[str, ...]
    outside_scope: tuple[str, ...]
    scope_violation: tuple[str, ...]
    partial: bool

def _git(ws, *args, env=None):
    return subprocess.run(["git", "-C", ws.root, *args], capture_output=True, timeout=60, env=env)

def _git_tree(ws):
    """Build a snapshot through a temporary index, preserving the user's index."""
    with tempfile.TemporaryDirectory(prefix="tf-baseline-") as tmp:
        index = os.path.join(tmp, "index")
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = index
        try:
            r = _git(ws, "rev-parse", "--git-path", "index")
            if r.returncode == 0:
                src = r.stdout.decode("utf-8", "replace").strip()
                if src:
                    src = src if os.path.isabs(src) else os.path.join(ws.root, src)
                    if os.path.isfile(src): shutil.copyfile(src, index)
            r = _git(ws, "add", "-A", "--", ".", env=env)
            if r.returncode: raise RuntimeError(r.stderr.decode("utf-8", "replace"))
            r = _git(ws, "write-tree", env=env)
            if r.returncode: raise RuntimeError(r.stderr.decode("utf-8", "replace"))
            return r.stdout.decode("ascii").strip()
        except (OSError, subprocess.SubprocessError):
            raise

def _hash_files(ws, task_files):
    files = {}
    total = 0
    partial = True
    for name in sorted(set(task_files)):
        path = os.path.join(ws.root, name)
        try:
            size = os.path.getsize(path)
            total += size
            if total > MAX_BASELINE_BYTES:
                files[name] = None
                continue
            with open(path, "rb") as f: files[name] = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            files[name] = None
    return Baseline("hash", None, files, partial)

def _untracked_bytes(ws):
    r = _git(ws, "ls-files", "--others", "--exclude-standard", "-z")
    if r.returncode: raise RuntimeError(r.stderr.decode("utf-8", "replace"))
    total = 0
    for entry in r.stdout.decode("utf-8", "replace").split("\0"):
        if entry:
            try: total += os.path.getsize(os.path.join(ws.root, entry))
            except OSError: pass
    return total

def baseline(ws: Workspace, task_files: list[str]) -> Baseline:
    try:
        if _untracked_bytes(ws) > MAX_BASELINE_BYTES:
            b = _hash_files(ws, task_files)
            return Baseline(b.kind, b.tree, b.files, True)
        tree = _git_tree(ws)
        return Baseline("git-tree", tree, {}, False)
    except Exception:
        return _hash_files(ws, task_files)

def _path_key(path):
    path = path.replace("\\", "/")
    return path.casefold() if os.name == "nt" or sys.platform == "darwin" else path

def _glob_matches(path, pattern):
    """Match a slash-separated glob; only ** may cross directory boundaries."""
    path, pattern = _path_key(path), _path_key(pattern.replace("\\", "/"))
    pieces = ["^"]
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                i += 1
                if i + 1 < len(pattern) and pattern[i + 1] == "/":
                    i += 1
                    pieces.append("(?:.*/)?")
                else:
                    pieces.append(".*")
            else:
                pieces.append("[^/]*")
        elif char == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(char))
        i += 1
    pieces.append("$")
    return re.match("".join(pieces), path) is not None

def changes(ws, base: Baseline, task_files, must_not_change) -> Changes:
    try:
        if base.kind == "git-tree":
            now = _git_tree(ws)
            r = _git(ws, "diff", "--relative", "--no-renames", "--name-only", "-z", base.tree or "", now)
            if r.returncode: raise RuntimeError(r.stderr.decode("utf-8", "replace"))
            changed = tuple(sorted(set(p for p in r.stdout.decode("utf-8", "replace").split("\0") if p)))
        else:
            current = _hash_files(ws, base.files).files
            changed = tuple(sorted(p for p in base.files if base.files[p] != current[p]))
        task_keys = {_path_key(p) for p in task_files}
        task_changed = tuple(p for p in changed if _path_key(p) in task_keys)
        outside = tuple(p for p in changed if _path_key(p) not in task_keys)
        patterns = [p.replace("\\", "/") for p in must_not_change]
        violations = tuple(p for p in changed if any(_glob_matches(p, pattern) for pattern in patterns))
        return Changes(changed, task_changed, outside, violations, base.partial)
    except Exception:
        return Changes((), (), (), (), True)

def manifest_from(ch: Changes, packet: bool) -> str:
    result = manifest(set(), set(ch.changed))
    if packet and ch.outside_scope:
        result += "\noutside_scope: " + ", ".join(ch.outside_scope)
    return result

@dataclass(frozen=True)
class AcceptSpec:
    argv: tuple[str, ...]
    env: dict[str, str]
    source: Literal["packet", "argument", "task_line"]
    def to_json(self): return {"argv": list(self.argv), "env": self.env, "source": self.source}
    @classmethod
    def from_json(cls, d): return cls(tuple(d["argv"]), dict(d.get("env") or {}), d.get("source", "packet"))

@dataclass(frozen=True)
class AcceptParse:
    spec: AcceptSpec | None
    note: str = ""

@dataclass(frozen=True)
class AcceptResult:
    ok: bool
    exit: int | None
    secs: float
    first_error: str
    out: str
    env_kind: str
    stop: str | None

def parse_accept(text: str, source: str, ws: Workspace) -> AcceptParse:
    if not text: return AcceptParse(None, "no accept")
    span = re.search(r"`([^`]+)`", text)
    command = span.group(1) if span else text.strip()
    quote = None
    for ch in command:
        if ch in "'\"": quote = None if quote == ch else (ch if quote is None else quote)
        elif ch in "&|;><" and quote is None:
            return AcceptParse(None, "refused: accept must be one command; put several steps in a script")
    if quote: return AcceptParse(None, "refused: unclosed quote")
    lexer = shlex.shlex(command, posix=True); lexer.whitespace_split = True; lexer.escape = ""; lexer.commenters = ""
    try: tokens = list(lexer)
    except ValueError: return AcceptParse(None, "refused: unclosed quote")
    env = {}
    while tokens and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
        k, v = tokens.pop(0).split("=", 1); env[k] = v
    if not tokens: return AcceptParse(None, "no accept")
    if source == "task_line" and not span:
        base = re.split(r"[/\\]", tokens[0])[-1].lower()
        if not re.fullmatch(r"(?:python3?|py)(?:\.exe)?", base): return AcceptParse(None, "prose")
    return AcceptParse(AcceptSpec(tuple(tokens), env, source), "")

def accept_from_task(task_text: str, accept_arg: str, ws: Workspace) -> AcceptParse:
    if accept_arg: return parse_accept(accept_arg, "argument", ws)
    found = re.findall(r"^\s*(?:accept|acceptance):\s*(.*)$", task_text, re.I | re.M)
    return parse_accept(found[-1], "task_line", ws) if found else AcceptParse(None, "no accept")

def _resolve_argv0(argv, ws):
    first = argv[0]; base = re.split(r"[/\\]", first)[-1].lower()
    if base in ("python", "python.exe", "python3", "python3.exe", "py", "py.exe") and not ("/" in first or "\\" in first):
        if ws.venv:
            path = ws.venv / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
            return (str(path), *argv[1:]), "venv" if path.exists() else "missing"
        resolved = shutil.which(first) or shutil.which("python3") or shutil.which("python") or shutil.which("py")
        return ((resolved, *argv[1:]), "system-python") if resolved else (argv, "missing")
    if "/" in first or "\\" in first:
        p = Path(first); resolved = p if p.is_absolute() else Path(ws.root) / p
        return ((str(resolved), *argv[1:]), "venv" if ws.venv else "system-python") if resolved.exists() else (argv, "missing")
    envpath = os.pathsep.join([str(ws.venv / ("Scripts" if os.name == "nt" else "bin"))] if ws.venv else [])
    resolved = shutil.which(first, path=envpath + os.pathsep + os.environ.get("PATH", ""))
    if not resolved: return argv, "missing"
    return (resolved, *argv[1:]), "venv" if ws.venv else "system-python"

def _first_error(out, root):
    lines = out.splitlines()
    root_key = os.path.normcase(os.path.realpath(root))
    frames = []
    for i, line in enumerate(lines):
        m = re.search(r'File "([^"]+)", line (\d+)', line)
        if m:
            try:
                if os.path.commonpath((os.path.normcase(os.path.realpath(m.group(1))), root_key)) == root_key:
                    errors = [item for item in lines[i + 1:] if re.search(r"\b\w*(?:Error|Exception)\b", item)]
                    if errors:
                        frames.append(f"{os.path.relpath(m.group(1), root)}:{m.group(2)}: {errors[-1]}")
            except ValueError:
                pass
    if frames: return frames[-1][:100]
    for i in range(len(lines)-1, -1, -1):
        if re.search(r"\b\w*(?:Error|Exception)\b", lines[i]): return lines[i][:100]
    for line in lines:
        if line.startswith(("FAIL:", "FAILED")): return line[:100]
    return (lines[-1] if lines else "accept command failed")[:100]

def _missing_module(out, ws, task_files):
    m = re.search(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)", out)
    if not m: return False
    name = m.group(1).split(".")[0]
    if any(Path(f).stem == name for f in task_files) or (Path(ws.root)/(name+".py")).exists() or (Path(ws.root)/name).is_dir():
        return False
    try:
        import tomllib
        data = tomllib.loads((Path(ws.root)/"pyproject.toml").read_text(encoding="utf-8"))
        packages = data.get("tool", {}).get("setuptools", {}).get("package-dir", {}).get("", "")
        if packages and ((Path(ws.root)/packages/name).exists() or (Path(ws.root)/packages/(name+".py")).exists()): return False
    except (OSError, ValueError, AttributeError):
        pass
    return True

def _windows_job(proc):
    if os.name != "nt": return None
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job: return None
    info = ctypes.create_string_buffer(144)
    ctypes.cast(ctypes.byref(info, 16), ctypes.POINTER(wintypes.DWORD))[0] = 0x2000  # KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), len(info)) or not kernel.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))):
        _close_handle(job); return None
    return job

def _kill_tree(proc):
    if proc.poll() is not None: return
    try:
        if os.name == "nt" and getattr(proc, "_tf_job", None):
            _close_handle(proc._tf_job)
            proc._tf_job = None
        elif os.name == "nt": subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5)
        else: os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        proc.kill()

def _close_job(proc):
    job = getattr(proc, "_tf_job", None)
    if job:
        _close_handle(job)
        proc._tf_job = None

def _close_handle(handle):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle(handle)

def _excerpt(raw):
    return raw if len(raw) <= 1600 else raw[:400] + "\n...\n" + raw[-1200:]

def run_accept_spec(spec: AcceptSpec, ws: Workspace, timeout: float, cancel: threading.Event | None = None,
                    task_files: tuple[str, ...] = ()) -> AcceptResult:
    cancel = cancel or threading.Event(); started = time.monotonic()
    argv, env_kind = _resolve_argv0(list(spec.argv), ws)
    if env_kind == "missing" or not Path(argv[0]).exists() and ("/" in argv[0] or "\\" in argv[0]):
        return AcceptResult(False, None, 0, f"program not found: {spec.argv[0]}", "", env_kind, "env_missing")
    env = accept_env(ws, spec.env)
    proc = None
    try:
        with tempfile.TemporaryFile() as out:
            proc = subprocess.Popen(argv, cwd=ws.root, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                    start_new_session=os.name != "nt", creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0))
            proc._tf_job = _windows_job(proc)
            deadline = started + timeout
            try:
                while proc.poll() is None:
                    if cancel.is_set() or time.monotonic() >= deadline:
                        _kill_tree(proc); proc.wait(timeout=5)
                        secs = time.monotonic()-started
                        err = f"timed out after {int(timeout)}s" if not cancel.is_set() else "cancelled"
                        out.seek(0)
                        excerpt = _excerpt(out.read().decode("utf-8", "replace"))
                        return AcceptResult(False, None, secs, err, excerpt, env_kind, "out_of_time")
                    time.sleep(.05)
                out.seek(0); raw = out.read().decode("utf-8", "replace")
            finally:
                if proc.poll() is None:
                    _kill_tree(proc)
                _close_job(proc)
    except OSError as e:
        return AcceptResult(False, None, time.monotonic()-started, f"program not found: {spec.argv[0]}", str(e)[:100], env_kind, "env_missing")
    excerpt = _excerpt(raw)
    missing = _missing_module(raw, ws, task_files)
    ok = proc.returncode == 0
    return AcceptResult(ok, proc.returncode, time.monotonic()-started, "" if ok else _first_error(raw, ws.root), excerpt, env_kind,
                        "env_missing" if missing else None)


def files_changed(repo: str) -> list[str]:
    r = subprocess.run(["git", "-C", repo, "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                       capture_output=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip())
    entries = r.stdout.decode("utf-8", "replace").split("\0")
    paths = set()
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        xy, path = e[:2], e[3:]
        if "R" in xy or "C" in xy:
            # rename/copy: the next NUL-separated field is the origin path; keep the new one
            i += 1
        paths.add(path)
    return sorted(paths)


def manifest(before: set[str], after: set[str], cap: int = 20) -> str:
    """One line naming the files a run changed (after minus before), sorted, with a count of any beyond cap."""
    new = sorted(after - before)
    if not new:
        return "files_changed: none"
    more = f" (+{len(new) - cap} more)" if len(new) > cap else ""
    return f"files_changed: {', '.join(new[:cap])}{more}"


def diff_applies(diff_text: str, repo: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(["git", "-C", repo, "apply", "--check", "-"], input=diff_text,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    except subprocess.TimeoutExpired:
        return False, "timed out after 30s"
    if r.returncode == 0:
        return True, ""
    return False, (r.stderr or r.stdout).strip()[:300]


def lint_python(paths: list[str], repo: str) -> list[str]:
    problems = []
    for p in paths:
        full = os.path.join(repo, p)
        if not p.endswith(".py") or not os.path.isfile(full):
            continue
        with open(full, encoding="utf-8") as f:
            msg = check_python(f.read())
        if msg:
            problems.append(f"{p}: {msg}")
    return problems


def check_deterministic(ws: Workspace, accept: AcceptParse | None, diff_text: str | None, timeout: float,
                        cancel: threading.Event | None = None, task_files: tuple[str, ...] = (),
                        changes: Changes | None = None, accept_result: AcceptResult | None = None) -> dict:
    items = []
    accept_item = None
    if accept and accept.spec:
        res = accept_result if accept_result is not None else run_accept_spec(accept.spec, ws, timeout, cancel, task_files)
        accept_item = {"name": "accept", "tag": "deterministic", "passed": res.ok,
                       "detail": res.first_error or res.out[-300:], "stop": res.stop, "env": res.env_kind}
        items.append(accept_item)
    repo = ws.root
    changed = list(changes.changed) if changes is not None else files_changed(repo)
    python_files = [p for p in changed if p.endswith(".py") and os.path.isfile(os.path.join(repo, p))]
    problems = lint_python(python_files, repo)
    items.append({"name": "lint", "tag": "deterministic", "passed": not problems,
                  "detail": "; ".join(problems) or "clean", "ran": bool(python_files)})
    if diff_text is not None:
        ok, detail = diff_applies(diff_text, repo)
        items.append({"name": "diff_applies", "tag": "deterministic", "passed": ok, "detail": detail})
    items.append({"name": "files_changed", "tag": "deterministic", "passed": True,
                  "detail": ", ".join(changed) or "none"})
    return {"items": items, "passed": all(i["passed"] for i in items),
            "stop": accept_item["stop"] if accept_item else None,
            "accept_note": accept.note if accept and not accept.spec else ""}
