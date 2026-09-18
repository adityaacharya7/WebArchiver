import { useEffect, useState } from 'react'

const KEY = 'orbitronix.ambient'

/**
 * The ambient layer — standing scanline, drifting grid, edge shimmer — is
 * striking for a minute and wearing across a shift, so it is opt-in and
 * remembered per operator rather than always on.
 */
export function useAmbient(): [boolean, () => void] {
  const [on, setOn] = useState(() => {
    try { return localStorage.getItem(KEY) === 'on' } catch { return false }
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-ambient', on ? 'on' : 'off')
    try { localStorage.setItem(KEY, on ? 'on' : 'off') } catch { /* private mode */ }
  }, [on])

  return [on, () => setOn(v => !v)]
}

export default function AmbientToggle({ on, toggle }: { on: boolean; toggle: () => void }) {
  return (
    <button
      onClick={toggle}
      aria-pressed={on}
      aria-label="Toggle ambient motion"
      title={on ? 'Ambient motion on' : 'Ambient motion off'}
      className="ox-focus group flex items-center gap-1.5 px-2 py-[3px] border shrink-0 transition-colors"
      style={{
        borderColor: on ? 'var(--signal)' : 'var(--hairline-2)',
        background: on ? 'var(--signal)' : 'transparent',
      }}
    >
      {/* Three bars standing in for a running scan */}
      <span className="flex items-end gap-[2px] h-[9px]" aria-hidden="true">
        {[0, 1, 2].map(i => (
          <span
            key={i}
            className="w-[2px]"
            style={{
              background: on ? 'var(--invert-fg)' : 'var(--ink-muted)',
              height: on ? '100%' : '45%',
              animation: on ? `ox-amb-bar 1.1s ease-in-out ${i * 0.16}s infinite` : 'none',
            }}
          />
        ))}
      </span>
      <span
        className="text-[8px] font-mono tracking-[0.14em] leading-none"
        style={{ color: on ? 'var(--invert-fg)' : 'var(--ink-dim)' }}
      >
        AMB
      </span>
    </button>
  )
}
