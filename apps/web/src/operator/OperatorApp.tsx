import { useCallback, useEffect, useState, type JSX } from 'react'
import * as api from '../shared/apiClient'
import { PickingScreen } from './PickingScreen'
import { ShiftStart } from './ShiftStart'
import type { AppState } from './db'
import { clearCurrentAppState, getCurrentAppState } from './db'
import { syncOutbox } from './outbox'

export function OperatorApp(): JSX.Element {
  const [appState, setAppState] = useState<AppState | null | undefined>(undefined)

  useEffect(() => {
    void getCurrentAppState().then((state) => setAppState(state ?? null))
  }, [])

  useEffect(() => {
    if (!appState) return
    const onOnline = (): void => {
      void syncOutbox(appState.token)
    }
    window.addEventListener('online', onOnline)
    // Also try once on mount, in case we regained connectivity while unmounted.
    onOnline()
    return () => window.removeEventListener('online', onOnline)
  }, [appState])

  const handleShiftStarted = useCallback(() => {
    void getCurrentAppState().then((state) => setAppState(state ?? null))
  }, [])

  const handleOrderComplete = useCallback(() => {
    if (!appState) return
    void (async () => {
      await syncOutbox(appState.token)
      try {
        await api.endSession(appState.token, appState.sessionId)
      } catch {
        // Offline at shift end is fine — the outbox already synced the
        // pick events; ending the session is a convenience, not
        // load-bearing for data correctness.
      }
      await clearCurrentAppState()
      setAppState(null)
    })()
  }, [appState])

  if (appState === undefined) {
    return <p>Cargando...</p>
  }

  if (appState === null) {
    return <ShiftStart onShiftStarted={handleShiftStarted} />
  }

  return <PickingScreen appState={appState} onOrderComplete={handleOrderComplete} />
}
