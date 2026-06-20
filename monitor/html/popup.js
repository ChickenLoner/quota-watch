"use strict";

/* ICONS — inline SVG (Feather) ------------------------------------------ */
const ICON = {
  refresh: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
  sun:  '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 1.6v2.3M12 20.1v2.3M4.3 4.3l1.6 1.6M18.1 18.1l1.6 1.6M1.6 12h2.3M20.1 12h2.3M4.3 19.7l1.6-1.6M18.1 5.9l1.6-1.6"/></svg>',
  moon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
};

/* STATE ----------------------------------------------------------------- */
const _STORAGE_KEY = 'qw_ui_state';

function _loadStoredState() {
  try { return JSON.parse(localStorage.getItem(_STORAGE_KEY) || '{}'); } catch (_) { return {}; }
}
function _saveState() {
  try {
    const { mode, theme, compact } = state;
    localStorage.setItem(_STORAGE_KEY, JSON.stringify({ mode, theme, compact }));
  } catch (_) {}
}

const _stored = _loadStoredState();
const state = {
  mode:     _stored.mode    || 'focus',
  theme:    _stored.theme   || 'dark',
  themeRot: 0,
  compact:  _stored.compact != null ? _stored.compact : false,
  active:   null,
  menuOpen: false,
  syncing:  false,
  data:     null,
};

const RANK = { crit: 0, err: 1, warn: 2, ok: 3 };
const SEV_LABEL = { ok: 'NOMINAL', warn: 'WARNING', crit: 'CRITICAL', err: 'UNAVAILABLE' };

/* helpers --------------------------------------------------------------- */
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function _fmtReset(iso) {
  if (!iso) return null;
  try {
    const diff = new Date(iso).getTime() - Date.now();
    if (diff <= 0) return null;
    const total_min = Math.floor(diff / 60000);
    if (total_min === 0) return null;
    const d = Math.floor(total_min / 1440);
    const h = Math.floor((total_min % 1440) / 60);
    const m = total_min % 60;
    const local = new Date(iso);
    const hh = local.getHours().toString().padStart(2, '0');
    const mm = local.getMinutes().toString().padStart(2, '0');
    const time = `${hh}:${mm}`;
    if (d > 0) {
      const day = ['SUN','MON','TUE','WED','THU','FRI','SAT'][local.getDay()];
      return `in ${d}d ${h.toString().padStart(2,'0')}h ${m.toString().padStart(2,'0')}m (${day} ${time})`;
    }
    if (h > 0) return `in ${h}h ${m}m (${time})`;
    return `in ${m}m (${time})`;
  } catch (_) { return null; }
}

function _fmtFooter(status) {
  if (!status) return { text: '...', isError: false };
  if (status.text) return { text: status.text, isError: status.is_error || false };
  if (status.refreshing) return { text: 'SYNCING...', isError: false };
  if (status.last_success_time) {
    const elapsed = Math.round(Date.now() / 1000 - status.last_success_time);
    const agoStr  = elapsed < 5 ? 'NOW' : elapsed < 60 ? `${elapsed}S AGO` : `${Math.floor(elapsed / 60)}M AGO`;
    const nextSecs = status.next_poll_time
      ? Math.max(0, Math.round(status.next_poll_time - Date.now() / 1000)) : null;
    const nextStr = nextSecs != null
      ? (nextSecs < 60 ? ` · NEXT IN ${nextSecs}S` : ` · NEXT IN ${Math.floor(nextSecs / 60)}M`) : '';
    const errStr = status.error ? ` · ${status.error}` : '';
    return { text: `UPDATED ${agoStr}${nextStr}${errStr}`, isError: !!status.error };
  }
  return { text: 'SYNCING...', isError: false };
}

function _worstBar(p) {
  if (!p.bars || p.bars.length === 0) return null;
  return p.bars.reduce((a, b) =>
    (RANK[b.sev] < RANK[a.sev] || (RANK[b.sev] === RANK[a.sev] && b.pct > a.pct) ? b : a),
    p.bars[0]);
}

function _sortedProviders() {
  return state.data.providers.slice().sort((a, b) => {
    const ra = RANK[a.statusSev], rb = RANK[b.statusSev];
    if (ra !== rb) return ra - rb;
    const wa = _worstBar(a), wb = _worstBar(b);
    return (wb ? wb.pct : 0) - (wa ? wa.pct : 0);
  });
}

/* fragment builders ----------------------------------------------------- */
function _planBadge(plan, sm) {
  if (!plan) return '';
  return `<span class="qw-plan${sm ? ' sm' : ''}">${esc(plan)}</span>`;
}

