import { describe, it, expect } from 'vitest'
import { xyPoints, bandPathD, fmtValue, fmtHours, tickValues } from './chart-utils'

const frame = { w: 100, h: 50, pl: 10, pr: 10, pt: 5, pb: 5 }

describe('xyPoints', () => {
  it('maps values onto the plot frame, min→bottom max→top', () => {
    const pts = xyPoints([0, 5, 10], frame, 0, 10)
    expect(pts[0]).toEqual({ x: 10, y: 45 })   // min at left/bottom
    expect(pts[2]).toEqual({ x: 90, y: 5 })    // max at right/top
    expect(pts[1].y).toBeCloseTo(25)
  })
  it('handles a flat series without dividing by zero', () => {
    const pts = xyPoints([5, 5], frame, 5, 5)
    expect(pts.every((p) => Number.isFinite(p.y))).toBe(true)
  })
  it('handles a single point', () => {
    expect(xyPoints([3], frame, 0, 10)).toHaveLength(1)
  })
})

describe('bandPathD', () => {
  it('draws hi edge forward then lo edge back, closed', () => {
    const d = bandPathD([{ lo: 0, hi: 10 }, { lo: 0, hi: 10 }], frame, 0, 10)
    expect(d.startsWith('M')).toBe(true)
    expect(d.endsWith('Z')).toBe(true)
    expect(d.match(/L/g).length).toBe(3) // 2 pts: 1 L forward + 2 L back
  })
  it('returns empty string for fewer than 2 points', () => {
    expect(bandPathD([{ lo: 0, hi: 1 }], frame, 0, 1)).toBe('')
  })
})

describe('fmtValue', () => {
  it('keeps small numbers plain with locale separators', () => {
    expect(fmtValue(842)).toBe('842')
    expect(fmtValue(8412)).toBe('8,412')
  })
  it('compacts 10k+', () => {
    expect(fmtValue(12912)).toBe('12.9K')
  })
  it('shows one decimal for small floats', () => {
    expect(fmtValue(51.66)).toBe('51.7')
  })
  it('handles null', () => {
    expect(fmtValue(null)).toBe('–')
  })
})

describe('fmtHours', () => {
  it('renders 7.2h as 7h12m', () => {
    expect(fmtHours(7.2)).toBe('7h12m')
  })
  it('handles null', () => {
    expect(fmtHours(null)).toBe('–')
  })
})

describe('tickValues', () => {
  it('returns min, mid, max rounded to one decimal', () => {
    expect(tickValues(47.4, 51.7)).toEqual([47.4, 49.6, 51.7])
  })
})
