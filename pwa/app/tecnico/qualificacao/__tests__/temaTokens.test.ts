import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { hsl2rgb, contraste, sobre, tokenDe } from '@/tests/contraste'

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
 * `PERMITIDO_TEMA` nasceu enumerando os infratores de 2026-09-06 e encolheu
 * conforme cada task da migração apagava as suas linhas (Tasks 3-7). A
 * migração está FECHADA (Task 8): o que resta na lista é permanente e
 * nomeado — cromo escuro declarado do visualizador, as três superfícies de
 * papel/assinatura branco fixo, e o traço branco do ícone do Toaster (sobre
 * o próprio círculo colorido do ícone, não sobre o fundo do app). Uma
 * entrada nova só entra com justificativa escrita que sobreviva a revisão,
 * nunca com "task pendente" como motivo. Entrada morta continua sendo erro,
 * para a lista não virar depósito.
 *
 * LIMITAÇÃO CONHECIDA — o que esta guarda cobre por texto, e o que não dá:
 *
 * A regra "cor absoluta branca"/"shade crua" só lê `className` (texto
 * estático em arquivo-fonte) — cor em atributo `style={{ ... }}` ou em prop
 * de animação de biblioteca (ex.: Framer Motion
 * `animate={{ backgroundColor: '...' }}`) não é uma string de classe, então
 * nenhuma das duas primeiras regras a alcança. Achado real: o indicador de
 * passo do login (`StepIndicator` em `app/login/page.tsx`) media a cor do
 * badge com branco translúcido em RGB literal fixo — funcionava sobre
 * cartão navy (escuro) e desaparecia sobre cartão branco (claro).
 *
 * Detectar o LITERAL ainda é possível mesmo fora de `className` — é
 * texto-fonte de qualquer forma — e é o que a regra "branco literal em
 * RGB/hex/palavra-chave" abaixo faz, nas três formas em que branco fixo
 * aparece em JS: `rgba(255,255,255,…)`, `#fff`/`#ffffff` e a palavra-chave
 * CSS `white` (ex.: `backgroundColor: 'white'`). O describe de
 * `globals.css` mais abaixo neste arquivo cobre só DUAS dessas formas
 * (`rgba(255,255,255` e `color:\s*white`, em CSS puro) — não é o mesmo
 * conjunto: a regra daqui é mais ampla (as três formas, em qualquer
 * contexto JS/TSX, não só `color:`) porque o achado real que a motivou
 * (revisão adversarial da Task 8) era exatamente a palavra-chave sozinha
 * escapando por uma regra que só pegava as duas primeiras formas.
 * O que a guarda genuinamente NÃO alcança, porque não é literal:
 *   - cor montada por concatenação/interpolação de string em runtime
 *     (`` `bg-${cor}` ``, `'text-' + variante`, ou uma cor calculada e
 *     passada para `style`/`animate`) — a regex casa contra o texto-fonte,
 *     não contra o valor em runtime, então o resultado final nunca aparece
 *     literalmente no arquivo. Nenhuma outra cor fixa (que não seja branco)
 *     em `style`/prop de animação também escapa até virar um achado novo e
 *     ganhar sua própria regra — mesmo raciocínio do buraco de
 *     `accent`/`placeholder` acima.
 *
 * O que fazer no lugar, quando o caso for cor em prop de animação: não
 * anime a COR — anime opacidade/transform/scale sobre um elemento que já
 * carrega a classe de token semântico (`bg-foreground/10`,
 * `border-foreground/30`, etc.). A cor fica fixa via Tailwind (e portanto
 * tematizada e coberta por esta guarda); só o que muda com a animação
 * (opacidade, escala, posição) fica na prop do Framer. Foi a saída aplicada
 * em `StepIndicator`.
 */

