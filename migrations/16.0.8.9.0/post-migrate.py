# -*- coding: utf-8 -*-
"""16.0.8.9.0 — template/procedimento por cliente/equipamento.

Remove a unique(equipment_category_id, company_id) (agora `is_default`
permite N procedimentos por categoria, só 1 marcado como padrão) e marca
como `is_default=True` os procedimentos existentes — antes desta versão
havia no máximo 1 por categoria (a constraint removida garantia isso), então
migrar todos para padrão preserva o comportamento de `resolve_for`.

Ressalva (categorias vazias / genéricas): a constraint antiga tratava NULL
como distinto de si mesmo no Postgres, então uma empresa podia ter VÁRIOS
procedimentos sem categoria (genéricos) simultaneamente — diferente das
categorizadas, que eram sempre 0 ou 1. Marcar TODOS como is_default=True
violaria a nova regra "no máximo 1 is_default por (categoria, empresa)"
assim que o primeiro desses registros fosse salvo de novo. Por isso: linhas
categorizadas viram is_default=True (1:1, sem risco); linhas genéricas
(equipment_category_id IS NULL) só a de menor id por empresa vira
is_default=True — as demais ficam is_default=False (deixam de ser retornadas
por resolve_for/_resolve_for_equipment; permanecem selecionáveis à mão no
equipamento/cliente/wizard).

Qualificações antigas ficam com procedimento_id/relatorio_template_id vazios
(fora de escopo deduzir retroativamente — decisão 10 do spec).
"""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE afr_qualificacao_procedimento "
        "DROP CONSTRAINT IF EXISTS afr_qualificacao_procedimento_uniq_category_company"
    )

    # Categorizadas: 1 por (categoria, empresa) já garantido pela constraint
    # removida acima — todas viram padrão da categoria.
    cr.execute(
        "UPDATE afr_qualificacao_procedimento SET is_default = TRUE "
        "WHERE equipment_category_id IS NOT NULL"
    )

    # Genéricas (sem categoria): pode haver várias por empresa; só a mais
    # antiga (menor id) vira padrão, para não violar a nova unicidade.
    cr.execute(
        """
        UPDATE afr_qualificacao_procedimento p
        SET is_default = TRUE
        WHERE p.equipment_category_id IS NULL
          AND p.id = (
              SELECT MIN(p2.id)
              FROM afr_qualificacao_procedimento p2
              WHERE p2.equipment_category_id IS NULL
                AND (p2.company_id = p.company_id
                     OR (p2.company_id IS NULL AND p.company_id IS NULL))
          )
        """
    )
