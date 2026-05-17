{
    "name": "AFR Qualificação",
    "version": "16.0.2.2.2",
    "category": "Maintenance",
    "license": "LGPL-3",
    "author": "AFR Sistemas",
    "website": "https://www.afrsistemas.com.br",
    "summary": (
        "Gerencia qualificações (QI/QO/QD/QS/Calibração) com fluxo "
        "comercial quote-first + certificado público verificável (QR + hash)."
    ),
    "description": """
        AFR Qualificação — Fluxo Quote-First + Certificado Digital Verificável

        Fluxo:
        1. Comercial cria orçamento (sale.order) e abre Configurador
        2. Wizard fullscreen monta matriz equipamento × tipo qualif
        3. Apply gera linhas SO marcadas (is_qualificacao_managed)
        4. Cliente aprova via portal/email
        5. SO confirm gera engc.os (1/equip) + afr.qualificacao (1/equip×tipo)
        6. Técnico executa em campo (cycles/malhas explodidos)
        7. Aprovação propaga qty_delivered + emite certificado (hash+token+QR)
        8. Fatura via fluxo Odoo padrão
        9. Cliente verifica certificado em /qualificacao/verify/<token>

        Certificado: SHA-256 do snapshot técnico + UUID4 token + QR pública.
        Calib usa report nativo engc.calibration (extensão por inherit).
    """,
    "depends": [
        "base",
        "mail",
        "engc_os",
        "sale_management",
        "account",
        "website",
        "portal",
    ],
    "data": [
        "security/qualificacao_groups.xml",
        "security/ir.model.access.csv",
        "data/sensor_kind_seed.xml",
        "data/standard_seed.xml",
        "views/sensor_kind_views.xml",
        "views/standard_views.xml",
        "views/cycle_type_views.xml",
        "views/malha_type_views.xml",
        "views/config_template_views.xml",
        "views/qualificacao_type_config_views.xml",
        "views/qualificacao_views.xml",
        "views/sale_order_views.xml",
        "views/engc_os_views.xml",
        "views/certificate_verify_templates.xml",
        "wizards/qualificacao_configurator_views.xml",
        "views/qualificacao_menus.xml",
        "views/docx_template_views.xml",
        "reports/qualificacao_certificate_template.xml",
        "reports/qualificacao_certificate_report.xml",
        "reports/calibration_certificate_inherit.xml",
        "reports/quotation_template.xml",
    ],
    "external_dependencies": {
        "python": [
            "docxtpl",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
