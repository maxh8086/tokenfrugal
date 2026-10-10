"""Build a model-comparison table from bench/*.json runs that cover the full realworld suite.
Usage: python -m scripts.bench_table [glob ...]   (default: bench/*full-*.json bench/*confirm*.json)
Writes Benchmark/model-comparison.md and a sortable/filterable Benchmark/model-comparison.html."""
import glob
import yaml
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(patterns):
    rows = {}
    for pat in patterns:
        for f in sorted(glob.glob(str(ROOT / pat))):
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            rw = (d.get("results") or {}).get("realworld") or {}
            if len(rw) >= 16:
                rows[d["tag"]] = (d, rw)  # later files win for the same tag
    return rows


NOTES = {
    "confirmA": "yarn3b builder + granite4 thinker (earlier run)",
    "confirmB": "qwen25c-7b builder + granite4 thinker (earlier run)",
    "confirmC": "earlier run, config not recorded",
    "full-defaults-yarn3b-llama32": "current personas.yaml pair",
}

# parameters in billions: (label, sort key = largest model loaded)
PARAMS = {
    "confirmA": ("3B + 3B", 3), "confirmB": ("7B + 3B", 7), "confirmC": ("?", 0),
    "full-defaults-yarn3b-llama32": ("3B + 3B", 3), "full-llama3-2-3b-16k": ("3B", 3),
    "full-ts-granite4-micro-16384": ("3B", 3), "full-ts-qwen3-4b-16384": ("4B", 4),
    "full-ts-phi4-mini-16384": ("3.8B", 3.8), "full-ts-gemma3-4b-16384": ("4B", 4),
    "full-ts-gemma4-e4b-16384": ("4B eff. (8B raw)", 4), "full-ts-qwen25c-7b-16384": ("7B", 7),
    "full-ts-qwen25c-7b-builder-granite-thinker": ("7B + 3B", 7), "full-ts-granite3-3-8b-16384": ("8B", 8),
    "full-ts-llama3-1-8b-16384": ("8B", 8), "full-ts-qwen2-5-7b-16384": ("7B", 7),
    "full-ts-qwen3-8b-16384": ("8B", 8), "full-ts-ministral-3-8b-16384": ("8B", 8),
    "full-ts-qwen2-5vl-7b-16384": ("7B", 7), "full-ts-deepseek-r1-8b-16384": ("8B", 8),
    "full-ts-starcoder2-7b-16384": ("7B", 7), "full-ts-michelrosselli-bonsai-27b-16384": ("27B", 27),
}


# case -> role that serves it (see gateway/personas.yaml; agent slug -> role via division/overrides)
CASE_ROLE = {
    "write_function": "builder", "fix_bug": "builder", "write_tests": "builder", "rename_across_files": "builder",
    "find_symbol": "builder", "review_sqli": "reviewer", "debug_trace": "debugger", "summarize_readme": "research",
    "role_analyzer": "analyzer", "role_data": "data", "role_docs": "docs", "role_security": "security",
    "role_designer": "designer", "role_browser": "browser", "role_tracker": "tracker", "role_research": "research",
}
# tool the case task actually asks for (what a replacement tool would have to match)
CASE_TOOL = {
    "write_function": "write_file", "fix_bug": "read_file+edit_file", "write_tests": "read_file+write_file",
    "rename_across_files": "search_files+edit_file", "find_symbol": "search_graph", "review_sqli": "read_file",
    "debug_trace": "read_file", "summarize_readme": "fetch/read_file", "role_analyzer": "search_graph",
    "role_data": "list_directory", "role_docs": "read_file", "role_security": "read_file",
    "role_designer": "high_level_overview", "role_browser": "navigate_page+take_snapshot",
    "role_tracker": "plan_status", "role_research": "crawl_markdown",
}


SYN = {"search_graph", "get_code_snippet", "trace_path"}
FS = {"read_file", "write_file", "edit_file", "search_files", "list_directory"}


