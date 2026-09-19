/**
 * Plays voice clips from Cache Storage (prefetched from the voice
 * manifest at shift start), falling back to `speechSynthesis` on a cache
 * miss — per ADR 0001, the operator is never left in silence.
 *
 * Clips are looked up by exact rendered text, not by content hash: the
 * client renders the same phrase templates as the backend
 * (`shared/phrases.ts` mirrors `macenplast.voice.phrases`), so matching
 * on text sidesteps needing to reproduce the backend's hash function
 * (text + voice id + model id + output format) in the browser.
 */

const CACHE_NAME = 'macenplast-voice-clips'

// 1 sample of silence, base64-encoded WAV — just enough for a real
// `HTMLAudioElement.play()` call inside the "Start shift" tap handler,
// which is what satisfies browsers' autoplay-after-user-gesture policy
// for every subsequent programmatic play in the session.
const SILENT_WAV =
  'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='

export class ClipPlayer {
  private textToUrl = new Map<string, string>()
  private audio: HTMLAudioElement | null = null
  // Serializes speak() calls: without this, two phrases triggered close
  // together (a fast operator scanning ahead of a clip finishing) would
  // both grab `this.audio`, and the second's pause() aborts the first's
  // in-flight play() — which then falls back to speechSynthesis on top of
  // the real clip, so the operator hears both, overlapping and cut off.
  private queue: Promise<void> = Promise.resolve()

  registerManifest(clips: Array<{ url: string; text: string }>): void {
    for (const clip of clips) {
      this.textToUrl.set(clip.text, clip.url)
    }
  }

  async prefetch(clips: Array<{ url: string }>): Promise<void> {
    if (typeof caches === 'undefined') return
    const cache = await caches.open(CACHE_NAME)
    await Promise.all(
      clips.map(async (clip) => {
        const already = await cache.match(clip.url)
        if (already) return
        try {
          await cache.add(clip.url)
        } catch {
          // Best-effort: speechSynthesis covers a missing clip at playback time.
        }
      }),
    )
  }

  /** Call once, synchronously, inside the "Start shift" button's click
   * handler — see the module docstring on why. */
  unlock(): void {
    this.audio = new Audio(SILENT_WAV)
    void this.audio.play().catch(() => {
      // Some browsers still refuse; playback later falls back per-call anyway.
    })
  }

  /** Queues this phrase behind any still-playing one — see the `queue`
   * field docstring for why this can't just play immediately. */
  speak(text: string): Promise<void> {
    // A swallowed error here must not reject `this.queue` itself — that
    // would permanently skip every phrase queued after it for the rest of
    // the shift, since .then() on a rejected promise never runs.
    this.queue = this.queue.then(() => this.speakNow(text).catch(() => {}))
    return this.queue
  }

  private async speakNow(text: string): Promise<void> {
    const url = this.textToUrl.get(text)
    const playedFromCache = url ? await this.playFromCache(url) : false
    if (!playedFromCache) {
      await this.speakWithSpeechSynthesis(text)
    }
  }

  private async playFromCache(url: string): Promise<boolean> {
    if (typeof caches === 'undefined') return false
    let objectUrl: string | null = null
    try {
      const cache = await caches.open(CACHE_NAME)
      const response = await cache.match(url)
      if (!response) return false
      const blob = await response.blob()
      objectUrl = URL.createObjectURL(blob)
      const audio = new Audio(objectUrl)
      this.audio = audio
      await audio.play()
      // Wait for the clip to actually finish — the play() promise only
      // resolves once playback *starts*, not once it ends. Capped: these
      // clips are a few seconds of speech at most, so if 'ended'/'error'
      // never fire (e.g. a stalled decode), give up rather than jamming
      // every phrase queued behind this one for the rest of the shift —
      // playback did start, so this counts as a successful clip play, not
      // a cache miss that should also trigger the speechSynthesis fallback.
      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, 15_000)
        const finish = (): void => {
          clearTimeout(timer)
          resolve()
        }
        audio.addEventListener('ended', finish, { once: true })
        audio.addEventListener('error', finish, { once: true })
      })
      return true
    } catch {
      return false
    } finally {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }

  private speakWithSpeechSynthesis(text: string): Promise<void> {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return Promise.resolve()
    }
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'es-CO'
      utterance.onend = () => resolve()
      utterance.onerror = () => resolve()
      window.speechSynthesis.speak(utterance)
    })
  }
}
