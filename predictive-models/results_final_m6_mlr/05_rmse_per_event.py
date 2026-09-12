# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
@file 05_rmse_per_event.py
@brief REQM (RMSE) per test event breakdown — M4 LightGBM vs M6 MLR (Issue #138).

Computes, for each test event and each prediction horizon (+30/+60/
+90/+120 min), the Root Mean Square Error between predicted and actual level.
Produces a 2×2 subplot figure (one panel per horizon) with grouped bars for
M4 and M6 side by side, enabling direct comparison at the event level.

The existing compare_m4_vs_m6.png shows only aggregate RMSE by horizon; this
script exposes the per-event distribution needed for the results narrative.

Input files:
  results_final_m4_lgbm/output/continuous_predictions.csv
  results_final_m6_mlr/output/continuous_predictions_m6.csv
  results_final_m4_lgbm/event_windows_v3.csv (via config.EVENTS_CSV)

Output (results_final_m6_mlr/output/):
  rmse_per_event_m4_vs_m6.png   — 2×2 subplot, one panel per horizon
  rmse_per_event.csv             — tabular RMSE values

Usage (run from the results_final_m6_mlr/ folder):

    cd AppTest/raspberry/predictive_model_darts/results_final_m6_mlr/
    python3 05_rmse_per_event.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M4_DIR = os.path.join(_HERE, "..", "results_final_m4_lgbm")
sys.path.insert(0, _HERE)
import config
import real_utils

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

M4_PREDS_CSV = os.path.join(_M4_DIR, "output", "continuous_predictions.csv")
M6_PREDS_CSV = os.path.join(_HERE, "output", "continuous_predictions_m6.csv")
EVENTS_CSV = config.EVENTS_CSV
"""Only used for the log line: the catalogue itself is loaded through
real_utils.load_event_catalogue(). The hardcoded v2 path used to make the log
claim the superseded catalogue had been read, while the data was already v3."""

COLOR_M4 = "#1565C0"  # dark blue for M4 LightGBM
COLOR_M6 = "#2E7D32"  # dark green for M6 MLR

# ---------------------------------------------------------------------------
# RMSE helpers
# ---------------------------------------------------------------------------


def _rmse(predicted: pd.Series, actual: pd.Series) -> float:
    """Compute RMSE ignoring NaN pairs.

    @param predicted  Predicted level values.
    @param actual     Actual observed level values at the future timestep.
    @return           RMSE in cm, or NaN if fewer than 3 valid pairs exist.
    """
    mask = predicted.notna() & actual.notna()
    if mask.sum() < 3:
        return np.nan
    return float(np.sqrt(np.mean((predicted[mask] - actual[mask]) ** 2)))


def compute_rmse_per_event(
    df_preds: pd.DataFrame,
    df_events: pd.DataFrame,
    model_label: str,
) -> pd.DataFrame:
    """Compute RMSE for each test event and each prediction horizon.

    @param df_preds     Continuous predictions DataFrame (timestamp, h_pred_XX,
                        h_actual_XX for each horizon XX in HORIZONS_MIN).
    @param df_events    Event windows catalogue DataFrame.
    @param model_label  Short label for the model ('M4' or 'M6').
    @return             DataFrame with columns: model, event_num, peak_cm,
                        rmse_30, rmse_60, rmse_90, rmse_120.
    """
    test_events = df_events[df_events["split_set"] == "test"].copy()
    records: list[dict] = []

    for _, evt in test_events.iterrows():
        event_num = int(evt["event_num"])
        analysis_start = pd.Timestamp(evt["analysis_start"])
        analysis_end = pd.Timestamp(evt["analysis_end"])
        peak_cm = float(evt["peak_cm"])

        mask = (df_preds["timestamp"] >= analysis_start) & (
            df_preds["timestamp"] <= analysis_end
        )
        grp = df_preds[mask].copy()

        row: dict = {
            "model": model_label,
            "event_num": event_num,
            "peak_cm": peak_cm,
        }
        for h in config.HORIZONS_MIN:
            pred_col = f"h_pred_{h}"
            actual_col = f"h_actual_{h}"
            if pred_col not in grp.columns or actual_col not in grp.columns:
                row[f"rmse_{h}"] = np.nan
            else:
                row[f"rmse_{h}"] = _rmse(grp[pred_col], grp[actual_col])
        records.append(row)

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_rmse_per_event(df_m4: pd.DataFrame, df_m6: pd.DataFrame, out_dir: str) -> None:
    """Produce a 2×2 subplot with RMSE per test event for M4 vs M6.

    Each panel corresponds to one prediction horizon (+30/+60/+90/+120 min).
    Bars are side by side (M4 blue, M6 green).  Events are ordered by event_num
    and labelled with E-number and peak cota.

    @param df_m4    RMSE table for M4 (output of compute_rmse_per_event).
    @param df_m6    RMSE table for M6.
    @param out_dir  Directory where the PNG is written.
    """
    horizons = config.HORIZONS_MIN
    events = df_m4["event_num"].values
    n = len(events)
    x = np.arange(n)
    bar_w = 0.38

    event_labels = [
        f"E{int(enum):02d}\n{int(pk)} cm"
        for enum, pk in zip(df_m4["event_num"], df_m4["peak_cm"])
    ]

    fig, axes = plt.subplots(2, 2, figsize=(18, 10), sharey=False)
    axes_flat = axes.flatten()

    for ax, h in zip(axes_flat, horizons):
        col_h = f"rmse_{h}"
        v4 = df_m4[col_h].values
        v6 = df_m6.set_index("event_num").reindex(events)[col_h].values

        b4 = ax.bar(
            x - bar_w / 2,
            v4,
            bar_w,
            label="M4 LightGBM",
            color=COLOR_M4,
            alpha=0.80,
            edgecolor="white",
            linewidth=0.5,
        )
        b6 = ax.bar(
            x + bar_w / 2,
            v6,
            bar_w,
            label="M6 MLR",
            color=COLOR_M6,
            alpha=0.80,
            edgecolor="white",
            linewidth=0.5,
        )

        # Value labels on top of bars
        for bar, val in zip(b4, v4):
            if not np.isnan(val):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    f"{val:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    color=COLOR_M4,
                    fontweight="bold",
                )
        for bar, val in zip(b6, v6):
            if not np.isnan(val):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    f"{val:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    color=COLOR_M6,
                    fontweight="bold",
                )

        ax.set_xticks(x)
        ax.set_xticklabels(event_labels, fontsize=7)
        ax.set_ylabel("REQM (cm)", fontsize=9)
        ax.set_title(f"Horizonte +{h} min", fontsize=10, fontweight="bold")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(axis="y", alpha=0.3, linestyle=":")
        ax.set_ylim(bottom=0)

    fig.suptitle(
        "REQM por Evento de Teste — M4 LightGBM vs M6 Regressão Linear Múltipla\n"
        f"{n} eventos de teste (fora da amostra), {len(horizons)} horizontes de previsão",
        fontsize=12,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    path = os.path.join(out_dir, "rmse_per_event_m4_vs_m6.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"  Saved {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Compute and save RMSE per test event for M4 and M6."""
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 66)
    print("  REQM por Evento — M4 vs M6 (Issue #138)")
    print("=" * 66)

    # ── 1. Load predictions ───────────────────────────────────────────────────
    for csv_path, label in [(M4_PREDS_CSV, "M4"), (M6_PREDS_CSV, "M6")]:
        if not os.path.exists(csv_path):
            print(f"  [ERROR] {label} predictions not found: {csv_path}")
            sys.exit(1)

    print(f"\n[1/3] Loading M4 predictions:\n  {M4_PREDS_CSV}")
    df_m4_preds = pd.read_csv(M4_PREDS_CSV, parse_dates=["timestamp"])
    print(f"  {len(df_m4_preds):,} rows")

    print(f"\n[2/3] Loading M6 predictions:\n  {M6_PREDS_CSV}")
    df_m6_preds = pd.read_csv(M6_PREDS_CSV, parse_dates=["timestamp"])
    print(f"  {len(df_m6_preds):,} rows")

    print(f"\n[3/3] Loading event catalogue:\n  {EVENTS_CSV}")
    # Via real_utils so the effective train/test split matches the mode the
    # model was actually fitted with (Issue #223).
    df_events = real_utils.load_event_catalogue()
    n_test = (df_events["split_set"] == "test").sum()
    print(f"  {len(df_events)} events ({n_test} test).")

    # ── 2. Compute RMSE ───────────────────────────────────────────────────────
    print("\nComputing RMSE per event ...")
    df_rmse_m4 = compute_rmse_per_event(df_m4_preds, df_events, "M4")
    df_rmse_m6 = compute_rmse_per_event(df_m6_preds, df_events, "M6")

    df_combined = pd.concat([df_rmse_m4, df_rmse_m6], ignore_index=True)

    print("\nRMSE summary (test events):")
    for h in config.HORIZONS_MIN:
        col = f"rmse_{h}"
        m4_mean = df_rmse_m4[col].mean()
        m6_mean = df_rmse_m6[col].mean()
        print(f"  +{h:3d} min  M4={m4_mean:5.2f} cm   M6={m6_mean:5.2f} cm")

    # ── 3. Save CSV ───────────────────────────────────────────────────────────
    csv_path = os.path.join(out_dir, "rmse_per_event.csv")
    df_combined.to_csv(csv_path, index=False)
    print(f"\n  Saved {csv_path}")

    # ── 4. Save plot ──────────────────────────────────────────────────────────
    plot_rmse_per_event(df_rmse_m4, df_rmse_m6, out_dir)

    print(f"\nAll outputs in: {out_dir}")
    print("=== REQM POR EVENTO DONE ===\n")


if __name__ == "__main__":
    main()
