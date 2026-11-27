"""Replay task rw-013: scripts/bench.py ollama_env() records the Ollama environment and task timeout (offline)."""
import os
import sys

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
OLLAMA_KEYS = ["OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL", "OLLAMA_KEEP_ALIVE", "OLLAMA_FLASH_ATTENTION", "OLLAMA_KV_CACHE_TYPE"]


def fail(message):
    print("FAIL:", message)
    return 1


def main():
    try:
        import scripts.bench as bench
    except Exception as exc:
        return fail("cannot import scripts.bench: %r" % (exc,))
    for name in list(os.environ):
        if name.startswith("TOKENFRUGAL_") or name.startswith("OLLAMA_"):
            del os.environ[name]
    if not callable(getattr(bench, "ollama_env", None)):
        return fail("scripts/bench.py has no ollama_env()")
    try:
        env = bench.ollama_env()
    except Exception as exc:
        return fail("ollama_env() raised %r" % (exc,))
    if not isinstance(env, dict):
        return fail("ollama_env() returned a %s, not a dict" % type(env).__name__)
    if set(env) != set(OLLAMA_KEYS) | {"task_timeout_s"}:
        return fail("keys are %r, expected the five OLLAMA keys and task_timeout_s" % (sorted(env),))
    if any(env[key] != "unset" for key in OLLAMA_KEYS):
        return fail("with no OLLAMA variables set the values are %r, expected 'unset'" % ({k: env[k] for k in OLLAMA_KEYS},))
    timeout = env["task_timeout_s"]
    if type(timeout) is not int or timeout != 150:
        return fail("task_timeout_s is %r, expected the integer 150 with the variable cleared" % (timeout,))
    os.environ.update({"OLLAMA_NUM_PARALLEL": "3", "OLLAMA_KEEP_ALIVE": "10m", "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_HOST": "decoy-host:1"})
    env = bench.ollama_env()
    want = {"OLLAMA_MAX_LOADED_MODELS": "unset", "OLLAMA_NUM_PARALLEL": "3", "OLLAMA_KEEP_ALIVE": "10m",
            "OLLAMA_FLASH_ATTENTION": "1", "OLLAMA_KV_CACHE_TYPE": "unset"}
    for key, value in want.items():
        if env.get(key) != value:
            return fail("%s is %r, expected %r" % (key, env.get(key), value))
    if "OLLAMA_HOST" in env or "decoy-host:1" in env.values():
        return fail("ollama_env() reads a variable other than the five keys")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
