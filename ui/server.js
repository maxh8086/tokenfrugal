// Live dashboard for the tokenfrugal router: which role/model is running which task.
// Zero dependencies. Tails router/events.jsonl (written by router/events.py) and streams it over SSE.
//   node ui/server.js        ->  http://127.0.0.1:7777   (`port:` in router/ui.yaml; UI_PORT / GATEWAY_EVENTS override)
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { execFile } = require('node:child_process');
const os = require('node:os');

function configPort() { // `port: N` from router/ui.yaml, the same file the launcher reads
  try {
    const m = /^port:\s*(\d+)/m.exec(fs.readFileSync(path.join(__dirname, '..', 'router', 'ui.yaml'), 'utf8'));
    return m ? Number(m[1]) : 7777;
  } catch { return 7777; }
}
function cfgNum(key, dflt) {
  try {
    const m = new RegExp('^' + key + ':\\s*(\\d+)', 'm').exec(fs.readFileSync(path.join(__dirname, '..', 'router', 'ui.yaml'), 'utf8'));
    return m ? Number(m[1]) : dflt;
  } catch { return dflt; }
}
const PORT = Number(process.env.UI_PORT || configPort());
const EVENTS = process.env.GATEWAY_EVENTS || path.join(__dirname, '..', 'router', 'events.jsonl');
const ROLES = path.join(path.dirname(EVENTS), 'roles.json');
const OVERRIDES = path.join(path.dirname(EVENTS), 'config_overrides.json');
const RECONNECT_REQUEST = path.join(path.dirname(EVENTS), 'reconnect_request.json');
const RECONNECT_RESULT = path.join(path.dirname(EVENTS), 'reconnect_result.json');
const MAX_TASKS = 200;

const tasks = new Map(); // id -> task
const clients = new Set();
const gateways = new Map(); // router pid -> MCP client name (Claude, Codex, ...)
const HEALTH_STALE = 30; // seconds without a router health event before it counts as down
const health = new Map(); // router pid -> {ts, status} from its latest health event
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
  if (ev.pid && !gateways.has(ev.pid)) gateways.set(ev.pid, ''); // every event line carries its router pid
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
    Object.assign(t, { status: 'done', summary: ev.summary, endedAt: ev.ts, updatedAt: ev.ts, tool: '', saved: Number(ev.saved) || 0, e2e: Number(ev.e2e) || 0 });
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
    task: e.task || (tasks.get(e.id) || {}).prompt || '', agent: e.agent || (tasks.get(e.id) || {}).agent || '', calls: Number(e.calls) || 0, input: Number(e.input) || 0, output: Number(e.output) || 0, e2e: Number(e.e2e) || 0, secs: Number(e.secs) || 0 }));
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
    .map((x) => ({ task: x.task || x.id, persona: x.agent || '?', model: x.model || '?', first: x.ts, calls: x.calls, input: x.input, cached: 0, output: x.output, total: x.input + x.output,
      e2e: x.e2e, tps: x.secs > 0 ? Math.round((x.output / x.secs) * 10) / 10 : 0 }));
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

// Settings written from the Configuration tab; router/config.py reads the same file at start.
function readOverrides() {
  try { return JSON.parse(fs.readFileSync(OVERRIDES, 'utf8')) || {}; } catch { return {}; }
}
const MCP_MODES = ['allow', 'ask', 'disable'];
function cleanOverrides(input) {
  const out = {};
  const str = (v, max) => (typeof v === 'string' ? v.trim().slice(0, max) : null);
  for (const k of ['workspace', 'bind_writable', 'bind_readonly', 'llm_url']) {
    const v = str(input[k], 500);
    if (v) out[k] = v; // empty means "use .env"
  }
  const t = Number(input.temperature);
  if (input.temperature !== undefined && input.temperature !== '' && t >= 0 && t <= 2) out.temperature = t;
  const m = Number(input.max_tokens);
  if (input.max_tokens !== undefined && input.max_tokens !== '' && Number.isInteger(m) && m >= 1 && m <= 131072) out.max_tokens = m;
  if (input.role_models && typeof input.role_models === 'object' && !Array.isArray(input.role_models)) {
    out.role_models = {};
    for (const [role, model] of Object.entries(input.role_models)) {
      const v = str(model, 200);
      if (v) out.role_models[role] = v;
    }
  }
  // role -> MCP -> tool -> Auto/Ask/Disable (stored as allow/ask/disable)
  if (input.role_tool_modes && typeof input.role_tool_modes === 'object' && !Array.isArray(input.role_tool_modes)) {
    out.role_tool_modes = {};
    for (const [role, mcps] of Object.entries(input.role_tool_modes).slice(0, 60)) {
      if (!mcps || typeof mcps !== 'object' || Array.isArray(mcps)) continue;
      const keptMcps = {};
      for (const [mcp, tools] of Object.entries(mcps).slice(0, 60)) {
        if (!tools || typeof tools !== 'object' || Array.isArray(tools) || mcp.length > 100) continue;
        const keptTools = {};
        for (const [tool, mode] of Object.entries(tools).slice(0, 100)) {
          if (tool.length <= 100 && MCP_MODES.includes(mode)) keptTools[tool] = mode;
        }
        if (Object.keys(keptTools).length) keptMcps[mcp] = keptTools;
      }
      out.role_tool_modes[role] = keptMcps;
    }
  }
  if (input.role_mcps && typeof input.role_mcps === 'object' && !Array.isArray(input.role_mcps)) {
    out.role_mcps = {};
    for (const [role, names] of Object.entries(input.role_mcps)) {
      if (!Array.isArray(names)) continue;
      out.role_mcps[role] = names.filter((n) => typeof n === 'string' && n.length <= 100).slice(0, 60);
    }
  }
  return out;
}

