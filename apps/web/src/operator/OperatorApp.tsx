import { useCallback, useEffect, useState, type JSX } from 'react'
import * as api from '../shared/apiClient'
import { clipPlayer } from './clipPlayerInstance'
import { PickingScreen } from './PickingScreen'
import { ShiftStart } from './ShiftStart'
import type { AppState } from './db'
import { clearCurrentAppState, getCurrentAppState } from './db'
import { syncOutbox } from './outbox'

/** Re-populates the in-memory ClipPlayer after a resume (page reload,
 * PWA relaunch, etc.). `ClipPlayer.textToUrl` only lives in JS memory —
 * `handleStartShift` fills it once at shift start, but a fresh page load
 * starts a fresh, empty ClipPlayer, so without this every phrase for the
 * rest of the order would silently fall back to speechSynthesis even
 * though the real clips are already cached server-side. Best-effort, same
 * as the original prefetch: a failure here still leaves the operator
 * hearing speechSynthesis, never silence. */
async function resyncVoiceManifest(state: AppState): Promise<void> {
  if (state.mode !== 'VOICE') return
  try {
    const manifest = await api.getVoiceManifest(state.token, state.orderId)
    clipPlayer.registerManifest(manifest.clips)
    await clipPlayer.prefetch(manifest.clips)
  } catch {
    // Best-effort — speechSynthesis covers the rest.
  }
}

export function OperatorApp(): JSX.Element {
  const [appState, setAppState] = useState<AppState | null | undefined>(undefined)

  useEffect(() => {
    void getCurrentAppState().then((state) => {
      setAppState(state ?? null)
      if (state) void resyncVoiceManifest(state)
    })
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
