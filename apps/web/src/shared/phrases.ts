/**
 * Spanish phrase catalog — TypeScript port of
 * `apps/api/src/macenplast/voice/phrases.es.yaml` /
 * `macenplast/voice/phrases.py`. Kept in sync by hand.
 *
 * Used for the `speechSynthesis` fallback when a pre-built clip for a
 * phrase isn't in Cache Storage (see `operator/ClipPlayer.ts`) — the
 * manifest already carries rendered text for clips it knows about, but a
 * REPEAT or a state the manifest didn't anticipate still needs to render
 * text locally.
 */

import { numberToEs } from './numbersEs'

const CATALOG: Record<string, string> = {
  INSTRUCTION:
    'Pasillo {aisle}. Estante {bay}. Nivel {level}. Referencia, {reference}. Cantidad, {quantity}.',
  LOCATION_CORRECT: 'Ubicación correcta.',
  QTY_PROMPT: 'Cantidad, {quantity}.',
  CORRECT: 'Correcto.',
  CALL_SUPERVISOR: 'Llame al supervisor.',
  ASK_CONFIRM_SHORT: 'Cantidad registrada, {quantity}. Confirme el faltante.',
  MISMATCH: 'Incorrecto.',
}

export class UnknownPhraseError extends Error {}

export function phraseKeys(): string[] {
  return Object.keys(CATALOG)
}

export function renderPhrase(key: string, args: Record<string, string | number> = {}): string {
  const template = CATALOG[key]
  if (template === undefined) {
    throw new UnknownPhraseError(key)
  }

  return template.replace(/\{(\w+)\}/g, (_match, name: string) => {
    const value = args[name]
    if (value === undefined) {
      throw new Error(`Missing arg "${name}" for phrase "${key}"`)
    }
    return typeof value === 'number' ? numberToEs(value) : value
  })
}
