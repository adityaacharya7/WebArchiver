import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import AmbientToggle from './AmbientToggle'

const navItems = [
  { id: 'overview', label: 'Overview' },
  { id: 'orbitview', label: '3D Orbit View' },
  { id: 'alerts', label: 'Active Alerts' },
  { id: 'assessment', label: 'Event Assessment' },
  { id: 'model-details', label: 'Model Details' },
  { id: 'analytics', label: 'Risk Analytics' },
  { id: 'evaluation', label: 'Evaluation' },
  { id: 'documentation', label: 'Documentation' },
]

interface Props {
  activePage: string
  setActivePage: (page: string) => void
  ambient: boolean
  toggleAmbient: () => void
}

export default function Navigation({ activePage, setActivePage, ambient, toggleAmbient }: Props) {
  const [menuOpen, setMenuOpen] = useState(false)

  const handleNav = (id: string) => {
    setActivePage(id)
    setMenuOpen(false)
  }

  const activeIdx = Math.max(0, navItems.findIndex(n => n.id === activePage))

  return (
    <>
      <nav
        className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl border-b"
        style={{ background: 'var(--surface)', borderColor: 'var(--hairline-2)' }}
      >
        {/* ── Upper rail: identity + status telemetry ─────────────────── */}
        <div
          className="max-w-[1460px] mx-auto px-3 sm:px-6 h-[26px] flex items-center justify-between border-b"
          style={{ borderColor: 'var(--hairline)' }}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="ox-micro shrink-0" style={{ color: 'var(--ink-dim)' }}>
              ESA·KELVINS / HOLDOUT
            </span>
            <span className="ox-rule-glyph hidden sm:block max-w-[80px]" />
            <span className="ox-micro shrink-0 hidden sm:inline" style={{ color: 'var(--ink-dim)' }}>
              LGBM·XGB v1.0
            </span>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="ox-micro hidden md:inline" style={{ color: 'var(--ink-dim)' }}>
              NDCG@10 1.0000
            </span>
            <span className="ox-micro hidden lg:inline" style={{ color: 'var(--ink-dim)' }}>
              P@10 1.0000
            </span>
            <span className="flex items-center gap-1.5">
              <span
                className="w-[5px] h-[5px] rounded-full ox-pulse"
                style={{ background: 'var(--signal)' }}
              />
              <span className="ox-micro" style={{ color: 'var(--ink-strong)' }}>ACTIVE</span>
            </span>
          </div>
        </div>

        {/* ── Main rail ────────────────────────────────────────────────── */}
        <div className="max-w-[1460px] mx-auto px-3 sm:px-6 h-[54px] flex items-center justify-between gap-4">
          {/* Wordmark */}
          <button
            onClick={() => handleNav('overview')}
            className="ox-focus flex items-baseline gap-2.5 shrink-0 text-left"
          >
            <span
              className="ox-display text-[19px] tracking-[-0.02em] font-[600]"
              style={{ color: 'var(--ink-max)' }}
            >
              ORBITRONIX
            </span>
            <span className="ox-micro hidden sm:inline" style={{ color: 'var(--ink-dim)' }}>
              ®
            </span>
          </button>

          {/* Desktop nav — numbered, ruled */}
          <div className="hidden lg:flex items-stretch h-full">
            {navItems.map((item, i) => {
              const on = activePage === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => handleNav(item.id)}
                  className="ox-focus relative group px-3 flex flex-col justify-center border-l transition-colors duration-200"
                  style={{ borderColor: 'var(--hairline)' }}
                >
                  {on && (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0"
                      style={{ background: 'var(--signal-soft)' }}
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                    />
                  )}
                  {on && (
                    <motion.span
                      layoutId="nav-active-bar"
                      className="absolute left-0 right-0 bottom-0 h-[2px]"
                      style={{ background: 'var(--signal)' }}
                      transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                    />
                  )}
                  <span
                    className="relative z-10 ox-num text-[8px] tracking-[0.12em] mb-[3px]"
                    style={{ color: on ? 'var(--ink-muted)' : 'var(--ink-dim)' }}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span
                    className="relative z-10 text-[11px] font-medium tracking-[0.03em] transition-colors duration-200"
                    style={{ color: on ? 'var(--ink-max)' : 'var(--ink-muted)' }}
                  >
                    {item.label}
                  </span>
                </button>
              )
            })}
            <span className="border-l" style={{ borderColor: 'var(--hairline)' }} />
          </div>

          {/* Right rail */}
          <div className="flex items-center gap-3 shrink-0">
            <span className="ox-micro hidden xl:inline" style={{ color: 'var(--ink-dim)' }}>
              {String(activeIdx + 1).padStart(2, '0')} / {String(navItems.length).padStart(2, '0')}
            </span>
            <AmbientToggle on={ambient} toggle={toggleAmbient} />
            <button
              onClick={() => setMenuOpen(o => !o)}
              className="ox-focus lg:hidden flex flex-col gap-[5px] p-1.5"
              aria-label="Toggle menu"
            >
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="block w-[18px] h-[1.5px] transition-all duration-200"
                  style={{
                    background: 'var(--ink-max)',
                    transform: menuOpen
                      ? i === 0 ? 'rotate(45deg) translate(4px,5px)'
                        : i === 2 ? 'rotate(-45deg) translate(4px,-5px)' : 'none'
                      : 'none',
                    opacity: menuOpen && i === 1 ? 0 : 1,
                  }}
                />
              ))}
            </button>
          </div>
        </div>
      </nav>

      {/* ── Mobile drawer ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 backdrop-blur-sm lg:hidden"
              style={{ background: 'var(--vignette)' }}
              onClick={() => setMenuOpen(false)}
            />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', stiffness: 360, damping: 32 }}
              className="fixed top-0 right-0 bottom-0 z-50 w-[min(21rem,calc(100vw-1.5rem))] lg:hidden flex flex-col border-l"
              style={{ background: 'var(--ground)', borderColor: 'var(--hairline-2)' }}
            >
              <div
                className="h-[54px] flex items-center justify-between px-5 border-b"
                style={{ borderColor: 'var(--hairline)' }}
              >
                <span className="ox-micro ox-micro-lg" style={{ color: 'var(--ink-strong)' }}>
                  INDEX
                </span>
                <button
                  onClick={() => setMenuOpen(false)}
                  className="ox-micro"
                  style={{ color: 'var(--ink-muted)' }}
                >
                  CLOSE ✕
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                {navItems.map((item, i) => {
                  const on = activePage === item.id
                  return (
                    <button
                      key={item.id}
                      onClick={() => handleNav(item.id)}
                      className="w-full text-left px-5 py-3.5 flex items-center gap-3 border-b transition-colors"
                      style={{
                        borderColor: 'var(--hairline)',
                        background: on ? 'var(--signal-soft)' : 'transparent',
                      }}
                    >
                      <span className="ox-num text-[9px]" style={{ color: 'var(--ink-dim)' }}>
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span
                        className="text-[13px] font-medium flex-1"
                        style={{ color: on ? 'var(--ink-max)' : 'var(--ink-muted)' }}
                      >
                        {item.label}
                      </span>
                      {on && <span className="w-[5px] h-[5px]" style={{ background: 'var(--signal)' }} />}
                    </button>
                  )
                })}
              </div>
              <div className="px-5 py-4 border-t" style={{ borderColor: 'var(--hairline)' }}>
                <div className="flex items-center gap-2">
                  <span
                    className="w-[5px] h-[5px] rounded-full ox-pulse"
                    style={{ background: 'var(--signal)' }}
                  />
                  <span className="ox-micro" style={{ color: 'var(--ink-strong)' }}>SYSTEM ACTIVE</span>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
