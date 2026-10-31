#!/usr/bin/env python3
"""Smoke test for tokenfrugal/youtube-mcp:1 (stdlib only).

Starts the image with `docker run --rm -i`, performs an MCP initialize and
tools/list over stdin/stdout (newline-delimited JSON-RPC), prints the tool
names and exits 0 on success.

No real API key is needed and no YouTube API call is made: tools/list is
answered from the server's own registry. Without a key the server registers
only getTranscripts. Pass --dummy-key to set a placeholder YOUTUBE_API_KEY so
the full tool list is registered (the placeholder is never sent anywhere
during tools/list).

Usage: python smoke.py [--dummy-key] [image-tag]
"""
import json
import subprocess
import sys
import threading

TIMEOUT_S = 60

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "smoke.py", "version": "1.0"},
    },
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}


def send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()


def read_response(proc, wanted_id):
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("container closed stdout before responding")
        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            msg = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(f"non-JSON on stdout: {text[:200]}")
        if msg.get("id") == wanted_id:
            if "error" in msg:
                raise RuntimeError(f"JSON-RPC error: {msg['error']}")
            return msg["result"]


def main(argv):
    dummy_key = "--dummy-key" in argv
    args = [a for a in argv if a != "--dummy-key"]
    image = args[0] if args else "tokenfrugal/youtube-mcp:1"

    cmd = ["docker", "run", "--rm", "-i"]
    if dummy_key:
        cmd += ["-e", "YOUTUBE_API_KEY=smoke-test-placeholder"]
    cmd.append(image)
    print(f"running: {' '.join(cmd[:-1])} {image}")

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timer = threading.Timer(TIMEOUT_S, proc.kill)
    timer.start()
    try:
        send(proc, INIT)
        init = read_response(proc, 1)
        print(f"server: {init.get('serverInfo', {})} protocol: {init.get('protocolVersion')}")
        send(proc, INITIALIZED)
        send(proc, LIST)
        tools = read_response(proc, 2).get("tools", [])
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}")
        if proc.poll() is not None:
            err = proc.stderr.read(2000)
            if err:
                print(err.decode("utf-8", errors="replace"))
        return 1
    finally:
        timer.cancel()
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    names = [t["name"] for t in tools]
    print(f"tools ({len(names)}):")
    for name in names:
        print(f"  - {name}")
    if not names:
        print("SMOKE FAILED: tools/list returned no tools")
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
