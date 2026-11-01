"""Offline tests for scripts/comfy_spike.py and scripts/comfy_quality.py: parsing, workflow injection, CSV rows,
threshold derivation, PSNR/SSIM on synthetic planes and the refuse-to-run guards (mocked).

No GPU, Docker, ComfyUI, Ollama, nvidia-smi or network: every hardware call is replaced by a mock or a fake value.
"""
import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import comfy_quality as quality
from scripts import comfy_spike as spike

WORKFLOW = spike.WORKFLOW_DIR / "ltx098.json"


class NvidiaSmiTests(unittest.TestCase):
    def test_used_memory_takes_the_largest_gpu_value(self):
        self.assertEqual(spike.parse_nvidia_smi_used_mb("1024\n6900\n"), 6900.0)

    def test_empty_output_raises(self):
        with self.assertRaises(ValueError):
            spike.parse_nvidia_smi_used_mb("")

    def test_compute_apps_with_pids(self):
        apps = spike.parse_compute_apps("1234, python.exe, 5120\n")
        self.assertEqual(apps, [{"pid": 1234, "name": "python.exe", "used_mb": 5120.0}])

    def test_compute_apps_none_running_and_windows_na(self):
        self.assertEqual(spike.parse_compute_apps("No running processes found"), [])
        apps = spike.parse_compute_apps("[N/A], ollama.exe, [N/A]")
        self.assertEqual(len(apps), 1)
        self.assertIsNone(apps[0]["pid"])
        self.assertIsNone(apps[0]["used_mb"])


class TypeperfTests(unittest.TestCase):
    CAPTURE = (
        '"(PDH-CSV 4.0)","\\\\HOST\\GPU Adapter Memory(luid_0x0_0x0_phys_0)\\Shared Usage",'
        '"\\\\HOST\\GPU Adapter Memory(luid_0x0_0x1_phys_0)\\Shared Usage"\n'
        '"04/12/2026 10:00:01.123","1000000","0"\n'
        '"04/12/2026 10:00:02.123","2000000","500000"\n'
        "Exiting, please wait...\n"
        "The command completed successfully.\n"
    )

    def test_data_lines_are_summed_across_adapters(self):
        self.assertEqual(spike.parse_typeperf(self.CAPTURE), [1000000.0, 2500000.0])

    def test_header_and_footer_are_skipped(self):
        self.assertIsNone(spike.parse_typeperf_line("Exiting, please wait..."))
        self.assertIsNone(spike.parse_typeperf_line('"(PDH-CSV 4.0)","x"'))
        self.assertIsNone(spike.parse_typeperf_line(""))

    def test_blank_cells_do_not_count_as_zero_samples(self):
        self.assertIsNone(spike.parse_typeperf_line('"04/12/2026 10:00:01.123",""'))


class SizeParsingTests(unittest.TestCase):
    def test_sizes_to_mb(self):
        self.assertEqual(spike.parse_size_mb("8GB"), 8192.0)
        self.assertEqual(spike.parse_size_mb("8G"), 8192.0)
        self.assertEqual(spike.parse_size_mb("8192MB"), 8192.0)
        self.assertEqual(spike.parse_size_mb(" 512 MB "), 512.0)
        self.assertEqual(spike.parse_size_mb("1TB"), 1024.0 * 1024)

    def test_bad_size_raises(self):
        with self.assertRaises(ValueError):
            spike.parse_size_mb("lots")

    def test_wslconfig_memory_in_wsl2_section(self):
        text = "[wsl2]\nprocessors=8  # cores\nmemory = 12GB ; cap\n\n[experimental]\nautoMemoryReclaim=gradual\n"
        self.assertEqual(spike.parse_wslconfig_memory_mb(text), 12 * 1024.0)

    def test_wslconfig_memory_in_other_section_is_ignored(self):
        self.assertIsNone(spike.parse_wslconfig_memory_mb("[other]\nmemory=4GB\n"))

    def test_wslconfig_missing_key_is_none(self):
        self.assertIsNone(spike.parse_wslconfig_memory_mb("[wsl2]\nprocessors=4\n"))

    def test_read_wslconfig_from_file_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / ".wslconfig"
            path.write_text("[wsl2]\nmemory=16GB\n", encoding="utf-8")
            self.assertEqual(spike.read_wslconfig_memory_mb(path), 16 * 1024.0)
            self.assertIsNone(spike.read_wslconfig_memory_mb(Path(d) / "absent"))

    def test_docker_mem_usage(self):
        self.assertAlmostEqual(spike.parse_mem_usage_mb("1.5GiB / 15.6GiB"), 1.5 * 1024)
        self.assertAlmostEqual(spike.parse_mem_usage_mb("512MiB / 15.6GiB"), 512.0)
        self.assertAlmostEqual(spike.parse_mem_usage_mb("900kB / 15.6GiB"), 900 / 1024.0)
        with self.assertRaises(ValueError):
            spike.parse_mem_usage_mb("??")


