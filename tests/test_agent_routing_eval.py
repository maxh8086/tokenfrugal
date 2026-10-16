import contextlib
import io
import json
import os
import tempfile
import unittest

from scripts import agent_routing_eval as pre

AGENTS_YAML = """\
agent_models:
  engineering-backend-architect: builder
  design-ui-designer: builder
overrides:
  testing-api-tester: builder
agent_skills:
  product-manager: planning
divisions:
  engineering: [engineering-backend-architect]
"""


def write_tmp(content, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def write_jsonl(rows, blank_lines=False):
    lines = [json.dumps(r) for r in rows]
    if blank_lines:
        lines.insert(1, "")
        lines.append("   ")
    return write_tmp("\n".join(lines) + "\n", ".jsonl")


class LoadAgentSlugsTests(unittest.TestCase):
    def test_union_of_slug_sections_sorted_and_excludes_divisions(self):
        path = write_tmp(AGENTS_YAML, ".yaml")
        self.addCleanup(os.remove, path)
        slugs = pre.load_agent_slugs(path)
        self.assertEqual(slugs, sorted(slugs))
        self.assertEqual(
            slugs,
            ["design-ui-designer", "engineering-backend-architect", "product-manager", "testing-api-tester"],
        )
        self.assertNotIn("engineering", slugs)

    def test_missing_sections_yield_empty_list(self):
        path = write_tmp("roles: {}\n", ".yaml")
        self.addCleanup(os.remove, path)
        self.assertEqual(pre.load_agent_slugs(path), [])


class KeywordRouteTests(unittest.TestCase):
    slugs = ["design-ui-designer", "engineering-backend-architect", "testing-api-tester"]

    def test_picks_slug_with_most_matching_parts(self):
        self.assertEqual(
            pre.keyword_route("Design the backend architect for the API", self.slugs),
            "engineering-backend-architect",
        )

    def test_ignores_parts_shorter_than_four_chars(self):
        # "ui" is 2 chars and "api" is 3 chars, so neither counts.
        self.assertIsNone(pre.keyword_route("ui api", self.slugs))

    def test_tie_broken_alphabetically(self):
        slugs = ["zeta-tester", "alpha-tester"]
        self.assertEqual(pre.keyword_route("tester please", slugs), "alpha-tester")

    def test_no_match_returns_none(self):
        self.assertIsNone(pre.keyword_route("write a poem", self.slugs))

    def test_empty_slugs_returns_none(self):
        self.assertIsNone(pre.keyword_route("design", []))

    def test_punctuation_and_case_are_normalised(self):
        self.assertEqual(pre.keyword_route("TESTING, api-tester!", self.slugs), "testing-api-tester")


class ValidateLabelsTests(unittest.TestCase):
    def test_reports_index_and_agent_for_unknown_slugs(self):
        rows = [{"persona": "a-b"}, {"persona": "bogus"}, {"persona": "c-d"}]
        self.assertEqual(pre.validate_labels(rows, ["a-b", "c-d"]), [(1, "bogus")])

    def test_all_known_returns_empty(self):
        self.assertEqual(pre.validate_labels([{"persona": "a-b"}], ["a-b"]), [])


class ScorePredictionsTests(unittest.TestCase):
    def test_accuracy_and_per_agent_counts(self):
        result = pre.score_predictions(["a-x", "a-x", "b-y"], ["a-x", "b-y", "b-y"])
        self.assertEqual(result["correct"], 2)
        self.assertEqual(result["total"], 3)
        self.assertAlmostEqual(result["accuracy"], 2 / 3)
        self.assertEqual(result["per_agent"]["a-x"], {"correct": 1, "total": 2})
        self.assertEqual(result["per_agent"]["b-y"], {"correct": 1, "total": 1})

    def test_none_prediction_is_wrong(self):
        result = pre.score_predictions(["a-x"], [None])
        self.assertEqual(result["correct"], 0)
        self.assertEqual(result["per_agent"]["a-x"], {"correct": 0, "total": 1})

    def test_empty_labels_gives_zero_accuracy(self):
        result = pre.score_predictions([], [])
        self.assertEqual(result, {"accuracy": 0.0, "correct": 0, "total": 0, "per_agent": {}})


class LoadJsonlTests(unittest.TestCase):
    def test_skips_blank_lines(self):
        path = write_jsonl([{"task": "t1", "persona": "a-b"}, {"task": "t2", "persona": "c-d"}], blank_lines=True)
        self.addCleanup(os.remove, path)
        self.assertEqual(
            pre.load_jsonl(path),
            [{"task": "t1", "persona": "a-b"}, {"task": "t2", "persona": "c-d"}],
        )


class MainTests(unittest.TestCase):
    def setUp(self):
        self.agents = write_tmp(AGENTS_YAML, ".yaml")
        self.addCleanup(os.remove, self.agents)

    def run_main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pre.main(argv)
        return code, out.getvalue()

    def test_exit_zero_prints_baseline_and_predictions(self):
        labels = write_jsonl([
            {"task": "design the ui designer mockup", "persona": "design-ui-designer"},
            {"task": "write a poem", "persona": "product-manager"},
        ])
        preds = write_jsonl([{"persona": "design-ui-designer"}, {"persona": None}])
        self.addCleanup(os.remove, labels)
        self.addCleanup(os.remove, preds)

        code, out = self.run_main(["--agents", self.agents, "--labels", labels, "--predictions", preds])

        self.assertEqual(code, 0)
        self.assertIn("keyword baseline accuracy: 0.500 (1/2)", out)
        self.assertIn("predictions accuracy: 0.500 (1/2)", out)

    def test_exit_zero_without_predictions(self):
        labels = write_jsonl([{"task": "testing the api tester", "persona": "testing-api-tester"}])
        self.addCleanup(os.remove, labels)

        code, out = self.run_main(["--agents", self.agents, "--labels", labels])

        self.assertEqual(code, 0)
        self.assertIn("keyword baseline accuracy: 1.000 (1/1)", out)
        self.assertNotIn("predictions accuracy", out)

    def test_exit_two_on_unknown_agent(self):
        labels = write_jsonl([
            {"task": "x", "persona": "product-manager"},
            {"task": "y", "persona": "not-an-agent"},
        ])
        self.addCleanup(os.remove, labels)

        code, out = self.run_main(["--agents", self.agents, "--labels", labels])

        self.assertEqual(code, 2)
        self.assertIn("bad row 1", out)
        self.assertIn("not-an-agent", out)
        self.assertNotIn("keyword baseline", out)


if __name__ == "__main__":
    unittest.main()
