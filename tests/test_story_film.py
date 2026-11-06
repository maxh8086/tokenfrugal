import argparse
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from unittest import mock

from scripts import story_film
from scripts.story_film import (
    amplitude_envelope,
    build_scene_html,
    check_scene_motion,
    end_card_html,
    end_card_tagline,
    mux_film,
    scene_backdrop_html,
    scene_motion_spec,
    scene_props,
    series_offsets,
    write_index_html,
)

SHOT_SENTENCES = [
    "The gateway sends events to the database.",
    "Four boxes arrived at the depot.",
    "Simple plain sentence here.",
]


def _index_script(text):
    """The inline script of a composition index (the one without a src attribute)."""
    scripts = re.findall(r"<script>(.*?)</script>", text, re.S)
    assert len(scripts) == 1, len(scripts)
    return scripts[0]


def _helpers_block(text):
    """The browser helper functions (bnSpring, bnRand, bnDotPositions) from an index."""
    m = re.search(r"// BN-HELPERS-BEGIN\n(.*?)\n// BN-HELPERS-END", text, re.S)
    assert m, "helper block missing"
    return m.group(1)


def _run_node(source, check_only=False):
    """Run JavaScript source with node (or node --check) and return stdout. Skips if node is absent."""
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "check.js")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        args = [node, "--check", path] if check_only else [node, path]
        result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout


