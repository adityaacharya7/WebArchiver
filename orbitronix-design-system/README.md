# Orbitronix Design System — Portable Package
**The Monochrome-Maximalist Aerospace Telemetry Interface**

A complete, self-contained extraction of the Orbitronix design language. This folder is designed to be moved directly into any React / TypeScript / Vite / Next.js project so that developers or AI coding assistants can immediately replicate the exact aesthetic, UI components, typography, and motion primitives.

---

## What’s in this Folder

```
orbitronix-design-system/
├── README.md                 # This guide & integration instructions
├── DESIGN_SYSTEM.md          # Comprehensive design language specification
├── AI_PROMPT.md              # Ready-to-use prompt for AI assistants
├── css/
│   └── theme.css             # Full CSS tokens, Tailwind v4 @theme, and .ox-* utility classes
├── components/
│   ├── Chrome.tsx            # HUD brackets, Plates, Mastheads, SectionRules, Tickers, RiskChips
│   ├── Navigation.tsx        # Top telemetry rail + pill navigation bar
│   ├── MetricCard.tsx        # Telemetry cards with corner plates and texture bands
│   ├── CountUp.tsx           # Universal regex-based number animator
│   ├── Sweep.tsx             # Sensor-acquisition page transition
│   ├── AmbientToggle.tsx     # Ambient audio synthesizer and toggle button
│   └── Panel.tsx             # Surface token helper
├── lib/
│   └── useLenis.ts           # Lenis smooth scrolling hook
├── templates/
│   ├── DashboardTemplate.tsx # Complete sample dashboard demonstrating all primitives
│   └── index.html.template   # Web fonts and HTML setup
└── assets/
    └── icons.svg             # SVG icon sprite sheet
```

---

## Quick Setup in Any New Project

### 1. Dependencies
Install the required packages in your target project:
```bash
npm install framer-motion lenis lucide-react
# Optional, if using Tailwind CSS v4:
npm install tailwindcss @tailwindcss/vite
```

### 2. Fonts (`index.html`)
Add the Google Fonts link into your `index.html` `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Archivo:wght@200;300;400;500;600;700;800;900&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet">
```

### 3. Styles (`index.css`)
Import or paste `css/theme.css` into your project's main stylesheet (`src/index.css` or `src/globals.css`).

### 4. Components
Copy `components/` and `lib/` into your project's `src/` folder.

### 5. Give Context to an AI Assistant
When asking an AI (Antigravity, Claude, ChatGPT, Cursor, Gemini) to build a page or feature in your new project, give it:
1. `AI_PROMPT.md`
2. `DESIGN_SYSTEM.md`
3. Point it to `theme.css` and `Chrome.tsx`

The AI will follow the exact design rules, typography conventions, and layout structures automatically.
