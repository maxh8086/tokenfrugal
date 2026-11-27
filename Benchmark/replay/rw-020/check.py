"""Verify the values imported by both report generators."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.cwd()))
for key in list(os.environ):
    if key.startswith("TOKENFRUGAL_"):
        del os.environ[key]

from scripts import bench_consolidate, bench_csv

expected = dict.fromkeys(
    "write_function fix_bug write_tests rename_across_files find_symbol".split(),
    "engineering-backend-architect",
)
expected.update(
    review_sqli="testing-code-reviewer", debug_trace="engineering-sre",
    summarize_readme="engineering-technical-writer", role_research="support-docs-writer",
    role_analyzer="engineering-software-architect", role_data="gis-analyst",
    role_docs="engineering-technical-writer", role_security="security-auditor",
    role_designer="design-ui-designer", role_browser="testing-evidence-collector",
    role_tracker="project-management-project-shepherd",
)
case = "summarize_readme"
assert [tuple(row) for row in bench_csv.LAYOUT if row[0] == case] == [
    (case, case, "Read local README and summarize (docs role, read_file)")
]
assert bench_csv.PERSONAS == expected
assert bench_consolidate.CASE_PERSONA == expected
