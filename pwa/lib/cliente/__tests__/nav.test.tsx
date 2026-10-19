// @vitest-environment happy-dom
/// <reference types="@testing-library/jest-dom" />
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { clienteUrl, goCliente, levantamentoRedirect, useClienteNav } from '../nav'

afterEach(() => {
  vi.restoreAllMocks()
  window.history.replaceState(null, '', '/cliente')
})

describe('clienteUrl / levantamentoRedirect', () => {
  it('monta a query', () => {
    expect(clienteUrl()).toBe('/cliente')
    expect(clienteUrl({ id: '7' })).toBe('/cliente?id=7')
    expect(clienteUrl({ id: 'tmp:a', eq: 'novo' })).toBe('/cliente?id=tmp%3Aa&eq=novo')
    expect(clienteUrl({ eq: '3' })).toBe('/cliente')
  })
  it('mapa de redirecionamento do /levantamento', () => {
    expect(levantamentoRedirect()).toBe('/cliente')
    expect(levantamentoRedirect(['7'])).toBe('/cliente?id=7')
    expect(levantamentoRedirect(['7', '10'])).toBe('/cliente?id=7&eq=10')
    expect(levantamentoRedirect(['tmp%3Aa', 'novo'])).toBe('/cliente?id=tmp%3Aa&eq=novo')
  })
})

describe('useClienteNav', () => {
  it('go usa pushState (ou replaceState) e o hook acompanha; popstate restaura', () => {
    const push = vi.spyOn(window.history, 'pushState')
    const repl = vi.spyOn(window.history, 'replaceState')
    const { result } = renderHook(() => useClienteNav())
    expect(result.current.id).toBeNull()
    act(() => result.current.go({ id: '7' }))
    expect(push).toHaveBeenCalledWith(null, '', '/cliente?id=7')
    expect(result.current).toMatchObject({ id: '7', eq: null })
    act(() => goCliente({ id: '7', eq: 'tmp:x' }, { replace: true }))
    expect(repl).toHaveBeenCalledWith(null, '', '/cliente?id=7&eq=tmp%3Ax')
    expect(result.current).toMatchObject({ id: '7', eq: 'tmp:x' })
    act(() => {
      window.history.replaceState(null, '', '/cliente')
      window.dispatchEvent(new PopStateEvent('popstate'))
    })
    expect(result.current.id).toBeNull()
  })
})
