# Template e procedimento por cliente/equipamento — design

Data: 2026-09-29 · Módulo: `afr_qualificacao` · Branch: `feat/relatorio-final`
Status: aprovado pelo user (partes 1–3 em chat).

## Problema

- O template do Relatório Final é sugerido só pela categoria do equipamento; sem
  match, cai no "primeiro template" em silêncio. Hospital e indústria têm a mesma
  categoria (autoclave) ⇒ relatório industrial nasceu com template Hospitalar
  (caso 212-25-4, relatório id 2 no qualificacao-dev).
- Procedimento de qualificação: 1 por categoria (trava SQL), aplicado
  automaticamente na geração da OS sem escolha; a qualificação não registra qual
  procedimento foi usado.

## Objetivo

Cliente e equipamento carregam os padrões; a escolha é explícita e visível ao
gerar a OS (procedimento + template por equipamento) e, se ainda faltar
template, ao gerar os Relatórios Finais. Nada de fallback silencioso.

## Decisões

1. **Cliente** (`res.partner`, commercial partner): `afr_relatorio_template_id`
   (M2O `afr.relatorio.template`) e `afr_procedimento_ids` (M2M
   `afr.qualificacao.procedimento`, no máximo 1 por categoria — constraint).
2. **Equipamento** (`engc.equipment`): `afr_procedimento_id` (M2O), domínio =
   procedimentos da categoria do equipamento ou genéricos (sem categoria).
3. **Procedimento**: remove `uniq_category_company`; novo `is_default`
   ("Padrão da categoria"), no máximo 1 `is_default` por (categoria, empresa) —
   `api.constrains`. `resolve_for(category)` passa a devolver o padrão da
   categoria (senão genérico padrão, senão genérico mais antigo) — API mantida.
4. **Qualificação** (`afr.qualificacao`): `procedimento_id` (M2O, aplicado) e
   `relatorio_template_id` (M2O, escolhido na OS).
5. **Resolução de procedimento** (função única, `procedimento._resolve_for_equipment(equipment, partner)` → `(procedimento, origem)`):
   equipamento → procedimento do cliente da mesma categoria → padrão da
   categoria → genérico padrão → vazio. `origem` ∈ `equipamento|cliente|categoria|generico|False`.
6. **Resolução de template** (`relatorio._resolve_template(equipment, partner, qualificacoes)` → `(template, origem)`):
   `relatorio_template_id` gravado nas qualificações do equipamento na OS →
   template do cliente → template cujo `equipment_category_ids` contém a
   categoria → vazio. **Remove** o fallback "menor sequence da empresa".
   Relatório criado sem template nasce sem blocos (verificação acusa; "Recarregar
   template" resolve).
7. **Wizard Gerar OS** (`afr.qualificacao.os.generate.wizard`): troca a M2M de
   equipamentos por linhas (`afr.qualificacao.os.generate.wizard.line`):
   incluir, equipamento, categoria, procedimento, template, origem (badge).
   Pré-preenchido pelas regras 5/6. `Salvar escolhas como padrão` (bool no
   wizard): grava procedimento no equipamento e template no cliente. **Gerar**
   bloqueia se linha incluída sem procedimento (mensagem lista os equipamentos).
   A materialização usa o procedimento escolhido (não mais `resolve_for`) e grava
   `procedimento_id`/`relatorio_template_id` nas qualificações.
   Chamada sem wizard (código/PWA/API) mantém comportamento: resolve pela regra 5.
8. **Gerar Relatórios Finais** (`action_generate_relatorios_open`): se todo
   equipamento resolve template (regra 6) ⇒ gera direto; senão abre wizard
   `afr.qualificacao.relatorio.template.wizard` com linha por equipamento sem
   template resolvido (+ os resolvidos, readonly/informativos) e
   `Salvar como padrão do cliente`.
9. **Aplicar procedimento** (wizard existente): usa a regra 5 para o default
   da linha, lista procedimentos da categoria + genéricos, grava
   `procedimento_id` na qualificação.
10. **Migração 16.0.8.9.0** (post): `DROP CONSTRAINT IF EXISTS
    afr_qualificacao_procedimento_uniq_category_company`; marca `is_default=True`
    em todos os procedimentos existentes (hoje únicos por categoria). Qualificações
    antigas ficam com `procedimento_id` vazio.

## Fora de escopo
Deduzir `procedimento_id` de qualificações antigas; segmento "hospitalar/industrial"
como campo próprio (o template do cliente cumpre o papel).

## Testes
Ver plano: regras 5/6 (inclusive procedimento do cliente de outra categoria
ignorado; sem fallback silencioso), constraint de padrão único, migração,
wizard Gerar OS (pré-preenchimento/origem, bloqueio, gravação, salvar padrão,
explode do procedimento escolhido), Gerar Relatórios (direto × wizard, salvar
no cliente), Aplicar procedimento grava `procedimento_id`. UI via agent-browser
no qualificacao-dev com a cotação C26-09-0019 (cliente configurado Industrial).