function _bigBar(b) {
  const resetStr = _fmtReset(b.resets_at);
  const resetHtml = resetStr
    ? `<div class="qw-reset"><span>⏱</span><span class="lbl">resets</span><span class="val" data-resets="${esc(b.resets_at)}">${esc(resetStr)}</span></div>`
    : '';
  return `<div class="sev-${b.sev}">
    <div class="qw-bar-head">
      <div>
        <div class="qw-bar-label">${esc(b.label)}</div>
        <div class="qw-bar-pct">${Math.round(b.pct)}<small>%</small></div>
      </div>
      <span class="qw-badge sev-${b.sev}">${SEV_LABEL[b.sev] || ''}</span>
    </div>
    <div class="qw-track"><div class="qw-fill" style="width:${Math.min(100, b.pct)}%"></div></div>
    ${resetHtml}
  </div>`;
}

function _cardBar(b) {
  const resetStr = _fmtReset(b.resets_at);
  const resetHtml = resetStr
    ? `<div class="qw-cb-reset">↺ <span data-resets="${esc(b.resets_at)}">${esc(resetStr)}</span></div>`
    : '';
  return `<div class="qw-cb sev-${b.sev}">
    <div class="qw-cb-head"><span class="qw-cb-label">${esc(b.label)}</span><span class="qw-cb-pct">${Math.round(b.pct)}%</span></div>
    <div class="qw-cb-track"><div class="qw-cb-fill" style="width:${Math.min(100, b.pct)}%"></div></div>
    ${resetHtml}
  </div>`;
}

function _errorBlock(p) {
  const icon = p.authStatus === 'auth_error' ? '⚠' : '⚡';
  const msg  = p.errorText || (p.authStatus === 'auth_error' ? 'Authentication required.' : 'Unavailable.');
  const hint = p.reAuthHint ? `<div class="hint">${esc(p.reAuthHint)}</div>` : '';
  return `<div class="qw-error">
    <span class="ico">${icon}</span>
    <div><div class="msg">${esc(msg)}</div>${hint}</div>
  </div>`;
}

function _extraBlock(extra) {
  if (!extra) return '';
  return `<div class="qw-extra">
    <div class="qw-extra-head">
      <span class="lbl">EXTRA USAGE</span>
      <span class="spent">${esc(extra.spent_text)}</span>
      <span class="pct">${esc(extra.pct_text)}</span>
    </div>
    <div class="qw-cb-track"><div class="qw-cb-fill" style="width:${Math.min(100, extra.fill_pct * 100)}%"></div></div>
  </div>`;
}

function _installsBlock(installs) {
  if (!installs || installs.length === 0) return '';
  const rows = installs.map(i =>
    `<div class="qw-install-row"><span>${esc(i.name)}</span><span class="ver">${esc(i.version)}</span></div>`
  ).join('');
  return `<div class="qw-installs">
    <div class="qw-installs-head">
      <span class="lbl">CLAUDE CODE</span>
      <span class="link" data-act="changelog">CHANGELOG</span>
    </div>
    ${rows}
  </div>`;
}

/* header (shared) ------------------------------------------------------- */
function _header(grid) {
  const count = state.data.providers.length;
  const meta  = grid ? `<span class="qw-count">${count} PROVIDERS</span>` : '';
  const icon  = state.theme === 'dark' ? ICON.sun : ICON.moon;
  return `<div class="qw-header">
    <div class="qw-brand"><span class="qw-live"></span><span class="name">QuotaWatch</span>${meta}</div>
    <div class="qw-actions">
      <button class="qw-iconbtn qw-refresh${state.syncing ? ' is-syncing' : ''}" data-act="sync" title="Refresh">
        <span class="ico">${ICON.refresh}</span></button>
      <button class="qw-iconbtn qw-theme is-${state.theme}" data-act="theme" title="Toggle theme">
        <span class="ico" style="transform:rotate(${state.themeRot}deg)">${icon}</span></button>
      <span class="qw-close" data-act="close">&times;</span>
    </div>
  </div>`;
}

