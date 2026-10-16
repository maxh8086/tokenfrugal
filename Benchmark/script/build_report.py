"""Rebuild the generated parts of Benchmark/Benchmark.md and Benchmark/explorer.html from results/benchmark.csv.

    python Benchmark/script/build_report.py

Only the text between <!-- BEGIN:auto --> and <!-- END:auto --> in Benchmark.md is replaced; the
hand-written sections (conclusions, observations) are never touched.

Inputs: results/benchmark.csv plus results/cloud.csv (if present), merged into one list of runs.
Cloud rows (builder_model starting with `claude-`) live in cloud.csv, with the same header, so the
Haiku baseline stays intact unless a new cloud run is added there.
"""
import csv
import html
import json
import re
from pathlib import Path

import yaml

B = Path(__file__).resolve().parent.parent          # Benchmark/
AGENTS = B.parent / "router" / "agents.yaml"

# The 16 real case columns. Anything else in the CSV (meta, context_used_* columns) is not a case.
BUILDER_CASES = ["write_function", "fix_bug", "write_tests", "rename_across_files"]
THINKER_CASES = ["find_symbol", "review_sqli", "debug_trace", "summarize_readme", "code_graph_search",
                 "list_project_files", "read_docs_file", "security_file_read", "design_overview",
                 "browser_navigate_snapshot", "plan_status", "web_crawl"]
CASES = BUILDER_CASES + THINKER_CASES
assert len(CASES) == 16

# Cases that need a specific MCP tool. A 0 score here is marked with a warning sign.
REQUIRED_TOOL_CASES = {
    "plan_status": "plan_status",                       # role_tracker
    "design_overview": "high_level_overview",           # role_designer
    "browser_navigate_snapshot": "navigate_page",       # role_browser
}

rows = []
for _name in ("benchmark.csv", "cloud.csv"):
    _path = B / "results" / _name
    if _path.exists():
        rows += list(csv.DictReader(_path.open(encoding="utf-8")))
missing = [c for c in CASES if c not in rows[0]]
if missing:
    raise SystemExit(f"benchmark.csv is missing case columns: {missing}")


def num(r, k):
    try:
        return float(r[k])
    except (ValueError, TypeError, KeyError):
        return 0.0


def pct(r):
    return 100 * num(r, "score") / max(num(r, "max"), 1)


def params_b(p):
    m = re.match(r"\s*([\d.]+)B", p or "")
    return float(m.group(1)) if m else None


def case_frac(r, c):
    try:
        a, n = r[c].split("/")
        return int(a) / int(n)
    except Exception:
        return None


LOCAL_BUILDS = {   # tag -> (base model to pull, Modelfile that derives the tag)
    "qwen2.5-coder-yarn:3b": ("qwen2.5-coder:3b", "models/builder.Modelfile"),
    "llama3.2:3b-16k": ("llama3.2:3b", "models/thinker.Modelfile"),
}


def origin(name):
    """(source, exact command to get this model) from the model tag the run used."""
    if name.startswith("claude-"):
        return "Anthropic API", "not pullable (cloud baseline)"
    if name in LOCAL_BUILDS:
        base, mf = LOCAL_BUILDS[name]
        return "Ollama library + local Modelfile", f"ollama pull {base} && ollama create {name} -f {mf}"
    if name.startswith("hf.co/"):
        org_repo = name[len("hf.co/"):].split(":")[0]
        return f"Hugging Face: {org_repo}", f"ollama pull {name}"
    return "Ollama library", f"ollama pull {name}"


def subtotal(r, cases):
    """(passed, total) summed over the given case columns."""
    a = n = 0
    for c in cases:
        try:
            x, y = r[c].split("/")
            a, n = a + int(x), n + int(y)
        except Exception:
            pass
    return a, n


def sub_md(r, cases):
    a, n = subtotal(r, cases)
    return f"{a}/{n}" if n else "·"


rows.sort(key=lambda r: (-pct(r), num(r, "mean_s_per_case")))
for r in rows:
    r["pct"] = round(pct(r))
    r["day"] = (r.get("date") or "")[:10]
    r["source"], r["pull"] = origin(r["builder_model"])
    r["builder_score"], r["thinker_score"] = sub_md(r, BUILDER_CASES), sub_md(r, THINKER_CASES)
    r["params_b"] = params_b(r["params"])


