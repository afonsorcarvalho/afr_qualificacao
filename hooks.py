"""Module install hooks (post_init).

post_init_hook roda APENAS no install inicial — NÃO em upgrades.
Permite que dados seed (template de proposta) sejam criados uma vez
e o utilizador possa editar/eliminar sem que voltem em upgrades futuros.

Para dados que devem permanecer atualizáveis (sections, opcionais, etc.),
manter em data/*.xml com noupdate="1".
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


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


PARTE_01_NAME = "Parte 01"

# Produtos serviço genéricos por tipo (preço 0; comercial ajusta no
# orçamento). Tuple: (xmlid_suffix, nome, has_parte).
QUALIF_SERVICE_PRODUCTS = {
    "installation": ("product_qi_service", "Qualificação de Instalação (QI)", True),
    "operational": ("product_qo_service", "Qualificação de Operação (QO)", True),
    "software": ("product_qs_service", "Qualificação de Software (QS)", False),
}


def _parte_variant(template, value_name):
    """Retorna o product.product do template cujo valor de atributo Parte == value_name."""
    for variant in template.product_variant_ids:
        names = variant.product_template_variant_value_ids.mapped("name")
        if value_name in names:
            return variant
    _logger.warning(
        "Parte variant '%s' não encontrado no template %s — usando variante padrão.",
        value_name, template.display_name,
    )
    return template.product_variant_id  # fallback (sem atributo)


def _install_qualif_type_configs(env):
    """Garante produtos serviço + type.config p/ QI, QO e QS no install.

    QI e QO recebem o atributo 'Parte' (Parte 01 / Parte 02) → 2 variantes cada.
    type_config installation/operational apontam para o variante Parte 01.

    Idempotente e multi-company: só cria o que falta. Em DBs que já têm os
    registros (labquali configurado manualmente), não faz nada — preserva
    a customização. Roda só no install (post_init), nunca em upgrade, logo
    nunca colide com a constraint unique(qualification_type, company_id).
    """
    Template = env["product.template"]
    TypeConfig = env["afr.qualificacao.type.config"]
    ImdData = env["ir.model.data"]
    attr = env.ref("afr_qualificacao.product_attribute_parte", raise_if_not_found=False)
    val01 = env.ref("afr_qualificacao.product_attribute_value_parte_01", raise_if_not_found=False)
    val02 = env.ref("afr_qualificacao.product_attribute_value_parte_02", raise_if_not_found=False)

    tmpl_by_type = {}
    for qtype, (suffix, name, has_parte) in QUALIF_SERVICE_PRODUCTS.items():
        tmpl = env.ref(f"afr_qualificacao.{suffix}", raise_if_not_found=False)
        if not tmpl:
            tmpl = Template.create({
                "name": name,
                "type": "service",
                "detailed_type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "list_price": 0.0,
            })
            ImdData.create({
                "name": suffix,
                "module": "afr_qualificacao",
                "model": "product.template",
                "res_id": tmpl.id,
                "noupdate": True,
            })
        # Adiciona atributo Parte se ainda não tiver e o atributo seed existe.
        if has_parte and attr and val01 and val02 and not tmpl.attribute_line_ids.filtered(
            lambda l: l.attribute_id == attr
        ):
            tmpl.write({"attribute_line_ids": [(0, 0, {
                "attribute_id": attr.id,
                "value_ids": [(6, 0, [val01.id, val02.id])],
            })]})
        tmpl_by_type[qtype] = tmpl

    # type.config por empresa. active_test=False p/ não recriar sobre um
    # registro inativo e violar a constraint unique.
    for company in env["res.company"].search([]):
        for qtype in ("installation", "operational", "software"):
            has_parte = QUALIF_SERVICE_PRODUCTS[qtype][2]
            exists = TypeConfig.with_context(active_test=False).search([
                ("qualification_type", "=", qtype),
                ("company_id", "=", company.id),
            ], limit=1)
            if exists:
                # software (sem Parte): preserva a config existente como antes.
                if not has_parte:
                    continue
                # installation/operational: em DBs upgradeadas de <16.0.5.9.0,
                # a config existente aponta para o produto QI/QO ANTIGO (sem
                # atributo Parte / sem variantes). Garante que passa a apontar
                # para a variante Parte 01 DO PRODUTO JÁ CONFIGURADO (preserva
                # o produto/pricing do utilizador em vez de trocar pelo seed).
                _ensure_parte_repoint(exists, attr, val01, val02)
                continue
            tmpl = tmpl_by_type[qtype]
            product = _parte_variant(tmpl, PARTE_01_NAME) if has_parte else tmpl.product_variant_id
            TypeConfig.create({
                "qualification_type": qtype,
                "company_id": company.id,
                "service_product_id": product.id,
                "default_unit_price": 0.0,
                "estimated_hours": 0.0,
            })


def _ensure_parte_repoint(cfg, attr, val01, val02):
    """Garante que um type_config installation/operational existente aponte
    para a variante 'Parte 01' do produto que ele JÁ usa.

    Preserva o produto/pricing configurado pelo utilizador: anexa o atributo
    'Parte' ao template já apontado (se faltar) — criando as 2 variantes — e
    repoint a config para a variante Parte 01 desse mesmo template.

    Idempotente: se a config já aponta para uma variante Parte 01, não faz
    nada. Seguro se attr/val01/val02 ou o produto não estiverem disponíveis.
    """
    if not (attr and val01 and val02):
        return
    product = cfg.service_product_id
    if not product:
        return
    # Já é uma variante Parte 01 → nada a fazer.
    if PARTE_01_NAME in product.product_template_variant_value_ids.mapped("name"):
        return
    existing_tmpl = product.product_tmpl_id
    if not existing_tmpl:
        return
    # Anexa o atributo Parte ao template já configurado, se ainda não tiver.
    # IMPORTANTE: este write regenera as variantes (create_variant='always'),
    # arquivando a variante sem-atributo. Só depois resolvemos a Parte 01.
    if not existing_tmpl.attribute_line_ids.filtered(
        lambda l: l.attribute_id == attr
    ):
        existing_tmpl.write({"attribute_line_ids": [(0, 0, {
            "attribute_id": attr.id,
            "value_ids": [(6, 0, [val01.id, val02.id])],
        })]})
    cfg.service_product_id = _parte_variant(existing_tmpl, PARTE_01_NAME)


# Backward-compat alias — mantém imports existentes funcionando.
_install_qi_qs_type_config = _install_qualif_type_configs


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

    # Seed QI/QO/QS type.config (independente do template; idempotente).
    _install_qualif_type_configs(env)

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
