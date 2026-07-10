// SVG chart components ported from design/mockup.html (the frozen UI spec).
import { useState } from 'react'
import { xyPoints, bandPathD, fmtValue, tickValues } from './chart-utils'

function useTip() {
  const [tip, setTip] = useState(null) // {x, y, html}
  const show = (e, node) =>
    setTip({ x: Math.min(e.clientX + 14, window.innerWidth - 190), y: e.clientY + 14, node })
  return [tip, show, () => setTip(null)]
}

function Tip({ tip }) {
  if (!tip) return null
  return (
    <div className="tip" style={{ left: tip.x, top: tip.y }}>
      {tip.node}
    </div>
  )
}

export function Sparkline({ values, w = 150, h = 30 }) {
  if (!values?.length) return <svg width={w} height={h} />
  const frame = { w, h, pl: 2, pr: 6, pt: 4, pb: 4 }
  const pts = xyPoints(values, frame, Math.min(...values), Math.max(...values))
  const last = pts[pts.length - 1]
  return (
    <svg width={w} height={h}>
      <polyline
        points={pts.map((p) => `${p.x},${p.y}`).join(' ')}
        fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeLinejoin="round"
      />
      <circle cx={last.x} cy={last.y} r="3.5" fill="var(--accent)"
        stroke="var(--surface)" strokeWidth="2" />
    </svg>
  )
}

export function BandChart({ points, label, unit = '', w = 380, h = 150 }) {
  const [tip, show, hide] = useTip()
  if (!points?.length) return <p className="empty">No data yet.</p>
  const frame = { w, h, pl: 40, pr: 60, pt: 10, pb: 20 }
  const values = points.map((p) => p.value)
  const min = Math.min(...values, ...points.map((p) => p.lo))
  const max = Math.max(...values, ...points.map((p) => p.hi))
  const pts = xyPoints(values, frame, min, max)
  const last = pts[pts.length - 1]
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const i = Math.round(((e.clientX - box.left - frame.pl) / (w - frame.pl - frame.pr)) * (points.length - 1))
    if (i < 0 || i >= points.length) return hide()
    const p = points[i]
    show(e, (
      <>
        <div className="t">{p.date}</div>
        {label}: <b>{fmtValue(p.value)}{unit}</b>
        <div className="t">normal {fmtValue(p.lo)}–{fmtValue(p.hi)}</div>
      </>
    ))
  }
  return (
    <div className="chartbox">
      <svg width={w} height={h} onMouseMove={onMove} onMouseLeave={hide}>
        {tickValues(min, max).map((v) => {
          const y = xyPoints([v], frame, min, max)[0].y
          return (
            <g key={v}>
              <line x1={frame.pl} x2={w - frame.pr} y1={y} y2={y} stroke="var(--grid)" />
              <text x={frame.pl - 6} y={y + 4} textAnchor="end">{v}</text>
            </g>
          )
        })}
        <path d={bandPathD(points, frame, min, max)} fill="var(--band)" />
        <polyline points={pts.map((p) => `${p.x},${p.y}`).join(' ')} fill="none"
          stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={last.x} cy={last.y} r="4" fill="var(--accent)"
          stroke="var(--surface)" strokeWidth="2" />
        <text className="endlab" x={last.x + 8} y={last.y + 4}>
          {fmtValue(values[values.length - 1])}{unit}
        </text>
        <text x={frame.pl} y={h - 5}>{points[0].date.slice(5)}</text>
        <text x={w - frame.pr} y={h - 5} textAnchor="end">{points[points.length - 1].date.slice(5)}</text>
      </svg>
      <Tip tip={tip} />
    </div>
  )
}

const STAGES = [
  ['deep_h', 'var(--stage-deep)', 'Deep'],
  ['core_h', 'var(--stage-core)', 'Core'],
  ['rem_h', 'var(--stage-rem)', 'REM'],
  ['awake_h', 'var(--stage-awake)', 'Awake'],
]

