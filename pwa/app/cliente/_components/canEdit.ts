'use client'
import { createContext, useContext } from 'react'

/**
 * Modo de edição das telas de cliente. A página fornece o valor de
 * `useCanEdit()` (grupo do levantamento); sem ele as telas ficam em leitura.
 * Default `true`: componentes isolados (testes) continuam editáveis.
 */
export const CanEditContext = createContext(true)
export const useCanEditCtx = () => useContext(CanEditContext)
