"""
ml_engine.py — Sentineli Soil Moisture Inference Handler
=========================================================

Architecture
------------
Exact mirror of the production model defined in references/production_estimation.py:

  Input features (4, one per day):
    0 – Precipitation   (Daymet DAYMET_004_prcp, mm/day)
    1 – T_Max           (Daymet DAYMET_004_tmax, °C)
    2 – T_Min           (Daymet DAYMET_004_tmin, °C)
    3 – SMAP_Moisture   (SPL3SMP_E.006 AM retrieval, m³/m³; -9999 → gap-filled)

  Sequence: 14-day look-back window → shape (1, 14, 4)

  Network:
    LSTM(input_size=4, hidden_size=64, num_layers=1, batch_first=True)
    Dropout(0.2)
    Linear(64 → 32) + ReLU
    Linear(32 → 1)           ← linear output, NO sigmoid

  Scaling:
    feature_scaler : MinMaxScaler fitted on TxSON 2015–2021 training features
    target_scaler  : MinMaxScaler fitted on TxSON SWC_5 ground truth
    Both saved as sklearn joblib files alongside the .pt weights.
    Prediction = target_scaler.inverse_transform(lstm_output) → m³/m³

Data sources
------------
  SMAP  : CropAnalytics-BOB-SMAP-2024-SPL3SMP-E-006-results.csv
            Column : SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_AM_soil_moisture
            Fill   : -9999.0 → forward-fill → backward-fill

  Daymet: Pending NASA AppEEARS delivery (same format as references/datasets/NASA_Weather/)
            Columns: DAYMET_004_prcp, DAYMET_004_tmax, DAYMET_004_tmin
            When present, merged on (ID, Date) before inference.

SMAP-only fallback
------------------
When Daymet is absent, Precipitation/T_Max/T_Min are set to their training-set
means (derived from the TxSON calibration period and stored alongside the scaler).
This keeps the 4-feature input intact so frozen weights load without shape errors.
If weights are also absent, the smoothed SMAP series is returned directly.

Zero-leakage guarantee
-----------------------
The LSTM runs in eval() + torch.no_grad() with frozen parameters.
No gradient ever touches the inference path.

Public API
----------
  run_inference(smap_id, master_csv_path, daymet_csv_path=None) -> dict
"""
from __future__ import annotations

import csv
import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Optional PyTorch — graceful degradation when not installed
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn
    _TORCH = True
except ImportError:
    _TORCH = False

# Optional scikit-learn — needed for scaler loading
try:
    import joblib
    _JOBLIB = True
except ImportError:
    _JOBLIB = False

# ---------------------------------------------------------------------------
# Constants  (must match production_estimation.py exactly)
# ---------------------------------------------------------------------------
LOOKBACK    = 14
HIDDEN_SIZE = 64
NUM_LAYERS  = 1          # production model: single-layer LSTM
N_FEATURES  = 4          # Precipitation, T_Max, T_Min, SMAP_Moisture

# Feature column order must be consistent with training
FEATURE_ORDER = ["Precipitation", "T_Max", "T_Min", "SMAP_Moisture"]

# NASA AppEEARS column names in the raw Daymet CSV
_DAYMET_COLS = {
    "prcp": "DAYMET_004_prcp",
    "tmax": "DAYMET_004_tmax",
    "tmin": "DAYMET_004_tmin",
}
_COL_ID      = "ID"
_COL_DATE    = "Date"
_COL_SM_SMAP = "SPL3SMP_E_006_Soil_Moisture_Retrieval_Data_AM_soil_moisture"
_FILL_VAL    = -9999.0

# Únicos umbrales de humedad (m³/m³) del proyecto. Definidos por el equipo para
# los Altos de Jalisco; no están validados con mediciones de campo.
SM_SECO   = 0.12   # por debajo: estrés hídrico
SM_HUMEDO = 0.30   # por encima: exceso; también se usa como proxy de capacidad de campo

_WEIGHTS_DIR    = Path(__file__).parent / "weights"
_WEIGHTS_PATH   = _WEIGHTS_DIR / "lstm_soil_moisture.pt"
_FEAT_SCALER    = _WEIGHTS_DIR / "feature_scaler.joblib"
_TARGET_SCALER  = _WEIGHTS_DIR / "target_scaler.joblib"
# Fallback feature means when Daymet is absent (fitted from TxSON 2015-2021)
# Override by shipping a means.json alongside the weights.
_MEANS_PATH     = _WEIGHTS_DIR / "feature_means.json"

