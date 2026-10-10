// Live dashboard for the tokenfrugal gateway: which role/model is running which task.
// Zero dependencies. Tails gateway/events.jsonl (written by gateway/events.py) and streams it over SSE.
//   node ui/server.js        ->  http://127.0.0.1:7777   (`port:` in gateway/ui.yaml; UI_PORT / GATEWAY_EVENTS override)
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { execFile } = require('node:child_process');
const os = require('node:os');

function configPort() { // `port: N` from gateway/ui.yaml, the same file the launcher reads
  try {
    const m = /^port:\s*(\d+)/m.exec(fs.readFileSync(path.join(__dirname, '..', 'gateway', 'ui.yaml'), 'utf8'));
    return m ? Number(m[1]) : 7777;
  } catch { return 7777; }
}
function cfgNum(key, dflt) {
  try {
    const m = new RegExp('^' + key + ':\\s*(\\d+)', 'm').exec(fs.readFileSync(path.join(__dirname, '..', 'gateway', 'ui.yaml'), 'utf8'));
    return m ? Number(m[1]) : dflt;
  } catch { return dflt; }
}
const PORT = Number(process.env.UI_PORT || configPort());
const EVENTS = process.env.GATEWAY_EVENTS || path.join(__dirname, '..', 'gateway', 'events.jsonl');
const ROLES = path.join(path.dirname(EVENTS), 'roles.json');
const MAX_TASKS = 200;

const tasks = new Map(); // id -> task
const clients = new Set();
const gateways = new Map(); // gateway pid -> MCP client name (Claude, Codex, ...)
const HEALTH_STALE = 30; // seconds without a gateway health event before it counts as down
const health = new Map(); // gateway pid -> {ts, status} from its latest health event
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
  if (ev.pid && !gateways.has(ev.pid)) gateways.set(ev.pid, ''); // every event line carries its gateway pid
  if (ev.kind === 'client') { gateways.set(ev.pid, String(ev.name || '')); return null; }
  if (ev.kind === 'health') { health.set(ev.pid, { ts: ev.ts, status: ev.status }); return null; }
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
  for (const p of (cfg.ui && cfg.ui.synaptree_ports) || []) { // synaptree-mcp UI: any HTTP answer on a configured local port
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

// Token-saved totals per time scope, from usage.jsonl (never rotated) plus the rotating events logs, deduped by task id.
function readJsonl(file) {
  try { return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }); } catch { return []; }
}
function usage(now = Date.now() / 1000) {
  const rows = new Map();
  for (const f of [EVENTS + '.1', EVENTS, path.join(path.dirname(EVENTS), 'usage.jsonl')])
    for (const e of readJsonl(f)) if (e && (e.kind === 'task_done' || e.kind === 'task_failed') && e.id) rows.set(e.id, { ...rows.get(e.id), ...e });
  const list = [...rows.values()].map((e) => ({ ts: e.ts, pid: e.pid, id: e.id, ok: e.kind === 'task_done', saved: Number(e.saved) || 0,
    role: e.role || (tasks.get(e.id) || {}).role || '', model: e.model || (tasks.get(e.id) || {}).model || '',
    task: e.task || (tasks.get(e.id) || {}).prompt || '', agent: e.agent || (tasks.get(e.id) || {}).agent || '', calls: Number(e.calls) || 0, input: Number(e.input) || 0, output: Number(e.output) || 0 }));
  const d = new Date(now * 1000);
  const day = Math.min(Math.max(cfgNum('renewal_day', 1), 1), 28);
  let start = new Date(d.getFullYear(), d.getMonth(), day);
  if (start > d) start = new Date(d.getFullYear(), d.getMonth() - 1, day);
  const end = new Date(start.getFullYear(), start.getMonth() + 1, day);
  const hours = cfgNum('window_hours', 5);
  const scopes = {
    window: now - hours * 3600,
    today: new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() / 1000,
    week: now - 7 * 86400,
    month: start.getTime() / 1000,
  };
  const total = (from) => { const r = list.filter((x) => x.ts >= from); return { saved: r.reduce((n, x) => n + x.saved, 0), tasks: r.length, failed: r.filter((x) => !x.ok).length }; };
  const out = { windowHours: hours, renewalDay: day, periodStart: start.getTime() / 1000, periodEnd: end.getTime() / 1000, totals: {} };
  for (const [k, from] of Object.entries(scopes)) out.totals[k] = total(from);
  const group = (from, keyOf) => {
    const g = new Map();
    for (const x of list.filter((r) => r.ts >= from)) {
      const k = keyOf(x); const a = g.get(k) || { key: k, saved: 0, tasks: 0, first: x.ts, last: x.ts };
      a.saved += x.saved; a.tasks += 1; a.first = Math.min(a.first, x.ts); a.last = Math.max(a.last, x.ts); g.set(k, a);
    }
    return [...g.values()].sort((a, b) => b.last - a.last);
  };
  // Per session: which local models ran its tasks in the window (count, failures and tokens saved per model).
  const modelsOf = (pid) => {
    const m = new Map();
    for (const x of list.filter((r) => r.ts >= scopes.window && r.pid === pid)) {
      const k = x.model || '?'; const a = m.get(k) || { model: k, tasks: 0, failed: 0, saved: 0 };
      a.tasks += 1; a.failed += x.ok ? 0 : 1; a.saved += x.saved; m.set(k, a);
    }
    return [...m.values()].sort((a, b) => b.tasks - a.tasks);
  };
  out.sessions = group(scopes.window, (x) => x.pid).map((a) => ({ ...a, pid: a.key, live: alive(a.key), models: modelsOf(a.key) }));
  out.days = group(scopes.month, (x) => new Date(x.ts * 1000).toLocaleDateString('en-CA')).map((a) => ({ ...a, day: a.key })).sort((a, b) => (a.day < b.day ? 1 : -1));
  out.roles = group(scopes.month, (x) => x.role || '?').map((a) => ({ ...a, role: a.key })).sort((a, b) => b.saved - a.saved);
  // Local tasks this period, one row per task id, same columns as Claude's subagent table (input/output are estimates when the backend sends no usage).
  out.localTasks = list.filter((x) => x.ts >= scopes.month).sort((a, b) => b.ts - a.ts).slice(0, 200)
    .map((x) => ({ task: x.task || x.id, persona: x.agent || '?', model: x.model || '?', first: x.ts, calls: x.calls, input: x.input, cached: 0, output: x.output, total: x.input + x.output }));
  out.claude = claudeUsage(scopes);
  return out;
}

