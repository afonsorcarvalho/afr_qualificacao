{
    "name": "AFR Qualificação",
    "version": "16.0.3.1.0",
    "category": "Maintenance",
    "license": "LGPL-3",
    "author": "AFR Sistemas",
    "website": "https://www.afrsistemas.com.br",
    "summary": (
        "Gerencia qualificações (QI/QO/QD/QS/Calibração) com OS própria, "
        "fluxo comercial quote-first e certificado público verificável (QR + hash)."
    ),
    "description": """
        AFR Qualificação — OS própria + Quote-First + Certificado Digital Verificável

        Roadmap 16.0.3.x:
          F1 (16.0.3.0.0): OS própria afr.qualificacao.os (container) + relatórios
            parciais + workflow draft→scheduled→in_progress→in_approved→approved→done.
            Grupo Técnico isolado.
          F2 (16.0.3.1.0): Quote-first cutover (SO confirm cria OS em vez de engc.os).
          F3 (16.0.3.2.0): Procedimento template + collect.items unificados.
          F4 (16.0.3.3.0): Padrões metrológicos M2M (engc.calibration.instruments).
          F5 (16.0.3.4.0): Reports completos + record rules technician.
          F6 (futuro):     DOCX por procedimento (consolidação de coletas/fotos).

        Fluxo:
        1. Comercial cria orçamento (sale.order) e abre Configurador
        2. Wizard fullscreen monta matriz equipamento × tipo qualif
        3. Apply gera linhas SO marcadas (is_qualificacao_managed)
        4. Cliente aprova via portal/email
        5. SO confirm gera afr.qualificacao.os (1/SO, agregando) + qualifs (F2+)
        6. Técnico abre OS, executa relatórios parciais, coleta evidências
        7. Aprovação OS cascateia para qualifs → emissão certificados
        8. Fatura via fluxo Odoo padrão
        9. Cliente verifica certificado em /qualificacao/verify/<token>

        Certificado: SHA-256 do snapshot técnico + UUID4 token + QR pública.
        Calib usa report nativo engc.calibration (extensão por inherit).
    """,
    "depends": [
        "base",
        "mail",
        "hr",
        "engc_os",
        "sale_management",
        "account",
        "website",
        "portal",
    ],
    "data": [
        # Security
        "security/qualificacao_groups.xml",
        "security/ir.model.access.csv",
        # Data seeds
        "data/sequences.xml",
        "data/sensor_kind_seed.xml",
        "data/standard_seed.xml",
        # Views — config (master data) com actions
        "views/sensor_kind_views.xml",
        "views/standard_views.xml",
        "views/cycle_type_views.xml",
        "views/malha_type_views.xml",
        "views/config_template_views.xml",
        "views/qualificacao_type_config_views.xml",
        # Views — operação (actions registradas antes do menu)
        "views/qualificacao_os_relatorio_views.xml",
        "views/qualificacao_os_views.xml",
        "views/qualificacao_views.xml",
        "views/sale_order_views.xml",
        "views/engc_os_views.xml",
        "views/certificate_verify_templates.xml",
        # Wizards
        "wizards/qualificacao_configurator_views.xml",
        "wizards/relatorio_wizard_views.xml",
        # Menus (carregar antes de views que referenciam menu_root como parent)
        "views/qualificacao_menus.xml",
        # Views com menuitem que referencia menu_root (depois dos menus principais)
        "views/docx_template_views.xml",
        # Reports
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
