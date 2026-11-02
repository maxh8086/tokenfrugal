"""Replays recorded ComfyUI websocket events through router/comfy_bridge.py with a fake clock.

No ComfyUI, GPU, docker or network is used. The fixture is synthetic: its timestamps are chosen so the expected values
are easy to check by hand (load 40 s, 10 s per sampler step, 4 s from the last step to the end of the prompt).
"""
import copy
import json
import tempfile
import threading
import unittest
import warnings
from pathlib import Path
from unittest import mock

from router import comfy_bridge as cb
from router import gpu_lease

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "comfy_events.jsonl"


def _lines():
    return [json.loads(x) for x in FIXTURE.read_text(encoding="utf-8").splitlines() if x.strip()]


def _status(n):
    return {"type": "status", "data": {"status": {"exec_info": {"queue_remaining": n}}}}


def _progress(value, top=4):
    return {"type": "progress", "data": {"value": value, "max": top, "prompt_id": "p", "node": "3"}}


class ReplayTest(unittest.TestCase):
    """Replays the fixture once and checks the snapshot after each line (index = line number - 1)."""

    @classmethod
    def setUpClass(cls):
        clock = {"t": 0.0}
        cls.tracker = cb.ComfyTracker(clock=lambda: clock["t"])
        cls.snap, cls.recorded = {}, None
        cls.lines = _lines()
        for i, line in enumerate(cls.lines):
            clock["t"] = line["t"]
            cls.tracker.handle(line["msg"])
            if "workflow" in line:
                cls.tracker.set_workflow(line["workflow"])  # the runner fetches it from GET /queue
            if line["msg"]["type"] == "execution_success":
                cls.recorded = cls.tracker.record()
            cls.snap[i] = cls.tracker.snapshot(now=line["t"])
        cls.key = cb.workflow_key(cls.lines[1]["workflow"])

    def test_loading_until_first_sampler_step(self):
        self.assertEqual(self.snap[1]["state"], "loading")
        self.assertEqual(self.snap[1]["elapsed_s"], 0.0)
        self.assertEqual(self.snap[2]["state"], "loading")
        self.assertEqual(self.snap[2]["elapsed_s"], 1.0)

    def test_elapsed_counts_from_execution_start_and_load_time_is_recorded(self):
        self.assertEqual(self.snap[3]["state"], "running")
        self.assertEqual(self.snap[3]["elapsed_s"], 40.0)  # 41 - 1
        self.assertEqual(self.snap[3]["load_s"], 40.0)
        self.assertEqual(self.snap[3]["step"], 1)
        self.assertIsNone(self.snap[3]["eta_s"])  # no step time yet

    def test_eta_appears_after_two_sampler_steps(self):
        self.assertEqual(self.snap[4]["step"], 2)
        # step time 10 s; remaining (4 - 2) steps = 20 s; no history yet, so the post-sampling part counts as 0
        self.assertEqual(self.snap[4]["eta_s"], 20.0)
        self.assertTrue(self.snap[4]["eta_partial"])

    def test_finishing_state_after_last_step(self):
        self.assertEqual(self.snap[6]["state"], "finishing")
        self.assertEqual(self.snap[6]["eta_s"], 0.0)

    def test_success_is_recorded_with_timings(self):
        self.assertEqual(self.recorded, {"load_s": 40.0, "step_s": 10.0, "post_s": 4.0, "total_s": 75.0})
        self.assertEqual(self.snap[8]["last_result"], "success")
        self.assertEqual(len(self.tracker.history[self.key]), 1)

    def test_failed_run_is_not_recorded(self):
        self.assertEqual(self.snap[13]["last_result"], "error")
        self.assertEqual(len(self.tracker.history[self.key]), 1)

    def test_both_runs_share_one_history_key(self):
        self.assertEqual(cb.workflow_key(self.lines[1]["workflow"]), cb.workflow_key(self.lines[10]["workflow"]))

    def test_empty_queue_is_detected_and_debounced(self):
        self.assertEqual(self.snap[9]["empty_for_s"], 0.0)
        # the last status (index 14) at t=121 leaves the queue empty; the debounce is 180 s
        self.assertFalse(self.tracker.should_release(now=121 + 179))
        self.assertTrue(self.tracker.should_release(now=121 + gpu_lease.QUEUE_DEBOUNCE_S))


class WorkflowKeyTest(unittest.TestCase):
    def setUp(self):
        self.wf = _lines()[1]["workflow"]

    def test_seed_and_prompt_text_do_not_change_the_key(self):
        other = copy.deepcopy(self.wf)
        other["3"]["inputs"]["seed"] = 99
        other["5"]["inputs"]["text"] = "something else entirely"
        self.assertEqual(cb.workflow_key(self.wf), cb.workflow_key(other))

    def test_structure_changes_the_key(self):
        other = copy.deepcopy(self.wf)
        other["3"]["inputs"]["steps"] = 8
        self.assertNotEqual(cb.workflow_key(self.wf), cb.workflow_key(other))
        other2 = copy.deepcopy(self.wf)
        other2["3"]["class_type"] = "KSamplerAdvanced"
        self.assertNotEqual(cb.workflow_key(self.wf), cb.workflow_key(other2))


