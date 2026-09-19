import { describe, expect, it } from 'vitest'
import type { PickContext } from '../shared/pickMachine'
import { applyBaselineEvent } from './baselineMode'

const baseContext: PickContext = {
  locationCheckEnabled: true,
  expectedLocationBarcode: 'LOC-A1',
  expectedSkuBarcode: 'SKU-100',
  expectedQty: 10,
  attempts: 0,
  blockedOn: null,
  lastQty: null,
}

describe('applyBaselineEvent', () => {
  it('advances normally on a correct scan, same as VOICE mode', () => {
    const result = applyBaselineEvent('AWAITING_LOCATION', baseContext, {
      type: 'SCAN',
      barcode: 'LOC-A1',
    })
    expect(result.state).toBe('AWAITING_SCAN')
    expect(result.mismatchUnblocked).toBe(false)
  })

  it('never blocks on a wrong location scan — forces forward instead', () => {
    const result = applyBaselineEvent('AWAITING_LOCATION', baseContext, {
      type: 'SCAN',
      barcode: 'WRONG',
    })
    expect(result.state).toBe('AWAITING_SCAN')
    expect(result.context.attempts).toBe(0)
    expect(result.mismatchUnblocked).toBe(true)
    expect(
      result.effects.some((e) => e.type === 'PLAY_ALERT' && e.alert === 'MISMATCH_UNBLOCKED'),
    ).toBe(true)
  })

  it('never blocks on a wrong SKU scan', () => {
    const result = applyBaselineEvent('AWAITING_SCAN', baseContext, {
      type: 'SCAN',
      barcode: 'WRONG-SKU',
    })
    expect(result.state).toBe('AWAITING_QTY')
    expect(result.mismatchUnblocked).toBe(true)
  })

  it('never blocks on an over-quantity entry — completes the line anyway', () => {
    const result = applyBaselineEvent('AWAITING_QTY', baseContext, {
      type: 'QTY',
      quantity: 999,
    })
    expect(result.state).toBe('DONE')
    expect(result.mismatchUnblocked).toBe(true)
    expect(result.effects.some((e) => e.type === 'QUEUE_SYNC')).toBe(true)
  })

  it('does not increment attempts across repeated mismatches (BLOCKED is never reached)', () => {
    let context = baseContext
    for (let i = 0; i < 5; i++) {
      const result = applyBaselineEvent('AWAITING_LOCATION', context, {
        type: 'SCAN',
        barcode: 'WRONG',
      })
      expect(result.state).not.toBe('BLOCKED')
      expect(result.state).not.toBe('NEEDS_OVERRIDE')
      context = result.context
    }
  })
})