_DEFAULT_MEANS = {          # conservative Jalisco-region priors
    "Precipitation": 2.1,   # mm/day  (annual mean for semi-arid highland)
    "T_Max":         27.5,  # °C
    "T_Min":         12.0,  # °C
}

# ---------------------------------------------------------------------------
# LSTM definition  (must match production_estimation.py exactly)
# ---------------------------------------------------------------------------
if _TORCH:
    class _SoilMoistureLSTM(torch.nn.Module):
        """
        Single-layer LSTM + linear regression head.
        input  : (batch, 14, 4)
        output : (batch, 14, 1)  — last timestep used for prediction
        """
        def __init__(self):
            super().__init__()
            self.lstm = torch.nn.LSTM(
                input_size=N_FEATURES,
                hidden_size=HIDDEN_SIZE,
                num_layers=NUM_LAYERS,
                dropout=0.0,    # no dropout on a single-layer LSTM
                batch_first=True,
            )
            self.dropout = torch.nn.Dropout(0.2)
            self.head = torch.nn.Sequential(
                torch.nn.Linear(HIDDEN_SIZE, 32),
                torch.nn.ReLU(),
                torch.nn.Linear(32, 1),
                # NO sigmoid — raw linear output, inverse-transformed by scaler
            )

        def forward(self, x):          # x: (batch, seq, 4)
            out, _ = self.lstm(x)      # (batch, seq, hidden)
            out = self.dropout(out)
            return self.head(out)      # (batch, seq, 1)


_model_singleton     = None
_feat_scaler_obj     = None
_target_scaler_obj   = None


def _load_artifacts():
    """
    Lazy-load model weights and scalers once per process lifetime.
    Returns (model | None, feat_scaler | None, target_scaler | None).
    """
    global _model_singleton, _feat_scaler_obj, _target_scaler_obj

    # --- weights ---
    if _model_singleton is None and _TORCH:
        m = _SoilMoistureLSTM()
        if _WEIGHTS_PATH.exists():
            state = torch.load(str(_WEIGHTS_PATH), map_location="cpu", weights_only=True)
            m.load_state_dict(state)
        for p in m.parameters():
            p.requires_grad = False
        m.eval()
        _model_singleton = m

    # --- scalers ---
    if _feat_scaler_obj is None and _JOBLIB and _FEAT_SCALER.exists():
        _feat_scaler_obj = joblib.load(str(_FEAT_SCALER))

    if _target_scaler_obj is None and _JOBLIB and _TARGET_SCALER.exists():
        _target_scaler_obj = joblib.load(str(_TARGET_SCALER))

    return _model_singleton, _feat_scaler_obj, _target_scaler_obj


def _load_feature_means() -> dict:
    if _MEANS_PATH.exists():
        with open(_MEANS_PATH) as fh:
            return json.load(fh)
    return _DEFAULT_MEANS.copy()


# ---------------------------------------------------------------------------
# CSV readers
# ---------------------------------------------------------------------------
def _read_smap_csv(master_csv_path: str) -> dict[str, list[tuple[str, float]]]:
    """
    Parse the SMAP master CSV.
    Returns {plot_id: [(date_str, sm_value_or_nan), …]} sorted by date.
    """
    data: dict[str, list[tuple[str, float]]] = {}
    path = Path(master_csv_path)
    if not path.exists():
        raise FileNotFoundError(f"SMAP master CSV not found: {master_csv_path}")

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            plot_id  = row[_COL_ID].strip()
            date_str = row[_COL_DATE].strip()
            try:
                val = float(row[_COL_SM_SMAP].strip())
            except (ValueError, KeyError):
                val = np.nan
            if val == _FILL_VAL:
                val = np.nan
            data.setdefault(plot_id, []).append((date_str, val))

    for pid in data:
        data[pid].sort(key=lambda x: x[0])
    return data


def _read_daymet_csv(daymet_csv_path: str, plot_id: str) -> dict[str, dict]:
    """
    Parse a Daymet AppEEARS CSV (same format as references/datasets/NASA_Weather/).
    Returns {date_str: {Precipitation, T_Max, T_Min}} for the requested plot_id.
    """
    result = {}
    path = Path(daymet_csv_path)
    if not path.exists():
        return result

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get(_COL_ID, "").strip() != plot_id:
                continue
            date_str = row[_COL_DATE].strip()
            try:
                result[date_str] = {
                    "Precipitation": float(row[_DAYMET_COLS["prcp"]]),
                    "T_Max":         float(row[_DAYMET_COLS["tmax"]]),
                    "T_Min":         float(row[_DAYMET_COLS["tmin"]]),
                }
            except (ValueError, KeyError):
                pass
    return result


