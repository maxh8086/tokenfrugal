#!/usr/bin/env bash
# Regenerate the SonarQube user token used by mcp-sonarqube and store it in the Docker secret file.
# Usage (Git Bash, repo root): bash scripts/regen_sonarqube_token.sh
# Prompts for a SonarQube admin login and password (read silently). The token is never printed.
set -euo pipefail

SQ_URL="http://127.0.0.1:9100"
TOKEN_NAME="tokenfrugal"
PY=".venv/Scripts/python.exe"

read -r -p "SonarQube admin login [admin]: " SQ_USER
SQ_USER=${SQ_USER:-admin}
read -r -s -p "SonarQube admin password: " SQ_PASS
echo

# Revoke the old token with this name. A 404 just means it did not exist.
curl -sS -u "$SQ_USER:$SQ_PASS" -X POST "$SQ_URL/api/user_tokens/revoke" \
  --data-urlencode "name=$TOKEN_NAME" -o /dev/null -w "revoke HTTP %{http_code}\n"

# Generate the new token and store it straight into the secret file (stdin, never printed).
curl -sS -f -u "$SQ_USER:$SQ_PASS" -X POST "$SQ_URL/api/user_tokens/generate" \
  --data-urlencode "name=$TOKEN_NAME" \
  | "$PY" -c 'import json,sys; sys.stdout.write(json.load(sys.stdin)["token"])' \
  | "$PY" -m router.secrets_store set SONARQUBE_TOKEN
unset SQ_PASS

# Validate the stored token against SonarQube. Expect {"valid":true}.
# Read the secret with Python: bash (WSL or Git Bash) may not be able to open the Windows path.
SECRET_PATH=$("$PY" -m router.secrets_store get-path SONARQUBE_TOKEN | tr -d '\r')
"$PY" -c '
import base64, pathlib, sys, urllib.request
token = pathlib.Path(sys.argv[1]).read_text().strip()
req = urllib.request.Request(sys.argv[2] + "/api/authentication/validate")
req.add_header("Authorization", "Basic " + base64.b64encode((token + ":").encode()).decode())
print(urllib.request.urlopen(req).read().decode())
' "$SECRET_PATH" "$SQ_URL"