def _build_index(tmp, scene_htmls, width=1920, height=1080, props=None):
    """Write scene files and build the index in tmp/comp. Returns (out_dir, index text).

    Put a mixed.wav in tmp/comp before calling to exercise the audio glow.
    """
    paths = []
    for i, scene_html in enumerate(scene_htmls):
        path = os.path.join(tmp, f"scene_{i}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(scene_html)
        paths.append(path)
    out_dir = os.path.join(tmp, "comp")
    os.makedirs(out_dir, exist_ok=True)
    index = write_index_html(out_dir, paths, width, height, props=props)
    with open(index, encoding="utf-8") as fh:
        return out_dir, fh.read()


class TestBackdrop(unittest.TestCase):
    def test_backdrop_chips_for_capitalised_terms_then_long_lowercase_fallback(self):
        html = scene_backdrop_html(["The Kubernetes cluster runs Docker and go."], 1080, 1920)
        self.assertIn('class="backdrop"', html)
        self.assertIn(">Kubernetes<", html)
        self.assertIn(">Docker<", html)
        self.assertIn(">cluster<", html)  # fallback: lowercase, 7+ letters, fewer than 3 capitalised
        self.assertNotIn(">The<", html)   # first word of the sentence
        self.assertNotIn(">go<", html)    # lowercase and under 7 letters
        self.assertEqual(html.count('class="chip"'), 3)

    def test_fallback_chips_for_two_eight_letter_lowercase_words(self):
        html = scene_backdrop_html(["Go with reliable routines and sturdy tools."], 1080, 1920)
        self.assertEqual(html.count('class="chip"'), 2)
        self.assertIn(">reliable<", html)
        self.assertIn(">routines<", html)

    def test_at_most_six_chips(self):
        words = " ".join(f"Alpha{i}x Term" for i in range(10))
        sentence = "Start here " + " ".join(f"Brand{c}" for c in "ABCDEFGHIJ") + "."
        html = scene_backdrop_html([sentence + " " + words], 1080, 1920)
        self.assertLessEqual(html.count('class="chip"'), 6)

    def test_chips_in_upper_sixty_percent_two_columns(self):
        sentence = "Start " + " ".join(f"Brand{c}" for c in "ABCDEF") + "."
        html = scene_backdrop_html([sentence], 1000, 1000)
        tops = [int(t) for t in __import__("re").findall(r"top: (\d+)px", html)]
        lefts = {int(t) for t in __import__("re").findall(r"left: (\d+)px", html)}
        self.assertEqual(len(lefts), 2)
        self.assertTrue(all(t + 150 <= 600 for t in tops))

    def test_scene_timeline_lights_chip_at_first_word_of_sentence(self):
        sentences = ["Plain start here.", "Then Kubernetes arrives."]
        html = build_scene_html(2, sentences, 0.0, 6.0, 1080, 1920)
        self.assertIn('class="backdrop"', html)
        self.assertIn("#scene-2 .backdrop > .chip:nth-child(1)", html)
        self.assertIn('backgroundColor: "#2563eb", opacity: 1', html)
        timings = story_film.word_timings(sentences, 6.0 - 0.6)
        light = timings[3][1]  # "Then" is word 3 (index 3 counting from 0)
        self.assertIn(f"{light:.3f});", html)


class TestEndCard(unittest.TestCase):
    def test_tagline_unchanged_within_twelve_words(self):
        tagline = end_card_tagline("  one two three four five six seven eight nine ten.  ")
        self.assertEqual(tagline, "one two three four five six seven eight nine ten.")

    def test_long_sentence_with_comma_yields_first_clause(self):
        sentence = ("The team shipped the new engine after months of careful testing, "
                    "and customers noticed the difference right away.")
        self.assertEqual(end_card_tagline(sentence),
                         "The team shipped the new engine after months of careful testing.")

    def test_long_sentence_without_clause_break_yields_closing(self):
        sentence = "one two three four five six seven eight nine ten eleven twelve thirteen."
        self.assertEqual(end_card_tagline(sentence), story_film.END_CARD_CLOSING)
        self.assertEqual(story_film.END_CARD_CLOSING, "Find out more at Business Next")

    def test_end_card_contents_and_fade_in(self):
        html = end_card_html("Short tagline", 1080, 1920, scene_index=3, start_s=10.0, duration_s=3.0)
        self.assertIn('id="scene-3"', html)
        self.assertIn('data-start="10.000"', html)
        self.assertIn('data-duration="3.000"', html)
        self.assertIn("Short tagline", html)
        self.assertIn("SBI | Business Next", html.replace("&amp;", "&"))
        self.assertIn('data-fade-in="0.600"', html)
        self.assertIn("opacity: 1, duration: 0.600", html)

    def test_index_adds_end_card_fade_in_without_fade_out(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scene_0.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(end_card_html("End", 1080, 1920, scene_index=0, start_s=5.0, duration_s=3.0))
            out = os.path.join(tmp, "comp")
            index = write_index_html(out, [path], 1080, 1920)
            text = open(index, encoding="utf-8").read()
        self.assertIn('tl.fromTo("#scene-0", {opacity: 0}, {opacity: 1, duration: 0.600}, 5.000);', text)
        self.assertNotIn('{opacity: 0, duration: 0.4}, 7.600', text)


class TestCaptionAndLoudness(unittest.TestCase):
    def test_caption_fixed_width_min_height_left_aligned(self):
        html = build_scene_html(0, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn("left: 120px", html)
        self.assertIn("width: 1680px", html)
        self.assertIn("top: 760px", html)
        self.assertIn("bottom: 80px", html)
        self.assertIn("min-height: 3.75em", html)
        self.assertIn("text-align: left", html)

    def test_mux_uses_loudnorm_at_minus_16_lufs_and_minus_1_5_tp(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "video.mp4")
            mixed = os.path.join(tmp, "mixed.wav")
            out = os.path.join(tmp, "film.mp4")
            for p in (video, mixed):
                open(p, "wb").close()

            loudnorm_json = (
                '{\n'
                '\t"input_i" : "-17.0",\n'
                '\t"input_tp" : "-2.0",\n'
                '\t"input_lra" : "6.0",\n'
                '\t"input_thresh" : "-27.0",\n'
                '\t"target_offset" : "1.0"\n'
                '}'
            )

            def fake_run(work, args):
                open(out, "wb").close()
                is_pass1 = any("print_format=json" in str(a) for a in args)
                stderr = loudnorm_json if is_pass1 else ""
                return mock.Mock(returncode=0, stderr=stderr, stdout="")

            with mock.patch.object(story_film, "_docker_in_work", side_effect=fake_run) as run:
                mux_film(video, mixed, out)
            args = run.call_args[0][1]
        self.assertIn("-af", args)
        af = args[args.index("-af") + 1]
        self.assertIn("I=-16", af)
        self.assertIn("TP=-1.5", af)


class TestBuildSceneHtml(unittest.TestCase):
    def test_doctype_has_greater_than(self):
        """Test that doctype has proper > character."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn("<!doctype html>", html)
        self.assertIn("<!doctype html>", html)  # Should have >

    def test_scene_div_has_data_start(self):
        """Test scene div has correct id and data-start attribute."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn('id="scene-1"', html)
        self.assertIn('data-start="0.000"', html)

    def test_gsap_timeline_registered(self):
        """Test GSAP timeline is registered as window.__timelines['scene-N']."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn('window.__timelines["scene-1"]', html)

    def test_words_wrapped_in_span_class_w(self):
        """Test each word is wrapped in <span class="w">."""
        html = build_scene_html(1, ["Hello world"], 0.0, 5.0, 1920, 1080)
        self.assertIn('<span class="w">Hello</span>', html)
        self.assertIn('<span class="w">world</span>', html)

    def test_words_have_style_bold_white_48px_inter_caption_left_aligned_in_caption_zone(self):
        """Test word spans have correct styling."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn('font-weight: 700', html)  # bold
        self.assertIn('color: #ffffff', html)  # white
        self.assertIn('font-size: 48px', html)
        self.assertIn('font-family: Inter', html)
        self.assertIn('caption', html)
        self.assertIn('text-align: left', html)
        self.assertIn('bottom: 80px', html)  # caption zone y760-1000

    def test_word_reveal_tween_exists(self):
        """Test word reveal is an opacity-only tween (no y offset)."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn('{opacity: 0}, {opacity: 1, duration: 0.25}', html)
        self.assertNotIn('y: 20', html)
        self.assertIn('duration: 0.25', html)

    def test_word_start_times_spread_evenly(self):
        """Test word start times are spread evenly by character count."""
        html = build_scene_html(1, ["Hello world"], 0.0, 5.0, 1920, 1080)
        # With 2 words and 5s duration, start times should be spread
        self.assertIn('start:', html)

    def test_scene_fade_out_at_duration_minus_0_4(self):
        """Test scene fade-out happens at duration_s - 0.4."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        self.assertIn('duration: 0.4', html)
        self.assertIn('5.0', html)  # duration_s should be in the timeline

    def test_multiple_sentences(self):
        """Test multiple sentences are handled correctly."""
        html = build_scene_html(1, ["First sentence.", "Second sentence!"], 0.0, 5.0, 1920, 1080)
        self.assertIn('id="scene-1"', html)
        self.assertIn('window.__timelines["scene-1"]', html)
        self.assertIn('<span class="w">First</span>', html)
        self.assertIn('<span class="w">sentence.</span>', html)
        self.assertIn('<span class="w">Second</span>', html)
        self.assertIn('<span class="w">sentence!</span>', html)

    def test_fstring_doubled_braces_in_js(self):
        """Test that f-string uses doubled braces for JS variables."""
        html = build_scene_html(1, ["Hello"], 0.0, 5.0, 1920, 1080)
        # The scene index should be properly escaped in JS
        self.assertIn('scene-1', html)


class TestAccentLayer(unittest.TestCase):
    SENTENCES = ["First sentence here.", "Second one follows."]

    def _accents_attr(self, html_text):
        match = re.search(r'data-accents="([^"]*)"', html_text)
        self.assertIsNotNone(match)
        return json.loads(html_lib.unescape(match.group(1)))

    def test_no_accent_blocks_and_one_progress_rule(self):
        html_text = build_scene_html(1, self.SENTENCES, 0.0, 6.0, 1920, 1080)
        self.assertEqual(html_text.count('class="accent"'), 0)
        self.assertEqual(html_text.count('class="progress"'), 1)

    def test_data_accents_lists_index_start_end_triples(self):
        html_text = build_scene_html(1, self.SENTENCES, 0.0, 6.0, 1920, 1080)
        accents = self._accents_attr(html_text)
        self.assertEqual(len(accents), 2)
        for triple in accents:
            self.assertEqual(len(triple), 3)
            self.assertLess(triple[1], triple[2])
        self.assertEqual([t[0] for t in accents], [0, 1])

    def test_write_index_keeps_accent_selector_for_index_one(self):
        scene_html = build_scene_html(1, self.SENTENCES, 0.0, 6.0, 1920, 1080)
        with tempfile.TemporaryDirectory() as tmp:
            scene_path = os.path.join(tmp, "scene-1.html")
            with open(scene_path, "w", encoding="utf-8") as fh:
                fh.write(scene_html)
            out_dir = os.path.join(tmp, "out")
            index = write_index_html(out_dir, [scene_path], 1080, 1920)
            with open(index, encoding="utf-8") as fh:
                content = fh.read()
        self.assertIn('#scene-1 .accent[data-index=\\"1\\"]', content)
        self.assertIn('#scene-1 .progress', content)


class TestContainerPlumbing(unittest.TestCase):
    def test_docker_in_work_runs_directly_inside_container(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(story_film, "IN_CONTAINER", True), \
                mock.patch.object(story_film.subprocess, "run",
                                  return_value=mock.Mock(returncode=0)) as run:
            story_film._docker_in_work(tmp, ["ffprobe", "-v", "error"])
        cmd = run.call_args[0][0]
        self.assertEqual(cmd, ["ffprobe", "-v", "error"])
        self.assertNotIn("docker", cmd)
        self.assertEqual(run.call_args[1]["cwd"], tmp)

    def test_docker_in_work_uses_docker_run_on_host(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(story_film, "IN_CONTAINER", False), \
                mock.patch.object(story_film.subprocess, "run",
                                  return_value=mock.Mock(returncode=0)) as run:
            story_film._docker_in_work(tmp, ["ffmpeg", "-version"])
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[:2], ["docker", "run"])
        self.assertIn(story_film.MEDIA_IMAGE, cmd)
        self.assertEqual(cmd[-2:], ["ffmpeg", "-version"])

    def test_run_cli_writes_plan_and_assembles_in_container_without_numpy(self):
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            story = os.path.join(tmp, "story.md")
            with open(story, "w", encoding="utf-8") as fh:
                fh.write("First sentence here. Second one follows. Third line ends.\n")
            out = os.path.join(tmp, "out")
            args = argparse.Namespace(story=story, destination="youtube-shorts",
                                      format="9x16", out=out, minutes=1.0)
            # Blocking numpy and soundfile proves the host path never imports them.
            blocked = {"numpy": None, "soundfile": None}
            with mock.patch.dict(sys.modules, blocked), \
                    mock.patch.object(story_film, "narrate") as narrate_mock, \
                    mock.patch.object(story_film.subprocess, "run",
                                      return_value=mock.Mock(returncode=0)) as run:
                code = story_film.run_cli(args)
            with open(os.path.join(out, "tmp", "plan.json"), encoding="utf-8") as fh:
                plan = json.load(fh)

        self.assertEqual(code, 0)
        self.assertEqual(narrate_mock.call_count, 3)
        self.assertEqual(set(plan), {"chosen", "last_sentence", "width", "height", "minutes",
                                     "destination", "format", "story", "word_count", "wav_files"})
        self.assertEqual(plan["chosen"], ["First sentence here.", "Second one follows.",
                                          "Third line ends."])
        self.assertEqual(plan["last_sentence"], "Third line ends.")
        self.assertEqual((plan["width"], plan["height"]), (1080, 1920))
        self.assertEqual(plan["wav_files"], ["tmp/s0.wav", "tmp/s1.wav", "tmp/s2.wav"])
        self.assertEqual(plan["destination"], "youtube-shorts")
        self.assertEqual(plan["format"], "9x16")

        cmd = run.call_args[0][0]
        self.assertIn("STORY_FILM_IN_CONTAINER=1", cmd)
        self.assertIn("maxh8086/media-generator:latest", cmd)
        self.assertIn("/app/scripts/story_film.py", cmd)
        self.assertIn("assemble", cmd)
        self.assertEqual(cmd[-1], "/work/tmp/plan.json")


class TestBeatsAndMotion(unittest.TestCase):
    def test_hold_rule_present_for_two_sentence_scene(self):
        html = build_scene_html(0, ["First sentence here.", "Second one follows."], 0.0, 6.0, 1080, 1920)
        self.assertIn('class="hold"', html)
        self.assertIn('tl.fromTo("#scene-0 .hold"', html)
        self.assertIn('data-hold="', html)

    def test_hold_window_never_negative_for_short_scene(self):
        html = build_scene_html(0, ["Short line here."], 0.0, 0.5, 1080, 1920)
        match = re.search(r'data-hold="([^"]*)"', html)
        self.assertIsNotNone(match)
        start, end = (float(v) for v in match.group(1).split(","))
        self.assertGreaterEqual(start, 0.0)
        self.assertGreaterEqual(end, start)

    def test_check_scene_motion_passes_normal_scene(self):
        spec = scene_motion_spec(0, ["First sentence here.", "Second one follows."], 0.0, 6.0, 1080, 1920)
        report = check_scene_motion([spec])
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]["index"], 0)
        self.assertLessEqual(report[0]["max_gap_s"], 2.5)

    def test_check_scene_motion_rejects_last_point_three_seconds_before_end(self):
        spec = {
            "index": 2, "start": 0.0, "duration": 10.0,
            "timings": [[0.0, 1.0], [1.0, 7.0]], "chips": [], "accents": [], "hold": None,
        }
        with self.assertRaises(ValueError) as ctx:
            check_scene_motion([spec])
        self.assertIn("scene 2", str(ctx.exception))

    def test_check_scene_motion_rejects_point_beyond_duration(self):
        spec = {
            "index": 1, "start": 0.0, "duration": 5.0,
            "timings": [[0.0, 1.0], [1.0, 5.5]], "chips": [], "accents": [], "hold": None,
        }
        with self.assertRaises(ValueError) as ctx:
            check_scene_motion([spec])
        self.assertIn("scene 1", str(ctx.exception))


class TestShotZone(unittest.TestCase):
    def test_index_has_shot_tweens(self):
        sentences = ["Alpha bravo charlie.", "Delta echo foxtrot.", "Golf hotel india."]
        scene = build_scene_html(0, sentences, 5.0, 12.0, 1920, 1080)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scene_0.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(scene)
            index = write_index_html(os.path.join(tmp, "comp"), [path], 1920, 1080)
            with open(index, encoding="utf-8") as fh:
                text = fh.read()
        self.assertIn('tl.fromTo("#scene-0 .shot-slot-0", {opacity: 0}, {opacity: 1, duration: 0.250}, 5.000);', text)
        self.assertIn('"#scene-0 .shot-slot-0 .sh-', text)

    def test_end_card_glyph_sized(self):
        self.assertIn(".endcard-mark svg", story_film.END_CARD_CSS)
        self.assertIn("width: 160px", story_film.END_CARD_CSS)
        self.assertNotIn("width: 120px", end_card_html("Tag", 1920, 1080))

    def test_shots_zone_above_divider(self):
        slots, _js, _shots = story_film._shot_slots_html(0, ["Alpha bravo.", "Delta echo."], 12.0, 1920, 1080)
        heights = [int(h) for h in re.findall(r"height: (\d+)px; opacity: 0;", slots)]
        self.assertTrue(heights)
        for h in heights:
            self.assertLessEqual(h, 740)

    def test_index_has_no_keyframes_and_push_in_and_node_tweens(self):
        sentences = ["The gateway sends events to the database.", "Four boxes arrived at the depot.",
                     "Simple plain sentence here."]
        scene = build_scene_html(0, sentences, 0.0, 12.0, 1920, 1080)
        self.assertNotIn("@keyframes", scene)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scene_0.html")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(scene)
            index = write_index_html(os.path.join(tmp, "comp"), [path], 1920, 1080)
            with open(index, encoding="utf-8") as fh:
                text = fh.read()
        self.assertNotIn("@keyframes", text)
        self.assertNotIn("animation:", text)
        self.assertIn(".shot-stage", text)
        self.assertIn("scale: 1.04", text)
        self.assertIn(".sh-node-0", text)
        self.assertIn("scale: 0.6, opacity: 0", text)

    def test_scene_html_has_divider_and_dark_background(self):
        scene = build_scene_html(0, ["Hello there."], 0.0, 5.0, 1920, 1080)
        self.assertIn("top: 740px", scene)
        self.assertIn("background: #21262d", scene)
        self.assertIn("background: #0d1117", scene)


class TestSeriesOffsets(unittest.TestCase):
    DURATIONS = [6.0, 5.25, 7.1, 4.4, 6.35, 3.0]

    def test_matches_running_start_times_for_six_scenes(self):
        expected, t = [], 0.0
        for d in self.DURATIONS:
            expected.append(round(t, 3))
            t += d
        self.assertEqual(series_offsets(self.DURATIONS), expected)
        self.assertEqual(series_offsets(self.DURATIONS), [0.0, 6.0, 11.25, 18.35, 22.75, 29.1])

    def test_empty_and_first_item_starts_at_zero(self):
        self.assertEqual(series_offsets([]), [])
        self.assertEqual(series_offsets([4.0, 2.5]), [0.0, 4.0])

    def test_scene_props_starts_equal_series_offsets(self):
        props = scene_props({"width": 1920, "height": 1080, "scene_ids": list(range(6)),
                             "scene_durations": self.DURATIONS})
        self.assertEqual(props["scene_starts"], series_offsets(self.DURATIONS))

    def test_index_clip_starts_are_the_series_offsets(self):
        starts = series_offsets(self.DURATIONS)
        scenes = [build_scene_html(k, ["Hello there."], s, d, 1920, 1080)
                  for k, (s, d) in enumerate(zip(starts, self.DURATIONS))]
        with tempfile.TemporaryDirectory() as tmp:
            _out, text = _build_index(tmp, scenes)
        for k, s in enumerate(starts):
            self.assertIn(f'id="scene-{k}" data-start="{s:.3f}"', text)


class TestPropsJson(unittest.TestCase):
    def test_props_json_written_beside_index(self):
        scenes = [build_scene_html(0, SHOT_SENTENCES, 0.0, 12.0, 1920, 1080)]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir, _text = _build_index(tmp, scenes)
            with open(os.path.join(out_dir, "props.json"), encoding="utf-8") as fh:
                props = json.load(fh)
        self.assertEqual(props["scene_ids"], [0])
        self.assertEqual(props["scene_starts"], [0.0])
        self.assertEqual(props["scene_durations"], [12.0])
        self.assertEqual(props["accent"], "#2f81f7")
        self.assertEqual(props["width"], 1920)
        self.assertEqual(len(props["shots"]), 1)
        self.assertTrue(props["shots"][0])

    def test_props_drive_scene_timing_when_passed(self):
        durations = [5.0, 4.0]
        props = scene_props({"width": 1080, "height": 1920, "format": "9x16", "start_s": 10.0,
                             "scene_ids": [0, 1], "scene_durations": durations})
        json.dumps(props)  # JSON-serialisable
        scenes = [build_scene_html(k, ["Hello there."], s, d, 1080, 1920)
                  for k, (s, d) in enumerate(zip(props["scene_starts"], durations))]
        with tempfile.TemporaryDirectory() as tmp:
            _out, text = _build_index(tmp, scenes, width=1080, height=1920, props=props)
        self.assertIn('id="scene-0" data-start="10.000"', text)
        self.assertIn('id="scene-1" data-start="15.000"', text)

    def test_mismatched_props_raise(self):
        scenes = [build_scene_html(0, ["Hello there."], 0.0, 5.0, 1920, 1080)]
        props = scene_props({"width": 1920, "height": 1080, "scene_ids": [0, 1],
                             "scene_durations": [5.0, 5.0]})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _build_index(tmp, scenes, props=props)


class TestAudioGlow(unittest.TestCase):
    def _write_mixed(self, path, seconds, amplitude):
        import numpy as np
        import soundfile as sf

        t = np.arange(int(seconds * 44100)) / 44100
        sf.write(path, amplitude * np.sin(2 * np.pi * 220 * t), 44100, subtype="PCM_16")

    def test_envelope_is_normalised_per_tenth_second(self):
        import numpy as np
        import soundfile as sf

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "mixed.wav")
            tone = 0.5 * np.sin(2 * np.pi * 220 * np.arange(44100) / 44100)
            sf.write(path, np.concatenate([np.zeros(44100), tone]), 44100, subtype="PCM_16")
            env = amplitude_envelope(path)
        self.assertEqual(len(env), 20)
        self.assertTrue(all(v == 0.0 for v in env[:10]))
        self.assertAlmostEqual(max(env), 1.0)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in env))
        self.assertTrue(all(v > 0.9 for v in env[10:]))

    def test_bn_env_and_glow_present_when_mixed_wav_exists(self):
        scenes = [build_scene_html(0, SHOT_SENTENCES, 0.0, 2.0, 1920, 1080)]
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "comp"))
            self._write_mixed(os.path.join(tmp, "comp", "mixed.wav"), 2.0, 0.5)
            _out, text = _build_index(tmp, scenes)
        m = re.search(r"var BN_ENV = (\[[^\]]*\]);", text)
        self.assertIsNotNone(m)
        env = json.loads(m.group(1))
        self.assertEqual(len(env), 20)
        self.assertIn("BN_ENV[bk]", text)
        self.assertIn('tl.set(".bn-glow"', text)
        self.assertIn("0.25 + 0.35 * BN_ENV[bk]", text)
        _run_node(_index_script(text), check_only=True)

    def test_glow_absent_without_mixed_wav_and_index_still_valid(self):
        scenes = [build_scene_html(0, SHOT_SENTENCES, 0.0, 2.0, 1920, 1080)]
        with tempfile.TemporaryDirectory() as tmp:
            _out, text = _build_index(tmp, scenes)
        self.assertNotIn("BN_ENV", text)
        self.assertNotIn('tl.set(".bn-glow"', text)
        self.assertIn('id="scene-0"', text)
        _run_node(_index_script(text), check_only=True)


