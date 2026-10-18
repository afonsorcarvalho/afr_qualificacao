/** Pub/sub mínimo: o provider de sync avisa as telas que o banco local mudou. */
const listeners = new Set<() => void>()

export function onSyncTick(fn: () => void): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

export function emitSyncTick() {
  listeners.forEach((fn) => fn())
}
