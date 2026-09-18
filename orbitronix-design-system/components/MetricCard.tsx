import { motion } from 'framer-motion'
import CountUp from './CountUp'

interface Props {
  label: string
  value: string | number
  sublabel?: string
  /** Retained for call-site compatibility; now drives texture, not hue. */
  accent?: 'electric' | 'critical' | 'high' | 'medium'
  delay?: number
  index?: number
}

/**
 * Accent maps to the severity band. `electric` is the neutral option for
 * cards that report a metric rather than a risk level — colour on those
 * would imply a danger reading that isn't there.
 */
const accentTexture: Record<string, string> = {
  critical: 'ox-t-critical',
  high: 'ox-t-high',
  medium: 'ox-t-medium',
  electric: 'ox-t-neutral-solid',
}

export default function MetricCard({
  label, value, sublabel, accent = 'electric', delay = 0, index,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="ox-panel ox-bracket group relative min-w-0 p-4 sm:p-5 overflow-hidden"
    >
      {/* Texture band — the hue replacement */}
      <div
        className={`absolute top-0 left-0 right-0 h-[3px] border-0 ${accentTexture[accent]}`}
        style={{ opacity: 0.9 }}
      />

      {/* Index numeral, set in the corner like a plate reference */}
      {index !== undefined && (
        <span
          className="absolute top-3 right-3 ox-num text-[10px] tracking-[0.1em]"
          style={{ color: 'var(--ink-dim)' }}
        >
          {String(index).padStart(2, '0')}
        </span>
      )}

      <p className="ox-micro mb-3 pr-7">{label}</p>
      <p className="ox-display text-[30px] sm:text-[38px] leading-[0.9] transition-transform duration-300 group-hover:-translate-y-[1px]">
        <CountUp>{value}</CountUp>
      </p>

      {sublabel && (
        <>
          <div className="ox-rule-solid my-3" />
          <p className="ox-micro" style={{ color: 'var(--ink-dim)', letterSpacing: '0.14em' }}>
            {sublabel}
          </p>
        </>
      )}
    </motion.div>
  )
}