class HistoryTest(unittest.TestCase):
    def _finish(self, tracker, result, post):
        tracker.finished_result = result
        tracker.finished_key = "k"
        tracker.finished_stats = {"load_s": 1.0, "step_s": 1.0, "post_s": post, "total_s": 2.0}
        return tracker.record()

    def test_history_is_capped_at_twenty_runs_per_key(self):
        tracker = cb.ComfyTracker(clock=lambda: 0.0)
        for i in range(25):
            self._finish(tracker, "success", float(i))
        self.assertEqual(len(tracker.history["k"]), cb.HISTORY_PER_KEY)
        self.assertEqual(tracker.history["k"][0]["post_s"], 5.0)  # the oldest five were dropped

    def test_failed_and_interrupted_runs_are_not_recorded(self):
        tracker = cb.ComfyTracker(clock=lambda: 0.0)
        self.assertIsNone(self._finish(tracker, "error", 1.0))
        self.assertIsNone(self._finish(tracker, "interrupted", 1.0))
        self.assertNotIn("k", tracker.history)

    def test_median_post_time_from_history_drives_eta(self):
        clock = {"t": 0.0}
        wf = _lines()[1]["workflow"]
        key = cb.workflow_key(wf)
        history = {key: [{"post_s": 6.0}, {"post_s": 8.0}]}
        tracker = cb.ComfyTracker(clock=lambda: clock["t"], history=history)
        clock["t"] = 0.0
        tracker.handle({"type": "execution_start", "data": {"prompt_id": "p"}})
        tracker.set_workflow(wf)
        clock["t"] = 0.0
        tracker.handle(_progress(1))
        clock["t"] = 10.0
        tracker.handle(_progress(2))
        clock["t"] = 20.0
        tracker.handle(_progress(3))
        # step time 10 s; one step left = 10 s; median post-sampling time 7 s
        self.assertEqual(tracker.eta_s(now=20.0), 17.0)
        self.assertFalse(tracker.snapshot(now=20.0)["eta_partial"])


class QueueStateTest(unittest.TestCase):
    def test_queued_state_and_debounce_restarts_when_work_arrives(self):
        clock = {"t": 0.0}
        tracker = cb.ComfyTracker(clock=lambda: clock["t"])
        tracker.handle(_status(2))
        self.assertEqual(tracker.snapshot(now=0.0)["state"], "queued")
        clock["t"] = 50.0
        tracker.handle(_status(0))  # empty from t=50
        clock["t"] = 60.0
        tracker.handle(_status(1))  # work arrives: the empty period restarts
        clock["t"] = 70.0
        tracker.handle(_status(0))  # empty from t=70
        self.assertFalse(tracker.should_release(now=70 + 179))
        self.assertTrue(tracker.should_release(now=70 + gpu_lease.QUEUE_DEBOUNCE_S))

    def test_status_file_payload_has_the_fields_the_tab_reads(self):
        tracker = cb.ComfyTracker(clock=lambda: 0.0)
        snap = tracker.snapshot(now=0.0)
        for key in ("state", "elapsed_s", "step", "max_steps", "eta_s", "eta_partial", "load_s",
                    "queue_remaining", "empty_for_s", "debounce_s", "last_result"):
            self.assertIn(key, snap)


class BridgeWebsocketTest(unittest.TestCase):
    """run() opens a sync websocket without a context manager; websockets 17 must not warn about it."""

    def test_run_connects_and_receives_without_connect_deprecation(self):
        from websockets.sync.server import serve

        def handler(conn):
            try:
                conn.recv()  # waits until the bridge closes the connection
            except Exception:  # noqa: BLE001 - the close is the expected end
                pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stop_file = root / cb.STOP_FILE
            real_write = cb._write_json
            writes = {"n": 0}

            def write_then_request_stop(path, obj):
                real_write(path, obj)
                writes["n"] += 1
                if writes["n"] == 3:  # a few polls over the live socket, then ask for a clean stop
                    stop_file.write_text("stop", encoding="utf-8")

            lease = object()
            server = serve(handler, "127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.socket.getsockname()[1]
                with mock.patch.object(cb, "_lease_root", return_value=root), \
                        mock.patch.object(cb, "POLL_S", 0.05), \
                        mock.patch.object(cb.gpu_lease, "acquire", return_value=lease), \
                        mock.patch.object(cb.gpu_lease, "start_heartbeat",
                                          return_value=threading.Event()), \
                        mock.patch.object(cb.gpu_lease, "release", return_value=True), \
                        mock.patch.object(cb, "_queue", return_value=([], [])), \
                        mock.patch.object(cb, "_stop_container"), \
                        mock.patch.object(cb, "_write_json", side_effect=write_then_request_stop):
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        code = cb.run(f"http://127.0.0.1:{port}")
            finally:
                server.shutdown()
                server.socket.close()

            self.assertEqual(code, 0)
            self.assertGreaterEqual(writes["n"], 3)
            deprecated = [w for w in caught
                          if issubclass(w.category, DeprecationWarning) and "context manager" in str(w.message)]
            self.assertEqual(deprecated, [])


if __name__ == "__main__":
    unittest.main()
