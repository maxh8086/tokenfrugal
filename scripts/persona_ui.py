"""Local editor for the per-persona model mapping.

    python -m scripts.persona_ui [--port 7878]     # then open http://127.0.0.1:7878

Shows every persona with its yaml default and the model it will use, lets you pick another installed model
(or builder/thinker), and saves only your changes to gateway/persona_models.json. A blank choice resets a
persona to its role's model. Restart the MCP client (gateway) to apply.
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


def user_overrides() -> dict:
    try:
        return json.loads(config.PERSONA_MODELS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def state() -> dict:
    base = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    defaults, user = base.get("persona_models") or {}, user_overrides()
    rows = []
    for slug in sorted(set(defaults) | set(user)):
        role = config.resolve_role(slug, base)  # role default (before persona mapping)
        rows.append({"persona": slug, "role": role["role"], "role_model": role["model"],
                     "default": defaults.get(slug, ""), "override": user.get(slug)})
    return {"rows": rows, "logical": base["models"], "installed": installed_models(), "file": str(config.PERSONA_MODELS_FILE)}


def save(mapping: dict) -> dict:
    """Store only the entries that differ from the yaml default ('' = use the role's model)."""
    base = yaml.safe_load(YAML.read_text(encoding="utf-8")).get("persona_models") or {}
    clean = {str(k).strip(): str(v).strip() for k, v in mapping.items() if str(k).strip()}
    diff = {k: v for k, v in clean.items() if v != base.get(k, "")}
    config.PERSONA_MODELS_FILE.write_text(json.dumps(diff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return diff


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


PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Persona models</title>
<style>:root{color-scheme:light dark}body{font:14px system-ui;margin:16px;max-width:1000px}table{border-collapse:collapse;width:100%}
th,td{border:1px solid #8884;padding:5px 8px;text-align:left}select,input,button{font:inherit}.d{opacity:.6}#msg{margin-left:8px}</style>
<h2>Model per persona</h2>
<p>Pick the local model each persona uses. Defaults are the best measured model per persona. Changes are saved to
<code id=f></code>; restart the MCP client to apply. Blank = the persona's role model.</p>
<table><thead><tr><th>Persona<th>Role<th>Default<th>Model</tr></thead><tbody id=b></tbody></table>
<p><input id=np placeholder="add persona slug, e.g. engineering-sre"> <button id=add>Add</button>
<button id=save>Save</button> <button id=reset>Reset to defaults</button><span id=msg></span></p>
<script>
let S,sel={};const $=id=>document.getElementById(id);
function opts(cur){const all=[...new Set([...Object.keys(S.logical),...S.installed,cur].filter(x=>x!==undefined))];
return '<option value="">(role model)</option>'+all.map(m=>`<option${m===cur?" selected":""}>${m}</option>`).join("")}
function draw(){$("b").innerHTML=S.rows.map(r=>`<tr data-p="${r.persona}"><td>${r.persona}<td>${r.role} <span class=d>${r.role_model}</span>
<td class=d>${r.default||"-"}<td><select>${opts(sel[r.persona])}</select></tr>`).join("");
document.querySelectorAll("tr[data-p]").forEach(t=>t.querySelector("select").onchange=e=>{sel[t.dataset.p]=e.target.value})}
async function load(){S=await (await fetch("/api/state")).json();$("f").textContent=S.file;sel={};
S.rows.forEach(r=>sel[r.persona]=r.override??r.default);draw()}
$("add").onclick=()=>{const p=$("np").value.trim();if(p&&!(p in sel)){S.rows.push({persona:p,role:"?",role_model:"",default:"",override:""});sel[p]="";draw()}$("np").value=""};
$("reset").onclick=()=>{S.rows.forEach(r=>sel[r.persona]=r.default);draw()};
$("save").onclick=async()=>{const r=await fetch("/api/save",{method:"POST",body:JSON.stringify(sel)});
$("msg").textContent=r.ok?"Saved. Restart the MCP client to apply.":"Save failed";};
load();
</script>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=7878)
    a = ap.parse_args()
    print(f"Persona model editor: http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
