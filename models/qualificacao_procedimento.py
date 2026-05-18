# -*- coding: utf-8 -*-
"""Procedimento de Qualificação (template master) + linhas (procedimento.item).

Template pré-programado que define o que deve ser COLETADO em campo durante
a execução de uma qualificação (fotos cargas, dados qualificador, planilhas,
indicadores biológicos, fitas etc.).

Resolve por (applicable_qualification_type + equipment_category_id) com
fallback para apenas tipo. Explosão para collect.items acontece em
sale_order._explode_collect_items() na confirmação do SO (F3 16.0.3.2.0).
"""
from odoo import _, api, fields, models


KIND_SELECTION = [
    ("foto", "Foto"),
    ("excel", "Planilha Excel/CSV"),
    ("pdf", "PDF"),
    ("qualificador_data", "Arquivo do Qualificador (raw)"),
    ("outro", "Outro"),
]

# F4.3: default de requires_instrument conforme natureza do item.
DEFAULT_REQUIRES_INSTRUMENT_BY_KIND = {
    "foto": False,
    "excel": True,
    "pdf": False,
    "qualificador_data": True,
    "outro": False,
}

# F6.1 (16.0.3.5.0): seção do relatório DOCX onde a coleta será listada.
# Os valores correspondem aos blocos de loop esperados pelos templates
# docs/MODELO_QUALIFICACAO_*.docx (e estrutura de docs/exemplo_contexto.json).
DOCX_SECTION_SELECTION = [
    # QI
    ("qi_utilidades", "QI — Utilidades"),
    ("qi_documentos", "QI — Documentos"),
    ("qi_componentes", "QI — Componentes"),
    ("qi_instalacao", "QI — Instalação"),
    ("qi_calibracoes", "QI — Calibrações"),
    ("qi_treinamentos", "QI — Treinamentos"),
    # QO
    ("qo_testes_funcionais", "QO — Testes Funcionais"),
    ("qo_testes_seguranca", "QO — Testes de Segurança"),
    ("qo_mapeamento_ciclo1", "QO — Mapeamento Ciclo 1"),
    ("qo_mapeamento_ciclo2", "QO — Mapeamento Ciclo 2"),
    ("qo_mapeamento_ciclo3", "QO — Mapeamento Ciclo 3"),
    # QD
    ("qd_carga", "QD — Carga"),
    ("qd_penetracao_ciclo1", "QD — Penetração Ciclo 1"),
    ("qd_penetracao_ciclo2", "QD — Penetração Ciclo 2"),
    ("qd_penetracao_ciclo3", "QD — Penetração Ciclo 3"),
    ("qd_indicadores_quimicos", "QD — Indicadores Químicos"),
    ("qd_indicadores_biologicos", "QD — Indicadores Biológicos"),
    ("qd_bowie_dick", "QD — Bowie-Dick"),
    ("qd_repetibilidade", "QD — Repetibilidade"),
    # Catch-all
    ("anexos", "Anexos (genérico)"),
]


class AfrQualificacaoProcedimento(models.Model):
    _name = "afr.qualificacao.procedimento"
    _description = "Procedimento de Qualificação (Template)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, tracking=True)
    code = fields.Char(tracking=True)
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    applicable_qualification_type = fields.Selection(
        [
            ("installation", "QI"),
            ("operational", "QO"),
            ("performance", "QD"),
            ("software", "QS"),
            ("calibration", "Calibração"),
        ],
        required=True,
        string="Tipo aplicável",
        tracking=True,
    )
    equipment_category_id = fields.Many2one(
        "engc.equipment.category",
        string="Categoria do equipamento",
        help="Vazio = aplica a qualquer categoria (fallback). Específica = match preferencial.",
        tracking=True,
    )
    item_ids = fields.One2many(
        "afr.qualificacao.procedimento.item",
        "procedimento_id",
        copy=True,
        string="Itens (esperados)",
    )
    item_count = fields.Integer(compute="_compute_item_count")

    _sql_constraints = [
        (
            "uniq_type_category_company",
            "unique(applicable_qualification_type, equipment_category_id, company_id)",
            "Já existe procedimento ativo para esse tipo + categoria + empresa.",
        ),
    ]

    @api.depends("item_ids")
    def _compute_item_count(self):
        for r in self:
            r.item_count = len(r.item_ids)

    @api.model
    def resolve_for(self, qualification_type, equipment_category):
        """Retorna melhor match para (type + category) ativo.

        Preferência: 1) match exato (type + category) → 2) só type
        (equipment_category_id vazio = fallback genérico). Retorna recordset
        vazio se nenhum.
        """
        domain = [
            ("active", "=", True),
            ("applicable_qualification_type", "=", qualification_type),
        ]
        cat_id = equipment_category.id if equipment_category else False
        if cat_id:
            rec = self.search(
                domain + [("equipment_category_id", "=", cat_id)], limit=1
            )
            if rec:
                return rec
        return self.search(
            domain + [("equipment_category_id", "=", False)], limit=1
        )


