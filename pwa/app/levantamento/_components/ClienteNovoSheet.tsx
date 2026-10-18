'use client'
import { useState } from 'react'
import { BottomSheet } from '@/components/ui/BottomSheet'
import { Button } from '@/components/ui/button'
import { isValidCnpj, maskCnpj, onlyDigits } from '@/lib/levantamento/cnpj'
import { createPartner } from '@/lib/levantamento/repo'

const CAMPO =
  'mt-1 block min-h-[44px] w-full rounded-md border border-input bg-background px-3 text-sm'

/** Cadastro mínimo de cliente em campo. O servidor faz o merge por CNPJ. */
export function ClienteNovoSheet({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (key: string) => void
}) {
  const [name, setName] = useState('')
  const [vat, setVat] = useState('')
  const [city, setCity] = useState('')
  const [contactName, setContactName] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [erroNome, setErroNome] = useState(false)
  const [erroCnpj, setErroCnpj] = useState(false)
  const [salvando, setSalvando] = useState(false)

  async function salvar(e: React.FormEvent) {
    e.preventDefault()
    const nome = name.trim()
    const nomeRuim = !nome
    // CNPJ é opcional (nem todo cliente tem em mãos), mas se digitado tem de fechar.
    const cnpjRuim = onlyDigits(vat).length > 0 && !isValidCnpj(vat)
    setErroNome(nomeRuim)
    setErroCnpj(cnpjRuim)
    if (nomeRuim || cnpjRuim) return
    setSalvando(true)
    try {
      const input: Parameters<typeof createPartner>[0] = { name: nome }
      if (vat) input.vat = maskCnpj(vat)
      if (city.trim()) input.city = city.trim()
      if (contactName.trim()) input.contact_name = contactName.trim()
      if (contactPhone.trim()) input.contact_phone = contactPhone.trim()
      const key = await createPartner(input)
      setName(''); setVat(''); setCity(''); setContactName(''); setContactPhone('')
      onCreated(key)
      onClose()
    } finally {
      setSalvando(false)
    }
  }

  return (
    <BottomSheet open={open} title="Cliente novo" onClose={onClose}>
      <form onSubmit={salvar} noValidate className="space-y-3">
        <label className="block text-sm">
          Nome
          <input
            className={CAMPO}
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-invalid={erroNome || undefined}
            autoComplete="off"
          />
          {erroNome && <span className="text-xs text-danger">Informe o nome</span>}
        </label>
        <label className="block text-sm">
          CNPJ
          <input
            className={CAMPO}
            inputMode="numeric"
            value={vat}
            onChange={(e) => setVat(maskCnpj(e.target.value))}
            aria-invalid={erroCnpj || undefined}
            autoComplete="off"
          />
          {erroCnpj && <span className="text-xs text-danger">CNPJ inválido</span>}
        </label>
        <label className="block text-sm">
          Cidade
          <input className={CAMPO} value={city} onChange={(e) => setCity(e.target.value)} />
        </label>
        <label className="block text-sm">
          Contato
          <input className={CAMPO} value={contactName} onChange={(e) => setContactName(e.target.value)} />
        </label>
        <label className="block text-sm">
          Telefone do contato
          <input
            className={CAMPO}
            type="tel"
            value={contactPhone}
            onChange={(e) => setContactPhone(e.target.value)}
          />
        </label>
        <Button type="submit" className="min-h-[44px] w-full" loading={salvando}>
          Salvar
        </Button>
      </form>
    </BottomSheet>
  )
}
