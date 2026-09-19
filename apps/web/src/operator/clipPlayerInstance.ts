import { ClipPlayer } from './clipPlayer'

/** One shared player for the whole app — audio unlock and the in-memory
 * text->url map are both process-wide, not per-component. */
export const clipPlayer = new ClipPlayer()
