/* QuotaWatch — popup logic */
'use strict';

let els;
let statusState = {};
let textTimerId  = null;
let activeProvider = null;   // null = single-provider (no tabs)
let allUsageBars   = [];     // full unfiltered list from last updateData

/**
 * Bootstrap: inject translations, set static text, bind events, render initial data.
 * Called once by Python after the page loads.
 *
 * @param {object} config - { t, app_version, data }
 */
function init(config) {
    const t = config.t;

    document.getElementById('title').textContent           = t.title;
    document.getElementById('headingAccount').textContent  = t.account;
    document.getElementById('labelEmail').textContent      = t.email;
    document.getElementById('labelPlan').textContent       = t.plan;
    document.getElementById('headingUsage').textContent    = t.usage;
    document.getElementById('headingExtraUsage').textContent = t.extra_usage;
    document.getElementById('headingClaudeCode').textContent = t.claude_code;
    document.getElementById('appVersion').textContent      = config.app_version;

    const link = document.getElementById('changelogLink');
    link.textContent = t.changelog;
    link.addEventListener('click', () => {
        if (window.pywebview) pywebview.api.open_url();
    });

    document.getElementById('refreshBtn').addEventListener('click', () => {
        if (window.pywebview) {
            document.getElementById('refreshBtn').classList.add('spinning');
            pywebview.api.refresh();
        }
    });

    document.getElementById('closeBtn').addEventListener('click', () => {
        if (window.pywebview) pywebview.api.close();
    });

    els = {
        providerTabs:    document.getElementById('providerTabs'),
        accountSection:  document.getElementById('accountSection'),
        emailRow:        document.getElementById('emailRow'),
        emailValue:      document.getElementById('emailValue'),
        planRow:         document.getElementById('planRow'),
        planValue:       document.getElementById('planValue'),
        usageSection:    document.getElementById('usageSection'),
        usageBars:       document.getElementById('usageBars'),
        extraSection:    document.getElementById('extraSection'),
        extraSpent:      document.getElementById('extraSpent'),
        extraPct:        document.getElementById('extraPct'),
        extraFill:       document.getElementById('extraFill'),
        installSection:  document.getElementById('installSection'),
        installRows:     document.getElementById('installRows'),
        statusSection:   document.getElementById('statusSection'),
        statusText:      document.getElementById('statusText'),
    };

    // Keep translations and last data for tab switching
    window._t = t;
    window._lastData = config.data;

    updateData(config.data);
    requestAnimationFrame(() => document.body.classList.add('open'));
}

function refreshDone(config) {
    document.getElementById('refreshBtn').classList.remove('spinning');
    window._lastData = config.data;
    updateData(config.data);
}

function updateData(data) {
    // Build / refresh tabs if providers changed
    _initTabs(data.providers || []);

    // Store full bar list for tab switching
    allUsageBars = data.usage || [];

    _renderForActiveProvider(data);
    updateStatus(data.status);
}

function _renderForActiveProvider(data) {
    const onClaude = !activeProvider || activeProvider === 'Claude';

    // Account section — per-provider profile
    const profiles = data.provider_profiles || {};
    const profileKey = activeProvider || 'Claude';
    const prof = profiles[profileKey] || (onClaude ? data.profile : null);
    const hasProfile = !!(prof && (prof.email || prof.plan));
    els.accountSection.classList.toggle('visible', hasProfile);
    if (hasProfile) {
        els.emailValue.textContent = prof.email || '';
        els.emailRow.style.display = prof.email ? '' : 'none';
        els.planValue.textContent  = prof.plan  || '';
        els.planRow.style.display  = prof.plan  ? '' : 'none';
    }

    // Usage bars — filtered to active provider
    const bars = activeProvider
        ? allUsageBars.filter(b => b.provider === activeProvider)
        : allUsageBars;
    const hasUsage = !!bars.length;
    els.usageSection.classList.toggle('visible', hasUsage);
    if (hasUsage) updateUsageBars(bars);

    // Extra usage (Claude-only)
    const hasExtra = !!(data.extra && onClaude);
    els.extraSection.classList.toggle('visible', hasExtra);
    if (hasExtra) {
        els.extraSpent.textContent = data.extra.spent_text;
        els.extraPct.textContent   = data.extra.pct_text;
        els.extraPct.className     = 'bar-pct ok';
        els.extraFill.style.width  = `${data.extra.fill_pct * 100}%`;
    }

    // Installs (Claude-only)
    const hasInstalls = !!(data.installations && data.installations.length && onClaude);
    els.installSection.classList.toggle('visible', hasInstalls);
    if (hasInstalls) {
        els.installRows.replaceChildren(...data.installations.map(inst => {
            const row = document.createElement('div');
            const dt  = document.createElement('dt'); dt.textContent = inst.name;
            const dd  = document.createElement('dd'); dd.textContent = inst.version;
            row.append(dt, dd);
            return row;
        }));
    }
}

