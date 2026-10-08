"""
soil_moisture_forecast.py — Temporal baseline projection for Sentineli
======================================================================

Current scope
-------------
We have real SMAP + Daymet data for 2024 only.
For all other years (historical and future) we project the 2024 seasonal
pattern as a static baseline, clearly labeled so the frontend can display
the appropriate caveat.

Future upgrade path
-------------------
A proper multi-year forecast would require either:
  (a) Extended SMAP/Daymet pulls from NASA AppEEARS for each year, or
  (b) A sequence-to-sequence LSTM trained on multi-year TxSON data to
      generate N-step-ahead forecasts.
This module is designed so that (b) can be dropped in by replacing
`project_year()` with a real forecast call without changing any callers.

Public API
----------
  get_annual_profile(smap_id, year, master_csv, daymet_csv) -> AnnualProfile
  project_year(smap_id, year, master_csv, daymet_csv)       -> AnnualProfile
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from .ml_engine import SM_HUMEDO, SM_SECO, run_inference

BASELINE_YEAR = 2024


@dataclass
class AnnualProfile:
    year:         int
    smap_id:      str
    dates:        list[str]
    soil_moisture: list[float]   # daily m³/m³
    mean_sm:      float
    min_sm:       float
    max_sm:       float
    dry_days:     int
    wet_days:     int
    is_real_data: bool           # True = from actual 2024 datasets
    model_backend: str


def get_annual_profile(
    smap_id: str,
    year: int,
    master_csv: str,
    daymet_csv: Optional[str] = None,
) -> AnnualProfile:
    """
    Return the soil moisture profile for *year*.

    If year == BASELINE_YEAR (2024): run real inference.
    Otherwise: re-use the 2024 profile with dates shifted to the target year
               and label it as a projected baseline.
    """
    if year == BASELINE_YEAR:
        result = run_inference(smap_id, master_csv, daymet_csv)
        return AnnualProfile(
            year          = year,
            smap_id       = smap_id,
            dates         = result["dates"],
            soil_moisture = result["soil_moisture"],
            mean_sm       = result["mean_sm"],
            min_sm        = result["min_sm"],
            max_sm        = result["max_sm"],
            dry_days      = result["dry_days"],
            wet_days      = result["wet_days"],
            is_real_data  = True,
            model_backend = result["model_backend"],
        )
    return project_year(smap_id, year, master_csv, daymet_csv)


def project_year(
    smap_id: str,
    year: int,
    master_csv: str,
    daymet_csv: Optional[str] = None,
) -> AnnualProfile:
    """
    Build a projected annual soil-moisture profile for any non-2024 year.

    The 2024 seasonal pattern is re-stamped onto the target year:
      - Dates are recalculated for the target year (leap/non-leap handled).
      - Values are identical to the real 2024 inference result.
      - is_real_data = False  →  frontend shows "Proyección de Línea Base 2024"

    This is intentionally simple. A future forecasting model (e.g. Seq2Seq
    LSTM or statistical downscaling from OpenMeteo) can replace this function
    without any changes to callers.
    """
    # Run real 2024 inference to get the seasonal pattern
    base = run_inference(smap_id, master_csv, daymet_csv)

    # Shift dates: replace 2024 with target year, keeping MM-DD
    def _restamp(date_str: str, target_year: int) -> str:
        """Replace year in 'YYYY-MM-DD', skipping Feb-29 on non-leap years."""
        parts = date_str.split("-")
        mm, dd = parts[1], parts[2]
        if mm == "02" and dd == "29" and not _is_leap(target_year):
            return f"{target_year}-03-01"
        return f"{target_year}-{mm}-{dd}"

    new_dates = [_restamp(d, year) for d in base["dates"]]
    sm        = base["soil_moisture"]

    return AnnualProfile(
        year          = year,
        smap_id       = smap_id,
        dates         = new_dates,
        soil_moisture = sm,
        mean_sm       = base["mean_sm"],
        min_sm        = base["min_sm"],
        max_sm        = base["max_sm"],
        dry_days      = base["dry_days"],
        wet_days      = base["wet_days"],
        is_real_data  = False,
        model_backend = f"projected_baseline_{BASELINE_YEAR}",
    )


def _is_leap(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def summarise_profile(profile: AnnualProfile) -> dict:
    """
    Derive agronomically meaningful summary statistics from an annual profile.
    Used by the hybrid recommender to score soil conditions per cycle.
    """
    n = len(profile.soil_moisture)
    if n == 0:
        return {}

    sm = profile.soil_moisture

    # Growing-season window: May 1 – Oct 31 (days 122–304 in non-leap year)
    # We use the date strings to detect this precisely
    growing_sm = [
        v for d, v in zip(profile.dates, sm)
        if _in_growing_season(d)
    ]

    growing_mean = round(sum(growing_sm) / len(growing_sm), 4) if growing_sm else profile.mean_sm
    growing_dry  = sum(1 for v in growing_sm if v < SM_SECO)
    growing_wet  = sum(1 for v in growing_sm if v > SM_HUMEDO)

    # Stress index: fraction of growing-season days below threshold
    stress_index = round(growing_dry / len(growing_sm), 3) if growing_sm else 0.5

    # Rainfed suitability score (0–100)
    # Thresholds are calibrated to Jalisco highland conditions (semi-arid, 1600–2050 m asl).
    # Observed 2024 growing-season means: 0.136–0.156 m³/m³; stress indices: 0.38–0.51.
    # Bands reflect relative moisture adequacy within this region, not global standards.
    #
    # Score  | grow_mean       | stress_index   | Agronomic interpretation
    # -----  | --------------- | -------------- | ----------------------------
    # 85     | ≥ 0.165         | < 0.30         | Excellent for region
    # 70     | ≥ 0.155         | < 0.38         | Good — above-average season
    # 55     | ≥ 0.145         | < 0.45         | Moderate — typical season
    # 40     | ≥ 0.130         | < 0.55         | Below average — drought risk
    # 20     | < 0.130         | any            | Severe deficit
    if growing_mean >= 0.165 and stress_index < 0.30:
        suitability = 85
    elif growing_mean >= 0.155 and stress_index < 0.38:
        suitability = 70
    elif growing_mean >= 0.145 and stress_index < 0.45:
        suitability = 55
    elif growing_mean >= 0.130 and stress_index < 0.55:
        suitability = 40
    else:
        suitability = 20

    return {
        "annual_mean_sm":     profile.mean_sm,
        "growing_mean_sm":    growing_mean,
        "growing_dry_days":   growing_dry,
        "growing_wet_days":   growing_wet,
        "stress_index":       stress_index,
        "rainfed_suitability": suitability,
        "is_real_data":       profile.is_real_data,
        "model_backend":      profile.model_backend,
    }


def _in_growing_season(date_str: str) -> bool:
    """True if date falls between May 1 and Oct 31 inclusive."""
    try:
        mm = int(date_str[5:7])
        return 5 <= mm <= 10
    except (IndexError, ValueError):
        return False
