# Handoff: QuotaWatch Popup UI/UX Redesign

## Overview
A redesign of the QuotaWatch Windows system-tray popup that displays AI quota/token
usage across multiple providers (Claude, Codex, Windsurf, Antigravity, Grok, OpenCode, …).

It replaces the old single-column "SOC console" popup with a cleaner, modern panel that has:

- **Two layouts**, switchable with a toggle:
  - **FOCUS** — one provider at a time, with large legible usage bars and prominent reset countdowns. Provider is chosen from a **dropdown switcher** (scales to any number of providers — none get hidden off-screen).
  - **GRID** — all providers at once, **sorted by severity** (critical first), in a height-capped scrollable list, with a **compact / comfortable density toggle**.
- **Independent light/dark theme toggle** (layout and theme are decoupled).
- **Smooth size animation** when switching layouts or providers (the panel grows/shrinks).
- **Live reset countdowns** that tick every second.
- Polished micro-interactions on the **refresh** (cyan glow + spin) and **theme** (sun/moon morph with rotate) buttons.

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing the
intended look and behavior, **not production code to ship verbatim**. The task is to
**recreate this design inside the existing QuotaWatch codebase** (Python + Edge WebView2,
plain HTML/CSS/JS in `monitor/html/`), wiring it to the real quota payload — following the
repo's established patterns.

Two reference files are included:

| File | What it is | How to use it |
|---|---|---|
| `quotawatch-ui-reference.html` | A **self-contained vanilla HTML/CSS/JS** implementation. No framework, no build step. Open it in any browser to interact with the full design. | This is the primary reference. Its `<style>`, shell markup, and `<script>` are split with `popup.css` / `popup.html` / `popup.js` markers and map almost 1:1 onto the repo's three files. Lift from it. |
| `QuotaWatch Variants.dc.html` | The original interactive prototype (authored in a component framework). | Visual source of truth only — needs its runtime to open. Prefer the vanilla file for code. |

> The vanilla reference already uses the **same architecture as the repo**: an `init(payload)`
> / `refreshDone(payload)` entry pair, a single delegated click handler, and a JS render that
> builds the panel from a data payload. You are adapting it, not starting over.

## Fidelity
**High-fidelity (hifi).** Final colors, typography, spacing, radii, animations and interaction
states are all specified below and embedded in the reference files. Recreate pixel-for-pixel,
then wire to live data.

---

## Target codebase map (`monitor/`)

| Repo file | Change |
|---|---|
| `html/popup.html` | Replace body with the shell `<div class="qw-shell"><div class="qw-panel" id="qwPanel"></div></div>`. The panel is rendered by JS. |
| `html/popup.css` | Replace with the `popup.css` block from the reference (token `:root` + `[data-theme="light"]`, all component classes). |
| `html/popup.js` | Replace render logic with the `popup.js` block. Keep the existing `init()` / `refreshDone()` names — they're already called from Python. Add a `normalize(payload)` adapter (see **Data**). |
| `popup.py` | `_build_payload()` → reshape to the payload contract below. `_POPUP_W` is currently a fixed `340`; make width **per-layout** (360 focus / 440 grid) or pick one. `report_height()` already resizes the native window — call it from JS `measure()` for the height animation (see **Size animation** caveat). |
| `tray.py` | Unaffected (tray icon renderer) unless you want the icon to follow the new severity colors. |

---

## Screens / Views

