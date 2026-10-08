"""
hybrid_recommender.py — Soil-moisture-aware hybrid corn ranking for Sentineli
==============================================================================

Flow
----
1. Receive user inputs: lat, lon, extension_ha, has_irrigation.
2. Snap to the nearest of the 11 SMAP plots via Haversine.
3. Run (or load cached) LSTM inference → 2024 soil moisture profile.
4. Derive agronomic summary (growing-season mean, stress index, suitability).
5. Query the DB for all Ciclos with the correct condicion (Temporal / Riego).
6. For each hybrid found:
   a. Pull historical average bromatological values from ResultadoLaboratorio.
   b. Pull historical average yield (laboratorio__rms) filtered by condicion.
   c. Apply a soil-moisture compatibility adjustment to yield_dm.
   d. Run MILK2024 to get leche_ton, leche_ha, and economic analysis.
   e. Score the hybrid (MILK performance × SM compatibility).
7. Return ranked list with MILK2024 metrics, SM context, and recommendation text.

Soil-moisture × yield adjustment
---------------------------------
The SM compatibility factor adjusts the historical average yield to reflect
what the estimated moisture conditions of the user's plot would yield,
using a simplified FAO-56 water-productivity relationship:

  adjusted_yield = historical_yield × (1 - Ky × (1 - ETa/ETc))

Where:
  Ky  = yield response factor for maize (≈ 1.25, FAO Irrigation Paper 33)
  ETa/ETc ≈ growing_mean_sm / field_capacity_sm  (proxy, bounded [0,1])
  field_capacity_sm = 0.30 m³/m³  (typical for Jalisco highland soils)

This is a first-order approximation; it doesn't replace a full water-balance
model, but gives a physically grounded adjustment visible to the user.
"""
from __future__ import annotations

import math
import os
from typing import Optional

from django.conf import settings
from django.db.models import Avg, Count, StdDev

from ..ml.plot_registry import JALISCO_PLOTS
from ..ml.soil_moisture_forecast import get_annual_profile, summarise_profile
from ..utils.milk_calculator import calcular_metricas_milk2024, calcular_valor_ensilaje, datos_milk2024
from ..utils.geospatial_estimator import calcular_distancia_haversine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_FIELD_CAPACITY_SM = 0.30    # m³/m³ — typical Jalisco highland Vertisol
_KY_MAIZE          = 1.25    # FAO-56 yield response factor, grain maize
_YIELD_FALLBACK    = 18.0    # ton DM/ha — used when no DB records exist

# Scoring weights — sum to 1.0
# Each component is min-max normalised across the current candidate set,
# so every dimension contributes independently of its absolute scale.
#
# leche_ton  (kg milk / t DM)  — pure nutritional quality, bromatology-driven
# yield_adj  (t DM / ha)       — adjusted productivity, location-driven via SM factor
# ndf_score  (inverted NDF%)   — digestibility / starch proxy; rewards low-NDF hybrids;
#                                 weight doubles under drought (suitability < 45)
# consistency (1 - CV)         — hybrid's yield stability across historical cycles
_W_QUALITY    = 0.30
_W_YIELD      = 0.35
_W_NDF        = 0.20
_W_CONSISTENCY = 0.15


# ---------------------------------------------------------------------------
# Snap user pin to nearest SMAP plot
# ---------------------------------------------------------------------------
def snap_to_plot(lat: float, lon: float) -> tuple[dict, float]:
    """Return (plot_dict, distance_km) for the nearest registered SMAP plot."""
    best, best_dist = None, float("inf")
    for p in JALISCO_PLOTS:
        d = calcular_distancia_haversine(lat, lon, p["lat"], p["lon"])
        if d < best_dist:
            best_dist = d
            best = p
    return best, round(best_dist, 2)


# ---------------------------------------------------------------------------
# FAO-56 yield adjustment
# ---------------------------------------------------------------------------
def _sm_yield_factor(growing_mean_sm: float) -> float:
    """
    Return a multiplier [0.30, 1.05] that adjusts historical yield for the
    estimated soil moisture conditions of the user's plot.
    """
    eta_etc = min(1.0, growing_mean_sm / _FIELD_CAPACITY_SM)
    factor = 1.0 - _KY_MAIZE * (1.0 - eta_etc)
    return round(max(0.30, min(1.05, factor)), 4)


