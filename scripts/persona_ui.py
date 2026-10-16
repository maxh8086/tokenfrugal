"""Local editor for the per-persona toolkit (MCPs) and model.

    python -m scripts.persona_ui [--port 7878]     # then open http://127.0.0.1:7878

Pick a profile type (Financial analyst, Programmer, Data scientist, ...), a persona, the MCPs it may use
(checkboxes or multi-select) and its model. Saves only changes to router/persona_mcps.json and
router/persona_models.json. A blank model resets a persona to its role's model. Restart the MCP client to apply.
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

from router import config

YAML = config.Path(config.__file__).parent / "agents.yaml"


def installed_models() -> list[str]:
    try:
        req = urllib.request.Request(config.OLLAMA_URL.rstrip("/") + "/models",
                                     headers={"Authorization": f"Bearer {config.LLM_API_KEY}"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return sorted(m["id"] for m in json.load(r)["data"])
    except Exception:
        return []


def _read(path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def state() -> dict:
    base = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    cat = config.load_catalog()
    defaults = base.get("persona_models") or {}
    user, umcp = _read(config.PERSONA_MODELS_FILE), _read(config.PERSONA_MCPS_FILE)
    slugs = {p for t in cat["profile_types"].values() for p in t["personas"]} | set(defaults) | set(user) | set(umcp)
    rows = {}
    for slug in sorted(slugs):
        role = config.resolve_role(slug, base)  # role default (no persona mapping applied to base)
        rows[slug] = {"role": role["role"], "role_model": role["model"], "default": defaults.get(slug, ""),
                      "override": user.get(slug), "mcp_default": config.default_mcps(role, cat), "mcps": umcp.get(slug)}
    return {"rows": rows, "types": cat["profile_types"], "mcps": cat["mcps"], "logical": base["models"],
            "installed": installed_models(), "file": str(config.PERSONA_MODELS_FILE), "mcp_file": str(config.PERSONA_MCPS_FILE)}


def save(body: dict) -> dict:
    """Store only what differs from the defaults: models vs the yaml ('' = role model), MCPs vs the role's toolkit."""
    base = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    cat = config.load_catalog()
    pdef = base.get("persona_models") or {}
    models = {str(k).strip(): str(v or "").strip() for k, v in (body.get("models") or {}).items() if str(k).strip()}
    diff = {k: v for k, v in models.items() if v != pdef.get(k, "")}
    config.PERSONA_MODELS_FILE.write_text(json.dumps(diff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    mdiff = {}
    for k, v in (body.get("mcps") or {}).items():
        v = [n for n in v if n in cat["mcps"]]
        if v != config.default_mcps(config.resolve_role(k, base), cat):
            mdiff[k] = v
    config.PERSONA_MCPS_FILE.write_text(json.dumps(mdiff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"models": diff, "mcps": mdiff}


JOB = {"running": False, "log": [], "summary": None, "proc": None, "tag": "", "t0": 0.0}
_LOCK = threading.Lock()


def bench_summary(tag: str) -> dict | None:
    """Pass counts from the newest bench/<tag>/*.json (realworld section)."""
    files = sorted((config.ROOT / "bench" / tag).glob("*.json"))
    if not files:
        return None
    cases = (_read(files[-1]).get("results") or {}).get("realworld") or {}
    ver = sum(int(v.get("verified") or 0) for v in cases.values())
    ran = sum(int(v.get("ran") or 0) for v in cases.values())
    p50 = [v["s"]["p50"] for v in cases.values() if isinstance(v.get("s"), dict) and v["s"].get("p50")]
    return {"model": tag, "verified": ver, "ran": ran, "cases": len(cases),
            "pct": round(100 * ver / ran) if ran else 0,
            "s_per_case": round(sum(p50) / len(p50), 1) if p50 else None, "file": files[-1].name}


def _run_bench(cmd: list[str], tag: str) -> None:
    try:
        proc = subprocess.Popen(cmd, cwd=str(config.ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
        JOB["proc"] = proc
        for line in proc.stdout:
            JOB["log"].append(line.rstrip())
            del JOB["log"][:-400]
        proc.wait()
    except OSError as e:
        JOB["log"].append(f"failed to start: {e}")
    JOB["summary"] = bench_summary(tag)
    JOB["running"] = False


def bench_start(body: dict) -> dict:
    from scripts.bench_model import _sanitize, _url_tag
    model, url = str(body.get("model") or "").strip(), str(body.get("url") or "").strip()
    n = max(1, min(int(body.get("n") or 2), 10))
    if bool(model) == bool(url):
        raise ValueError("give exactly one of model or endpoint URL")
    if url and not url.startswith(("http://", "https://")):
        raise ValueError("endpoint URL must start with http:// or https://")
    with _LOCK:
        if JOB["running"]:
            raise ValueError("a benchmark is already running")
        tag = _sanitize(model) if model else _url_tag(url)
        cmd = [sys.executable, "-m", "scripts.bench_model", "--n", str(n)] + (["--model", model] if model else ["--url", url])
        JOB.update(running=True, log=[], summary=None, tag=tag, t0=time.time())
        threading.Thread(target=_run_bench, args=(cmd, tag), daemon=True).start()
    return {"started": tag}


def bench_stop() -> dict:
    p = JOB.get("proc")
    if JOB["running"] and p:
        p.terminate()
    return {"stopped": True}


def bench_status() -> dict:
    return {"running": JOB["running"], "tag": JOB["tag"], "log": JOB["log"][-60:], "summary": JOB["summary"],
            "elapsed": round(time.time() - JOB["t0"]) if JOB["running"] else 0}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/state":
            self._send(200, state())
        elif self.path == "/api/bench/status":
            self._send(200, bench_status())
        elif self.path == "/benchmark":
            f = config.ROOT / "Benchmark" / "explorer.html"
            self._send(200 if f.exists() else 404, f.read_bytes() if f.exists() else b"run python Benchmark/script/build_report.py", "text/html; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        routes = {"/api/save": lambda b: {"saved": save(b)}, "/api/bench/start": bench_start,
                  "/api/bench/stop": lambda b: bench_stop()}
        if self.path not in routes or self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            self._send(200, routes[self.path](json.loads(self.rfile.read(n) or b"{}")))
        except (ValueError, TypeError, OSError) as e:
            self._send(400, {"error": str(e)})

    def log_message(self, *a):
        pass


PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Persona toolkit</title>
<style>:root{color-scheme:light dark}body{font:14px system-ui;margin:16px;max-width:1000px}select,input,button{font:inherit}
label{display:block;margin:2px 0}.d{opacity:.6}.w{color:#b60}#msg{margin-left:8px}.box{border:1px solid #8886;padding:8px 10px;margin:8px 0}
details{border:1px solid #8886;border-radius:4px;padding:4px 8px;display:inline-block;min-width:380px;vertical-align:top}summary{cursor:pointer}
.pr{color:#2a7;font-size:12px;margin-left:4px}
.tabs{display:flex;gap:4px;border-bottom:1px solid #8886;margin-bottom:12px}.tabs button{border:0;border-bottom:3px solid transparent;background:none;padding:6px 14px;cursor:pointer}
.tabs button.on{border-color:#2a7;font-weight:600}pre{background:#8881;padding:8px;max-height:220px;overflow:auto;font-size:12px;white-space:pre-wrap}
textarea{width:100%;box-sizing:border-box;font:inherit}.sh button{margin-right:6px}</style>
<div class=tabs><button id=tp class=on>Personas</button><button id=tb>Benchmark</button></div>
<div id=pv>
<h2>Toolkit and model per persona</h2>
<div class=box><b>Review the benchmark first.</b> Before choosing MCPs and a model, check which tool works best with which model:
<a href="/benchmark" target=_blank>benchmark results (local)</a> |
<a href="https://github.com/maxh8086/tokenfrugal/tree/main/Benchmark" target=_blank rel=noopener>Benchmark/ in the repo</a>.
<label><input type=checkbox id=ack> I reviewed the benchmark results</label></div>
<p>Profile type <select id=t></select> Persona <select id=p></select></p>
<p id=info class=d></p>
<p>MCPs (tick any number) <span class=d>- "proposed" = the benchmarked default</span><br>
<details id=dd><summary id=sm></summary><div id=cb></div></details></p>
<p id=warn class=w></p>
<p>Model (one per persona) <select id=m></select> <span class=d>proposed: <span id=md></span></span></p>
<p><button id=save disabled>Save</button> <button id=reset>Reset persona to proposed</button><span id=msg></span></p>
<p class=d>Saved to <code id=f></code> and <code id=g></code>; restart the MCP client to apply.</p>
</div>
<div id=bv hidden>
<h2>Run a benchmark</h2>
<p>Test one model on the 16 real-world cases (same harness as the published results). Pick an installed Ollama model or an OpenAI-compatible endpoint.</p>
<p>Model <select id=bm></select> or endpoint URL <input id=bu size=32 placeholder="http://127.0.0.1:8282/v1">
Repeats <input id=bn type=number min=1 max=10 value=2 style="width:50px">
<button id=bgo>Run benchmark</button> <button id=bstop hidden>Stop</button> <span id=bst class=d></span></p>
<pre id=blog>No run yet.</pre>
<p class=d>Published results: <a href="https://maxh8086.github.io/tokenfrugal/Benchmark/" target=_blank rel=noopener>Benchmark index</a> | <a href="https://maxh8086.github.io/tokenfrugal/Benchmark/explorer.html" target=_blank rel=noopener>Explorer</a></p>
<div id=bres hidden class=box>
<h3>Share your results</h3>
<p id=bsum></p>
<p>Share <select id=bwhat><option value="index">Benchmark index</option><option value="explorer">Explorer</option></select></p>
<p>Tag on LinkedIn <input id=tli size=40> Tag on X <input id=ttw size=20> <span class=d>(defaults to the project author; edit or clear)</span></p>
<p><textarea id=btxt rows=7></textarea></p>
<p class=sh><button id=sli>Share on LinkedIn</button><button id=stw>Share on X</button><button id=cp>Copy text</button><span id=cpm class=d></span></p>
<p class=d>LinkedIn cannot prefill text from a link: the text is copied for you, paste it into the post box that opens.</p>
</div>
</div>
<script>
let S,mc={},md={};const $=id=>document.getElementById(id);
const cur=()=>$("p").value;
const PR=' <span class=pr>(proposed)</span>';
function draw(){const p=cur(),r=S.rows[p],sel=mc[p],prop=r.mcp_default;
$("info").textContent=`role: ${r.role} (${r.role_model})`;
$("sm").textContent=sel.length?sel.map(n=>S.mcps[n].label).join(", "):"(none: role default toolkit)";
$("cb").innerHTML=Object.entries(S.mcps).map(([n,m])=>`<label><input type=checkbox value="${n}"${sel.includes(n)?" checked":""}> ${m.label}${prop.includes(n)?PR:""}</label>`).join("");
document.querySelectorAll("#cb input").forEach(c=>c.onchange=()=>{mc[p]=[...document.querySelectorAll("#cb input:checked")].map(x=>x.value);const o=$("dd").open;draw();$("dd").open=o});
const n=new Set(sel.flatMap(x=>S.mcps[x].tools)).size;
$("warn").textContent=n>6?`${n} tools selected; 3B models work best with 6 or fewer.`:"";
const pm=r.default||"",c=md[p];
const all=[...new Set([...Object.keys(S.logical),...S.installed,pm,c].filter(Boolean))];
$("m").innerHTML='<option value="">(role model)</option>'+all.map(m=>`<option value="${m}"${m===c?" selected":""}>${m}${m===pm?" (proposed)":""}</option>`).join("");
$("m").onchange=e=>{md[p]=e.target.value};$("md").textContent=pm||r.role_model}
function pickType(){const t=S.types[$("t").value];
$("p").innerHTML=t.personas.map(x=>`<option${x===t.default?" selected":""}>${x}</option>`).join("");draw()}
async function load(){S=await (await fetch("/api/state")).json();$("f").textContent=S.file;$("g").textContent=S.mcp_file;
for(const [k,r] of Object.entries(S.rows)){mc[k]=[...(r.mcps??r.mcp_default)];md[k]=r.override??r.default}
$("t").innerHTML=Object.entries(S.types).map(([k,t])=>`<option value="${k}">${t.label}</option>`).join("");
$("t").onchange=pickType;$("p").onchange=draw;pickType()}
$("ack").onchange=()=>{$("save").disabled=!$("ack").checked};
$("reset").onclick=()=>{const p=cur(),r=S.rows[p];mc[p]=[...r.mcp_default];md[p]=r.default;draw()};
$("save").onclick=async()=>{const r=await fetch("/api/save",{method:"POST",body:JSON.stringify({models:md,mcps:mc})});
$("msg").textContent=r.ok?"Saved. Restart the MCP client to apply.":"Save failed"};
load();
const BASE="https://maxh8086.github.io/tokenfrugal/Benchmark/";
const GH="https://github.com/maxh8086/tokenfrugal";
const LI0="https://www.linkedin.com/in/vpavtekar",TW0="@vaibhavpavtekar";
let sm0=null,poll=null;
function tab(b){$("pv").hidden=b;$("bv").hidden=!b;$("tp").className=b?"":"on";$("tb").className=b?"on":""}
$("tp").onclick=()=>tab(false);
$("tb").onclick=()=>{tab(true);$("bm").innerHTML='<option value="">(choose model)</option>'+(S?S.installed:[]).map(m=>`<option>${m}</option>`).join("")};
const link=()=>BASE+($("bwhat").value==="explorer"?"explorer.html":"");
function shareText(){const s=sm0,tags=[$("tli").value.trim(),$("ttw").value.trim()].filter(Boolean).join(" ");
return `I benchmarked ${s.model} with TokenFrugal: ${s.verified}/${s.ran} checks passed (${s.pct}%) across ${s.cases} real-world coding cases`+(s.s_per_case?`, ~${s.s_per_case}s per case`:"")+` on my own machine.\\n\\nCompare local models: ${link()}\\nGitHub: ${GH}\\n\\n#LocalLLM #Ollama #TokenFrugal`+(tags?`\\n${tags}`:"")}
function refreshShare(){if(sm0)$("btxt").value=shareText()}
function showRes(s){sm0=s;$("bres").hidden=!s||!s.ran;if(!s||!s.ran)return;
$("bsum").textContent=`${s.model}: ${s.verified}/${s.ran} checks (${s.pct}%), ${s.cases} cases`+(s.s_per_case?`, ${s.s_per_case}s per case`:"");
if(!$("tli").dataset.set){$("tli").value=LI0;$("ttw").value=TW0;$("tli").dataset.set=1}refreshShare()}
["tli","ttw","bwhat"].forEach(i=>$(i).oninput=refreshShare);
$("bwhat").onchange=refreshShare;
$("stw").onclick=()=>{const t=$("btxt").value.replace(link(),"").replace(/\\n{3,}/g,"\\n\\n").trim();
window.open("https://twitter.com/intent/tweet?text="+encodeURIComponent(t)+"&url="+encodeURIComponent(link()),"_blank","noopener")};
async function copy(){try{await navigator.clipboard.writeText($("btxt").value);$("cpm").textContent=" copied";return true}catch(e){$("btxt").select();$("cpm").textContent=" press Ctrl+C";return false}}
$("cp").onclick=copy;
$("sli").onclick=async()=>{await copy();window.open("https://www.linkedin.com/sharing/share-offsite/?url="+encodeURIComponent(link()),"_blank","noopener")};
async function tick(){const r=await (await fetch("/api/bench/status")).json();
$("blog").textContent=r.log.length?r.log.join("\\n"):"No run yet.";$("blog").scrollTop=1e9;
$("bgo").disabled=r.running;$("bstop").hidden=!r.running;$("bst").textContent=r.running?`running ${r.tag}, ${r.elapsed}s`:(r.tag?"finished":"");
if(!r.running){clearInterval(poll);poll=null;showRes(r.summary)}}
$("bgo").onclick=async()=>{const m=$("bm").value,u=$("bu").value.trim();
const r=await fetch("/api/bench/start",{method:"POST",body:JSON.stringify({model:u?"":m,url:u,n:+$("bn").value})});
if(!r.ok){$("bst").textContent=(await r.json()).error;return}
$("bres").hidden=true;poll=setInterval(tick,2000);tick()};
$("bstop").onclick=()=>fetch("/api/bench/stop",{method:"POST",body:"{}"});
fetch("/api/bench/status").then(r=>r.json()).then(r=>{if(r.running){poll=setInterval(tick,2000);tick()}else if(r.summary)showRes(r.summary)});
</script>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=7878)
    a = ap.parse_args()
    print(f"Persona toolkit editor: http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
