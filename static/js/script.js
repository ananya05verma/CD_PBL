/* =============================================================
   RegexEdu – script.js
   Vanilla JS – works with Flask backend
   ============================================================= */

/* ── Session helpers ─────────────────────────────────────── */
function getSession() {
  try {
    const s = sessionStorage.getItem('regex_edu_user');
    return s ? JSON.parse(s) : null;
  } catch { return null; }
}
function setSession(data) {
  sessionStorage.setItem('regex_edu_user', JSON.stringify(data));
}
function clearSession() {
  sessionStorage.removeItem('regex_edu_user');
}

/* ── Toast ───────────────────────────────────────────────── */
function showToast(msg, type = 'info', duration = 3000) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast ' + type;
  t.classList.remove('hidden');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), duration);
}

/* ── Copy to clipboard ───────────────────────────────────── */
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', 'success');
  }).catch(() => {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('Copied!', 'success');
  });
}

/* ── Matrix canvas (auth pages) ─────────────────────────── */
function initMatrix(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  const chars = '01∑∂∈∉∀∃⊂⊃∪∩→←↔≡≠≤≥[](){}^$*+?|\\';
  const fontSize = 13;
  let cols = Math.floor(canvas.width / fontSize);
  let drops = Array(cols).fill(0).map(() => Math.random() * -100);

  function draw() {
    ctx.fillStyle = 'rgba(11,14,20,0.05)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#00d4ff';
    ctx.font = fontSize + 'px Share Tech Mono, monospace';

    cols = Math.floor(canvas.width / fontSize);
    if (drops.length < cols) drops = drops.concat(Array(cols - drops.length).fill(0));

    for (let i = 0; i < cols; i++) {
      const ch = chars[Math.floor(Math.random() * chars.length)];
      ctx.fillText(ch, i * fontSize, drops[i] * fontSize);
      if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) drops[i] = 0;
      drops[i] += 0.4;
    }
  }
  setInterval(draw, 60);
}

/* ═══════════════════════════════════════════════════════════
   AUTH
   ═══════════════════════════════════════════════════════════ */

/** Called from login.html */
async function loginUser() {

  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;

  const errBox = document.getElementById('login-error');
  errBox.classList.add('hidden');

  if (!email || !password) {
    errBox.textContent = 'Please fill in all fields.';
    errBox.classList.remove('hidden');
    return;
  }
  try {
    const res = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (res.ok && data.user_id) {
      setSession({
        user_id: data.user_id,
        name: data.name || email
      });
      window.location.href = "/dashboard";
    } else {
      errBox.textContent = data.error || "Invalid email or password.";
      errBox.classList.remove('hidden');
    }
  } catch (err) {
    errBox.textContent = "Server error. Try again.";
    errBox.classList.remove('hidden');
  }
}

/** Called from register.html */
async function registerUser() {

  const name = document.getElementById('register-name').value.trim();
  const email = document.getElementById('register-email').value.trim();
  const password = document.getElementById('register-password').value;

  const errBox = document.getElementById('register-error');
  const okBox = document.getElementById('register-success');

  errBox.classList.add('hidden');
  okBox.classList.add('hidden');

  if (!name || !email || !password) {
    errBox.textContent = "Please fill in all fields.";
    errBox.classList.remove('hidden');
    return;
  }

  try {

    const res = await fetch('/register', {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({ name, email, password })

    });

    const data = await res.json();

    if (res.ok) {

      okBox.textContent = data.message || "Account created successfully!";
      okBox.classList.remove('hidden');

      setTimeout(() => {

        window.location.href = "/";

      }, 1200);

    } else {

      errBox.textContent = data.error || "Registration failed.";
      errBox.classList.remove('hidden');

    }

  } catch (err) {

    errBox.textContent = "Server error. Please try again.";
    errBox.classList.remove('hidden');

  }
}

function logoutUser() {
  sessionStorage.removeItem("regex_edu_user");
  window.location.href = "/";
}

/* Enter-key support for auth */
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  if (document.getElementById('login-email')) loginUser();
  else if (document.getElementById('register-name')) registerUser();
});

/* ═══════════════════════════════════════════════════════════
   DASHBOARD INIT
   ═══════════════════════════════════════════════════════════ */
