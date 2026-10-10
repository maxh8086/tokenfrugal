"""Per-persona model mapping page, built from the solo full-suite runs.

Default model per persona = among models that verify at least 75% of the best score on that persona's cases,
the smallest (parameters), then the fastest (seconds). Rule and tables: Benchmark/persona-model-selection.md.
The page lets you pick a model per persona, shows predicted score/time, and exports the mapping.
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python -m scripts.bench_persona
Output: Benchmark/persona-config.html and Benchmark/persona-defaults.md
"""
import json
from collections import defaultdict

from scripts.bench_table import load, PARAMS, CASE_PERSONA, CASE_PUBLIC, ROOT
from scripts.bench_combo import SOLO_TAGS, MAX_PARAMS

name = lambda t: t.replace("full-ts-", "").replace("full-", "").replace("-16384", "")

# Benchmark name -> (Ollama tag, base model, params, quantization, context, extra Modelfile settings).
# Read from `ollama show` / models/*.Modelfile / models/trial/*.Modelfile; all runs used temperature 0.1.
_T = "temp 0.1"
INFO = {
    "yarn3b-solo": ("qwen2.5-coder-yarn:3b", "qwen2.5-coder:3b", "3.1B", "Q4_K_M", 65536, _T + "; YaRN-extended ctx (models/builder.Modelfile)"),
    "llama3-2-3b-16k": ("llama3.2:3b-16k", "llama3.2:3b", "3.2B", "Q4_K_M", 16384, _T + ", repeat_penalty 1.1, llama3 stop tokens (models/thinker.Modelfile)"),
    "qwen3-4b": ("ts-qwen3-4b-16384", "qwen3:4b", "4.0B", "Q4_K_M", 16384, _T),
    "phi4-mini": ("ts-phi4-mini-16384", "phi4-mini", "3.8B", "Q4_K_M", 16384, _T),
    "gemma3-4b": ("ts-gemma3-4b-16384", "gemma3:4b", "3.9B", "Q4_K_M", 16384, _T),
    "qwen25c-7b": ("ts-qwen25c-7b-16384", "qwen2.5-coder:7b", "7.6B", "Q4_K_M", 16384, _T),
    "granite3-3-8b": ("ts-granite3-3-8b-16384", "granite3.3:8b", "8.2B", "Q4_K_M", 16384, _T),
    "llama3-1-8b": ("ts-llama3-1-8b-16384", "llama3.1:8b", "8.0B", "Q4_K_M", 16384, _T),
    "qwen2-5-7b": ("ts-qwen2-5-7b-16384", "qwen2.5:7b", "7.6B", "Q4_K_M", 16384, _T),
    "qwen3-8b": ("ts-qwen3-8b-16384", "qwen3:8b", "8.2B", "Q4_K_M", 16384, _T + ", top_k 20, top_p 0.95, repeat_penalty 1"),
    "ministral-3-8b": ("ts-ministral-3-8b-16384", "ministral-3:8b", "8.9B", "Q4_K_M", 16384, _T),
    "gemma4-e4b": ("ts-gemma4-e4b-16384", "gemma4:e4b", "7.5B (4B effective)", "Q4_K_M", 16384, _T + ", top_k 64, top_p 0.95, vision projector"),
    "qwen2-5vl-7b": ("ts-qwen2-5vl-7b-16384", "qwen2.5vl:7b", "8.3B", "Q4_K_M", 16384, _T + ", vision"),
    "deepseek-r1-8b": ("ts-deepseek-r1-8b-16384", "deepseek-r1:8b", "8.2B", "Q4_K_M", 16384, _T + ", reasoning model"),
    "deepseek-r1-distill-qwen-7b": ("ts-deepseek-r1-distill-qwen-7b-16384", "hf.co/lmstudio-community/DeepSeek-R1-Distill-Qwen-7B-GGUF", "7.6B", "Q4_K_M", 16384, _T + ", reasoning model"),
    "starcoder2-7b": ("ts-starcoder2-7b-16384", "starcoder2:7b", "7B", "Q4_0", 16384, _T + ", code-completion model"),
}


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
        sc = {m: sum(models[m][c][0] for c in cs) for m in models}
        ok = [m for m in models if sc[m] >= 0.75 * max(sc.values())]
        best[p] = min(ok, key=lambda m: (float(INFO[m][2].split("B")[0]), sum(models[m][c][1] for c in cs)))
    out = ["# Default model per persona (smallest adequate model, then fastest)", "",
           "| Persona | Cases | Default model (Ollama tag) | Quant | Ctx | Verified | s |", "|---|---|---|---|---|---|---|"]
    ts = tv = 0
    for p, cs in personas.items():
        m = best[p]
        v, t = sum(models[m][c][0] for c in cs), sum(models[m][c][1] for c in cs)
        ts, tv = ts + t, tv + v
        i = INFO[m]
        out.append(f"| {p} | {', '.join(cs)} | `{i[0]}` | {i[3]} | {i[4]} | {v}/{2*len(cs)} | {t:.0f} |")
    out += ["", f"All defaults together: {tv}/32 in {ts:.0f} s (sum of per-case means; model swap time not included)."]
    (ROOT / "Benchmark" / "persona-defaults.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    meta = {p: {"cases": cs, "srv": sorted({CASE_PUBLIC[c][1] for c in cs})} for p, cs in personas.items()}
    info = {m: dict(zip(("tag", "base", "params", "quant", "ctx", "cfg"), INFO[m])) for m in models}
    best_tag = {p: info[m]["tag"] for p, m in best.items()}
    html = HTML.replace("__I__", json.dumps(info)).replace("__M__", json.dumps(models)).replace("__P__", json.dumps(meta)).replace("__B__", json.dumps(best))
    json.dumps(best_tag)
    (ROOT / "Benchmark" / "persona-config.html").write_text(html, encoding="utf-8")
    print("\n".join(out))


HTML = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Persona model mapping</title>
<style>body{font:14px system-ui;margin:16px;background:#fff;color:#111}@media(prefers-color-scheme:dark){body{background:#161616;color:#eee}}
.w{overflow-x:auto}table{border-collapse:collapse}th,td{border:1px solid #8884;padding:4px 8px;text-align:left;vertical-align:top}
select,button{font:inherit}pre{background:#8882;padding:8px;overflow:auto}.d{opacity:.7;font-size:12px}td.n{white-space:nowrap}</style>
<h2>Choose a model per persona</h2>
<p>Defaults are the best measured solo model for each persona. The Model column shows the exact Ollama tag; the columns to its right are the settings that tag was tested with (quantization, context window, Modelfile config). Predicted score and time are sums of measured per-case means, 2 runs per case, model swap time not included.</p>
<div class=w><table><thead><tr><th>Persona<th>MCP server(s)<th>Cases<th>Model (Ollama tag)<th>Base<th>Params<th>Quant<th>Context<th>Config<th>Verified<th>Time s</tr></thead><tbody></tbody></table></div>
<p><b id=tot></b> <button id=rs>Reset to defaults</button> <button id=dl>Download persona_models.json</button></p>
<p>Mapping for <code>gateway/persona_models.json</code> (valid as-is; or use <code>python -m scripts.persona_ui</code>):</p><pre id=ex></pre>
<script>
const I=__I__,M=__M__,P=__P__,B=__B__;let sel={...B};
const tb=document.querySelector("tbody");
for(const p in P)tb.insertAdjacentHTML("beforeend",`<tr data-p="${p}"><td>${p}<td>${P[p].srv.join("<br>")}<td>${P[p].cases.join(", ")}<td><select></select><td class=b><td class=n><td class=n><td class=n><td class=d><td class="v n"><td class="s n"></tr>`);
function draw(){let v=0,s=0,n=0;const map={};document.querySelectorAll("tr[data-p]").forEach(r=>{const p=r.dataset.p,m=sel[p],cs=P[p].cases,i=I[m];
const a=cs.reduce((x,c)=>x+M[m][c][0],0),t=cs.reduce((x,c)=>x+M[m][c][1],0);v+=a;s+=t;n+=2*cs.length;
r.querySelector(".v").textContent=a+"/"+2*cs.length;r.querySelector(".s").textContent=t.toFixed(0);
r.querySelector(".b").textContent=i.base;r.children[5].textContent=i.params;r.children[6].textContent=i.quant;r.children[7].textContent=i.ctx;r.children[8].textContent=i.cfg;map[p]=i.tag});
document.getElementById("tot").textContent=`Predicted: ${v}/${n} in ${s.toFixed(0)} s`;document.getElementById("ex").textContent=JSON.stringify(map,null,2)}
document.querySelectorAll("tr[data-p]").forEach(r=>{const p=r.dataset.p,se=r.querySelector("select");
Object.keys(M).sort().forEach(m=>se.add(new Option(I[m].tag+(m==B[p]?" (default)":""),m)));se.value=sel[p];se.onchange=()=>{sel[p]=se.value;draw()}});
document.getElementById("rs").onclick=()=>{sel={...B};document.querySelectorAll("tr[data-p]").forEach(r=>r.querySelector("select").value=sel[r.dataset.p]);draw()};
document.getElementById("dl").onclick=()=>{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([document.getElementById("ex").textContent],{type:"application/json"}));a.download="persona_models.json";a.click()};
draw();
</script>"""

if __name__ == "__main__":
    main()
