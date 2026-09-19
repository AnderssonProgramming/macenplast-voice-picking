/**
 * Scanner input: one always-focused text field that accepts both a real
 * hardware scanner (keyboard-wedge — keystrokes arrive far faster than a
 * human types, terminated by Enter) and manual typing (the "lost/broken
 * scanner" fallback from `PLAN.md` section 1's additions). Both paths
 * call the same `onScan` callback; `source` is recorded for telemetry
 * only; a manual entry is never rejected for being "too slow."
 *
 * Camera-based scanning (`BarcodeDetector`/ZXing) is out of scope for
 * this pass — see `docs/PROGRESS.md`'s Phase 5 entry for why.
 */

import { useCallback, useRef, type KeyboardEvent } from 'react'

const FAST_KEYSTROKE_THRESHOLD_MS = 30
const MIN_SAMPLES_TO_CLASSIFY_AS_SCANNER = 3
const FAST_FRACTION_TO_CLASSIFY_AS_SCANNER = 0.7

export interface ScanResult {
  code: string
  source: 'scanner' | 'manual'
}

export function useScannerInput(onScan: (result: ScanResult) => void): {
  onKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void
} {
  const bufferRef = useRef('')
  const lastKeyTimeRef = useRef(0)
  const fastCountRef = useRef(0)
  const totalCountRef = useRef(0)

  const reset = useCallback(() => {
    bufferRef.current = ''
    lastKeyTimeRef.current = 0
    fastCountRef.current = 0
    totalCountRef.current = 0
  }, [])

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLInputElement>) => {
      const now = performance.now()

      if (event.key === 'Enter') {
        const code = bufferRef.current.trim()
        if (code.length > 0) {
          const looksLikeScanner =
            totalCountRef.current >= MIN_SAMPLES_TO_CLASSIFY_AS_SCANNER &&
            fastCountRef.current / totalCountRef.current >= FAST_FRACTION_TO_CLASSIFY_AS_SCANNER
          onScan({ code, source: looksLikeScanner ? 'scanner' : 'manual' })
        }
        reset()
        event.currentTarget.value = ''
        return
      }

      if (event.key.length === 1) {
        if (
          lastKeyTimeRef.current > 0 &&
          now - lastKeyTimeRef.current < FAST_KEYSTROKE_THRESHOLD_MS
        ) {
          fastCountRef.current += 1
        }
        totalCountRef.current += 1
        lastKeyTimeRef.current = now
        bufferRef.current += event.key
      }
    },
    [onScan, reset],
  )

  return { onKeyDown }
}
