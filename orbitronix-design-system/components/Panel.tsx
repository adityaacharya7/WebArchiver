/**
 * Shared surface tokens. The deck is ink-only, so these resolve straight to
 * the CSS custom properties with no theme branch.
 */
export function usePanel() {
  return {
    panel: 'ox-panel ox-bracket',
    label: 'text-[var(--ink-muted)]',
    text: 'text-[var(--ink-max)]',
    muted: 'text-[var(--ink-muted)]',
    sublabel: 'text-[var(--ink-dim)]',
    tooltip: {
      background: '#111110',
      border: '1px solid #3d3d38',
      borderRadius: 0,
      fontSize: 11,
      fontFamily: 'JetBrains Mono, monospace',
      color: '#f7f7f0',
      boxShadow: '0 8px 28px rgba(0,0,0,0.6)',
    },
    tickFill: '#85857c',
  }
}
