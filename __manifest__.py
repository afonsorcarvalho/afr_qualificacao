{
    "name": "AFR Qualificação",
    "version": "16.0.5.4.0",
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
          F6.1 (16.0.3.5.0): Relatório DOCX individual por qualif (QI/QO/QD/QS)
            com templates default por tipo + mapeamento docx_section por
            procedimento.item. Render via docxtpl, contexto rico (cliente,
            equipamento, instrumentos, tabelas agrupadas por seção).
          F6.2 (futuro):   DOCX UNIFICADO por OS (agrega QI+QO+QD).
          F6.3 (futuro):   Conversão DOCX → PDF (LibreOffice headless).
          F8 (16.0.4.x): Proposta LEGO — builder de cotação. Catálogos de
            templates de equipamento (cycle/malha com specs técnicas + preço)
            + biblioteca de blocos de texto reutilizáveis montados por
            proposta.
            F8.1 (16.0.4.0.0): camada de dados (catálogos + section/template/
              optional + seeds).
            F8.2 (16.0.4.1.0): builder — wizard escolhe template de
              equipamento + opcionais; sale.order ganha proposal_template_id
              + blocos lego editáveis (afr.proposal.block).
            F8.3 (16.0.4.2.0): report percorre proposal_block_ids — blocos
              static renderizados com {{ tokens }} (inline_template) +
              blocos dinâmicos (escopo/ciclos/normas/financeiro/opcionais/
              aceite). Fallback para layout fixo quando sem blocos.
            F8.4 (16.0.4.3.0): configurador guiado multi-step — Escopo →
              Opcionais → Blocos → Revisão, com navegação Voltar/Próximo.
            F8.5 (16.0.4.4.0): botão "Editar" por bloco (modal). Bloco
              dinâmico é convertido por snapshot — conteúdo auto-gerado
              congelado em HTML editável (vira static).
            F8.6 (16.0.4.5.0): quebra de página por bloco (page_break) —
              flag vem do template.line, copiada para o bloco; default
              continua na mesma página.
            F8.7 (16.0.4.6.0): passos do configurador reordenados (Blocos
              antes de Opcionais); título do bloco editável no template
              (template.line.title) — usado no relatório.
            F8.8 (16.0.4.7.0): escopo detalhado — ciclos QO (sem carga)
              modelados igual aos QD (cycle_type + qty por linha SO);
              tabelas QO + QD inline dentro do Equipment Scope; execução
              tracka ciclos QO em afr.qualificacao.cycle; seed de
              cycle_types comuns por equipamento.
            F8.9 (16.0.4.8.0): seeds de categorias de equipamento +
              malhas (Temp/Press/Umidade) + linka cycle_types às
              categorias + template "Pacote Autoclave a Vapor" pronto
              (QI+QO+QD+ciclos+malhas+preço sugerido).
            F8.10 (16.0.4.9.0): refinamento Equipment Scope — remove
              subtotal por equipamento (preço só no Resumo Financeiro);
              calib renderiza como "0N Calibração de <malha>".
            F8.11 (16.0.4.10.0): description + unit_price editáveis nas
              sublines QO/QD/Calib do configurador (default ← product.name
              / list_price); description vira `name` da linha SO,
              unit_price vira `price_unit`. Bulk "Adicionar Vários" ganha
              aba Ciclos QO. Aba "Optional Products" do sale_management
              escondida (não usada).
            F8.12 (16.0.4.11.0): cycle_type + malha_type ganham
              `default_unit_price` (override product.list_price para
              precificação ciclo-a-ciclo). Onchange/autofill sublines usa
              `default_unit_price or product.list_price`. Removido
              checkbox `do_qo` do equipment_line + bulk wizard (presença
              de qo_line_ids = aplicar QO; fallback type.config descontinuado).
              ACL faltante adicionada para `afr.qualificacao.configurator.bulk.qo`.
            F8.13 (16.0.4.12.0): templates de equipamento ganham
              `description` (Char) por linha QO/QD/Calib. Autofill do
              configurador usa template description antes do product.name
              como default da subline. Permite cadastrar descrição rica
              uma vez no template e reaproveitar em todas as cotações.
            F8.13.1 (16.0.4.12.1): 3 baselines pre-existing F8.6-F8.10
              corrigidas. test_seed_default_template_loaded espera 17
              linhas (cycle_specs removido F8.8). test_snapshot_cycle_specs
              + test_render_cycle_specs_block injetam template line
              cycle_specs dinamicamente em setUpClass. 225/0/0 PASS.
            F8.14 (16.0.4.13.0): cronograma estimado — estimated_hours
              em cycle_type/malha_type/type.config + override no
              template/configurator/SO line. Helpers _qualif_estimated_hours,
              _qualif_estimated_days (hours/8), _qualif_schedule_rows,
              _qualif_section_hours. PDF: tfoot subtotal em tabelas QO/QD
              do Equipment Scope, rodapé "Cronograma estimado: N dias úteis"
              por equipamento, novo block_kind='schedule' opcional com
              tabela equipamento × horas × dias.
            F8.15 (16.0.4.14.0): refinamento Escopo + Tabela Resumo.
              Tabelas QO/QD/cycle_specs reordenam cols (Ciclo|Qtd antes
              de Temperatura); col "Tempo" renomeada "Tempo Esteril";
              nova col "Tempo Estimado" (= cycle.estimated_hours × qty).
              tfoot Total: <qty> ciclo(s) (sum qty independente de tipo)
              + horas/dias. Ordem das seções no Equipment Scope reordenada
              (QUALIF_TYPE_LABELS): QI → Calibração → QO → QD → QS.
            F8.16 (16.0.4.15.0): Equipment Scope sem tabelas inline
              QO/QD (dados duplicados removidos — tabela única em "Tabela
              Resumo de Ciclos"). Bullets QO/QD exibem ciclo + qtd +
              temperatura + tempo esteril. Labels QUALIF_TYPE_LABELS
              padronizadas sem abreviação parentética. cycle_specs
              default title → "Tabela Resumo de Ciclos". CSS margin
              entre seções aumentada.

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
        "afr_labquali_layout",
    ],
    "data": [
        # Security
        "security/qualificacao_groups.xml",
        "security/ir.model.access.csv",
        # Data seeds
        "data/sequences.xml",
        "data/sensor_kind_seed.xml",
        "data/standard_seed.xml",
        "data/docx_templates_seed.xml",
        # F10 — papéis metrológicos (VALIDADOR/PADRAO) p/ o plano de recursos
        "data/instrument_function_seed.xml",
        # F8.9 — categorias de equipamento (engc.equipment.category)
        "data/equipment_category_seed.xml",
        # F8.9 — malhas comuns (Temp/Press/Umidade)
        "data/malha_type_seed.xml",
        # F8.8 — ciclos comuns por equipamento (linkados às categorias)
        "data/cycle_type_seed.xml",
        # F8.9 — templates de equipamento prontos (Pacote Autoclave a Vapor)
        "data/config_template_seed.xml",
        # F8.1 — Proposta LEGO: blocos e templates (section antes de template)
        # NOTA F9.2: proposal_template_seed.xml removido daqui — migrado para
        # post_init_hook (hooks._install_proposal_template_seed) para que o
        # template default seja criado APENAS no install. Updates do módulo
        # não recriam linhas eliminadas pelo utilizador.
        "data/proposal_section_seed.xml",
        "data/proposal_optional_seed.xml",
        # F9.3 — Email template LabQuali para envio de proposta
        "data/mail_template_proposal.xml",
        # Views — config (master data) com actions
        "views/sensor_kind_views.xml",
        "views/standard_views.xml",
        "views/cycle_type_views.xml",
        "views/malha_type_views.xml",
        "views/config_template_views.xml",
        # F8.1 — Proposta LEGO: views master data (actions; menus em qualificacao_menus.xml)
        "views/proposal_section_views.xml",
        "views/proposal_optional_views.xml",
        "views/proposal_template_views.xml",
        "views/proposal_block_views.xml",
        "views/qualificacao_type_config_views.xml",
        "views/qualificacao_procedimento_views.xml",
        # Views — operação (actions registradas antes do menu)
        "views/qualificacao_collect_item_views.xml",
        "views/qualificacao_subrecords_views.xml",
        "views/qualificacao_os_relatorio_views.xml",
        "views/qualificacao_os_views.xml",
        "views/qualificacao_views.xml",
        "views/sale_order_views.xml",
        # F10.5 — equipamento focado em Qualificação + menu em Vendas
        "views/engc_equipment_views.xml",
        # F9.4 — Cotação online LabQuali (portal)
        "views/sale_order_portal_template.xml",
        "views/engc_os_views.xml",
        "views/certificate_verify_templates.xml",
        "views/res_config_settings_views.xml",
        # Wizards
        "wizards/qualificacao_configurator_views.xml",
        "wizards/relatorio_wizard_views.xml",
        "wizards/apply_procedimento_wizard_views.xml",
        # Menus (carregar antes de views que referenciam menu_root como parent)
        "views/qualificacao_menus.xml",
        "views/calibration_instruments_views.xml",
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
    # F9.4 — SCSS da cotação online LabQuali (portal)
    "assets": {
        "web.assets_frontend": [
            "afr_qualificacao/static/src/scss/sale_portal_qualif.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    # F9.2 — template seed só no install (não recria deleções em updates)
    "post_init_hook": "_install_proposal_template_seed",
}