def mmss(v):
    """total_s seconds as m:ss; '' when blank (legacy rows written before total_s existed)."""
    try:
        t = int(float(v))
    except (ValueError, TypeError):
        return ""
    return f"{t // 60}:{t % 60:02d}"


RANK_LEGEND = [
    f"Score = verified checks passed out of total checks across {len(CASES)} cases.",
    "Pass rate % = Score / max.",
    "Builder / Thinker = the same score split by role cases.",
    "s per case = mean seconds per case.",
    "Run time = wall clock for the whole run.",
    "Valid cases = cases that finished without infrastructure failure (invalid cases are excluded from speed, not from score).",
    "Date = when the run happened; newer = made with newer code.",
]
RANK_LEGEND_MD = "\n".join(f"- {l}" for l in RANK_LEGEND)


def md_table():
    o = ["| # | Model | Date | Params | Score | Pass rate % | Builder | Thinker | s per case | Run time | Valid cases |",
         "|--:|---|---|---|--:|--:|--:|--:|--:|--:|--:|"]
    for i, r in enumerate(rows, 1):
        m = f"`{r['builder_model']}`" + (" ⚠infra" if num(r, "infra_cases") > 0 else "")
        o.append(f"| {i} | {m} | {r['day']} | {r['params']} | {r['score']}/{r['max']} "
                 f"| {r['pct']} | {r['builder_score']} | {r['thinker_score']} "
                 f"| {r['mean_s_per_case']} | {mmss(r.get('total_s'))} | {r.get('valid_cases') or ''} |")
    return "\n".join(o)


def role_rank(cases, top=5):
    """Local models ranked on one role's cases only. Only each model's newest-dated runs count, so
    results from older harness or router code never mix with current ones. Runs on that date are
    merged (passes and checks summed); ties go to more evidence, then speed. Cloud baseline excluded."""
    newest = {}
    for r in rows:
        d = (r.get("date") or "")[:10]
        newest[r["builder_model"]] = max(newest.get(r["builder_model"], ""), d)
    agg = {}
    for r in rows:
        a, n = subtotal(r, cases)
        if not n or r["builder_model"].startswith("claude-") or (r.get("date") or "")[:10] != newest[r["builder_model"]]:
            continue
        m = agg.setdefault(r["builder_model"], {"a": 0, "n": 0, "runs": 0, "s": [], "r": r, "d": newest[r["builder_model"]], "g": set(), "h": set()})
        m["a"] += a
        m["n"] += n
        m["runs"] += 1
        m["g"].add((r.get("git_sha") or "")[:7])
        m["h"].add(r.get("harness_version") or "")
        if num(r, "mean_s_per_case"):
            m["s"].append(num(r, "mean_s_per_case"))
    ranked = sorted(agg.items(), key=lambda kv: (-kv[1]["a"] / kv[1]["n"], -kv[1]["n"],
                                                  sum(kv[1]["s"]) / max(len(kv[1]["s"]), 1)))
    o = ["| # | Model | Date | Code (git) | Harness | Role score | % | Runs | s/case | Shared memory GB | Pull command |",
         "|--:|---|---|---|---|--:|--:|--:|--:|--:|---|"]
    for i, (name, m) in enumerate(ranked[:top], 1):
        spc = f"{sum(m['s']) / len(m['s']):.1f}" if m["s"] else ""
        sha = ", ".join(f"`{g}`" for g in sorted(m["g"]) if g)
        o.append(f"| {i} | `{name}` | {m['d']} | {sha} | {', '.join(sorted(h for h in m['h'] if h)) or '-'} | {m['a']}/{m['n']} | {round(100 * m['a'] / m['n'])} | {m['runs']} | {spc} "
                 f"| {m['r'].get('shared_system_memory_gb') or ''} | `{m['r']['pull']}` |")
    return "\n".join(o)


def cell_md(r, c):
    f = case_frac(r, c)
    if f is None:
        return "·"
    mark = "🟩" if f == 1 else "🟨" if f > 0 else "🟥"
    if f == 0 and c in REQUIRED_TOOL_CASES:
        mark += "⚠"
    return mark


def heatmap(cases):
    o = ["| Run | " + " | ".join(c.replace("_", " ") for c in cases) + " |",
         "|---|" + "---|" * len(cases)]
    for r in rows:
        o.append(f"| `{r['builder_model'][:44]}` | " + " | ".join(cell_md(r, c) for c in cases) + " |")
    return "\n".join(o)