class AfrQualificacaoProcedimentoItem(models.Model):
    _name = "afr.qualificacao.procedimento.item"
    _description = "Item do Procedimento (Esperado de Coleta)"
    _order = "procedimento_id, sequence, id"

    procedimento_id = fields.Many2one(
        "afr.qualificacao.procedimento",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    kind = fields.Selection(
        KIND_SELECTION,
        required=True,
        default="foto",
        string="Tipo de mídia",
    )
    required = fields.Boolean(default=True)
    instruction = fields.Text(translate=True, help="Instrução para o técnico em campo.")
    mimetypes_hint = fields.Char(
        string="Mime types sugeridos",
        help="Ex: image/png,image/jpeg,application/pdf (informativo apenas).",
    )
    target_level = fields.Selection(
        [
            ("qualificacao", "Qualificação (1 por qualif)"),
            ("cycle", "Ciclo (1 por ciclo da qualif QD)"),
            ("malha", "Malha (1 por malha da qualif Calib)"),
        ],
        required=True,
        default="qualificacao",
        help="Cycle/malha explodem N collect.items conforme qty da qualif.",
    )

    # F4.3 — Exigência de instrumento padrão
    requires_instrument = fields.Boolean(
        string="Requer padrão metrológico",
        default=lambda self: self._default_requires_instrument(),
        help=(
            "Quando ativo, o collect.item gerado por este template exige que "
            "o técnico associe ao menos um instrumento padrão cobrindo as "
            "grandezas listadas. Default automático por tipo de mídia: "
            "Planilha/Arquivo Qualificador = True; Foto/PDF/Outro = False."
        ),
    )
    required_sensor_kind_ids = fields.Many2many(
        "afr.qualificacao.sensor.kind",
        "afr_proc_item_sensor_kind_rel",
        "procedimento_item_id",
        "sensor_kind_id",
        string="Grandezas requeridas",
        help=(
            "Grandezas que os instrumentos padrão devem cobrir (ex: TEMP, "
            "PRESS). Para itens multi-medida (ex: Dados do Qualificador), "
            "liste todas as grandezas que aparecem no arquivo bruto. Cobertura "
            "do collect.item é validada contra a união das grandezas dos "
            "instrumentos selecionados."
        ),
    )

    # F6.1 (16.0.3.5.0) — seção do relatório DOCX onde o item aparece.
    docx_section = fields.Selection(
        DOCX_SECTION_SELECTION,
        string="Seção no relatório DOCX",
        help=(
            "Classifica em qual tabela do relatório DOCX (QI/QO/QD) o "
            "collect.item gerado a partir deste template será listado. "
            "Vazio = não aparece em tabela específica (aparece em 'anexos' "
            "se for required ou se tiver arquivo). Os valores casam com "
            "os blocos {% for %} dos templates em static/docx/."
        ),
    )

    @api.model
    def _default_requires_instrument(self):
        kind = self.env.context.get("default_kind", "foto")
        return DEFAULT_REQUIRES_INSTRUMENT_BY_KIND.get(kind, False)

    @api.onchange("kind")
    def _onchange_kind_requires_instrument(self):
        for r in self:
            r.requires_instrument = DEFAULT_REQUIRES_INSTRUMENT_BY_KIND.get(
                r.kind, False
            )