def server_for(role, tool):
    """MCP server that really exposes the tool (profiles/*.yaml, native servers in personas.yaml)."""
    rw = role in ("builder", "data")
    if tool in FS:
        return "ts-fs-rw" if rw else "ts-fs-ro"
    if tool in SYN:
        return "synaptree"
    if tool in ("git_diff", "git_log"):
        return "ts-git"
    if tool == "ast-grep":
        return "ast-grep"
    if tool == "sequentialthinking":
        return "sequentialthinking"
    if tool == "execute_code":
        return "mcp-code-interpreter"
    if tool == "fetch":
        return "fetch"
    if tool in ("search_sonar_issues_in_projects", "search_security_hotspots", "show_rule"):
        return "sonarqube"
    if tool in ("high_level_overview", "get_design_context", "get_screenshot", "component_map", "token_map", "design_diff"):
        return "ts-penpot"
    if tool.startswith("plan_"):
        return "plan (native)"
    if tool == "web_search":
        return "searxng"
    if tool.startswith("crawl_"):
        return "crawl4ai"
    if tool in ("read_query", "write_query", "list_tables"):
        return "db (none in profile)"
    return "tokenfrugal-chrome-devtools"


def qual(role, spec):
    return " + ".join(f"{server_for(role, t)}.{t}" for t in spec.replace("fetch/read_file", "fetch").split("+"))


FSS = "Filesystem MCP server (mcp/filesystem)"
SYNS = "synaptree-mcp (maxh8086/synaptree-mcp)"
# case -> (display name, public MCP server, tools the task exercises)
CASE_PUBLIC = {
    "write_function": ("write_function", FSS, "write_file"),
    "fix_bug": ("fix_bug", FSS, "read_file, edit_file"),
    "write_tests": ("write_tests", FSS, "read_file, write_file"),
    "rename_across_files": ("rename_across_files", FSS, "search_files, edit_file"),
    "find_symbol": ("find_symbol", SYNS, "search_graph"),
    "review_sqli": ("review_sqli", FSS, "read_file"),
    "debug_trace": ("debug_trace", FSS, "read_file"),
    "summarize_readme": ("summarize_readme", "Fetch MCP server (mcp/fetch)", "fetch"),
    "role_analyzer": ("code_graph_search", SYNS, "search_graph"),
    "role_data": ("list_project_files", FSS, "list_directory"),
    "role_docs": ("read_docs_file", FSS, "read_file"),
    "role_security": ("security_file_read", FSS, "read_file"),
    "role_designer": ("design_overview", "Penpot MCP (penpot/penpot, mcp package)", "high_level_overview"),
    "role_browser": ("browser_navigate_snapshot", "Chrome DevTools MCP (ChromeDevTools/chrome-devtools-mcp)", "navigate_page, take_snapshot"),
    "role_tracker": ("plan_status", "TokenFrugal plan MCP server (this repo, Neo4j backed)", "plan_status"),
    "role_research": ("web_crawl", "Crawl4AI MCP server (unclecode/crawl4ai)", "crawl_markdown"),
}


# agency-agents persona used by each case (scripts/bench_real.py)
CASE_PERSONA = {
    "write_function": "engineering-backend-architect", "fix_bug": "engineering-backend-architect",
    "write_tests": "engineering-backend-architect", "rename_across_files": "engineering-backend-architect",
    "find_symbol": "engineering-backend-architect", "review_sqli": "testing-code-reviewer",
    "debug_trace": "engineering-sre", "summarize_readme": "support-docs-writer", "role_analyzer": "finance-analyst",
    "role_data": "gis-analyst", "role_docs": "engineering-technical-writer", "role_security": "security-auditor",
    "role_designer": "design-ui-designer", "role_browser": "testing-evidence-collector",
    "role_tracker": "project-management-project-shepherd", "role_research": "support-docs-writer",
}


def case_meta():
    return {c: {"name": n, "srv": srv, "tools": t, "persona": CASE_PERSONA[c]} for c, (n, srv, t) in CASE_PUBLIC.items()}


def params(tag):
    if tag in PARAMS:
        return PARAMS[tag]
    if "gemma4" in tag and "granite4" in tag:
        return ("4B eff. + 3B", 4)
    if "gemma4" in tag:
        return ("4B eff. + 3B", 4)
    if "granite4-solo" in tag:
        return ("3B", 3)
    return ("?", 0)


