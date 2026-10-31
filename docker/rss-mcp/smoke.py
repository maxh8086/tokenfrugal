#!/usr/bin/env python3
"""Smoke test for tokenfrugal/rss-mcp:1 (stdlib only).

Starts the image with `docker run --rm -i`, performs an MCP initialize and
tools/list over stdin/stdout (newline-delimited JSON-RPC), prints the tool
names and exits 0 on success. Makes no feed or network requests itself.

Usage: python smoke.py [image-tag]
"""
import json
import subprocess
import sys
import threading

IMAGE = sys.argv[1] if len(sys.argv) > 1 else "tokenfrugal/rss-mcp:1"
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
            # Ignore non-JSON noise; MCP stdio must be JSON only, so report it.
            raise RuntimeError(f"non-JSON on stdout: {text[:200]}")
        if msg.get("id") == wanted_id:
            if "error" in msg:
                raise RuntimeError(f"JSON-RPC error: {msg['error']}")
            return msg["result"]


def main():
    cmd = ["docker", "run", "--rm", "-i", IMAGE]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Kill the container if it hangs, so the smoke test cannot block forever.
    timer = threading.Timer(TIMEOUT_S, proc.kill)
    timer.start()
    try:
        send(proc, INIT)
        init = read_response(proc, 1)
        print(f"server: {init.get('serverInfo', {})} protocol: {init.get('protocolVersion')}")
        send(proc, INITIALIZED)
        send(proc, LIST)
        tools = read_response(proc, 2).get("tools", [])
    except Exception as exc:  # report and fail
        print(f"SMOKE FAILED: {exc}")
        err = proc.stderr.read(2000) if proc.poll() is not None else b""
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
    sys.exit(main())