function _initTabs(providers) {
    if (providers.length <= 1) {
        els.providerTabs.classList.remove('visible');
        activeProvider = null;
        return;
    }
    // Rebuild tabs only when provider list changes
    const existing = [...els.providerTabs.querySelectorAll('.provider-tab')].map(t => t.dataset.provider);
    if (JSON.stringify(existing) === JSON.stringify(providers)) return;

    els.providerTabs.replaceChildren(...providers.map((name, i) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'provider-tab' + (i === 0 ? ' active' : '');
        btn.dataset.provider = name;
        btn.textContent = name;
        btn.addEventListener('click', () => _switchTab(name));
        return btn;
    }));
    els.providerTabs.classList.add('visible');
    if (!activeProvider || !providers.includes(activeProvider)) {
        activeProvider = providers[0];
    }
}

function _switchTab(name) {
    activeProvider = name;
    for (const tab of els.providerTabs.querySelectorAll('.provider-tab')) {
        tab.classList.toggle('active', tab.dataset.provider === name);
    }
    _renderForActiveProvider(window._lastData);
}

// ── Bar helpers ──────────────────────────────────────────────────────────────

/** Return CSS class and severity label for a bar. */
function _barMeta(fillPct, isWarn) {
    const p = fillPct * 100;
    if (p >= 95)                    return ['crit', 'red',   'BREACH'];
    if (p >= 90)                    return ['crit', 'red',   'CRITICAL'];
    if (p >= 60)                    return ['warn', 'amber', 'WARNING'];
    if (isWarn && p >= 20)          return ['warn', 'amber', 'WARNING'];
    return                                 ['ok',   'green', 'NOMINAL'];
}

function updateUsageBars(entries) {
    if (entries.length !== els.usageBars.children.length) {
        els.usageBars.replaceChildren(...entries.map(_createBar));
        requestAnimationFrame(() => {
            for (let i = 0; i < entries.length; i++) {
                _setBarWidth(els.usageBars.children[i], entries[i].fill_pct);
            }
        });
    } else {
        for (let i = 0; i < entries.length; i++) {
            _updateBar(els.usageBars.children[i], entries[i]);
        }
    }
}

function _createBar(entry) {
    const [cls, sevCls, sevLabel] = _barMeta(entry.fill_pct, entry.warn);

    const div = document.createElement('div');
    div.className = 'usage-entry';

    // Header row
    const hdr = document.createElement('div');
    hdr.className = 'bar-header';

    const label = document.createElement('span');
    label.className = 'bar-label';
    label.textContent = entry.label;

    const right = document.createElement('div');
    right.className = 'bar-right';

    const pct = document.createElement('span');
    pct.className = `bar-pct ${cls}`;
    pct.textContent = entry.pct_text;

    const badge = document.createElement('span');
    badge.className = `sev ${sevCls}`;
    badge.innerHTML = `<span class="dot"></span>${sevLabel}`;

    right.append(pct, badge);
    hdr.append(label, right);

    // Bar track
    const track = document.createElement('div');
    track.className = 'bar-container';

    const fill = document.createElement('div');
    fill.className = `bar-fill ${cls}`;
    fill.style.width = '0%';
    track.appendChild(fill);

    // Midnight dividers
    for (const pos of entry.midnights) {
        const d = document.createElement('div');
        d.className = 'bar-divider';
        d.style.left = `calc(${pos * 100}% - 0.5px)`;
        track.appendChild(d);
    }

    // Time marker
    if (entry.marker_rel !== null) {
        const m = document.createElement('div');
        m.className = 'bar-marker';
        m.style.left = `calc(${entry.marker_rel * 100}% - 1px)`;
        track.appendChild(m);
    }

    div.append(hdr, track);

    const rt = document.createElement('div');
    rt.className = 'reset-text';
    if (entry.resets_at) rt.dataset.resetsAt = entry.resets_at;
    rt.textContent = entry.reset_text || '';
    rt.style.display = entry.reset_text ? '' : 'none';
    div.appendChild(rt);

    return div;
}

function _setBarWidth(div, fillPct) {
    const fill = div.querySelector('.bar-fill');
    if (fill) fill.style.width = `${fillPct * 100}%`;
}

function _updateBar(div, entry) {
    const [cls, sevCls, sevLabel] = _barMeta(entry.fill_pct, entry.warn);

    const pct = div.querySelector('.bar-pct');
    if (pct) { pct.textContent = entry.pct_text; pct.className = `bar-pct ${cls}`; }

    const badge = div.querySelector('.sev');
    if (badge) { badge.className = `sev ${sevCls}`; badge.innerHTML = `<span class="dot"></span>${sevLabel}`; }

    const fill = div.querySelector('.bar-fill');
    if (fill) { fill.style.width = `${entry.fill_pct * 100}%`; fill.className = `bar-fill ${cls}`; }

    const track = div.querySelector('.bar-container');

    // Rebuild midnight dividers
    for (const d of track.querySelectorAll('.bar-divider')) d.remove();
    for (const pos of entry.midnights) {
        const d = document.createElement('div');
        d.className = 'bar-divider';
        d.style.left = `calc(${pos * 100}% - 0.5px)`;
        track.appendChild(d);
    }

    // Update/add/remove time marker
    let marker = track.querySelector('.bar-marker');
    if (entry.marker_rel !== null) {
        if (!marker) {
            marker = document.createElement('div');
            marker.className = 'bar-marker';
            track.appendChild(marker);
        }
        marker.style.left = `calc(${entry.marker_rel * 100}% - 1px)`;
    } else if (marker) {
        marker.remove();
    }

    // Reset text
    let rt = div.querySelector('.reset-text');
    if (!rt) { rt = document.createElement('div'); rt.className = 'reset-text'; div.appendChild(rt); }
    if (entry.resets_at) rt.dataset.resetsAt = entry.resets_at;
    rt.textContent    = entry.reset_text || '';
    rt.style.display  = entry.reset_text ? '' : 'none';
}

