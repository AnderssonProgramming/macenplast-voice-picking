import { useCallback, useEffect, useRef, useState, type FormEvent, type JSX } from 'react'
import { renderPhrase } from '../shared/phrases'
import type { PickContext, PickEvent } from '../shared/pickMachine'
import { transition } from '../shared/pickMachine'
import { applyBaselineEvent } from './baselineMode'
import { clipPlayer } from './clipPlayerInstance'
import type { AppState, CachedLine } from './db'
import { db, getNextIncompleteLine } from './db'
import { pendingCount, queueEvent, syncOutbox } from './outbox'
import { useScannerInput } from './useScannerInput'

interface PickingScreenProps {
  appState: AppState
  onOrderComplete: () => void
}

function lineToContext(line: CachedLine): PickContext {
  return {
    locationCheckEnabled: line.locationCheckEnabled,
    expectedLocationBarcode: line.locationBarcode,
    expectedSkuBarcode: line.skuBarcode,
    expectedQty: line.expectedQty,
    attempts: line.attempts,
    blockedOn: line.blockedOn,
    lastQty: line.lastQty,
  }
}

export function PickingScreen({ appState, onOrderComplete }: PickingScreenProps): JSX.Element {
  const [line, setLine] = useState<CachedLine | null>(null)
  const [qtyInput, setQtyInput] = useState('')
  const [message, setMessage] = useState('')
  const [pendingSync, setPendingSync] = useState(0)
  const presentedRef = useRef<string | null>(null)

  const loadNextLine = useCallback(async () => {
    const next = await getNextIncompleteLine(appState.orderId)
    if (!next) {
      onOrderComplete()
      return
    }
    setMessage('')
    setLine(next)
  }, [appState.orderId, onOrderComplete])

  useEffect(() => {
    // Async IndexedDB read on mount/order-change — setState only happens
    // once the promise resolves, not synchronously in the effect body.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadNextLine()
  }, [loadNextLine])

  useEffect(() => {
    const refreshPendingCount = (): void => {
      void syncOutbox(appState.token).then(() => pendingCount().then(setPendingSync))
    }
    window.addEventListener('online', refreshPendingCount)
    return () => window.removeEventListener('online', refreshPendingCount)
  }, [appState.token])

  const speakOrShow = useCallback(
    (text: string) => {
      if (appState.mode === 'VOICE') {
        void clipPlayer.speak(text)
      } else {
        setMessage(text)
      }
    },
    [appState.mode],
  )

  const applyEvent = useCallback(
    async (currentLine: CachedLine, event: PickEvent) => {
      const context = lineToContext(currentLine)
      const result =
        appState.mode === 'BASELINE'
          ? applyBaselineEvent(currentLine.state, context, event)
          : { ...transition(currentLine.state, context, event), mismatchUnblocked: false }

      const updated: CachedLine = {
        ...currentLine,
        state: result.state,
        attempts: result.context.attempts,
        blockedOn: result.context.blockedOn,
        lastQty: result.context.lastQty,
      }
      await db.lines.put(updated)
      setLine(updated)

      for (const effect of result.effects) {
        if (effect.type === 'SPEAK') {
          // INSTRUCTION deliberately carries no args from the pure state
          // machine — PickContext has no aisle/bay/level/reference, only
          // barcodes and quantity. The caller (here, or the backend's
          // orders.py) supplies those from the actual line data.
          const args =
            effect.phrase === 'INSTRUCTION'
              ? {
                  aisle: currentLine.aisle,
                  bay: Number(currentLine.bay),
                  level: Number(currentLine.level),
                  reference: currentLine.reference,
                  quantity: currentLine.expectedQty,
                }
              : (effect.args ?? {})
          speakOrShow(renderPhrase(effect.phrase, args))
        } else if (effect.type === 'PLAY_ALERT') {
          speakOrShow(
            effect.alert === 'MISMATCH_UNBLOCKED'
              ? 'Diferencia registrada (no bloqueante).'
              : 'Incorrecto.',
          )
        }
      }

      await queueEvent({
        pickLineId: currentLine.lineId,
        sessionId: appState.sessionId,
        event,
      })
      await syncOutbox(appState.token)
      setPendingSync(await pendingCount())

      if (result.state === 'DONE' || result.state === 'EXCEPTED') {
        setTimeout(() => void loadNextLine(), 300)
      }
    },
    [appState.mode, appState.sessionId, appState.token, loadNextLine, speakOrShow],
  )

  // Present a freshly-loaded line as soon as it arrives.
  useEffect(() => {
    if (!line || line.state !== 'PENDING' || presentedRef.current === line.lineId) return
    presentedRef.current = line.lineId
    void applyEvent(line, { type: 'PRESENT' })
  }, [line, applyEvent])

  const handleScan = useCallback(
    (code: string) => {
      if (line) void applyEvent(line, { type: 'SCAN', barcode: code })
    },
    [line, applyEvent],
  )
  const { onKeyDown } = useScannerInput(({ code }) => {
    handleScan(code)
  })

  function handleQtySubmit(event: FormEvent): void {
    event.preventDefault()
    if (!line) return
    const quantity = Number(qtyInput)
    if (Number.isNaN(quantity)) return
    setQtyInput('')
    void applyEvent(line, { type: 'QTY', quantity })
  }

  if (!line) {
    return <p>Cargando línea...</p>
  }

  const showQtyInput = line.state === 'AWAITING_QTY' || line.state === 'SHORT_PENDING'
  const showScanInput =
    !showQtyInput &&
    line.state !== 'NEEDS_OVERRIDE' &&
    line.state !== 'DONE' &&
    line.state !== 'EXCEPTED'

  return (
    <div className="picking-screen">
      <div
        data-testid="mode-indicator"
        className={`mode-indicator mode-${appState.mode.toLowerCase()}`}
      >
        {appState.mode}
      </div>
      <p data-testid="pending-sync-count">Pendientes por sincronizar: {pendingSync}</p>

      {appState.mode === 'BASELINE' && (
        <div className="instruction">
          <p>
            Pasillo {line.aisle}, Estante {line.bay}, Nivel {line.level}
          </p>
          <p>Referencia: {line.reference}</p>
          <p>Cantidad esperada: {line.expectedQty}</p>
        </div>
      )}
      {message && <p className="message">{message}</p>}

      <p data-testid="line-state">Estado: {line.state}</p>

      {line.state === 'NEEDS_OVERRIDE' && <p role="alert">Llame al supervisor.</p>}

      {showScanInput && (
        <>
          <input
            aria-label="scan-input"
            autoFocus
            onKeyDown={onKeyDown}
            placeholder="Escanear código"
          />
          <div className="exceptions">
            <button
              type="button"
              onClick={() => void applyEvent(line, { type: 'EXCEPTION', reason: 'empty_location' })}
            >
              Ubicación vacía
            </button>
            <button
              type="button"
              onClick={() => void applyEvent(line, { type: 'EXCEPTION', reason: 'damaged' })}
            >
              Producto dañado
            </button>
          </div>
        </>
      )}

      {showQtyInput && (
        <form onSubmit={handleQtySubmit}>
          <input
            aria-label="qty-input"
            type="number"
            value={qtyInput}
            onChange={(e) => setQtyInput(e.target.value)}
            autoFocus
          />
          <button type="submit">Confirmar</button>
          {line.state === 'SHORT_PENDING' && (
            <button
              type="button"
              onClick={() => void applyEvent(line, { type: 'EXCEPTION', reason: 'short' })}
            >
              Confirmar faltante
            </button>
          )}
        </form>
      )}
    </div>
  )
}
