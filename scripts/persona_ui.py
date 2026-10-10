"""Local editor for the per-persona toolkit (MCPs) and model.

    python -m scripts.persona_ui [--port 7878]     # then open http://127.0.0.1:7878

Pick a profile type (Financial analyst, Programmer, Data scientist, ...), a persona, the MCPs it may use
(checkboxes or multi-select) and its model. Saves only changes to gateway/persona_mcps.json and
gateway/persona_models.json. A blank model resets a persona to its role's model. Restart the MCP client to apply.
"""
import argparse
import json
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

from gateway import config

YAML = config.Path(config.__file__).parent / "personas.yaml"


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
        elif self.path == "/benchmark":
            f = config.ROOT / "Benchmark" / "persona-config.html"
            self._send(200 if f.exists() else 404, f.read_bytes() if f.exists() else b"run python -m scripts.bench_persona", "text/html; charset=utf-8")
        elif self.path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/save" or self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            self._send(200, {"saved": save(json.loads(self.rfile.read(n)))})
        except (ValueError, TypeError, OSError) as e:
            self._send(400, {"error": str(e)})

    def log_message(self, *a):
        pass


PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Persona toolkit</title>
<style>:root{color-scheme:light dark}body{font:14px system-ui;margin:16px;max-width:1000px}select,input,button{font:inherit}
label{display:block;margin:2px 0}.d{opacity:.6}.w{color:#b60}#msg{margin-left:8px}.box{border:1px solid #8886;padding:8px 10px;margin:8px 0}
details{border:1px solid #8886;border-radius:4px;padding:4px 8px;display:inline-block;min-width:380px;vertical-align:top}summary{cursor:pointer}
.pr{color:#2a7;font-size:12px;margin-left:4px}</style>
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
</script>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=7878)
    a = ap.parse_args()
    print(f"Persona toolkit editor: http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
