// Live dashboard for the tokenfrugal gateway: which role/model is running which task.
// Zero dependencies. Tails gateway/events.jsonl (written by gateway/events.py) and streams it over SSE.
//   node ui/server.js        ->  http://127.0.0.1:7777   (`port:` in gateway/ui.yaml; UI_PORT / GATEWAY_EVENTS override)
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { execFile } = require('node:child_process');

function configPort() { // `port: N` from gateway/ui.yaml, the same file the launcher reads
  try {
    const m = /^port:\s*(\d+)/m.exec(fs.readFileSync(path.join(__dirname, '..', 'gateway', 'ui.yaml'), 'utf8'));
    return m ? Number(m[1]) : 7777;
  } catch { return 7777; }
}
const PORT = Number(process.env.UI_PORT || configPort());
const EVENTS = process.env.GATEWAY_EVENTS || path.join(__dirname, '..', 'gateway', 'events.jsonl');
const ROLES = path.join(path.dirname(EVENTS), 'roles.json');
const MAX_TASKS = 200;

const tasks = new Map(); // id -> task
const clients = new Set();
const gateways = new Map(); // gateway pid -> MCP client name (Claude, Codex, ...)
let offset = 0;
let tail = '';

function alive(pid) {
  try { process.kill(pid, 0); return true; } catch (e) { return e.code === 'EPERM'; }
}

function view(t) {
  const status = t.status === 'running' && !alive(t.pid) ? 'stale' : t.status;
  return { ...t, status };
}

function note(t, ts, text) {
  t.log.push({ ts, text: String(text).slice(0, 1000) });
  if (t.log.length > 40) t.log.shift();
}

function apply(ev) {
  if (ev.kind === 'client') { gateways.set(ev.pid, String(ev.name || '')); return null; }
  let t = tasks.get(ev.id);
  if (ev.kind === 'task_start') {
    t = { id: ev.id, pid: ev.pid, agent: ev.agent, role: ev.role, model: ev.model, prompt: ev.prompt,
          maxSteps: ev.max_steps, attempt: ev.attempt, status: 'running', step: 0, fix: false, tool: '', log: [], think: '', calls: 0,
          startedAt: ev.ts, updatedAt: ev.ts, endedAt: null, summary: '', error: '' };
    note(t, ev.ts, 'started: ' + (ev.prompt || ''));
    tasks.set(ev.id, t);
    if (tasks.size > MAX_TASKS) tasks.delete(tasks.keys().next().value);
  } else if (!t) {
    return null;
  } else if (ev.kind === 'step') {
    t.step = ev.n; t.tool = ''; t.updatedAt = ev.ts; note(t, ev.ts, 'step ' + ev.n);
  } else if (ev.kind === 'retry') {
    t.fix = true; t.updatedAt = ev.ts; note(t, ev.ts, 'fix needed: ' + (ev.reason || ''));
  } else if (ev.kind === 'tool') {
    t.fix = false; t.tool = ev.name; t.calls += 1; t.updatedAt = ev.ts;
    note(t, ev.ts, `tool ${ev.name}(${ev.args || ''})`);
  } else if (ev.kind === 'say') {
    note(t, ev.ts, ev.text); t.think = ev.text; t.updatedAt = ev.ts;
  } else if (ev.kind === 'task_done') {
    note(t, ev.ts, 'done: ' + ev.summary);
    Object.assign(t, { status: 'done', summary: ev.summary, endedAt: ev.ts, updatedAt: ev.ts, tool: '', saved: Number(ev.saved) || 0 });
  } else if (ev.kind === 'task_failed') {
    note(t, ev.ts, 'failed: ' + ev.error);
    Object.assign(t, { status: 'failed', error: ev.error, endedAt: ev.ts, updatedAt: ev.ts, tool: '', saved: Number(ev.saved) || 0 });
  } else {
    return null;
  }
  return t;
}

function broadcast(t) {
  const msg = `data: ${JSON.stringify(view(t))}\n\n`;
  for (const c of clients) c.write(msg);
}

function poll() {
  let st;
  try { st = fs.statSync(EVENTS); } catch { return; }
  if (st.size < offset) { offset = 0; tail = ''; tasks.clear(); } // rotated or truncated
  if (st.size === offset) return;
  const fd = fs.openSync(EVENTS, 'r');
  const buf = Buffer.alloc(st.size - offset);
  fs.readSync(fd, buf, 0, buf.length, offset);
  fs.closeSync(fd);
  offset = st.size;
  const lines = (tail + buf.toString('utf8')).split('\n');
  tail = lines.pop(); // partial last line, completed on the next poll
  for (const line of lines) {
    if (!line) continue;
    let ev;
    try { ev = JSON.parse(line); } catch { continue; }
    const t = apply(ev);
    if (t) broadcast(t);
  }
}