/* FOCUS layout ---------------------------------------------------------- */
function _renderFocus() {
  const provs  = state.data.providers;
  const active = provs.find(p => p.id === state.active) || provs[0];
  if (!active) return '';
  state.active = active.id;

  const seg = `<div class="qw-toggles"><div class="qw-seg">
    <button class="active" data-act="focus">FOCUS</button>
    <button data-act="grid">GRID</button>
  </div></div>`;

  const menu = state.menuOpen ? `<div class="qw-menu">${provs.map(p => {
    const w = _worstBar(p);
    const pctHtml = w
      ? `<span class="pct sev-${w.sev}" style="color:var(--c)">${Math.round(w.pct)}%</span>`
      : `<span class="pct sev-err" style="color:var(--c)">—</span>`;
    return `<button class="qw-menu-item${p.id === active.id ? ' active' : ''}" data-pick="${esc(p.id)}">
      <span class="qw-dot" style="background:${esc(p.dot)}"></span>
      <span class="nm">${esc(p.name)}</span>
      ${_planBadge(p.plan, true)}
      ${pctHtml}
      <span class="qw-sevdot sev-${p.statusSev}"></span>
    </button>`;
  }).join('')}</div>` : '';

  const switcher = `<div class="qw-switcher-wrap" data-menu>
    <button class="qw-switcher" data-act="menu">
      <span class="qw-dot" style="background:${esc(active.dot)}"></span>
      <span class="nm">${esc(active.name)}</span>
      ${_planBadge(active.plan, false)}
      <span class="count">${provs.length}&nbsp;&#9662;</span>
    </button>${menu}
  </div>`;

  const account = (active.email || active.plan)
    ? `<div class="qw-account">
        <span class="email">${esc(active.email || '')}</span>
        ${_planBadge(active.plan, false)}
      </div>`
    : '';

  let body;
  if (!active.bars || active.bars.length === 0) {
    body = _errorBlock(active);
  } else {
    body = `<div class="qw-bars">${active.bars.map(_bigBar).join('')}</div>`;
    if (active.id === 'claude') {
      body += _extraBlock(active.extra);
      body += _installsBlock(active.installs);
    }
  }

  const { text, isError } = _fmtFooter(state.data.status);
  const footer = `<div class="qw-footer${isError ? ' is-error' : ''}">
    <span>${esc(text)}</span><span>${esc(state.data.version)}</span>
  </div>`;

  return _header(false) + seg + switcher + account + body + footer;
}

/* GRID layout ----------------------------------------------------------- */
function _renderGrid() {
  const provs = _sortedProviders();

  const toggles = `<div class="qw-toggles">
    <div class="qw-toggle-row">
      <div class="qw-seg">
        <button data-act="focus">FOCUS</button>
        <button class="active" data-act="grid">GRID</button>
      </div>
      <button class="qw-density${state.compact ? ' active' : ''}" data-act="density" title="Toggle density">&#9776;</button>
    </div>
    <div class="qw-sort-note">SORTED BY SEVERITY</div>
  </div>`;

  const cards = provs.map((p, i) => {
    if (state.compact) {
      const sev = p.statusSev;
      let miniHtml;
      if (!p.bars || p.bars.length === 0) {
        miniHtml = `<div class="mini sev-err"><div style="width:0%"></div></div>
                    <span class="pct sev-err" style="color:var(--c)">—</span>`;
      } else if (p.bars.length === 1) {
        const w = p.bars[0];
        miniHtml = `<div class="mini sev-${w.sev}"><div style="width:${Math.min(100, w.pct)}%"></div></div>
                    <span class="pct sev-${w.sev}" style="color:var(--c)">${Math.round(w.pct)}%</span>`;
      } else {
        miniHtml = `<div class="qw-row-multi">${p.bars.map(b =>
          `<div class="qw-row-mini-item sev-${b.sev}">
            <span class="mini-lbl">${esc(b.label)}</span>
            <div class="mini"><div style="width:${Math.min(100, b.pct)}%"></div></div>
            <span class="pct">${Math.round(b.pct)}%</span>
          </div>`).join('')}</div>`;
      }
      return `<div class="qw-row sev-${sev}" style="--i:${i}">
        <span class="qw-dot" style="background:${esc(p.dot)}"></span>
        <span class="nm">${esc(p.name)}</span>
        ${_planBadge(p.plan, true)}
        ${miniHtml}
        <span class="qw-sevdot sev-${sev}"></span>
      </div>`;
    }

    let cardBody;
    if (!p.bars || p.bars.length === 0) {
      cardBody = `<div class="qw-card-bars">${_errorBlock(p)}</div>`;
    } else {
      let bars = `<div class="qw-card-bars">${p.bars.map(_cardBar).join('')}</div>`;
      if (p.id === 'claude') {
        bars += _extraBlock(p.extra);
        bars += _installsBlock(p.installs);
      }
      cardBody = bars;
    }

    return `<div class="qw-card" style="--i:${i}">
      <div class="qw-card-head">
        <div class="qw-card-id">
          <span class="qw-dot" style="background:${esc(p.dot)}"></span>
          <span class="nm">${esc(p.name)}</span>
          ${_planBadge(p.plan, false)}
        </div>
        <span class="qw-chip sev-${p.statusSev}">&#9679; ${SEV_LABEL[p.statusSev] || ''}</span>
      </div>
      ${cardBody}
    </div>`;
  }).join('');

  const { text, isError } = _fmtFooter(state.data.status);
  const footer = `<div class="qw-footer${isError ? ' is-error' : ''}">
    <span>${esc(text)}</span><span>${esc(state.data.version)}</span>
  </div>`;

  return _header(true) + toggles + `<div class="qw-cards">${cards}</div>` + footer;
}

