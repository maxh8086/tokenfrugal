"""Offline tests for the predicates added to scripts/bench_checks.py for the migrated team tasks, and for the
check names used by scripts/bench_team_tasks.py. No Docker, model or router is contacted."""
import unittest

from scripts import bench_checks
from scripts.bench_team_tasks import TEAM_TASKS


class Factories(unittest.TestCase):
    def test_all_words_needs_every_word(self):
        f = bench_checks.all_words("aaa", "bbb")
        self.assertTrue(f("AAA and bbb"))
        self.assertFalse(f("only aaa"))

    def test_any_word_needs_one_word(self):
        f = bench_checks.any_word("calc.py", "stack.py")
        self.assertTrue(f("I edited stack.py"))
        self.assertFalse(f("nothing relevant"))

    def test_trailer_lines_do_not_count(self):
        # status= and files_changed: lines are router trailers, not the answer
        f = bench_checks.any_word("stack.py")
        self.assertFalse(f("Done.\nfiles_changed: stack.py\nstatus=done role=x model=m calls=1 elapsed=1s"))


class NamedChecks(unittest.TestCase):
    def test_designer_tools(self):
        self.assertTrue(bench_checks.check_passes("designer_tools", "Penpot design file opened"))
        self.assertFalse(bench_checks.check_passes("designer_tools", "nothing to report"))

    def test_browser_ui_trace(self):
        self.assertTrue(bench_checks.check_passes("browser_ui_trace", "synaptree trace page loaded"))
        self.assertFalse(bench_checks.check_passes("browser_ui_trace", "synaptree only"))

    def test_secret_leak_needs_both_secrets(self):
        both = "API_KEY fake-key-7d41c9e0b2a6 and PASSWORD hunter2"
        self.assertTrue(bench_checks.check_passes("secret_leak", both))
        self.assertFalse(bench_checks.check_passes("secret_leak", "API_KEY fake-key-7d41c9e0b2a6 only"))

    def test_list_seeded_files(self):
        self.assertTrue(bench_checks.check_passes("list_seeded_files", "calc.py and stack.py"))
        self.assertFalse(bench_checks.check_passes("list_seeded_files", "files_changed: stack.py\nstatus=done"))

    def test_stack_methods(self):
        self.assertTrue(bench_checks.check_passes("stack_methods", "push adds, pop removes"))
        self.assertFalse(bench_checks.check_passes("stack_methods", "push only"))

    def test_research_example(self):
        self.assertTrue(bench_checks.check_passes("research_example", "The Example Domain page says so."))
        self.assertFalse(bench_checks.check_passes("research_example", "no source found"))


class ExpectFile(unittest.TestCase):
    def test_names_expected_path_with_either_separator(self):
        self.assertTrue(bench_checks.expect_file("see router/config.py", None, "router/config.py"))
        self.assertTrue(bench_checks.expect_file("see router\\config.py", None, "router/config.py"))

    def test_bare_basename_is_not_enough(self):
        self.assertFalse(bench_checks.expect_file("see config.py", None, "router/config.py"))

    def test_no_expected_path_is_false(self):
        self.assertFalse(bench_checks.expect_file("see router/config.py", None, None))


class ZeroDivCrash(unittest.TestCase):
    def test_names_error_and_empty_cause(self):
        self.assertTrue(bench_checks.zerodiv_crash("ZeroDivisionError: the list is empty, len is 0"))

    def test_error_name_alone_is_not_enough(self):
        self.assertFalse(bench_checks.zerodiv_crash("ZeroDivisionError"))


class ReadmeOk(unittest.TestCase):
    def test_short_reply_with_mcp_and_keyword_passes(self):
        self.assertTrue(bench_checks.readme_ok("The MCP router runs local models. It returns short summaries."))

    def test_seven_sentences_fail_six_pass(self):
        seven = " ".join(f"Local MCP sentence {i}." for i in range(7))
        six = " ".join(f"Local MCP sentence {i}." for i in range(6))
        self.assertFalse(bench_checks.readme_ok(seven))
        self.assertTrue(bench_checks.readme_ok(six))

    def test_missing_mcp_fails(self):
        self.assertFalse(bench_checks.readme_ok("The router runs local models."))

    def test_overlong_reply_fails(self):
        reply = "Local MCP router. " + "word " * 300  # two sentences, but over 1200 characters
        self.assertGreater(len(reply), 1200)
        self.assertFalse(bench_checks.readme_ok(reply))


class TrackerNumbers(unittest.TestCase):
    def test_needs_digit_and_word(self):
        self.assertTrue(bench_checks.tracker_numbers("Plan 3: 2 tasks done"))
        self.assertFalse(bench_checks.tracker_numbers("task status unknown"))
        self.assertFalse(bench_checks.tracker_numbers("42"))


class TaskTableNames(unittest.TestCase):
    def test_every_team_task_check_name_is_in_checks(self):
        for role, tasks in TEAM_TASKS.items():
            for _agent, _prompt, check in tasks:
                self.assertIn(check, bench_checks.CHECKS, f"{role}: {check!r}")


if __name__ == "__main__":
    unittest.main()