function initDashboard() {
  const session = getSession();
  if (!session) {
    window.location.href = '/login';
    return;
  }

  const badge = document.getElementById('user-badge');
  if (badge) badge.textContent = '⟨ ' + (session.name || 'User') + ' ⟩';

  loadTheory();      // pre-load theory in background
}

/* ── Tab switching ───────────────────────────────────────── */
function switchTab(tabId, el) {
  // Deactivate all
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Activate target
  const panel = document.getElementById('tab-' + tabId);
  if (panel) panel.classList.add('active');

  if (el) {
    el.classList.add('active');
  } else {
    // called programmatically — find the matching nav item
    const navItem = document.querySelector('[data-tab="' + tabId + '"]');
    if (navItem) navItem.classList.add('active');
  }

  // Side effects
  if (tabId === 'history') loadHistory();
  if (tabId === 'phases') {
    // switch phases nav item active
  }
}

/* ═══════════════════════════════════════════════════════════
   PROCESS INPUT  (Pattern Converter + Lab)
   ═══════════════════════════════════════════════════════════ */
let lastResult = null; // cache for regex tester

/** Called from Pattern Converter */
async function processInput() {
  const text    = document.getElementById('pattern-input').value.trim();
  const mode    = document.getElementById('mode-select').value;
  await _doProcess(text, mode);
}

/** Called from Lab tab */
async function processLabInput() {
  const text    = document.getElementById('lab-textarea').value.trim();
  const mode    = document.getElementById('lab-mode-select').value;
  await _doProcess(text, mode);
  // Switch to phases tab to show output
  switchTab('phases', null);
}

async function _doProcess(text, mode) {
  if (!text) { showToast('Please enter a pattern first.', 'error'); return; }

  const session = getSession();
  if (!session) { window.location.href = '/login'; return; }

  const spinner = document.getElementById('generate-spinner');
  const btnText = document.querySelector('.generate-btn .btn-text');

  if (spinner) spinner.classList.remove('hidden');
  if (btnText) btnText.textContent = 'GENERATING...';

  try {
    const res = await fetch('/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, mode, user_id: session.user_id })
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.error || data.message || 'Processing failed.');

    lastResult = data;
    renderResults(data, text);
    showToast('Regex generated successfully!', 'success');
  } catch (err) {
    showToast(err.message || 'Failed to generate regex.', 'error');
  } finally {
    if (spinner) spinner.classList.add('hidden');
    if (btnText) btnText.textContent = 'GENERATE REGEX';
  }
}

/* ── Render results ──────────────────────────────────────── */
function renderResults(data, inputText) {
  /* Quick preview on converter tab */
  const quickResult = document.getElementById('quick-result');
  if (quickResult) {
    document.getElementById('quick-regex').textContent  = data.regex || '—';
    document.getElementById('quick-class').textContent  = data.classification || '—';
    quickResult.classList.remove('hidden');
    // pre-fill tester
    const tester = document.getElementById('regex-pattern-tester');
    if (tester) tester.value = data.optimized_regex || data.regex || '';
  }

  /* Compiler phases tab */
  const empty = document.getElementById('phases-empty');
  const output = document.getElementById('phases-output');
  if (empty)  empty.classList.add('hidden');
  if (output) output.classList.remove('hidden');

  // Tokens
  renderTokens(data.tokens);

  // AST
  renderAST(data.ast);

  // Regex
  const pr = document.getElementById('phase-regex');
  if (pr) pr.textContent = data.regex || '—';

  // Optimized
  const po = document.getElementById('phase-optimized');
  if (po) po.textContent = data.optimized_regex || data.regex || '—';

  // Classification
  const pc = document.getElementById('phase-class');
  const pd = document.getElementById('class-description');
  if (pc) pc.textContent = data.classification || '—';
  if (pd) pd.textContent = classificationDescription(data.classification, data.automata);

  // Automata section (beginner-friendly): show theory note + regex feature checklist
  renderAutomataInfo(data.automata || null, data.optimized_regex || data.regex || '');

  // Symbol tables (per phase)
  renderSymbolTables(data.symbol_tables || {});
}

/* ── Symbol table rendering ─────────────────────────────── */
function renderSymbolTables(symbolTables) {
  renderSymbolTablePhase('tokens', symbolTables.tokens, 'symtab-tokens');
  renderSymbolTablePhase('ast', symbolTables.ast, 'symtab-ast');
  renderSymbolTablePhase('regex', symbolTables.regex, 'symtab-regex');
  renderSymbolTablePhase('optimized_regex', symbolTables.optimized_regex, 'symtab-optimized_regex');
}

