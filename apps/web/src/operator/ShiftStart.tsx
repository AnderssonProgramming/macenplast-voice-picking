import { useState, type FormEvent, type JSX } from 'react'
import * as api from '../shared/apiClient'
import type { OrderLineDetail, PendingOrderSummary } from '../shared/apiTypes'
import { clipPlayer } from './clipPlayerInstance'
import { db, setCurrentAppState } from './db'

interface ShiftStartProps {
  onShiftStarted: () => void
}

type Step = 'login' | 'choose-order' | 'starting'

export function ShiftStart({ onShiftStarted }: ShiftStartProps): JSX.Element {
  const [step, setStep] = useState<Step>('login')
  const [badgeCode, setBadgeCode] = useState('')
  const [pin, setPin] = useState('')
  const [mode, setMode] = useState<'BASELINE' | 'VOICE'>('VOICE')
  const [error, setError] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [operatorId, setOperatorId] = useState<string | null>(null)
  const [fullName, setFullName] = useState<string>('')
  const [role, setRole] = useState<'operator' | 'supervisor'>('operator')
  const [orders, setOrders] = useState<PendingOrderSummary[]>([])

  async function handleLogin(event: FormEvent): Promise<void> {
    event.preventDefault()
    setError(null)
    try {
      const response = await api.login({ badge_code: badgeCode, pin })
      setToken(response.access_token)
      setOperatorId(response.operator_id)
      setFullName(response.full_name)
      setRole(response.role)
      const pending = await api.listPendingOrders(response.access_token)
      setOrders(pending)
      setStep('choose-order')
    } catch {
      setError('Badge o PIN incorrecto.')
    }
  }

  async function handleStartShift(orderId: string): Promise<void> {
    if (!token || !operatorId) return
    setStep('starting')
    setError(null)

    // Must run inside this click handler (a user gesture) — see ClipPlayer.
    clipPlayer.unlock()

    if (navigator.wakeLock) {
      try {
        await navigator.wakeLock.request('screen')
      } catch {
        // Not fatal — picking still works without the wake lock.
      }
    }

    try {
      const devices = await api.listDevices(token)
      const device = devices[0]
      if (!device) {
        throw new Error('No hay dispositivos registrados.')
      }

      const session = await api.startSession(token, { device_id: device.id, mode })
      await api.assignOrder(token, orderId, { session_id: session.id })
      const lines = await api.getOrderLines(token, orderId)

      await db.lines.clear()
      await db.lines.bulkAdd(
        lines.map((line: OrderLineDetail) => ({
          lineId: line.line_id,
          orderId,
          sequence: line.sequence,
          state: line.state,
          attempts: line.attempts,
          blockedOn: line.blocked_on,
          lastQty: line.last_qty,
          locationCheckEnabled: line.location_check_enabled,
          aisle: line.aisle,
          bay: line.bay,
          level: line.level,
          locationBarcode: line.location_barcode,
          skuCode: line.sku_code,
          skuBarcode: line.sku_barcode,
          reference: line.reference,
          expectedQty: line.expected_qty,
        })),
      )

      if (mode === 'VOICE') {
        try {
          const manifest = await api.getVoiceManifest(token, orderId)
          clipPlayer.registerManifest(manifest.clips)
          await clipPlayer.prefetch(manifest.clips)
        } catch {
          // Voice manifest prefetch is best-effort — speechSynthesis covers the rest.
        }
      }

      await setCurrentAppState({
        key: 'current',
        token,
        operatorId,
        fullName,
        role,
        deviceId: device.id,
        sessionId: session.id,
        mode,
        orderId,
      })

      onShiftStarted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo iniciar el turno.')
      setStep('choose-order')
    }
  }

  if (step === 'login') {
    return (
      <form onSubmit={(e) => void handleLogin(e)} className="shift-start">
        <h1>Macenplast — Iniciar turno</h1>
        <label>
          Badge
          <input value={badgeCode} onChange={(e) => setBadgeCode(e.target.value)} autoFocus />
        </label>
        <label>
          PIN
          <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit">Ingresar</button>
      </form>
    )
  }

  return (
    <div className="shift-start">
      <h1>Hola, {fullName}</h1>
      <fieldset>
        <legend>Modo de sesión</legend>
        <label>
          <input
            type="radio"
            name="mode"
            checked={mode === 'VOICE'}
            onChange={() => setMode('VOICE')}
          />
          VOICE (guiado por voz)
        </label>
        <label>
          <input
            type="radio"
            name="mode"
            checked={mode === 'BASELINE'}
            onChange={() => setMode('BASELINE')}
          />
          BASELINE (en pantalla)
        </label>
      </fieldset>

      <h2>Órdenes disponibles</h2>
      {error && <p role="alert">{error}</p>}
      <ul>
        {orders.map((order) => (
          <li key={order.id}>
            {order.order_code} ({order.line_count} líneas){' '}
            <button
              type="button"
              disabled={step === 'starting'}
              onClick={() => void handleStartShift(order.id)}
            >
              Iniciar turno
            </button>
          </li>
        ))}
      </ul>
      {orders.length === 0 && <p>No hay órdenes disponibles.</p>}
    </div>
  )
}
