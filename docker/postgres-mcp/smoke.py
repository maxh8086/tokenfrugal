"""Smoke test for tokenfrugal/postgres-mcp:1 (stdlib only).

Starts the container with `docker run --rm -i`, performs MCP initialize and
tools/list over stdin/stdout (newline-delimited JSON-RPC, stdio transport) and
prints the tool names. Exit code 0 means the server answered and listed tools.

Usage:  python smoke.py [image-tag]
DATABASE_URI is forwarded by name only when it is set on the host, so the value
never appears on the command line. If it is unset, a placeholder that points at
a closed local port is used. The server starts without a reachable database
(it only warns), and tools/list does not query the database.
"""

import json
import os
import queue
import subprocess
import sys
import threading

IMAGE = sys.argv[1] if len(sys.argv) > 1 else "tokenfrugal/postgres-mcp:1"
TIMEOUT = 120
PLACEHOLDER_URI = "postgresql://smoke:smoke@127.0.0.1:1/smoke"  # never contacted successfully


def send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()


def wait_for_id(lines, want_id):
    while True:
        try:
            line = lines.get(timeout=TIMEOUT)
        except queue.Empty:
            raise SystemExit(f"timeout waiting for response id={want_id}")
        if line is None:
            raise SystemExit(f"server closed stdout before response id={want_id}")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # ignore non-JSON noise on stdout
        if msg.get("id") == want_id:
            return msg


def main():
    cmd = ["docker", "run", "--rm", "-i", "--network", "none"]
    if "DATABASE_URI" in os.environ:
        cmd += ["-e", "DATABASE_URI"]
    else:
        cmd += ["-e", f"DATABASE_URI={PLACEHOLDER_URI}"]
    cmd.append(IMAGE)

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    lines = queue.Queue()

    def reader():
        for raw in proc.stdout:
            lines.put(raw.decode("utf-8", "replace").strip())
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    try:
        send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        })
        init = wait_for_id(lines, 1)
        if "error" in init or "result" not in init:
            raise SystemExit(f"initialize failed: {init}")
        server = init["result"].get("serverInfo", {})
        print(f"initialize ok: {server.get('name')} {server.get('version')}")

        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = wait_for_id(lines, 2)
        if "error" in listed or "result" not in listed:
            raise SystemExit(f"tools/list failed: {listed}")
        tools = [t["name"] for t in listed["result"].get("tools", [])]
        print(f"tools/list ok: {len(tools)} tool(s)")
        for name in tools:
            print(f"  - {name}")
        if not tools:
            raise SystemExit("no tools listed")
        print("SMOKE PASS")
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
