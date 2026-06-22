"use strict";

/* ICONS — inline SVG (Feather) ------------------------------------------ */
const ICON = {
  refresh: '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
  sun:  '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 1.6v2.3M12 20.1v2.3M4.3 4.3l1.6 1.6M18.1 18.1l1.6 1.6M1.6 12h2.3M20.1 12h2.3M4.3 19.7l1.6-1.6M18.1 5.9l1.6-1.6"/></svg>',
  moon: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
};

/* PROVIDER LOGOS — base64 PNG 32×32 ------------------------------------ */
const LOGOS = {
  claude:      'data:image/png;base64,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',
  antigravity:      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAHp0lEQVR4nK1WbYycVRV+zrn3/ZqZnZnd7i4lSn+Uis02KKR+tKBsQTRB0ZCQIZoYiQblFxpiiNAq2xFCoyiiJsJKIiFiTHb5oSV+JP5gKzEWLAKFNsQYv4hAd9tupzsz79e995g72yIfu3Sxnj933nfufZ7nPPece1/C2wgRMBFc72fvuDbM9M32qLoQnZB1N3zBLqkfRQ8+/aAA5OcSIGvB5DWTz0B58pce3bhH1aJHLAeXFiqol0rXRKv3hWH4k/6nP/jAYHKrxaeF/F8EzMy0FF0H+/zvJm5ORqu3vpxG9oiJXJdi9DjCCQncoiOTVJMbutde+i2anbVexFqwaS22++HxJ9//Lp3Tc9yD4g5x2FUULCmEJxnhEiHoQqI+bL0gXWb2ksovfv9HabXUQMzZODA72yIiyJGi2u7EzfDfRV2OYJiOYB0WMIJjNIwON9BTNepxREbHSEnvGSyemJCzcmBKprhNbTd94JrzKbeHi54O0A+g+yFF3QBJT6PaBWo9g1qvRK2fI0lzN1w6Ru62Nfb++okzuaDfUt7cnHfIdcrgc5w0w8UTMLCJVjZBJBESURgioE4lCs5gOIVVfdcky2nZuwHAE2flAAQ0NTepMt74XEnVzUsnQidpjTmtIEwTVPoaQ32gmRYYTvsYTntopEsyWqYUZN35uulvGtu7d8l3xGptyatxt2ZaCgTpBO++qEvNzfMnh2SxHOVjZgxH7TlYsOdgXs7FPNZjntZjgdfjqBrHYjBGR7jhkIyNH1ejly2Drd4RerU/JsYmBu4slfWrbDSCThHYvGxoU9ZB5RC0rSBzGiUAwyWs6sHpBGIj2DByDeRkjL4awK/m5pex3paA9hycH7v50McK00C3iKnMm7BlAzA1+DowTg8mOTKASgAdQySEQ8ih61MUyRWPTU7py/e1zWo8vOLbqSlGu+1aj317fVo0Ll7q1JAX67goRlAWwyjMMArbQC4N9KmBLjfQUU0sBiM4Ho7ieDTKL+umLCXjm4rza5s9pHjMtQqYPPW+30m2l2p9Ne03rSmGyZTDAwecrcG6KkqpIEcFKVfQVXWc1A10giYWo3VehM3qG/hotG5QB3PYsXYB2LFjMKRFc0dejvqsxZZNiKlDbBUwFYiLYRHDUISCYmQqRk9XcTJYFnEiGsGxeB26lfEB2MKWhRW7gFYUIEK+cS796S+fEjrn4nwpdlLWWTyxSUAuACyDwFAQaHEIvRwpUZUCQy7DkEvdKJWc5CdeHI/MBZ9vX54BQgDJWzswNcUgku0PP7KhLOsTRS+GlDUakNsYcAHEKStQBiDnwM6SMiW0LThExt6JCrpBjY9xIv3K6HmvuPoWD91qzb6Jj9+8/8t7VWbj20WfG9msasVUaUBuQ8CxU2GodKI1BZpJa+Yk0EgiVUK5nIOBiL5K0NVVm9XOxaKuTnrMiYkWrbkNS1O5UnEdzorQgDwAiXIqDtnk2C/AwzA4xCidOL5AC32G4+iKMi/EW0jMIGHqUAwV1j4C4J7Dh2dlTTWwdXo6yIsPHVY0tklSduxiJhdYn7ktXPvp29TuldZt22NuCgL1AzaljeA4gkVNM0WmfzwEbfzxrSOdU/UlKzswJYw2uV7x4Qs1hs6XDEIuYrHK6iRUpu/ufmaX2t1qiZqfAI0fXj7f/W8/7ruNfrhtj9FREtxTpMYSs+o641SlOeLy9BIAv2nNgmcBu6KASYD3DQ62+OMqHiPpZwZOkQojZVJ34Jmd/LXJQvTsbtjXZrEcQlunJdh/I31v+132o1FFX5VnxoK0ZIpJwJ/0AuYPvd51fu3DPg/sby4XXoOcfMUToAlOhJ29yZOOb/F35BvJB7spV78E6y0W8JfzwmWWmQoh7hWgDPoTk1N/j/e1/bnt2/GNAlozyvf+lu+++B6moYtdVgqgRMcBuwIzf/56uL81I2r2Olr146LdJje5G2r/TvqrMXwfYuZStEsL61wYbEiq77zMk7dm/svLr9q/3CICqVyvgzqTaMOk2RWucFze7jObPXTmT22/hb6WSsGeIsWi02ADZQ0DBvyFlQ8iEfL2b50+3iAXflYy6/sdOlYsJT9wcGf8F188vkDPJMDP8bX0zC5asBZ3Uwg2DpSmEEP8qSvvlQ2zrWWRrwrwtvl9LRb1jUFcG5PSlkorZVO36CJ8009eS/avq6UpYVmH7+dd/AMBlLEoJUaSp/iq5zp94bGf6G274DsnR4nCWyS1wlCiImbn5LaDt9B8awtoTdmfDiLxa566kfoAvuLTcwDlfTin8cVtd8mmfW1Y38689WUoDx6Xwb1BFI1KKYVOVGh6+O2zu/T0mQpvtfBr/NoDO2lv2XMPcRWBsShEIxHGfb4W/PkxaIf33pl+SVfjadu3OUcqgsE/TYoPHNyNBex+m9m/NkSodR34b1ciwnH8QcW4yKbIwipi08Ptf9pJd9BFd5ZXIeBH4WBVwKGzOGoNLj+4i54/fTLibOIUxpY75Lw4xJwKsNFmyFWIyJa4noX5ISZWp8hfcDl2eHJv31mT+/AYU8KHvkEvZgV2mBJPcozIOUAc7mdy+BcROs7g53IClz17Ox36X/f9LUW0RHkRZh5X2AL3O8IrAjz+HxFbzjjMmtL7AAAAAElFTkSuQmCC',
  codex:      'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAEqElEQVR4nJ2Xa4iVZRDHf+ec3cytiN0P3TDSoIjMQmyLrnTBYutDtkQglXZhJQoW6kv6pVIsi1q7EnQPCiPLQugelbWQrSWmIkoXrLTsbq7r2kV3Yw7/iX8v79kjDbznfc88zzPzn3lm5pkHmlNN7yOBhcBqYAgYAX4C3gCutHmtQIs91X3Q0ZBS6HXAd8CoPSOF/x8BJzWQU20EpNJE+V5gPnCreKuAZ4BPgZ3A4UAXcDlwFLADmAu0yfqvgU+AzQWZTalV70vNwoVjuPNiYLDgkXx2Ay8AJxiIhlQR8vz+SkLuFy8AjDMhhwJ9wO+2LSvlpaeBfgMSHps5FoiqfR8N3KGF4b7xWtRic3vk4lTwInByidypwKsGsKsMRE3vCcBTwLAtCAt9W84vWBZxcVGJYvdU0OOavxXokIcrbnknsMUE79B7tibGvHtt/HugV4qczgKOLwCpCswarZ2nsRYkfKJyOgY3ysrX9H+GCfpRQfUgcERB8RTgTa3ZBdwJtGtsP4GYLa+u1v9KLn5ZC9crsFCBcQCB9jfg0YLimP+w5v4CvGNe+hK42uYeA+zRFh+SzGnA32JmIQl3vV4CIFLtPrPqRhWoP1QvYm+DLpMxCeQ94DRZ/Kt4Eeh1ukuMyFVsT4sAWpVK90jYRlPwTUkGHKC9ToVRgJ6XjD0K+Dq9pQk9QtgIQKTit8B28T8HpgMXABvEWwYcy39pkjLLi9M6jVXi52Mxu821DqC7ACCy4yarCei7V8E3pO0IDzidA3wmmVsUxJUYeFvMOSUeCFddKP54uW+xxjO18gm6zQ6pbVb5kjqUATH+UgpZq8HpGkgakeCpVtMzdVLpXj0Jpk2BGjVlE7BEBk6RZyOLrlLAxzlzaig6RUJCwWTbhhOB96V8heZt17lQs8qIvmsK6BCeNNeywLd3ifiLqiqlUQf2B55V8fhLgXIuMEuVbQA4WArS8vTEiP5nkLXJU2vEd7AVAzQtGRNUo0e16IzC3h2k43hYnrrZrEEgeuWhrRaA3ZL5gXkq6BLxBxIAUuxdzmNqMpyOA17R+CadbOfpOythADhQ82eI/6FtQUXVcVSlu06HAX8qjZYZiJ+BW0pSqrNwFG9QQC2Ql8aNASDouYwBrFjkCRiTzlTgpYL1arsylW5X+Q1rr7easEhGlAGomhd3KcU7MaGDYsaBkVtzjQ6UBPKuvBLfD/mBInpAcooA+i2WVloDU6dsDFYpBmYJbQZMuwJwSAszr52yNRtW7Y8scAArtEUD+v+DAr+KuW+eBtdaP+/NRrju7ILimHdDoZFZbAXrCvGyZxxV7NTTLwGkBzosFZ8spFix60ElOt2Zbo5GBvNen2VWlPFHFPD/Kk/KWt5lAperDBcpeEsLFvWYwBYDvVlz5utmlVTa3tf0nmn9YFr2hLzSr0BNt/ZZB5VKU/jdmveF6WhpchkiQUxWg7K7wWVjUJeRMqroVMy53eK1NppcJL8+TVKuTpTlO2VZu1y/VNVsm86SCK5rgdO1foHA7POVDFHDy6SuWHERLfNMPhHMcaFNg/43BQi/aqcb4zvqRXTO0aqHdyJuIs/jIpv9XlPl/wDuH4YGeE/UMQAAAABJRU5ErkJggg==',
};

