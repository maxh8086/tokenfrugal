"""Rebuild the generated parts of Benchmark/Benchmark.md and Benchmark/explorer.html from results/benchmark.csv.

    python Benchmark/script/build_report.py

Only the text between <!-- BEGIN:auto --> and <!-- END:auto --> in Benchmark.md is replaced; the
Observations section (hand or cloud written) is never touched.
"""
import csv
import json
import re
from pathlib import Path

B = Path(__file__).resolve().parent.parent
META = ("tag", "params", "score", "max", "ran", "mean_s_per_case", "hardware", "valid_cases", "infra_cases", "mean_s_valid",
        "total_s")
rows = list(csv.DictReader((B / "results" / "benchmark.csv").open(encoding="utf-8")))
CASES = [k for k in rows[0] if k not in META]


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


rows.sort(key=lambda r: (-pct(r), num(r, "mean_s_per_case")))
for r in rows:
    r["pct"] = round(pct(r))
    r["params_b"] = params_b(r["params"])


def mmss(v):
    """total_s seconds as m:ss; '' when blank (legacy rows written before total_s existed)."""
    try:
        t = int(float(v))
    except (ValueError, TypeError):
        return ""
    return f"{t // 60}:{t % 60:02d}"


def md_table():
    o = ["| # | Run tag | Params | Score | % | s/case | total | valid | Hardware |",
         "|--:|---|---|--:|--:|--:|--:|--:|---|"]
    for i, r in enumerate(rows, 1):
        tag = f"`{r['tag']}`" + (" ⚠infra" if num(r, "infra_cases") > 0 else "")
        o.append(f"| {i} | {tag} | {r['params']} | {r['score']}/{r['max']} | {r['pct']} "
                 f"| {r['mean_s_per_case']} | {mmss(r.get('total_s'))} | {r.get('valid_cases') or ''} | {r['hardware']} |")
    return "\n".join(o)


def bar_chart():
    xs = ", ".join(f'"{i}"' for i in range(1, len(rows) + 1))
    ys = ", ".join(str(r["pct"]) for r in rows)
    return ("```mermaid\nxychart-beta\n    title \"Verified score % by run (rank order, see table)\"\n"
            f"    x-axis [{xs}]\n    y-axis \"% verified\" 0 --> 100\n    bar [{ys}]\n```")


def speed_chart():
    pts = sorted((r for r in rows if num(r, "mean_s_per_case")), key=lambda r: num(r, "mean_s_per_case"))
    xs = ", ".join(f'"{num(r, "mean_s_per_case"):.0f}"' for r in pts)
    ys = ", ".join(str(r["pct"]) for r in pts)
    return ("```mermaid\nxychart-beta\n    title \"Score % as runs get slower (x: s per case)\"\n"
            f"    x-axis [{xs}]\n    y-axis \"% verified\" 0 --> 100\n    line [{ys}]\n```")


def heatmap():
    o = ["| Run | " + " | ".join(c.replace("_", " ") for c in CASES) + " |",
         "|---|" + "---|" * len(CASES)]
    for r in rows:
        cells = []
        for c in CASES:
            f = case_frac(r, c)
            cells.append("·" if f is None else "🟩" if f == 1 else "🟨" if f > 0 else "🟥")
        o.append(f"| `{r['tag'][:36]}` | " + " | ".join(cells) + " |")
    return "\n".join(o)


auto = f"""<!-- BEGIN:auto -->
_{len(rows)} runs x {len(CASES)} cases, generated from `results/benchmark.csv` by `script/build_report.py`. Interactive filtering: open `explorer.html`._

### Ranking (best score first, ties by speed)

{md_table()}

### Score by run

{bar_chart()}

### Speed vs score

{speed_chart()}

### Per-case heatmap (🟩 all verified, 🟨 partial, 🟥 none, · not run)

{heatmap()}
<!-- END:auto -->"""

p = B / "Benchmark.md"
text = p.read_text(encoding="utf-8") if p.exists() else "# TokenFrugal benchmark\n\n## Observations\n\n_pending cloud review_\n\n"
if "<!-- BEGIN:auto -->" in text:
    text = re.sub(r"<!-- BEGIN:auto -->.*?<!-- END:auto -->", lambda m: auto, text, flags=re.S)