def role_cfg():
    """Role -> model class -> allowed tools, read from router/agents.yaml so it cannot drift."""
    return yaml.safe_load(AGENTS.read_text(encoding="utf-8"))


_CFG = role_cfg()

LEGEND_MD = """- Each **run** is one local model setup, scored on the same 16 cases. `score` is passes out of `max`.
- **Builder** (`qwen2.5-coder-yarn:3b`) writes code and edits files. **Thinker** (`llama3.2:3b-16k`) reads, analyses and browses.
- A task uses **one** model at a time. Models never run together or talk to each other.
- The role table shows which tools each role is allowed to call. A case needs the tools of its role.
- 🟩 all checks passed, 🟨 some passed, 🟥 none passed, `·` not run.
- ⚠ on a case that needs a specific tool means that run scored 0 on it, so the tool was likely missing or not called."""

auto = f"""<!-- BEGIN:auto -->
_{len(rows)} runs x {len(CASES)} cases, generated from `results/benchmark.csv` and `results/cloud.csv` by `script/build_report.py`._

### Ranking (best score first, ties by speed)

{RANK_LEGEND_MD}

{md_table()}

### Best model per role (local models, top 5 each)

Each role is ranked only on its own cases, because one model is pinned to both roles in a run. Only a model's newest-dated runs count, so older results from earlier code never mix with current ones; the `Code (git)` column shows the commit that produced them. Results change as the router and harness change, so re-run a model after significant changes before trusting its place. Ties go to the model with more evidence, then the faster one. `Shared memory GB` above 0 means part of the model spilled off the GPU, which is slower. The Haiku cloud baseline is left out because it cannot be pulled.

**Builder** (cases: {", ".join(f"`{c}`" for c in BUILDER_CASES)})

{role_rank(BUILDER_CASES)}

**Thinker** (cases: {", ".join(f"`{c}`" for c in THINKER_CASES)})

{role_rank(THINKER_CASES)}

Charts, filters, the legend and the roles table are in [explorer.html](explorer.html).

### Builder cases (code and file edits: needs write/edit tools)

{heatmap(BUILDER_CASES)}

### Thinker cases (read, analyse, browse: needs read/graph/browser tools)

{heatmap(THINKER_CASES)}
<!-- END:auto -->"""

p = B / "Benchmark.md"
# Benchmark.md holds stable text only; results are rendered into index.html (not written to the md).


def roles_html():
    body = ["<tr><th>Role</th><th>Model class</th><th>Tools the role may call</th></tr>"]
    for name, r in _CFG["roles"].items():
        cls = r.get("model")
        tag = _CFG["models"].get(cls, "?")
        tools = ", ".join(html.escape(t) for t in (r.get("tools") or []))
        body.append(f"<tr><td><code>{html.escape(name)}</code></td><td>{html.escape(cls)} (<code>{html.escape(tag)}</code>)</td><td>{tools}</td></tr>")
    return (f"<details open><summary>Roles and models</summary>"
            f"<div class=\"w\"><table class=\"roles\">{''.join(body)}</table></div>"
            f"<p class=\"mut\">Column groups: builder cases = {html.escape(', '.join(BUILDER_CASES))}. "
            f"Thinker cases = {html.escape(', '.join(THINKER_CASES))}.</p></details>")


def legend_html():
    items = RANK_LEGEND + [l.lstrip('- ').replace('**', '') for l in LEGEND_MD.splitlines()]
    return ("<details open><summary>How to read this</summary><ul>"
            + "".join(f"<li>{html.escape(l)}</li>" for l in items) + "</ul></details>")


