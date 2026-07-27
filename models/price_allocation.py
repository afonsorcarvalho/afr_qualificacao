# -*- coding: utf-8 -*-
"""Rateio de um preço-alvo entre linhas de venda — matemática pura, sem ORM.

O processo é o inverso da precificação normal: em vez de somar subtotais para
achar o total, parte-se do total negociado e distribui-se proporcionalmente ao
subtotal atual de cada linha, back-calculando o `price_unit`.

Restrição central: `price_unit` tem 2 casas decimais (precisão global "Product
Price") e as quantidades são horas fracionárias. Um centavo no `price_unit` de
uma linha de 7,5h move o subtotal R$ 0,075 → nem todo alvo é alcançável mexendo
numa linha só. Daí a busca combinada em `_search_residual`.

Todo arredondamento é HALF-UP (moeda), nunca o banker's rounding do `round()`.
"""

from odoo.tools import float_round

# Quantas linhas a busca combinada pode ajustar, e em quantos centavos.
_SEARCH_MAX_LINES = 3
_SEARCH_MAX_CENTS = 20


def _round(value, digits=2):
    return float_round(value, precision_digits=digits, rounding_method="HALF-UP")


def subtotal_for(qty, price_unit, digits=2):
    """Subtotal previsto de uma linha, com o mesmo arredondamento do Odoo."""
    return _round(qty * price_unit, digits)


def allocate_target(target, lines, digits=2):
    """Distribui `target` entre `lines` proporcionalmente ao subtotal atual.

    :param target: total desejado (sem impostos)
    :param lines: list[(qty, subtotal_atual)]
    :param digits: casas decimais da moeda
    :return: dict(price_units=list[float], achieved=float, exact=bool)
    """
    if not lines:
        return {"price_units": [], "achieved": 0.0, "exact": False}

    base = sum(sub for _qty, sub in lines)
    if not base:
        return {"price_units": [], "achieved": 0.0, "exact": False}

    # 1. Shares proporcionais, arredondados; resíduo na maior linha.
    shares = [_round(target * sub / base, digits) for _qty, sub in lines]
    residual = _round(target - sum(shares), digits)
    biggest = max(range(len(lines)), key=lambda i: lines[i][1])
    shares[biggest] = _round(shares[biggest] + residual, digits)

    # 2. Back-calc do price_unit (nunca negativo).
    price_units = []
    for (qty, _sub), share in zip(lines, shares):
        pu = _round(share / qty, digits) if qty else 0.0
        price_units.append(max(pu, 0.0))

    # 3. O arredondamento do price_unit desloca o subtotal — mede o desvio.
    achieved = _round(
        sum(subtotal_for(qty, pu, digits)
            for (qty, _sub), pu in zip(lines, price_units)),
        digits,
    )
    diff = _round(target - achieved, digits)
    if diff:
        adjusted = _search_residual(lines, price_units, diff, digits)
        if adjusted is not None:
            price_units = adjusted
            achieved = _round(
                sum(subtotal_for(qty, pu, digits)
                    for (qty, _sub), pu in zip(lines, price_units)),
                digits,
            )

    return {
        "price_units": price_units,
        "achieved": achieved,
        "exact": not _round(target - achieved, digits),
    }


def _search_residual(lines, price_units, diff, digits=2):
    """Procura ajuste de n centavos no price_unit de até 3 linhas p/ zerar `diff`.

    Puro e em memória: nenhuma escrita no ORM aqui. Devolve a nova lista de
    price_units, ou None se nenhuma combinação fecha.

    As linhas são tentadas da grade mais fina para a mais grossa — a grade de uma
    linha é `qty × 0,01`, o quanto seu subtotal anda por centavo de price_unit.
    """
    step = 10 ** -digits
    order = sorted(range(len(lines)), key=lambda i: lines[i][0])
    candidates = order[:_SEARCH_MAX_LINES]

    def delta_for(idx, cents):
        qty = lines[idx][0]
        novo = _round(price_units[idx] + cents * step, digits)
        if novo < 0.0:
            return None
        return _round(
            subtotal_for(qty, novo, digits)
            - subtotal_for(qty, price_units[idx], digits),
            digits,
        )

    cents_range = [
        c for c in range(-_SEARCH_MAX_CENTS, _SEARCH_MAX_CENTS + 1) if c
    ]

    # 1 linha
    for idx in candidates:
        for cents in cents_range:
            d = delta_for(idx, cents)
            if d is not None and not _round(d - diff, digits):
                out = list(price_units)
                out[idx] = _round(out[idx] + cents * step, digits)
                return out

    # 2 linhas
    for a_pos, a in enumerate(candidates):
        for b in candidates[a_pos + 1:]:
            for ca in cents_range:
                da = delta_for(a, ca)
                if da is None:
                    continue
                for cb in cents_range:
                    db = delta_for(b, cb)
                    if db is None:
                        continue
                    if not _round(da + db - diff, digits):
                        out = list(price_units)
                        out[a] = _round(out[a] + ca * step, digits)
                        out[b] = _round(out[b] + cb * step, digits)
                        return out
    return None
