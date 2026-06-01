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


# Produtos serviço genéricos por tipo (preço 0; comercial ajusta no
# orçamento). Idempotente via xmlid. (xmlid_suffix, nome).
QI_QS_SERVICE_PRODUCTS = {
    "installation": ("product_qi_service", "Qualificação de Instalação (QI)"),
    "software": ("product_qs_service", "Qualificação de Software (QS)"),
}


def _install_qi_qs_type_config(env):
    """Garante produtos serviço + type.config p/ QI e QS no install.

    O configurador (action_apply) levanta UserError se não houver
    afr.qualificacao.type.config para 'installation'/'software' na empresa
    — quebrando fresh-installs/deploys que não têm os dados cadastrados à
    mão (como o labquali tem). Este seed cria o mínimo viável (produto
    preço 0 + config por empresa) para o configurador funcionar.

    Idempotente e multi-company: só cria o que falta. Em DBs que já têm os
    registros (labquali configurado manualmente), não faz nada — preserva
    a customização. Roda só no install (post_init), nunca em upgrade, logo
    nunca colide com a constraint unique(qualification_type, company_id).
    """
    Product = env["product.product"]
    TypeConfig = env["afr.qualificacao.type.config"]
    ImdData = env["ir.model.data"]

    prod_by_type = {}
    for qtype, (xmlid_suffix, name) in QI_QS_SERVICE_PRODUCTS.items():
        prod = env.ref(
            f"afr_qualificacao.{xmlid_suffix}", raise_if_not_found=False
        )
        if not prod:
            prod = Product.create({
                "name": name,
                "type": "service",
                "detailed_type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 0.0,
            })
            ImdData.create({
                "name": xmlid_suffix,
                "module": "afr_qualificacao",
                "model": "product.product",
                "res_id": prod.id,
                "noupdate": True,
            })
        prod_by_type[qtype] = prod

    # type.config por empresa. active_test=False p/ não recriar sobre um
    # registro inativo e violar a constraint unique.
    for company in env["res.company"].search([]):
        for qtype in ("installation", "software"):
            exists = TypeConfig.with_context(active_test=False).search([
                ("qualification_type", "=", qtype),
                ("company_id", "=", company.id),
            ], limit=1)
            if exists:
                continue
            TypeConfig.create({
                "qualification_type": qtype,
                "company_id": company.id,
                "service_product_id": prod_by_type[qtype].id,
                "default_unit_price": 0.0,
                "estimated_hours": 0.0,
            })


def _ensure_company_data_block(env):
    """Garante o bloco institucional 'Dados Cadastrais' no template QI/QO/QD.

    Idempotente: acrescenta 1 linha static (seção SEC-DADOS-CADASTRAIS) ao
    template proposal_template_labquali se ainda não existir, posicionada
    logo antes do bloco de aceite (ou ao final, se não houver aceite).
    Chamado pelo post_init (fresh-install) e pela migration 16.0.5.7.0
    (upgrade na labquali).
    """
    section = env.ref(
        "afr_qualificacao.sec_dados_cadastrais", raise_if_not_found=False
    )
    template = env.ref(
        "afr_qualificacao.proposal_template_labquali", raise_if_not_found=False
    )
    if not section or not template:
        return
    if template.line_ids.filtered(lambda l: l.section_id == section):
        return  # já tem
    used = set(template.line_ids.mapped("sequence"))
    acceptance = template.line_ids.filtered(
        lambda l: l.block_kind == "acceptance"
    )
    if acceptance:
        seq = min(acceptance.mapped("sequence")) - 1
    else:
        seq = max(used or [0]) + 10
    # evita colisão de sequence (ordem determinística: _order = sequence, id)
    while seq in used:
        seq -= 1
    env["afr.proposal.template.line"].create({
        "template_id": template.id,
        "sequence": seq,
        "block_kind": "static",
        "section_id": section.id,
    })


def _install_proposal_template_seed(cr, registry):
    """Cria o template default ‘Proposta LabQuali QI/QO/QD’ no install.

    Idempotente: se o xmlid já existe, retorna sem fazer nada.
    Registra ir.model.data com noupdate=True para que env.ref() funcione
    em código (tests, futuros hooks) mas updates do módulo não recriem
    nem modifiquem o template — utilizador controla 100%.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Seed QI/QS type.config (independente do template; idempotente).
    _install_qi_qs_type_config(env)

    template = env.ref(
        "afr_qualificacao.proposal_template_labquali",
        raise_if_not_found=False,
    )
    if template:
        _ensure_company_data_block(env)  # retrofit em template já existente
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

    # Bloco institucional Dados Cadastrais (após template recém-criado).
    _ensure_company_data_block(env)