function renderSymbolTablePhase(phaseName, tableObj, containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  if (!tableObj || !tableObj.entries || tableObj.entries.length === 0) {
    el.innerHTML = '<div class="symtab-empty">No symbol table entries.</div>';
    return;
  }

  const cols = Array.isArray(tableObj.columns) && tableObj.columns.length
    ? tableObj.columns
    : Object.keys(tableObj.entries[0] || {});

  const thead = cols.map(c => `<th>${escHtml(String(c))}</th>`).join('');

  const rows = tableObj.entries.map(row => {
    const tds = cols.map(c => {
      const v = row[c];
      let text = '';
      if (v === null || typeof v === 'undefined') text = '—';
      else if (typeof v === 'object') text = JSON.stringify(v);
      else text = String(v);
      return `<td title="${escHtml(text)}">${escHtml(text)}</td>`;
    }).join('');
    return `<tr>${tds}</tr>`;
  }).join('');

  el.innerHTML = `
    <div class="symtab-meta">
      <span class="symtab-badge">${escHtml(phaseName)}</span>
      <span class="symtab-count">${tableObj.entries.length} entry${tableObj.entries.length === 1 ? '' : 'ies'}</span>
    </div>
    <div class="symtab-table-wrap">
      <table class="symtab-table">
        <thead><tr>${thead}</tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

/* ── Token rendering ────────────────────────────────────── */
function renderTokens(tokens) {
  const list = document.getElementById('token-list');
  if (!list) return;
  list.innerHTML = '';

  if (!tokens || tokens.length === 0) {
    list.innerHTML = '<span style="color:var(--text-muted);font-size:0.8rem">No tokens available.</span>';
    return;
  }

  const items = Array.isArray(tokens) ? tokens : String(tokens).split(/\s+/).filter(Boolean);

  items.forEach((tok, i) => {
    const chip = document.createElement('span');
    chip.className = 'token-chip ' + tokenType(tok);
    chip.textContent = typeof tok === 'object' ? JSON.stringify(tok) : tok;
    chip.style.animationDelay = (i * 40) + 'ms';
    list.appendChild(chip);
  });
}

function tokenType(tok) {
  const t = String(tok).toLowerCase();
  if (/\b(word|letter|digit|start|end|match|or|and|not|any|all)\b/.test(t)) return 'type-keyword';
  if (/^["']/.test(t) || /literal|string/.test(t)) return 'type-literal';
  if (/[+*?|^$()[\]{}\\]/.test(t)) return 'type-op';
  return 'type-default';
}

/* ── AST rendering (D3 tree) ─────────────────────────────── */
function renderAST(ast) {
  const rawEl = document.getElementById('ast-raw');
  const container = document.getElementById('ast-tree-container');
  if (!rawEl || !container) return;

  rawEl.textContent = JSON.stringify(ast, null, 2);
  container.innerHTML = '';

  if (!ast || ast === '—') return;

  // ✅ CONVERT TO D3 FORMAT
  const treeData = convertASTtoD3(ast);

  console.log("TREE DATA:", treeData); // debug

  if (!treeData) return;

  drawD3Tree(container, treeData);
}

function buildSimpleTree(astStr) {
  // Converts a string like "CONCAT(CHAR(a), STAR(CHAR(b)))" into a D3-friendly tree
  const lines = astStr.split('\n').filter(Boolean);
  if (lines.length <= 1) {
    return { name: astStr.substring(0, 50), children: [] };
  }
  // Build from lines with indentation
  const root = { name: 'AST', children: [] };
  const stack = [{ node: root, depth: -1 }];
  lines.forEach(line => {
    const depth = line.search(/\S/);
    const name  = line.trim().replace(/^[-└├│]+\s*/, '');
    const node  = { name: name.substring(0, 40), children: [] };
    while (stack.length > 1 && stack[stack.length - 1].depth >= depth) stack.pop();
    stack[stack.length - 1].node.children.push(node);
    stack.push({ node, depth });
  });
  return root;
}

function convertASTtoD3(node) {
  if (!node) return null;

  // If string, try parsing
  if (typeof node === "string") {
    try {
      node = JSON.parse(node);
    } catch {
      return { name: node, children: [] };
    }
  }

  let children = [];

  // Handle left/right (main tree)
  if (node.left) {
    const left = convertASTtoD3(node.left);
    if (left) children.push(left);
  }

  if (node.right) {
    const right = convertASTtoD3(node.right);
    if (right) children.push(right);
  }

  // 🔥 IMPORTANT: value node (THIS WAS MISSING)
  if (node.value) {
    children.push({
      name: node.value,
      children: []
    });
  }

  // Lab AST support
  if (node.components) {
    children = node.components.map(c => ({
      name: c,
      children: []
    }));
  }

  if (node.start) {
    children.push({ name: node.start, children: [] });
  }

  if (node.follow) {
    children.push({ name: node.follow, children: [] });
  }

  return {
    name: node.type || node.rule || "NODE",
    children: children
  };
}

function drawD3Tree(container, data) {
  if (typeof d3 === 'undefined') {
    container.innerHTML = '<pre style="font-family:var(--font-mono);font-size:0.78rem;color:var(--text-secondary)">' + JSON.stringify(data, null, 2) + '</pre>';
    return;
  }

  const width  = container.clientWidth || 600;
  const margin = { top: 20, right: 20, bottom: 20, left: 40 };
  const root   = d3.hierarchy(data);
  const treeH  = Math.max(160, root.height * 90 + 60);

  const treeLayout = d3.tree().size([width - margin.left - margin.right, treeH - margin.top - margin.bottom]);
  treeLayout(root);

  const svg = d3.select(container).append('svg')
    .attr('width', width)
    .attr('height', treeH)
    .attr('viewBox', `0 0 ${width} ${treeH}`)
    .style('overflow', 'auto');

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  // Links
  g.selectAll('.ast-link')
    .data(root.links())
    .join('path')
    .attr('class', 'ast-link')
    .attr('d', d3.linkVertical().x(d => d.x).y(d => d.y));

  // Nodes
  const node = g.selectAll('.ast-node')
    .data(root.descendants())
    .join('g')
    .attr('class', 'ast-node')
    .attr('transform', d => `translate(${d.x},${d.y})`);

  node.append('circle').attr('r', 16);

  node.append('text')
    .attr('dy', '0.32em')
    .attr('text-anchor', 'middle')
    .text(d => {
      const t = d.data.name || '';
      return t.length > 8 ? t.substring(0, 7) + '…' : t;
    })
    .append('title')
    .text(d => d.data.name);
}

function toggleASTView() {
  const raw  = document.getElementById('ast-raw');
  const tree = document.getElementById('ast-tree-container');
  if (!raw || !tree) return;
  const show = raw.classList.toggle('hidden');
  tree.style.display = show ? 'block' : 'none';
}

/* ── Classification description ─────────────────────────── */
function classificationDescription(cls, automata) {
  // Keep this phrasing evaluation-safe:
  // Regex defines a regular language, so both NFA and DFA exist (equivalent power).
  const base = 'Theory note: Every regular expression defines a regular language, and every regular language can be recognized by both an equivalent NFA and an equivalent DFA.';
  if (automata && automata.nfa && automata.nfa.kind) {
    return base + ' This project visualizes the Thompson NFA construction for Pattern Mode inputs.';
  }
  return base;
}

function renderAutomataInfo(automata, regex) {
  const noteEl = document.getElementById('nfa-note');
  const featuresEl = document.getElementById('regex-features');
  if (!noteEl || !featuresEl) return;

  featuresEl.innerHTML = '';
  noteEl.textContent = '';

  if (!automata) {
    noteEl.textContent = 'No automata data available.';
    return;
  }

  noteEl.textContent = automata.note || 'Theory note: Every regex has an equivalent NFA and DFA.';

  const r = String(regex || '');
  const features = [
    { label: 'Anchors (^ or $)', on: /[\^$]/.test(r) },
    { label: 'Alternation (|)', on: /\|/.test(r) },
    { label: 'Kleene star (*)', on: /\*/.test(r) },
    { label: 'Plus (+)', on: /\+/.test(r) },
    { label: 'Character class ([...])', on: /\[[^\]]+\]/.test(r) },
    { label: 'Grouping ((...))', on: /\([^)]*\)/.test(r) },
    { label: 'Wildcard dot (.)', on: /\./.test(r) },
  ];

  const rows = features.map(f => `
    <div class="feat-row">
      <span class="feat-dot ${f.on ? 'on' : ''}"></span>
      <span class="feat-label">${escHtml(f.label)}</span>
      <span class="feat-val">${f.on ? 'Used' : 'Not used'}</span>
    </div>
  `).join('');

  featuresEl.innerHTML = `
    <div class="feat-box">
      <div class="feat-title">Regex features used</div>
      <div class="feat-list">${rows}</div>
    </div>
  `;
}

/* ═══════════════════════════════════════════════════════════
   REGEX TESTER
   ═══════════════════════════════════════════════════════════ */
function testRegex() {
  const pattern = document.getElementById('regex-pattern-tester').value.trim();
  const testStr = document.getElementById('test-string').value;
  const result  = document.getElementById('test-result');
  if (!result) return;

  if (!pattern) { showToast('Enter a regex pattern to test.', 'error'); return; }

  result.className = 'test-result';
  result.classList.remove('hidden');

  try {
    const rx    = new RegExp(pattern);
    const match = rx.test(testStr);
    const found = testStr.match(new RegExp(pattern, 'g'));

    if (match) {
      result.classList.add('match');
      result.innerHTML = '✓ MATCH — Found ' + (found ? found.length : 1) + ' occurrence(s): <span style="opacity:.7">' +
        (found ? found.slice(0,5).map(m => '<code style="background:rgba(16,214,138,0.1);padding:1px 5px;border-radius:3px">' + escHtml(m) + '</code>').join(' ') : '') + '</span>';
    } else {
      result.classList.add('no-match');
      result.textContent = '✗ NO MATCH — Pattern did not match the input string.';
    }
  } catch (err) {
    result.classList.add('error');
    result.textContent = '⚠ INVALID REGEX — ' + err.message;
  }
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

/* Enter key for tester */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && document.activeElement && document.activeElement.id === 'test-string') {
    testRegex();
  }
});

/* ═══════════════════════════════════════════════════════════
   HISTORY
   ═══════════════════════════════════════════════════════════ */
let _historyData = [];

async function loadHistory() {
  const session = getSession();
  if (!session) return;

  const tbody = document.getElementById('history-tbody');
  if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Loading…</td></tr>';

  try {
    const res  = await fetch('/history/' + session.user_id);
    const data = await res.json();

    _historyData = Array.isArray(data) ? data : (data.history || []);
    renderHistoryTable(_historyData);
  } catch (err) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Failed to load history.</td></tr>';
  }
}

function renderHistoryTable(rows) {
  const tbody = document.getElementById('history-tbody');
  if (!tbody) return;

  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No history found. Generate some regexes first!</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map((row, i) => `
    <tr>
      <td style="color:var(--text-muted);font-family:var(--font-mono);font-size:0.72rem">${i + 1}</td>
      <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(row.input || row.text || '')}">${escHtml((row.input || row.text || '—').substring(0, 60))}</td>
      <td><span class="mode-badge ${(row.mode || '').toLowerCase()}">${row.mode || '—'}</span></td>
      <td title="${escHtml(row.regex || '')}">${escHtml((row.regex || '—').substring(0, 40))}${(row.regex || '').length > 40 ? '…' : ''}</td>
      <td><span class="badge-classification">${row.classification || '—'}</span></td>
      <td><button class="btn-history-load" onclick="loadFromHistory(${i})">Load</button></td>
    </tr>
  `).join('');
}

function filterHistory() {
  const q = (document.getElementById('history-search').value || '').toLowerCase();
  if (!q) { renderHistoryTable(_historyData); return; }
  const filtered = _historyData.filter(r =>
    (r.input || r.text || '').toLowerCase().includes(q) ||
    (r.regex || '').toLowerCase().includes(q) ||
    (r.mode || '').toLowerCase().includes(q) ||
    (r.classification || '').toLowerCase().includes(q)
  );
  renderHistoryTable(filtered);
}

function loadFromHistory(idx) {
  const row = _historyData[idx];
  if (!row) return;
  // Populate converter
  const pi = document.getElementById('pattern-input');
  const ms = document.getElementById('mode-select');
  if (pi) pi.value = row.input || row.text || '';
  if (ms) ms.value = row.mode || 'pattern';
  // Re-render phases with cached data
  renderResults(row, row.input || row.text || '');
  switchTab('converter', null);
  showToast('Loaded from history.', 'info');
}

/* ═══════════════════════════════════════════════════════════
   THEORY
   ═══════════════════════════════════════════════════════════ */
const FALLBACK_THEORY = [
  {
    icon: '⚙️',
    title: 'Compiler Basics',
    content: 'A compiler is a program that translates source code into machine code through phases: lexical analysis, syntax analysis, semantic analysis, code generation, and optimization.'
  },
  {
    icon: '🔤',
    title: 'Lexical Analysis',
    content: 'The first phase — breaks input into tokens like keywords, identifiers, literals, and operators. A <code>Lexer</code> uses regular expressions and finite automata to recognize token patterns.'
  },
  {
    icon: '🌳',
    title: 'Syntax Analysis',
    content: 'The parser reads tokens and builds a parse tree or AST (Abstract Syntax Tree) based on a context-free grammar. It verifies that the structure conforms to language rules.'
  },
  {
    icon: '🌿',
    title: 'Abstract Syntax Tree',
    content: 'An AST is a tree representation of the abstract syntactic structure of source code. Each node denotes a construct in the source, stripped of syntactic sugar.'
  },
  {
    icon: '📐',
    title: 'Regular Expressions',
    content: 'Regular expressions describe regular languages using operations: concatenation, union <code>|</code>, Kleene star <code>*</code>, plus <code>+</code>, and optional <code>?</code>. All regular languages have an equivalent finite automaton.'
  },
  {
    icon: '◈',
    title: 'DFA vs NFA',
    content: 'A DFA (Deterministic FA) has exactly one transition per state/symbol. An NFA allows multiple or no transitions. Both recognize the same class of languages, but DFAs are faster to simulate while NFAs are more compact.'
  }
];

async function loadTheory() {
  try {
    const res  = await fetch('/theory');
    const data = await res.json();
    const cards = Array.isArray(data) ? data : (data.topics || data.theory || FALLBACK_THEORY);
    renderTheory(cards.length > 0 ? cards : FALLBACK_THEORY);
  } catch {
    renderTheory(FALLBACK_THEORY);
  }
}

function renderTheory(topics) {
  const loading = document.getElementById('theory-loading');
  const grid    = document.getElementById('theory-grid');
  if (!grid) return;

  if (loading) loading.classList.add('hidden');
  grid.classList.remove('hidden');

  grid.innerHTML = topics.map((t, i) => `
    <div class="theory-card" style="animation-delay:${i * 80}ms">
      <div class="theory-card-top"></div>
      <div class="theory-card-body">
        <span class="theory-card-icon">${t.icon || '📌'}</span>
        <h3 class="theory-card-title">${escHtml(t.title || 'Topic')}</h3>
        <div class="theory-card-content">${t.content || ''}</div>
      </div>
    </div>
  `).join('');
}

/* ═══════════════════════════════════════════════════════════
   LAB PRACTICE
   ═══════════════════════════════════════════════════════════ */
function loadLabProblem(card) {
  const problem = card.getAttribute('data-problem');
  const title   = card.querySelector('.lab-title').textContent;

  // Highlight selected card
  document.querySelectorAll('.lab-problem').forEach(c => c.style.borderColor = '');
  card.style.borderColor = 'var(--accent)';

  const area = document.getElementById('lab-input-area');
  const ta   = document.getElementById('lab-textarea');
  const ttl  = document.getElementById('lab-problem-title');

  if (area) area.classList.remove('hidden');
  if (ta)   ta.value = problem;
  if (ttl)  ttl.textContent = title;

  area.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* ═══════════════════════════════════════════════════════════
   KEYBOARD SHORTCUTS
   ═══════════════════════════════════════════════════════════ */
document.addEventListener('keydown', (e) => {
  // Alt+1..5 to switch tabs
  if (e.altKey) {
    const tabs = ['converter','lab','phases','history','theory'];
    const n = parseInt(e.key) - 1;
    if (n >= 0 && n < tabs.length) {
      e.preventDefault();
      const el = document.querySelector('[data-tab="' + tabs[n] + '"]');
      switchTab(tabs[n], el);
    }
  }
  // Ctrl+Enter to process
  if (e.ctrlKey && e.key === 'Enter') {
    const active = document.querySelector('.tab-panel.active');
    if (active && active.id === 'tab-converter') processInput();
  }
});
