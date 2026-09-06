import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Guarda do tema claro.
 *
 * Em 2026-09-06 o user relatou, usando o app publicado, que no MODO CLARO
 * "botões e informações ficaram difíceis de ler". A medição achou 397
 * ocorrências abaixo do piso AA e a inspeção na tela mostrou coisa pior: o
 * login perde o texto inteiro, porque `text-white/60` sobre `bg-card` é
 * branco sobre branco.
 *
 * A causa não é um componente: é que cor de estado virou shade crua do
 * Tailwind espalhada por 17 arquivos, cada uma escolhida olhando só o tema
 * escuro. Consertar componente a componente traz o defeito de volta no
 * próximo componente escrito.
 *
 * Então este teste proíbe os PADRÕES, não os pixels:
 *   - `text-white`, `bg-white/40`, `border-white/10` e cia. — cor absoluta
 *     que assume fundo escuro;
 *   - `text-emerald-300`, `bg-cyan-500/15` e cia. — shade crua no lugar do
 *     token semântico (`text-ok`, `bg-info-surface`);
 *   - `text-muted-foreground/80` — "Tinta Apagada", que o DESIGN.md proíbe
 *     em texto que o técnico precisa ler (a /80 dá 4.35:1, abaixo do piso).
 *
 * `PERMITIDO_TEMA` nasceu enumerando os infratores de 2026-09-06 e só pode
 * ENCOLHER: cada task da migração apaga as suas linhas. Entrada morta é
 * erro, para a lista não virar depósito.
 */

const RAIZ = join(__dirname, '..', '..', '..', '..')
const PASTAS = ['app', 'components', 'lib']

const FAMILIAS = 'emerald|amber|red|rose|cyan|sky|blue|green|yellow|orange|teal|violet|indigo|fuchsia|pink|lime'

const PROIBIDO: { nome: string; re: RegExp; conserto: string }[] = [
  {
    nome: 'cor absoluta branca',
    re: new RegExp(String.raw`\b(?:text|bg|border|divide|ring)-white(?:\/\d{1,3})?\b`, 'g'),
    conserto: 'usar o papel semântico: text-foreground / text-muted-foreground / bg-surface-raised / border-border',
  },
  {
    nome: 'shade crua de cor de estado',
    re: new RegExp(String.raw`\b(?:text|bg|border|ring)-(?:${FAMILIAS})-\d{2,3}(?:\/\d{1,3})?\b`, 'g'),
    conserto: 'usar o token de estado: text-ok/warn/danger/info e bg-*-surface',
  },
  {
    nome: 'opacidade sobre tinta secundária',
    re: /\btext-muted-foreground\/\d{1,3}\b/g,
    conserto: 'usar text-muted-foreground puro — a opacidade derruba abaixo de 4.5:1',
  },
  {
    nome: 'família dark-* (fundo fixo escuro)',
    re: /\bbg-dark-\d{3}\b/g,
    conserto: 'usar bg-card / bg-muted / bg-surface-raised, ou declarar a superfície como cromo escuro em PERMITIDO_TEMA',
  },
]

/**
 * Exceções justificadas. Chave: `caminho relativo :: classe`.
 * NÃO acrescentar linha sem justificativa que sobreviva a uma revisão.
 */
const PERMITIDO_TEMA: Record<string, string> = {
  // --- catraca da migração de 2026-09-06: estas linhas SAEM conforme as tasks avançam ---
  // Task 3 (_components/)
  'app/tecnico/qualificacao/_components/ColetaList.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/CollectedCard.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/EquipmentHeader.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/FileInput.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/InstrumentBadges.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/OsCard.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/RelatorioHeader.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/ReviewPanel.tsx :: *': 'migração pendente (Task 3)',
  'app/tecnico/qualificacao/_components/SignatureCanvas.tsx :: *': 'migração pendente (Task 3)',
  'components/ui/StatusBadge.tsx :: *': 'migração pendente (Task 3)',
  // Achados no pre-flight da Task 1, fora da lista original do plano — mesma
  // pasta/natureza dos demais arquivos da Task 3, adicionar ao Modify dela.
  'app/tecnico/qualificacao/_components/MicButton.tsx :: *': 'migração pendente (Task 3) — fora da lista original do plano',
  'components/ui/GlassCard.tsx :: *': 'migração pendente (Task 3) — fora da lista original do plano',
  // Task 4 (histórico + perfil)
  'app/tecnico/qualificacao/historico/page.tsx :: *': 'migração pendente (Task 4)',
  'app/tecnico/qualificacao/perfil/page.tsx :: *': 'migração pendente (Task 4)',
  // Task 5 (OS / coleta / relatório)
  'app/tecnico/qualificacao/[osId]/(painel)/layout.tsx :: *': 'migração pendente (Task 5)',
  'app/tecnico/qualificacao/[osId]/(painel)/coleta/[itemId]/page.tsx :: *': 'migração pendente (Task 5)',
  'app/tecnico/qualificacao/[osId]/relatorio/[relId]/page.tsx :: *': 'migração pendente (Task 5)',
  'app/tecnico/qualificacao/[osId]/relatorio/[relId]/finalizar/page.tsx :: *': 'migração pendente (Task 5)',
  'components/providers/AuthGuard.tsx :: *': 'migração pendente (Task 5)',
  // Task 6 (login)
  'app/login/page.tsx :: *': 'migração pendente (Task 6)',
  // Task 7 (visualizador)
  'components/ui/PdfViewerModal.tsx :: *': 'migração pendente (Task 7)',
}

