"""Per-persona model mapping page, built from the solo full-suite runs.

Default model per persona = most verified runs on that persona's cases, then least seconds.
The page lets you pick a model per persona, shows predicted score/time, and exports the mapping.
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python -m scripts.bench_persona
Output: Benchmark/persona-config.html and Benchmark/persona-defaults.md
"""
import json
from collections import defaultdict

from scripts.bench_table import load, PARAMS, CASE_PERSONA, CASE_PUBLIC, ROOT
from scripts.bench_combo import SOLO_TAGS, MAX_PARAMS

name = lambda t: t.replace("full-ts-", "").replace("full-", "").replace("-16384", "")


def main():
    models = {}
    for tag, (d, rw) in load(["bench/*full-*.json"]).items():
        if (SOLO_TAGS(tag) or tag == "full-yarn3b-solo") and PARAMS.get(tag, ("", 3))[1] <= MAX_PARAMS:
            models[name(tag)] = {c: [int(v["verified"].split("/")[0]), round(v["s"]["mean"] or 0, 1)] for c, v in rw.items()}
    personas = defaultdict(list)
    for c, p in CASE_PERSONA.items():
        personas[p].append(c)
    best = {}
    for p, cs in personas.items():
        best[p] = min(models, key=lambda m: (-sum(models[m][c][0] for c in cs), sum(models[m][c][1] for c in cs)))
    out = ["# Default model per persona (best measured solo result)", "",
           "| Persona | Cases | Default model | Verified | s |", "|---|---|---|---|---|"]
    ts = tv = 0
    for p, cs in personas.items():
        m = best[p]
        v, t = sum(models[m][c][0] for c in cs), sum(models[m][c][1] for c in cs)
        ts, tv = ts + t, tv + v
        out.append(f"| {p} | {', '.join(cs)} | {m} | {v}/{2*len(cs)} | {t:.0f} |")
    out += ["", f"All defaults together: {tv}/32 in {ts:.0f} s (sum of per-case means; model swap time not included)."]
    (ROOT / "Benchmark" / "persona-defaults.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    meta = {p: {"cases": cs, "srv": sorted({CASE_PUBLIC[c][1] for c in cs})} for p, cs in personas.items()}
    html = HTML.replace("__M__", json.dumps(models)).replace("__P__", json.dumps(meta)).replace("__B__", json.dumps(best))
    (ROOT / "Benchmark" / "persona-config.html").write_text(html, encoding="utf-8")
    print("\n".join(out))


HTML = """<!doctype html><meta charset=utf-8><title>Persona model mapping</title>
<style>body{font:14px system-ui;margin:16px;background:#fff;color:#111}@media(prefers-color-scheme:dark){body{background:#161616;color:#eee}}
table{border-collapse:collapse}th,td{border:1px solid #8884;padding:4px 8px;text-align:left}select,button{font:inherit}pre{background:#8882;padding:8px;overflow:auto}</style>
<h2>Choose a model per persona</h2>
<p>Defaults are the best measured solo model for each persona. Change a row to see the predicted score and time (sum of measured per-case means, 2 runs per case; model swap time not included).</p>
<table id=t><thead><tr><th>Persona<th>MCP server(s)<th>Cases<th>Model<th>Verified<th>Time s</tr></thead><tbody></tbody></table>
<p><b id=tot></b> <button id=rs>Reset to defaults</button></p>
<p>Mapping (JSON, one model per persona):</p><pre id=ex></pre>
<script>
const M=__M__,P=__P__,B=__B__;let sel={...B};
const tb=document.querySelector("tbody");
for(const p in P)tb.insertAdjacentHTML("beforeend",`<tr data-p="${p}"><td>${p}<td>${P[p].srv.join("<br>")}<td>${P[p].cases.join(", ")}<td><select></select><td class=v><td class=s></tr>`);
function draw(){let v=0,s=0,n=0;document.querySelectorAll("tr[data-p]").forEach(r=>{const p=r.dataset.p,m=sel[p],cs=P[p].cases;
const a=cs.reduce((x,c)=>x+M[m][c][0],0),t=cs.reduce((x,c)=>x+M[m][c][1],0);v+=a;s+=t;n+=2*cs.length;r.querySelector(".v").textContent=a+"/"+2*cs.length;r.querySelector(".s").textContent=t.toFixed(0)});
document.getElementById("tot").textContent=`Predicted: ${v}/${n} in ${s.toFixed(0)} s`;document.getElementById("ex").textContent=JSON.stringify(sel,null,2)}
document.querySelectorAll("tr[data-p]").forEach(r=>{const p=r.dataset.p,se=r.querySelector("select");
Object.keys(M).sort().forEach(m=>se.add(new Option(m+(m==B[p]?" (default)":""),m)));se.value=sel[p];se.onchange=()=>{sel[p]=se.value;draw()}});
document.getElementById("rs").onclick=()=>{sel={...B};document.querySelectorAll("tr[data-p]").forEach(r=>r.querySelector("select").value=sel[r.dataset.p]);draw()};draw();
</script>"""

if __name__ == "__main__":
    main()
