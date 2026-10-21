# -*- coding: utf-8 -*-
"""Rateio de um tempo-alvo (horas) entre linhas — matemática pura, sem ORM.

Mesmo espírito de `price_allocation.allocate_target`: parte-se do total
combinado e distribui-se proporcionalmente ao peso atual de cada linha
(horas da linha = nº ciclos × horas/ciclo). As horas de cada linha saem em
múltiplos de `step` (0,25 h) e o resíduo vai para a linha de maior peso,
garantindo soma exata. Se o próprio alvo não for múltiplo de `step`, só a
linha de resíduo fica fora da grade.
"""

import math


def _round6(value):
    return round(value + 0.0, 6)


def allocate_hours(target_hours, weights, step=0.25):
    """Distribui `target_hours` entre `weights`.

    :param target_hours: horas totais desejadas
    :param weights: list[float] — peso atual de cada linha (horas)
    :param step: grade das horas por linha
    :return: list[float] do mesmo tamanho de `weights`, soma == target_hours
    """
    if not weights:
        return []
    n = len(weights)
    total_w = sum(w for w in weights if w > 0)
    if total_w <= 0:
        ws = [1.0] * n
        total_w = float(n)
    else:
        ws = [max(w, 0.0) for w in weights]

    # Shares na grade (HALF-UP em unidades de step).
    shares = [
        math.floor(target_hours * w / total_w / step + 0.5) * step
        for w in ws
    ]
    residual = target_hours - sum(shares)
    biggest = max(range(n), key=lambda i: ws[i])
    shares[biggest] += residual
    return [_round6(max(s, 0.0)) for s in shares]
