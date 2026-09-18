/**
 * Chrome.tsx — Monochrome-maximalist primitives.
 *
 * Every element here earns its density: rules carry index numerals, panels
 * carry corner brackets, sections carry marginalia. Risk is expressed through
 * luminance, weight and texture (see .ox-t-* in index.css) so the deck stays
 * legible for hue-blind operators and in printed mission logs.
 */
import type { ReactNode, CSSProperties } from 'react'
import CountUp from './CountUp'

export type Tier = 'Critical' | 'High' | 'Medium' | 'Low' | string

/* ── Risk → texture, never hue ─────────────────────────────────────────── */
export const tierClass = (t: Tier): string =>
  t === 'Critical' ? 'ox-t-critical'
  : t === 'High'   ? 'ox-t-high'
  : t === 'Medium' ? 'ox-t-medium'
  : 'ox-t-low'

/** Ordinal weight 0–3, used for bar fills and sort emphasis. */
export const tierRank = (t: Tier): number =>
  t === 'Critical' ? 3 : t === 'High' ? 2 : t === 'Medium' ? 1 : 0

/** Severity hue for chart marks and any bare numeral that states a tier. */
export const tierInk = (t: Tier): string =>
  t === 'Critical' ? 'var(--sev-critical)'
  : t === 'High'   ? 'var(--sev-high)'
  : t === 'Medium' ? 'var(--sev-medium)'
  : 'var(--sev-low)'

/**
 * Ordered ink ramp for multi-series charts. These stay MONOCHROME on purpose:
 * a feature-importance or metric series is not a severity readout, and hue
 * spent there would dilute the only signal colour is allowed to carry.
 */
export const SERIES_INK = [
  'var(--ink-max)', 'var(--ink-muted)', 'var(--ink-strong)',
  'var(--ink-dim)', 'var(--ink-body)', 'var(--hairline-2)',
]

/* ── Operator decision ladder ───────────────────────────────────────────
 * The four actions sit on the same urgency ramp as the four risk tiers, so
 * they share its hues: escalating is the red end, dismissing the green one.
 * One definition here keeps the buttons and the status chips they produce
 * from ever drifting apart.
 * ─────────────────────────────────────────────────────────────────────── */
export type OperatorStatus =
  | 'escalated' | 'under_assessment' | 'monitoring' | 'reviewed' | 'dismissed' | 'new'

/** Severity token for an operator status, as a `var(--…)` reference. */
export const statusInk = (s: string): string => {
  switch (s) {
    case 'escalated':        return 'var(--sev-critical)'
    case 'under_assessment':
    case 'monitoring':       return 'var(--sev-high)'
    case 'reviewed':         return 'var(--sev-medium)'
    case 'dismissed':        return 'var(--sev-low)'
    default:                 return 'var(--ink-muted)'
  }
}

/** Inline style carrying the ladder hue to .ox-act / .ox-status. */
export const actStyle = (ink: string): CSSProperties =>
  ({ ['--act']: ink } as CSSProperties)

export interface DecisionAction {
  status: Exclude<OperatorStatus, 'new' | 'under_assessment'>
  glyph: string
  label: string
  /** Summary persisted with the assessment record. */
  summary: string
}

/** Ordered most to least urgent — the grid reads as a ladder, top-left down. */
export const DECISION_ACTIONS: DecisionAction[] = [
  { status: 'escalated', glyph: '▲', label: 'Escalate Event',  summary: 'Escalated for Detailed Assessment' },
  { status: 'monitoring', glyph: '◎', label: 'Monitor Closely', summary: 'Marked for Close Monitoring' },
  { status: 'reviewed',   glyph: '✓', label: 'Mark Reviewed',   summary: 'Marked as Reviewed' },
  { status: 'dismissed',  glyph: '✕', label: 'Dismiss Alert',   summary: 'Dismissed as False Alarm' },
]

