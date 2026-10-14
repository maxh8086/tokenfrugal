"""Post-write feedback for Python files: syntax errors and names that are used but never bound.
Conservative on purpose (module-wide binding set, no scopes) so it never flags valid code."""
import ast
import builtins


def check_python(src: str) -> str | None:
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return f"syntax error line {e.lineno}: {e.msg}"
    bound = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.name == "*":
                    return None
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            bound.add(n.name)
    missing = sorted({n.id for n in ast.walk(tree)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in bound})
    return f"undefined names: {', '.join(missing)} (add the missing import or definition)" if missing else None
