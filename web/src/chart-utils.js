// Pure geometry + formatting helpers shared by all SVG charts.

export function xyPoints(values, frame, min, max) {
  const { w, h, pl, pr, pt, pb } = frame
  const span = max - min || 1
  const innerW = w - pl - pr
  const n = values.length
  return values.map((v, i) => ({
    x: pl + (n > 1 ? (i / (n - 1)) * innerW : innerW / 2),
    y: pt + (1 - (v - min) / span) * (h - pt - pb),
  }))
}

export function bandPathD(points, frame, min, max) {
  if (points.length < 2) return ''
  const hi = xyPoints(points.map((p) => p.hi), frame, min, max)
  const lo = xyPoints(points.map((p) => p.lo), frame, min, max)
  const fwd = hi.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join('')
  const back = lo.reverse().map((p) => `L${p.x},${p.y}`).join('')
  return `${fwd}${back}Z`
}

export function fmtValue(v) {
  if (v == null) return '–'
  if (v >= 10000) return `${(v / 1000).toFixed(1)}K`
  if (Number.isInteger(v)) return v.toLocaleString('en-AU')
  return v.toFixed(1)
}

export function fmtHours(h) {
  if (h == null) return '–'
  const whole = Math.floor(h)
  const mins = Math.round((h - whole) * 60)
  return `${whole}h${String(mins).padStart(2, '0')}m`
}

export function tickValues(min, max) {
  const r = (x) => Math.round(x * 10) / 10
  return [r(min), r((min + max) / 2), r(max)]
}