### 1. FOCUS layout (default)
- **Purpose:** Watch one provider closely; switch provider via dropdown.
- **Width:** 360px. **Font:** Manrope.
- **Vertical order:** Header → Layout toggle → Provider switcher → Account row → Usage bars → Footer.
- **Components:**
  - **Header** (`padding:14px 16px`): left = pulsing live dot (8px, `--dot`, `box-shadow 0 0 9px`, `qw-pulse 1.8s`) + "QuotaWatch" (14px/700). Right = refresh button, theme button, close `×` (`--close`, 18px). Action gap 8px.
  - **Layout toggle** (`padding:0 16px 10px`): segmented control, `--toggle-bg` track, radius 10, 3px pad. Two buttons FOCUS/GRID (mono 10.5px/600, `.08em`). Active = `--accent` bg / `--accent-on` text (light theme active = white bg + subtle shadow).
  - **Provider switcher** (`padding:0 16px 5px`): full-width button (radius 9, `--btn-border`, `--btn-bg`) = provider dot (9×9 radius 3) + name (13px/700) + plan badge + right-aligned `"<count> ▾"` (mono 9.5px `--faint`). Opens **dropdown menu** (absolute, `--menu-bg`, border `--border`, radius 11, `--shadow`, `max-height:228px`, scroll). Each menu item: dot + name (12.5px/600, min-width 72) + plan badge (sm) + right-aligned worst-% (severity colored) + severity dot. Active item bg `--plan-bg`. Closes on select or outside click.
  - **Account row** (`padding:9px 16px 14px`): email (12.5px `--dim`) left, plan badge right.
  - **Usage bars** (`padding:0 16px 6px`, `gap:16px`): per bar — label (mono 10px `.14em` uppercase `--faint`), big % (26px/800, `letter-spacing -.03em`, severity text color; the `%` sign is 15px `--dim`), severity badge top-right, then track (height 9, radius 6, `--track`) with fill (severity bar color, `transition:width .5s`), then optional **reset pill** (`--reset-bg`, radius 8): `⏱` + "resets in" (11px `--dim`) + value (mono 12.5px/700 `--text`).
  - **Footer** (`padding:13px 16px`, top border `--card-border`): status string left, version right (both mono 10px `--faint`).

### 2. GRID layout
- **Purpose:** See every provider at once; compare; spot trouble (sorted by severity).
- **Width:** 440px. **Font:** Space Grotesk.
- **Vertical order:** Header (with "<N> PROVIDERS" tag, white header bar + bottom border) → Layout toggle + density button + "SORTED BY SEVERITY" note → Cards (scroll area) → Footer.
- **Sorting:** by severity rank `crit(0) < warn(1) < ok(2)`, tie-break by worst-bar % descending.
- **Cards area** (`padding:10px 14px 12px`, `gap:9px`, **`max-height:368px; overflow-y:auto`**).
- **Comfortable card:** header row = dot + name (13.5px/700) + plan badge, with severity **chip** (`● NOMINAL/WARNING/CRITICAL`) right. Below: bars wrap (`flex 1 1 40%`, min-width 130) each = label + % (mono 13px/700 severity) + thin track (height 7) + optional `↺ <reset>` (mono 10px `--faint`).
- **Compact row** (density on): single line — dot + name (min-width 72) + plan badge (sm) + flexible mini-bar (height 6) of the **worst** bar + worst-% (severity) + severity dot. ~46px tall; lets ~8+ providers fit without scrolling.
- **Density toggle:** 34×34 button showing `☰`; active = `--plan-bg`/`--plan-color`.

---

## Interactions & Behavior
- **Layout toggle** FOCUS⇄GRID: changes `state.mode`; shell width animates 360⇄440, height animates to new content. Closes the dropdown.
- **Theme toggle:** flips `state.theme` and adds **+180°** to `state.themeRot`. Icon morphs sun⇄moon and the icon `<span>` rotates with spring easing `cubic-bezier(.34,1.56,.64,1)` over `.55s`. Hover glow: amber (`--sun-glow`) in dark, indigo (`--moon-glow`) in light. All themeable colors cross-fade `.4s` (rule: `.qw-shell, .qw-shell * { transition: background-color/color/border-color/box-shadow .4s ease }`).
- **Provider switcher:** click opens dropdown; clicking an item sets `state.active`, closes menu, swaps bars; outside `mousedown` closes it.
- **Density toggle (grid):** flips `state.compact`; cards re-render comfortable⇄compact.
- **Refresh:** sets `state.syncing=true` → button gets cyan border + `box-shadow 0 0 16px rgba(34,211,238,.45)` + bg `rgba(34,211,238,.1)`; the icon turns cyan, `drop-shadow(0 0 5px …)`, spins `qw-spin .7s linear`. In the prototype it auto-clears after 800ms; **in the real app, `state.syncing` clears when `refreshDone(payload)` arrives.** Hover (idle): icon rotates 150°, turns cyan, button glows.
- **All icon buttons:** `:active { transform:scale(.86) }`.
- **Live countdowns:** a 1s interval decrements each bar's `secs` and updates `[data-key]` text in place (does **not** re-render the panel, so animations/transforms aren't interrupted).
- **Close `×`:** call `pywebview.api.close()`.

