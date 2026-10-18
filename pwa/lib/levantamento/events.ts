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

/** Pedido de envio imediato (ex.: "Reenviar"); o provider de sync chama `kick()`. */
const requestListeners = new Set<() => void>()

export function onSyncRequest(fn: () => void): () => void {
  requestListeners.add(fn)
  return () => {
    requestListeners.delete(fn)
  }
}

export function requestSync() {
  requestListeners.forEach((fn) => fn())
}
