/**
 * Spanish (Colombia) number-to-speech, 0-999, nominal form only.
 *
 * TypeScript port of `apps/api/src/macenplast/domain/numbers_es.py` — kept
 * in sync by hand (small enough that shared test vectors like
 * `pickMachine`'s aren't worth the ceremony). Used by the offline client
 * to render phrases for `speechSynthesis` fallback when a pre-built clip
 * isn't cached — see `macenplast.voice.phrases`'s Python docstring for why
 * this is always the nominal form, never a noun-phrase form.
 */

const UNITS = [
  'cero',
  'uno',
  'dos',
  'tres',
  'cuatro',
  'cinco',
  'seis',
  'siete',
  'ocho',
  'nueve',
] as const

const TEENS = [
  'diez',
  'once',
  'doce',
  'trece',
  'catorce',
  'quince',
  'dieciséis',
  'diecisiete',
  'dieciocho',
  'diecinueve',
] as const

const TWENTIES = [
  'veinte',
  'veintiuno',
  'veintidós',
  'veintitrés',
  'veinticuatro',
  'veinticinco',
  'veintiséis',
  'veintisiete',
  'veintiocho',
  'veintinueve',
] as const

const TENS: Record<number, string> = {
  30: 'treinta',
  40: 'cuarenta',
  50: 'cincuenta',
  60: 'sesenta',
  70: 'setenta',
  80: 'ochenta',
  90: 'noventa',
}

const HUNDREDS: Record<number, string> = {
  100: 'cien',
  200: 'doscientos',
  300: 'trescientos',
  400: 'cuatrocientos',
  500: 'quinientos',
  600: 'seiscientos',
  700: 'setecientos',
  800: 'ochocientos',
  900: 'novecientos',
}

export const MIN_SUPPORTED = 0
export const MAX_SUPPORTED = 999

export function numberToEs(n: number): string {
  if (!Number.isInteger(n) || n < MIN_SUPPORTED || n > MAX_SUPPORTED) {
    throw new RangeError(`numberToEs only supports ${MIN_SUPPORTED}-${MAX_SUPPORTED}, got ${n}`)
  }

  if (n < 10) return UNITS[n]
  if (n < 20) return TEENS[n - 10]
  if (n < 30) return TWENTIES[n - 20]
  if (n < 100) {
    const tensWord = TENS[Math.floor(n / 10) * 10]
    const remainder = n % 10
    return remainder === 0 ? tensWord : `${tensWord} y ${UNITS[remainder]}`
  }
  if (n === 100) return 'cien'

  const hundredsBase = Math.floor(n / 100) * 100
  const remainder = n % 100
  const hundredsWord = hundredsBase === 100 ? 'ciento' : HUNDREDS[hundredsBase]
  return remainder === 0 ? hundredsWord : `${hundredsWord} ${numberToEs(remainder)}`
}
