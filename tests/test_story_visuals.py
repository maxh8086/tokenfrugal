import os
import unittest

import re

from scripts.story_film import _group_scenes, parse_story
from scripts.story_visuals import (
    ACCENT,
    SPRING_EASE_JS,
    _panel_html,
    shot_tween_js,
    choose_group_type,
    choose_shot_type,
    glyph_for,
    glyph_set,
    shot_html,
    split_scene,
)

_STORY_MD = "Benchmark/story-test/outputs-v3/linkedin/ministral-3-8b/topic-2/story.md"

_DIAGRAM_SENTENCES = ["The gateway sends events to the database.", "The user connects to the cloud."]
_DATA_SENTENCES = ["Four boxes arrived."]
_STATEMENT_SENTENCES = ["Simple plain sentence here."]


def _shot(sentences, kind):
    return {"start_s": 0.0, "end_s": 6.0, "type": kind, "sentences": sentences}


_SAMPLES = {
    "diagram": _shot(_DIAGRAM_SENTENCES, "diagram"),
    "data": _shot(_DATA_SENTENCES, "data"),
    "statement": _shot(_STATEMENT_SENTENCES, "statement"),
}


class TestChooseShotType(unittest.TestCase):
    def test_digit_sentence_is_data(self):
        self.assertEqual(choose_shot_type("Latency fell by 40 percent."), "data")

    def test_number_word_is_data(self):
        self.assertEqual(choose_shot_type("Three services restarted."), "data")

    def test_connecting_word_is_diagram(self):
        self.assertEqual(choose_shot_type("The gateway sends events to the database."), "diagram")

    def test_plain_sentence_is_statement(self):
        self.assertEqual(choose_shot_type("Simple plain sentence here."), "statement")


class TestSplitScene(unittest.TestCase):
    def test_covers_duration_without_gaps(self):
        shots = split_scene(["a b.", "c d.", "e f.", "g h."], 20.0)
        self.assertEqual(len(shots), 4)
        self.assertEqual(shots[0]["start_s"], 0.0)
        self.assertEqual(shots[-1]["end_s"], 20.0)
        for prev, cur in zip(shots, shots[1:]):
            self.assertEqual(prev["end_s"], cur["start_s"])
        for shot in shots:
            length = shot["end_s"] - shot["start_s"]
            self.assertGreaterEqual(length, 4.0)
            self.assertLessEqual(length, 6.0)
        self.assertEqual(sum(len(s["sentences"]) for s in shots), 4)

    def test_zero_duration_raises(self):
        with self.assertRaises(ValueError):
            split_scene(["a b.", "c d."], 0)


class TestGlyphFor(unittest.TestCase):
    def test_database_keyword(self):
        self.assertEqual(glyph_for("the database is fast"), "database")

    def test_default_glyph(self):
        self.assertEqual(glyph_for("nothing relevant"), "document")


class TestShotHtml(unittest.TestCase):
    def test_each_type_is_a_shot_div(self):
        for kind, shot in _SAMPLES.items():
            with self.subTest(kind=kind):
                out = shot_html(shot)
                self.assertTrue(out.startswith("<div"))
                self.assertIn(f"shot-{kind}", out)

    def test_no_colour_or_background_transition(self):
        for kind, shot in _SAMPLES.items():
            with self.subTest(kind=kind):
                out = shot_html(shot)
                self.assertNotIn("transition:", out.replace("transition:none", ""))
                self.assertIsNone(re.search(r"transition:[^;]*(color|background)", out))
                self.assertIsNone(re.search(r"transition:\s*(color|background)", out))

    def test_font_sizes_are_at_least_20px(self):
        for kind, shot in _SAMPLES.items():
            with self.subTest(kind=kind):
                sizes = [int(v) for v in re.findall(r"font-size:\s*(\d+)px", shot_html(shot))]
                if kind != "diagram":
                    self.assertTrue(sizes)
                for size in sizes:
                    self.assertGreaterEqual(size, 20)

    def test_statement_text_is_escaped(self):
        # Statement shots show a glyph, not the sentence, so the sentence markup must not leak.
        out = shot_html(_shot(["Use <b>bold</b> text."], "statement"))
        self.assertNotIn("<b>", out)

    def test_diagram_has_two_to_four_tiles(self):
        out = shot_html(_SAMPLES["diagram"])
        tiles = out.count('class="sh-node sh-node-')
        self.assertGreaterEqual(tiles, 2)
        self.assertLessEqual(tiles, 4)


class TestGroupTypes(unittest.TestCase):
    def test_one_is_not_data(self):
        self.assertEqual(choose_group_type(["No one briefed me."], None), "statement")
        self.assertEqual(choose_group_type(["Four boxes arrived."], None), "data")

    def test_data_never_follows_data(self):
        self.assertNotEqual(choose_group_type(["Four boxes arrived."], "data"), "data")

    def test_glyph_set(self):
        self.assertEqual(
            glyph_set(["At the depot, the loader and dispatcher deferred."]), ["door", "user"]
        )