# ---------------------------------------------------------------------------
# Gap-filling (forward-fill then backward-fill, same as production_estimation.py)
# ---------------------------------------------------------------------------
def _ffill_bfill(arr: np.ndarray, fallback: float = 0.22) -> np.ndarray:
    out = arr.copy()
    last = np.nan
    for i in range(len(out)):
        if not np.isnan(out[i]):
            last = out[i]
        elif not np.isnan(last):
            out[i] = last
    last = np.nan
    for i in range(len(out) - 1, -1, -1):
        if not np.isnan(out[i]):
            last = out[i]
        elif not np.isnan(last):
            out[i] = last
    out = np.where(np.isnan(out), fallback, out)
    return out


# ---------------------------------------------------------------------------
# Hann-weighted 7-day centred smoother (SMAP noise reduction)
# ---------------------------------------------------------------------------
def _smooth(arr: np.ndarray, window: int = 7) -> np.ndarray:
    hann = np.hanning(window)
    hann /= hann.sum()
    half = window // 2
    n    = len(arr)
    out  = np.zeros(n, dtype=np.float32)
    for i in range(n):
        lo      = max(0, i - half)
        hi      = min(n, i + half + 1)
        w_slice = hann[half - (i - lo): half + (hi - i)]
        w_slice = w_slice / w_slice.sum()
        out[i]  = float(np.dot(arr[lo:hi], w_slice))
    return out


# ---------------------------------------------------------------------------
# Feature matrix builder
# ---------------------------------------------------------------------------
def _build_feature_matrix(
    dates: list[str],
    sm_filled: np.ndarray,
    daymet: dict[str, dict],
    means: dict,
) -> np.ndarray:
    """
    Assemble the (N, 4) normalised feature matrix in FEATURE_ORDER.

    When Daymet data is missing for a date, the training-set mean is used
    (same imputation strategy as production_estimation.py's gap filling).
    """
    n = len(dates)
    X = np.zeros((n, N_FEATURES), dtype=np.float32)
    for i, d in enumerate(dates):
        w = daymet.get(d, {})
        X[i, 0] = float(w.get("Precipitation", means["Precipitation"]))
        X[i, 1] = float(w.get("T_Max",         means["T_Max"]))
        X[i, 2] = float(w.get("T_Min",         means["T_Min"]))
        X[i, 3] = float(sm_filled[i])
    return X


# ---------------------------------------------------------------------------
# LSTM sliding-window inference
# ---------------------------------------------------------------------------
def _lstm_predict(
    model,
    X_scaled: np.ndarray,
    target_scaler,
) -> np.ndarray:
    """
    Run LSTM with a 14-day look-back window over the full time series,
    all windows in a single batched forward pass.

    Uses target_scaler.inverse_transform() to recover physical m³/m³,
    matching the production_estimation.py output stage exactly.
    Falls back to a clipped linear rescale when no scaler is available.
    """
    # Zero-pad the first LOOKBACK-1 days so every day t gets the window [t-13, t]
    padded  = np.vstack([np.zeros((LOOKBACK - 1, N_FEATURES), dtype=np.float32),
                         X_scaled.astype(np.float32)])
    windows = np.lib.stride_tricks.sliding_window_view(padded, LOOKBACK, axis=0)
    windows = np.ascontiguousarray(windows.transpose(0, 2, 1))   # (n, 14, 4)

    with torch.no_grad():
        raw = model(torch.from_numpy(windows))[:, -1, 0].numpy()  # (n,)

    if target_scaler is not None:
        physical = target_scaler.inverse_transform(raw.reshape(-1, 1)).ravel()
    else:
        # Approximate inverse: assume TxSON SWC_5 range ≈ [0.04, 0.35]
        physical = raw * 0.31 + 0.04

    return np.clip(physical, 0.01, 0.70).astype(np.float32)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
