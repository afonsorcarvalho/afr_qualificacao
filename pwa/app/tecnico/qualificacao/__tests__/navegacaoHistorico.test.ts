import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * Guarda contra o defeito de "beco sem saída no histórico".
 *
 * Três vezes o mesmo erro, achado em campo em 2026-09-05: `router.push` depois
 * de uma ação TERMINAL deixa a tela concluída no histórico, e o botão voltar
 * do navegador leva de volta a ela.
 *
 *   - fechar relatório  -> voltava ao formulário do relatório já fechado, e
 *     tentar fechar de novo dava erro no servidor;
 *   - sair (logout)     -> voltava à tela autenticada sem sessão, com o
 *     AuthGuard expulsando depois (piscada + POST de logout extra);
 *   - entrar (login)    -> voltava ao formulário de credenciais já logado.
 *
 * Teste de unidade cobre o caso que existe hoje; este cobre o **próximo**.
 * Ele lê o código-fonte e obriga todo `router.push` a estar declarado abaixo
 * com uma justificativa. Quem acrescentar um novo vê o teste falhar e decide
 * conscientemente entre `push` (navegação de ida, volta faz sentido) e
 * `replace` (ação terminal, a tela não deve sobreviver no histórico).
 */

const RAIZ = join(__dirname, '..', '..', '..', '..')
const PASTAS = ['app', 'components', 'lib']

/**
 * `push` legítimo: navegação de ida, em que voltar é o comportamento certo.
 * Chave: `caminho do arquivo :: primeiro argumento, como escrito`.
 */
const PUSH_PERMITIDO: Record<string, string> = {
  'app/tecnico/qualificacao/[osId]/(painel)/layout.tsx :: `/tecnico/qualificacao/${id}/relatorio/${data.open_relatorio_id}/finalizar`':
    'Ida para o fechamento do turno. Voltar dali para a OS é o esperado, e o formulário ainda não foi enviado.',
  'app/tecnico/qualificacao/_components/TecnicoNav.tsx :: href':
    'Troca de aba (OSs / Histórico / Perfil). Voltar tem que devolver à aba anterior.',
  'components/ui/PendingLink.tsx :: href':
    'Link genérico de lista para detalhe (abrir uma coleta). Voltar é justamente o caminho de saída.',
}

function arquivosFonte(dir: string): string[] {
  const saida: string[] = []
  const caminhar = (d: string) => {
    for (const nome of readdirSync(d)) {
      if (nome === 'node_modules' || nome === '.next' || nome === '__tests__') continue
      const p = join(d, nome)
      if (statSync(p).isDirectory()) caminhar(p)
      else if (/\.tsx?$/.test(p) && !/\.test\.tsx?$/.test(p)) saida.push(p)
    }
  }
  caminhar(dir)
  return saida
}

/** Primeiro argumento da chamada, respeitando parênteses e crases aninhados. */
function primeiroArgumento(texto: string, aberturaIdx: number): string {
  let nivel = 0
  for (let i = aberturaIdx; i < texto.length; i++) {
    const c = texto[i]
    if (c === '(') nivel++
    else if (c === ')') {
      nivel--
      if (nivel === 0) return texto.slice(aberturaIdx + 1, i).trim()
    }
  }
  return texto.slice(aberturaIdx + 1, aberturaIdx + 80).trim()
}

type Ocorrencia = { arquivo: string; linha: number; arg: string; chave: string }

function acharPushes(): Ocorrencia[] {
  const achados: Ocorrencia[] = []
  for (const pasta of PASTAS) {
    for (const abs of arquivosFonte(join(RAIZ, pasta))) {
      const src = readFileSync(abs, 'utf8')
      const arquivo = relative(RAIZ, abs)
      const re = /router\.push\s*\(/g
      let m: RegExpExecArray | null
      while ((m = re.exec(src))) {
        const idx = m.index + m[0].length - 1
        const arg = primeiroArgumento(src, idx)
        achados.push({
          arquivo,
          linha: src.slice(0, m.index).split('\n').length,
          arg,
          chave: `${arquivo} :: ${arg}`,
        })
      }
    }
  }
  return achados
}

describe('histórico de navegação', () => {
  it('todo router.push é declarado, com motivo', () => {
    const naoDeclarados = acharPushes().filter((o) => !(o.chave in PUSH_PERMITIDO))
    if (naoDeclarados.length > 0) {
      // Erro lançado à mão, não `expect(...).toEqual([])`: a orientação é o
      // ponto do teste, e o diff de array a esconderia.
      throw new Error(
        [
          'router.push novo encontrado:',
          ...naoDeclarados.map((o) => `  ${o.arquivo}:${o.linha}  ->  ${o.arg}`),
          '',
          'Decida antes de liberar:',
          '',
          '  A tela de onde ele sai é TERMINAL? (fechou o relatório, saiu da',
          '  conta, entrou, salvou e não há mais o que fazer ali)',
          '      -> use router.replace.',
          '  Deixá-la no histórico faz o botão voltar devolver o técnico a uma',
          '  tela já consumida, e repetir a ação costuma dar erro no servidor.',
          '',
          '  É navegação de IDA, em que voltar é o comportamento certo?',
          '      -> mantenha o push e declare em PUSH_PERMITIDO, com o motivo.',
        ].join('\n'),
      )
    }
  })

  it('a lista de permitidos não guarda entrada morta', () => {
    // Entrada que sobra depois de o código mudar vira permissão fantasma:
    // libera silenciosamente um `push` futuro no mesmo arquivo.
    const presentes = new Set(acharPushes().map((o) => o.chave))
    const orfas = Object.keys(PUSH_PERMITIDO).filter((k) => !presentes.has(k))
    expect(orfas, 'remova de PUSH_PERMITIDO o que não existe mais no código').toEqual([])
  })

  it('nenhum router.push dentro de onSuccess', () => {
    // `onSuccess` é, por definição, o fim de uma ação: a tela que a disparou
    // já cumpriu seu papel e não deve sobreviver no histórico. Foi assim que
    // o fechamento de relatório quebrou.
    const suspeitos: string[] = []
    for (const pasta of PASTAS) {
      for (const abs of arquivosFonte(join(RAIZ, pasta))) {
        const src = readFileSync(abs, 'utf8')
        const re = /onSuccess\s*:\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{([\s\S]{0,600}?)\n\s*\},/g
        let m: RegExpExecArray | null
        while ((m = re.exec(src))) {
          if (m[1].includes('router.push')) {
            suspeitos.push(
              `${relative(RAIZ, abs)}:${src.slice(0, m.index).split('\n').length}`,
            )
          }
        }
      }
    }
    expect(suspeitos, 'use router.replace: onSuccess é ação terminal').toEqual([])
  })
})
