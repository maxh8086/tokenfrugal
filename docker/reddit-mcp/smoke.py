"""Smoke test: start the image over stdio, MCP initialize + tools/list, print tool names.

Stdlib only. Usage: python smoke.py [image-tag]   (default tokenfrugal/reddit-mcp:1)
Exit code 0 on success, 1 on any protocol or timeout failure.
"""
import json
import subprocess
import sys

IMAGE = sys.argv[1] if len(sys.argv) > 1 else "tokenfrugal/reddit-mcp:1"
TIMEOUT = 60  # seconds per response line


def read_response(proc, want_id):
    """Read newline-delimited JSON until the response with want_id arrives."""
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("container closed stdout before responding")
        text = line.decode("utf-8", "replace").strip()
        if not text:
            continue
        try:
            msg = json.loads(text)
        except ValueError:
            raise RuntimeError(f"non-JSON line on stdout (protocol broken): {text[:200]!r}")
        if msg.get("id") == want_id:
            return msg


def send(proc, msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()


def main():
    proc = subprocess.Popen(
        ["docker", "run", "--rm", "-i", IMAGE],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        send(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        })
        init = read_response(proc, 1)
        if "error" in init or "result" not in init:
            raise RuntimeError(f"initialize failed: {init}")
        info = init["result"].get("serverInfo", {})
        print(f"initialized: server={info.get('name')} version={info.get('version')} "
              f"protocol={init['result'].get('protocolVersion')}")

        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = read_response(proc, 2)
        if "error" in listed or "result" not in listed:
            raise RuntimeError(f"tools/list failed: {listed}")
        tools = listed["result"].get("tools", [])
        print(f"tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.get('name')}")
        if not tools:
            raise RuntimeError("tools/list returned no tools")
        print("SMOKE OK")
        return 0
    except RuntimeError as exc:
        print(f"SMOKE FAILED: {exc}")
        err = proc.stderr.read(4000) if proc.poll() is not None else b""
        if err:
            print(err.decode("utf-8", "replace"))
        return 1
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