HTML = """<!doctype html><meta charset=utf-8><title>Model comparison</title>
<style>body{font:14px system-ui;margin:16px;background:#fff;color:#111}@media(prefers-color-scheme:dark){body{background:#161616;color:#eee}th{background:#2a2a2a!important}}
.bar{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;align-items:center}input,select{font:inherit;padding:4px}
table{border-collapse:collapse}th,td{border:1px solid #8884;padding:3px 7px;text-align:center;white-space:nowrap}
th{background:#eee;cursor:pointer;position:sticky;top:0;z-index:2}td.f,th.f{position:sticky;background:#fff;z-index:1}th.f{z-index:3;background:#eee}@media(prefers-color-scheme:dark){td.f{background:#161616}th.f{background:#2a2a2a!important}}th.mt{white-space:normal;word-break:break-word;vertical-align:middle;font-weight:400;font-size:11px;text-align:left;cursor:default;vertical-align:top;top:0}tr.m th.mt{position:sticky;text-align:left;background:#fff}tr.m th.f{background:#eee}tr.m th.mt b{font-size:12px}tr.m th.mt div{margin:2px 0}td.r,th.mt{min-width:190px;max-width:190px}.fl{border-right:2px solid #888}td.l{text-align:left}.w{overflow:auto;max-height:85vh;max-width:100%}
.c2{background:#2e7d3255}.c1{background:#f9a82555}.c0{background:#c6282833}</style>
<h2>Model comparison (realworld suite, 2 runs per case)</h2>
<div class=bar><input id=q placeholder="filter by model or note"><label>min verified <input id=mv type=number value=0 min=0 max=32 style="width:55px"></label>
<label>passes case <select id=cs><option value="">any</option></select> at least <select id=cl><option value=1>1/2</option><option value=2>2/2</option></select></label>
<label><input id=hz type=checkbox> hide zero-score models</label><span id=cnt></span></div>
<div class=w><table id=t><thead></thead><tbody></tbody></table></div>
<p>Left columns stay fixed; scroll right for per-case results. Click a column header to sort (click again to reverse). Cells: verified runs out of 2. Each case column is headed by the public MCP server and tool(s) that the task exercises.</p>
<script>
const D=__DATA__,C=__CASES__,M=__META__;let sk="ok",sd=-1;
const cols=[["Sr",null],["Model","tag"],["Params (B)","pk"],["Time (s)","mean"],["Verified","ok"],["Ran","ran"],["Note","note"],...C.map(c=>[M[c].name,c])];
const th=document.querySelector("thead");const NF=6;
const fc=(i)=>i<NF?` class="f${i==NF-1?" fl":""}"`:"";
const gh="<tr class=m>"+cols.slice(0,NF).map((x,i)=>`<th class="f${i==NF-1?" fl":""}"></th>`).join("")+"<th></th>"+C.map(c=>`<th class=mt><b>${M[c].srv}</b><br>persona: <i>${M[c].persona}</i><br>tools: <i>${M[c].tools}</i></th>`).join("")+"</tr>";
th.innerHTML=gh+"<tr>"+cols.map(([n,k],i)=>`<th data-k="${k}"${fc(i)}>${n}</th>`).join("")+"</tr>";
const cs=document.getElementById("cs");C.forEach(c=>cs.add(new Option(M[c].name,c)));
const val=(r,k)=>C.includes(k)?r.cases[k]:r[k];
function draw(){const q=document.getElementById("q").value.toLowerCase(),mv=+document.getElementById("mv").value,
c=cs.value,cl=+document.getElementById("cl").value,hz=document.getElementById("hz").checked;
let rows=D.filter(r=>(r.tag+" "+r.note).toLowerCase().includes(q)&&r.ok>=mv&&(!hz||r.ok>0)&&(!c||r.cases[c]>=cl));
rows.sort((a,b)=>{const x=val(a,sk),y=val(b,sk);return (x>y?1:x<y?-1:0)*sd});
document.querySelector("tbody").innerHTML=rows.map((r,i)=>"<tr><td class=f>"+(i+1)+`</td><td class="l f" title="${r.tag}">${r.tag.replace(/^full-(ts-)?/,"").replace(/-16384$/,"")}</td><td class=f>${r.params}</td><td class=f>${r.mean}</td><td class=f>${r.ok}/${r.tot}</td><td class="f fl">${r.ran}/${r.tot}</td><td class=l>${r.note}</td>`+C.map(k=>`<td class="r c${r.cases[k]}">${r.cases[k]}/2</td>`).join("")+"</tr>").join("");
document.getElementById("cnt").textContent=rows.length+" of "+D.length+" models";freeze()}
function freeze(){document.querySelectorAll("th.f,td.f").forEach(c=>{c.style.minWidth=c.style.maxWidth="";c.style.left=""});const w=[...document.querySelector("tbody tr").children].slice(0,NF).map(c=>c.offsetWidth);document.querySelectorAll("th.f,td.f").forEach(c=>{const i=c.cellIndex;c.style.left=w.slice(0,i).reduce((a,b)=>a+b,0)+"px";c.style.minWidth=c.style.maxWidth=(w[i]-14-1)+"px"});const h=document.querySelector("tr.m").offsetHeight;document.querySelectorAll("thead tr:nth-child(2) th").forEach(c=>c.style.top=h+"px")}
th.onclick=e=>{const k=e.target.dataset.k;if(!k||k=="null")return;sd=(sk==k)?-sd:(k=="tag"||k=="note"||k=="mean"||k=="pk"?1:-1);sk=k;draw()};
["q","mv","cs","cl","hz"].forEach(i=>document.getElementById(i).oninput=draw);draw();
</script>"""


