# -*- coding: utf-8 -*-
"""16.0.8.9.0 — template/procedimento por cliente/equipamento.

Remove a unique(equipment_category_id, company_id) (agora `is_default`
permite N procedimentos por categoria, só 1 marcado como padrão) — a
constraint no Postgres e o registro dela em `ir_model_constraint` (+ o
xmlid `constraint_..._uniq_category_company` em `ir_model_data`), para não
sobrar metadado órfão.

Depois marca como `is_default=True` exatamente UM procedimento por
(categoria, empresa) — incluindo categoria vazia (genéricos) e empresa
vazia, que o `DISTINCT ON` agrupa como NULL = NULL — preferindo o ativo e,
entre eles, o de menor id; todos os demais ficam `is_default=False`.
Categorizadas eram 0 ou 1 por (categoria, empresa) (a constraint removida
garantia isso), então viram padrão 1:1 e o `resolve_for` se mantém. Já os
genéricos podiam ser vários (a constraint antiga tratava NULL como distinto
de si mesmo): só o mais antigo ativo vira padrão, sem violar a nova regra
"no máximo 1 is_default ativo por (categoria, empresa)"; os demais seguem
selecionáveis à mão no equipamento/cliente/wizard.

Idempotente: zerar + remarcar produz sempre o mesmo resultado, e os DELETE/
DROP não falham se já não houver o que remover.

Qualificações antigas ficam com procedimento_id/relatorio_template_id vazios
(fora de escopo deduzir retroativamente — decisão 10 do spec).
"""

CONSTRAINT = "afr_qualificacao_procedimento_uniq_category_company"


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE afr_qualificacao_procedimento "
        "DROP CONSTRAINT IF EXISTS %s" % CONSTRAINT
    )
    cr.execute(
        "DELETE FROM ir_model_data "
        "WHERE model = 'ir.model.constraint' AND module = 'afr_qualificacao' "
        "AND name = %s",
        ("constraint_" + CONSTRAINT,),
    )
    cr.execute("DELETE FROM ir_model_constraint WHERE name = %s", (CONSTRAINT,))

    cr.execute("UPDATE afr_qualificacao_procedimento SET is_default = FALSE")
    cr.execute(
        """
        UPDATE afr_qualificacao_procedimento SET is_default = TRUE
        WHERE id IN (
            SELECT DISTINCT ON (equipment_category_id, company_id) id
            FROM afr_qualificacao_procedimento
            ORDER BY equipment_category_id, company_id, active DESC, id
        )
        """
    )
