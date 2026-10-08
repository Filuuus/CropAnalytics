"""
Panorama de humedad por celda a partir de la serie diaria del LSTM (2015-2025).

Todos los indicadores son relativos al historial de la propia celda: el LSTM
acierta el momento de humectación y secado, pero no el nivel absoluto, que en
sitios nuevos trae un sesgo constante por el suelo (evaluación en las 6
estaciones TxSON). El índice 0-100 elimina ese sesgo.

Parámetros iniciales; se calibran con las 18 fechas de siembra de temporal y
los rendimientos de los 547 ciclos de temporal del dataset.
"""
from datetime import date, timedelta
from statistics import median

import numpy as np

UMBRAL_INICIO = 50              # índice a partir del cual se considera temporada húmeda
DIAS_SOSTENIDOS = 10            # días seguidos con media de 7 días >= UMBRAL_INICIO
MESES_INICIO = (6, 9)           # el inicio se busca del 1 de junio al 30 de septiembre
UMBRAL_SECO = 30                # índice bajo el cual un día cuenta como seco
DIAS_RACHA_SECA = 10            # racha seca relevante
DIAS_A_FLORACION = 75           # mediana de DFF en los ciclos de temporal del dataset
MEDIA_VENTANA_FLORACION = 15    # floración = inicio + 75 ± 15 días (rango DFF observado 65-88)
VENTANA_BANDAS = 7              # ± días del año agrupados para las bandas


def indice_relativo(sm: np.ndarray) -> np.ndarray:
    """0-100 entre los percentiles 5 y 95 de la propia serie."""
    lo, hi = np.nanpercentile(sm, [5, 95])
    if hi <= lo:
        return np.full(len(sm), 50.0)
    return np.clip((sm - lo) / (hi - lo) * 100, 0, 100)


def bandas(fechas: list[date], indice: np.ndarray) -> dict:
    """P10/P50/P90 del índice por día del año (1-366), con los días ±VENTANA_BANDAS de todos los años."""
    doy = np.array([f.timetuple().tm_yday for f in fechas])
    out = {'p10': [], 'p50': [], 'p90': []}
    for d in range(1, 367):
        dist = np.abs(doy - d)
        vals = indice[np.minimum(dist, 366 - dist) <= VENTANA_BANDAS]
        p10, p50, p90 = np.percentile(vals, [10, 50, 90]) if len(vals) else (np.nan,) * 3
        out['p10'].append(round(float(p10), 1))
        out['p50'].append(round(float(p50), 1))
        out['p90'].append(round(float(p90), 1))
    return out


def inicio_lluvias(fechas: list[date], indice: np.ndarray) -> dict[int, date | None]:
    """Por año: primer día (jun-sep) en que la media de 7 días se mantiene >= UMBRAL_INICIO DIAS_SOSTENIDOS días."""
    acumulada = np.cumsum(np.insert(indice, 0, 0.0))
    idx = np.arange(len(indice))
    media7 = (acumulada[idx + 1] - acumulada[np.maximum(idx - 6, 0)]) / np.minimum(idx + 1, 7)
    humedo = media7 >= UMBRAL_INICIO

    inicios: dict[int, date | None] = {}
    for i, f in enumerate(fechas):
        inicios.setdefault(f.year, None)
        if (inicios[f.year] is None and MESES_INICIO[0] <= f.month <= MESES_INICIO[1]
                and i + DIAS_SOSTENIDOS <= len(fechas) and humedo[i:i + DIAS_SOSTENIDOS].all()):
            inicios[f.year] = f
    return inicios


def racha_seca_en_floracion(fechas: list[date], indice: np.ndarray, inicio: date) -> bool | None:
    """¿Hubo >= DIAS_RACHA_SECA días seguidos con índice < UMBRAL_SECO durante la floración?
    None si la serie no cubre toda la ventana."""
    desde = inicio + timedelta(days=DIAS_A_FLORACION - MEDIA_VENTANA_FLORACION)
    hasta = inicio + timedelta(days=DIAS_A_FLORACION + MEDIA_VENTANA_FLORACION)
    if fechas[0] > desde or fechas[-1] < hasta:
        return None
    racha = 0
    for f, v in zip(fechas, indice):
        if desde <= f <= hasta:
            racha = racha + 1 if v < UMBRAL_SECO else 0
            if racha >= DIAS_RACHA_SECA:
                return True
    return False


def _mmdd(dia_del_anio: float) -> str:
    return (date(2023, 1, 1) + timedelta(days=round(dia_del_anio) - 1)).strftime('%m-%d')


def resumir_celda(fechas: list[date], sm: np.ndarray) -> dict:
    """Panorama de una celda: bandas del índice, inicio de lluvias y riesgo de sequía en floración."""
    indice = indice_relativo(np.asarray(sm, dtype=float))
    inicios = inicio_lluvias(fechas, indice)
    con_inicio = {y: d for y, d in inicios.items() if d}
    sequia = {y: racha_seca_en_floracion(fechas, indice, d) for y, d in con_inicio.items()}
    evaluables = [v for v in sequia.values() if v is not None]
    doys = [d.timetuple().tm_yday for d in con_inicio.values()]
    return {
        'bandas': bandas(fechas, indice),
        'inicio_lluvias': {
            'mediana': _mmdd(median(doys)) if doys else None,
            'temprana': _mmdd(min(doys)) if doys else None,
            'tardia': _mmdd(max(doys)) if doys else None,
            'por_anio': {str(y): (d.isoformat() if d else None) for y, d in inicios.items()},
        },
        'sequia_floracion': {
            'probabilidad': round(sum(evaluables) / len(evaluables), 2) if evaluables else None,
            'anios_evaluados': len(evaluables),
            'por_anio': {str(y): v for y, v in sequia.items()},
        },
    }