function _dot(pid, dotColor) {
  const src = LOGOS[pid];
  if (src) return `<img class="qw-prov-logo" src="${src}" alt="">`;
  return `<span class="qw-dot" style="background:${esc(dotColor)}"></span>`;
}

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

/* Grid order: healthiest providers first, so the user sees at a glance
   which one is safe to switch to; worst-off providers sink to the bottom. */
const _HEALTH_RANK = { ok: 0, warn: 1, err: 2, crit: 3 };
function _healthSortedProviders() {
  return state.data.providers.slice().sort((a, b) => {
    const ra = _HEALTH_RANK[a.statusSev], rb = _HEALTH_RANK[b.statusSev];
    if (ra !== rb) return ra - rb;
    const wa = _worstBar(a), wb = _worstBar(b);
    return (wa ? wa.pct : 0) - (wb ? wb.pct : 0);
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
  const launchBtn = (p.id === 'antigravity' && p.errorText === 'Run agy to see quota' && p.canLaunchAgy)
    ? `<button class="qw-launch-btn" data-act="launch_agy">&#9654; Launch agy</button>`
    : '';
  return `<div class="qw-error">
    <span class="ico">${icon}</span>
    <div><div class="msg">${esc(msg)}</div>${hint}${launchBtn}</div>
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

function _changelogBlock(url, label) {
  if (!url) return '';
  return `<div class="qw-installs">
    <div class="qw-installs-head">
      <span class="lbl">${esc(label || 'CLI')}</span>
      <span class="link" data-act="changelog" data-url="${esc(url)}">CHANGELOG</span>
    </div>
  </div>`;
}

function _installsBlock(installs, changelogUrl, label) {
  if (!installs || installs.length === 0) return '';
  const rows = installs.map(i =>
    `<div class="qw-install-row"><span>${esc(i.name)}</span><span class="ver">${esc(i.version)}</span></div>`
  ).join('');
  return `<div class="qw-installs">
    <div class="qw-installs-head">
      <span class="lbl">${esc(label || 'CLI')}</span>
      <span class="link" data-act="changelog" data-url="${esc(changelogUrl || '')}">CHANGELOG</span>
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
      <button class="qw-iconbtn qw-refresh${state.syncing ? ' is-syncing' : ''}" data-act="sync" title="Refresh (R)">
        <span class="ico">${ICON.refresh}</span></button>
      <button class="qw-iconbtn qw-theme is-${state.theme}" data-act="theme" title="Toggle theme (T)">
        <span class="ico" style="transform:rotate(${state.themeRot}deg)">${icon}</span></button>
      <span class="qw-close" data-act="close" title="Close (Esc)">&times;</span>
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
    <button class="active" data-act="focus" title="Focus mode (←)">FOCUS</button>
    <button data-act="grid" title="Grid mode (→)">GRID</button>
  </div></div>`;

  const menu = state.menuOpen ? `<div class="qw-menu">${provs.map(p => {
    const w = _worstBar(p);
    let pctHtml;
    if (!w) {
      pctHtml = `<span class="pct sev-err" style="color:var(--c)">—</span>`;
    } else if (p.bars.length === 1) {
      pctHtml = `<span class="pct sev-${w.sev}" style="color:var(--c)">${Math.round(w.pct)}%</span>`;
    } else {
      pctHtml = `<div class="qw-menu-multi">${p.bars.map(b =>
        `<div class="qw-menu-multi-row sev-${b.sev}">
          <span class="lbl">${esc(b.label)}</span>
          <span class="pct" style="color:var(--c)">${Math.round(b.pct)}%</span>
        </div>`).join('')}</div>`;
    }
    return `<button class="qw-menu-item${p.id === active.id ? ' active' : ''}" data-pick="${esc(p.id)}">
      ${_dot(p.id, p.dot)}
      <span class="nm">${esc(p.name)}</span>
      ${_planBadge(p.plan, true)}
      ${pctHtml}
      <span class="qw-sevdot sev-${p.statusSev}"></span>
    </button>`;
  }).join('')}</div>` : '';

  const switcher = `<div class="qw-switcher-wrap" data-menu>
    <button class="qw-switcher" data-act="menu" title="Switch provider (↑↓)">
      ${_dot(active.id, active.dot)}
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
    const staleNotice = (active.stale && active.errorText)
      ? `<div class="qw-stale-notice">&#9888; ${esc(active.errorText)}</div>`
      : '';
    body = staleNotice + `<div class="qw-bars">${active.bars.map(_bigBar).join('')}</div>`;
    if (active.id === 'claude') {
      body += _extraBlock(active.extra);
      body += _installsBlock(active.installs, active.changelog_url, 'CLAUDE CODE');
    } else if (active.installs && active.installs.length > 0) {
      body += _installsBlock(active.installs, active.changelog_url, active.changelog_label);
    } else {
      body += _changelogBlock(active.changelog_url, active.changelog_label);
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
  const provs = _healthSortedProviders();

  const toggles = `<div class="qw-toggles">
    <div class="qw-toggle-row">
      <div class="qw-seg">
        <button data-act="focus" title="Focus mode (←)">FOCUS</button>
        <button class="active" data-act="grid" title="Grid mode (→)">GRID</button>
      </div>
      <button class="qw-density${state.compact ? ' active' : ''}" data-act="density" title="Toggle compact (C)">&#9776;</button>
    </div>
    <div class="qw-sort-note">SORTED BY HEALTH</div>
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
        ${_dot(p.id, p.dot)}
        <span class="nm">${esc(p.name)}</span>
        ${_planBadge(p.plan, true)}
        ${miniHtml}
        <span class="qw-sevdot sev-${sev}"></span>
      </div>`;
    }

    let cardBody;
    if (!p.bars || p.bars.length === 0) {
      cardBody = _errorBlock(p);
    } else {
      const staleNotice = (p.stale && p.errorText)
        ? `<div class="qw-stale-notice qw-stale-card">&#9888; ${esc(p.errorText)}</div>`
        : '';
      let bars = staleNotice + `<div class="qw-card-bars">${p.bars.map(_cardBar).join('')}</div>`;
      if (p.id === 'claude') {
        bars += _extraBlock(p.extra);
        bars += _installsBlock(p.installs, p.changelog_url, 'CLAUDE CODE');
      } else if (p.installs && p.installs.length > 0) {
        bars += _installsBlock(p.installs, p.changelog_url, p.changelog_label);
      } else {
        bars += _changelogBlock(p.changelog_url, p.changelog_label);
      }
      cardBody = bars;
    }

    return `<div class="qw-card" style="--i:${i}">
      <div class="qw-card-head">
        <div class="qw-card-id">
          ${_dot(p.id, p.dot)}
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
  _cancelAnim();
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
let _animTimer  = null;
let _staggerTimer = null;

function _cancelAnim() {
  if (_animTimer !== null)    { clearTimeout(_animTimer); _animTimer = null; }
  if (_staggerTimer !== null) { clearTimeout(_staggerTimer); _staggerTimer = null; }
}

function _animatedRender() {
  /* Cancel any in-flight transition instead of dropping this call — keeps
     rapid key presses (arrows, R/T/C back-to-back) from being silently
     ignored or racing a stale deferred render. */
  _cancelAnim();

  /* Set target width immediately so shell starts resizing */
  const targetW = state.mode === 'grid' ? 440 : 360;
  shell.style.width = targetW + 'px';

  /* Phase 1 — fade out current content */
  panel.classList.add('is-exit');

  _animTimer = setTimeout(() => {
    _animTimer = null;

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
        /* Remove stagger class after entrance animations finish */
        _staggerTimer = setTimeout(() => {
          _staggerTimer = null;
          panel.classList.remove('is-animated');
        }, 600);
      });
    });
  }, _FADE_MS);
}

/* event delegation ------------------------------------------------------ */
shell.addEventListener('click', (e) => {
  const pick = e.target.closest('[data-pick]');
  if (pick) { state.active = pick.dataset.pick; state.menuOpen = false; _animatedRender(); return; }
  const act = e.target.closest('[data-act]');
  if (!act) return;
  switch (act.dataset.act) {
    case 'focus':     state.mode = 'focus'; _saveState(); _animatedRender(); break;
    case 'grid':      state.mode = 'grid'; state.menuOpen = false; _saveState(); _animatedRender(); break;
    case 'menu':      state.menuOpen = !state.menuOpen; render(); break;
    case 'density':   state.compact = !state.compact; _saveState(); _animatedRender(); break;
    case 'theme':     state.theme = state.theme === 'dark' ? 'light' : 'dark'; state.themeRot += 180; _saveState(); render(); break;
    case 'sync':       _doSync(); break;
    case 'close':      if (typeof pywebview !== 'undefined') pywebview.api.close(); break;
    case 'changelog':  if (typeof pywebview !== 'undefined') pywebview.api.open_url(act.dataset.url || ''); break;
    case 'launch_agy':
      if (typeof pywebview !== 'undefined') {
        pywebview.api.launch_agy();
        setTimeout(_doSync, 8000);
      }
      break;
  }
});

document.addEventListener('mousedown', (e) => {
  if (state.menuOpen && !e.target.closest('[data-menu]')) { state.menuOpen = false; render(); }
});

document.addEventListener('keydown', (e) => {
  if (!state.data) return;
  if (e.key === 'Escape') {
    if (state.menuOpen) { state.menuOpen = false; render(); }
    else if (typeof pywebview !== 'undefined') pywebview.api.close();
    e.preventDefault();
    return;
  }
  /* Use e.code (physical key, layout-independent) instead of e.key for
     letter shortcuts — e.key reflects the active IME/keyboard layout
     (e.g. Thai Kedmanee maps physical R/T/C to พ/ะ/แ), so e.key checks
     silently no-op whenever a non-Latin layout is active. */
  if (e.code === 'KeyR') { _doSync(); e.preventDefault(); return; }
  if (e.code === 'KeyC') { state.compact = !state.compact; _saveState(); _animatedRender(); e.preventDefault(); return; }
  if (e.code === 'KeyT') {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    state.themeRot += 180;
    _saveState();
    render();
    e.preventDefault();
    return;
  }
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    const next = e.key === 'ArrowRight' ? 'grid' : 'focus';
    if (state.mode !== next) {
      state.mode = next;
      state.menuOpen = false;
      _saveState();
      _animatedRender();
      e.preventDefault();
    }
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if (state.mode === 'focus') {
      const provs = _sortedProviders();
      const idx = provs.findIndex(p => p.id === state.active);
      if (idx !== -1) {
        const next = e.key === 'ArrowDown'
          ? (idx + 1) % provs.length
          : (idx - 1 + provs.length) % provs.length;
        state.active = provs[next].id;
        state.menuOpen = false;
        _animatedRender();
        e.preventDefault();
      }
    } else if (state.mode === 'grid') {
      const cards = document.querySelector('.qw-cards');
      if (cards) {
        cards.scrollBy({ top: e.key === 'ArrowDown' ? 80 : -80, behavior: 'smooth' });
        e.preventDefault();
      }
    }
  }
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
    p.stale        = p.stale        || false;
    p.canLaunchAgy = p.canLaunchAgy || false;
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
  // First poll not done yet — auto-refresh once data arrives
  if (!state.data.providers.length) {
    setTimeout(_doSync, 800);
  }
}

function refreshDone(payload) {
  state.data    = normalize(payload);
  state.syncing = false;
  render();
}