const RAIZ = join(__dirname, '..', '..', '..', '..')
/**
 * TRÊS FRONTEIRAS CONHECIDAS desta varredura, registradas para quem for
 * confiar nela: (a) só estas pastas são varridas — `.ts`/`.tsx` na raiz do
 * projeto (`middleware.ts`, `tailwind.config.ts`) fica de fora; (b) valor
 * arbitrário não-branco (`bg-[#0a0f1e]`, `text-[rgb(10,15,30)]`) escapa de
 * todas as regras, que casam nome de família/token, não hex solto; (c) a
 * regra de opacidade nua só morde quando um token de TEXTO está na mesma
 * linha — texto que herda a cor do pai, ou cuja classe carrega só tamanho
 * (`text-[11px] ... opacity-70`), passa batido (achados reais em
 * `RelatorioHeader.tsx` e `KindPill.tsx`, corrigidos à mão na revisão final
 * de 2026-09-06).
 */
const PASTAS = ['app', 'components', 'lib']

const FAMILIAS = 'emerald|amber|red|rose|cyan|sky|blue|green|yellow|orange|teal|violet|indigo|fuchsia|pink|lime|gray|slate|zinc|neutral|stone'

/**
 * Prefixos de utilitário de cor do Tailwind que carregam cor de estado ou
 * cor absoluta. As duas regras de `PROIBIDO` abaixo (branco / shade crua)
 * enxergam o MESMO conjunto — uma cobrindo mais prefixos que a outra é
 * assimetria, e assimetria é o próximo buraco (achado real: `accent-emerald-500`
 * em `page.tsx` passava pela Regra 2 porque `accent` não estava na lista;
 * segundo achado: `placeholder-white/40` no login escapava das duas regras
 * porque `placeholder` também não estava na lista — só apareceu por grep
 * manual, não pela guarda).
 */
const PREFIXOS = 'text|bg|border|divide|ring|accent|from|via|to|shadow|outline|decoration|caret|fill|stroke|placeholder'

/**
 * Tokens que pintam TEXTO. Enumerados literalmente, não por prefixo `text-`:
 * `text-[11px]` e `text-xs` também começam com `text-` e não são cor nenhuma.
 */
const TOKEN_TEXTO = String.raw`text-(?:muted-foreground|foreground|ok|warn|danger|info)\b`