# ponytail: per-process cache keyed by file paths; restart the server after
# replacing the SMAP/Daymet CSVs. Callers must treat the result as read-only.
@lru_cache(maxsize=64)
def run_inference(
    smap_id: str,
    master_csv_path: str,
    daymet_csv_path: str | None = None,
) -> dict:
    """
    Execute the full inference pipeline for one Jalisco plot.

    Parameters
    ----------
    smap_id : str
        The `ID` value in the SMAP master CSV (e.g. "MUN_537_PLOT_5").
    master_csv_path : str
        Path to the SMAP master CSV.
    daymet_csv_path : str | None
        Path to the Daymet AppEEARS CSV (same format as references/datasets/
        NASA_Weather/TxSON-Daymet-Weather-24-TD-DAYMET-004-results.csv).
        Pass None while waiting for delivery — the engine will fill
        meteo features with their TxSON training-set means.

    Returns
    -------
    dict:
        dates           : list[str]        ISO-8601 date strings
        soil_moisture   : list[float]      daily estimated sm m³/m³
        smap_raw        : list[float|None] original SMAP retrievals (None = fill)
        mean_sm         : float
        min_sm          : float
        max_sm          : float
        dry_days        : int   (sm < SM_SECO)
        wet_days        : int   (sm > SM_HUMEDO)
        valid_smap_days : int   days with a real SMAP retrieval
        has_daymet      : bool  True when Daymet features were used
        model_backend   : str   "lstm_frozen" | "smap_smoothed"
    """
    # 1. Load SMAP series
    all_smap = _read_smap_csv(master_csv_path)
    if smap_id not in all_smap:
        raise ValueError(
            f"Plot '{smap_id}' not found in SMAP CSV. "
            f"Available IDs: {list(all_smap.keys())}"
        )

    plot_rows   = all_smap[smap_id]
    dates       = [r[0] for r in plot_rows]
    raw_sm      = np.array([r[1] for r in plot_rows], dtype=np.float64)
    valid_count = int(np.sum(~np.isnan(raw_sm)))

    # 2. Gap-fill SMAP (ffill → bfill, same as production_estimation.py line 83)
    sm_filled = _ffill_bfill(raw_sm, fallback=0.22).astype(np.float32)

    # 4. Load Daymet (if available)
    has_daymet = False
    daymet: dict[str, dict] = {}
    if daymet_csv_path:
        daymet     = _read_daymet_csv(daymet_csv_path, smap_id)
        has_daymet = len(daymet) > 0

    means = _load_feature_means()

    # 5. Build 4-feature matrix. The LSTM was trained on gap-filled raw SMAP,
    #    so it gets the same here (not the smoothed series).
    X_raw = _build_feature_matrix(dates, sm_filled, daymet, means)

    # 6. Load model + scalers
    model, feat_scaler, target_scaler = _load_artifacts()

    if model is not None and _WEIGHTS_PATH.exists():
        # Scale features with the TxSON-calibrated scaler (or fallback MinMax)
        if feat_scaler is not None:
            X_scaled = feat_scaler.transform(X_raw).astype(np.float32)
        else:
            # Approximate normalisation with known TxSON training ranges
            _feat_min = np.array([0.0,  -5.0, -20.0, 0.0],  dtype=np.float32)
            _feat_max = np.array([60.0,  45.0,  30.0, 0.6], dtype=np.float32)
            X_scaled  = np.clip(
                (X_raw - _feat_min) / (_feat_max - _feat_min + 1e-8), 0.0, 1.0
            ).astype(np.float32)

        sm_final      = _lstm_predict(model, X_scaled, target_scaler)
        backend_label = "lstm_frozen"
    else:
        # SMAP-only fallback: Hann-smoothed satellite series is the physical estimate
        sm_final      = _smooth(sm_filled, window=7)
        backend_label = "smap_smoothed"

    sm_list = [round(float(v), 4) for v in sm_final]

    # 7. Preserve raw SMAP column for frontend transparency
    smap_raw_out = [
        None if np.isnan(raw_sm[i]) else round(float(raw_sm[i]), 4)
        for i in range(len(raw_sm))
    ]

    return {
        "dates":           dates,
        "soil_moisture":   sm_list,
        "smap_raw":        smap_raw_out,
        "mean_sm":         round(float(np.mean(sm_final)), 4),
        "min_sm":          round(float(np.min(sm_final)),  4),
        "max_sm":          round(float(np.max(sm_final)),  4),
        "dry_days":        int(np.sum(sm_final < SM_SECO)),
        "wet_days":        int(np.sum(sm_final > SM_HUMEDO)),
        "valid_smap_days": valid_count,
        "has_daymet":      has_daymet,
        "model_backend":   backend_label,
    }