def frac(s):
    a, b = s.split("/")
    return int(a), int(b)


def main():
    pats = sys.argv[1:] or ["bench/*full-*.json", "bench/*confirm*.json", "bench/*-llama*full*.json"]
    rows = load(pats)
    if not rows:
        sys.exit("no full-suite runs found")
    cases = list(next(iter(rows.values()))[1])
    table = []
    for tag, (d, rw) in rows.items():
        ok = sum(frac(c["verified"])[0] for c in rw.values() if c["verified"] != "n/a" and "/" in c["verified"])
        tot = sum(frac(c["verified"])[1] for c in rw.values() if "/" in c["verified"])
        ran = sum(frac(c["ran"])[0] for c in rw.values() if "/" in c["ran"])
        mean = sum(c["s"]["mean"] for c in rw.values() if c.get("s")) / max(1, len(rw))
        table.append((ok / max(tot, 1), tag, ok, tot, ran, mean, rw))
    table.sort(reverse=True)
    out = ["# Model comparison (realworld suite, all cases)", "",
           "| Model / run tag | Params | Verified | Ran | Mean s/case | " + " | ".join(f"{CASE_PUBLIC[c][0]}<br>{CASE_PUBLIC[c][1]}<br>persona: {CASE_PERSONA[c]}" for c in cases) + " |",
           "|---|---|---|---|---|" + "---|" * len(cases)]
    for _, tag, ok, tot, ran, mean, rw in table:
        out.append(f"| {tag} | {params(tag)[0]} | {ok}/{tot} | {ran}/{tot} | {mean:.1f} | " + " | ".join(rw[c]["verified"] if c in rw else "-" for c in cases) + " |")
    text = "\n".join(out) + "\n"
    (ROOT / "Benchmark").mkdir(exist_ok=True)
    (ROOT / "Benchmark" / "model-comparison.md").write_text(text, encoding="utf-8")
    data = []
    for _, tag, ok, tot, ran, mean, rw in table:
        data.append({"tag": tag, "ok": ok, "tot": tot, "ran": ran, "mean": round(mean, 1), "params": params(tag)[0], "pk": params(tag)[1], "note": NOTES.get(tag, ""),
                     "cases": {c: (frac(rw[c]["verified"])[0] if c in rw and "/" in rw[c]["verified"] else 0) for c in cases}})
    html = HTML.replace("__DATA__", json.dumps(data)).replace("__CASES__", json.dumps(cases)).replace("__META__", json.dumps(case_meta()))
    (ROOT / "Benchmark" / "model-comparison.html").write_text(html, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