const PROIBIDO: { nome: string; re: RegExp; conserto: string; exigeNaLinha?: RegExp }[] = [
  {
    // `black` entrou junto com as famílias neutras logo abaixo (Task 13,
    // Step 2-A): mesma assimetria de `accent`/`placeholder` — a Regra 2
    // (shade crua) exige sufixo numérico (`-gray-500`), que `black`/`white`
    // não têm, então os dois só podem ser pegos aqui.
    nome: 'cor absoluta branca ou preta',
    re: new RegExp(String.raw`\b(?:${PREFIXOS})-(?:white|black)(?:\/\d{1,3})?\b`, 'g'),
    conserto: 'usar o papel semântico: text-foreground / text-muted-foreground / bg-surface-raised / border-border, ou declarar cromo escuro/overlay em PERMITIDO_TEMA quando for decisão de projeto',
  },
  {
    nome: 'shade crua de cor de estado',
    re: new RegExp(String.raw`\b(?:${PREFIXOS})-(?:${FAMILIAS})-\d{2,3}(?:\/\d{1,3})?\b`, 'g'),
    conserto: 'usar o token de estado: text-ok/warn/danger/info e bg-*-surface',
  },
  {
    nome: 'opacidade sobre tinta secundária',
    re: /\btext-muted-foreground\/\d{1,3}\b/g,
    conserto: 'usar text-muted-foreground puro — a opacidade derruba abaixo de 4.5:1',
  },
  {
    // ACHADO DA REVISÃO FINAL (2026-09-06), e o erro estava no PLANO:
    // a tabela de tradução mandava trocar `text-muted-foreground/60` (que a
    // regra acima proíbe) por `text-muted-foreground opacity-60`, com o
    // argumento de que "o mecanismo proibido é a opacidade embutida na
    // classe de COR". Isso confunde MECANISMO com EFEITO: os dois compõem
    // pixel idêntico — 2,80:1 no claro, 3,74:1 no escuro — e a saída
    // sancionada reproduzia o defeito no mesmo valor, agora invisível para
    // a guarda. A regra acima virava teatro.
    //
    // A decisão: para TEXTO não existe terceiro nível de tinta (DESIGN.md,
    // "Tinta Apagada" é proibida em texto que o técnico precisa ler). Se a
    // hierarquia ficar chapada, ela volta por TAMANHO ou PESO de fonte.
    // `opacity-N` continua permitido em ÍCONE e DECORAÇÃO, onde não há piso
    // — por isso a regra pega a CO-OCORRÊNCIA (opacidade nua + token de
    // texto na mesma linha) e os ícones entram nomeados em PERMITIDO_TEMA,
    // não por curinga.
    //
    // Só opacidade NUA conta. `opacity-0`/`opacity-100` (extremos de
    // animação) e qualquer variante prefixada (`hover:`, `group-hover/x:`,
    // `disabled:`, `focus:`, `peer-*:`) ficam de fora de propósito: são
    // interação e estado desabilitado, não redução permanente de tinta —
    // incluí-las obrigaria a cadastrar exceção para cada revelação em hover
    // do app, que é exatamente o tipo de exceção que ninguém entende depois.
    nome: 'opacidade nua sobre token de texto (mesmo efeito de text-X/60)',
    re: /(?<![\w:/-])opacity-(?:[1-9]\d?|\[[^\]\s]*\])(?![\w-])/g,
    exigeNaLinha: new RegExp(TOKEN_TEXTO),
    conserto: 'texto não leva opacidade — usar o token puro e diferenciar por tamanho/peso de fonte; se for ícone ou decoração, declarar exceção nomeada em PERMITIDO_TEMA',
  },
  {
    nome: 'família dark-* (fundo fixo escuro)',
    re: /\bbg-dark-\d{3}\b/g,
    conserto: 'usar bg-card / bg-muted / bg-surface-raised, ou declarar a superfície como cromo escuro em PERMITIDO_TEMA',
  },
  {
    nome: 'branco literal em RGB/hex/palavra-chave (fora de className)',
    // Não é uma classe Tailwind — é o padrão que apareceu dentro de uma prop
    // de animação do Framer Motion (`animate={{ backgroundColor: 'rgba(255,
    // 255, 255, …)' }}` ou, forma mais curta, `backgroundColor: 'white'`),
    // onde nenhuma regra de `className` acima alcança. Detectar o literal no
    // texto-fonte É possível (é isto aqui); resolver sozinho não é — Framer
    // não interpola `hsl(var(--token))`, então a correção continua sendo
    // trocar a prop de cor por uma classe de token fixo (ver LIMITAÇÃO
    // CONHECIDA no topo do arquivo). As três formas do literal contam:
    // `rgba(255,255,255,…)`, `#fff`/`#ffffff` e a palavra-chave CSS `white`
    // (revisão adversarial: `backgroundColor: 'white'` no `StepIndicator`
    // passava batido com só as duas primeiras formas). O look-behind
    // `(?<!-)` na palavra-chave existe para NÃO recair sobre o sufixo de
    // classes Tailwind já cobertas pela Regra 1 (`text-white`, `bg-white/40`,
    // `border-white/10`, …) — sem ele, cada ocorrência dessas classes vira
    // uma SEGUNDA violação (mesma linha, chave de exceção diferente).
    re: /(?<!-)\bwhite\b|rgba?\(\s*255,\s*255,\s*255|#fff\b|#ffffff\b/gi,
    conserto: 'não anime a cor — classe de token no elemento (ex.: bg-foreground/10), animando só opacidade/transform/scale; se for cor fixa sobre uma superfície que não é o fundo do app (ex.: ícone sobre círculo colorido próprio), declarar exceção nomeada em PERMITIDO_TEMA',
  },
]

/**
 * Exceções justificadas. Chave: `caminho relativo :: classe`.
 * NÃO acrescentar linha sem justificativa que sobreviva a uma revisão.
 */