// Claude token usage from Claude Code transcripts (~/.claude/projects/**), deduped by message id; subagent files carry the task description.
const PROJECTS = process.env.CLAUDE_PROJECTS || path.join(os.homedir(), '.claude', 'projects');
const fileCache = new Map();
function transcriptFiles() {
  const out = [];
  const walk = (dir, depth) => {
    let ents = []; try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      const f = path.join(dir, e.name);
      if (e.isDirectory() && depth < 3 && e.name !== 'tool-results' && e.name !== 'memory') walk(f, depth + 1);
      else if (e.isFile() && e.name.endsWith('.jsonl')) out.push(f);
    }
  };
  walk(PROJECTS, 0);
  return out;
}
function parseTranscript(f) {
  let st; try { st = fs.statSync(f); } catch { return []; }
  const hit = fileCache.get(f);
  if (hit && hit.key === st.mtimeMs + ':' + st.size) return hit.rows;
  const isSub = path.basename(path.dirname(f)) === 'subagents';
  let meta = {}; if (isSub) { try { meta = JSON.parse(fs.readFileSync(f.replace(/\.jsonl$/, '.meta.json'), 'utf8')); } catch { /* no meta */ } }
  const byId = new Map();
  for (const e of readJsonl(f)) {
    const m = e && e.type === 'assistant' && e.message;
    if (!m || !m.usage || !m.model || m.model === '<synthetic>') continue;
    const u = m.usage, t = Date.parse(e.timestamp) / 1000;
    byId.set(m.id || e.uuid, { ts: t, model: m.model, input: u.input_tokens || 0, cacheRead: u.cache_read_input_tokens || 0,
      cacheWrite: u.cache_creation_input_tokens || 0, output: u.output_tokens || 0,
      agent: isSub ? (e.agentId || path.basename(f, '.jsonl')) : '', task: meta.description || '' });
  }
  const rows = [...byId.values()];
  fileCache.set(f, { key: st.mtimeMs + ':' + st.size, rows });
  return rows;
}
function claudeUsage(scopes) {
  const rows = transcriptFiles().flatMap(parseTranscript);
  const sum = (a) => a.reduce((n, x) => n + x.input + x.cacheRead + x.cacheWrite + x.output, 0);
  const byModel = (from) => {
    const g = new Map();
    for (const x of rows.filter((r) => r.ts >= from)) {
      const a = g.get(x.model) || { model: x.model, calls: 0, input: 0, cacheRead: 0, cacheWrite: 0, output: 0 };
      a.calls++; a.input += x.input; a.cacheRead += x.cacheRead; a.cacheWrite += x.cacheWrite; a.output += x.output; g.set(x.model, a);
    }
    return [...g.values()].map((a) => ({ ...a, total: a.input + a.cacheRead + a.cacheWrite + a.output })).sort((a, b) => b.total - a.total);
  };
  const totals = {}; for (const [k, from] of Object.entries(scopes)) totals[k] = sum(rows.filter((r) => r.ts >= from));
  const g = new Map();
  for (const x of rows.filter((r) => r.agent && r.ts >= scopes.month)) {
    const a = g.get(x.agent) || { agent: x.agent, task: x.task, model: x.model, calls: 0, input: 0, output: 0, cached: 0, first: x.ts };
    a.calls++; a.input += x.input; a.output += x.output; a.cached += x.cacheRead + x.cacheWrite; a.first = Math.min(a.first, x.ts); g.set(x.agent, a);
  }
  const subagents = [...g.values()].map((a) => ({ ...a, total: a.input + a.output + a.cached })).sort((a, b) => b.first - a.first).slice(0, 200);
  return { totals, models: byModel(scopes.month).slice(0, 12), modelsWindow: byModel(scopes.window).slice(0, 12), subagents };
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
  if (url.pathname === '/health') { // gateway health, published by each gateway as health events
    const now = Date.now() / 1000;
    const up = [...health.values()].some((h) => h.status === 'up' && now - h.ts < HEALTH_STALE);
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ status: up ? 'up' : 'down', ts: now }));
  }
  if (url.pathname === '/api/usage') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify(usage()));
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