## Size animation (important caveat)
The prototype animates the **inner** `.qw-shell` (CSS `transition: width/height .44s cubic-bezier(.32,.72,0,1)`, `overflow:hidden`, JS sets `height = panel.offsetHeight`). In the real app the popup is a **native frameless WebView2 window** sized by `monitor/popup.py` via `report_height()` / `win.resize()`. Native window resizes do **not** tween. Recommended approach:
1. Keep the CSS size-transition on `.qw-shell` **inside** the web content.
2. Make the **native window** large enough to contain the biggest state (or resize it to the target size up front), and let the inner shell animate within it. A transparent/blended window background (`background_color` already `#070b14` → change to match `--bg`, or make per-theme) avoids a visible box around the animating shell.
3. Alternatively, accept an instant native-window resize and only animate inner content — still reads well.
Call `measure()` (which reads `panel.offsetHeight`) wherever the prototype does, and additionally call `pywebview.api.report_height(panel.offsetHeight)` so Python tracks the window size.

## State Management
`state = { mode:'focus'|'grid', theme:'dark'|'light', themeRot:int, active:providerId, compact:bool, menuOpen:bool, syncing:bool, data:payload }`. Persisting `mode`/`theme`/`compact` across opens (e.g. registry or a small JSON) is a nice-to-have — not in the prototype.

## Data (payload contract)
JS expects (adapt `_build_payload()` in `monitor/popup.py`, then map in `normalize()`):
```js
{
  version: "v2.4.0",
  status:  "UPDATED 12S AGO",          // footer string
  providers: [
    {
      id: "claude", name: "Claude",
      plan: "MAX",                      // subscription tier badge (short word)
      email: "alex@studio.dev",         // or "local · no login"
      dot: "#c2683f",                   // per-provider accent dot
      statusSev: "crit",                // worst severity → 'ok' | 'warn' | 'crit'
      bars: [
        { label:"SESSION · 5H", pct:72, sev:"warn", key:"c_sess", secs:8040 },
        { label:"WEEKLY · 7D",  pct:91, sev:"crit", key:"c_week", secs:280800 }
        // key/secs null when a field has no reset (e.g. Antigravity groups)
      ]
    }
    // …one entry per provider; UI scales automatically
  ]
}
```
**Severity rule** (server-side, mirrors old behavior): a field is `crit` at ≥100% (breach) or near-exhaustion; `warn` when usage outpaces the elapsed-time proportion (the old `pct > time_pct`); else `ok`. A provider's `statusSev` = worst of its bars. Keep the existing `monitor/providers/*` reset/elapsed logic; just emit `sev` + `secs` per field. `secs` = seconds until reset (drives the live countdown via `fmt()`); send the absolute reset timestamp if you prefer and compute `secs` client-side each tick.

## Design Tokens

### Colors — Dark (default)
| Token | Value | Token | Value |
|---|---|---|---|
| `--bg` | `#14161c` | `--text` | `#e7e9ef` |
| `--card` | `rgba(255,255,255,.03)` | `--dim` | `#8b91a3` |
| `--card-border` | `rgba(255,255,255,.06)` | `--faint` | `#5b6071` |
| `--border` | `rgba(255,255,255,.07)` | `--track` | `rgba(255,255,255,.06)` |
| `--header-bg` | `rgba(255,255,255,.015)` | `--btn-bg` | `rgba(255,255,255,.04)` |
| `--btn-border` | `rgba(255,255,255,.10)` | `--btn-color` | `#c9cedd` |
| `--toggle-bg` | `rgba(255,255,255,.05)` | `--menu-bg` | `#1b1e27` |
| `--plan-bg` | `rgba(154,160,255,.12)` | `--plan-color` | `#9aa0ff` |
| `--reset-bg` | `rgba(255,255,255,.04)` | `--close` | `#6a7185` |
| `--accent` | `#9aa0ff` | `--accent-on` | `#14161c` |
| `--dot` (live) | `#34d399` | `--shadow` | `0 24px 60px rgba(0,0,0,.4), 0 2px 8px rgba(0,0,0,.3)` |

