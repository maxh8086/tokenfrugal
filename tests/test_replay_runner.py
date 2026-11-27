"""Step 8f replay runner tests (parts A and B1): helpers only. No model, no Docker, no network, no real .env.

Every test uses temporary folders. The git tests build a temporary repository with a local identity.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from scripts import replay

ORIGINAL_RUN = subprocess.run


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)
    return done.stdout.decode("utf-8", "replace").strip()


class TempTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def make_repo(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "Replay Test")
        git(repo, "config", "user.email", "replay@example.invalid")
        (repo / "a.txt").write_text("one\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        return repo, git(repo, "rev-parse", "HEAD")

    def events(self, *lines):
        path = self.tmp / "events.jsonl"
        path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
        return path


class ArgumentParsingTest(unittest.TestCase):
    def test_all_options_parse(self):
        args = replay.parse_args(["--arm", "s2", "--router", "C:/r", "--repo", "tokenfrugal=C:/t",
                                  "--venv", "tokenfrugal=C:/v", "--env", "TOKENFRUGAL_THINK=low", "--env", "A=b=c",
                                  "--runs", "3", "--rerun-against", "base"])
        self.assertEqual(args.arm, "s2")
        self.assertEqual(args.router, "C:/r")
        self.assertEqual(args.repo, {"tokenfrugal": "C:/t"})
        self.assertEqual(args.venv, {"tokenfrugal": "C:/v"})
        self.assertEqual(args.env, {"TOKENFRUGAL_THINK": "low", "A": "b=c"})
        self.assertEqual(args.runs, 3)
        self.assertEqual(args.rerun_against, "base")
        self.assertFalse(args.check_corpus)

    def test_defaults_and_check_corpus(self):
        args = replay.parse_args(["--check-corpus"])
        self.assertTrue(args.check_corpus)
        self.assertEqual(args.runs, 1)
        self.assertEqual(args.repo, {})
        self.assertEqual(args.env, {})

    def test_run_needs_arm_and_router(self):
        with self.assertRaises(SystemExit):
            replay.parse_args(["--router", "C:/r"])
        with self.assertRaises(SystemExit):
            replay.parse_args(["--arm", "s2"])

    def test_pair_without_equals_is_refused(self):
        with self.assertRaises(SystemExit):
            replay.parse_args(["--arm", "s2", "--router", "C:/r", "--repo", "tokenfrugal"])


class RunEnvironmentTest(TempTest):
    def test_isolation_and_venv_first_on_path(self):
        gateway, ws, venv = self.tmp / "gw", self.tmp / "ws", self.tmp / "venv"
        base = {"PATH": "/usr/bin", "CC_WORKSPACE": "/old", "GATEWAY_DB": "/old/tasks.db", "GATEWAY_EVENTS": "/old/e.jsonl"}
        env = replay.run_env(base, gateway_dir=gateway, workspace=ws, venv=venv, extra={"TOKENFRUGAL_THINK": "low"})
        self.assertEqual(Path(env["GATEWAY_DB"]), gateway / "tasks.db")
        self.assertEqual(Path(env["GATEWAY_EVENTS"]), gateway / "events.jsonl")
        self.assertEqual(Path(env["CC_WORKSPACE"]), ws)
        self.assertEqual(Path(env["TOKENFRUGAL_HOST_ACCEPT_PATHS"]), ws)
        self.assertEqual(Path(env["TOKENFRUGAL_ACCEPT_VENV"]), venv)
        self.assertEqual(env["TOKENFRUGAL_THINK"], "low")
        first = env["PATH"].split(os.pathsep)[0]
        expected = venv / ("Scripts" if os.name == "nt" else "bin")
        self.assertEqual(os.path.realpath(first), os.path.realpath(expected))
        self.assertIn("/usr/bin", env["PATH"].split(os.pathsep))

    def test_path_key_is_not_duplicated(self):
        env = replay.run_env({"Path": "C:/Windows"}, gateway_dir=self.tmp / "gw", workspace=self.tmp / "ws", venv=self.tmp / "v")
        keys = [k for k in env if k.upper() == "PATH"]
        self.assertEqual(len(keys), 1)
        self.assertIn("C:/Windows", env[keys[0]])

    def test_venv_bin_dir_follows_platform(self):
        self.assertEqual(replay.venv_bin_dir(Path("v"), "nt"), Path("v") / "Scripts")
        self.assertEqual(replay.venv_bin_dir(Path("v"), "posix"), Path("v") / "bin")
        self.assertEqual(replay.venv_python(Path("v"), "nt"), Path("v") / "Scripts" / "python.exe")


class SettingsCopyTest(TempTest):
    def test_copies_env_and_router_json_only(self):
        src, dst = self.tmp / "main", self.tmp / "worktree"
        (src / "router").mkdir(parents=True)
        (src / ".env").write_text("K=v\n", encoding="utf-8")
        (src / "router" / "config_overrides.json").write_text("{}", encoding="utf-8")
        (src / "router" / "notes.txt").write_text("skip", encoding="utf-8")
        (dst / "router").mkdir(parents=True)
        replay.copy_settings(src, dst)
        self.assertEqual((dst / ".env").read_text(encoding="utf-8"), "K=v\n")
        self.assertTrue((dst / "router" / "config_overrides.json").is_file())
        self.assertFalse((dst / "router" / "notes.txt").exists())

    def test_same_checkout_is_left_alone(self):
        src = self.tmp / "main"
        (src / "router").mkdir(parents=True)
        (src / ".env").write_text("K=v\n", encoding="utf-8")
        self.assertEqual(replay.copy_settings(src, src), [])

    def test_router_checkout_kind(self):
        (self.tmp / "router").mkdir()
        self.assertEqual(replay.child_mode(self.tmp), "legacy")
        (self.tmp / "router" / "packet.py").write_text("", encoding="utf-8")
        self.assertEqual(replay.child_mode(self.tmp), "packet")


class ScopeTest(TempTest):
    def test_glob_matches(self):
        self.assertTrue(replay.glob_matches("a/b/c.py", "a/**"))
        self.assertTrue(replay.glob_matches("a/b.py", "a/*.py"))
        self.assertFalse(replay.glob_matches("a/b/c.py", "a/*.py"))

    def test_path_key_normalises_like_checker(self):
        self.assertEqual(replay._path_key("a\\B\\c.py"), "a/B/c.py" if os.name != "nt" and sys.platform != "darwin" else "a/b/c.py")

    def test_glob_case_follows_checker_platform_rule(self):
        folded = os.name == "nt" or sys.platform == "darwin"
        self.assertEqual(replay.glob_matches("Secret/X.py", "secret/*.py"), folded)
        self.assertTrue(replay.glob_matches("secret\\x.py", "secret/*.py"))

    def test_new_untracked_file_in_must_not_change_fails_scope(self):
        repo, base = self.make_repo()
        (repo / "secret").mkdir()
        (repo / "secret" / "x.py").write_text("x = 1\n", encoding="utf-8")
        self.assertFalse(replay.scope_ok(repo, base, ["secret/*.py"]))

    def test_new_untracked_file_fails_scope_even_when_check_passes(self):
        repo, base = self.make_repo()
        (repo / "secret").mkdir()
        (repo / "secret" / "x.py").write_text("x = 1\n", encoding="utf-8")
        scope, check_ok = replay.grade_run(repo, base, ["secret/*.py"], lambda: True)
        self.assertFalse(scope)
        self.assertTrue(check_ok)
        self.assertEqual(replay.grade(CHILD, 1, check_ok, scope), "fail")

    def test_file_outside_must_not_change_passes_scope(self):
        repo, base = self.make_repo()
        (repo / "docs").mkdir()
        (repo / "docs" / "notes.md").write_text("n\n", encoding="utf-8")
        self.assertTrue(replay.scope_ok(repo, base, ["secret/**"]))

    def test_file_written_by_check_is_not_counted(self):
        repo, base = self.make_repo()

        def check():
            (repo / "out").mkdir(exist_ok=True)
            (repo / "out" / "a.txt").write_text("grader output\n", encoding="utf-8")
            return True

        scope, check_ok = replay.grade_run(repo, base, ["out/*.txt"], check)
        self.assertTrue(scope)
        self.assertTrue(check_ok)

    def test_worktree_round_trip(self):
        repo, base = self.make_repo()
        dest = self.tmp / "ws"
        replay.make_worktree(repo, base, dest)
        self.assertEqual((dest / "a.txt").read_text(encoding="utf-8"), "one\n")
        replay.remove_worktree(repo, dest)
        self.assertFalse(dest.exists())


class ChildOutputTest(TempTest):
    def test_rowless_busy_refusal_does_not_read_the_store(self):
        def no_store(tid):
            raise AssertionError("store.get must not be called without a row")

        out = replay.finish_child(None, "workspace_busy: edit task 7 is running in this workspace; retry later",
                                  no_store, self.tmp / "missing.jsonl")
        self.assertIsNone(out["tid"])
        self.assertIsNone(out["status"])
        self.assertIsNone(out["outcome"])
        self.assertEqual(out["error_kind"], "workspace_busy")
        self.assertIsNone(out["saved"])
        self.assertEqual(replay.grade(out, None, False, False), "infra")

    def test_other_rowless_refusal_is_fail(self):
        out = replay.finish_child(None, "refused: accept is not on the list", lambda t: None, self.tmp / "x.jsonl")
        self.assertEqual(out["error_kind"], "refused")
        self.assertEqual(replay.grade(out, None, True, True), "fail")

    def test_row_fields_and_saved_from_last_task_event(self):
        events = self.events({"kind": "task_done", "saved": 5}, {"kind": "step", "saved": 100},
                             {"kind": "task_failed", "saved": 9}, {"kind": "step", "saved": 200})
        row = {"status": "done", "outcome": "satisfied", "error_kind": None, "model_tag": "m", "peak_ctx": 1234}
        out = replay.finish_child("t1", "reply", lambda tid: row if tid == "t1" else None, events)
        self.assertEqual(out["tid"], "t1")
        self.assertEqual(out["status"], "done")
        self.assertEqual(out["outcome"], "satisfied")
        self.assertEqual(out["saved"], 9)
        self.assertEqual(replay.grade(out, 3, True, True), "pass")

    def test_parent_reads_the_marked_line_only(self):
        stdout = "router noise\n" + replay.RESULT_PREFIX + json.dumps({"tid": None}) + "\nmore noise\n"
        self.assertEqual(replay.parse_child(stdout), {"tid": None})
        self.assertIsNone(replay.parse_child("no marker here\n"))


class StepCountTest(TempTest):
    def test_largest_step_of_the_task(self):
        path = self.events({"kind": "step", "id": "t1", "n": 2}, {"kind": "step", "id": "t1", "n": 5},
                           {"kind": "step", "id": "t2", "n": 9}, {"kind": "task_done", "id": "t1"})
        self.assertEqual(replay.count_steps(path, "t1"), 5)

    def test_null_without_steps_or_task_or_file(self):
        path = self.events({"kind": "step", "id": "t2", "n": 9})
        self.assertIsNone(replay.count_steps(path, "t1"))
        self.assertIsNone(replay.count_steps(path, None))
        self.assertIsNone(replay.count_steps(self.tmp / "missing.jsonl", "t1"))


CHILD = {"tid": "t1", "reply": "r", "status": "done", "outcome": "done", "error_kind": None,
         "saved": 7, "model_tag": "m", "peak_ctx": 10}


class GradeTest(unittest.TestCase):
    def test_done_or_satisfied_with_checks_and_scope_passes(self):
        self.assertEqual(replay.grade(CHILD, 1, True, True), "pass")
        self.assertEqual(replay.grade(dict(CHILD, outcome="satisfied"), 1, True, True), "pass")

    def test_status_is_used_when_outcome_is_null(self):
        self.assertEqual(replay.grade(dict(CHILD, outcome=None, status="done"), 1, True, True), "pass")
        self.assertEqual(replay.grade(dict(CHILD, outcome=None, status="failed"), 1, True, True), "fail")

    def test_failed_outcome_or_missed_check_or_scope_fails(self):
        self.assertEqual(replay.grade(dict(CHILD, outcome="failed"), 1, True, True), "fail")
        self.assertEqual(replay.grade(CHILD, 1, False, True), "fail")
        self.assertEqual(replay.grade(CHILD, 1, True, False), "fail")

    def test_busy_and_gpu_and_infra_kinds_are_infra(self):
        for kind in ("workspace_busy", "gpu_busy", "infra"):
            self.assertEqual(replay.grade(dict(CHILD, error_kind=kind, outcome=None, status=None), 4, True, True), "infra", kind)

    def test_crash_before_any_step_is_infra_and_after_a_step_is_fail(self):
        crashed = dict(CHILD, tid=None, error_kind="crashed", outcome=None, status=None)
        self.assertEqual(replay.grade(crashed, None, False, False), "infra")
        self.assertEqual(replay.grade(crashed, 3, False, False), "fail")

    def test_timeout_is_fail_not_infra(self):
        timed_out = dict(CHILD, tid=None, error_kind="timeout", outcome=None, status=None)
        self.assertEqual(replay.grade(timed_out, None, False, False), "fail")


class RecordTest(unittest.TestCase):
    def test_record_has_status_result_steps_and_stop(self):
        rec = replay.build_record("fb-001", "s2", 1, CHILD, steps=4, check_ok=True, scope_ok=True, secs=1.5)
        self.assertEqual(rec["id"], "fb-001")
        self.assertEqual(rec["status"], "done")
        self.assertEqual(rec["result"], "pass")
        self.assertEqual(rec["steps"], 4)
        self.assertIsNone(rec["stop"])
        self.assertEqual(rec["est_saved_tokens"], 7)


class InfraRerunTest(unittest.TestCase):
    def test_infra_is_rerun_once_and_both_are_kept(self):
        results = iter([{"result": "infra"}, {"result": "pass"}])
        records = replay.run_with_infra_rerun(lambda attempt: next(results))
        self.assertEqual([r["attempt"] for r in records], [1, 2])
        self.assertEqual([r["result"] for r in records], ["infra", "pass"])

    def test_non_infra_is_not_rerun(self):
        calls = []
        records = replay.run_with_infra_rerun(lambda attempt: calls.append(attempt) or {"result": "fail"})
        self.assertEqual(calls, [1])
        self.assertEqual(len(records), 1)

    def test_second_infra_stops_without_a_third_run(self):
        calls = []
        records = replay.run_with_infra_rerun(lambda attempt: calls.append(attempt) or {"result": "infra"})
        self.assertEqual(calls, [1, 2])
        self.assertEqual(len(records), 2)


class ChildTimeoutTest(TempTest):
    def test_timed_out_child_is_recorded_and_worktree_removed(self):
        repo, base = self.make_repo()
        router = self.tmp / "router-checkout"
        router.mkdir()
        venv = self.tmp / "venv"
        task = {"id": "fb-001", "folder": self.tmp, "meta": {"base_commit": base, "agent": "a", "repo": "r"},
                "packet": {"goal": "g", "kind": "edit", "files": [{"path": "a.txt"}], "must_not_change": []}}
        real_python = replay.venv_python(venv)

        def fake_run(argv, *args, **kwargs):
            if argv[0] == sys.executable:
                raise subprocess.TimeoutExpired(argv, 1)
            if argv[0] == str(real_python):
                return subprocess.CompletedProcess(argv, 0, "", "")
            return ORIGINAL_RUN(argv, *args, **kwargs)

        with mock.patch.object(replay.subprocess, "run", side_effect=fake_run):
            record = replay.run_once(task, "s2", router, repo, venv, {}, 1)
        self.assertEqual(record["stop"], "timeout")
        self.assertEqual(record["result"], "fail")
        self.assertEqual(record["id"], "fb-001")
        worktrees = git(repo, "worktree", "list", "--porcelain").splitlines()
        self.assertEqual(len([x for x in worktrees if x.startswith("worktree ")]), 1)


class WrongRouterTest(TempTest):
    def test_child_refuses_a_router_outside_its_checkout(self):
        checkout = self.tmp / "checkout"
        checkout.mkdir()
        other = self.tmp / "other"
        (other / "router").mkdir(parents=True)
        for name in ("__init__.py", "config.py", "server.py", "store.py", "packet.py"):
            (other / "router" / name).write_text("", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(other)
        env["GATEWAY_EVENTS"] = str(self.tmp / "events.jsonl")
        payload = {"router": str(checkout), "mode": "legacy", "agent": "a", "prompt": "p"}
        proc = subprocess.run([sys.executable, replay.__file__, replay.LOCAL_CHILD_FLAG], input=json.dumps(payload),
                              text=True, capture_output=True, cwd=str(checkout), env=env, timeout=120)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not under", proc.stderr)
        self.assertNotIn(replay.RESULT_PREFIX, proc.stdout)

    def test_router_under_checkout_uses_path_boundary(self):
        root = self.tmp / "tf"
        self.assertTrue(replay.router_under(root / "router" / "__init__.py", root))
        self.assertFalse(replay.router_under(self.tmp / "tf2" / "router" / "__init__.py", root))
        self.assertFalse(replay.router_under(self.tmp / "elsewhere" / "__init__.py", root))


class PromptAndRecordTest(TempTest):
    def test_base_arm_prompt_keeps_star_argv_and_has_no_backticks(self):
        argv = ["python", "-m", "unittest", "tests/test_*.py"]
        packet = {"goal": "Fix it", "kind": "edit", "files": [{"path": "router/x.py"}], "accept": argv}
        prompt = replay.plain_prompt(packet)
        self.assertNotIn("`", prompt)
        accept_line = [line for line in prompt.splitlines() if line.startswith("Accept: ")][0]
        self.assertEqual(accept_line[len("Accept: "):].split(), argv)
        self.assertEqual(" ".join(argv).split(), argv)

    def test_one_json_line_per_run_in_dated_results_file(self):
        path = replay.append_record(self.tmp, "s2", {"id": "fb-001", "run": 1}, date(2026, 11, 27))
        self.assertEqual(path, self.tmp / "Benchmark" / "replay" / "results" / "s2-20261127.jsonl")
        replay.append_record(self.tmp, "s2", {"id": "fb-002", "run": 1}, date(2026, 11, 27))
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x)["id"] for x in lines], ["fb-001", "fb-002"])


PACKET_BODY = {"v": 1, "goal": "Fix the thing", "kind": "edit", "files": [{"path": "a.txt"}]}


def write_task(root, task_id, *, toml=None, packet=None, check=True):
    folder = root / "Benchmark" / "replay" / task_id
    folder.mkdir(parents=True)
    text = toml if toml is not None else 'repo = "r"\nbase_commit = "abc123"\nagent = "coding-l2"\n'
    (folder / "task.toml").write_text(text, encoding="utf-8")
    (folder / "packet.json").write_text(json.dumps(packet if packet is not None else PACKET_BODY), encoding="utf-8")
    if check:
        (folder / "check.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    return folder


def write_results(root, name, lines):
    path = root / "Benchmark" / "replay" / "results" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    return path


def quiet_main(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = replay.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CorpusTest(TempTest):
    def use_corpus(self):
        corpus = self.tmp / "corpus"
        corpus.mkdir()
        patcher = mock.patch.object(replay, "ROOT", corpus)
        patcher.start()
        self.addCleanup(patcher.stop)
        return corpus


class CorpusCheckTest(CorpusTest):
    def setUp(self):
        super().setUp()
        self.corpus = self.use_corpus()
        self.repo = self.tmp / "repo"
        (self.repo / ".venv").mkdir(parents=True)

    def corpus_check(self):
        return replay.corpus_check(self.corpus, {"r": str(self.repo)}, {})

    def test_clean_corpus_has_no_problems_and_skips_results(self):
        write_task(self.corpus, "fb-001")
        write_results(self.corpus, "s2-20261126.jsonl", [])
        self.assertEqual(self.corpus_check(), (1, []))

    def test_missing_check_file_is_a_problem(self):
        write_task(self.corpus, "fb-002", check=False)
        count, problems = self.corpus_check()
        self.assertEqual(count, 1)
        self.assertTrue(any("fb-002" in p and "check.py" in p for p in problems), problems)

    def test_task_toml_without_agent_is_a_problem(self):
        write_task(self.corpus, "fb-002", toml='repo = "r"\nbase_commit = "abc123"\n')
        _, problems = self.corpus_check()
        self.assertTrue(any("agent" in p for p in problems), problems)

    def test_packet_with_an_unknown_key_is_a_problem(self):
        write_task(self.corpus, "fb-002", packet=dict(PACKET_BODY, extra=1))
        _, problems = self.corpus_check()
        self.assertTrue(any("packet.json" in p for p in problems), problems)

    def test_accept_that_does_not_round_trip_is_a_problem(self):
        write_task(self.corpus, "fb-002", packet=dict(PACKET_BODY, accept=["python", "a b"]))
        _, problems = self.corpus_check()
        self.assertTrue(any("accept" in p for p in problems), problems)

    def test_star_argv_round_trips(self):
        write_task(self.corpus, "fb-001", packet=dict(PACKET_BODY, accept=["python", "-m", "unittest", "tests/test_*.py"]))
        self.assertEqual(self.corpus_check(), (1, []))

    def test_missing_venv_folder_is_a_problem(self):
        write_task(self.corpus, "fb-001")
        _, problems = replay.corpus_check(self.corpus, {"r": str(self.tmp / "norepo")}, {})
        self.assertTrue(any("venv" in p for p in problems), problems)

    def test_venv_flag_must_name_an_existing_folder(self):
        write_task(self.corpus, "fb-001")
        _, problems = replay.corpus_check(self.corpus, {}, {"r": str(self.tmp / "nov")})
        self.assertTrue(problems)

    def test_main_prints_problems_and_count_and_sets_exit_code(self):
        write_task(self.corpus, "fb-001")
        code, out, _ = quiet_main("--check-corpus", "--repo", f"r={self.repo}")
        self.assertEqual(code, 0)
        self.assertIn("tasks: 1", out)
        write_task(self.corpus, "fb-002", check=False)
        code, out, _ = quiet_main("--check-corpus", "--repo", f"r={self.repo}")
        self.assertEqual(code, 1)
        self.assertIn("fb-002", out)
        self.assertIn("tasks: 2", out)

    def test_check_corpus_starts_no_run(self):
        write_task(self.corpus, "fb-001")
        with mock.patch.object(replay, "run_once") as run_once:
            code, _, _ = quiet_main("--check-corpus", "--repo", f"r={self.repo}")
        self.assertEqual(code, 0)
        run_once.assert_not_called()

    def test_main_missing_venv_folder_exits_1(self):
        write_task(self.corpus, "fb-001")
        code, out, _ = quiet_main("--check-corpus", "--repo", f"r={self.tmp / 'norepo'}")
        self.assertEqual(code, 1)
        self.assertIn("venv r", out)
        self.assertIn("tasks: 1", out)


class RerunHelpersTest(CorpusTest):
    def setUp(self):
        super().setUp()
        self.corpus = self.use_corpus()

    def test_newest_base_file_by_date_and_exact_arm_name(self):
        write_results(self.corpus, "base-20261120.jsonl", [])
        newest = write_results(self.corpus, "base-20261126.jsonl", [])
        write_results(self.corpus, "base2-20261130.jsonl", [])
        self.assertEqual(replay.base_results_file(self.corpus, "base"), newest)
        self.assertIsNone(replay.base_results_file(self.corpus, "nobase"))

    def test_base_results_skip_infra_and_keep_the_last_result(self):
        path = write_results(self.corpus, "base-20261126.jsonl", [
            {"id": "fb-001", "result": "pass"}, {"id": "fb-001", "result": "infra"}, {"id": "fb-002", "result": "fail"}])
        self.assertEqual(replay.base_results(path), {"fb-001": "pass", "fb-002": "fail"})

    def test_rerun_ids_only_for_present_tasks_that_differ(self):
        base = {"fb-001": "pass", "fb-002": "fail"}
        records = [{"id": "fb-001", "result": "fail"}, {"id": "fb-002", "result": "fail"},
                   {"id": "fb-003", "result": "pass"}, {"id": "fb-004", "result": "infra"}]
        self.assertEqual(replay.rerun_ids(records, base), ["fb-001"])

    def test_rerun_ids_compare_the_last_non_infra_result(self):
        records = [{"id": "fb-001", "result": "pass"}, {"id": "fb-001", "result": "infra"}]
        self.assertEqual(replay.rerun_ids(records, {"fb-001": "fail"}), ["fb-001"])
        self.assertEqual(replay.rerun_ids(records, {"fb-001": "pass"}), [])


class RerunAgainstTest(CorpusTest):
    def setUp(self):
        super().setUp()
        self.corpus = self.use_corpus()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        write_task(self.corpus, "fb-001")

    def run_against_base(self, result):
        write_results(self.corpus, "base-20261126.jsonl", [{"id": "fb-001", "result": "pass"}])
        runs = []

        def fake(task, arm, router, repo, venv, extra_env, run_no):
            runs.append(run_no)
            return {"id": task["id"], "arm": arm, "run": run_no, "result": result}

        with mock.patch.object(replay, "run_once", side_effect=fake):
            code, _, _ = quiet_main("--arm", "s2", "--router", str(self.tmp / "router"),
                                    "--repo", f"r={self.repo}", "--rerun-against", "base")
        return code, runs

    def test_differing_task_gets_two_more_runs_numbered_2_and_3(self):
        code, runs = self.run_against_base("fail")
        self.assertEqual(code, 0)
        self.assertEqual(runs, [1, 2, 3])

    def test_matching_task_is_not_rerun(self):
        code, runs = self.run_against_base("pass")
        self.assertEqual(code, 0)
        self.assertEqual(runs, [1])

    def test_missing_base_file_stops_before_any_run(self):
        with mock.patch.object(replay, "run_once") as run_once:
            code, _, err = quiet_main("--arm", "s2", "--router", str(self.tmp / "router"),
                                      "--repo", f"r={self.repo}", "--rerun-against", "nobase")
        self.assertNotEqual(code, 0)
        self.assertIn("nobase", err)
        run_once.assert_not_called()


class WrongRouterFatalTest(CorpusTest):
    def task_for(self, repo, base):
        return {"id": "fb-001", "folder": self.tmp, "meta": {"base_commit": base, "agent": "a", "repo": "r"},
                "packet": {"goal": "g", "kind": "edit", "files": [{"path": "a.txt"}], "must_not_change": []}}

    def test_child_exit_3_raises_setup_fault_and_removes_the_worktree(self):
        repo, base = self.make_repo()
        router, venv = self.tmp / "router-checkout", self.tmp / "venv"
        router.mkdir()

        def fake_run(argv, *args, **kwargs):
            if argv[0] == sys.executable:
                return subprocess.CompletedProcess(argv, replay.WRONG_ROUTER_EXIT, "", "not under the checkout")
            return ORIGINAL_RUN(argv, *args, **kwargs)

        with mock.patch.object(replay.subprocess, "run", side_effect=fake_run):
            with self.assertRaises(replay.SetupFault):
                replay.run_once(self.task_for(repo, base), "s2", router, repo, venv, {}, 1)
        worktrees = git(repo, "worktree", "list", "--porcelain").splitlines()
        self.assertEqual(len([x for x in worktrees if x.startswith("worktree ")]), 1)

    def test_main_stops_at_once_and_writes_no_record(self):
        corpus = self.use_corpus()
        write_task(corpus, "fb-001")
        write_task(corpus, "fb-002")
        with mock.patch.object(replay, "run_once", side_effect=replay.SetupFault("wrong router")) as run_once:
            code, _, err = quiet_main("--arm", "s2", "--router", str(self.tmp / "router"), "--repo", f"r={self.tmp}")
        self.assertNotEqual(code, 0)
        self.assertIn("wrong router", err)
        self.assertEqual(run_once.call_count, 1)
        self.assertFalse((corpus / "Benchmark" / "replay" / "results").exists())


class CheckTimeoutTest(TempTest):
    def test_check_timeout_is_a_failed_check_and_the_runner_goes_on(self):
        repo, base = self.make_repo()
        router, venv = self.tmp / "router-checkout", self.tmp / "venv"
        router.mkdir()
        folder = self.tmp / "task"
        folder.mkdir()
        task = {"id": "fb-001", "folder": folder, "meta": {"base_commit": base, "agent": "a", "repo": "r"},
                "packet": {"goal": "g", "kind": "edit", "files": [{"path": "a.txt"}], "must_not_change": []}}
        child = {"tid": "t1", "reply": "done", "status": "done", "outcome": "done", "error_kind": None,
                 "saved": 1, "model_tag": "m", "peak_ctx": 1}
        real_python = replay.venv_python(venv)
        seen = {}

        def fake_run(argv, *args, **kwargs):
            if argv[0] == sys.executable:
                return subprocess.CompletedProcess(argv, 0, replay.RESULT_PREFIX + json.dumps(child) + "\n", "")
            if argv[0] == str(real_python):
                seen["timeout"] = kwargs.get("timeout")
                raise subprocess.TimeoutExpired(argv, kwargs.get("timeout"))
            return ORIGINAL_RUN(argv, *args, **kwargs)

        with mock.patch.object(replay.subprocess, "run", side_effect=fake_run):
            record = replay.run_once(task, "s2", router, repo, venv, {}, 1)
        self.assertEqual(replay.CHECK_TIMEOUT, 600)
        self.assertEqual(seen["timeout"], 600)
        self.assertFalse(record["check_ok"])
        self.assertEqual(record["result"], "fail")
        self.assertIsNone(record["stop"])
        worktrees = git(repo, "worktree", "list", "--porcelain").splitlines()
        self.assertEqual(len([x for x in worktrees if x.startswith("worktree ")]), 1)


if __name__ == "__main__":
    unittest.main()
