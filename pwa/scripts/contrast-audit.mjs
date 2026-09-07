#!/usr/bin/env node
/* Auditoria de contraste do tema CLARO do PWA Técnico.
 * Resolve a paleta real do Tailwind + os tokens de :root do globals.css,
 * compõe as cores translúcidas sobre o fundo, e calcula a razão WCAG.
 * Sem browser: determinístico, e serve de fixture pro teste-guarda.
 */
import fs from 'node:fs'
import path from 'node:path'
import resolveConfig from 'tailwindcss/resolveConfig.js'

const ROOT = process.argv[2] || process.cwd()
const THEME = (process.env.THEME || 'light')

// ── paleta do Tailwind (inclui o `extend` do projeto) ────────────────────
const cfgSrc = fs.readFileSync(path.join(ROOT, 'tailwind.config.ts'), 'utf8')
// Extrai só o objeto `colors:` do extend — evita ter que transpilar TS.
const colorsBlock = cfgSrc.slice(cfgSrc.indexOf('colors: {'))
const customFamilies = {}
for (const m of colorsBlock.matchAll(/(\w+):\s*\{([^}]*?)\}/g)) {
  const fam = m[1], body = m[2]
  const shades = {}
  for (const s of body.matchAll(/(\d{2,3}):\s*'(#[0-9a-fA-F]{3,8})'/g)) shades[s[1]] = s[2]
  if (Object.keys(shades).length) customFamilies[fam] = shades
}
const tw = resolveConfig({ content: [] })
const palette = { ...tw.theme.colors, ...customFamilies }

// ── tokens do globals.css ────────────────────────────────────────────────
const css = fs.readFileSync(path.join(ROOT, 'app/globals.css'), 'utf8')
function tokenBlock(selector) {
  const i = css.indexOf(selector + ' {')
  if (i < 0) return {}
  const body = css.slice(i, css.indexOf('\n}', i))
  const out = {}
  for (const m of body.matchAll(/--([\w-]+):\s*([^;]+);/g)) out[m[1]] = m[2].trim()
  return out
}
const tokens = THEME === 'dark' ? { ...tokenBlock(':root'), ...tokenBlock(':root.dark') } : tokenBlock(':root')

// ── conversões de cor ────────────────────────────────────────────────────
const hex2rgb = (h) => {
  h = h.replace('#', '')
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16))
}
const hsl2rgb = (hStr) => {
  const [h, s, l] = hStr.split(/\s+/).map((v) => parseFloat(v))
  const S = s / 100, L = l / 100
  const c = (1 - Math.abs(2 * L - 1)) * S
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = L - c / 2
  const seg = [[c,x,0],[x,c,0],[0,c,x],[0,x,c],[x,0,c],[c,0,x]][Math.floor((h % 360) / 60)]
  return seg.map((v) => Math.round((v + m) * 255))
}
// Resolve "emerald-300", "white", "muted-foreground", "card" → [r,g,b] ou null
function resolveColor(name) {
  if (name === 'white') return [255, 255, 255]
  if (name === 'black') return [0, 0, 0]
  if (name === 'transparent' || name === 'current' || name === 'inherit') return null
  // Qualquer token declarado no `:root` do globals.css resolve direto pelo nome
  // da classe: `text-ok` -> `--ok`, `bg-ok-surface` -> `--ok-surface`,
  // `bg-surface-raised` -> `--surface-raised`.
  //
  // ARMADILHA (custou um "zero achados" falso em 2026-09-06): a primeira versão
  // usava um mapa fixo de nomes semânticos, escrito antes dos tokens de estado
  // existirem. Depois da migração, quase toda classe de cor da árvore é um token
  // novo — e cada uma caía no `return null` do fim, sendo pulada em silêncio. O
  // relatório saía limpo por cegueira, não por acerto. Se uma auditoria "depois"
  // vier quase vazia, confira ANTES que `text-ok` e `bg-ok-surface` resolvem para
  // RGB de verdade.
  if (tokens[name]) return hsl2rgb(tokens[name])
  const m = name.match(/^([a-z]+)-(\d{2,3})$/)
  if (m && palette[m[1]] && palette[m[1]][m[2]]) {
    const v = palette[m[1]][m[2]]
    return typeof v === 'string' && v.startsWith('#') ? hex2rgb(v) : null
  }
  return null
}
const over = (fg, alpha, bg) => fg.map((c, i) => Math.round(c * alpha + bg[i] * (1 - alpha)))
const lum = (rgb) => {
  const [r, g, b] = rgb.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}
