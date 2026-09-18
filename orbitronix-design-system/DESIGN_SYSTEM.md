# ORBITRONIX DESIGN SYSTEM SPECIFICATION
## "Monochrome Maximalist Aerospace Telemetry"

---

## 1. Core Philosophy

The Orbitronix design language is modeled after **aerospace telemetry consoles, radar decks, and orbital flight instruments**. 

Key principles:
1. **Luminance, Weight, and Texture Over Hue**: Information priority and risk are expressed through brightness (luminance), typographic weight, and textural patterns (crosshatches, stipples, solid blocks) rather than rainbow hues.
2. **Hue is a Reserved Weapon**: Color is **strictly prohibited** for decorative accents. Color is reserved exclusively for **severity / urgency ratings** (Critical, High, Medium, Low) and trend directions (Rising, Falling).
3. **Monochrome Maximalism**: The deck is dense, informative, and technical. It fills negative space with purposeful structural marginalia: corner brackets, registration crosshairs (`+`), indexing numerals (`[ 01 ]`), repeating glyph rules, and telemetry tickers.
4. **Instrument in a Dark Room**: The UI operates on a deep, warm-neutral dark ground (`#0c0c0b`). It feels like high-precision hardware manufactured for mission-critical operations.

---

## 2. Color Palette & Tokens

### The Ink Ramp (Warm-Neutral Ground)
```css
--color-ink-000: #000000;
--color-ink-050: #070706;
--color-ink-100: #0c0c0b; /* Primary ground */
--color-ink-150: #111110;
--color-ink-200: #161614; /* Surface background */
--color-ink-250: #1c1c1a; /* Secondary surface */
--color-ink-300: #232320;
--color-ink-400: #2e2e2a;
--color-ink-500: #3d3d38;
--color-ink-600: #5a5a53; /* Dim text */
--color-ink-700: #85857c; /* Muted text & rules */
--color-ink-800: #b4b4a9; /* Body text */
--color-ink-900: #e4e4db; /* Strong headings */
--color-ink-950: #f7f7f0; /* Maximum signal / primary white */
```

### Runtime Surface & Line Tokens
| Token | Value | Purpose |
|---|---|---|
| `--ground` | `#0c0c0b` | Base page canvas |
| `--ground-deep` | `#070706` | Insets, scrollbar tracks |
| `--surface` | `rgba(22, 22, 20, 0.72)` | Frosted glass cards and panels |
| `--surface-2` | `rgba(28, 28, 26, 0.90)` | Machined inset plates |
| `--hairline` | `rgba(133, 133, 124, 0.16)` | Subtle dividing borders |
| `--hairline-2` | `rgba(133, 133, 124, 0.30)` | Active/hover borders |
| `--rule` | `rgba(133, 133, 124, 0.42)` | Structural dividing lines & corner brackets |
| `--signal` | `#f7f7f0` | High-contrast highlights and active state fills |
| `--signal-soft` | `rgba(247, 247, 240, 0.08)` | Subtle hover fills |
| `--grid` | `rgba(133, 133, 124, 0.055)` | Blueprint substrate grid |

### Severity Tokens (Reserved Chromatic Palette)
| Tier | Token | Color | Texture / Pattern |
|---|---|---|---|
| **Critical** | `--sev-critical` | `#f2555a` | **Solid Fill**: Maximum contrast, pulsing indicator dot |
| **High** | `--sev-high` | `#f5952f` | **Dense 45° Hatch**: 1px stripes at 4px intervals |
| **Medium** | `--sev-medium` | `--sev-medium`: `#e8c84a` | **Sparse Dot Field**: 0.7px radial dots on 4px grid |
| **Low** | `--sev-low` | `#4fb477` | **Quiet Tint**: Semi-transparent fill with border |
| **Rising Trend** | `--sev-rising` | `#f2555a` | Slope climbing toward critical threshold |
| **Falling Trend** | `--sev-falling` | `#4fb477` | Slope decaying safely |

---

## 3. Typography System

The interface uses four distinct typefaces in strict functional roles:

1. **Grotesque UI (`DM Sans`)** — Primary reading text and controls.
   - Clean, geometric, neutral.
   - CSS: `--font-sans: 'DM Sans', system-ui, sans-serif;`
2. **Monospace Telemetry (`JetBrains Mono`)** — All data points, coordinates, status codes, micro-labels, and table cells.
   - Must use tabular numbers (`tabular-nums`).
   - CSS: `--font-mono: 'JetBrains Mono', ui-monospace, monospace;`
3. **Display Numeral (`Archivo`)** — Oversized metric numerals and masthead titles.
   - Ultra-light weight (`font-weight: 200`), tight tracking (`letter-spacing: -0.045em`), compressed line-height (`0.88`).
   - CSS: `--font-display: 'Archivo', 'DM Sans', sans-serif;`
4. **Editorial Serif (`Instrument Serif`)** — Rare contrasting accents, notes, or italicized quotes.
   - Used sparingly to create high-low typographic tension.
   - CSS: `--font-editorial: 'Instrument Serif', Georgia, serif;`