class TestNoKeyframes(unittest.TestCase):
    def test_shot_html_has_no_keyframes(self):
        expected_class = {"diagram": "sh-node", "data": "sh-big", "statement": "sh-node"}
        for kind, shot in _SAMPLES.items():
            with self.subTest(kind=kind):
                out = shot_html(shot)
                self.assertNotIn("@keyframes", out)
                self.assertNotIn("animation:", out)
                self.assertIn(expected_class[kind], out)
                self.assertIn("sh-", out)


_FILLER = ("total", "rate", "share")
_SCENE = [
    "Four boxes arrived at the depot.",
    "The sensor reported in from the truck.",
    "Simple plain sentence here.",
]


class TestVisualLayout(unittest.TestCase):
    def test_one_is_never_a_figure(self):
        self.assertNotEqual(choose_group_type(["One team arrived."], None), "data")

    def test_data_shot_has_no_filler_labels(self):
        shot = _shot(["Four boxes arrived.", "Two depots closed."], "data")
        out = shot_html(shot).lower()
        self.assertIn("sh-row-1", out)
        for word in _FILLER:
            self.assertNotIn(f">{word}<", out)

    def test_single_figure_uses_big_number_layout(self):
        out = shot_html(_shot(["Six years passed."], "data"))
        self.assertIn("sh-big", out)
        self.assertNotIn("sh-row-0", out)
        self.assertIn(">Six<", out)
        self.assertIn(">years<", out)

    def test_heading_never_repeats_caption(self):
        for shot in split_scene(_SCENE, 12.0):
            caption = " ".join(_SCENE)
            out = shot_html(shot, caption=caption)
            heading = re.search(r'class="sh-title"[^>]*>([^<]*)</p>', out).group(1)
            with self.subTest(heading=heading):
                self.assertNotIn(heading.lower(), caption.lower())
                self.assertLessEqual(len(heading.split()), 4)
                subline = re.search(r'class="sh-sub"[^>]*>([^<]*)</p>', out).group(1)
                self.assertLessEqual(len(subline.split()), 12)

    def test_shot_elements_stay_above_divider(self):
        for kind, shot in _SAMPLES.items():
            with self.subTest(kind=kind):
                tops = [int(t) for t in re.findall(r"top:(\d+)px", shot_html(shot))]
                self.assertTrue(tops)
                self.assertLess(max(tops), 740)


@unittest.skipUnless(os.path.exists(_STORY_MD), "needs local Benchmark/story-test output (not in repo)")
class TestStorySentencesMix(unittest.TestCase):
    def test_story_sentences_mix(self):
        sentences = parse_story(_STORY_MD)
        scenes = [[sentences[i] for i in group] for group in _group_scenes(len(sentences))]
        self.assertEqual(len(scenes), 5)
        types = [[shot["type"] for shot in split_scene(scene, 11.4)] for scene in scenes]
        flat = [t for scene in types for t in scene]
        message = f"shot types per scene: {types}"
        self.assertGreaterEqual(flat.count("diagram"), 2, message)
        self.assertGreaterEqual(flat.count("data"), 1, message)
        for scene in types:
            for prev, cur in zip(scene, scene[1:]):
                self.assertFalse(prev == "data" and cur == "data", message)


class TestSpringAndGlowMarkup(unittest.TestCase):
    SPRING = "ease: function(p){return bnSpring(p);}"

    def _tween_lines(self, kind, count):
        shot = {"type": kind, "length": 6.0, "count": count}
        return shot_tween_js("#scene-0", 0, shot, 1.0).splitlines()

    def test_heading_subline_and_panel_use_spring(self):
        lines = self._tween_lines("statement", 1)
        for target in ("sh-title", "sh-sub", "sh-panel"):
            line = next(ln for ln in lines if target in ln)
            self.assertIn(self.SPRING, line, target)

    def test_diagram_tiles_and_big_number_use_spring(self):
        for line in self._tween_lines("diagram", 3):
            if "sh-node-" in line and "sh-edge" not in line and "sh-label" not in line:
                self.assertIn(self.SPRING, line)
        line = next(ln for ln in self._tween_lines("data", 1) if "sh-big" in ln)
        self.assertIn(self.SPRING, line)
        line = next(ln for ln in self._tween_lines("statement", 1) if "sh-node-0" in ln)
        self.assertIn(self.SPRING, line)

    def test_tween_durations_unchanged(self):
        lines = self._tween_lines("statement", 1)
        title = next(ln for ln in lines if "sh-title" in ln)
        self.assertIn("duration: 0.5", title)
        big = self._tween_lines("data", 1)
        self.assertIn("duration: 0.6", next(ln for ln in big if "sh-big" in ln))

    def test_panel_has_glow_ring_driven_by_bn_glow_class(self):
        panel = _panel_html()
        self.assertIn('class="sh-panel"', panel)
        self.assertIn('class="bn-glow"', panel)
        self.assertIn(f"border:2px solid {ACCENT}", panel)

    def test_spring_ease_constant_matches_index_helper(self):
        self.assertEqual(SPRING_EASE_JS, "function(p){return bnSpring(p);}")


if __name__ == "__main__":
    unittest.main()
