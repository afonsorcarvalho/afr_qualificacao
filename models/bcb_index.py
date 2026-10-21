# -*- coding: utf-8 -*-
"""Índices de preço do Banco Central (API SGS) — acumulado 12 meses.

Padrão HTTP do `afr_brasil_lookup`: `urllib.request`, timeout 10 s, erros
convertidos em `UserError` amigável. `_http_get_json` é o ponto de mock
dos testes.
"""
import calendar
import json
import urllib.error
import urllib.request
from datetime import date

from odoo import _
from odoo.exceptions import UserError

HTTP_TIMEOUT = 10
SGS_URL = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.%(serie)s/dados"
           "?formato=json&dataInicial=%(ini)s&dataFinal=%(fim)s")
SERIES = {"ipca": 433, "igpm": 189, "inpc": 188}


def _http_get_json(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "afr_qualificacao/16.0"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise UserError(_("Erro HTTP %s ao consultar o Banco Central.")
                        % e.code) from e
    except (urllib.error.URLError, OSError) as e:
        raise UserError(_("Falha de rede ao consultar o Banco Central.")) from e
    except ValueError as e:
        raise UserError(_("Resposta inválida do Banco Central.")) from e


def period_12m(ref_month):
    """(início, fim) dos 12 meses que terminam no mês anterior a `ref_month`."""
    y, m = ref_month.year, ref_month.month - 1
    if m == 0:
        y, m = y - 1, 12
    fim = date(y, m, calendar.monthrange(y, m)[1])
    ini = date(y, 1, 1) if m == 12 else date(y - 1, m + 1, 1)
    return ini, fim


def accumulated_12m(serie, ref_month):
    """Acumulado (%) = Π(1+v/100)−1 das 12 variações mensais da série."""
    ini, fim = period_12m(ref_month)
    data = _http_get_json(SGS_URL % {
        "serie": serie, "ini": ini.strftime("%d/%m/%Y"),
        "fim": fim.strftime("%d/%m/%Y")})
    try:
        valores = [float(str(d["valor"]).replace(",", ".")) for d in data]
    except (TypeError, KeyError, ValueError) as e:
        raise UserError(_("Resposta inválida do Banco Central.")) from e
    if len(valores) != 12:
        raise UserError(_(
            "O Banco Central ainda não publicou os 12 meses do período "
            "(%(n)s de 12).") % {"n": len(valores)})
    fator = 1.0
    for v in valores:
        fator *= 1 + v / 100.0
    return (fator - 1) * 100.0