### Micro-Typography Conventions
- **Micro Label (`.ox-micro`)**:
  ```css
  font-family: 'JetBrains Mono', monospace;
  font-size: 9.5px;
  line-height: 1.1;
  text-transform: uppercase;
  letter-spacing: 0.22em;
  color: var(--ink-muted);
  ```
- **Index Tag**: `[ 01 ]`, `[ 02 ]` set in `var(--ink-dim)` before section headers.
- **Watermark/Ghost Heading**: Clipped, 1px outlined text set in `.ox-display` at `124px–168px` behind page mastheads with `WebkitTextStroke: 1px var(--hairline-2)` and `opacity: 0.5`.

---

## 4. Textures, Atmosphere & Substrates

### 1. Film Grain
A high-frequency SVG fractal noise layer drifts subtly over the viewport at `3%` opacity:
```css
body::after {
  content: ''; position: fixed; inset: -50%; z-index: 9999; pointer-events: none;
  opacity: var(--grain);
  background-image: url("data:image/svg+xml,...");
  animation: grain-drift 800ms steps(4) infinite;
}
```

### 2. Dual Blueprint Grid
A dual-frequency (128px major grid + 16px minor grid) radial-masked substrate:
```css
body::before {
  content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px),
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 128px 128px, 128px 128px, 16px 16px, 16px 16px;
  mask-image: radial-gradient(ellipse 110% 80% at 50% 0%, #000 30%, transparent 88%);
}
```

### 3. Flight Instrument Corner Brackets
Panels feature 9px optical L-brackets in opposing corners (`.ox-bracket`):
```css
.ox-bracket::before { top: -1px; left: -1px; border-top: 1px solid var(--rule); border-left: 1px solid var(--rule); }
.ox-bracket::after  { bottom: -1px; right: -1px; border-bottom: 1px solid var(--rule); border-right: 1px solid var(--rule); }
```

### 4. Registration Crosshair (`.ox-reg`)
An 11×11px technical reticle used beside headers:
```css
.ox-reg { position: relative; width: 11px; height: 11px; flex: none; opacity: 0.6; }
.ox-reg::before { left: 50%; top: 0; bottom: 0; width: 1px; transform: translateX(-50%); }
.ox-reg::after  { top: 50%; left: 0; right: 0; height: 1px; transform: translateY(-50%); }
```

### 5. Repeating Glyph Rule (`.ox-rule-glyph`)
Fills horizontal space between header titles and status labels with vertical micro-ticks:
```css
.ox-rule-glyph {
  flex: 1; height: 7px; min-width: 12px;
  background-image: repeating-linear-gradient(90deg,
    var(--rule) 0px, var(--rule) 1px, transparent 1px, transparent 5px);
  opacity: 0.55;
}
```

---

## 5. Component Patterns

### 1. Masthead Header
- Top rule: `.ox-rule-heavy` (1px solid `var(--rule)`).
- Eyebrow: Registration mark + `.ox-micro` category label.
- Title: Massive `.ox-display` heading.
- Ghost stamp in background.
- Right rail: Status metrics or action buttons.

### 2. MetricCard
- Corner index number (`01`, `02`, etc.) in top right.
- Top 3px texture stripe (`accentTexture[accent]`).
- `.ox-micro` title.
- Huge `.ox-display` number wrapped in `<CountUp>`.
- Solid hairline separator + micro sublabel note.

### 3. SectionRule
- Form: `[ 01 ] ── + TITLE ───────────── (glyphs) ── [Optional Note]`

### 4. Telemetry Ticker
- Continuous horizontal marquee running on a loop.
- Contains system status strings separated by registration crosshairs.

### 5. Operator Decision Ladder
Actions are mapped directly to the urgency tiers:
- **Escalate** (Red / Critical)
- **Monitor** (Amber / High)
- **Review** (Yellow / Medium)
- **Dismiss** (Green / Low)
Each action button sets `--act: <color>` and applies `.ox-act`, turning solid upon commitment (`.ox-act-on`).

### 6. Sensor Acquisition Sweep (`Sweep.tsx`)
Page transitions mimic an optical radar/sensor sweep:
- A glowing 1px scanline (`.ox-scanbar`) sweeps from `0vh` to `100vh` over `820ms`.
- Trailing wake (`.ox-scanwake`) diffuses behind it.
- Panels and rules uncover with staggered delays relative to their Y-position.

---

## 6. Do's and Don'ts for Replication

- **DO** use uppercase monospace text with wide tracking for all labels, keys, and metadata.
- **DO** use corner brackets and registration marks on data cards.
- **DO** make numbers oversized (`36px+`) with thin font weights.
- **DO** use tabular numerals (`font-variant-numeric: tabular-nums`) everywhere numbers appear.
- **DON'T** use random saturated colors (blue, purple, pink) for buttons, badges, or backgrounds.
- **DON'T** use rounded pill buttons with bright gradients. All buttons must be crisp, bordered, and monospace.
- **DON'T** use standard generic cards with soft box shadows. Use 1px borders with `backdrop-filter: blur(14px)`.