# ---------------------------------------------------------------------------
# Main recommendation function
# ---------------------------------------------------------------------------
def recomendar_hibridos(
    lat: float,
    lon: float,
    extension_ha: float,
    has_irrigation: bool,
    year: int = 2024,
    precios_mercado: Optional[dict] = None,
) -> dict:
    """
    Core recommendation engine.

    Parameters
    ----------
    lat, lon        : User's GPS pin (decimal degrees)
    extension_ha    : Plot size in hectares
    has_irrigation  : True → filter Ciclos condicion='Riego'
                      False → filter Ciclos condicion='Temporal'
    year            : Target year for soil moisture profile (default 2024)
    precios_mercado : Optional price overrides for MILK2024 economic model

    Returns
    -------
    {
      snapped_plot     : {id, smap_id, name, lat, lon, distance_km},
      sm_profile       : {annual_mean_sm, growing_mean_sm, stress_index,
                          rainfed_suitability, is_real_data, model_backend},
      sm_warning       : str | None,   # shown when suitability < 55
      condicion        : "Temporal" | "Riego",
      year             : int,
      extension_ha     : float,
      ranking          : [ HybridResult, … ],   # sorted best-first
      nota_proyeccion  : str | None,
    }
    """
    from ..models import Ciclo, Hibrido, ResultadoLaboratorio

    # 1. Snap to nearest plot
    plot, dist_km = snap_to_plot(lat, lon)

    # 2. Soil moisture profile
    master_csv = getattr(
        settings, "ML_SMAP_MASTER_CSV",
        os.path.join(settings.BASE_DIR, "data",
                     "CropAnalytics-BOB-SMAP-2024-SPL3SMP-E-006-results.csv")
    )
    daymet_csv = getattr(settings, "ML_DAYMET_CSV", None)

    profile = get_annual_profile(plot["smap_id"], year, master_csv, daymet_csv)
    sm_summary = summarise_profile(profile)

    # 3. Soil moisture warning
    suitability = sm_summary["rainfed_suitability"]
    sm_warning = None
    if not has_irrigation:
        if suitability < 35:
            sm_warning = (
                "⚠️ Humedad estimada muy baja para temporal. "
                "El estrés hídrico proyectado durante la temporada de crecimiento es severo. "
                "Se recomienda considerar riego suplementario o seleccionar híbridos de ciclo corto."
            )
        elif suitability < 55:
            sm_warning = (
                "⚠️ Condiciones de humedad marginales para temporal. "
                "Se esperan períodos de estrés moderado. "
                "Priorizar híbridos con tolerancia a sequía."
            )

    # 4. Query hybrids matching the irrigation condition
    condicion = "Riego" if has_irrigation else "Temporal"
    # Con riego el agua no la limita la humedad de temporal estimada por SMAP.
    sm_factor = 1.0 if has_irrigation else _sm_yield_factor(sm_summary["growing_mean_sm"])

    ciclos_qs = (
        Ciclo.objects
        .filter(
            condicion__iexact=condicion,
            laboratorio__isnull=False,
            laboratorio__fdn__gt=20,    # exclude records missing NDF (would inflate leche_ton)
            laboratorio__rms__gt=0,     # exclude zero-yield records
        )
        .values("hibrido__id", "hibrido__nombre", "hibrido__marca")
        .annotate(
            n_ciclos       = Count("id"),
            avg_ms         = Avg("laboratorio__ms"),
            avg_pc         = Avg("laboratorio__pc"),
            avg_gc         = Avg("laboratorio__gc"),
            avg_cen        = Avg("laboratorio__cen"),
            avg_fdn        = Avg("laboratorio__fdn"),
            avg_cnf        = Avg("laboratorio__cnf"),
            avg_yield_dm   = Avg("laboratorio__rms"),
            std_yield_dm   = StdDev("laboratorio__rms"),   # for yield consistency
            avg_dff        = Avg("laboratorio__dff"),
        )
        .filter(n_ciclos__gt=0)
    )

    if not ciclos_qs.exists():
        return {
            "snapped_plot":    {**plot, "distance_km": dist_km},
            "sm_profile":      sm_summary,
            "sm_warning":      sm_warning,
            "condicion":       condicion,
            "year":            year,
            "extension_ha":    extension_ha,
            "ranking":         [],
            "error":           f"No se encontraron híbridos con ciclos bajo régimen '{condicion}'.",
            "nota_proyeccion": _nota_proyeccion(year, profile.is_real_data),
        }

    # 5. Build raw candidate list (pre-scoring pass)
    precios = precios_mercado or {}
    candidates = []

    for item in ciclos_qs:
        hist_yield  = float(item["avg_yield_dm"] or _YIELD_FALLBACK)
        adj_yield   = round(hist_yield * sm_factor, 2)
        total_yield = round(adj_yield * extension_ha, 2)

        # Yield consistency: CV = std/mean; 1-CV bounded [0,1].
        # With n=1 there is no std → treat as average consistency (0.5) so
        # single-cycle hybrids neither get rewarded nor punished for stability.
        std_y = float(item["std_yield_dm"] or 0.0)
        n_cy  = item["n_ciclos"] or 1
        cv    = (std_y / hist_yield) if (hist_yield > 0 and n_cy > 1) else 0.20
        consistency = round(max(0.0, min(1.0, 1.0 - cv)), 4)

        brom = datos_milk2024(
            item["avg_ms"], item["avg_pc"], item["avg_gc"],
            item["avg_cen"], item["avg_fdn"], item["avg_cnf"], adj_yield,
        )

        milk = calcular_metricas_milk2024(brom)
        econ = calcular_valor_ensilaje(brom, milk, precios)

        candidates.append({
            "hibrido": {
                "id":     item["hibrido__id"],
                "nombre": item["hibrido__nombre"],
                "marca":  item["hibrido__marca"],
            },
            "n_ciclos_historicos": item["n_ciclos"],
            "rendimiento": {
                "historico_dm_ha":   round(hist_yield, 2),
                "ajustado_sm_dm_ha": adj_yield,
                "factor_ajuste_sm":  sm_factor,
                "total_dm_plot":     total_yield,
                "avg_dff":           round(float(item["avg_dff"] or 65.0), 1),
            },
            "bromatologia": {
                "ms":   round(brom["ms"], 2),
                "cp":   round(brom["cp"], 2),
                "ee":   round(brom["ee"], 2),
                "ash":  round(brom["ash"], 2),
                "ndf":  round(brom["ndf"], 2),
            },
            "milk2024":           milk,
            "analisis_economico": econ,
            # raw signals for normalisation pass
            "_leche_ton":   milk["leche_ton"],   # nutritional quality, yield-independent
            "_adj_yield":   adj_yield,           # SM-adjusted productivity
            "_ndf":         brom["ndf"],         # lower = more digestible / starch-rich
            "_consistency": consistency,         # yield stability
        })

    # 6. Normalise each signal across the candidate set (min-max → [0, 1])
    #    then compute weighted composite score.
    def _minmax(vals: list[float]) -> list[float]:
        lo, hi = min(vals), max(vals)
        rng = hi - lo
        if rng < 1e-9:
            return [0.5] * len(vals)
        return [(v - lo) / rng for v in vals]

    lt_norms   = _minmax([c["_leche_ton"]   for c in candidates])
    y_norms    = _minmax([c["_adj_yield"]   for c in candidates])
    ndf_norms  = _minmax([-c["_ndf"]        for c in candidates])   # inverted: lower NDF → higher score
    con_norms  = _minmax([c["_consistency"] for c in candidates])

    # Under drought (suitability < 45) shift weight FROM yield TOWARD nutritional quality
    # and consistency — a more digestible, stable hybrid matters more when water is scarce.
    # Under ideal conditions (≥ 55) shift toward raw yield — more biomass wins.
    if suitability < 45:
        w_quality     = _W_QUALITY     + 0.10   # 0.40 — reward high leche_ton
        w_yield       = _W_YIELD       - 0.15   # 0.20 — yield less decisive under drought
        w_ndf         = _W_NDF         + 0.10   # 0.30 — lower NDF = better under water stress
        w_consistency = _W_CONSISTENCY - 0.05   # 0.10
    elif suitability >= 55:
        w_quality     = _W_QUALITY     - 0.05   # 0.25
        w_yield       = _W_YIELD       + 0.10   # 0.45 — more water → more biomass matters
        w_ndf         = _W_NDF         - 0.05   # 0.15
        w_consistency = _W_CONSISTENCY          # 0.15
    else:
        w_quality, w_yield, w_ndf, w_consistency = _W_QUALITY, _W_YIELD, _W_NDF, _W_CONSISTENCY

    ranking = []
    for c, lt_n, y_n, ndf_n, con_n in zip(candidates, lt_norms, y_norms, ndf_norms, con_norms):
        composite = (
            w_quality     * lt_n
            + w_yield       * y_n
            + w_ndf         * ndf_n
            + w_consistency * con_n
        )
        # Scale to a legible 0–10000 range (matches previous leche_ha score magnitude)
        score = round(composite * 10000, 1)

        entry = {k: v for k, v in c.items() if not k.startswith("_")}
        entry["score"] = score
        entry["score_breakdown"] = {
            "calidad_nutricional": round(lt_n * 10000 * w_quality, 1),
            "productividad_sm":    round(y_n  * 10000 * w_yield,   1),
            "digestibilidad_ndf":  round(ndf_n * 10000 * w_ndf,    1),
            "consistencia":        round(con_n  * 10000 * w_consistency, 1),
        }
        ranking.append(entry)

    ranking.sort(key=lambda x: x["score"], reverse=True)

    return {
        "snapped_plot":    {**plot, "distance_km": dist_km},
        "sm_profile":      sm_summary,
        "sm_warning":      sm_warning,
        "condicion":       condicion,
        "year":            year,
        "extension_ha":    extension_ha,
        "ranking":         ranking,
        "nota_proyeccion": _nota_proyeccion(year, profile.is_real_data),
    }


def _nota_proyeccion(year: int, is_real: bool) -> Optional[str]:
    if is_real:
        return None
    if year < 2024:
        return (
            f"Los datos de humedad del suelo para {year} se estiman a partir del "
            "patrón estacional 2024 (datos reales disponibles). "
            "Se asume un patrón anual similar al año de referencia."
        )
    return (
        f"Los datos de humedad del suelo para {year} son una proyección de línea base "
        "construida a partir del patrón 2024. No se dispone de datos satelitales reales "
        "para este año. Una versión futura integrará pronósticos de OpenMeteo / NASA POWER."
    )
