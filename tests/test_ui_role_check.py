import tempfile
import unittest
from pathlib import Path

from scripts import ui_role_check as chk
from scripts import ui_role_smoke as smoke


class UiRoleCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "skills" / "role-ui").mkdir(parents=True)
        (self.root / "skills" / "role-ui" / "SKILL.md").write_text("## ui-x\nDo it.\n", encoding="utf-8")
        (self.root / "profiles").mkdir()
        (self.root / "profiles" / "build.yaml").write_text("tools:\n  - read_file\n  - name: run_tests\n", encoding="utf-8")
        self.entry = {"profile": "build", "tools": ["read_file", "run_tests"], "skills": ["role-ui"], "improve": "gated"}

    def tearDown(self):
        self._tmp.cleanup()

    def check(self, entry):
        return chk.check_role("ui-x", entry, skills=self.root / "skills", profiles=self.root / "profiles")

    def test_clean_entry_has_no_errors_or_warnings(self):
        self.assertEqual(self.check(self.entry), ([], []))

    def test_model_key_is_an_error(self):
        errors, _ = self.check({**self.entry, "model": "builder"})
        self.assertTrue(any("model key" in e for e in errors))

    def test_missing_gate_is_an_error(self):
        entry = {k: v for k, v in self.entry.items() if k != "improve"}
        errors, _ = self.check(entry)
        self.assertTrue(any("gated" in e for e in errors))

    def test_missing_skill_section_is_an_error(self):
        errors, _ = self.check({**self.entry, "skills": ["role-missing"]})
        self.assertTrue(any("skill file missing" in e for e in errors))
        (self.root / "skills" / "role-ui" / "SKILL.md").write_text("## other\n", encoding="utf-8")
        errors, _ = self.check(self.entry)
        self.assertTrue(any("no '## ui-x' section" in e for e in errors))

    def test_unknown_tool_is_a_warning(self):
        _, warnings = self.check({**self.entry, "tools": ["read_file", "nope"]})
        self.assertTrue(any("'nope'" in w for w in warnings))

    def test_real_pending_roles_pass_structure_check(self):
        self.assertEqual(chk.main([]), 0)


class UiRoleSmoke(unittest.TestCase):
    def test_plan_only_without_confirm_and_no_model_call(self):
        self.assertEqual(smoke.main(["ui-layout", "--model", "builder"]), 0)

    def test_model_required(self):
        self.assertEqual(smoke.main(["ui-layout"]), 2)

    def test_unknown_role_rejected(self):
        self.assertEqual(smoke.main(["ui-nope", "--model", "builder"]), 2)

    def test_config_for_does_not_write_tf_roles(self):
        before = smoke.Path(smoke.__file__).resolve().parent.parent / "router" / "tf-roles.yaml"
        text = before.read_text(encoding="utf-8")
        cfg = smoke.config_for("ui-layout", "ui-test-layout", "builder")
        self.assertEqual(cfg["roles"]["ui-layout"]["model"], "builder")
        self.assertEqual(before.read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()
