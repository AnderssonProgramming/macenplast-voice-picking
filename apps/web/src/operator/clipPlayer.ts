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

  async speak(text: string): Promise<void> {
    const url = this.textToUrl.get(text)
    const playedFromCache = url ? await this.playFromCache(url) : false
    if (!playedFromCache) {
      this.speakWithSpeechSynthesis(text)
    }
  }

  private async playFromCache(url: string): Promise<boolean> {
    if (typeof caches === 'undefined') return false
    try {
      const cache = await caches.open(CACHE_NAME)
      const response = await cache.match(url)
      if (!response) return false
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      this.audio?.pause()
      this.audio = new Audio(objectUrl)
      await this.audio.play()
      return true
    } catch {
      return false
    }
  }

  private speakWithSpeechSynthesis(text: string): void {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'es-CO'
    window.speechSynthesis.speak(utterance)
  }
}