// ── Status footer ────────────────────────────────────────────────────────────

function updateStatus(status) {
    if (textTimerId) { clearInterval(textTimerId); textTimerId = null; }

    if (!status) { els.statusSection.classList.remove('visible'); return; }
    els.statusSection.classList.add('visible');

    if (status.last_success_time !== undefined) {
        statusState = {
            lastSuccessTime: status.last_success_time,
            nextPollTime:    status.next_poll_time,
            refreshing:      status.refreshing,
            error:           status.error,
        };
        els.statusSection.classList.toggle('error', !!status.error);
        _tickStatus();
        textTimerId = setInterval(_tickStatus, 1000);
    } else {
        statusState = {};
        els.statusText.textContent = status.text || '';
        els.statusSection.classList.toggle('error', !!status.is_error);
    }
}

function _tickStatus() {
    if (!statusState.lastSuccessTime) return;

    const t   = window._t;
    const now = Date.now() / 1000;
    const ago = Math.max(0, Math.floor(now - statusState.lastSuccessTime));
    const isStale = !!statusState.nextPollTime && now > statusState.nextPollTime + 30;

    document.getElementById('usageSection')?.classList.toggle('stale', isStale);
    document.getElementById('extraSection')?.classList.toggle('stale', isStale);

    const parts = [_fmtAgo(ago, t)];

    if (statusState.refreshing) {
        parts.push(t.status_refreshing);
    } else if (statusState.error) {
        parts.push(statusState.error);
    } else if (ago >= 60 && statusState.nextPollTime) {
        const until = Math.max(0, Math.floor(statusState.nextPollTime - now));
        if (until > 0) parts.push(t.status_next_update.replace('{duration}', _fmtCountdown(until, t)));
    }

    els.statusText.textContent = parts.join(' · ');
}

function _fmtAgo(s, t) {
    if (s < 60) return t.status_updated_s.replace('{s}', s);
    const m = Math.floor(s / 60), h = Math.floor(m / 60), mins = m % 60;
    const dur = h > 0
        ? t.duration_hm.replace('{h}', h).replace('{m}', mins)
        : t.duration_m.replace('{m}', m);
    return t.status_updated.replace('{duration}', dur);
}

function _fmtCountdown(s, t) {
    if (s < 60) return t.duration_s.replace('{s}', s);
    const m = Math.ceil(s / 60), h = Math.floor(m / 60), mins = m % 60;
    return h > 0
        ? t.duration_hm.replace('{h}', h).replace('{m}', mins)
        : t.duration_m.replace('{m}', m);
}

// ── Live reset countdown ─────────────────────────────────────────────────────

function _fmtResetText(isoStr) {
    if (!isoStr) return '';
    const reset  = new Date(isoStr);
    const now    = new Date();
    const diffMs = reset - now;
    if (diffMs <= 0) return '';

    const pad2     = n => String(n).padStart(2, '0');
    const hhmm     = `${pad2(reset.getHours())}:${pad2(reset.getMinutes())}`;
    const dayNames = ['SUN','MON','TUE','WED','THU','FRI','SAT'];

    const totalMin = Math.floor(diffMs / 60000);
    const daysLeft = Math.floor(totalMin / (24 * 60));
    const remMin   = totalMin % (24 * 60);
    const h = Math.floor(remMin / 60), m = remMin % 60;

    if (daysLeft === 0) {
        return `RESETS IN ${h > 0 ? `${h}H ${pad2(m)}M` : `${m}M`} (${hhmm})`;
    }
    return `RESETS IN ${daysLeft}D ${h}H ${pad2(m)}M (${dayNames[reset.getDay()]} ${hhmm})`;
}

function _tickResetTexts() {
    for (const el of document.querySelectorAll('.reset-text[data-resets-at]')) {
        const text = _fmtResetText(el.dataset.resetsAt);
        el.textContent   = text;
        el.style.display = text ? '' : 'none';
    }
}

setInterval(_tickResetTexts, 30000);

// ── Height reporting ─────────────────────────────────────────────────────────
new ResizeObserver(() => {
    const h = document.body.scrollHeight;
    if (window.pywebview?.api?.report_height) pywebview.api.report_height(h);
}).observe(document.body);