/* render + size reporting ----------------------------------------------- */
const shell = document.getElementById('qwShell');
const panel = document.getElementById('qwPanel');

function render() {
  document.documentElement.setAttribute('data-theme', state.theme);
  panel.className = 'qw-panel' + (state.mode === 'grid' ? ' is-grid' : '');
  panel.innerHTML = state.mode === 'grid' ? _renderGrid() : _renderFocus();
  shell.style.width = (state.mode === 'grid' ? 440 : 360) + 'px';
  _measure();
}

function _measure() {
  const w = state.mode === 'grid' ? 440 : 360;
  const h = panel.offsetHeight;
  shell.style.height = h + 'px';
  if (typeof pywebview !== 'undefined' && pywebview.api) {
    if (pywebview.api.report_size) pywebview.api.report_size(w, h);
    else if (pywebview.api.report_height) pywebview.api.report_height(h);
  }
}

/* animated mode / density transition ---------------------------------- */
const _FADE_MS = 160;
let _animating = false;

function _animatedRender() {
  if (_animating) return;
  _animating = true;

  /* Set target width immediately so shell starts resizing */
  const targetW = state.mode === 'grid' ? 440 : 360;
  shell.style.width = targetW + 'px';

  /* Phase 1 — fade out current content */
  panel.classList.add('is-exit');

  setTimeout(() => {
    /* Phase 2 — swap content while invisible */
    document.documentElement.setAttribute('data-theme', state.theme);
    panel.className = 'qw-panel is-enter is-animated'
      + (state.mode === 'grid' ? ' is-grid' : '');
    panel.innerHTML = state.mode === 'grid' ? _renderGrid() : _renderFocus();

    /* Measure new content → report to pywebview */
    _measure();

    /* Phase 3 — fade in on next frame */
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        panel.classList.remove('is-enter');
        _animating = false;
        /* Remove stagger class after entrance animations finish */
        setTimeout(() => panel.classList.remove('is-animated'), 600);
      });
    });
  }, _FADE_MS);
}

/* event delegation ------------------------------------------------------ */
shell.addEventListener('click', (e) => {
  const pick = e.target.closest('[data-pick]');
  if (pick) { state.active = pick.dataset.pick; state.menuOpen = false; render(); return; }
  const act = e.target.closest('[data-act]');
  if (!act) return;
  switch (act.dataset.act) {
    case 'focus':     state.mode = 'focus'; _saveState(); _animatedRender(); break;
    case 'grid':      state.mode = 'grid'; state.menuOpen = false; _saveState(); _animatedRender(); break;
    case 'menu':      state.menuOpen = !state.menuOpen; render(); break;
    case 'density':   state.compact = !state.compact; _saveState(); _animatedRender(); break;
    case 'theme':     state.theme = state.theme === 'dark' ? 'light' : 'dark'; state.themeRot += 180; _saveState(); render(); break;
    case 'sync':      _doSync(); break;
    case 'close':     if (typeof pywebview !== 'undefined') pywebview.api.close(); break;
    case 'changelog': if (typeof pywebview !== 'undefined') pywebview.api.open_url(); break;
  }
});

document.addEventListener('mousedown', (e) => {
  if (state.menuOpen && !e.target.closest('[data-menu]')) { state.menuOpen = false; render(); }
});

function _doSync() {
  state.syncing = true;
  render();
  if (typeof pywebview !== 'undefined') pywebview.api.refresh();
}

/* reset countdowns — re-derive from absolute ISO every 30s -------------- */
setInterval(() => {
  document.querySelectorAll('[data-resets]').forEach(el => {
    const str = _fmtReset(el.dataset.resets);
    el.textContent = str || '';
  });
}, 30000);

/* footer status ticker every 5s (no full re-render) --------------------- */
setInterval(() => {
  if (!state.data) return;
  const { text, isError } = _fmtFooter(state.data.status);
  document.querySelectorAll('.qw-footer').forEach(el => {
    const s = el.querySelector('span');
    if (s) s.textContent = text;
    el.classList.toggle('is-error', isError);
  });
}, 5000);

/* normalize — defensive defaults on incoming payload -------------------- */
function normalize(payload) {
  if (!payload || !payload.providers) return payload;
  payload.providers.forEach(p => {
    p.bars       = p.bars       || [];
    p.statusSev  = p.statusSev  || 'ok';
    p.errorText  = p.errorText  || null;
    p.reAuthHint = p.reAuthHint || null;
  });
  return payload;
}

/* entry points called from Python --------------------------------------- */
function init(payload) {
  state.data = normalize(payload);
  if (!state.active && state.data.providers.length) {
    state.active = state.data.providers[0].id;
  }
  render();
}

function refreshDone(payload) {
  state.data    = normalize(payload);
  state.syncing = false;
  render();
}
