"""Every active role in router/tf-roles.yaml has a complete contract, and contract_errors catches the gaps."""
import copy
import unittest

from router.config import load_tf_roles
from router.preflight import contract_errors

CFG = load_tf_roles()
GOOD = {
    "purpose": "Write one change.",
    "inputs": ["named files", "the change"],
    "output_format": "changed paths, then the Accept line",
    "stop_condition": "Accept exits 0, or 12 steps",
    "checklist": [
        {"text": "Only named files changed.", "kind": "deterministic"},
        {"text": "Accept exits 0.", "kind": "deterministic"},
        {"text": "The change does what was asked.", "kind": "judgement"},
    ],
}


class RealConfigTest(unittest.TestCase):
    def test_every_active_role_has_a_valid_contract(self):
        self.assertEqual(contract_errors(CFG["roles"], CFG["contracts"]), {})


class ContractErrorsTest(unittest.TestCase):
    def check(self, contract):
        return contract_errors({"r": {}}, {"r": contract})

    def test_good_contract_passes(self):
        self.assertEqual(self.check(copy.deepcopy(GOOD)), {})

    def test_missing_contract(self):
        self.assertEqual(contract_errors({"r": {}}, {}), {"r": ["no contract"]})

    def test_missing_field(self):
        c = copy.deepcopy(GOOD)
        del c["stop_condition"]
        self.assertEqual(self.check(c), {"r": ["missing stop_condition"]})

    def test_short_checklist(self):
        c = copy.deepcopy(GOOD)
        c["checklist"] = c["checklist"][:2]
        self.assertIn("checklist needs 3 or more items", self.check(c)["r"])

    def test_bad_kind(self):
        c = copy.deepcopy(GOOD)
        c["checklist"][0]["kind"] = "maybe"
        self.assertTrue(any("kind of deterministic or judgement" in p for p in self.check(c)["r"]))

    def test_item_without_text(self):
        c = copy.deepcopy(GOOD)
        c["checklist"][1]["text"] = "  "
        self.assertTrue(any("needs text" in p for p in self.check(c)["r"]))

    def test_checklist_not_a_list(self):
        c = copy.deepcopy(GOOD)
        c["checklist"] = "one string"
        self.assertIn("checklist must be a list", self.check(c)["r"])

    def test_contract_for_unknown_role(self):
        out = contract_errors({}, {"ghost": copy.deepcopy(GOOD)})
        self.assertEqual(out, {"ghost": ["contract has no active role"]})


if __name__ == "__main__":
    unittest.main()
