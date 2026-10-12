import unittest
from unittest import mock

from scripts import bench_env


class CaptureEnvTests(unittest.TestCase):
    def test_reports_each_ollama_key_and_marks_missing_as_unset(self):
        env = bench_env.capture_env({"OLLAMA_NUM_PARALLEL": "1", "OLLAMA_KV_CACHE_TYPE": "q8_0", "PATH": "x"})
        self.assertEqual(list(env), list(bench_env.OLLAMA_ENV_KEYS))
        self.assertEqual(env["OLLAMA_NUM_PARALLEL"], "1")
        self.assertEqual(env["OLLAMA_KV_CACHE_TYPE"], "q8_0")
        self.assertEqual(env["OLLAMA_MAX_LOADED_MODELS"], "unset")
        self.assertNotIn("PATH", env)


class TaskTimeoutTests(unittest.TestCase):
    def test_env_value_wins_over_default(self):
        t = bench_env.task_timeout({"TOKENFRUGAL_TASK_TIMEOUT": "300"}, "150")
        self.assertEqual(t, {"task_timeout_s": 300.0, "source": "env"})

    def test_missing_env_uses_default_and_says_so(self):
        t = bench_env.task_timeout({}, "150")
        self.assertEqual(t, {"task_timeout_s": 150.0, "source": "bench default"})


class ParseNvidiaTests(unittest.TestCase):
    def test_parses_one_gpu_line(self):
        r = bench_env.parse_nvidia("4, 4821, 8188, 47, 1.88\n")
        self.assertEqual(r, {"gpu_util_pct": 4.0, "vram_used_mib": 4821.0, "vram_total_mib": 8188.0,
                             "gpu_temp_c": 47.0, "gpu_power_w": 1.88})

    def test_not_supported_fields_become_none(self):
        r = bench_env.parse_nvidia("[N/A], 100, 8188, [Not Supported], 12.5")
        self.assertIsNone(r["gpu_util_pct"])
        self.assertIsNone(r["gpu_temp_c"])
        self.assertEqual(r["vram_used_mib"], 100.0)

    def test_empty_output_gives_all_none(self):
        self.assertTrue(all(v is None for v in bench_env.parse_nvidia("").values()))


OLLAMA_PS = """NAME ID SIZE PROCESSOR CONTEXT UNTIL
a:3b abc 2.1 GB 100% GPU 8192 4 minutes from now
b:8b def 6.0 GB 48%/52% CPU/GPU 16384 4 minutes from now
c:1b ghi 1.0 GB 100% CPU 4096 4 minutes from now
"""


class ParseOllamaPsTests(unittest.TestCase):
    def test_reads_processor_split_per_model(self):
        rows = bench_env.parse_ollama_ps(OLLAMA_PS)
        self.assertEqual([r["model"] for r in rows], ["a:3b", "b:8b", "c:1b"])
        self.assertEqual([r["processor"] for r in rows], ["100% GPU", "48%/52% CPU/GPU", "100% CPU"])
        self.assertEqual([r["cpu_share_pct"] for r in rows], [0.0, 48.0, 100.0])

    def test_header_only_means_no_loaded_models(self):
        self.assertEqual(bench_env.parse_ollama_ps("NAME ID SIZE PROCESSOR CONTEXT UNTIL\n"), [])


def _fake_run(gpu_lines, ps_texts):
    """Returns canned output per call: nvidia-smi lines and ollama ps texts, consumed in order."""
    gpu, ps = iter(gpu_lines), iter(ps_texts)

    def run(cmd):
        return next(gpu) if cmd[0] == "nvidia-smi" else next(ps)
    return run


class HardwareSamplerTests(unittest.TestCase):
    def test_summary_spreads_and_processor_split(self):
        run = _fake_run(["10, 1000, 8188, 40, 5.0", "30, 3000, 8188, 50, 15.0"], [OLLAMA_PS, "NAME ID SIZE PROCESSOR\n"])
        with mock.patch.object(bench_env, "psutil", None):
            s = bench_env.HardwareSampler(run=run)
            s.sample_once()
            s.sample_once()
            out = s.summary()
        self.assertEqual(out["samples"], 2)
        self.assertEqual(out["gpu_util_pct"], {"min": 10.0, "avg": 20.0, "max": 30.0})
        self.assertEqual(out["vram_used_mib"], {"min": 1000.0, "avg": 2000.0, "max": 3000.0})
        self.assertEqual(out["vram_total_mib"], 8188.0)
        self.assertIsNone(out["cpu_pct"])
        self.assertEqual(out["processor_split"], {"100% GPU": 1, "48%/52% CPU/GPU": 1, "100% CPU": 1})
        self.assertEqual(out["max_cpu_share_pct"], 100.0)
        self.assertFalse(out["psutil"])

    def test_cpu_and_ram_come_from_psutil_when_present(self):
        fake = mock.Mock()
        fake.cpu_percent.return_value = 25.0
        fake.virtual_memory.return_value = mock.Mock(percent=60.0)
        with mock.patch.object(bench_env, "psutil", fake):
            s = bench_env.HardwareSampler(run=_fake_run(["0, 0, 8188, 40, 1"], [""]))
            row = s.sample_once()
        self.assertEqual((row["cpu_pct"], row["ram_pct"]), (25.0, 60.0))

    def test_start_and_stop_collect_samples(self):
        with mock.patch.object(bench_env, "psutil", None):
            s = bench_env.HardwareSampler(interval=0.01, run=lambda cmd: "")
            s.start()
            s.stop()
        self.assertGreaterEqual(len(s.samples), 1)


class MarkdownSectionTests(unittest.TestCase):
    def test_renders_env_timeout_and_hardware(self):
        hw = {"samples": 2, "psutil": True, "cpu_pct": {"min": 1.0, "avg": 2.0, "max": 3.0},
              "processor_split": {"100% GPU": 2}}
        text = "\n".join(bench_env.markdown_section({"OLLAMA_NUM_PARALLEL": "1"},
                                                    {"task_timeout_s": 300.0, "source": "env"}, hw))
        self.assertIn("## Environment and hardware", text)
        self.assertIn("| OLLAMA_NUM_PARALLEL | 1 |", text)
        self.assertIn("Task timeout: 300s (source: env)", text)
        self.assertIn("| CPU % | 1.0 | 2.0 | 3.0 |", text)
        self.assertIn("| RAM % | - | - | - |", text)
        self.assertIn("100% GPU (x2)", text)


if __name__ == "__main__":
    unittest.main()
