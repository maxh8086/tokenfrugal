"""Replay task rw-019: scripts/bench_real.py has a stricter _readme_ok checker and the summarize case uses it (offline)."""
import ast
import os
import sys

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
SOURCE = os.path.join(ROOT, "scripts", "bench_real.py")
TABLE = [
    ("Local MCP router.", True),
    ("ollama mcp delegation", True),
    ("local mcp summary of the project", True),
    ("LOCAL MCP ROUTER", True),
    ("mcp summary of the project", False),
    ("local summary only", False),
    ("mcp local but no action word", False),
    ("MCP local router. Could not read the second file.", False),
    ("MCP local router. I cannot read the README.", False),
    ("MCP local router, unable to read it", False),
    ("MCP local router, unable to access the disk", False),
    ("MCP local router. do not have access to docs", False),
    ("MCP local router, openai api used", False),
    ("MCP local router, github platform", False),
]
LONG = "MCP local router\n" + "x" * 200


def fail(message):
    print("FAIL:", message)
    return 1


def load_function(tree, text, name):
    found = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(found) != 1:
        return None, "module-level def %s not found exactly once" % name
    namespace = {}
    exec(ast.get_source_segment(text, found[0]), namespace)
    return namespace[name], ""


def main():
    with open(SOURCE, encoding="utf-8") as handle:
        text = handle.read()
    tree = ast.parse(text)
    checker, problem = load_function(tree, text, "_readme_ok")
    if problem:
        return fail(problem)
    for sample, want in TABLE:
        try:
            got = checker(sample)
        except Exception as exc:
            return fail("_readme_ok(%r) raised %r" % (sample, exc))
        if not (isinstance(got, tuple) and len(got) == 2):
            return fail("_readme_ok(%r) returned %r, expected a 2-tuple" % (sample, got))
        if bool(got[0]) != want:
            return fail("_readme_ok(%r)[0] is %r, expected %r" % (sample, got[0], want))
        if got[1] != sample[:100].replace("\n", " "):
            return fail("_readme_ok(%r)[1] is %r" % (sample, got[1]))
    got = checker(LONG)
    if bool(got[0]) is not True or got[1] != LONG[:100].replace("\n", " "):
        return fail("long answer: got %r" % (got,))
    hits = [node for node in ast.walk(tree) if isinstance(node, ast.Tuple) and node.elts
            and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == "summarize_readme"]
    if len(hits) != 1 or len(hits[0].elts) != 5:
        return fail("expected one summarize_readme 5-element case, found %d" % len(hits))
    agent, checker_node = hits[0].elts[1], hits[0].elts[4]
    if not (isinstance(agent, ast.Constant) and agent.value == "engineering-technical-writer"):
        return fail("summarize_readme agent is %r" % (ast.get_source_segment(text, agent),))
    if not (isinstance(checker_node, ast.Name) and checker_node.id == "_readme_ok"):
        return fail("summarize_readme checker is %r, expected _readme_ok" % (ast.get_source_segment(text, checker_node),))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