export function SleepBars({ nights, w = 780, h = 170 }) {
  const [tip, show, hide] = useTip()
  if (!nights?.length) return <p className="empty">No sleep data yet.</p>
  const pl = 34, pr = 8, pt = 8, pb = 20
  const slot = (w - pl - pr) / nights.length
  const bw = Math.min(24, slot - 2)
  const maxH = Math.max(...nights.map((n) => n.deep_h + n.core_h + n.rem_h + n.awake_h), 8)
  const yScale = (v) => (v / maxH) * (h - pt - pb)
  return (
    <div className="chartbox">
      <div className="legend">
        {STAGES.map(([, c, name]) => (
          <span key={name} className="key">
            <span className="sw" style={{ background: c }} />{name}
          </span>
        ))}
      </div>
      <svg width={w} height={h} onMouseLeave={hide}>
        {[4, 8].map((v) => (
          <g key={v}>
            <line x1={pl} x2={w - pr} y1={h - pb - yScale(v)} y2={h - pb - yScale(v)} stroke="var(--grid)" />
            <text x={pl - 6} y={h - pb - yScale(v) + 4} textAnchor="end">{v}h</text>
          </g>
        ))}
        {nights.map((n, i) => {
          let y = h - pb
          const total = (n.deep_h + n.core_h + n.rem_h).toFixed(1)
          const onMove = (e) =>
            show(e, (
              <>
                <div className="t">{n.date}</div>
                <b>{total}h</b> asleep
                <div className="t">
                  deep {n.deep_h.toFixed(1)}h · core {n.core_h.toFixed(1)}h · REM{' '}
                  {n.rem_h.toFixed(1)}h · awake {n.awake_h.toFixed(1)}h
                </div>
              </>
            ))
          return (
            <g key={n.date} onMouseMove={onMove}>
              {STAGES.map(([k, c], si) => {
                const hh = Math.max(yScale(n[k]) - 2, n[k] > 0 ? 1 : 0)
                y -= yScale(n[k])
                const isTop = si === STAGES.length - 1
                return (
                  <rect key={k} x={pl + i * slot + (slot - bw) / 2} y={y} width={bw}
                    height={hh} fill={c} rx={isTop ? 3 : 0} />
                )
              })}
            </g>
          )
        })}
        <text x={pl} y={h - 5}>{nights[0].date.slice(5)}</text>
        <text x={w - pr} y={h - 5} textAnchor="end">{nights[nights.length - 1].date.slice(5)}</text>
      </svg>
      <Tip tip={tip} />
    </div>
  )
}

export function Columns({ points, goal, w = 780, h = 150, unit = 'steps', grid = [5000, 10000] }) {
  const [tip, show, hide] = useTip()
  if (!points?.length) return <p className="empty">No data yet.</p>
  const pl = 40, pr = 8, pt = 8, pb = 20
  const slot = (w - pl - pr) / points.length
  const bw = Math.min(24, slot - 2)
  const maxV = Math.max(...points.map((p) => p.value), goal || 0) * 1.05
  const y = (v) => h - pb - (v / maxV) * (h - pt - pb)
  return (
    <div className="chartbox">
      <svg width={w} height={h} onMouseLeave={hide}>
        {grid.filter((v) => v < maxV).map((v) => (
          <g key={v}>
            <line x1={pl} x2={w - pr} y1={y(v)} y2={y(v)} stroke="var(--grid)" />
            <text x={pl - 6} y={y(v) + 4} textAnchor="end">{v >= 1000 ? `${v / 1000}k` : v}</text>
          </g>
        ))}
        {points.map((p, i) => (
          <rect key={p.date} x={pl + i * slot + (slot - bw) / 2} y={y(p.value)}
            width={bw} height={h - pb - y(p.value)} fill="var(--accent)" rx="3"
            onMouseMove={(e) =>
              show(e, (
                <>
                  <div className="t">{p.date}</div>
                  <b>{fmtValue(p.value)}</b> {unit}
                </>
              ))
            }
          />
        ))}
        {goal && (
          <g>
            <line x1={pl} x2={w - pr} y1={y(goal)} y2={y(goal)} stroke="var(--axis)" />
            <text x={pl + 4} y={y(goal) - 5}>goal {goal >= 1000 ? `${goal / 1000}k` : goal}</text>
          </g>
        )}
        <text x={pl} y={h - 5}>{points[0].date.slice(5)}</text>
        <text x={w - pr} y={h - 5} textAnchor="end">{points[points.length - 1].date.slice(5)}</text>
      </svg>
      <Tip tip={tip} />
    </div>
  )
}

export function TableView({ cols, rows }) {
  return (
    <details className="tbl">
      <summary>Table view</summary>
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}