const PERMITIDO_TEMA: Record<string, string> = {
  // --- migração de 2026-09-06, FECHADA na Task 8: as linhas abaixo são permanentes ---
  // Superfície de assinatura (DESIGN.md, "Signature Pad"): branca fixa,
  // permitida no tema escuro — assinatura é documento, e documento é sobre
  // papel, então o pad não segue o tema. O traço em si é `penColor="black"`
  // em JS (não classe, o teste-catraca não alcança) e é coberto por um teste
  // dedicado em `SignatureCanvas.test.tsx` que proíbe literal de cor branca
  // no traço — o risco real (assinatura branca sobre papel branco) está lá,
  // não aqui.
  'app/tecnico/qualificacao/_components/SignatureCanvas.tsx :: bg-white': 'permanente — pad de assinatura é papel branco fixo, independente do tema (DESIGN.md §Signature Pad)',
  // Segunda (e última) superfície branca fixa do app, pelo mesmo raciocínio
  // do Signature Pad: o `<img>` do logotipo da empresa é um ativo externo,
  // muitas vezes PNG com fundo transparente e traços escuros pensados pra
  // sentar sobre papel branco — não sobre o tema. `bg-card` bateria certo no
  // claro (que já é branco), mas no escuro é navy (`225 50% 8%`) e apagaria
  // logo com tinta escura; e o tema escuro não pode mudar de aparência
  // (Constraint global da Task 4). Fica fora do escopo mecânico da tabela de
  // tradução — mesma classe de decisão que o achado do `EquipmentHeader` na
  // Task 3.
  'app/tecnico/qualificacao/perfil/page.tsx :: bg-white': 'permanente — moldura do logotipo da empresa: ativo externo assumido sobre fundo branco, independente do tema (mesmo raciocínio do Signature Pad)',
  // Terceira superfície branca fixa, mesmo raciocínio do Signature Pad: aqui
  // não é o campo de captura, é a EXIBIÇÃO da assinatura já salva (relatório
  // fechado, somente leitura). O traço veio gravado com `penColor="black"`
  // (SignatureCanvas.tsx) — fundo que segue o tema apagaria a assinatura no
  // escuro (`bg-card` é navy), então o papel também não segue o tema aqui.
  'app/tecnico/qualificacao/[osId]/relatorio/[relId]/page.tsx :: bg-white': 'permanente — exibição da assinatura já capturada é documento/papel, mesmo raciocínio do Signature Pad (DESIGN.md)',

  // --- Task 7: visualizador (PdfViewerModal) — permanente, não é migração ---
  // Decisão de projeto: o visualizador é cromo escuro nos dois temas (foto de
  // coleta e PDF se leem melhor sobre fundo escuro; o overlay já é
  // `bg-black/85`). Cada classe abaixo é a família `dark-*`/tinta branca que
  // materializa essa decisão — nomeada, não curinga, porque um curinga
  // deixaria o arquivo livre para receber qualquer classe nova no futuro.
  'components/ui/PdfViewerModal.tsx :: bg-dark-800': 'Cromo escuro declarado — superfície do painel do visualizador (mesmo valor de --card no tema escuro: 225 50% 8%, aparência preservada).',
  'components/ui/PdfViewerModal.tsx :: bg-dark-700': 'Cromo escuro declarado — superfície elevada dentro do visualizador (chip do ícone no cabeçalho, botão de fechar).',
  'components/ui/PdfViewerModal.tsx :: bg-dark-900': 'Cromo escuro declarado — superfície dos campos de entrada (página e busca), mesmo valor de --background no tema escuro (224 71% 4%).',
  'components/ui/PdfViewerModal.tsx :: bg-white': 'Dois usos, nenhum tematizável: overlay sutil da toolbar (`bg-white/[0.02]`, cromo escuro) e a folha do PDF em si — papel tem fundo próprio, branco fixo, mesmo raciocínio do Signature Pad.',
  'components/ui/PdfViewerModal.tsx :: bg-white/5': 'Cromo escuro declarado — fundo sutil dos botões de ferramenta.',
  'components/ui/PdfViewerModal.tsx :: bg-white/10': 'Cromo escuro declarado — divisores e realce de hover do visualizador.',
  'components/ui/PdfViewerModal.tsx :: border-white/5': 'Cromo escuro declarado — borda decorativa do rodapé.',
  'components/ui/PdfViewerModal.tsx :: border-white/10': 'Cromo escuro declarado — bordas decorativas do painel, cabeçalho, toolbar e botões.',
  'components/ui/PdfViewerModal.tsx :: border-white/40': 'Cromo escuro declarado — borda dos campos de entrada; medida em ~3.8:1 sobre o painel escuro, acima do piso de 3:1 para fronteira de controle.',
  'components/ui/PdfViewerModal.tsx :: text-white': 'Cromo escuro declarado — título e textos principais do visualizador.',
  'components/ui/PdfViewerModal.tsx :: text-white/40': 'Cromo escuro declarado — ícone decorativo de busca (não é texto de conteúdo; piso de contraste de texto não se aplica).',
  'components/ui/PdfViewerModal.tsx :: text-white/50': 'Cromo escuro declarado — textos secundários (nome do arquivo, contagem de páginas, resultado de busca, rodapé, "Carregando PDF..."); medido em ~5.3:1 sobre o fundo escuro fixo, acima do piso de 4.5:1.',
  'components/ui/PdfViewerModal.tsx :: text-white/65': 'Cromo escuro declarado — ícones decorativos (arquivo no cabeçalho, spinner de carregamento); ~8.2:1, o valor que mais se aproxima de --muted-foreground do tema escuro (221 20% 70% ≈ rgb(163,173,194)), preservando o brilho original desses ícones.',
  'components/ui/PdfViewerModal.tsx :: text-white/70': 'Cromo escuro declarado — texto dos botões de ferramenta.',
  'components/ui/PdfViewerModal.tsx :: text-red-400': 'Cromo escuro declarado — cor de erro fixa (equivalente a --danger do tema escuro); o token semântico text-danger fica vermelho-escuro no tema claro e ficaria ilegível sobre o painel escuro fixo.',
  // Overlay que escurece o conteúdo por trás do modal — não é fundo de
  // painel (esses já são `bg-dark-*` acima), é a camada que separa o
  // visualizador do resto da página. Preto puro com opacidade funciona
  // igual nos dois temas porque a função é achatar tudo atrás, não seguir
  // paleta: overlay claro deixaria o PDF/foto competindo com o conteúdo por
  // baixo. Task 13, Step 2-A (família `black` fechando o buraco de `gray|
  // slate|zinc|neutral|stone` que a Task 8 tinha deixado sem regra).
  'components/ui/PdfViewerModal.tsx :: bg-black/85': 'Overlay preto sobre o conteúdo por trás do modal — legítimo nos dois temas, é o que faz o visualizador (foto/PDF) se ler sem competir com a página atrás.',
  'components/ui/PdfViewerModal.tsx :: bg-black/60': 'Overlay preto do fundo da área de página do visualizador — mesmo raciocínio do bg-black/85: escurece atrás do PDF nos dois temas, não é superfície temática.',

  // --- achado da Regra 5 (palavra-chave `white`), fixado na revisão adversarial da Task 8 ---
  // `<Toaster iconTheme>` (react-hot-toast) do layout raiz: `primary` é o
  // preenchimento do círculo do ícone (emerald/pink), `secondary` é o traço
  // do check/x por cima. O branco nunca senta sobre o fundo do app — senta
  // sobre o próprio círculo colorido, que é opaco e fixo nos dois temas — e
  // por isso não segue o token semântico (que mudaria de tom sem mudar o
  // círculo, quebrando o desenho do ícone). Mesmo raciocínio de "superfície
  // não é o app" das outras exceções permanentes, aplicado a um traço em vez
  // de a um fundo.
  'app/layout.tsx :: white': 'permanente — cor do traço do ícone de sucesso/erro do Toaster (react-hot-toast), sempre sobre o próprio círculo colorido do ícone (#10b981/#ec4899), nunca sobre o fundo do app.',

  // --- Task 13, Step 2-A: terceiro uso real de `black`, fora do PdfViewerModal ---
  // Lightbox de foto coletada (`CollectedCard.tsx`): mesmo raciocínio do
  // overlay do PdfViewerModal — preto translúcido escurece a página atrás
  // pra foto em tela cheia se ler, nos dois temas. Não é superfície do app,
  // é camada de foco sobre o conteúdo por trás.
  'app/tecnico/qualificacao/_components/CollectedCard.tsx :: bg-black/90': 'Overlay preto do lightbox de foto em tela cheia — legítimo nos dois temas, escurece a página atrás pra foto se ler (mesmo raciocínio do overlay do PdfViewerModal).',

  // --- revisão final de 2026-09-06: regra "opacidade nua sobre token de texto" ---
  // Único uso legítimo hoje: o `ChevronRight` do item de histórico. É ÍCONE
  // (affordance de "abre"), não texto — não responde a piso de contraste — e
  // a opacidade é metade de um par apaga/acende (`group-hover:opacity-100`)
  // que carrega a interação. O token de texto na mesma linha
  // (`text-muted-foreground`) é o que pinta o traço do ícone, e é só a
  // co-ocorrência com ele que traz a linha para a regra.
  'app/tecnico/qualificacao/historico/page.tsx :: opacity-60': 'ícone (ChevronRight) em par apaga/acende com group-hover:opacity-100 — decoração/affordance, sem piso de contraste de texto.',
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
      // Varredura por LINHA, não pelo arquivo inteiro. Para as regras de
      // token único o resultado é idêntico (a regex casa um pedaço só); o
      // que a linha habilita é `exigeNaLinha`, que só faz sentido com uma
      // noção de vizinhança — e a linha é a mesma noção de localidade que o
      // `scripts/contrast-audit.mjs` já usa para inferir fundo.
      for (const linha of src.split('\n')) {
        for (const regra of PROIBIDO) {
          if (regra.exigeNaLinha && !regra.exigeNaLinha.test(linha)) continue
          for (const m of linha.match(regra.re) ?? []) {
            const chaveCuringa = `${rel} :: *`
            const chaveExata = `${rel} :: ${m}`
            if (chaveCuringa in PERMITIDO_TEMA) { usadas.add(chaveCuringa); continue }
            if (chaveExata in PERMITIDO_TEMA) { usadas.add(chaveExata); continue }
            violacoes.push(`${rel}: \`${m}\` (${regra.nome}) — ${regra.conserto}`)
          }
        }
      }
    }

    const mortas = Object.keys(PERMITIDO_TEMA).filter((k) => !usadas.has(k))

    expect(violacoes, `Classe de cor sem token semântico:\n  ${violacoes.join('\n  ')}`).toEqual([])
    expect(mortas, `Exceção que não corresponde a nenhum uso — apague:\n  ${mortas.join('\n  ')}`).toEqual([])
  })
})

