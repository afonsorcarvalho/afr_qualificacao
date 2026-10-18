import { describe, it, expect } from 'vitest'
import { isValidCnpj, maskCnpj, onlyDigits } from '../cnpj'

describe('cnpj', () => {
  it('onlyDigits', () => expect(onlyDigits('11.222.333/0001-81')).toBe('11222333000181'))
  it('valida dígitos verificadores', () => {
    expect(isValidCnpj('11.222.333/0001-81')).toBe(true)
    expect(isValidCnpj('11222333000181')).toBe(true)
    expect(isValidCnpj('11.222.333/0001-80')).toBe(false)
    expect(isValidCnpj('00000000000000')).toBe(false)
    expect(isValidCnpj('123')).toBe(false)
    expect(isValidCnpj('')).toBe(false)
  })
  it('maskCnpj', () => {
    expect(maskCnpj('12345678000195')).toBe('12.345.678/0001-95')
    expect(maskCnpj('1234')).toBe('12.34')
    expect(maskCnpj('12345678000195999')).toBe('12.345.678/0001-95')
  })
})