HTML = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Benchmark explorer</title>
<style>
:root{--bg:#fff;--fg:#222;--mut:#666;--line:#e3e3e3;--acc:#2e9e5b;--cloud:#7a5af8}
@media(prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e6e6e6;--mut:#9aa;--line:#2c3036;--cloud:#a890ff}}
body{font:14px system-ui;margin:16px;background:var(--bg);color:var(--fg)}h1{font-size:18px}
.f{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}label{display:flex;flex-direction:column;font-size:12px;color:var(--mut)}
input,select{font:inherit;padding:4px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%}th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{cursor:pointer;position:sticky;top:0;background:var(--bg)}.bar{display:inline-block;height:10px;background:var(--acc);margin-right:6px}
.w{overflow-x:auto}.g{color:var(--acc)}.r{color:#d0453b}.y{color:#d9a021}.mut{color:var(--mut)}
details{margin:12px 0;font-size:13px}summary{cursor:pointer;font-weight:600}details ul{margin:8px 0 8px 18px;padding:0}
.cb{margin:16px 0}.cb h3{font-size:15px;margin:4px 0}.cb p{font-size:12px;margin:6px 0}
.ch svg{width:100%;height:auto;display:block}.ax{font-size:11px;fill:var(--mut)}.lb{font-size:10px;fill:var(--fg)}
</style>
<h1>Benchmark explorer</h1>
<p><a href="index.html">Back to the report</a></p>
__ROLES__
<div class="f">
<label>Min score %<input id="ms" type="number" value="0" min="0" max="100"></label>
<label>Max s/case<input id="mt" type="number" placeholder="any"></label>
<label>Max params (B)<input id="mp" type="number" placeholder="any"></label>
<label>Name contains<input id="q"></label>
<label>Must pass case<select id="cs"><option value="">(any)</option></select></label>
<label>From date<input id="fd" type="date"></label>
</div>
<div id="n"></div>
<div id="ch" class="ch"></div>
<div class="w"><table id="t"></table></div>
<script>
const D=__DATA__,C=__CASES__,REQ=__REQ__;let sk="pct",sd=-1;
const $=i=>document.getElementById(i);
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]);
const short=(s,n)=>s.length>n?s.slice(0,n-1)+"…":s;
C.forEach(c=>$("cs").add(new Option(c,c)));
const frac=(r,c)=>{try{const[a,n]=r[c].split("/");return a/n}catch(e){return null}};
const cols=[["builder_model","Model"],["day","Date","Day the run was made (YYYY-MM-DD)"],["source","Origin"],["pull","Pull command"],["params","Params"],["pct","Pass rate %","Score as a percentage of the max checks (higher is better)"],["score","Score"],["builder_score","Builder"],["thinker_score","Thinker"],["mean_s_per_case","s per case","Mean seconds per case (lower is faster)"],["total_s","Run time (s)","Wall clock seconds for the whole run"],...C.map(c=>[c,c])];
const wrap=(svg,n)=>`<div style="${n>30?"max-height:560px;overflow-y:auto":""}">${svg}</div>`;
function passChart(R){
 const S=[...R].sort((a,b)=>b.pct-a.pct);
 if(!S.length)return"<p class=\"mut\">No runs match.</p>";
 const L=230,W=680,RH=20,T=6,AX=40,PW=W-L-50,H=T+S.length*RH+AX;
 const X=v=>L+PW*v/100;
 let g="";
 [0,25,50,75,100].forEach(v=>{g+=`<line x1="${X(v)}" x2="${X(v)}" y1="${T}" y2="${H-AX}" style="stroke:var(--line)"/><text x="${X(v)}" y="${H-AX+14}" text-anchor="middle" class="ax">${v}%</text>`});
 S.forEach((r,i)=>{const y=T+i*RH;
  g+=`<text x="${L-6}" y="${y+14}" text-anchor="end" class="lb"><title>${esc(r.builder_model)}</title>${esc(short(r.builder_model,34))}</text>`
   +`<rect x="${L}" y="${y+3}" width="${PW*r.pct/100}" height="${RH-6}" style="fill:var(--acc)"><title>${esc(r.builder_model+" | "+r.pct+"%")}</title></rect>`
   +`<text x="${X(r.pct)+4}" y="${y+14}" class="lb">${r.pct}%</text>`});
 g+=`<text x="${L+PW/2}" y="${H-6}" text-anchor="middle" class="ax">Pass rate % (higher is better)</text>`;
 return wrap(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pass rate by run">${g}</svg>`,S.length);
}
function speedChart(R){
 const P=R.filter(r=>+r.mean_s_per_case>0);
 if(!P.length)return"<p class=\"mut\">No runs with seconds per case match.</p>";
 const W=680,H=380,L=52,RT=20,T=14,AX=44;
 const xmax=Math.max(10,Math.ceil(Math.max(...P.map(r=>+r.mean_s_per_case))/10)*10);
 const X=v=>L+(W-L-RT)*v/xmax, Y=v=>T+(H-T-AX)*(1-v/100);
 let g="";
 [0,25,50,75,100].forEach(v=>{g+=`<line x1="${L}" x2="${W-RT}" y1="${Y(v)}" y2="${Y(v)}" style="stroke:var(--line)"/><text x="${L-6}" y="${Y(v)+4}" text-anchor="end" class="ax">${v}</text>`});
 for(let k=0;k<=5;k++){const v=xmax*k/5;g+=`<line x1="${X(v)}" x2="${X(v)}" y1="${T}" y2="${H-AX}" style="stroke:var(--line)"/><text x="${X(v)}" y="${H-AX+14}" text-anchor="middle" class="ax">${Math.round(v)}</text>`}
 g+=`<text x="${(L+W-RT)/2}" y="${H-6}" text-anchor="middle" class="ax">Seconds per case, lower = faster</text>`;
 g+=`<text transform="translate(14 ${(T+H-AX)/2}) rotate(-90)" text-anchor="middle" class="ax">Pass rate %, higher = better</text>`;
 P.forEach(r=>{const cl=r.builder_model.startsWith("claude-"),p=r.params_b,rad=p==null||isNaN(p)?5:Math.min(12,2+Math.sqrt(p)*2.2),x=X(+r.mean_s_per_case),y=Y(r.pct);
  const t=`${r.builder_model} | score ${r.score}/${r.max} (${r.pct}%) | ${r.mean_s_per_case} s/case | params ${r.params||"unknown"}`;
  g+=`<circle cx="${x}" cy="${y}" r="${rad}" style="fill:${cl?"var(--cloud)":"var(--acc)"};fill-opacity:.8"><title>${esc(t)}</title></circle>`
   +`<text x="${x+rad+3}" y="${y+3}" class="lb">${esc(short(r.builder_model,28))}</text>`});
 return wrap(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Speed vs pass rate">${g}</svg>`,P.length);
}
function draw(){
 const q=$("q").value.toLowerCase(),ms=+$("ms").value,mt=+$("mt").value||1e9,mp=+$("mp").value||1e9,cs=$("cs").value,fd=$("fd").value;
 const R=D.filter(r=>r.pct>=ms&&+r.mean_s_per_case<=mt&&(r.params_b==null||r.params_b<=mp)&&(r.builder_model+r.source).toLowerCase().includes(q)&&(!cs||frac(r,cs)===1)&&(!fd||r.day>=fd));
 R.sort((a,b)=>{let x=a[sk],y=b[sk];x=isNaN(+x)?x:+x;y=isNaN(+y)?y:+y;return(x>y?1:x<y?-1:0)*sd});
 $("n").textContent=R.length+" of "+D.length+" runs match";
 $("ch").innerHTML=`<div class="cb"><h3>Pass rate by run</h3>${passChart(R)}</div>`
  +`<div class="cb"><h3>Speed vs pass rate</h3>${speedChart(R)}<p class="mut">Top-left corner = best (fast and accurate). Green = local, violet = cloud. Dot size = parameters.</p></div>`;
 $("t").innerHTML="<tr>"+cols.map(c=>`<th data-k="${c[0]}"${c[2]?` title="${esc(c[2])}"`:""}>${c[1].replace(/_/g," ")}</th>`).join("")+"</tr>"+
  R.map(r=>"<tr>"+cols.map(([k])=>{
   if(k=="pct")return`<td><span class="bar" style="width:${r.pct*.6}px"></span>${r.pct}</td>`;
   if(C.includes(k)){const p=frac(r,k);const w=(p===0&&REQ.includes(k))?" ⚠":"";return`<td class="${p==null?"":p==1?"g":p==0?"r":"y"}">${r[k]||"·"}${w}</td>`}
   return`<td>${r[k]}</td>`}).join("")+"</tr>").join("");
 document.querySelectorAll("th").forEach(h=>h.onclick=()=>{sd=sk==h.dataset.k?-sd:-1;sk=h.dataset.k;draw()});
}
document.querySelectorAll("input,select").forEach(e=>e.oninput=draw);draw();
</script>"""
(B / "explorer.html").write_text(
    HTML.replace("__ROLES__", legend_html() + roles_html())
        .replace("__DATA__", json.dumps(rows))
        .replace("__CASES__", json.dumps(CASES))
        .replace("__REQ__", json.dumps(list(REQUIRED_TOOL_CASES))),
    encoding="utf-8")
PAGE = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TokenFrugal benchmark</title>
<style>
:root{--bg:#fff;--fg:#222;--mut:#666;--line:#e3e3e3;--acc:#2e9e5b;--code:#f4f4f4}
@media(prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e6e6e6;--mut:#9aa;--line:#2c3036;--code:#22262b}}
body{font:15px/1.55 system-ui;margin:0;background:var(--bg);color:var(--fg)}
nav{display:flex;gap:16px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:2}
nav a{color:var(--acc);font-weight:600;text-decoration:none}
main{max-width:1100px;margin:0 auto;padding:8px 16px 48px}
a{color:var(--acc)}h1,h2,h3{line-height:1.25}h2{border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:2em}
table{border-collapse:collapse;display:block;overflow-x:auto;max-width:100%;font-size:13px}
th,td{padding:5px 8px;border:1px solid var(--line);text-align:left}th{background:var(--code)}
code{background:var(--code);padding:1px 4px;border-radius:3px}pre{background:var(--code);padding:10px;overflow-x:auto}pre code{padding:0}
.mermaid{overflow-x:auto;text-align:center}
</style>
<nav><a href="index.html">Report</a><a href="explorer.html">Interactive explorer</a>
<a href="__GH__/results/benchmark.csv">Raw data (CSV)</a><a href="__GH__/script/README.md">Run or add a model</a></nav>
<main><div id="res">Loading report...</div><div id="md"></div></main>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<script>
const GH="__GH__",SRC=__MD__,RES=__RES__;
const el=document.getElementById("res"),doc=document.getElementById("md");
el.innerHTML="<h1>TokenFrugal benchmark results</h1>"+marked.parse(RES);
doc.innerHTML="<h2>About this benchmark</h2>"+marked.parse(SRC.replace(/^# .*\n/,""));
doc.querySelectorAll("a[href]").forEach(a=>{const h=a.getAttribute("href");if(h&&!/^(https?:|#|explorer\.html|index\.html)/.test(h))a.href=GH+"/"+h.replace(/^\.?\//,"")});
function dateFilter(){
 const t=[...el.querySelectorAll("table")].find(t=>[...t.querySelectorAll("th")].some(h=>h.textContent.trim()==="Date"));
 if(!t)return;
 const di=[...t.querySelectorAll("th")].findIndex(h=>h.textContent.trim()==="Date");
 const s=document.createElement("select");
 [["","all time"],["7","last 7 days"],["30","last 30 days"],["90","last 90 days"]].forEach(([v,l])=>s.add(new Option(l,v)));
 const lab=document.createElement("label");
 lab.style.cssText="display:inline-flex;gap:8px;align-items:center;font-size:13px;margin:8px 0";
 lab.append("Show runs from: ",s);
 t.parentElement.insertBefore(lab,t);
 const cutoff=n=>{const d=new Date();d.setDate(d.getDate()-n);return[d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-")};
 s.onchange=()=>{const n=+s.value,cut=n?cutoff(n):"";
  t.querySelectorAll("tbody tr").forEach(tr=>{const c=tr.cells[di],v=c?c.textContent.trim().slice(0,10):"";tr.hidden=!!(cut&&v&&v<cut)})};
}
try{dateFilter()}catch(e){}
el.querySelectorAll("pre code.language-mermaid").forEach(c=>{const d=document.createElement("div");d.className="mermaid";d.textContent=c.textContent;c.parentElement.replaceWith(d)});
el.querySelectorAll("a[href]").forEach(a=>{const h=a.getAttribute("href");if(h&&!/^(https?:|#|explorer\.html)/.test(h))a.href=GH+"/"+h.replace(/^\.?\//,"")});
mermaid.initialize({startOnLoad:false,theme:matchMedia("(prefers-color-scheme:dark)").matches?"dark":"default"});
mermaid.run({querySelector:".mermaid"});
</script>"""
(B / "index.html").write_text(
    PAGE.replace("__GH__", "https://github.com/maxh8086/tokenfrugal/blob/main/Benchmark")
        .replace("__MD__", json.dumps(p.read_text(encoding="utf-8")).replace("</", "<\\/"))
        .replace("__RES__", json.dumps(re.sub(r"<!--.*?-->", "", auto, flags=re.S)).replace("</", "<\\/")),
    encoding="utf-8")
print(f"updated explorer.html and index.html ({len(rows)} runs, {len(CASES)} cases)")