describe('visualizador: superfície escura declarada', () => {
  const src = readFileSync(join(RAIZ, 'components/ui/PdfViewerModal.tsx'), 'utf8')

  it('o painel não usa superfície temática por baixo de tinta branca', () => {
    // `bg-card` + `text-white` = branco no branco quando o tema é claro.
    // Aqui o cromo é escuro DE PROPÓSITO: então a superfície tem que ser
    // escura de propósito também.
    expect(src).not.toMatch(/bg-(?:card|muted|background)\b/)
  })

  it('a decisão está escrita no arquivo', () => {
    expect(src).toMatch(/cromo escuro/i)
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

describe('tema: nada de escuro fixo no @layer base', () => {
  const css = readFileSync(join(RAIZ, 'app/globals.css'), 'utf8')

  it('color-scheme dos inputs de data segue o tema, não é fixo em dark', () => {
    // O script do next-themes já escreve `document.documentElement.style.colorScheme`.
    // Uma regra `color-scheme: dark` incondicional no CSS vence isso para os
    // inputs e entrega seletor de data escuro em página clara.
    const base = css.slice(css.indexOf('@layer base'))
    expect(base).not.toMatch(/color-scheme:\s*dark\s*;/)
  })

  it('scrollbar e seleção de texto não usam branco absoluto', () => {
    const base = css.slice(css.indexOf('@layer base'), css.indexOf('@layer utilities'))
    // `rgba(255,255,255,0.1)` num thumb sobre fundo claro é invisível;
    // `::selection { color: white }` sobre um realce de 20% de opacidade
    // apaga o texto selecionado.
    expect(base).not.toMatch(/rgba\(255,\s*255,\s*255/)
    expect(base).not.toMatch(/color:\s*white/)
  })
})

/**
 * Exceção nomeada e VIVA (Task 13): `--danger`/`--danger-surface` no
 * `:root.dark` passam a asserção "sem hover" (6.11:1) mas não a de "com
 * hover a 20% do próprio matiz" (4.38:1, abaixo do piso de 4.5). Nenhum chip
 * `danger` carrega hoje `hover:bg-danger/20` no escuro — confirmado por
 * grep em 2026-09-06 (`hover:bg-(ok|warn|danger|info)\b` só aparece em
 * `hover:bg-danger/10` num botão de borda, `hover:bg-ok/[0.04]` e o
 * `hover:bg-info/20` do ReviewPanel que motivou esta task) — é risco
 * preventivo, não bug ativo hoje.
 *
 * Corrigir exigiria mudar `--danger-surface` dentro de `:root.dark`, e a
 * Constraint global desta task proíbe tocar no escuro (está em produção).
 * Fica registrado aqui, não varrido para debaixo do tapete: a segunda
 * asserção do teste abaixo AFIRMA que a exceção CONTINUA necessária (valor
 * < 4.5). Se algum dia alguém escurecer `--danger-surface` no dark o
 * suficiente pra essa asserção passar sozinha, o teste quebra — mesmo
 * espírito da "exceção morta" que `PERMITIDO_TEMA` já aplica a classes.
 */
const EXCECAO_HOVER_CONTRASTE = new Set<string>([':root.dark::danger'])

describe('tema: token de estado tem folga para o hover do próprio matiz', () => {
  // Um chip `text-info` sobre `bg-info-surface` que ganha `hover:bg-info/20`
  // fica com texto e fundo do MESMO matiz se aproximando. Se o token não tiver
  // margem, o hover derruba abaixo do piso — foi o que aconteceu em
  // ReviewPanel.tsx:288 (3.66:1), achado pela auditoria de 2026-09-06.
  const css = readFileSync(join(RAIZ, 'app/globals.css'), 'utf8')

  // `hsl2rgb`/`luminancia`/`contraste`/`sobre` moram em `tests/contraste.ts`
  // desde a revisão final: `StatusBadge.test.tsx` precisa da MESMA medição, e
  // duas cópias da matemática de contraste é como a deriva de 8,72 -> 7,99
  // passou sem ninguém ver.
  const token = (tema: string, papel: string): string => {
    const v = tokenDe(css, tema, papel)
    expect(v, `--${papel} ausente em ${tema}`).not.toBeNull()
    return v!
  }

  it.each(['ok', 'warn', 'danger', 'info'])(
    '--%s legível sobre a própria superfície, inclusive com hover a 20%%',
    (papel) => {
      for (const tema of [':root', ':root.dark']) {
        const fg = hsl2rgb(token(tema, papel))
        const bg = hsl2rgb(token(tema, `${papel}-surface`))
        expect(contraste(fg, bg)).toBeGreaterThanOrEqual(4.5)

        const comHover = contraste(fg, sobre(fg, 0.2, bg))
        const chave = `${tema}::${papel}`
        if (EXCECAO_HOVER_CONTRASTE.has(chave)) {
          // Exceção viva: se isto passar a ser >= 4.5 sozinho, a linha em
          // EXCECAO_HOVER_CONTRASTE ficou morta — apagar.
          expect(comHover).toBeLessThan(4.5)
        } else {
          expect(comHover).toBeGreaterThanOrEqual(4.5)
        }
      }
    },
  )
})