class SystemStatsTests(unittest.TestCase):
    def test_cuda_version_comes_from_the_torch_build_tag(self):
        self.assertEqual(spike.torch_cuda_from_version("2.8.0+cu128"), "12.8")
        self.assertEqual(spike.torch_cuda_from_version("2.8.0"), None)

    def test_system_stats_fields(self):
        data = {"system": {"comfyui_version": "0.43.2", "pytorch_version": "2.8.0+cu128"}}
        self.assertEqual(spike.parse_system_stats(data),
                         {"comfyui": "0.43.2", "torch": "2.8.0+cu128", "cuda": "12.8"})
        self.assertEqual(spike.parse_system_stats({}), {"comfyui": "", "torch": "", "cuda": ""})

    def test_ollama_ps_names(self):
        self.assertEqual(spike.parse_ollama_ps({"models": [{"name": "a:1"}, {"model": "b:2"}]}), ["a:1", "b:2"])
        self.assertEqual(spike.parse_ollama_ps({"models": []}), [])


class WorkflowTests(unittest.TestCase):
    def test_shipped_workflow_is_valid_and_has_seed_and_prompt(self):
        wf = spike.load_workflow(WORKFLOW)
        self.assertEqual(spike.find_by_title(wf, "seed"), ["7"])
        self.assertEqual(spike.find_by_title(wf, "prompt"), ["3"])
        self.assertEqual(spike.workflow_steps(wf), 8)
        self.assertEqual(sorted(spike.node_ids(wf, spike.LOADER_CLASSES)), ["1", "2"])
        self.assertEqual(spike.node_ids(wf, (spike.SAMPLER_CLASS,)), ["11"])

    def test_injection_sets_seed_and_prompt_without_touching_the_original(self):
        wf = spike.load_workflow(WORKFLOW)
        out = spike.inject(wf, 777, "a red fox runs")
        self.assertEqual(out["7"]["inputs"]["noise_seed"], 777)
        self.assertEqual(out["3"]["inputs"]["text"], "a red fox runs")
        self.assertEqual(wf["7"]["inputs"]["noise_seed"], 42)
        self.assertEqual(out["4"]["inputs"]["text"], wf["4"]["inputs"]["text"])  # negative prompt untouched

    def test_missing_seed_title_is_refused(self):
        wf = {"1": {"class_type": "X", "inputs": {"text": "a"}, "_meta": {"title": "prompt"}}}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "w.json"
            path.write_text(json.dumps(wf), encoding="utf-8")
            with self.assertRaises(spike.WorkflowError):
                spike.load_workflow(path)

    def test_duplicate_prompt_title_is_refused(self):
        wf = {
            "1": {"class_type": "R", "inputs": {"noise_seed": 1}, "_meta": {"title": "seed"}},
            "2": {"class_type": "C", "inputs": {"text": "a"}, "_meta": {"title": "prompt"}},
            "3": {"class_type": "C", "inputs": {"text": "b"}, "_meta": {"title": "prompt"}},
        }
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "w.json"
            path.write_text(json.dumps(wf), encoding="utf-8")
            with self.assertRaises(spike.WorkflowError):
                spike.load_workflow(path)

    def test_non_node_entries_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "w.json"
            path.write_text(json.dumps({"1": {"inputs": {}}}), encoding="utf-8")
            with self.assertRaises(spike.WorkflowError):
                spike.load_workflow(path)

    def test_workflow_hash_is_sha256_of_the_bytes(self):
        self.assertEqual(spike.workflow_hash(b"abc"),
                         "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


class TimingTests(unittest.TestCase):
    ENTRY = {"status": {"messages": [
        ["execution_start", {"prompt_id": "p", "timestamp": 1000}],
        ["executing", {"node": "1", "prompt_id": "p", "timestamp": 1001}],
        ["executed", {"node": "1", "output": {}, "prompt_id": "p", "timestamp": 21000}],
        ["executed", {"node": "2", "output": {}, "prompt_id": "p", "timestamp": 31000}],
        ["executing", {"node": "11", "prompt_id": "p", "timestamp": 40000}],
        ["executed", {"node": "11", "output": {}, "prompt_id": "p", "timestamp": 100000}],
    ]}}

    def test_load_and_sampler_times(self):
        load_s, sampler_s = spike.timings_from_history(self.ENTRY, ["1", "2"], "11")
        self.assertEqual(load_s, 30.0)  # last loader finished at 31000 ms
        self.assertEqual(sampler_s, 60.0)

    def test_sampler_per_step(self):
        self.assertEqual(spike.sampler_s_per_step(60.0, 8), 7.5)
        self.assertIsNone(spike.sampler_s_per_step(None, 8))
        self.assertIsNone(spike.sampler_s_per_step(60.0, None))

    def test_missing_messages_give_none(self):
        self.assertEqual(spike.timings_from_history({}, ["1"], "11"), (None, None))

    def test_output_files_are_found_under_any_known_key(self):
        entry = {"outputs": {"14": {"images": [{"filename": "a.mp4", "subfolder": "video", "type": "output"}]},
                             "5": {"gifs": [{"filename": "b.gif"}]}}}
        names = [f["filename"] for f in spike.find_output_files(entry)]
        self.assertEqual(names, ["a.mp4", "b.gif"])


class SpillAndGuardTests(unittest.TestCase):
    def test_spill_needs_more_than_half_a_gigabyte_above_idle(self):
        idle = 1 * 1024 ** 3
        self.assertFalse(spike.spill_check(idle, [idle + 0.4 * 1024 ** 3])[0])
        flagged, excess = spike.spill_check(idle, [idle + 0.2 * 1024 ** 3, idle + 0.9 * 1024 ** 3])
        self.assertTrue(flagged)
        self.assertAlmostEqual(excess, 0.9 * 1024 ** 3, delta=1.0)

    def test_spill_unknown_without_idle_or_samples(self):
        self.assertEqual(spike.spill_check(None, [1.0]), (False, None))
        self.assertEqual(spike.spill_check(1.0, []), (False, None))

    def test_idle_value_is_the_median(self):
        self.assertEqual(spike.idle_value([1.0, 9.0, 2.0]), 2.0)
        self.assertIsNone(spike.idle_value([]))

    def test_guard_problems_lists_every_reason(self):
        lease = SimpleNamespace(holder="kalamanch")
        problems = spike.guard_problems(["m:1"], [{"name": "ollama"}], lease)
        self.assertEqual(len(problems), 3)
        self.assertIn("Ollama", problems[0])
        self.assertIn("compute processes", problems[1])
        self.assertIn("kalamanch", problems[2])

    def test_guard_passes_only_with_comfyui_lease_and_nothing_else(self):
        self.assertEqual(spike.guard_problems([], [], SimpleNamespace(holder="comfyui")), [])
        self.assertTrue(spike.guard_problems([], [], None))
        self.assertTrue(spike.guard_problems([], [], None, lease_error="bad json"))

    def _fake_lease_module(self, lease=None, error=None, models=()):
        module = mock.Mock()
        module.loaded_models.return_value = list(models)
        if error:
            module.read.side_effect = ValueError(error)
        else:
            module.read.return_value = lease
        return module

    def test_guard_state_refuses_when_another_process_uses_the_gpu(self):
        module = self._fake_lease_module(lease=SimpleNamespace(holder="comfyui"))
        with mock.patch.object(spike, "read_compute_apps", return_value=[{"pid": 9, "name": "x", "used_mb": 1.0}]):
            problems = spike.guard_state("http://x", "http://y", lease_module=module)
        self.assertEqual(len(problems), 1)
        self.assertIn("compute processes", problems[0])

    def test_guard_state_clear_when_all_three_checks_pass(self):
        module = self._fake_lease_module(lease=SimpleNamespace(holder="comfyui"))
        with mock.patch.object(spike, "read_compute_apps", return_value=[]):
            self.assertEqual(spike.guard_state("http://x", "http://y", lease_module=module), [])

    def test_guard_state_refuses_when_nvidia_smi_fails(self):
        module = self._fake_lease_module(lease=SimpleNamespace(holder="comfyui"))
        with mock.patch.object(spike, "read_compute_apps", side_effect=RuntimeError("no nvidia-smi")):
            problems = spike.guard_state("http://x", "http://y", lease_module=module)
        self.assertTrue(any("nvidia-smi" in p for p in problems))

    def test_run_once_refuses_before_contacting_comfyui(self):
        module = self._fake_lease_module(lease=None)
        with mock.patch.object(spike, "read_compute_apps", return_value=[]), \
                mock.patch.object(spike, "http_json", side_effect=AssertionError("must not contact ComfyUI")), \
                mock.patch.object(spike, "submit_prompt", side_effect=AssertionError("must not submit")):
            with self.assertRaises(spike.GuardRefused):
                spike.run_once(workflow_path=WORKFLOW, seed=1, prompt="p", settings="s", out_dir=".",
                               comfy_url="http://127.0.0.1:1", container="", ollama_native="http://127.0.0.1:1",
                               lease_module=module)


class CsvTests(unittest.TestCase):
    def test_header_then_rows_and_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sub" / "baseline.csv"
            spike.append_row(path, spike.make_row(workflow_hash="h", seed=42, settings="spike=baseline",
                                                  wall_s=12.3456, spill=False, load_s=None))
            spike.append_row(path, spike.make_row(workflow_hash="h", seed=43, spill=True))
            with path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            self.assertEqual(rows[0], spike.COLUMNS)
            self.assertEqual(len(rows), 3)
            first = dict(zip(spike.COLUMNS, rows[1]))
            self.assertEqual(first["wall_s"], "12.346")
            self.assertEqual(first["spill"], "false")
            self.assertEqual(first["load_s"], "")
            self.assertEqual(first["psnr"], "")
            self.assertEqual(dict(zip(spike.COLUMNS, rows[2]))["spill"], "true")

    def test_different_header_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "b.csv"
            path.write_text("a,b\n1,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                spike.append_row(path, spike.make_row(seed=1))

    def test_unknown_column_is_refused(self):
        with self.assertRaises(ValueError):
            spike.make_row(seed=1, bogus=2)

    def test_settings_string(self):
        self.assertEqual(spike.settings_string([("a", 1), ("b", "x")]), "a=1;b=x")


class CliTests(unittest.TestCase):
    def test_dry_run_contacts_nothing_and_writes_nothing(self):
        with mock.patch.object(spike, "http_json", side_effect=AssertionError("network")), \
                mock.patch.object(spike, "append_row", side_effect=AssertionError("csv")), \
                mock.patch.object(spike, "read_compute_apps", side_effect=AssertionError("gpu")):
            self.assertEqual(spike.main(["--dry-run"]), 0)

    def test_main_refuses_with_exit_2_when_guards_fail(self):
        with mock.patch.object(spike, "guard_state", return_value=["Ollama still has models loaded (x)"]), \
                mock.patch.object(spike, "submit_prompt", side_effect=AssertionError("must not submit")):
            self.assertEqual(spike.main(["--container", ""]), 2)

    def test_quality_refuses_with_exit_2_when_guards_fail(self):
        with mock.patch.object(spike, "guard_state", return_value=["no GPU lease is held"]), \
                mock.patch.object(quality, "_run", side_effect=AssertionError("must not run")):
            self.assertEqual(quality.main(["--workflow", "ltx098", "--seeds", "3"]), 2)

    def test_quality_rejects_bad_seed_count_and_unknown_variant(self):
        self.assertEqual(quality.main(["--seeds", "0"]), 2)
        self.assertEqual(quality.main(["--variant", "nope"]), 2)


class MetricTests(unittest.TestCase):
    def test_identical_frames_have_capped_psnr_and_unit_ssim(self):
        plane = bytes(range(64)) * 4  # 16 x 16
        self.assertEqual(quality.psnr_frame(plane, plane), quality.PSNR_CAP_DB)
        self.assertAlmostEqual(quality.ssim_frame(plane, plane, 16, 16), 1.0)

    def test_psnr_matches_the_formula(self):
        a = bytes([100] * 100)
        b = bytes([110] * 100)  # every sample off by 10: MSE 100
        self.assertAlmostEqual(quality.psnr_frame(a, b), 10.0 * math.log10(255 ** 2 / 100.0), places=9)

    def test_ssim_drops_for_a_changed_picture(self):
        w = h = 16
        a = bytes((x * 13) % 256 for x in range(w * h))
        b = bytes(255 - v for v in a)  # inverted: strongly different
        self.assertLess(quality.ssim_frame(a, b, w, h), 0.5)

    def test_small_noise_keeps_ssim_close_to_one(self):
        w = h = 16
        a = bytes((x * 7) % 256 for x in range(w * h))
        b = bytes(min(255, v + 1) for v in a)
        self.assertGreater(quality.ssim_frame(a, b, w, h), 0.99)

    def test_size_and_shape_errors(self):
        with self.assertRaises(ValueError):
            quality.psnr_frame(b"ab", b"abc")
        with self.assertRaises(ValueError):
            quality.ssim_frame(b"x" * 16, b"x" * 16, 8, 8)  # 16 bytes is not an 8 x 8 plane (64 bytes)
        with self.assertRaises(ValueError):
            quality.ssim_frame(b"x" * 4, b"x" * 4, 2, 2)  # smaller than one 8x8 block

    def test_frames_split_and_compare(self):
        raw = bytes(range(256)) * 3  # three 16x16 frames
        frames = quality.frames_from_raw(raw, 16, 16)
        self.assertEqual(len(frames), 3)
        psnrs, ssims = quality.compare_frames(frames, frames, 16, 16)
        self.assertEqual(psnrs, [quality.PSNR_CAP_DB] * 3)
        for value in ssims:
            self.assertAlmostEqual(value, 1.0, places=9)
        with self.assertRaises(ValueError):
            quality.frames_from_raw(b"abc", 16, 16)
        with self.assertRaises(ValueError):
            quality.compare_frames(frames, frames[:2], 16, 16)


class ThresholdTests(unittest.TestCase):
    def test_threshold_is_mean_minus_three_std_when_noise_is_large(self):
        values = [40.0, 41.0, 42.0]  # mean 41, stdev 1 -> margin 3
        self.assertAlmostEqual(quality.tier_a_threshold(values, 0.5), 38.0)

    def test_floor_applies_when_repeats_agree(self):
        values = [0.9990, 0.9990, 0.9990]  # stdev 0 -> margin is the floor
        self.assertAlmostEqual(quality.tier_a_threshold(values, 0.002), 0.9970)

    def test_needs_two_repeats(self):
        with self.assertRaises(ValueError):
            quality.tier_a_threshold([40.0], 0.5)

    def test_tier_a_pass_and_drop(self):
        self.assertTrue(quality.evaluate_tier_a([40.0, 41.0], [0.99, 0.99], 39.0, 0.98))
        self.assertFalse(quality.evaluate_tier_a([38.0, 38.0], [0.99, 0.99], 39.0, 0.98))  # PSNR fails
        self.assertFalse(quality.evaluate_tier_a([40.0], [0.97], 39.0, 0.98))  # SSIM fails
        self.assertFalse(quality.evaluate_tier_a([], [], 0.0, 0.0))

    def test_side_by_side_command(self):
        cmd = quality.side_by_side_cmd("a.mp4", "b.mp4", "out.mp4")
        self.assertIn("hstack=inputs=2", cmd)
        self.assertEqual(cmd[-1], "out.mp4")

    def test_shipped_variants_have_no_patch_yet_and_tiers_are_set(self):
        for name, v in quality.VARIANTS.items():
            self.assertIn(v["tier"], ("A", "B"), name)
            self.assertIsNone(v["patch"], name)


if __name__ == "__main__":
    unittest.main()