function arquivos(): string[] {
  const out: string[] = []
  for (const pasta of PASTAS) {
    const walk = (d: string) => {
      for (const nome of readdirSync(d)) {
        if (nome === 'node_modules' || nome.startsWith('.')) continue
        const p = join(d, nome)
        if (statSync(p).isDirectory()) { walk(p); continue }
        if (!/\.tsx?$/.test(nome)) continue
        if (p.includes('__tests__')) continue
        out.push(p)
      }
    }
    walk(join(RAIZ, pasta))
  }
  return out
}

describe('tema: cor de estado só via token semântico', () => {
  /**
   * As duas verificações vivem no MESMO `it` de propósito. Se a lista de
   * exceções usadas fosse montada num teste e lida noutro, rodar a suíte
   * filtrada (`vitest -t "..."`, que este plano usa em várias tasks) acusaria
   * exceção morta que não está morta — o outro teste simplesmente não rodou.
   */
  it('nenhuma cor absoluta ou shade crua fora da lista, e nenhuma exceção morta', () => {
    const violacoes: string[] = []
    const usadas = new Set<string>()

    for (const abs of arquivos()) {
      const rel = relative(RAIZ, abs).split('\\').join('/')
      const src = readFileSync(abs, 'utf8')
      for (const regra of PROIBIDO) {
        for (const m of src.match(regra.re) ?? []) {
          const chaveCuringa = `${rel} :: *`
          const chaveExata = `${rel} :: ${m}`
          if (chaveCuringa in PERMITIDO_TEMA) { usadas.add(chaveCuringa); continue }
          if (chaveExata in PERMITIDO_TEMA) { usadas.add(chaveExata); continue }
          violacoes.push(`${rel}: \`${m}\` (${regra.nome}) — ${regra.conserto}`)
        }
      }
    }

    const mortas = Object.keys(PERMITIDO_TEMA).filter((k) => !usadas.has(k))

    expect(violacoes, `Classe de cor sem token semântico:\n  ${violacoes.join('\n  ')}`).toEqual([])
    expect(mortas, `Exceção que não corresponde a nenhum uso — apague:\n  ${mortas.join('\n  ')}`).toEqual([])
  })
})

describe('tema: tokens definidos nos dois temas', () => {
  const css = readFileSync(join(RAIZ, 'app/globals.css'), 'utf8')
  const bloco = (sel: string) => {
    const i = css.indexOf(`${sel} {`)
    expect(i, `bloco ${sel} não encontrado em globals.css`).toBeGreaterThan(-1)
    return css.slice(i, css.indexOf('\n}', i))
  }
  const NOVOS = ['ok', 'ok-surface', 'warn', 'warn-surface', 'danger', 'danger-surface',
                 'info', 'info-surface', 'surface-raised']

  it.each(NOVOS)('--%s existe nos dois temas, em tripla HSL', (nome) => {
    for (const sel of [':root', ':root.dark']) {
      const m = bloco(sel).match(new RegExp(String.raw`--${nome}:\s*([^;]+);`))
      expect(m, `--${nome} ausente em ${sel}`).not.toBeNull()
      // Tripla HSL crua: é o que faz `bg-ok/15` gerar CSS. Hex ou hsl() gera ZERO.
      expect(m![1].trim()).toMatch(/^\d{1,3} \d{1,3}% \d{1,3}%$/)
    }
  })

  it.each(NOVOS)('%s está mapeado no tailwind.config.ts com <alpha-value>', (nome) => {
    const cfg = readFileSync(join(RAIZ, 'tailwind.config.ts'), 'utf8')
    expect(cfg).toContain(`hsl(var(--${nome}) / <alpha-value>)`)
  })
})
