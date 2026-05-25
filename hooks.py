"""Module install hooks (post_init).

post_init_hook roda APENAS no install inicial — NÃO em upgrades.
Permite que dados seed (template de proposta) sejam criados uma vez
e o utilizador possa editar/eliminar sem que voltem em upgrades futuros.

Para dados que devem permanecer atualizáveis (sections, opcionais, etc.),
manter em data/*.xml com noupdate="1".
"""

from odoo import api, SUPERUSER_ID


# Estrutura do template default "Proposta LabQuali QI/QO/QD".
# Tuple por linha: (xmlid_suffix, sequence, block_kind, section_xmlid|None,
#                   page_break, parent_xmlid_suffix|None)
PROPOSAL_TEMPLATE_LINES = [
    ("l01", 10, "static", "proposal_section_objetivo", True, None),
    ("l02", 20, "static", "proposal_section_metodologia", False, None),
    ("l02b", 25, "static", "proposal_section_qualif_termica", False, None),
    ("l03", 30, "static", "proposal_section_qi", False, "l02b"),
    ("l04", 40, "static", "proposal_section_qo", False, "l02b"),
    ("l05", 50, "static", "proposal_section_qd", False, "l02b"),
    ("l06", 60, "equipment_scope", None, True, None),
    ("l08", 80, "static", "proposal_section_validadores", False, None),
    ("l09", 90, "standards_table", None, False, None),
    ("l10", 100, "static", "proposal_section_normas", False, None),
    ("l11", 110, "static", "proposal_section_entregaveis", False, None),
    ("l12", 120, "financial", None, True, None),
    ("l13", 130, "optionals", None, False, None),
    ("l14", 140, "static", "proposal_section_responsabilidades", False, None),
    ("l15", 150, "static", "proposal_section_condicoes", False, None),
    ("l16", 160, "static", "proposal_section_credenciais", False, None),
    ("l17", 170, "acceptance", None, True, None),
    ("l18", 180, "static", "proposal_section_aceite", False, None),
]


def _install_proposal_template_seed(cr, registry):
    """Cria o template default ‘Proposta LabQuali QI/QO/QD’ no install.

    Idempotente: se o xmlid já existe, retorna sem fazer nada.
    Registra ir.model.data com noupdate=True para que env.ref() funcione
    em código (tests, futuros hooks) mas updates do módulo não recriem
    nem modifiquem o template — utilizador controla 100%.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    template = env.ref(
        "afr_qualificacao.proposal_template_labquali",
        raise_if_not_found=False,
    )
    if template:
        return  # já instalado

    Template = env["afr.proposal.template"]
    TemplateLine = env["afr.proposal.template.line"]
    ImdData = env["ir.model.data"]

    # 1) Template
    template = Template.create({
        "name": "Proposta LabQuali QI/QO/QD",
        "code": "TPL-LABQUALI",
        "sequence": 10,
    })
    ImdData.create({
        "name": "proposal_template_labquali",
        "module": "afr_qualificacao",
        "model": "afr.proposal.template",
        "res_id": template.id,
        "noupdate": True,
    })

    # 2) Linhas — 1ª passagem: criar todas sem parent_id
    suffix_to_line = {}
    for suffix, seq, kind, section_xmlid, page_break, _parent in PROPOSAL_TEMPLATE_LINES:
        section = (
            env.ref(f"afr_qualificacao.{section_xmlid}", raise_if_not_found=False)
            if section_xmlid else False
        )
        line = TemplateLine.create({
            "template_id": template.id,
            "sequence": seq,
            "block_kind": kind,
            "section_id": section.id if section else False,
            "page_break": page_break,
        })
        ImdData.create({
            "name": f"proposal_template_labquali_{suffix}",
            "module": "afr_qualificacao",
            "model": "afr.proposal.template.line",
            "res_id": line.id,
            "noupdate": True,
        })
        suffix_to_line[suffix] = line

    # 3) 2ª passagem — propagar parent_id (hierarquia)
    for suffix, _seq, _kind, _section, _pb, parent_suffix in PROPOSAL_TEMPLATE_LINES:
        if parent_suffix:
            parent = suffix_to_line.get(parent_suffix)
            if parent:
                suffix_to_line[suffix].parent_id = parent.id