const ratio = (a, b) => { const [l1, l2] = [lum(a), lum(b)].sort((x, y) => y - x); return (l1 + 0.05) / (l2 + 0.05) }

// ── varredura ────────────────────────────────────────────────────────────
const files = []
;(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (e.name === 'node_modules' || e.name === '__tests__' || e.name.startsWith('.')) continue
    const p = path.join(d, e.name)
    if (e.isDirectory()) walk(p)
    else if (/\.tsx$/.test(e.name)) files.push(p)
  }
})(path.join(ROOT, 'app'))
;(function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    if (e.name === 'node_modules' || e.name === '__tests__' || e.name.startsWith('.')) continue
    const p = path.join(d, e.name)
    if (e.isDirectory()) walk(p)
    else if (/\.tsx$/.test(e.name)) files.push(p)
  }
})(path.join(ROOT, 'components'))

const PAGE_BG = resolveColor('background')
const CARD_BG = resolveColor('card')
const CLS = /(?:text|bg|border|ring|from|to|via)-[a-z]+(?:-[a-z]+)*(?:-\d{2,3})?(?:\/\d{1,3})?/g

const findings = []
for (const file of files) {
  const src = fs.readFileSync(file, 'utf8')
  const lines = src.split('\n')
  lines.forEach((line, idx) => {
    const classes = line.match(CLS) || []
    if (!classes.length) return
    // fundo declarado na MESMA linha (aproximação do elemento)
    let localBg = null
    for (const c of classes) {
      const m = c.match(/^bg-([a-z]+(?:-[a-z]+)*(?:-\d{2,3})?)(?:\/(\d{1,3}))?$/)
      if (!m) continue
      const base = resolveColor(m[1])
      if (!base) continue
      const a = m[2] ? Number(m[2]) / 100 : 1
      localBg = over(base, a, localBg || PAGE_BG)
    }
    for (const c of classes) {
      const m = c.match(/^(text|border|ring)-([a-z]+(?:-[a-z]+)*(?:-\d{2,3})?)(?:\/(\d{1,3}))?$/)
      if (!m) continue
      const kind = m[1]
      const base = resolveColor(m[2])
      if (!base) continue
      const a = m[3] ? Number(m[3]) / 100 : 1
      // pior caso entre o fundo local (se houver) e as duas superfícies base
      const bgs = localBg ? [localBg] : [PAGE_BG, CARD_BG]
      for (const bg of bgs) {
        const fg = over(base, a, bg)
        const r = ratio(fg, bg)
        const floor = kind === 'text' ? 4.5 : 3.0   // AA texto / AA não-textual
        if (r < floor) {
          findings.push({ file: path.relative(ROOT, file), line: idx + 1, cls: c, kind,
            bg: localBg ? 'local' : (bg === PAGE_BG ? 'background' : 'card'),
            ratio: Number(r.toFixed(2)), floor })
        }
      }
    }
  })
}

findings.sort((a, b) => a.ratio - b.ratio)
const byClass = {}
for (const f of findings) (byClass[f.cls] ||= []).push(f)

console.log(`\n== Tema ${THEME.toUpperCase()} — ${findings.length} ocorrências abaixo do piso AA ==\n`)
for (const [cls, list] of Object.entries(byClass).sort((a, b) => a[1][0].ratio - b[1][0].ratio)) {
  console.log(`${cls}  — pior ${list[0].ratio}:1 (piso ${list[0].floor}) — ${list.length} ocorrência(s)`)
  for (const f of list.slice(0, 6)) console.log(`    ${f.file}:${f.line}  sobre ${f.bg}  ${f.ratio}:1`)
  if (list.length > 6) console.log(`    ... +${list.length - 6}`)
}
console.log(`\nArquivos afetados: ${new Set(findings.map((f) => f.file)).size}`)
