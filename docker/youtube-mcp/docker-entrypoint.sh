#!/bin/sh
# Entrypoint for tokenfrugal/youtube-mcp:1.
#
# The YouTube Data API key is never baked into the image. It can be provided in
# either of two ways at run time:
#   YOUTUBE_API_KEY=...            plain environment variable, or
#   YOUTUBE_API_KEY_FILE=/path     file containing only the key (e.g. a Docker
#                                  secret mounted under /run/secrets).
# When YOUTUBE_API_KEY_FILE is set, its contents (trailing newlines stripped)
# are exported as YOUTUBE_API_KEY before the server starts. The key value is
# never printed.
set -eu

if [ -n "${YOUTUBE_API_KEY_FILE:-}" ]; then
  if [ ! -r "$YOUTUBE_API_KEY_FILE" ]; then
    echo "youtube-mcp: YOUTUBE_API_KEY_FILE is set but not readable" >&2
    exit 1
  fi
  YOUTUBE_API_KEY="$(cat "$YOUTUBE_API_KEY_FILE")"
  export YOUTUBE_API_KEY
fi

exec node /app/dist/index.js "$@"
