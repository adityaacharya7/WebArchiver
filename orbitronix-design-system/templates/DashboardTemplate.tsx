import React, { useState } from 'react'
import {
  Plate,
  SectionRule,
  Masthead,
  Ticker,
  RiskChip,
  Stat,
  Marginalia,
  DECISION_ACTIONS,
  actStyle,
  statusInk,
  trendInk,
  type Tier,
  type OperatorStatus,
} from '../components/Chrome'
import MetricCard from '../components/MetricCard'

interface TelemetryRow {
  id: string
  target: string
  chaser: string
  tcaHours: number
  missDistanceKm: number
  riskScore: number
  tier: Tier
  trend: number
  status: OperatorStatus
}

const SAMPLE_ROWS: TelemetryRow[] = [
  {
    id: 'EVT-9042',
    target: 'STARLINK-2104',
    chaser: 'COSMOS-1408 DEB',
    tcaHours: 14.2,
    missDistanceKm: 0.182,
    riskScore: 0.942,
    tier: 'Critical',
    trend: 0.24,
    status: 'escalated',
  },
  {
    id: 'EVT-8811',
    target: 'ONEWEB-0142',
    chaser: 'FENGYUN-1C DEB',
    tcaHours: 28.5,
    missDistanceKm: 0.450,
    riskScore: 0.781,
    tier: 'High',
    trend: 0.08,
    status: 'monitoring',
  },
  {
    id: 'EVT-7634',
    target: 'SENTINEL-6A',
    chaser: 'CZ-4C R/B',
    tcaHours: 51.0,
    missDistanceKm: 1.120,
    riskScore: 0.435,
    tier: 'Medium',
    trend: -0.05,
    status: 'reviewed',
  },
  {
    id: 'EVT-6109',
    target: 'ISS (ZARYA)',
    chaser: 'SL-16 DEB',
    tcaHours: 68.3,
    missDistanceKm: 4.890,
    riskScore: 0.112,
    tier: 'Low',
    trend: -0.18,
    status: 'dismissed',
  },
]