/** Direction of the PoC trend toward TCA. Rising is the dangerous one. */
export const trendInk = (slope: number): string =>
  slope > 0 ? 'var(--sev-rising)' : slope < 0 ? 'var(--sev-falling)' : 'var(--ink-muted)'

/* ── Priority chip ─────────────────────────────────────────────────────── */
export function RiskChip({ tier, className = '' }: { tier: Tier; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-[3px] border text-[9.5px] font-mono uppercase tracking-[0.18em] leading-none ${tierClass(tier)} ${className}`}
    >
      {tier === 'Critical' && <span className="w-1 h-1 rounded-full bg-current ox-pulse" />}
      {tier}
    </span>
  )
}

/* ── Section rule: [ 04 ] ─ TITLE ─────────────────────────── glyph fill ── */
export function SectionRule({
  index, title, note, className = '',
}: { index?: string | number; title: string; note?: ReactNode; className?: string }) {
  return (
    <div className={`flex items-center gap-3 w-full ${className}`}>
      {index !== undefined && (
        <span className="ox-micro shrink-0" style={{ color: 'var(--ink-dim)' }}>
          [ {String(index).padStart(2, '0')} ]
        </span>
      )}
      <span className="ox-reg" />
      <h3
        className="text-[11px] font-mono uppercase tracking-[0.26em] shrink-0"
        style={{ color: 'var(--ink-strong)' }}
      >
        {title}
      </h3>
      <span className="ox-rule-glyph" />
      {note && <span className="ox-micro shrink-0">{note}</span>}
    </div>
  )
}

/* ── Bracketed panel ───────────────────────────────────────────────────── */
export function Plate({
  children, className = '', bracket = true, style,
}: { children: ReactNode; className?: string; bracket?: boolean; style?: CSSProperties }) {
  return (
    <div className={`ox-panel ${bracket ? 'ox-bracket' : ''} ${className}`} style={style}>
      {children}
    </div>
  )
}

/* ── Dense stat readout ────────────────────────────────────────────────── */
export function Stat({
  label, value, unit, sub, size = 'md', align = 'left',
}: {
  label: string; value: ReactNode; unit?: string; sub?: ReactNode
  size?: 'sm' | 'md' | 'lg'; align?: 'left' | 'right'
}) {
  const scale = size === 'lg' ? 'text-[32px] sm:text-[40px]'
    : size === 'sm' ? 'text-[15px]' : 'text-[22px] sm:text-[26px]'
  return (
    <div className={align === 'right' ? 'text-right' : ''}>
      <p className="ox-micro mb-1.5">{label}</p>
      <p className={`ox-display ${scale} flex items-baseline gap-1 ${align === 'right' ? 'justify-end' : ''}`}>
        {typeof value === 'string' || typeof value === 'number'
          ? <CountUp>{value}</CountUp>
          : value}
        {unit && (
          <span className="text-[10px] font-mono tracking-[0.12em]" style={{ color: 'var(--ink-dim)' }}>
            {unit}
          </span>
        )}
      </p>
      {sub && <p className="ox-micro mt-1.5" style={{ color: 'var(--ink-dim)' }}>{sub}</p>}
    </div>
  )
}

/* ── Vertical gutter label ─────────────────────────────────────────────── */
export function Marginalia({ children }: { children: ReactNode }) {
  return (
    <div className="hidden xl:flex absolute -left-9 top-0 bottom-0 items-start pt-1 select-none">
      <span className="ox-margin-note">{children}</span>
    </div>
  )
}

/* ── Telemetry ticker ──────────────────────────────────────────────────── */
export function Ticker({ items }: { items: string[] }) {
  const run = [...items, ...items]
  return (
    <div
      className="relative overflow-hidden border-y py-1.5"
      style={{ borderColor: 'var(--hairline)', background: 'var(--surface)' }}
    >
      <div className="ox-marquee">
        {run.map((t, i) => (
          <span key={i} className="ox-micro flex items-center gap-3 px-5 shrink-0">
            <span className="ox-reg" />
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ── Page masthead ─────────────────────────────────────────────────────── */
export function Masthead({
  eyebrow, title, lede, right, ghost,
}: { eyebrow: string; title: ReactNode; lede?: ReactNode; right?: ReactNode; ghost?: string }) {
  return (
    <header className="relative pt-7 overflow-hidden">
      {/* Outlined watermark — oversized, clipped, deliberately off the baseline */}
      {ghost && (
        <span
          aria-hidden
          className="pointer-events-none select-none absolute -top-3 right-0 ox-display hidden md:block
                     text-[124px] lg:text-[168px] leading-none whitespace-nowrap"
          style={{
            WebkitTextStroke: '1px var(--hairline-2)',
            color: 'transparent',
            opacity: 0.5,
          }}
        >
          {ghost}
        </span>
      )}
      <div className="ox-rule-heavy mb-4 relative" />
      <div className="relative flex items-start justify-between gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2.5 mb-3">
            <span className="ox-reg" />
            <p className="ox-micro ox-micro-lg" style={{ color: 'var(--ink-muted)' }}>{eyebrow}</p>
          </div>
          <h1 className="ox-display text-[40px] sm:text-[62px] lg:text-[74px]">
            {title}
          </h1>
          {lede && (
            <p
              className="ox-editorial text-[17px] sm:text-[19px] mt-4 max-w-[46ch] leading-[1.42]"
              style={{ color: 'var(--ink-body)' }}
            >
              {lede}
            </p>
          )}
        </div>
        {right && <div className="shrink-0">{right}</div>}
      </div>
      <div className="ox-rule-solid mt-6" />
    </header>
  )
}

/* ── Encounter gauge ─────────────────────────────────────────────────────
 * The table's version of the line drawn in the 3D scene: the same two
 * objects, the same log-scaled gap, the same severity hue dimmed by collision
 * chance. Reading a row and reading the orbit view should teach the same
 * encoding rather than two unrelated ones.
 * ─────────────────────────────────────────────────────────────────────── */
export function EncounterGauge({
  missDistance, riskScore, tier, width = 92,
}: { missDistance: number; riskScore: number; tier: Tier; width?: number }) {
  // Same log mapping the scene uses, expressed as a fraction of the track.
  const norm = Math.max(0, Math.min(1,
    Math.log10(Math.max(missDistance, 0) + 10) / Math.log10(30000)))
  const gap = 0.18 + 0.78 * norm          // fraction of track the pair spans
  const ink = tierInk(tier)
  // Improbable encounters recede; likely ones stay at full strength.
  const strength = 0.3 + 0.7 * riskScore

  return (
    <span
      className="inline-flex items-center align-middle"
      style={{ width }}
      title={`Primary ↔ Secondary · ${missDistance.toFixed(0)} m · P(High) ${riskScore.toFixed(3)}`}
    >
      <span className="relative flex items-center" style={{ width: '100%', height: 9 }}>
        {/* Track the pair sits on */}
        <span className="absolute left-0 right-0 h-px" style={{ background: 'var(--hairline)' }} />
        {/* The link itself */}
        <span
          className="absolute h-px"
          style={{
            left: `${(1 - gap) * 50}%`,
            width: `${gap * 100}%`,
            background: ink,
            opacity: strength,
          }}
        />
        {/* Primary and secondary */}
        {[(1 - gap) * 50, (1 + gap) * 50].map((pos, i) => (
          <span
            key={i}
            className="absolute rounded-full"
            style={{
              left: `${pos}%`,
              width: i === 0 ? 5 : 3.5,
              height: i === 0 ? 5 : 3.5,
              marginLeft: i === 0 ? -2.5 : -1.75,
              background: ink,
              opacity: strength,
            }}
          />
        ))}
      </span>
    </span>
  )
}
