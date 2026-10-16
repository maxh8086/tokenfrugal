"""Write a realworld benchmark result as CSV in the Benchmark/model-comparison.md layout.

Columns: Model / run tag, Params, Verified, Ran, Mean s/case, then one column per realworld case
(16 columns, in layout order). Each case cell is "verified/n".

Usage: python scripts/bench_csv.py bench/<stamp>-<tag>.json [out.csv]
"""
import csv
import json
import re
import sys
from pathlib import Path

# (bench_real case id, layout column, tool server, layout persona shown in the header)
LAYOUT = [
    ("write_function", "write_function", "Filesystem MCP server (mcp/filesystem)"),
    ("fix_bug", "fix_bug", "Filesystem MCP server (mcp/filesystem)"),
    ("write_tests", "write_tests", "Filesystem MCP server (mcp/filesystem)"),
    ("rename_across_files", "rename_across_files", "Filesystem MCP server (mcp/filesystem)"),
    ("find_symbol", "find_symbol", "synaptree-mcp (maxh8086/synaptree-mcp)"),
    ("review_sqli", "review_sqli", "Filesystem MCP server (mcp/filesystem)"),
    ("debug_trace", "debug_trace", "Filesystem MCP server (mcp/filesystem)"),
    ("summarize_readme", "summarize_readme", "Read local README and summarize (docs role, read_file)"),
    ("role_analyzer", "code_graph_search", "synaptree-mcp (maxh8086/synaptree-mcp)"),
    ("role_data", "list_project_files", "Filesystem MCP server (mcp/filesystem)"),
    ("role_docs", "read_docs_file", "Filesystem MCP server (mcp/filesystem)"),
    ("role_security", "security_file_read", "Filesystem MCP server (mcp/filesystem)"),
    ("role_designer", "design_overview", "Penpot MCP (penpot/penpot, mcp package)"),
    ("role_browser", "browser_navigate_snapshot", "Chrome DevTools MCP (ChromeDevTools/chrome-devtools-mcp)"),
    ("role_tracker", "plan_status", "TokenFrugal plan MCP server (this repo, Neo4j backed)"),
    ("role_research", "web_crawl", "Crawl4AI MCP server (unclecode/crawl4ai)"),
]

# Persona comes from the agent each case dispatches to (bench_real.cases()).
PERSONAS = {
    "write_function": "engineering-backend-architect", "fix_bug": "engineering-backend-architect",
    "write_tests": "engineering-backend-architect", "rename_across_files": "engineering-backend-architect",
    "find_symbol": "engineering-backend-architect", "review_sqli": "testing-code-reviewer",
    "debug_trace": "engineering-sre", "summarize_readme": "engineering-technical-writer",
    "role_analyzer": "engineering-software-architect", "role_data": "gis-analyst",
    "role_docs": "engineering-technical-writer", "role_security": "security-auditor",
    "role_designer": "design-ui-designer", "role_browser": "testing-evidence-collector",
    "role_tracker": "project-management-project-shepherd", "role_research": "support-docs-writer",
}

PARAMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[bB](?![a-zA-Z])")


def _params(tag):
    m = PARAMS_RE.search(tag)
    return f"{m.group(1)}B" if m else ""


def _split(cell):
    a, b = cell.split("/")
    return int(a), int(b)


def header():
    cols = ["Model / run tag", "Params", "Verified", "Ran", "Mean s/case"]
    for cid, label, server in LAYOUT:
        cols.append(f"{label}\n{server}\npersona: {PERSONAS[cid]}")
    return cols


def rows(data):
    res = data.get("results", {}).get("realworld", {})
    if "error" in res or not res:
        return []
    v_tot = v_n = r_tot = 0
    means = []
    cells = []
    for cid, _, _ in LAYOUT:
        c = res.get(cid)
        if c is None:
            cells.append("")
            continue
        v, n = _split(c["verified"])
        r, _ = _split(c["ran"])
        v_tot += v
        v_n += n
        r_tot += r
        if c.get("s"):
            means.append(c["s"]["mean"])
        cells.append(c["verified"])
    tag = data.get("tag", "")
    mean = round(sum(means) / len(means), 1) if means else ""
    return [[tag, _params(tag), f"{v_tot}/{v_n}", f"{r_tot}/{v_n}", mean] + cells]


def status_scores(cases):
    """(valid_cases, infra_cases, mean_s_valid) over realworld case results.
    A case whose status is "infra" (synaptree container down, see bench_real.case_status) counts only in
    infra_cases and is excluded from the mean. mean_s_valid is "" when no valid case has timings."""
    valid = infra = 0
    means = []
    for c in cases.values():
        if c.get("status") == "infra":
            infra += 1
            continue
        valid += 1
        if c.get("s"):
            means.append(c["s"]["mean"])
    mean = round(sum(means) / len(means), 1) if means else ""
    return valid, infra, mean


def total_seconds(cases):
    """Wall time in whole seconds of every repeat that ran, infra repeats included (their elapsed time is real).
    Sums the per-repeat "s" field that bench_real.run also feeds into the case timings. 0 when nothing ran."""
    total = 0.0
    for c in cases.values():
        if isinstance(c, dict):  # skips a section-level {"error": ...} entry
            total += sum(x.get("s", 0.0) for x in c.get("runs", []))
    return round(total)


def write(data, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header())
        w.writerows(rows(data))


if __name__ == "__main__":
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".csv")
    write(json.loads(src.read_text(encoding="utf-8")), dst)
    print("wrote", dst)