else:
    text = text.rstrip() + "\n\n" + auto + "\n"
p.write_text(text, encoding="utf-8")

HTML = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Benchmark explorer</title>
<style>
:root{--bg:#fff;--fg:#222;--mut:#666;--line:#e3e3e3;--acc:#2e9e5b}
@media(prefers-color-scheme:dark){:root{--bg:#16181b;--fg:#e6e6e6;--mut:#9aa;--line:#2c3036}}
body{font:14px system-ui;margin:16px;background:var(--bg);color:var(--fg)}h1{font-size:18px}
.f{display:flex;flex-wrap:wrap;gap:12px;margin:12px 0}label{display:flex;flex-direction:column;font-size:12px;color:var(--mut)}
input,select{font:inherit;padding:4px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px}
table{border-collapse:collapse;width:100%}th,td{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{cursor:pointer;position:sticky;top:0;background:var(--bg)}.bar{display:inline-block;height:10px;background:var(--acc);margin-right:6px}
.w{overflow-x:auto}.g{color:var(--acc)}.r{color:#d0453b}.y{color:#d9a021}
</style>
<h1>Benchmark explorer</h1>
<div class="f">
<label>Min score %<input id="ms" type="number" value="0" min="0" max="100"></label>
<label>Max s/case<input id="mt" type="number" placeholder="any"></label>
<label>Max params (B)<input id="mp" type="number" placeholder="any"></label>
<label>Name contains<input id="q"></label>
<label>Must pass case<select id="cs"><option value="">(any)</option></select></label>
<label>Hardware<select id="hw"><option value="">(any)</option></select></label>
</div>
<div id="n"></div><div class="w"><table id="t"></table></div>
<script>
const D=__DATA__,C=__CASES__;let sk="pct",sd=-1;
const $=i=>document.getElementById(i);
C.forEach(c=>$("cs").add(new Option(c,c)));
[...new Set(D.map(r=>r.hardware))].forEach(h=>$("hw").add(new Option(h,h)));
const frac=(r,c)=>{try{const[a,n]=r[c].split("/");return a/n}catch(e){return null}};
const cols=[["tag","Run"],["params","Params"],["pct","%"],["score","Score"],["mean_s_per_case","s/case"],["total_s","total s"],["hardware","Hardware"],...C.map(c=>[c,c])];
function draw(){
 const q=$("q").value.toLowerCase(),ms=+$("ms").value,mt=+$("mt").value||1e9,mp=+$("mp").value||1e9,cs=$("cs").value,hw=$("hw").value;
 const R=D.filter(r=>r.pct>=ms&&+r.mean_s_per_case<=mt&&(r.params_b==null||r.params_b<=mp)&&r.tag.toLowerCase().includes(q)&&(!cs||frac(r,cs)===1)&&(!hw||r.hardware==hw));
 R.sort((a,b)=>{let x=a[sk],y=b[sk];x=isNaN(+x)?x:+x;y=isNaN(+y)?y:+y;return(x>y?1:x<y?-1:0)*sd});
 $("n").textContent=R.length+" of "+D.length+" runs match";
 $("t").innerHTML="<tr>"+cols.map(c=>`<th data-k="${c[0]}">${c[1].replace(/_/g," ")}</th>`).join("")+"</tr>"+
  R.map(r=>"<tr>"+cols.map(([k])=>{
   if(k=="pct")return`<td><span class="bar" style="width:${r.pct*.6}px"></span>${r.pct}</td>`;
   if(C.includes(k)){const p=frac(r,k);return`<td class="${p==null?"":p==1?"g":p==0?"r":"y"}">${r[k]||"·"}</td>`}
   return`<td>${r[k]}</td>`}).join("")+"</tr>").join("");
 document.querySelectorAll("th").forEach(h=>h.onclick=()=>{sd=sk==h.dataset.k?-sd:-1;sk=h.dataset.k;draw()});
}
document.querySelectorAll("input,select").forEach(e=>e.oninput=draw);draw();
</script>"""
(B / "explorer.html").write_text(
    HTML.replace("__DATA__", json.dumps(rows)).replace("__CASES__", json.dumps(CASES)), encoding="utf-8")
print(f"updated {p.name} and explorer.html ({len(rows)} runs)")