const run = (cmd, args) => new Promise((ok) => execFile(cmd, args, { timeout: 4000, windowsHide: true }, (e, out) => ok(e ? null : String(out))));
let svc = { at: 0, data: null };

// Ollama (OpenAI-compatible /models), Docker engine and the ts-mcp compose containers; cached a few seconds.
async function services(cfg) {
  if (svc.data && Date.now() - svc.at < 4000) return svc.data;
  const llm = { url: cfg.llm_url || '', ok: false, models: [] };
  try {
    const r = await fetch(String(llm.url).replace(/\/$/, '') + '/models', { signal: AbortSignal.timeout(2000) });
    if (r.ok) { llm.ok = true; llm.models = ((await r.json()).data || []).map((m) => m.id); }
  } catch { /* down */ }
  const graph = { ok: false, url: '' };
  for (const p of (cfg.ui && cfg.ui.codelense_ports) || []) { // codelense-mcp UI: any HTTP answer on a configured local port
    try { await fetch(`http://127.0.0.1:${p}/healthz`, { signal: AbortSignal.timeout(600) }); graph.ok = true; graph.url = `http://127.0.0.1:${p}/ui/`; break; } catch { /* not listening */ }
  }
  const ver = await run('docker', ['info', '--format', '{{.ServerVersion}}']);
  const docker = { ok: !!ver && ver.trim() !== '', version: (ver || '').trim() };
  const ps = docker.ok ? await run('docker', ['ps', '-a', '--filter', 'label=com.docker.compose.project=' + (cfg.compose_project || 'ts-mcp'),
    '--format', '{{.Label "com.docker.compose.service"}}|{{.State}}']) : null;
  const containers = {};
  for (const l of (ps || '').split('\n')) { const [n, st] = l.trim().split('|'); if (n) containers[n] = st; }
  svc = { at: Date.now(), data: { ollama: llm, docker, graph, containers } };
  return svc.data;
}

// One row per MCP server a role can use, with a live status and which running tasks need it.
function mcpRows(cfg, sv, list, only) {
  const rows = new Map();
  const add = (name, kind, status, role) => {
    const k = kind + ':' + name;
    if (!rows.has(k)) rows.set(k, { name, kind, status, roles: [], active: false });
    const r = rows.get(k); r.roles.push(role);
    if (list.some((t) => t.status === 'running' && t.role === role)) r.active = true;
  };
  for (const r of (cfg.roles || []).filter((x) => x.role === only)) {
    if (r.profile) add(r.profile, 'profile', sv.docker.ok ? 'up' : 'down', r.role);
    for (const b of r.backends || []) add(b, 'backend', sv.containers[b] === 'running' ? 'up' : (sv.docker.ok ? 'idle' : 'down'), r.role);
    for (const n of r.native || []) add(n, 'native', 'native', r.role);
  }
  return [...rows.values()];
}

function roles() {
  try { return JSON.parse(fs.readFileSync(ROLES, 'utf8')); } catch { return { roles: [], divisions: {} }; }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/api/state') {
    const list = [...tasks.values()].map(view).sort((a, b) => b.startedAt - a.startedAt);
    const cfg = roles();
    const sv = await services(cfg);
    const cur = list.find((t) => t.status === 'running') || list[0] || null;
    const selected = cur ? cur.role : '';
    const connected = [...new Set([...gateways].filter(([pid]) => alive(pid)).map(([, n]) => n).filter(Boolean))];
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ now: Date.now() / 1000, tasks: list, ...cfg, services: sv, connected, selected,
      saved: list.reduce((n, t) => n + (t.saved || 0), 0),
      agent: cur && cur.status === 'running' ? cur.agent : '', mcp: mcpRows(cfg, sv, list, selected) }));
  }
  if (url.pathname === '/events') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive' });
    res.write(': connected\n\n');
    clients.add(res);
    return req.on('close', () => clients.delete(res));
  }
  if (url.pathname === '/logo.svg') {
    try {
      const svg = fs.readFileSync(path.join(__dirname, '..', 'assets', 'logo.svg'));
      res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
      return res.end(svg);
    } catch { return res.writeHead(404).end('not found'); }
  }
  if (url.pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(fs.readFileSync(path.join(__dirname, 'index.html')));
  }
  res.writeHead(404).end('not found');
});

poll();
setInterval(poll, 400);
setInterval(() => { // pids that died mid-task flip to "stale"; keepalive for idle SSE connections
  for (const t of tasks.values()) if (t.status === 'running' && !alive(t.pid)) broadcast(t);
  for (const c of clients) c.write(': ping\n\n');
}, 5000);

server.listen(PORT, '127.0.0.1', () => console.log(`tokenfrugal dashboard: http://127.0.0.1:${PORT}  (events: ${EVENTS})`));
