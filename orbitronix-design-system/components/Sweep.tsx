/**
 * Sweep.tsx — sensor-acquisition page transition.
 *
 * A scan bar crosses the viewport; the outgoing page is wiped ahead of the
 * leading edge and the incoming one uncovered behind it. The bar is literally
 * the seam between two clip-paths, so all three share SWEEP_MS and SWEEP_EASE.
 *
 * The clip already sequences the page vertically, so individual plates and
 * rules only need a short settle. What glues them to the bar is a per-element
 * animation-delay derived from measured Y offset — see useSweepStagger.
 */
import { useEffect, useRef, type ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export const SWEEP_MS = 820
/** Settle curve for individual plates. */
export const SWEEP_EASE = [0.62, 0.02, 0.24, 1] as const

/** True when the operator has asked the OS for less motion. */
export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true

/* ── The travelling bar ──────────────────────────────────────────────────
   Driven by framer rather than a CSS keyframe. A CSS animation and framer's
   rAF loop start on different clocks, which left the bar trailing the clip
   seam by ~40ms — visible as new content appearing just before the edge
   reached it. Sharing one animator removes the drift entirely. */
function ScanBar({ token }: { token: string }) {
  const travel = {
    initial: { y: '0vh' },
    animate: { y: '100vh' },
    transition: { duration: SWEEP_MS / 1000, ease: 'linear' as const },
  }
  return (
    <>
      <motion.div key={`bar-${token}`} className="ox-scanbar" aria-hidden="true" {...travel} />
      <motion.div key={`wake-${token}`} className="ox-scanwake" aria-hidden="true" {...travel} />
    </>
  )
}

/**
 * Writes an animation-delay onto every sweep-aware element, proportional to
 * how far down the viewport it sits. An element two-thirds of the way down
 * settles two-thirds of the way through the sweep — which is the moment the
 * bar reaches it.
 */
function useSweepStagger(stageRef: React.RefObject<HTMLDivElement | null>, token: string) {
  useEffect(() => {
    const stage = stageRef.current
    if (!stage || prefersReducedMotion()) return

    stage.classList.add('ox-sweeping')
    const vh = window.innerHeight || 1
    const nodes = stage.querySelectorAll<HTMLElement>(
      '.ox-panel, .ox-bracket, .ox-rule-glyph, .ox-rule-solid, .ox-rule-heavy, [data-sweep]'
    )

    nodes.forEach(node => {
      const top = node.getBoundingClientRect().top
      // Clamp so content below the fold still resolves inside the sweep.
      const ratio = Math.max(0, Math.min(1, top / vh))
      node.style.animationDelay = `${Math.round(ratio * SWEEP_MS)}ms`
    })

    const done = window.setTimeout(() => {
      stage.classList.remove('ox-sweeping')
      nodes.forEach(node => { node.style.animationDelay = '' })
    }, SWEEP_MS + 420)

    return () => {
      window.clearTimeout(done)
      stage.classList.remove('ox-sweeping')
    }
  }, [stageRef, token])
}

interface Props {
  /** Changes whenever a new page should be acquired. */
  pageKey: string
  children: ReactNode
}

export default function Sweep({ pageKey, children }: Props) {
  const stageRef = useRef<HTMLDivElement>(null)
  const mounted = useRef(false)

  // The bar is keyed on pageKey itself rather than on state set from an
  // effect. Driving it from an effect cost one render cycle, which put the
  // clip ~55ms ahead of the bar — a visible gap between the seam and the
  // edge that is supposed to be cutting it. Keying it here means bar and
  // clip start in the same commit.
  useEffect(() => { mounted.current = true }, [])

  useSweepStagger(stageRef, pageKey)
  const reduced = prefersReducedMotion()

  return (
    <>
      {mounted.current && !reduced && <ScanBar token={pageKey} />}
      <div className="ox-stage" ref={stageRef}>
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.div
            key={pageKey}
            initial={reduced ? { opacity: 0 } : { clipPath: 'inset(0% 0% 100% 0%)' }}
            animate={reduced ? { opacity: 1 } : { clipPath: 'inset(0% 0% 0% 0%)' }}
            exit={reduced ? { opacity: 0 } : { clipPath: 'inset(100% 0% 0% 0%)' }}
            // Linear so the clip seam tracks the bar exactly; the bar is the seam.
            transition={{ duration: reduced ? 0.15 : SWEEP_MS / 1000, ease: 'linear' }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </div>
    </>
  )
}
