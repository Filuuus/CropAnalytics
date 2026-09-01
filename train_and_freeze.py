"""
train_and_freeze.py — Production training script for Sentineli LSTM
=====================================================================

Replicates references/production_estimation.py exactly, but outputs
PyTorch artifacts instead of a Keras model so they're compatible with
the ml_engine.py inference handler.

Outputs (written to backend/api/ml/weights/):
  lstm_soil_moisture.pt   — model state_dict (frozen)
  feature_scaler.joblib   — MinMaxScaler fitted on training features
  target_scaler.joblib    — MinMaxScaler fitted on SWC_5 ground truth
  feature_means.json      — per-feature training means (Daymet fallback)

Architecture mirrors production_estimation.py:
  LSTM(input=4, hidden=64, layers=1) + Dropout(0.2) + Linear(64→32,ReLU) + Linear(32→1)
  Trained with Adam, MSE loss, 40 epochs, batch=32
  Features: [Precipitation, T_Max, T_Min, SMAP_Moisture]
  Target  : SWC_5 (5 cm volumetric soil water content from TxSON)
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT    = Path(__file__).resolve().parent
DATA_DIR     = REPO_ROOT / "references" / "datasets"
WEIGHTS_DIR  = REPO_ROOT / "backend" / "api" / "ml" / "weights"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

SMAP_CSV    = DATA_DIR / "TxSON_SMAP_Weather_Merged.csv"
STATION_CSV = DATA_DIR / "TxSON-Station-Files" / "Station1_filled_Data.csv"

# ---------------------------------------------------------------------------
# Hyper-parameters (identical to production_estimation.py)
# ---------------------------------------------------------------------------
LOOKBACK   = 14
HIDDEN     = 64
EPOCHS     = 40
BATCH_SIZE = 32
LR         = 1e-3
FEATURES   = ["Precipitation", "T_Max", "T_Min", "SMAP_Moisture"]
TARGET     = "SWC_5"
STATION_ID = "TXS01"

# ---------------------------------------------------------------------------
# 1. Load & merge data  (mirrors production_estimation.py §1–2)
# ---------------------------------------------------------------------------
print("Loading TxSON training data...")

df_feat = pd.read_csv(SMAP_CSV)
df_feat["Date"] = pd.to_datetime(df_feat["Date"])
txs01   = df_feat[df_feat["Station_ID"] == STATION_ID].copy()

df_tgt  = pd.read_csv(STATION_CSV)
df_tgt["Date"] = pd.to_datetime(df_tgt["Unnamed: 0"]).dt.normalize()
txs01_gt = df_tgt.groupby("Date")[[TARGET]].mean().reset_index()

train_df = (
    pd.merge(txs01, txs01_gt, on="Date", how="inner")
    .sort_values("Date")
    .reset_index(drop=True)
)

print(f"  Training period : {train_df['Date'].min().date()} → {train_df['Date'].max().date()}")
print(f"  Training samples: {len(train_df)}")

# ---------------------------------------------------------------------------
# 2. Fit scalers STRICTLY on training data
# ---------------------------------------------------------------------------
feature_scaler = MinMaxScaler(feature_range=(0, 1))
target_scaler  = MinMaxScaler(feature_range=(0, 1))

X_raw = train_df[FEATURES].values
y_raw = train_df[[TARGET]].values

X_scaled = feature_scaler.fit_transform(X_raw)
y_scaled = target_scaler.fit_transform(y_raw)

# ---------------------------------------------------------------------------
# 3. Build sequences
# ---------------------------------------------------------------------------
X_seq, y_seq = [], []
for i in range(LOOKBACK, len(X_scaled)):
    X_seq.append(X_scaled[i - LOOKBACK:i, :])
    y_seq.append(y_scaled[i, 0])

X_tensor = torch.tensor(np.array(X_seq), dtype=torch.float32)
y_tensor = torch.tensor(np.array(y_seq), dtype=torch.float32).unsqueeze(1)

print(f"  Sequence shape  : {X_tensor.shape}  →  target {y_tensor.shape}")

# ---------------------------------------------------------------------------
# 4. Model definition  (matches ml_engine._SoilMoistureLSTM exactly)
# ---------------------------------------------------------------------------
class SoilMoistureLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm    = nn.LSTM(input_size=4, hidden_size=HIDDEN,
                               num_layers=1, batch_first=True)
        self.dropout = nn.Dropout(0.2)
        self.head    = nn.Sequential(
            nn.Linear(HIDDEN, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        out, _ = self.lstm(x)
        out    = self.dropout(out)
        return self.head(out)          # (batch, seq, 1)

model     = SoilMoistureLSTM()
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
criterion = nn.MSELoss()

# ---------------------------------------------------------------------------
# 5. Training loop
# ---------------------------------------------------------------------------
print(f"\nTraining LSTM  ({EPOCHS} epochs, batch={BATCH_SIZE})...")
dataset  = torch.utils.data.TensorDataset(X_tensor, y_tensor)
loader   = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

model.train()
for epoch in range(1, EPOCHS + 1):
    epoch_loss = 0.0
    for xb, yb in loader:
        optimizer.zero_grad()
        # We need the last timestep of the sequence output
        pred = model(xb)[:, -1, :]    # (batch, 1)
        loss = criterion(pred, yb)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item() * len(xb)
    avg = epoch_loss / len(dataset)
    if epoch % 10 == 0 or epoch == 1:
        print(f"  Epoch {epoch:>3}/{EPOCHS}  MSE={avg:.6f}")

# ---------------------------------------------------------------------------
# 6. Quick validation (last 20% of training data as hold-out)
# ---------------------------------------------------------------------------
model.eval()
split = int(len(X_tensor) * 0.8)
X_val, y_val = X_tensor[split:], y_tensor[split:]

with torch.no_grad():
    val_pred_scaled = model(X_val)[:, -1, :].numpy()

val_pred = target_scaler.inverse_transform(val_pred_scaled).flatten()
val_true = target_scaler.inverse_transform(y_val.numpy()).flatten()

rmse = float(np.sqrt(np.mean((val_pred - val_true) ** 2)))
ss_res = np.sum((val_true - val_pred) ** 2)
ss_tot = np.sum((val_true - val_true.mean()) ** 2)
r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

print(f"\nValidation (last 20% of training data):")
print(f"  RMSE : {rmse:.4f} m³/m³")
print(f"  R²   : {r2:.4f}")

# ---------------------------------------------------------------------------
# 7. Freeze & save artifacts
# ---------------------------------------------------------------------------
for p in model.parameters():
    p.requires_grad = False
model.eval()

pt_path      = WEIGHTS_DIR / "lstm_soil_moisture.pt"
feat_path    = WEIGHTS_DIR / "feature_scaler.joblib"
target_path  = WEIGHTS_DIR / "target_scaler.joblib"
means_path   = WEIGHTS_DIR / "feature_means.json"

torch.save(model.state_dict(), pt_path)
joblib.dump(feature_scaler, feat_path)
joblib.dump(target_scaler,  target_path)

feature_means = {feat: float(train_df[feat].mean()) for feat in FEATURES[:3]}
with open(means_path, "w") as fh:
    json.dump(feature_means, fh, indent=2)

print(f"\nArtifacts saved to {WEIGHTS_DIR}/")
print(f"  {pt_path.name}")
print(f"  {feat_path.name}")
print(f"  {target_path.name}")
print(f"  {means_path.name}")
print(f"\nFeature means (Daymet fallback): {feature_means}")
