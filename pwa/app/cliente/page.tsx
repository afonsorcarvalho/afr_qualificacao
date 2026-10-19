'use client'
import { useClienteNav, useCanEdit } from '@/lib/cliente/nav'
import { CanEditContext } from './_components/canEdit'
import { ClientesView } from './_components/ClientesView'
import { ClienteView } from './_components/ClienteView'
import { FichaView } from './_components/FichaView'

/**
 * Página única de clientes: lista, cliente (equipamentos) e ficha, escolhidos
 * pela query (`?id=&eq=`). Uma rota só = um shell só para o service worker
 * servir offline; a troca de tela é `history.pushState` (ver `lib/cliente/nav`).
 */
export default function ClientePage() {
  const { id, eq } = useClienteNav()
  const podeEditar = useCanEdit()
  return (
    <CanEditContext.Provider value={podeEditar}>
      {!id ? <ClientesView /> : !eq ? <ClienteView key={id} id={id} /> : <FichaView key={id} id={id} eq={eq} />}
    </CanEditContext.Provider>
  )
}