// ---- Benchmark runner: spawns scripts.bench_model and summarises bench/<tag>/*.json
const REPO = path.join(__dirname, '..');
const JOB = { running: false, tag: '', log: [], summary: null, proc: null, code: null };
const sanitize = (s) => (String(s).replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^[._-]+|[._-]+$/g, '') || 'bench');
function urlTag(u) {
  const p = new URL(u);
  return sanitize(p.port ? `${p.hostname}_${p.port}` : p.hostname);
}
function benchSummary(tag) {
  const dir = path.join(REPO, 'bench', tag);
  let files;
  try { files = fs.readdirSync(dir).filter((f) => f.endsWith('.json')); } catch { return null; }
  files = files.map((f) => [f, fs.statSync(path.join(dir, f)).mtimeMs]).sort((a, b) => b[1] - a[1]);
  for (const [f] of files) {
    let data;
    try { data = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')); } catch { continue; }
    const rw = data && data.results && data.results.realworld;
    if (!rw || typeof rw !== 'object') continue;
    let verified = 0, ran = 0; const p50 = [];
    // per-case counts are "passed/total" strings in the result files; plain numbers are accepted too
    const frac = (v) => { const m = String(v ?? '').match(/^(\d+)\s*\/\s*(\d+)$/); return m ? [+m[1], +m[2]] : [Number(v) || 0, 0]; };
    for (const c of Object.values(rw)) {
      const [ok, total] = frac(c.verified);
      verified += ok; ran += String(c.verified).includes('/') ? total : Number(c.ran) || 0;
      if (c.s && typeof c.s.p50 === 'number') p50.push(c.s.p50);
    }
    const cases = Object.keys(rw).length;
    return { tag, verified, ran, cases, pct: ran ? Math.round((100 * verified) / ran) : 0,
      s_per_case: p50.length ? Math.round((10 * p50.reduce((a, b) => a + b, 0)) / p50.length) / 10 : null };
  }
  return null;
}
// Local runs only (Benchmark/results/benchmark.csv; the cloud baseline is excluded). Ranked by number of checks run,
// then pass rate (score / max), then mean seconds per case (faster first). Best run per model.
function csvRows(file) {
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return []; }
  const split = (line) => { // quote-aware, so notes with commas do not shift the columns
    const out = []; let cur = '', q = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (q) { if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; }
      else if (ch === '"') q = true;
      else if (ch === ',') { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur); return out;
  };
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  if (lines.length < 2) return [];
  const head = split(lines[0]);
  return lines.slice(1).map((l) => { const c = split(l); return Object.fromEntries(head.map((h, i) => [h, c[i] ?? ''])); });
}
function benchTop(n) {
  const dir = path.join(REPO, 'Benchmark', 'results');
  const rows = csvRows(path.join(dir, 'benchmark.csv'));
  const num = (r, k) => { const v = parseFloat(r[k]); return Number.isFinite(v) ? v : 0; };
  const best = new Map();
  for (const r of rows) {
    const model = r.builder_model || r.tag;
    if (!model || !num(r, 'max')) continue;
    const pct = Math.round((100 * num(r, 'score')) / num(r, 'max'));
    const speed = num(r, 'mean_s_per_case');
    // Output tokens summed over every check, divided by the wall time those checks took (mean s/case x checks run).
    const tokOut = num(r, 'tokens_out_per_run');
    const tps = speed && num(r, 'max') && tokOut ? Math.round((10 * tokOut) / (speed * num(r, 'max'))) / 10 : null;
    const cur = best.get(model);
    if (!cur || pct > cur.pct || (pct === cur.pct && speed < cur.speed)) {
      best.set(model, { model, tag: r.tag, verified: num(r, 'score'), ran: num(r, 'max'), cases: num(r, 'max'),
        pct, speed, s_per_case: Math.round(10 * speed) / 10 || null, tps });
    }
  }
  return [...best.values()]
    .sort((a, b) => b.ran - a.ran || b.pct - a.pct || a.speed - b.speed).slice(0, n)
    .map(({ speed, ...s }) => s);
}
// Default post pick: among complete local runs (full check count, not partial reruns), the highest composite score.
// composite = 0.6 * pass rate + 0.4 * ln(t/s) / ln(highest t/s among the candidates), so the speed reference moves with the pool.
const POST_PASS_WEIGHT = 0.6;
const POST_SPEED_WEIGHT = 0.4;
function benchLatest() {
  const all = benchTop(Infinity).filter((s) => s.ran && !s.model.startsWith('claude-') && s.tps > 0);
  const full = Math.max(0, ...all.map((s) => s.ran));
  const runs = all.filter((s) => s.ran === full);
  if (!runs.length) return null;
  const maxTps = Math.max(...runs.map((s) => s.tps));
  const scored = runs.map((s) => ({
    ...s,
    composite: POST_PASS_WEIGHT * (s.pct / 100) + POST_SPEED_WEIGHT * (Math.log(s.tps) / Math.log(maxTps)),
  }));
  return scored.sort((a, b) => b.composite - a.composite || b.pct - a.pct)[0];
}
function benchStart(b) {
  const model = typeof b.model === 'string' ? b.model.trim() : '';
  const endpoint = typeof b.url === 'string' ? b.url.trim() : '';
  if (!!model === !!endpoint) throw new Error('give exactly one of model or url');
  if (endpoint && !/^https?:\/\/[^/\s]+/i.test(endpoint)) throw new Error('url must start with http:// or https://');
  if (JOB.running) throw new Error('a benchmark is already running');
  const n = Math.max(1, Math.min(10, parseInt(b.n, 10) || 2));
  const tag = model ? sanitize(model) : urlTag(endpoint);
  const venv = path.join(REPO, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const py = fs.existsSync(venv) ? venv : 'python';
  const args = ['-m', 'scripts.bench_model', '--n', String(n), ...(model ? ['--model', model] : ['--url', endpoint])];
  Object.assign(JOB, { running: true, tag, log: [], summary: null, code: null });
  const { spawn } = require('node:child_process');
  const proc = spawn(py, args, { cwd: REPO, env: { ...process.env, PYTHONPATH: REPO, PYTHONUNBUFFERED: '1' } });
  JOB.proc = proc;
  const push = (d) => { for (const l of String(d).split(/\r?\n/)) if (l.trim()) JOB.log.push(l); if (JOB.log.length > 400) JOB.log.splice(0, JOB.log.length - 400); };
  proc.stdout.on('data', push); proc.stderr.on('data', push);
  proc.on('error', (e) => { push('failed to start: ' + e.message); JOB.running = false; JOB.proc = null; });
  proc.on('close', (code) => { JOB.code = code; JOB.running = false; JOB.proc = null; JOB.summary = benchSummary(tag); if (JOB.summary) JOB.summary.model = model || endpoint; });
  return tag;
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
  if (url.pathname === '/api/config' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify(readOverrides()));
  }
  if (url.pathname === '/api/config' && req.method === 'POST') {
    let body = '';
    let size = 0;
    for await (const chunk of req) {
      size += chunk.length;
      if (size > 65536) return res.writeHead(413).end('too large');
      body += chunk;
    }
    let input;
    try { input = JSON.parse(body || '{}'); } catch { return res.writeHead(400).end('bad json'); }
    if (!input || typeof input !== 'object' || Array.isArray(input)) return res.writeHead(400).end('bad json');
    const saved = cleanOverrides(input);
    try {
      fs.writeFileSync(OVERRIDES + '.tmp', JSON.stringify(saved, null, 2));
      fs.renameSync(OVERRIDES + '.tmp', OVERRIDES);
    } catch { return res.writeHead(500).end('write failed'); }
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ ok: true, saved }));
  }
  // Ask a running router to restart/reconnect one MCP server or all of them (no router restart).
  // The router polls the request file (router/reconnect.py) and writes the outcome to the result file.
  if (url.pathname === '/api/mcp/restart' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) { body += chunk; if (body.length > 4096) return res.writeHead(413).end('too large'); }
    let input;
    try { input = JSON.parse(body || '{}'); } catch { return res.writeHead(400).end('bad json'); }
    const target = input && input.target;
    const known = Object.keys(roles().mcp_catalog || {});
    if (typeof target !== 'string' || (target !== 'all' && !known.includes(target))) return res.writeHead(400).end('unknown target');
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const reply = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); };
    try {
      try { fs.unlinkSync(RECONNECT_RESULT); } catch { /* none yet */ }
      fs.writeFileSync(RECONNECT_REQUEST + '.tmp', JSON.stringify({ id, target }));
      fs.renameSync(RECONNECT_REQUEST + '.tmp', RECONNECT_REQUEST);
    } catch { return reply(500, { ok: false, message: 'could not write request' }); }
    const t0 = Date.now();
    while (Date.now() - t0 < 180000) {
      await new Promise((r) => setTimeout(r, 500));
      try {
        const out = JSON.parse(fs.readFileSync(RECONNECT_RESULT, 'utf8'));
        if (out.id === id) return reply(200, out);
      } catch { /* not written yet */ }
      // still unclaimed after 5s: no router is polling
      if (Date.now() - t0 > 5000 && fs.existsSync(RECONNECT_REQUEST)) {
        try { fs.unlinkSync(RECONNECT_REQUEST); } catch { /* claimed meanwhile */ }
        return reply(200, { ok: false, message: 'no router is running to handle the request' });
      }
    }
    return reply(200, { ok: false, message: 'timed out waiting for the router' });
  }
  if (url.pathname === '/health') { // router health, published by each router as health events
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
  if (url.pathname === '/api/modeltest' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) { body += chunk; if (body.length > 16384) return res.writeHead(413).end('too large'); }
    let b; try { b = JSON.parse(body || '{}'); } catch { return res.writeHead(400).end('bad json'); }
    const out = (o) => { res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(o)); };
    if (!b.model || !b.prompt) return out({ ok: false, error: 'model and prompt required' });
    const t0 = Date.now();
    try {
      const r = await fetch(String(roles().llm_url || '').replace(/\/$/, '') + '/chat/completions', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: String(b.model), messages: [{ role: 'user', content: String(b.prompt) }], temperature: 0.1, max_tokens: 800 }), signal: AbortSignal.timeout(120000) });
      const j = await r.json();
      const text = j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
      return out(text == null ? { ok: false, error: JSON.stringify(j).slice(0, 400) } : { ok: true, text, seconds: Math.round((Date.now() - t0) / 100) / 10 });
    } catch (e) { return out({ ok: false, error: 'LLM endpoint unreachable: ' + e.message }); }
  }
  if (url.pathname === '/api/bench/status') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ running: JOB.running, tag: JOB.tag, log: JOB.log.slice(-60), summary: JOB.summary, code: JOB.code }));
  }
  if (url.pathname === '/api/bench/top') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ top: benchTop(3) }));
  }
  if (url.pathname === '/api/bench/latest') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    return res.end(JSON.stringify({ latest: benchLatest() }));
  }
  if (url.pathname === '/api/bench/stop' && req.method === 'POST') {
    if (JOB.proc) { try { JOB.proc.kill(); } catch { /* gone */ } }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end('{"ok":true}');
  }
  if (url.pathname === '/api/bench/start' && req.method === 'POST') {
    let body = '';
    for await (const chunk of req) { body += chunk; if (body.length > 4096) return res.writeHead(413).end('too large'); }
    let input;
    try { input = JSON.parse(body || '{}'); } catch { return res.writeHead(400).end('bad json'); }
    const reply = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(obj)); };
    try { return reply(200, { ok: true, tag: benchStart(input || {}) }); } catch (e) { return reply(400, { ok: false, error: e.message }); }
  }
  if (url.pathname.startsWith('/Benchmark/')) { // local copy of the published benchmark pages (Explorer tab)
    const root = path.join(__dirname, '..', 'Benchmark');
    const file = path.join(root, decodeURIComponent(url.pathname.slice('/Benchmark/'.length)) || 'index.html');
    if (!file.startsWith(root + path.sep)) return res.writeHead(403).end('forbidden');
    try {
      const types = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png' };
      res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
      return res.end(fs.readFileSync(file));
    } catch { return res.writeHead(404).end('not found'); }
  }
  if (url.pathname === '/logo.svg') {
    try {
      const svg = fs.readFileSync(path.join(__dirname, '..', 'assets', 'logo.svg'));
      res.writeHead(200, { 'Content-Type': 'image/svg+xml' });
      return res.end(svg);
    } catch { return res.writeHead(404).end('not found'); }
  }
  if (url.pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    return res.end(fs.readFileSync(path.join(__dirname, 'index.html')));
  }
  if (url.pathname === '/post.html') { // ready-to-post page: text, benchmark image, LinkedIn/X links
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    return res.end(fs.readFileSync(path.join(__dirname, 'post.html')));
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