### Colors — Light (`[data-theme="light"]`)
`--bg #f4f5f7` · `--card #fff` · `--card-border #ebedf1` · `--border #e2e4e9` · `--header-bg #fff` ·
`--text #1a1d24` · `--dim #8a8f9c` · `--faint #9aa0ad` · `--track #eef0f3` · `--btn-bg #fff` ·
`--btn-border #e2e4e9` · `--btn-color #6b7180` · `--toggle-bg #eceef2` · `--menu-bg #fff` ·
`--plan-bg #eef0ff` · `--plan-color #6b6fd6` · `--reset-bg #f1f2f5` · `--close #9aa0ad` ·
`--accent #6b6fd6` · `--accent-on #fff` · `--dot #16a34a` · `--shadow 0 24px 60px rgba(40,44,54,.18), 0 2px 8px rgba(40,44,54,.08)`.

### Severity
| Sev | Bar fill | Text (dark) | Text (light) | Badge bg (dark / light) |
|---|---|---|---|---|
| ok | `#22c55e` | `#34d399` | `#16a34a` | `rgba(52,211,153,.12)` / `#e8f6ed` |
| warn | `#f59e0b` | `#fbbf24` | `#d97706` | `rgba(251,191,36,.12)` / `#fdf2e3` |
| crit | `#ef4444` | `#fb7185` | `#dc2626` | `rgba(251,113,133,.12)` / `#fdeaea` |

Dark badges also get a 1px border (`rgba(…,.30–.35)`); light badges use transparent border.

### Micro-interaction accents
Refresh sync: `#22d3ee` (cyan). Theme sun: `#fbbf24` glow `rgba(251,191,36,.45)`. Theme moon: `#818cf8` glow `rgba(129,140,248,.45)`.

### Provider dot colors (sample set — extend per provider)
Claude `#c2683f` · Codex `#5b8def` · Windsurf `#2bb3a3` · Antigravity `#b07ae0` · Grok `#7d8694` · OpenCode `#e0863f`.

### Typography
- **Manrope** (400–800): FOCUS layout body, names, big %.
- **Space Grotesk** (400–700): GRID layout body.
- **JetBrains Mono** (400–700): all labels, badges, %, countdowns, footer, meta.
- All available on Google Fonts. Ship them locally or keep the `<link>` (the popup is online-capable but bundling avoids a flash).

### Radii / spacing
Shell 14 · cards 11 · menu 11 · reset pill 8 · toggle track 10 / button 8 · icon button 9 · density 8 · plan badge 5 (sm 4) · badge 6 · chip 5 · bar track radius 6 (focus) / 5 (grid) · provider/severity square-dot 3 · sev round-dot 50%.
Icon buttons 30×30; density 34×34. Section horizontal padding 16 (focus) / 14–18 (grid).

### Animation
- Size: `width/height .44s cubic-bezier(.32,.72,0,1)`.
- Theme color cross-fade: `.4s ease` (scoped `.qw-shell *`).
- Theme icon rotate: `.55s cubic-bezier(.34,1.56,.64,1)`, +180°/toggle.
- Bar fill: `width .5s ease`.
- Refresh spin: `qw-spin .7s linear infinite`. Live dot: `qw-pulse 1.8s infinite`.
- Button press: `transform:scale(.86)`; refresh hover icon `rotate(150deg)`.

## Assets
- **Icons** are inline SVG (Feather `refresh-cw`, `sun`, `moon`) — see `ICON` in the reference JS. No image files.
- **Fonts**: Manrope, Space Grotesk, JetBrains Mono (Google Fonts).
- No raster assets, no logos. (If you add real provider logos for the dots later, swap the colored square for an `<img>`/SVG.)

## Files
- `quotawatch-ui-reference.html` — self-contained vanilla reference (open in a browser). Contains the `popup.css`, `popup.html`, and `popup.js` blocks clearly marked.
- `QuotaWatch Variants.dc.html` — original interactive prototype (visual source of truth; needs its runtime).

## Suggested implementation order
1. Drop the token `:root`/`[data-theme]` + component CSS into `popup.css`.
2. Put the shell markup in `popup.html`.
3. Port the render + event-delegation JS into `popup.js`, keeping `init()`/`refreshDone()`.
4. Reshape `_build_payload()` in `popup.py` to the payload contract; remove the old per-section payload.
5. Decide the native-window width per layout and wire `report_height()` for resize.
6. Map severity + reset logic from `monitor/providers/*` into `sev`/`secs` per field.
7. (Optional) persist `mode`/`theme`/`compact`; follow tray severity colors.
