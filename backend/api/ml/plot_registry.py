"""
Plot Registry — 11 real NASA SMAP sampling points in Jalisco, Mexico.

Coordinates and IDs are taken verbatim from the downloaded SMAP dataset:
  CropAnalytics-BOB-SMAP-2024-SPL3SMP-E-006-results.csv

The `smap_id` field matches the `ID` column in that CSV exactly.
The `csv_file` field refers to a per-plot CSV that can be split out from the
master file, OR the pipeline can read the master file directly (see ml_engine).
"""

JALISCO_PLOTS = [
    {
        "id": "mun_537_plot_5",
        "smap_id": "MUN_537_PLOT_5",
        "name": "Tepatitlán de Morelos (Plot 5)",
        "lat": 20.740333,
        "lon": -102.834666,
        "altitude_m": 1772,
    },
    {
        "id": "mun_571_plot_17",
        "smap_id": "MUN_571_PLOT_17",
        "name": "Lagos de Moreno (Plot 17)",
        "lat": 21.479897,
        "lon": -102.280986,
        "altitude_m": 1890,
    },
    {
        "id": "mun_582_plot_13",
        "smap_id": "MUN_582_PLOT_13",
        "name": "San Juan de los Lagos (Plot 13)",
        "lat": 21.131055,
        "lon": -102.454666,
        "altitude_m": 1815,
    },
    {
        "id": "mun_589_plot_2",
        "smap_id": "MUN_589_PLOT_2",
        "name": "Ojuelos de Jalisco (Plot 2)",
        "lat": 21.2645,
        "lon": -102.036666,
        "altitude_m": 2050,
    },
    {
        "id": "mun_609_plot_1",
        "smap_id": "MUN_609_PLOT_1",
        "name": "San Miguel el Alto (Plot 1)",
        "lat": 21.393667,
        "lon": -102.341833,
        "altitude_m": 1940,
    },
    {
        "id": "mun_610_plot_3",
        "smap_id": "MUN_610_PLOT_3",
        "name": "San Julián (Plot 3)",
        "lat": 20.951,
        "lon": -102.168,
        "altitude_m": 1850,
    },
    {
        "id": "mun_614_plot_9",
        "smap_id": "MUN_614_PLOT_9",
        "name": "Arandas (Plot 9)",
        "lat": 21.042833,
        "lon": -102.949666,
        "altitude_m": 1960,
    },
    {
        "id": "mun_629_plot_15",
        "smap_id": "MUN_629_PLOT_15",
        "name": "Jalostotitlán (Plot 15)",
        "lat": 20.876222,
        "lon": -102.715194,
        "altitude_m": 1775,
    },
    {
        "id": "mun_647_plot_4",
        "smap_id": "MUN_647_PLOT_4",
        "name": "Valle de Guadalupe (Plot 4)",
        "lat": 21.047,
        "lon": -102.623333,
        "altitude_m": 1830,
    },
    {
        "id": "mun_660_plot_25",
        "smap_id": "MUN_660_PLOT_25",
        "name": "Yahualica de González Gallo (Plot 25)",
        "lat": 20.753597,
        "lon": -103.113566,
        "altitude_m": 1700,
    },
    {
        "id": "mun_8_plot_8",
        "smap_id": "MUN_8_PLOT_8",
        "name": "Acatic (Plot 8)",
        "lat": 20.6945,
        "lon": -102.5865,
        "altitude_m": 1610,
    },
]

# Fast lookup by smap_id string
PLOTS_BY_SMAP_ID = {p["smap_id"]: p for p in JALISCO_PLOTS}


# ---------------------------------------------------------------------------
# Haversine snap utility (pure Python, no PostGIS/GeoDjango required)
# ---------------------------------------------------------------------------
import math as _math


def snap_to_nearest_plot(lat: float, lon: float) -> dict:
    """
    Return the plot from JALISCO_PLOTS that is closest to (lat, lon).
    The returned dict includes an additional ``distance_km`` key.
    """
    best: dict | None = None
    best_dist = float("inf")
    for plot in JALISCO_PLOTS:
        dlat = _math.radians(plot["lat"] - lat)
        dlon = _math.radians(plot["lon"] - lon)
        a = (
            _math.sin(dlat / 2) ** 2
            + _math.cos(_math.radians(lat))
            * _math.cos(_math.radians(plot["lat"]))
            * _math.sin(dlon / 2) ** 2
        )
        dist = 6371.0 * 2 * _math.asin(_math.sqrt(a))
        if dist < best_dist:
            best_dist = dist
            best = plot
    return {**best, "distance_km": round(best_dist, 2)}
