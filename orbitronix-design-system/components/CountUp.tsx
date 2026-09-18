/**
 * CountUp.tsx — numerals spin up to their value as the sweep uncovers them.
 *
 * Takes the already-formatted string the deck would have rendered anyway
 * ("24,020", "70.9%", "1.0000", "$1.2M") and animates only the numeric run
 * inside it, preserving prefix, suffix, decimal places and thousands
 * separators exactly. Call sites need no changes and no raw values.
 */
import { useEffect, useRef, useState } from 'react'
import { prefersReducedMotion, SWEEP_MS } from './Sweep'

const NUMERIC = /^(\D*?)(-?[\d,]+(?:\.\d+)?)(.*)$/s

interface Parsed {
  prefix: string
  suffix: string
  value: number
  decimals: number
  grouped: boolean
}

function parse(text: string): Parsed | null {
  const m = NUMERIC.exec(text.trim())
  if (!m) return null
  const [, prefix, raw, suffix] = m
  const value = Number(raw.replace(/,/g, ''))
  if (!Number.isFinite(value)) return null
  const dot = raw.indexOf('.')
  return {
    prefix,
    suffix,
    value,
    decimals: dot === -1 ? 0 : raw.length - dot - 1,
    grouped: raw.includes(','),
  }
}

const format = (n: number, p: Parsed) =>
  p.prefix +
  (p.grouped
    ? n.toLocaleString('en-US', { minimumFractionDigits: p.decimals, maximumFractionDigits: p.decimals })
    : n.toFixed(p.decimals)) +
  p.suffix

interface Props {
  children: string | number
  /** Fraction of the sweep to spend counting. */
  duration?: number
  className?: string
}

export default function CountUp({ children, duration = SWEEP_MS * 0.8, className }: Props) {
  const text = String(children)
  const parsed = parse(text)
  const [display, setDisplay] = useState(() => (parsed ? format(0, parsed) : text))
  const frame = useRef(0)

  useEffect(() => {
    if (!parsed || prefersReducedMotion()) { setDisplay(text); return }

    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      // Ease out so the last digits settle rather than snap.
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(format(parsed.value * eased, parsed))
      if (t < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame.current)
    // Re-run whenever the rendered figure itself changes.
  }, [text]) // eslint-disable-line react-hooks/exhaustive-deps

  return <span className={className}>{display}</span>
}
