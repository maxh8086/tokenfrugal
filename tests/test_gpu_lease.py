"""GPU lease (router/gpu_lease.py): takeover rules, refusal windows, rollback, generations, heartbeat.

No real Ollama, ComfyUI, nvidia-smi or docker: a local fake HTTP server (127.0.0.1 only) and a fake subprocess.run.
"""
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from router import gpu_lease
from router.gpu_lease import GpuBusy, LeaseLost, LowVram, UnloadTimeout
from router.proc_alive import _alive

NOW = dt.datetime(2026, 11, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # talks to the local fake only


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        st = self.server.state
        if self.path == "/api/ps":
            self._send({"models": [{"name": m} for m in st["models"]]})
        elif self.path == "/queue":
            self._send({"queue_running": st["comfy_running"]})
        else:
            self.send_error(404)

    def do_POST(self):
        st = self.server.state
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/api/generate":
            cur = gpu_lease.read()  # records what the lease said when Ollama was asked to unload
            st["state_at_unload"] = cur.state if cur else None
            if not st["stubborn"]:
                st["models"] = []
            self._send({})
        elif self.path == "/free":
            st["freed"] = True
            self._send({})
        else:
            self.send_error(404)


class _FakeRun:
    """Stands in for subprocess.run: nvidia-smi and docker inspect."""

    def __init__(self):
        self.vram = "8000"
        self.vram_exc = None
        self.docker_stdout = "false"
        self.docker_rc = 0
        self.docker_exc = None

    def __call__(self, args, **kwargs):
        if args[0] == "nvidia-smi":
            if self.vram_exc:
                raise self.vram_exc
            return subprocess.CompletedProcess(args, 0, self.vram + "\n", "")
        if self.docker_exc:
            raise self.docker_exc
        stderr = "No such container" if self.docker_rc else ""
        return subprocess.CompletedProcess(args, self.docker_rc, self.docker_stdout, stderr)


class _Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.run = _FakeRun()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.state = {"models": ["m1"], "comfy_running": False, "stubborn": False,
                             "freed": False, "state_at_unload": None}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self._stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(self._kill_live)
        patches = [
            mock.patch.dict(os.environ, {"GPU_LEASE_DIR": str(self.dir / "leases")}),
            mock.patch.object(gpu_lease, "_now", lambda: NOW),
            mock.patch.object(gpu_lease, "_sleep", lambda s: None),
            mock.patch.object(gpu_lease, "LOCK_WAIT_S", 0.05),
            mock.patch.object(gpu_lease, "_run", self.run),
            mock.patch.object(gpu_lease, "_urlopen", _OPENER.open),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()

    def _kill_live(self):
        self.live.kill()
        self.live.wait()

    def acq(self, holder="kalamanch", **kw):
        kw.setdefault("ollama_url", self.url)
        kw.setdefault("comfy_url", self.url)
        return gpu_lease.acquire(holder, "task", **kw)

    def put(self, age=0, holder="kalamanch", pid=None, container_id=None, generation=5, state="held"):
        stamp = gpu_lease._iso(NOW - dt.timedelta(seconds=age))
        gpu_lease._save(gpu_lease.Lease(version=1, holder=holder, state=state, task="old", job_id=None,
                                        pid=os.getpid() if pid is None else pid, container_id=container_id,
                                        started_at=stamp, heartbeat_at=stamp, ttl_s=gpu_lease.TTL_S,
                                        generation=generation))

    def dead_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        return p.pid

    def closed_url(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return f"http://127.0.0.1:{port}"

    def lease_path(self):
        return self.dir / "leases" / "gpu.json"


class AcquireTest(_Base):
    def test_pending_is_written_before_unload_and_held_after(self):
        lease = self.acq()
        self.assertEqual(self.server.state["state_at_unload"], "pending")
        self.assertEqual(self.server.state["models"], [])
        cur = gpu_lease.read()
        self.assertEqual(cur.state, "held")
        self.assertEqual(cur.generation, lease.generation)
        self.assertEqual(cur.holder, "kalamanch")
        self.assertEqual(cur.pid, os.getpid())

    def test_second_acquire_is_busy(self):
        self.acq()
        with self.assertRaises(GpuBusy) as ctx:
            self.acq()
        self.assertEqual(ctx.exception.holder, "kalamanch")
        self.assertIn("do not call resume_task", ctx.exception.hint)

    def test_low_vram_rolls_back(self):
        self.run.vram = "1024"
        with self.assertRaises(LowVram):
            self.acq()
        self.assertIsNone(gpu_lease.read())

    def test_nvidia_smi_missing_refuses(self):
        self.run.vram_exc = FileNotFoundError("nvidia-smi")
        with self.assertRaises(LowVram):
            self.acq()
        self.assertIsNone(gpu_lease.read())

    def test_nvidia_smi_timeout_refuses(self):
        self.run.vram_exc = subprocess.TimeoutExpired("nvidia-smi", 10)
        with self.assertRaises(LowVram):
            self.acq()
        self.assertIsNone(gpu_lease.read())

    def test_unload_timeout_rolls_back(self):
        self.server.state["stubborn"] = True
        with mock.patch.object(gpu_lease, "UNLOAD_WAIT_S", 0):
            with self.assertRaises(UnloadTimeout):
                self.acq()
        self.assertIsNone(gpu_lease.read())

    def test_generation_rises_and_old_holder_is_refused(self):
        first = self.acq()
        gpu_lease.release(first)
        second = self.acq()
        self.assertGreater(second.generation, first.generation)
        with self.assertRaises(LeaseLost):
            gpu_lease.release(first)
        with self.assertRaises(LeaseLost):
            gpu_lease.heartbeat(first)
        self.assertEqual(gpu_lease.read().generation, second.generation)

    def test_force_release_returns_old_record(self):
        self.acq()
        old = gpu_lease.force_release()
        self.assertEqual(old.holder, "kalamanch")
        self.assertIsNone(gpu_lease.read())
        self.assertIsNone(gpu_lease.force_release())

    def test_heartbeat_thread_reports_lost_lease(self):
        lease = self.acq()
        lost = threading.Event()
        with mock.patch.object(gpu_lease, "HEARTBEAT_S", 0.01):
            stop = gpu_lease.start_heartbeat(lease, on_lost=lambda e: lost.set())
            self.addCleanup(stop.set)
            gpu_lease.force_release()
            self.assertTrue(lost.wait(3))


class ExpiryTest(_Base):
    def test_expired_kalamanch_with_dead_pid_is_taken_over(self):
        self.put(age=40, pid=self.dead_pid(), generation=5)
        lease = self.acq()
        self.assertGreater(lease.generation, 5)
        self.assertEqual(gpu_lease.read().pid, os.getpid())

    def test_expired_kalamanch_with_live_pid_blocks(self):
        self.put(age=40, pid=self.live.pid, generation=5)
        with self.assertRaises(GpuBusy):
            self.acq()
        self.assertEqual(gpu_lease.read().generation, 5)

    def test_expired_comfy_with_running_container_blocks(self):
        self.run.docker_stdout = "true"
        self.put(age=40, holder="comfyui", container_id="c1", generation=5)
        with self.assertRaises(GpuBusy):
            self.acq()

    def test_expired_comfy_with_stopped_container_is_taken_over(self):
        self.run.docker_stdout = "false"
        self.put(age=40, holder="comfyui", container_id="c1", generation=5)
        self.assertGreater(self.acq().generation, 5)

    def test_expired_comfy_with_removed_container_is_taken_over(self):
        self.run.docker_rc = 1  # "No such container": the container is gone
        self.put(age=40, holder="comfyui", container_id="c1", generation=5)
        self.assertGreater(self.acq().generation, 5)

    def test_expired_comfy_when_docker_unreachable_blocks(self):
        self.run.docker_exc = OSError("docker not found")
        self.put(age=40, holder="comfyui", container_id="c1", generation=5)
        with self.assertRaises(GpuBusy):
            self.acq()

    def test_expired_comfy_without_container_blocks(self):
        self.put(age=40, holder="comfyui", container_id=None, generation=5)
        with self.assertRaises(GpuBusy):
            self.acq()

    def test_running_comfy_job_blocks_takeover(self):
        self.put(age=40, pid=self.dead_pid(), generation=5)
        self.server.state["comfy_running"] = True
        with self.assertRaises(GpuBusy):
            self.acq()

    def test_unreachable_queue_lets_takeover_through(self):
        self.put(age=40, pid=self.dead_pid(), generation=5)
        lease = self.acq(comfy_url=self.closed_url())
        self.assertGreater(lease.generation, 5)


class RefusalWindowTest(_Base):
    def test_fresh_lease_refuses(self):
        self.put(age=1)
        with self.assertRaises(GpuBusy):
            gpu_lease.check_for_ollama(self.url)

    def test_inside_refusal_window_refuses(self):
        self.put(age=gpu_lease.TTL_S + 29, pid=self.dead_pid())  # ttl+29 < ttl+30
        with self.assertRaises(GpuBusy):
            gpu_lease.check_for_ollama(self.url)

    def test_after_refusal_window_checks_queue(self):
        self.put(age=gpu_lease.TTL_S + 31, pid=self.dead_pid())  # ttl+31 >= ttl+30
        self.assertIsNone(gpu_lease.check_for_ollama(self.url))
        self.server.state["comfy_running"] = True
        with self.assertRaises(GpuBusy):
            gpu_lease.check_for_ollama(self.url)

    def test_queue_timeout_lets_task_through(self):
        self.put(age=gpu_lease.TTL_S + 31, pid=self.dead_pid())
        self.assertIsNone(gpu_lease.check_for_ollama(self.closed_url()))

    def test_guard_ollama_skips_remote_urls(self):
        self.put(age=1)
        self.assertIsNone(gpu_lease.guard_ollama("http://example.com:11434", comfy_url=self.url))
        with self.assertRaises(GpuBusy):
            gpu_lease.guard_ollama(self.url, comfy_url=self.url)


class UnreadableTest(_Base):
    def write_garbage(self, age):
        self.lease_path().parent.mkdir(parents=True, exist_ok=True)
        self.lease_path().write_text("{not json", encoding="utf-8")
        stamp = NOW.timestamp() - age
        os.utime(self.lease_path(), (stamp, stamp))

    def test_unreadable_inside_window_refuses(self):
        self.write_garbage(age=10)
        with self.assertRaises(GpuBusy):
            gpu_lease.check_for_ollama(self.url)
        with self.assertRaises(GpuBusy):
            self.acq()

    def test_unreadable_after_window_does_not_block(self):
        self.write_garbage(age=100)
        self.assertIsNone(gpu_lease.check_for_ollama(self.url))
        self.assertEqual(self.acq().state, "held")
        self.assertEqual(gpu_lease.read().state, "held")


class LockTest(_Base):
    def lock_path(self):
        return self.dir / "leases" / "gpu.lock"

    def test_stale_lock_is_removed(self):
        self.lock_path().parent.mkdir(parents=True, exist_ok=True)
        self.lock_path().write_text("")
        old = time.time() - 100
        os.utime(self.lock_path(), (old, old))
        with gpu_lease._locked():
            self.assertTrue(self.lock_path().exists())
        self.assertFalse(self.lock_path().exists())

    def test_fresh_lock_refuses(self):
        self.lock_path().parent.mkdir(parents=True, exist_ok=True)
        self.lock_path().write_text("")
        with self.assertRaises(GpuBusy):
            with gpu_lease._locked():
                pass
        self.assertTrue(self.lock_path().exists())


class ConcurrencyTest(_Base):
    def test_competing_acquires_have_one_winner(self):
        results, errors = [], []

        def try_acquire():
            try:
                results.append(self.acq())
            except GpuBusy as e:
                errors.append(e)

        threads = [threading.Thread(target=try_acquire) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 3)


class ComfyReleaseTest(_Base):
    def test_comfy_release_keeps_lease_when_vram_stays_low(self):
        lease = self.acq("comfyui", container_id="c1")
        self.run.vram = "1000"
        self.assertFalse(gpu_lease.release(lease, comfy_url=self.url))
        self.assertTrue(self.server.state["freed"])
        self.assertEqual(gpu_lease.read().generation, lease.generation)

    def test_comfy_release_deletes_when_vram_recovers(self):
        lease = self.acq("comfyui", container_id="c1")
        self.assertTrue(gpu_lease.release(lease, comfy_url=self.url))
        self.assertIsNone(gpu_lease.read())

    def test_comfy_release_keeps_lease_when_free_call_fails(self):
        lease = self.acq("comfyui", container_id="c1")
        self.assertFalse(gpu_lease.release(lease, comfy_url=self.closed_url()))
        self.assertEqual(gpu_lease.read().generation, lease.generation)


class HelperTest(_Base):
    def test_alive_reports_live_and_dead_pids(self):
        self.assertTrue(_alive(os.getpid()))
        self.assertTrue(_alive(self.live.pid))
        self.assertFalse(_alive(self.dead_pid()))


if __name__ == "__main__":
    unittest.main()