export default function DashboardTemplate() {
  const [activeFilter, setActiveFilter] = useState<string>('ALL')
  const [selectedId, setSelectedId] = useState<string>('EVT-9042')

  const selectedEvent = SAMPLE_ROWS.find(r => r.id === selectedId) || SAMPLE_ROWS[0]

  return (
    <div className="min-h-screen bg-[var(--ground)] text-[var(--ink-body)] p-4 sm:p-8 relative">
      {/* ── Page Masthead ────────────────────────────────────────── */}
      <div className="max-w-[1400px] mx-auto space-y-6">
        <Masthead
          eyebrow="MISSION CONTROL · ORBITAL RADAR"
          title={
            <>
              CONJUNCTION <span className="ox-editorial-i text-[var(--ink-muted)]">TELEMETRY</span>
            </>
          }
          lede="Real-time orbital conjunction assessment deck with Bayesian collision probability modeling."
          ghost="TELEMETRY"
          right={
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-2 px-3 py-1.5 border border-[var(--hairline-2)] text-[10px] font-mono tracking-widest uppercase">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--sev-low)] ox-pulse" />
                SYSTEM READY
              </span>
            </div>
          }
        />

        {/* ── Live Telemetry Ticker ─────────────────────────────── */}
        <Ticker
          items={[
            'PRIMARY RADAR LOCK: ACTIVE',
            'TRACKED OBJECTS: 28,490',
            'PREDICTIVE ACCURACY: 98.4%',
            'SOLAR FLUX INDEX: 142 SFU',
            'KALMAN FILTER: CONVERGED',
          ]}
        />

        {/* ── Top Metric Cards Grid ─────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="ACTIVE ALERTS"
            value="142"
            sublabel="8 CRITICAL IN NEXT 24H"
            accent="critical"
            index={1}
          />
          <MetricCard
            label="CLOSE APPROACHES"
            value="1,248"
            sublabel="MISS DISTANCE < 5.0 KM"
            accent="high"
            index={2}
          />
          <MetricCard
            label="FALSE ALARM DROP"
            value="73.4%"
            sublabel="PIPELINE PRUNING"
            accent="electric"
            index={3}
          />
          <MetricCard
            label="RADAR SENSOR SWEEP"
            value="0.82s"
            sublabel="CYCLE LATENCY"
            accent="electric"
            index={4}
          />
        </div>

        {/* ── Main Data Deck Split ──────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pt-4">
          {/* Left: Dense Telemetry Table (8 cols) */}
          <div className="lg:col-span-8 space-y-4 relative">
            <Marginalia>FEED // TIER 01-04</Marginalia>

            <div className="flex items-center justify-between gap-4">
              <SectionRule index={1} title="CONJUNCTION EVENT STREAM" note="SORTED BY RISK" />
              <div className="flex items-center gap-1 shrink-0">
                {['ALL', 'CRITICAL', 'HIGH'].map(f => (
                  <button
                    key={f}
                    onClick={() => setActiveFilter(f)}
                    className={`ox-btn ${activeFilter === f ? 'ox-btn-on' : ''}`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>

            <Plate className="overflow-x-auto">
              <table className="w-full text-left border-collapse font-mono text-[11px]">
                <thead>
                  <tr className="border-b border-[var(--hairline)] text-[var(--ink-muted)] ox-micro">
                    <th className="p-3">EVENT ID</th>
                    <th className="p-3">TARGET / CHASER</th>
                    <th className="p-3 text-right">TCA (H)</th>
                    <th className="p-3 text-right">MISS (KM)</th>
                    <th className="p-3">TREND</th>
                    <th className="p-3">PRIORITY</th>
                    <th className="p-3">STATUS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--hairline)]">
                  {SAMPLE_ROWS.map(row => (
                    <tr
                      key={row.id}
                      onClick={() => setSelectedId(row.id)}
                      className={`cursor-pointer transition-colors hover:bg-[var(--signal-soft)] ${
                        selectedId === row.id ? 'bg-[var(--signal-soft)] border-l-2 border-l-[var(--signal)]' : ''
                      }`}
                    >
                      <td className="p-3 text-[var(--ink-max)] font-semibold">{row.id}</td>
                      <td className="p-3">
                        <div className="text-[var(--ink-strong)]">{row.target}</div>
                        <div className="text-[var(--ink-dim)] text-[10px]">{row.chaser}</div>
                      </td>
                      <td className="p-3 text-right ox-num">{row.tcaHours.toFixed(1)}h</td>
                      <td className="p-3 text-right ox-num">{row.missDistanceKm.toFixed(3)}</td>
                      <td className="p-3" style={{ color: trendInk(row.trend) }}>
                        {row.trend > 0 ? '▲ RISING' : '▼ DECAY'}
                      </td>
                      <td className="p-3">
                        <RiskChip tier={row.tier} />
                      </td>
                      <td className="p-3">
                        <span
                          className="px-2 py-0.5 ox-status text-[9px] uppercase tracking-wider"
                          style={actStyle(statusInk(row.status))}
                        >
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Plate>
          </div>

          {/* Right: Operator Decision Ladder (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            <SectionRule index={2} title="OPERATOR ACTIONS" note="DECISION LADDER" />

            <Plate className="p-5 space-y-5">
              <div>
                <p className="ox-micro mb-1">SELECTED CONJUNCTION</p>
                <h4 className="text-[20px] font-mono text-[var(--ink-max)]">{selectedEvent.id}</h4>
                <p className="text-[12px] text-[var(--ink-dim)]">
                  {selectedEvent.target} vs {selectedEvent.chaser}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 p-3 bg-[var(--surface-2)] border border-[var(--hairline)]">
                <Stat label="MISS DISTANCE" value={selectedEvent.missDistanceKm} unit="KM" size="sm" />
                <Stat label="TIME TO TCA" value={selectedEvent.tcaHours} unit="HRS" size="sm" />
              </div>

              <div className="space-y-2 pt-2">
                <p className="ox-micro text-[var(--ink-dim)]">COMMITTED ACTIONS</p>
                {DECISION_ACTIONS.map(act => {
                  const isCommitted = selectedEvent.status === act.status
                  const ink = statusInk(act.status)
                  return (
                    <button
                      key={act.status}
                      style={actStyle(ink)}
                      className={`w-full flex items-center justify-between p-2.5 font-mono text-[10.5px] uppercase tracking-[0.14em] transition-all ${
                        isCommitted ? 'ox-act-on' : 'ox-act'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span>{act.glyph}</span>
                        <span>{act.label}</span>
                      </span>
                      {isCommitted && <span className="text-[9px]">CONFIRMED</span>}
                    </button>
                  )
                })}
              </div>
            </Plate>
          </div>
        </div>
      </div>
    </div>
  )
}
