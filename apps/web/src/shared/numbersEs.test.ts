import { describe, expect, it } from 'vitest'
import { MAX_SUPPORTED, MIN_SUPPORTED, numberToEs } from './numbersEs'

const KNOWN_VALUES: Record<number, string> = {
  0: 'cero',
  1: 'uno',
  10: 'diez',
  15: 'quince',
  16: 'dieciséis',
  20: 'veinte',
  21: 'veintiuno',
  22: 'veintidós',
  23: 'veintitrés',
  26: 'veintiséis',
  30: 'treinta',
  31: 'treinta y uno',
  45: 'cuarenta y cinco',
  99: 'noventa y nueve',
  100: 'cien',
  101: 'ciento uno',
  115: 'ciento quince',
  200: 'doscientos',
  201: 'doscientos uno',
  999: 'novecientos noventa y nueve',
}

describe('numberToEs', () => {
  for (const [n, expected] of Object.entries(KNOWN_VALUES)) {
    it(`renders ${n} as "${expected}"`, () => {
      expect(numberToEs(Number(n))).toBe(expected)
    })
  }

  it.each([-1, 1000, -100, 5000])('rejects out-of-range value %d', (n) => {
    expect(() => numberToEs(n)).toThrow(RangeError)
  })

  it('produces a unique word for every value in range', () => {
    const words = new Set<string>()
    for (let n = MIN_SUPPORTED; n <= MAX_SUPPORTED; n++) {
      words.add(numberToEs(n))
    }
    expect(words.size).toBe(MAX_SUPPORTED - MIN_SUPPORTED + 1)
  })

  it('never contains digits', () => {
    for (let n = MIN_SUPPORTED; n <= MAX_SUPPORTED; n++) {
      expect(numberToEs(n)).not.toMatch(/\d/)
    }
  })
})
