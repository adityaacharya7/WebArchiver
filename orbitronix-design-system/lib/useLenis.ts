import { useEffect } from 'react'
import Lenis from 'lenis'

/**
 * Smooth-scroll for the deck. A single Lenis instance drives the whole
 * document; framer-motion page transitions (Sweep) animate clip-path/opacity
 * on their own elements and don't fight with it.
 *
 * Respects prefers-reduced-motion — smooth scrolling is a comfort layer,
 * not a requirement, so operators who've asked the OS for less motion get
 * native instant scrolling instead.
 */
export function useLenis() {
  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduced) return

    const lenis = new Lenis({
      duration: 1.1,
      smoothWheel: true,
    })

    let frameId: number
    function raf(time: number) {
      lenis.raf(time)
      frameId = requestAnimationFrame(raf)
    }
    frameId = requestAnimationFrame(raf)

    return () => {
      cancelAnimationFrame(frameId)
      lenis.destroy()
    }
  }, [])
}
