{
    "name": "AFR Qualificação",
    "version": "16.0.2.0.0",
    "category": "Maintenance",
    "license": "LGPL-3",
    "author": "AFR Sistemas",
    "website": "https://www.afrsistemas.com.br",
    "summary": (
        "Gerencia qualificações (QI/QO/QD/QS/Calibração) com fluxo "
        "comercial quote-first (sale.order → afr.qualificacao + engc.os)."
    ),
    "description": """
        AFR Qualificação — Fluxo Quote-First
        =====================================

        Módulo que gerencia qualificações de equipamentos (QI/QO/QD/QS +
        Calibração metrológica) integrado ao módulo comercial nativo do Odoo.

        Fluxo:
        1. Comercial cria orçamento (sale.order) e abre Configurador
        2. Wizard fullscreen monta matriz equipamento × tipo qualif
        3. Apply gera linhas SO marcadas (is_qualificacao_managed)
        4. Cliente aprova via portal/email
        5. SO confirm gera engc.os (1/equip) + afr.qualificacao (1/equip×tipo)
        6. Técnico executa em campo (cycles/malhas explodidos)
        7. Aprovação propaga qty_delivered → fatura via fluxo Odoo padrão

        Integração engc.calibration: link manual via FK
        (engc_calibration_id + engc_calibration_measurement_id).
    """,
    "depends": [
        "base",
        "mail",
        "engc_os",
        "sale_management",
        "account",
    ],
    "data": [
        "security/qualificacao_groups.xml",
        "security/ir.model.access.csv",
        "data/sensor_kind_seed.xml",
        "views/sensor_kind_views.xml",
        "views/cycle_type_views.xml",
        "views/malha_type_views.xml",
        "views/config_template_views.xml",
        "views/qualificacao_type_config_views.xml",
        "views/qualificacao_views.xml",
        "views/sale_order_views.xml",
        "views/engc_os_views.xml",
        "wizards/qualificacao_configurator_views.xml",
        "views/qualificacao_menus.xml",
        "views/docx_template_views.xml",
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