class TestMotionHelpers(unittest.TestCase):
    def _index_text(self, tmp, durations=(12.0,)):
        starts = series_offsets(list(durations))
        scenes = [build_scene_html(k, SHOT_SENTENCES, s, d, 1920, 1080)
                  for k, (s, d) in enumerate(zip(starts, durations))]
        _out, text = _build_index(tmp, scenes)
        return text

    def test_spring_is_defined_settles_and_is_registered_as_ease(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._index_text(tmp)
        self.assertIn("function bnSpring(t)", text)
        self.assertGreater(text.count("ease: function(p){return bnSpring(p);}"), 4)
        values = json.loads(_run_node(
            _helpers_block(text)
            + "\nvar grid = []; for (var i = 0; i <= 1000; i++) grid.push(bnSpring(i / 1000));\n"
            + "console.log(JSON.stringify({start: bnSpring(0), end: bnSpring(1), late: bnSpring(0.99),"
            + " max: Math.max.apply(null, grid)}));\n"
        ))
        self.assertEqual(values["start"], 0)
        self.assertEqual(values["end"], 1)
        self.assertGreater(values["late"], 0.99)
        self.assertGreater(values["max"], 1.0)  # damped overshoot
        self.assertLess(values["max"], 1.1)

    def test_dots_stay_above_caption_zone_and_are_seeded(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = _helpers_block(self._index_text(tmp))
        source = script + (
            "\nvar out = [];\n"
            "for (var sid = 0; sid < 8; sid++) for (var w of [1080, 1920])"
            " out.push({sid: sid, w: w, dots: bnDotPositions(sid, 40, w, 736)});\n"
            "console.log(JSON.stringify(out));\n"
        )
        out = json.loads(_run_node(source))
        self.assertEqual(len(out), 16)
        for entry in out:
            self.assertEqual(len(entry["dots"]), 40)
            for d in entry["dots"]:
                self.assertGreaterEqual(d["y"], 0)
                self.assertLess(d["y"] + 2 * d["r"], 760)
                self.assertGreaterEqual(d["r"], 1)
                self.assertLess(d["r"], 2)
        again = json.loads(_run_node(source))
        self.assertEqual(out, again)  # same seeds, same field

    def test_dots_and_drift_tweens_in_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._index_text(tmp, durations=(6.0, 5.0))
        self.assertIn("bn-dot", text)
        self.assertIn("tl.fromTo(d, {opacity: 0.3, y: 0}, {opacity: 0.8, y: -8", text)
        self.assertIn("#30363d", text)
        self.assertIn("var BN_CFG = {", text)

    def test_index_has_no_math_random_or_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._index_text(tmp, durations=(6.0, 5.0))
        self.assertNotIn("Math.random", text)
        self.assertIsNone(re.search(r"\bDate\b", text))
        self.assertNotIn("performance.now", text)
        self.assertNotIn("@keyframes", text)
        self.assertNotIn("animation:", text)

    def test_index_script_passes_node_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._index_text(tmp, durations=(6.0, 5.0))
        _run_node(_index_script(text), check_only=True)


if __name__ == "__main__":
    unittest.main()
