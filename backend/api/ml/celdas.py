"""
Celdas del panorama de humedad: la malla de 9 km de SMAP (EASE-Grid 2.0 global,
EPSG:6933) recortada a la zona con ensayos de campo.

Cada celda es un píxel de SMAP L3 enhanced; una coordenada se convierte a su
celda directamente con la proyección, sin buscar la más cercana.
"""
import json
import math
from pathlib import Path

# Alcance (km al ensayo de campo más cercano): hasta RADIO_COMPLETO_KM se ofrece
# panorama y ranking de híbridos; hasta RADIO_MAX_KM solo panorama, con el
# ranking marcado como extrapolado; más lejos no hay datos de ensayos.
RADIO_COMPLETO_KM = 25
RADIO_MAX_KM = 40

CELDAS_PATH = Path(__file__).parent / "celdas_altos.json"

# EASE-Grid 2.0 global, malla M09 (NSIDC): 1624 filas x 3856 columnas
_A = 6378137.0                      # semieje mayor WGS84 (m)
_E2 = 0.0066943799901413165         # excentricidad² WGS84
_E = math.sqrt(_E2)
_K0 = math.cos(math.radians(30)) / math.sqrt(1 - _E2 * math.sin(math.radians(30)) ** 2)
_X0, _Y0 = -17367530.44516138, 7314540.83063784   # esquina superior izquierda (m)
_CELDA_M = 9008.055210146


def _q(sin_lat):
    return (1 - _E2) * (sin_lat / (1 - _E2 * sin_lat ** 2)
                        - math.log((1 - _E * sin_lat) / (1 + _E * sin_lat)) / (2 * _E))


def fila_col(lat, lon):
    """Fila y columna del píxel de 9 km que contiene (lat, lon)."""
    x = _A * _K0 * math.radians(lon)
    y = _A * _q(math.sin(math.radians(lat))) / (2 * _K0)
    return int((_Y0 - y) // _CELDA_M), int((x - _X0) // _CELDA_M)


def centro(fila, col):
    """Latitud y longitud del centro del píxel (inversa de la proyección)."""
    x = _X0 + (col + 0.5) * _CELDA_M
    y = _Y0 - (fila + 0.5) * _CELDA_M
    q = 2 * _K0 * y / _A
    lat = math.asin(q / 2)
    for _ in range(10):  # Newton para la latitud a partir de q
        s = math.sin(lat)
        lat += (1 - _E2 * s * s) ** 2 / (2 * math.cos(lat)) * (q / (1 - _E2) - _q(s) / (1 - _E2))
    return math.degrees(lat), math.degrees(x / (_A * _K0))


def id_celda(fila, col):
    return f"M09_{fila}_{col}"


def cargar_celdas():
    """{id_celda: celda} desde celdas_altos.json (lo genera `manage.py generar_celdas`)."""
    with open(CELDAS_PATH, encoding="utf-8") as fh:
        return {c["id"]: c for c in json.load(fh)}
