"""One-off: copy tokenfrugal secrets from the OS keyring into Docker secret files.

Run once: `.venv/Scripts/python.exe scripts/migrate_keyring_to_docker_secrets.py`. Each value is read from the keyring
(service `tokenfrugal`) and written to `<secrets dir>/NAME`. Only names and OK/MISSING status are printed. Keyring
entries are NOT deleted; remove them yourself after checking the files.
"""
import json
import sys
from pathlib import Path

import keyring

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from router import secrets_store  # noqa: E402

SERVICE = "tokenfrugal"
# Names the code knew: the backend secrets, the LLM key, and the old name index (router/secret_names.json).
KNOWN = ["CRAWL4AI_API_TOKEN", "SEARXNG_SECRET", "SONARQUBE_TOKEN", "SONARQUBE_ORG", "NEO4J_AUTH", "llm-api-key"]


def _indexed_names() -> list[str]:
    try:
        return json.loads((ROOT / "router" / "secret_names.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def main() -> int:
    names = sorted(set(KNOWN) | set(_indexed_names()))
    missing = []
    print(f"secrets directory: {secrets_store.SECRETS_DIR}")
    for name in names:
        try:
            value = keyring.get_password(SERVICE, name)
        except keyring.errors.KeyringError as e:
            print(f"{name}: MISSING ({type(e).__name__})")
            missing.append(name)
            continue
        if not value:
            print(f"{name}: MISSING")
            missing.append(name)
            continue
        secrets_store.put(name, value)
        print(f"{name}: OK")
    print(f"migrated {len(names) - len(missing)} of {len(names)}; missing: {', '.join(missing) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
