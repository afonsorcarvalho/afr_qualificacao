# -*- coding: utf-8 -*-
"""Pre-migration 16.0.6.0.0 — pivot procedimento (tipo×categoria → 1/categoria).

labquali está em DEV: limpamos os procedimentos antigos (formato
applicable_qualification_type × categoria) e seus itens, para que a nova
constraint unique(equipment_category_id, company_id) instale limpa. Re-seed
é manual pós-upgrade. NÃO usar em produção sem trocar por merge real tipo→fase.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DELETE FROM afr_qualificacao_procedimento_item")
    cr.execute("DELETE FROM afr_qualificacao_procedimento")
