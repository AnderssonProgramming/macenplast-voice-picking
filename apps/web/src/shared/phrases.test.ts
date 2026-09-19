import { describe, expect, it } from 'vitest'
import { UnknownPhraseError, phraseKeys, renderPhrase } from './phrases'

describe('renderPhrase', () => {
  it('converts numeric args to spoken words', () => {
    const text = renderPhrase('INSTRUCTION', {
      aisle: 'A',
      bay: 12,
      level: 1,
      reference: 'Producto uno',
      quantity: 21,
    })
    expect(text).toBe(
      'Pasillo A. Estante doce. Nivel uno. Referencia, Producto uno. Cantidad, veintiuno.',
    )
  })

  it('renders a fixed phrase with no args', () => {
    expect(renderPhrase('CORRECT')).toBe('Correcto.')
  })

  it('renders QTY_PROMPT', () => {
    expect(renderPhrase('QTY_PROMPT', { quantity: 5 })).toBe('Cantidad, cinco.')
  })

  it('throws for an unknown phrase key', () => {
    expect(() => renderPhrase('NOT_A_REAL_PHRASE')).toThrow(UnknownPhraseError)
  })

  it('includes every phrase key the pick machine emits', () => {
    const usedByMachine = [
      'INSTRUCTION',
      'LOCATION_CORRECT',
      'QTY_PROMPT',
      'CORRECT',
      'CALL_SUPERVISOR',
      'ASK_CONFIRM_SHORT',
    ]
    const keys = phraseKeys()
    for (const key of usedByMachine) {
      expect(keys).toContain(key)
    }
  })
})
