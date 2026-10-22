"""Rebuild the generated parts of Benchmark/Benchmark.md and Benchmark/explorer.html from results/benchmark.csv.

    python Benchmark/script/build_report.py

Only the text between <!-- BEGIN:auto --> and <!-- END:auto --> in Benchmark.md is replaced; the
hand-written sections (conclusions, observations) are never touched.

Inputs: results/benchmark.csv plus results/cloud.csv (if present), merged into one list of runs.
Cloud rows (builder_model starting with `claude-`) live in cloud.csv, with the same header, so the
Haiku baseline stays intact unless a new cloud run is added there.
"""
import sys as _sys
for _s in (_sys.stdout, _sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
import csv, html, json, math, re
from pathlib import Path
import yaml
import argparse
import subprocess
import sys

_ap = argparse.ArgumentParser(description="Rebuild the benchmark report, optionally after a fresh run.")
_ap.add_argument("--run", nargs="*", metavar="MODEL", help="fresh benchmark run first; no names = every model already in benchmark.csv")
_ap.add_argument("--n", type=int, default=3, help="runs per model for --run")
_ap.add_argument("--update", choices=["ask", "yes", "no"], default="ask", help="update recommendations after the rebuild (default: ask)")
_args = _ap.parse_args()
_HERE = Path(__file__).resolve().parent
if _args.run is not None:
    _models = _args.run
    if not _models:
        _seen = {}
        for _r in csv.DictReader((_HERE.parent / "results" / "benchmark.csv").open(encoding="utf-8")):
            if not _r["builder_model"].startswith("claude-") and (_r.get("ran") or "0") not in ("", "0"):
                _seen[_r["builder_model"]] = 1
        _models = list(_seen)
    for _m in _models:
        print(f"fresh run: {_m} (n={_args.n})", flush=True)
        _rc = subprocess.run([sys.executable, str(_HERE / "run_benchmark.py"), _m, "--n", str(_args.n), "--tag", re.sub(r"[^a-z0-9]+", "-", _m.lower()).strip("-") + "-n" + str(_args.n)],
                             cwd=_HERE.parent.parent).returncode
        if _rc:
            raise SystemExit(f"run_benchmark failed for {_m} (exit {_rc}); report not rebuilt")

sys.path.insert(0, str(Path(__file__).resolve().parent))  # `python -I` drops the script dir from sys.path
from ranking import *  # noqa
if not ollama_up():
    print("WARNING: Ollama not reachable at localhost:11434; ts- origin rows will read 'Local build (source not recorded)'. Start Ollama and rerun.")
from ranking import B, cloud_reference, _status, _sort_role, _role_agg, _load, _local, _cands, _max_tps
AGENTS = B.parent / "router" / "tf-roles.yaml"


def role_rank(cases, top=5):
    """Every local model on one role's cases, compared across all its runs, with a status dot.
    The first `top` rows show by default; the rest sit in a collapsed <details> block."""
    ranked = _sort_role(_role_agg(cases))
    head = ["| | # | Model | Latest run | Runs | Score | % | Rank | Shared memory GB | s/case | t/s (info) |",
            "|:-:|--:|---|---|--:|--:|--:|--:|--:|--:|--:|"]

    def row(i, name, m):
        tps = f"{sum(m['t']) / len(m['t']):.1f}" if m["t"] else ""
        spc = f"{sum(m['s']) / len(m['s']):.1f}" if m["s"] else ""
        return (f"| {DOT[_status(m)]} | {i} | `{name}` | {m['d']} | {m['runs']} "
                f"| {m['a']}/{m['n']} | {round(100 * m['a'] / m['n'])} | {round(100 * m['score'])} | {m['shared']:g} | {spc} | {tps} |")

    o = head + [row(i, n, m) for i, (n, m) in enumerate(ranked[:top], 1)]
    ref = cloud_reference(cases)
    if ref:
        a, n = ref[1]["a"], ref[1]["n"]
        o.append(f"| ☁️ | ref | `{ref[0]}` (cloud reference, not ranked) | | | {a}/{n} | {round(100 * a / n)} | 100 | | | |")
    rest = ranked[top:]
    if rest:
        o += ["", f"<details><summary>Show the other {len(rest)} models</summary>", "", *head,
              *[row(i, n, m) for i, (n, m) in enumerate(rest, top + 1)], "", "</details>"]
    return "\n".join(o)


def role_text():
    """Preferred models per role, each with its status dot, plus the faster option (see role_pick)."""
    o = []
    for label, cases in (("Builder", BUILDER_CASES), ("Thinker", THINKER_CASES)):
        agg = _role_agg(cases)
        greens, fast, best = role_pick(cases)
        if not greens:
            o.append(f"- **{label}:** no model passes every case in every run without flags, so these are the best available:")
            for name in best:
                o.append(f"  - {DOT[_status(agg[name])]} `{name}` — pull: `{agg[name]['pull']}`")
            continue
        o.append(f"- **{label}:** {len(greens)} preferred choice{'s' if len(greens) > 1 else ''}:")
        for name in greens:
            o.append(f"  - {DOT['green']} `{name}` — pull: `{agg[name]['pull']}`")
        if fast:
            o.append(f"  - Faster option with the same pass rate: `{fast}` — pull: `{agg[fast]['pull']}`")
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
    """Role -> model class -> allowed tools, read from router/tf-roles.yaml so it cannot drift."""
    return yaml.safe_load(AGENTS.read_text(encoding="utf-8"))


_CFG = role_cfg()

LEGEND_MD = """- Each **run** is one local model setup, scored on the same 16 cases. `score` is passes out of `max`.
- **Builder** writes code and edits files. **Thinker** reads, analyses and browses. The models for each role are set in `router/tf-roles.yaml`. Context window per model follows the `num_ctx` policy in `Benchmark/README.md`.
- A task uses **one** model at a time. Models never run together or talk to each other.
- The role table shows which tools each role is allowed to call. A case needs the tools of its role.
- 🟩 all checks passed, 🟨 some passed, 🟥 none passed, `·` not run.
- ⚠ on a case that needs a specific tool means that run scored 0 on it, so the tool was likely missing or not called."""

auto = f"""<!-- BEGIN:auto -->
_{len(rows)} runs x {len(CASES)} cases, generated from `results/benchmark.csv` and `results/cloud.csv` by `script/build_report.py`._

### Ranking (fastest first, by seconds per case)

{RANK_LEGEND_MD}

{md_table()}
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


def _coding():
    """Latest coding (L1-L6, realworld) run per model from results/coding/*.json; a complete run beats a newer partial one."""
    latest = {}
    for p in sorted((B / "results" / "coding").glob("*.json")):
        m = re.match(r"\d{8}-\d{6}-(c\d+|t\d+)-coding-(.+)\.json$", p.name)
        if not m:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cases = d.get("results", {}).get("realworld", {})
        if not cases:
            continue
        slug = m.group(2)
        complete = len(cases) >= 6
        if slug in latest and latest[slug]["complete"] and not complete:
            continue
        ok = ran = 0
        means = []
        row = {"model": slug, "suite": m.group(1), "n": d.get("n"), "complete": complete, "cases": {}}
        for c, v in cases.items():
            a, _, b = str(v.get("verified", "0/0")).partition("/")
            ok += int(a or 0)
            ran += int(b or 0)
            row["cases"][c] = str(v.get("verified", ""))
            if (v.get("s") or {}).get("mean") is not None:
                means.append(v["s"]["mean"])
        row.update(ok=ok, ran=ran, pct=round(100 * ok / ran) if ran else None,
                   mean_s=round(sum(means) / len(means), 1) if means else None)
        latest[slug] = row
    return sorted(latest.values(), key=lambda r: r["model"])


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
html,body{overflow-anchor:none}.w{overflow-x:auto}.g{color:var(--acc)}.r{color:#d0453b}.y{color:#d9a021}.mut{color:var(--mut)}
details{margin:12px 0;font-size:13px}summary{cursor:pointer;font-weight:600}details ul{margin:8px 0 8px 18px;padding:0}
.cb{margin:16px 0}.cb h3{font-size:15px;margin:4px 0}.cb p{font-size:12px;margin:6px 0}
.row{display:flex;flex-wrap:wrap;gap:24px}.row>.cb{flex:1 1 320px;min-width:0}.pw{display:flex;flex-wrap:wrap;align-items:center;gap:16px}.pw svg{flex:0 0 220px;width:220px}.pl{font-size:12px;font-weight:600;fill:#fff;pointer-events:none}.lg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;margin:4px 0}.li{display:inline-flex;align-items:center;gap:5px}.li[data-sk]{cursor:pointer}.li i{width:11px;height:11px;border-radius:2px;display:inline-block}.chip{display:inline-block;margin-left:8px;padding:1px 8px;border:1px solid var(--line);border-radius:10px;font-size:12px;cursor:pointer}.ch svg{width:100%;height:auto;display:block}.ax{font-size:11px;fill:var(--mut)}.lb{font-size:10px;fill:var(--fg)}
</style>
<h1>Benchmark explorer</h1>
<p><a href="index.html">Back to the report</a></p>
<details><summary>Role definitions and legend</summary>__ROLES__</details>
<details open id="fm" class="cb"><summary>Find my model</summary>
<p class="mut">Pick your GPU memory, the job and how much you value speed. Only runs measured on matching hardware count (so far: RTX 4060 Laptop 8 GB).</p>
<div class="f">
<label>Hardware<select id="fh"><option value="">(any measured)</option></select></label>
<label>GPU memory GB (model file must fit)<input id="fv" type="number" min="1" step="0.5" placeholder="any"></label>
<label>Role<select id="fr"><option value="">Overall</option><option value="builder_score">Builder (code, edits)</option><option value="thinker_score">Thinker (analysis)</option></select></label>
<label>Priority: <span id="fwl">40% speed / 60% accuracy</span><input id="fw" type="range" min="0" max="100" value="40"></label>
</div>
<div id="fo"></div></details>
<div class="f">
<label>Min score %<input id="ms" type="number" placeholder="any" min="0" max="100"></label>
<label>Max s/case<input id="mt" type="number" placeholder="any"></label>
<label>Max params (B)<input id="mp" type="number" placeholder="any"></label>
<label>Name contains<input id="q"></label>
<label>Must pass case<select id="cs"><option value="">(any)</option></select></label>
<label>From date<input id="fd" type="date"></label>
<label>Show<select id="lim"><option value="10" selected>Top 10 by Rank</option><option value="25">Top 25</option><option value="50">Top 50</option><option value="">All runs</option></select></label>
</div>
<div id="n"></div>
<div class="w"><table id="t"></table></div>
<details open><summary>Charts (linked to the filters and table)</summary><div id="ch" class="ch"></div></details>
<details open id="cdx"><summary>Coding (L1–L6, realworld suite)</summary><p class="mut">Separate suite from the table above: runs live in <code>results/coding/</code> and are not merged into benchmark.csv. Latest complete run per model; partial runs are marked.</p><div id="cd"></div></details>
<script>
const D=__DATA__,C=__CASES__,REQ=__REQ__,CD=__CODING__;let sk="composite",sd=-1;
const $=i=>document.getElementById(i);
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"})[c]);
const short=(s,n)=>s.length>n?s.slice(0,n-1)+"…":s;
const sn=m=>{m=m.replace(/^hf\.co\//,"").replace(/^[^\/]+\//,"").replace(/-GGUF/i,"").replace(/:/," ");return m};
C.forEach(c=>$("cs").add(new Option(c,c)));
const frac=(r,c)=>{try{const[a,n]=r[c].split("/");return a/n}catch(e){return null}};
const cols=[["builder_model","Model"],["day","Date","Day the run was made (YYYY-MM-DD)"],["source","Origin"],["pull","Pull command"],["params_b","Params (B)","Parameter count in billions, from the params column (blank = unknown)"],["pct","Pass rate %","Score as a percentage of the max checks (higher is better)"],["score","Score"],["builder_score","Builder"],["thinker_score","Thinker"],["tps","t/s (info)","Tokens per second, for information only (rewards verbose models)"],["composite","Rank","Rank = 100 x (60% pass rate + 40% speed, speed = seconds per case on a log scale between the fastest and slowest full run); higher is better, and the post pick uses the same score"],["mean_s_per_case","s per case","Mean seconds per case (lower is faster; primary speed metric)"],["total_s","Run time (s)","Wall clock seconds for the whole run"],...C.map(c=>[c,c])];
const wrap=(svg,n)=>`<div style="${n>30?"max-height:560px;overflow-y:auto":""}">${svg}</div>`;
const SEL={band:null,model:null};
const BANDS=[["90-100% (excellent)",90,101,"#2e9e5b"],["75-89% (good)",75,90,"#8bc34a"],["50-74% (fair)",50,75,"#d9a021"],["Below 50% (poor)",0,50,"#d0453b"]];
const bandOf=r=>BANDS.findIndex(b=>r.pct>=b[1]&&r.pct<b[2]);
const dim=(k,v)=>SEL[k]!=null&&SEL[k]!==v?";opacity:.3":"";
const sub=(r,k)=>{const m=/^(\d+)\/(\d+)$/.exec(r[k]||"");return m&&+m[2]?100*m[1]/m[2]:null};
const box=(h,body,foot)=>`<div class="cb"><h3>${h}</h3>${body}<p class="mut">${foot}</p></div>`;
const none="<p class=\"mut\">No runs match.</p>";
const grid=(L,PW,T,H,AX)=>[0,25,50,75,100].map(v=>`<line x1="${L+PW*v/100}" x2="${L+PW*v/100}" y1="${T}" y2="${H-AX}" style="stroke:var(--line)"/><text x="${L+PW*v/100}" y="${H-AX+14}" text-anchor="middle" class="ax">${v}%</text>`).join("");
const titles=(L,PW,T,H,AX,xt,yt)=>`<text x="${L+PW/2}" y="${H-6}" text-anchor="middle" class="ax">${xt}</text><text transform="translate(10 ${(T+H-AX)/2}) rotate(-90)" text-anchor="middle" class="ax">${yt}</text>`;
function legend(items){return`<div class="lg">`+items.map(i=>`<span class="li"${i.k?` data-sk="${i.k}" data-sv="${esc(i.v)}"`:""} style="${i.k&&SEL[i.k]!=null&&SEL[i.k]!==i.v?"opacity:.4":""}"><i style="background:${i.c}"></i>${esc(i.t)}</span>`).join("")+`</div>`}
function pie(R){
 if(!R.length)return none;
 const cnt=BANDS.map((b,i)=>R.filter(r=>bandOf(r)===i).length),tot=R.length,cx=110,cy=110,rad=90;
 let a0=-Math.PI/2,g="";
 cnt.forEach((n,i)=>{if(!n)return;const a1=a0+2*Math.PI*n/tot,mid=(a0+a1)/2,sel=SEL.band===i,ox=sel?8*Math.cos(mid):0,oy=sel?8*Math.sin(mid):0;
  const t=`${BANDS[i][0]}: ${n} run${n>1?"s":""} (${Math.round(100*n/tot)}%). Click to filter.`;
  const d=n===tot?`<circle cx="${cx}" cy="${cy}" r="${rad}"`:`<path d="M${cx+ox} ${cy+oy}L${cx+ox+rad*Math.cos(a0)} ${cy+oy+rad*Math.sin(a0)}A${rad} ${rad} 0 ${a1-a0>Math.PI?1:0} 1 ${cx+ox+rad*Math.cos(a1)} ${cy+oy+rad*Math.sin(a1)}Z"`;
  g+=`${d} data-sk="band" data-sv="${i}" style="fill:${BANDS[i][3]};stroke:var(--bg);stroke-width:2;cursor:pointer${dim("band",i)}"><title>${esc(t)}</title>${n===tot?"</circle>":"</path>"}`;
  if(n/tot>.06)g+=`<text x="${cx+ox+.6*rad*Math.cos(mid)}" y="${cy+oy+.6*rad*Math.sin(mid)+4}" text-anchor="middle" class="pl">${n}</text>`;a0=a1});
 return`<div class="pw"><svg viewBox="0 0 220 220" role="img" aria-label="Runs by score band">${g}</svg>`
  +legend(BANDS.map((b,i)=>({k:"band",v:i,c:b[3],t:`${b[0]}: ${cnt[i]}`})))+`</div>`}
function passChart(R){
 const S=[...R].sort((a,b)=>b.pct-a.pct);
 if(!S.length)return none;
 const L=230,W=680,RH=20,T=6,AX=40,PW=W-L-50,H=T+S.length*RH+AX;
 let g=grid(L,PW,T,H,AX);
 S.forEach((r,i)=>{const y=T+i*RH,m=r.builder_model;
  g+=`<g data-sk="model" data-sv="${esc(m)}" style="cursor:pointer${dim("model",m)}"><text x="${L-6}" y="${y+14}" text-anchor="end" class="lb">${esc(short(sn(m),34))}</text>`
   +`<rect x="${L}" y="${y+3}" width="${PW*r.pct/100}" height="${RH-6}" style="fill:${BANDS[bandOf(r)][3]}"><title>${esc(m+" | "+r.pct+"% | click to filter")}</title></rect>`
   +`<text x="${L+PW*r.pct/100+4}" y="${y+14}" class="lb">${r.pct}%</text></g>`});
 g+=titles(L,PW,T,H,AX,"Pass rate % (higher is better)","Run (model)");
 return legend(BANDS.map(b=>({c:b[3],t:b[0]})))+wrap(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pass rate by run">${g}</svg>`,S.length);
}
function roleChart(R){
 const S=[...R].sort((a,b)=>b.pct-a.pct).slice(0,12);
 if(!S.length)return none;
 const L=230,W=680,RH=30,T=6,AX=40,PW=W-L-50,H=T+S.length*RH+AX;
 let g=grid(L,PW,T,H,AX);
 S.forEach((r,i)=>{const y=T+i*RH,m=r.builder_model;
  g+=`<g data-sk="model" data-sv="${esc(m)}" style="cursor:pointer${dim("model",m)}"><text x="${L-6}" y="${y+17}" text-anchor="end" class="lb">${esc(short(sn(m),34))}</text>`;
  [["builder_score","#3b82f6","Builder"],["thinker_score","#f97316","Thinker"]].forEach(([k,c,n],j)=>{const v=sub(r,k);
   if(v!=null)g+=`<rect x="${L}" y="${y+2+j*12}" width="${PW*v/100}" height="10" style="fill:${c}"><title>${esc(m+" | "+n+" "+r[k]+" ("+Math.round(v)+"%)")}</title></rect><text x="${L+PW*v/100+4}" y="${y+11+j*12}" class="lb">${Math.round(v)}%</text>`});
  g+="</g>"});
 g+=titles(L,PW,T,H,AX,"Role pass rate % (share of that role's checks passed)","Run (model)");
 return legend([{c:"#3b82f6",t:"Builder (code, file edits)"},{c:"#f97316",t:"Thinker (read, analyse, browse)"}])+wrap(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Builder vs thinker">${g}</svg>`,S.length);
}
function caseChart(R){
 if(!R.length)return none;
 const A=C.map(c=>{const v=R.map(r=>frac(r,c)).filter(x=>x!=null&&isFinite(x));return[c,v.length?100*v.reduce((x,y)=>x+y)/v.length:0]}).sort((x,y)=>x[1]-y[1]);
 const L=190,W=680,RH=20,T=6,AX=40,PW=W-L-50,H=T+A.length*RH+AX,cur=$("cs").value;
 let g=grid(L,PW,T,H,AX);
 A.forEach(([c,v],i)=>{const y=T+i*RH,col=v>=75?"#2e9e5b":v>=40?"#d9a021":"#d0453b";
  g+=`<g data-sk="case" data-sv="${esc(c)}" style="cursor:pointer;${cur&&cur!==c?"opacity:.3":""}"><text x="${L-6}" y="${y+14}" text-anchor="end" class="lb">${esc(c)}${REQ.includes(c)?" ⚠":""}</text><rect x="${L}" y="${y+3}" width="${PW*v/100}" height="${RH-6}" style="fill:${col}"><title>${esc(c+": "+Math.round(v)+"% average pass. Click to require this case.")}</title></rect><text x="${L+PW*v/100+4}" y="${y+14}" class="lb">${Math.round(v)}%</text></g>`});
 g+=titles(L,PW,T,H,AX,"Average pass rate % across the runs shown","Benchmark case");
 return legend([{c:"#2e9e5b",t:"75%+ easy"},{c:"#d9a021",t:"40-74% mixed"},{c:"#d0453b",t:"under 40% hard"}])+wrap(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Pass rate per case">${g}</svg>`,A.length);
}
function scatter(P,xf,xt,xmax,rf,leg,label,yf=r=>r.pct,yt="Pass rate %, higher = better"){
 const W=680,H=360,L=52,RT=20,T=14,AX=44;
 const X=v=>L+(W-L-RT)*v/xmax,Y=v=>T+(H-T-AX)*(1-v/100);let g="";
 [0,25,50,75,100].forEach(v=>{g+=`<line x1="${L}" x2="${W-RT}" y1="${Y(v)}" y2="${Y(v)}" style="stroke:var(--line)"/><text x="${L-6}" y="${Y(v)+4}" text-anchor="end" class="ax">${v}</text>`});
 for(let k=0;k<=5;k++){const v=xmax*k/5;g+=`<line x1="${X(v)}" x2="${X(v)}" y1="${T}" y2="${H-AX}" style="stroke:var(--line)"/><text x="${X(v)}" y="${H-AX+14}" text-anchor="middle" class="ax">${+v.toFixed(1)}</text>`}
 g+=`<text x="${(L+W-RT)/2}" y="${H-6}" text-anchor="middle" class="ax">${xt}</text><text transform="translate(14 ${(T+H-AX)/2}) rotate(-90)" text-anchor="middle" class="ax">${yt}</text>`;
 P.forEach(r=>{const m=r.builder_model,x=X(xf(r)),y=Y(yf(r)),rad=rf(r),f=leg(r);
  g+=`<g data-sk="model" data-sv="${esc(m)}" style="cursor:pointer${dim("model",m)}"><circle cx="${x}" cy="${y}" r="${rad}" style="fill:${f};fill-opacity:.8"><title>${esc(sn(m)+" ("+m+") | score "+r.score+"/"+r.max+" ("+r.pct+"%) | "+(r.tps==null?"t/s n/a":r.tps+" t/s")+" | "+r.mean_s_per_case+" s/case | params "+(r.params||"unknown")+" | click to filter")}</title></circle></g>`});
 return wrap(`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${label}">${g}</svg>`,P.length);
}
const sizeNone=what=>`<p class="mut">${SEL.model!=null?`<b>${esc(SEL.model)}</b> has no parameter count, so it cannot be placed on this chart. `:""}No ${what} match the current filters. Cloud runs have no parameter count, so they never plot here.${SEL.model!=null||SEL.band!=null?` <span class="chip" data-sk="clear">Clear chart selections</span>`:""}</p>`;
function sizeChart(R){
 const P=R.filter(r=>r.params_b!=null&&!isNaN(r.params_b));
 if(!P.length)return sizeNone("local runs with a known size");
 const xmax=Math.max(4,Math.ceil(Math.max(...D.filter(r=>r.params_b!=null&&!isNaN(r.params_b)).map(r=>r.params_b))/4)*4);
 return legend(BANDS.map(b=>({c:b[3],t:b[0]})))+scatter(P,r=>r.params_b,"Model size, billions of parameters",xmax,()=>7,r=>BANDS[bandOf(r)][3],"Size vs pass rate");
}
function sizeRankChart(R){
 const P=R.filter(r=>r.params_b!=null&&!isNaN(r.params_b)&&r.composite!=null);
 if(!P.length)return sizeNone("local runs with a known size and a rank");
 const xmax=Math.max(4,Math.ceil(Math.max(...D.filter(r=>r.params_b!=null&&!isNaN(r.params_b)).map(r=>r.params_b))/4)*4);
 return legend(BANDS.map(b=>({c:b[3],t:b[0]})))+scatter(P,r=>r.params_b,"Model size, billions of parameters",xmax,()=>7,r=>BANDS[bandOf(r)][3],"Size vs rank",r=>r.composite*100,"Rank, higher = better");
}

function findModel(){
 const hw=$("fh").value,vr=+$("fv").value||1e9,role=$("fr").value,w=+$("fw").value/100;
 $("fwl").textContent=Math.round(100*w)+"% speed / "+Math.round(100*(1-w))+"% accuracy";
 const L=D.filter(r=>!r.builder_model.startsWith("claude-")&&+r.mean_s_per_case>0&&(!hw||r.hardware_id===hw)&&(!(+r.model_file_size_gb>0)||+r.model_file_size_gb<=vr)&&(vr>=1e9||+r.model_file_size_gb>0));
 const by={};L.forEach(r=>{const v=role?sub(r,role):r.pct;if(v==null)return;(by[r.builder_model]=by[r.builder_model]||[]).push({r,v})});
 const A=Object.entries(by).map(([m,a])=>{const n=a.length,pct=a.reduce((x,y)=>x+y.v,0)/n,s=a.reduce((x,y)=>x+ +y.r.mean_s_per_case,0)/n;
  return{builder_model:m,pct:Math.round(pct*10)/10,mean_s_per_case:Math.round(s*10)/10,score:"",max:"",tps:null,params:a[0].r.params,params_b:a[0].r.params_b,gb:a[0].r.model_file_size_gb,n}});
 if(!A.length){$("fo").innerHTML=none;return}
 const ss=A.map(a=>a.mean_s_per_case),hi=Math.max(...ss),lo=Math.min(...ss);
 A.forEach(a=>{a.speed=hi>lo?Math.log(hi/a.mean_s_per_case)/Math.log(hi/lo):1;a.fit=100*((1-w)*a.pct/100+w*a.speed)});
 A.sort((a,b)=>b.fit-a.fit||b.pct-a.pct);
 const front=A.filter(a=>!A.some(b=>b!==a&&b.pct>=a.pct&&b.mean_s_per_case<=a.mean_s_per_case&&(b.pct>a.pct||b.mean_s_per_case<a.mean_s_per_case)));
 const top=A.slice(0,3).map((a,i)=>`<tr><td>${i+1}</td><td title="${esc(a.builder_model)}"><b>${esc(sn(a.builder_model))}</b></td><td>${a.pct}%</td><td>${a.mean_s_per_case} s</td><td>${a.gb||"·"} GB</td><td>${a.fit.toFixed(1)}</td></tr>`).join("");
 const xmax=Math.max(10,Math.ceil(hi/10)*10);
 $("fo").innerHTML=`<div class="w"><table><tr><th>#</th><th>Model</th><th>Pass rate</th><th>Per case</th><th>File size</th><th>Fit score</th></tr>${top}</table></div>`
  +legend([{c:"var(--acc)",t:"Candidate"},{c:"#2e7de0",t:"Pareto front (nothing is both faster and more accurate)"}])
  +scatter(A,r=>r.mean_s_per_case,"Seconds per case, lower = faster",xmax,r=>front.includes(r)?9:6,r=>front.includes(r)?"#2e7de0":"var(--acc)","Pareto chart")
  +`<p class="mut">${A.length} models qualify (${L.length} runs). Fit score = accuracy and log-scaled speed mixed by the priority slider.</p>`;
}
[...new Set(D.map(r=>r.hardware_id).filter(Boolean))].forEach(h=>$("fh").add(new Option(h,h)));
["fh","fv","fr","fw"].forEach(i=>$(i).addEventListener("input",findModel));
function draw(){
 findModel();
 const q=$("q").value.toLowerCase(),ms=+$("ms").value,mt=+$("mt").value||1e9,mp=+$("mp").value||1e9,cs=$("cs").value,fd=$("fd").value,lim=+$("lim").value||1e9;
 const R0=D.filter(r=>r.builder_model.startsWith("claude-")||(r.pct>=ms&&+r.mean_s_per_case<=mt&&(mp>=1e9||(r.params_b==null?r.builder_model.startsWith("claude-"):r.params_b<=mp))&&(r.builder_model+r.source).toLowerCase().includes(q)&&(!cs||frac(r,cs)===1)&&(!fd||r.day>=fd)));
 const R1=R0.filter(r=>SEL.model==null||r.builder_model===SEL.model),R2=R1.filter(r=>SEL.band==null||bandOf(r)===SEL.band);
 R2.sort((a,b)=>{let x=a[sk],y=b[sk];x=isNaN(+x)?x:+x;y=isNaN(+y)?y:+y;let c=(x>y?1:x<y?-1:0)*sd;if(c==0&&sk=="composite")c=(b.pct-a.pct);return c});
 R2.sort((a,b)=>b.builder_model.startsWith("claude-")-a.builder_model.startsWith("claude-"));
 const R=R2.filter((r,i)=>i<lim||r.builder_model.startsWith("claude-"));
 const chips=(SEL.band!=null?`<span class="chip" data-sk="band" data-sv="${SEL.band}">Score band: ${esc(BANDS[SEL.band][0])} ✕</span>`:"")+(SEL.model!=null?`<span class="chip" data-sk="model" data-sv="${esc(SEL.model)}">Model: ${esc(sn(SEL.model))} ✕</span>`:"")+(cs?`<span class="chip" data-sk="case" data-sv="${esc(cs)}">Case: ${esc(cs)} ✕</span>`:"");
 $("n").innerHTML=R2.length+" of "+D.length+" runs match"+(R.length<R2.length?` (showing top ${R.length} by ${sk=="composite"?"Rank":sk})`:"")+chips+(SEL.band!=null||SEL.model!=null?`<span class="chip" data-sk="clear">Clear chart selections</span>`:"");
 $("ch").innerHTML=`<p class="mut">Click a pie slice, bar, dot or case to filter the table and every chart; click again to undo. The filter fields above update every chart too.</p>`
  +`<div class="row">`+box("Runs by score band",pie(R1),"Pie: share of runs per pass-rate band, after the filters above. Click a slice or legend entry to show only those runs.")+`</div>`
  +box("Model comparison: pass rate by run",passChart(R),"One horizontal bar per run, colored by score band. Click a bar to focus that model.")
  +box("Builder vs thinker by run",roleChart(R),"Top 12 runs by pass rate. Blue = builder cases, orange = thinker cases. Click to focus a model.")
  +box("Model size vs pass rate",sizeChart(R2),"Does a bigger model score higher? Local runs with a known size only (all runs matching the filters, not just the top-N table rows). Click a dot to focus a model.")
  +box("Model size vs rank",sizeRankChart(R2),"Rank (60% pass rate, 40% speed) against parameter count. Local runs with a known size and a rank only. Click a dot to focus a model.");
 $("t").innerHTML="<tr>"+cols.map(c=>`<th data-k="${c[0]}"${c[2]?` title="${esc(c[2])}"`:""}>${c[1].replace(/_/g," ")}</th>`).join("")+"</tr>"+
  R.map(r=>"<tr>"+cols.map(([k])=>{
   if(k=="pct")return`<td><span class="bar" style="width:${r.pct*.6}px"></span>${r.pct}</td>`;
   if(C.includes(k)){const p=frac(r,k);const w=(p===0&&REQ.includes(k))?" ⚠":"";return`<td class="${p==null?"":p==1?"g":p==0?"r":"y"}">${r[k]||"·"}${w}</td>`}
   if(k=="params_b")return`<td>${r.params_b==null?"·":r.params_b}</td>`;
   if(k=="composite")return`<td>${r.composite==null?"":(r.composite*100).toFixed(1)}</td>`;
   if(k=="builder_model")return`<td title="${esc(r[k])}">${esc(sn(r[k]))}</td>`;return`<td>${r[k]}</td>`}).join("")+"</tr>").join("");
 document.querySelectorAll("th").forEach(h=>h.onclick=()=>{sd=sk==h.dataset.k?-sd:-1;sk=h.dataset.k;draw()});
}
const pick=e=>{const t=e.target.closest("[data-sk]");if(!t)return;const k=t.dataset.sk,v=t.dataset.sv;
 if(k==="clear"){SEL.band=SEL.model=null}
 else if(k==="case")$("cs").value=$("cs").value===v?"":v;
 else if(k==="band")SEL.band=SEL.band===+v?null:+v;
 else SEL.model=SEL.model===v?null:v;
 draw();toTop();requestAnimationFrame(toTop)};
// Inside the dashboard the explorer is an auto-sized iframe (scrolling="no"), so scroll the host page to the frame's top instead
const toTop=()=>{const f=window.frameElement;if(!f){window.scrollTo(0,0);return}const p=window.parent;p.scrollTo(0,Math.max(0,p.scrollY+f.getBoundingClientRect().top-8))};
$("ch").addEventListener("click",pick);$("n").addEventListener("click",pick);
function renderCoding(){
 if(!CD.length){$("cd").innerHTML='<p class="mut">No coding runs yet.</p>';return}
 const cols=[...new Set(CD.flatMap(r=>Object.keys(r.cases)))].sort();
 const lab=c=>(c.split("_")[1]||c).toUpperCase();
 const rows=[...CD].sort((a,b)=>(b.pct??-1)-(a.pct??-1)||(a.mean_s??1e9)-(b.mean_s??1e9));
 const tbl=`<div class="w"><table><tr><th>Model</th><th>Suite</th><th>Runs</th><th>Passed</th><th>Pass rate</th><th>Mean s/case</th>${cols.map(c=>`<th title="${esc(c)}">${lab(c)}</th>`).join("")}</tr>`
  +rows.map(r=>`<tr><td title="${esc(r.model)}"><b>${esc(sn(r.model))}</b>${r.complete?"":" <i>(partial)</i>"}</td><td>${esc(r.suite)}</td><td>${r.n==null?"·":r.n}</td><td>${r.ok}/${r.ran}</td><td>${r.pct==null?"·":r.pct+"%"}</td><td>${r.mean_s==null?"·":r.mean_s+" s"}</td>`
  +cols.map(c=>{const v=r.cases[c]||"";const [a,b]=v.split("/").map(Number);const cls=!b?"":a===b?"g":a===0?"r":"y";return`<td class="${cls}">${v||"·"}</td>`}).join("")+"</tr>").join("")+"</table></div>";
 const bars=rows.map(r=>`<div><span title="${esc(r.model)}">${esc(short(sn(r.model),40))}</span> <span class="bar" style="width:${(r.pct||0)*3}px"></span> ${r.pct==null?"·":r.pct+"%"}</div>`).join("");
 $("cd").innerHTML=tbl+box("Coding pass rate by model",bars,"Share of coding verifications passed across the L1–L6 cases, latest complete run per model.");
}
renderCoding();
document.querySelectorAll("input,select").forEach(e=>e.oninput=draw);draw();
</script>"""
(B / "explorer.html").write_text(
    HTML.replace("__ROLES__", legend_html() + roles_html())
        .replace("__DATA__", json.dumps(rows))
        .replace("__CASES__", json.dumps(CASES))
        .replace("__REQ__", json.dumps(list(REQUIRED_TOOL_CASES)))
        .replace("__CODING__", json.dumps(_coding())),
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
const GH="__GH__",SRC=__MD__,RES=__RES__,D=__DATA__,BC=__BC__,TC=__TC__;
const el=document.getElementById("res"),doc=document.getElementById("md");
el.innerHTML="<h1>TokenFrugal benchmark results</h1>"+marked.parse(RES);
doc.innerHTML="<h2>About this benchmark</h2>"+marked.parse(SRC.replace(/^# .*\n/,""));
doc.querySelectorAll("a[href]").forEach(a=>{const h=a.getAttribute("href");if(h&&!/^(https?:|#|explorer\.html|index\.html)/.test(h))a.href=GH+"/"+h.replace(/^\.?\//,"")});
{const loc=/^(localhost|127\.|\[::1\]|)$/.test(location.hostname),u=loc?"https://maxh8086.github.io/tokenfrugal/Benchmark/":location.href.split("#")[0],t="🚀💥 Boom! My model just took on the TokenFrugal Benchmark! 🧠🔥\n\nTry your own model using https://github.com/maxh8086/tokenfrugal shared by @vpavtekar. Share me your results below so we can see how different hardware performs!\n#LocalLLM #Ollama #TokenFrugal",e=encodeURIComponent,
x="https://twitter.com/intent/tweet?text="+e(t)+"&url="+e(u),l="https://www.linkedin.com/sharing/share-offsite/?url="+e(u);
doc.insertAdjacentHTML("beforeend","<h2>Share with friends</h2><p><a id=lnk href=\""+l+"\" target=_blank rel=noopener>Share on LinkedIn</a> | <a href=\""+x+"\" target=_blank rel=noopener>Share on X</a> | <a href=\"https://github.com/maxh8086/tokenfrugal\" target=_blank rel=noopener>GitHub repo</a></p>");const k=doc.querySelector("#lnk");if(k)k.onclick=ev=>{ev.preventDefault();window.open("/post.html","_blank","noopener")}}
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cnt=(r,cs)=>{let a=0,n=0;cs.forEach(c=>{const m=/^(\d+)\/(\d+)$/.exec(r.cases[c]||"");if(m){a+=+m[1];n+=+m[2]}});return[a,n]};
const frac=(r,cs)=>{const[a,n]=cnt(r,cs);return n?a/n:-1};
const sub=(r,cs)=>{const[a,n]=cnt(r,cs);return n?a+"/"+n:"·"};
const tie=(x,y)=>(y.pct-x.pct)||((x.s||1e9)-(y.s||1e9));
const mmss=t=>t?Math.floor(t/60)+":"+String(Math.round(t%60)).padStart(2,"0"):"";
const mark=(r,c)=>{const m=/^(\d+)\/(\d+)$/.exec(r.cases[c]||"");if(!m)return"·";const f=+m[1]/+m[2];let s=f===1?"🟩":f>0?"🟨":"🟥";if(f===0&&r.req.includes(c))s+="⚠";return s};
const S={sort:{},f:{}};
const DEF={rank:"10",rb:"5",rt:"5",hc:"10"};
const TOPS={rank:[5,10,20,0],rb:[3,5,10,0],rt:[3,5,10,0],hc:[5,10,20,0]};
function bar(id){
 const f=S.f[id]={q:"",size:"",days:"",top:DEF[id]};
 const b=$(id+"-bar");
 b.style.cssText="display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:13px;margin:8px 0";
 b.innerHTML=`<label>Model name <input data-f="q" placeholder="e.g. qwen, gemma" style="width:140px"></label>
 <label>Size <select data-f="size"><option value="">any</option><option value="4">up to 4B</option><option value="8">up to 8B</option><option value="14">up to 14B</option><option value="40">up to 40B</option></select></label>
 <label>Runs from <select data-f="days"><option value="">all time</option><option value="7">last 7 days</option><option value="30">last 30 days</option><option value="90">last 90 days</option></select></label>
 <label>Show <select data-f="top">${TOPS[id].map(n=>`<option value="${n}"${String(n)===DEF[id]?" selected":""}>${n?"top "+n:"all"}</option>`).join("")}</select></label>
 <button type="button">Reset</button><span data-f="c" style="color:var(--mut)"></span>`;
 const go=()=>{b.querySelectorAll("[data-f]").forEach(e=>{if(e.dataset.f!=="c")f[e.dataset.f]=e.value.trim().toLowerCase()});draw(id)};
 b.querySelectorAll("input").forEach(e=>e.addEventListener("input",go));
 b.querySelectorAll("select").forEach(e=>e.addEventListener("change",go));
 b.querySelector("button").onclick=()=>{b.querySelectorAll("input").forEach(e=>e.value="");b.querySelectorAll("select").forEach(e=>e.value=e.dataset.f==="top"?DEF[id]:"");go()};
}
function cutoff(n){const d=new Date();d.setDate(d.getDate()-n);return[d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-")}
function table(id,cols,rows,key){
 const[k,dir]=S.sort[key]||[null,0],c=cols.find(c=>c.k===k);
 if(c&&c.v)rows=[...rows].sort((x,y)=>{const a=c.v(x),b=c.v(y);return(a<b?-1:a>b?1:0)*dir||tie(x,y)});
 return rows;
}
function render(id,cols,rows,key){
 const[k,dir]=S.sort[key]||[null,0];
 const h=cols.map(c=>`<th data-k="${c.k}"${c.v?' style="cursor:pointer"':""}>${c.l}${c.k===k?(dir<0?" ▼":" ▲"):""}</th>`).join("");
 const b=rows.map((r,i)=>"<tr>"+cols.map(c=>`<td>${c.f(r,i)}</td>`).join("")+"</tr>").join("");
 $(id).innerHTML=`<table><thead><tr>${h}</tr></thead><tbody>${b}</tbody></table>`;
 $(id).querySelectorAll("th[data-k]").forEach(t=>t.onclick=()=>{const c=cols.find(c=>c.k===t.dataset.k);if(!c.v)return;
  const[k0,d0]=S.sort[key]||[];S.sort[key]=[c.k,k0===c.k?-d0:(c.str?1:-1)];draw(id)});
}
const code=s=>"<code>"+esc(s)+"</code>";
function sel(id){const f=S.f[id];
 const R=D.filter(r=>r.model.startsWith("claude-")||((!f.q||r.model.toLowerCase().includes(f.q))&&(!f.size||(r.pb!=null&&r.pb<=+f.size))&&(!f.days||!r.day||r.day>=cutoff(+f.days))));
 R.sort(id==="rank"?(x,y)=>((y.comp??-1)-(x.comp??-1))||tie(x,y):tie);R.sort((x,y)=>y.model.startsWith("claude-")-x.model.startsWith("claude-"));return R}
// Cloud baseline rows are always kept; "Show top N" counts local rows only.
function topN(V,n,k){let c=0;return n?V.filter(x=>k(x).startsWith("claude-")||c++<n):V}
function note(id,shown,total,what){$(id+"-bar").querySelector('[data-f="c"]').textContent=`Showing ${shown} of ${total} ${what}`}
function draw(id){
 const R=sel(id),top=+S.f[id].top;
 if(id==="rank"){
  const cols=[{k:"n",l:"#",f:(r,i)=>i+1},
   {k:"model",l:"Model",str:1,v:r=>r.model.toLowerCase(),f:r=>code(r.model)+(r.infra>0?" ⚠infra":"")},
   {k:"day",l:"Date",str:1,v:r=>r.day,f:r=>r.day},
   {k:"pb",l:"Params",v:r=>r.pb==null?-1:r.pb,f:r=>esc(r.params)},
   {k:"score",l:"Score",v:r=>r.score,f:r=>r.score+"/"+r.max},
   {k:"pct",l:"Pass rate %",v:r=>r.pct,f:r=>r.pct},
   {k:"b",l:"Builder",v:r=>frac(r,BC),f:r=>sub(r,BC)},
   {k:"t",l:"Thinker",v:r=>frac(r,TC),f:r=>sub(r,TC)},
   {k:"tps",l:"t/s (info)",v:r=>r.tps||-1,f:r=>r.tps??""},
   {k:"comp",l:"Rank",v:r=>r.comp??-1,f:r=>r.comp==null?"":(r.comp*100).toFixed(1),t:"Rank = 100 x (60% pass rate + 40% speed, speed = log-scaled seconds per case); higher is better, and the post pick uses the same score"},
   {k:"s",l:"s per case",v:r=>r.s||1e9,f:r=>r.s||""},
   {k:"tot",l:"Run time",v:r=>r.tot||1e9,f:r=>mmss(r.tot)},
   {k:"valid",l:"Valid cases",v:r=>+r.valid||0,f:r=>r.valid||""}];
  let V=table(id,cols,R,"rank");V=topN(V,top,r=>r.model);
  render(id,cols,V,"rank");note(id,V.length,R.length,"runs");
 }else if(id==="rb"||id==="rt"){
  const cs=id==="rb"?BC:TC;
  const agg={};
  R.forEach(r=>{const[a,n]=cnt(r,cs);if(!n||r.model.startsWith("claude-"))return;
   const m=agg[r.model]||(agg[r.model]={model:r.model,a:0,n:0,runs:0,ss:[],day:r.day,h:new Set,r});
   m.a+=a;m.n+=n;m.runs++;if(r.day>m.day)m.day=r.day;m.h.add(r.harness);if(r.s)m.ss.push(r.s)});
  const L=Object.values(agg).map(m=>({...m,pct:Math.round(100*m.a/m.n),s:m.ss.length?m.ss.reduce((x,y)=>x+y)/m.ss.length:0}));
  L.sort((x,y)=>(y.a/y.n-x.a/x.n)||(y.n-x.n)||((x.s||1e9)-(y.s||1e9)));
  const rc=[{k:"n",l:"#",f:(m,i)=>i+1},
   {k:"model",l:"Model",str:1,v:m=>m.model.toLowerCase(),f:m=>code(m.model)},
   {k:"day",l:"Date",str:1,v:m=>m.day,f:m=>m.day},
   {k:"h",l:"Harness",f:m=>[...m.h].filter(Boolean).join(", ")||"-"},
   {k:"a",l:"Score",v:m=>m.a/m.n,f:m=>m.a+"/"+m.n},
   {k:"pct",l:"%",v:m=>m.pct,f:m=>m.pct},
   {k:"runs",l:"Runs",v:m=>m.runs,f:m=>m.runs},
   {k:"tps",l:"t/s (info)",v:m=>m.tps||-1,f:m=>m.tps==null?"":m.tps.toFixed(1)},
   {k:"s",l:"s/case",v:m=>m.s||1e9,f:m=>m.s?m.s.toFixed(1):""},
   {k:"sh",l:"Shared memory GB",f:m=>m.r.shared||""}];
  const[k,d]=S.sort[id]||[],c=rc.find(c=>c.k===k);
  let V=c&&c.v?[...L].sort((x,y)=>{const a=c.v(x),b=c.v(y);return(a<b?-1:a>b?1:0)*d}):L;
  V=[...V].sort((x,y)=>y.model.startsWith("claude-")-x.model.startsWith("claude-"));
  const all=V.length;V=topN(V,top,m=>m.model);
  render(id,rc,V,id);note(id,V.length,all,"local models");
 }else{
  const cs=BC.concat(TC);
  const hc=[{k:"model",l:"Run",str:1,v:r=>r.model.toLowerCase(),f:r=>code(r.model.slice(0,44))+" <small>"+r.day+"</small>"},
   {k:"pct",l:"%",v:r=>frac(r,cs),f:r=>sub(r,cs)}]
   .concat(cs.map(c=>({k:c,l:c.replace(/_/g," "),v:r=>{const m=/^(\d+)\/(\d+)$/.exec(r.cases[c]||"");return m?+m[1]/+m[2]:-1},f:r=>mark(r,c)})));
  let V=table(id,hc,R,id);V=topN(V,top,r=>r.model);
  render(id,hc,V,id);note(id,V.length,R.length,"runs");
 }
}
["rank","rb","rt","hc"].forEach(id=>{bar(id);draw(id)});
el.querySelectorAll("a[href]").forEach(a=>{const h=a.getAttribute("href");if(h&&!/^(https?:|#|explorer\.html)/.test(h))a.href=GH+"/"+h.replace(/^\.?\//,"")});
</script>"""
def _data():
    out = []
    for r in rows:
        out.append({"model": r["builder_model"], "day": r["day"], "params": r["params"], "pb": r["params_b"],
                    "score": r["score"], "max": r["max"], "pct": r["pct"], "tps": r["tps"], "s": num(r, "mean_s_per_case"),
                    "tot": num(r, "total_s"), "comp": r["composite"], "valid": r.get("valid_cases") or "", "infra": num(r, "infra_cases"),
                    "git": (r.get("git_sha") or "")[:7], "harness": r.get("harness_version") or "",
                    "shared": r.get("shared_system_memory_gb") or "", "pull": r["pull"],
                    "req": list(REQUIRED_TOOL_CASES), "cases": {c: r.get(c, "").lstrip("'") for c in CASES}})
    return out


DYN = f"""_{len(rows)} runs x {len(CASES)} cases, generated from `results/benchmark.csv` and `results/cloud.csv` by `script/build_report.py`. Each table below has its own filters (model name, size, recency, how many to show) and sortable headers; defaults show the top runs by rank (ties by pass rate)._

### Ranking

{RANK_LEGEND_MD}

<div id="rank-bar"></div>

<div id="rank"></div>

### Best model per role (local models, top 5 each)

Each role is ranked only on its own cases, because one model is pinned to both roles in a run. Each model is compared across all of its runs in the filtered set. `Runs` shows how many runs it has. `Shared memory GB` above 0 means part of the model spilled off the GPU, which is slower. The Haiku cloud baseline is left out because it cannot be pulled.

**Builder** (cases: {", ".join(f"`{c}`" for c in BUILDER_CASES)})

<div id="rb-bar"></div>

<div id="rb"></div>

**Thinker** (cases: {", ".join(f"`{c}`" for c in THINKER_CASES)})

<div id="rt-bar"></div>

<div id="rt"></div>

### Recommended model per role

Each model is compared across all of its runs. The dot shows how far to trust it for that role:

{RANK_DOT_LEGEND_MD}

**Builder**

{role_rank(BUILDER_CASES, top=5)}

**Thinker**

{role_rank(THINKER_CASES, top=5)}

{role_text()}

### Hard thinker suite (5 harder cases, separate from the 48-case score)

Multi-file bug, two vulnerabilities, ambiguous trace, long summary and function comparison, each run n times (`a/b` = verified runs). Run automatically after the standard benchmark (`run_benchmark.py --no-hard` skips it). Results live in `results/hard_test.csv` and are joined to the models above by name; they do not change the ranking.

{hard_md()}

### Case results (builder and thinker cases together)

<div id="hc-bar"></div>

<div id="hc"></div>

"""
(B / "index.html").write_text(
    PAGE.replace("__GH__", "https://github.com/maxh8086/tokenfrugal/blob/main/Benchmark")
        .replace("__MD__", json.dumps(p.read_text(encoding="utf-8")).replace("</", "<\\/"))
        .replace("__RES__", json.dumps(DYN).replace("</", "<\\/"))
        .replace("__DATA__", json.dumps(_data()).replace("</", "<\\/"))
        .replace("__BC__", json.dumps(BUILDER_CASES))
        .replace("__TC__", json.dumps(THINKER_CASES)),
    encoding="utf-8")
print(f"updated explorer.html and index.html ({len(rows)} runs, {len(CASES)} cases)")

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run_queue.sh uses python -I, which skips the script dir
import clean_outputs
clean_outputs.run()


if _args.update != "no":
    _go = _args.update == "yes"
    if _args.update == "ask":
        try:
            _go = input("Update recommendations (ui ranking dots + default models in tf-roles.yaml) from all data? [y/N] ").strip().lower() in ("y", "yes")
        except EOFError:
            _go = False
    if _go:
        subprocess.run([sys.executable, str(_HERE / "update_recommendations.py")], check=True)
