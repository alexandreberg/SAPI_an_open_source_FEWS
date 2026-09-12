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
@file 06_compare_fullsim.py
@brief REQM da simulação contínua completa para M4 LightGBM vs M6 MLR (Issue #140).

Generates compare_m4_vs_m6_fullsim.png — RMSE computed over the full continuous
backtesting run (~133,000 steps, Dec/2024 – May/2026), without any precipitation
gate or debounce filter.  This matches the values in the dissertation table
tab:rmse_comparativo and must be used as the figure accompanying that table.

The existing compare_m4_vs_m6.png was generated with stale directory paths
(real_data_v3_continuous, which was later renamed to results_final_m4_lgbm).
This script uses the current canonical paths and intersects both model timelines
so that RMSE is computed over exactly the same set of timestamps for both models.

Expected sanity values (updated 2026-09-11 after the Issue #124 Station-02
rain spread, on top of the #227 artifact exclusion — see EXPECTED below):
  M4 LightGBM:  +30=1.00  +60=1.45  +90=1.67  +120=1.81 cm
  M6 MLR:       +30=0.97  +60=1.51  +90=1.92  +120=2.22 cm

Values after #227 and before #124, for reference:
  M4 LightGBM:  +30=1.00  +60=1.36  +90=1.61  +120=1.83 cm
  M6 MLR:       +30=0.97  +60=1.52  +90=1.93  +120=2.24 cm

Part of the #227 drop from the previous values is a population change, not a
model change: the 9 artifact windows (large errors) are now blanked out of
the series. For a like-for-like before/after, compare the out-of-sample slice
only — see Documentation/predictive_model/artefatos_catalogo_v3.md.

Values after the Issue #223 fix (2026-09-09, v2 catalogue), for reference:
  M4 LightGBM:  +30=1.31  +60=1.62  +90=1.76  +120=1.82 cm
  M6 MLR:       +30=1.30  +60=1.81  +90=2.15  +120=2.38 cm

CAVEAT — do not read the M4-vs-M6 ranking off these numbers. This RMSE spans
the FULL continuous series, which under TRAIN_MODE="continuous" includes the
training period, so it rewards in-sample fit: M4 looks better here purely
because a 500-tree ensemble fits its training window far more tightly than a
linear model (in-sample +120: 0.97 vs 2.23 cm). On the out-of-sample slice
the ranking reverses: M6 is better at every horizon (+30: 0.71 vs 1.10 cm,
+120: 2.18 vs 2.61 cm, 2026-09-11 after #124). Use
scan_audit_findings.py --calibration, which splits in-sample from
out-of-sample, for any claim about relative model performance.

Previous values, before the Issue #223 fix, for reference:
  M4 LightGBM:  +30=11.83  +60=30.32  +90=40.69  +120=34.51 cm
  M6 MLR:       +30=4.04   +60=9.53   +90=12.91  +120=14.34 cm

Input files:
  results_final_m4_lgbm/output/continuous_predictions.csv
  results_final_m6_mlr/output/continuous_predictions_m6.csv

Output (results_final_m6_mlr/output/):
  compare_m4_vs_m6_fullsim.png
  compare_m4_vs_m6_fullsim.csv   — tabular RMSE values for reference

Usage (run from the results_final_m6_mlr/ folder):

    cd AppTest/raspberry/predictive_model_darts/results_final_m6_mlr/
    python3 06_compare_fullsim.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M4_DIR = os.path.join(_HERE, "..", "results_final_m4_lgbm")
sys.path.insert(0, _HERE)
import config

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

M4_PREDS_CSV = os.path.join(_M4_DIR, "output", "continuous_predictions.csv")
M6_PREDS_CSV = os.path.join(_HERE, "output", "continuous_predictions_m6.csv")
OUT_PNG = os.path.join(config.OUTPUT_DIR, "compare_m4_vs_m6_fullsim.png")
OUT_CSV = os.path.join(config.OUTPUT_DIR, "compare_m4_vs_m6_fullsim.csv")

# Expected values (sanity check tolerance: 0.05 cm). Updated 2026-09-11 after
# the Issue #124 Station-02 rain spread, on top of the #227 artifact exclusion
# on the v3 catalogue (60/75/90 cm) — the pre-fix dissertation table values are
# stale and will no longer match; see
# Documentation/predictive_model/base_reescrita_dissertacao.md.
EXPECTED = {
    "M4": {30: 1.003, 60: 1.448, 90: 1.671, 120: 1.806},
    "M6": {30: 0.968, 60: 1.510, 90: 1.917, 120: 2.216},
}
SANITY_TOL = 0.05  # cm — warn if computed RMSE deviates more than this

COLORS = {
    "M4 LightGBM": "#1565C0",
    "M6 MLR": "#6A1B9A",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_fullsim_rmse(
    df_m4: pd.DataFrame,
    df_m6: pd.DataFrame,
) -> tuple[dict[int, float], dict[int, float], int]:
    """Compute full-simulation RMSE per horizon over the common time window.

    Aligns both DataFrames on timestamp (inner join) so that RMSE is computed
    over exactly the same set of steps for M4 and M6.  Only rows where both
    h_pred_H and h_actual_H are non-NaN for the given model are included.

    @param df_m4  M4 continuous predictions DataFrame.
    @param df_m6  M6 continuous predictions DataFrame.
    @return Tuple: (rmse_m4, rmse_m6, n_common_rows) where rmse_XX is
            Dict {horizon_min: rmse_cm}.
    """
    # Align on timestamp (inner join keeps only timestamps present in both)
    df_m4 = df_m4.set_index("timestamp")
    df_m6 = df_m6.set_index("timestamp")
    common_idx = df_m4.index.intersection(df_m6.index)
    n_common = len(common_idx)

    df_m4c = df_m4.loc[common_idx]
    df_m6c = df_m6.loc[common_idx]

    rmse_m4: dict[int, float] = {}
    rmse_m6: dict[int, float] = {}

    for h in config.HORIZONS_MIN:
        pred_col = f"h_pred_{h}"
        actual_col = f"h_actual_{h}"

        for label, df, rmse_dict in [("M4", df_m4c, rmse_m4), ("M6", df_m6c, rmse_m6)]:
            if pred_col not in df.columns or actual_col not in df.columns:
                rmse_dict[h] = np.nan
                print(f"  [WARN] {label}: columns {pred_col}/{actual_col} not found.")
                continue
            mask = df[pred_col].notna() & df[actual_col].notna()
            n = mask.sum()
            if n == 0:
                rmse_dict[h] = np.nan
                continue
            err = df.loc[mask, pred_col] - df.loc[mask, actual_col]
            val = float(np.sqrt((err**2).mean()))
            rmse_dict[h] = val
            print(f"  {label}  +{h:3d} min  RMSE={val:.3f} cm  (n={n:,})")

    return rmse_m4, rmse_m6, n_common


def sanity_check(
    rmse_m4: dict[int, float],
    rmse_m6: dict[int, float],
) -> bool:
    """Warn if computed values deviate from the dissertation table expectations.

    @param rmse_m4  Computed RMSE dict for M4.
    @param rmse_m6  Computed RMSE dict for M6.
    @return True if all values are within SANITY_TOL of expected; False otherwise.
    """
    ok = True
    for label, rmse, exp in [
        ("M4", rmse_m4, EXPECTED["M4"]),
        ("M6", rmse_m6, EXPECTED["M6"]),
    ]:
        for h, expected_val in exp.items():
            computed = rmse.get(h, np.nan)
            if np.isnan(computed):
                print(f"  [WARN] {label} +{h} min: NaN (expected {expected_val:.3f})")
                ok = False
                continue
            delta = abs(computed - expected_val)
            status = "OK" if delta <= SANITY_TOL else "WARN"
            print(
                f"  [{status}] {label} +{h:3d} min: computed={computed:.3f}  "
                f"expected={expected_val:.3f}  Δ={delta:.3f} cm"
            )
            if delta > SANITY_TOL:
                ok = False
    return ok


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_fullsim(
    rmse_m4: dict[int, float],
    rmse_m6: dict[int, float],
    n_common: int,
    out_png: str,
) -> None:
    """Save grouped bar chart of full-simulation RMSE for M4 vs M6.

    @param rmse_m4   RMSE dict for M4 {horizon_min: rmse_cm}.
    @param rmse_m6   RMSE dict for M6 {horizon_min: rmse_cm}.
    @param n_common  Number of common timestamps used in computation.
    @param out_png   Full output path for the PNG.
    """
    horizons = config.HORIZONS_MIN
    x = np.arange(len(horizons))
    bar_w = 0.35

    vals_m4 = [rmse_m4.get(h, np.nan) for h in horizons]
    vals_m6 = [rmse_m6.get(h, np.nan) for h in horizons]

    fig, ax = plt.subplots(figsize=(9, 6))

    bars_m4 = ax.bar(
        x - bar_w / 2,
        vals_m4,
        bar_w,
        color=COLORS["M4 LightGBM"],
        label="M4 LightGBM",
        alpha=0.88,
        edgecolor="white",
        linewidth=0.6,
    )
    bars_m6 = ax.bar(
        x + bar_w / 2,
        vals_m6,
        bar_w,
        color=COLORS["M6 MLR"],
        label="M6 Reg. Linear Múltipla",
        alpha=0.88,
        edgecolor="white",
        linewidth=0.6,
    )

    for bars, vals, color in [
        (bars_m4, vals_m4, COLORS["M4 LightGBM"]),
        (bars_m6, vals_m6, COLORS["M6 MLR"]),
    ]:
        for bar, v in zip(bars, vals):
            if not np.isnan(v):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.25,
                    f"{v:.2f} cm",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    fontweight="bold",
                    color=color,
                )

    ax.set_xticks(x)
    ax.set_xticklabels([f"+{h} min" for h in horizons], fontsize=11)
    ax.set_ylabel("REQM (cm)", fontsize=11)
    ax.set_xlabel("Horizonte de Previsão", fontsize=11)
    ax.set_title(
        "REQM por Horizonte — Simulação Contínua Completa\n"
        f"M4 LightGBM vs M6 Regressão Linear Múltipla  "
        f"({n_common:,} passos de 5 min, dez/2024–mai/2026)",
        fontsize=10,
        fontweight="bold",
    )
    ax.legend(fontsize=10)
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax.grid(axis="y", which="major", ls="-", lw=0.5, alpha=0.45)
    ax.grid(axis="y", which="minor", ls="--", lw=0.3, alpha=0.3)
    ax.set_ylim(bottom=0)

    fig.tight_layout()
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out_png}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Compute full-simulation RMSE and generate the comparison figure."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    print("=" * 66)
    print("  REQM Simulação Contínua Completa — M4 vs M6 (Issue #140)")
    print("=" * 66)

    # ── 1. Load predictions ───────────────────────────────────────────────────
    for csv_path, label in [(M4_PREDS_CSV, "M4"), (M6_PREDS_CSV, "M6")]:
        if not os.path.exists(csv_path):
            print(f"  [ERROR] {label} predictions not found:\n  {csv_path}")
            sys.exit(1)

    print(f"\n[1/4] Loading M4 predictions:\n  {M4_PREDS_CSV}")
    df_m4 = pd.read_csv(M4_PREDS_CSV, parse_dates=["timestamp"])
    print(
        f"  {len(df_m4):,} rows  ({df_m4['timestamp'].min()} → {df_m4['timestamp'].max()})"
    )

    print(f"\n[2/4] Loading M6 predictions:\n  {M6_PREDS_CSV}")
    df_m6 = pd.read_csv(M6_PREDS_CSV, parse_dates=["timestamp"])
    print(
        f"  {len(df_m6):,} rows  ({df_m6['timestamp'].min()} → {df_m6['timestamp'].max()})"
    )

    # ── 2. Compute RMSE ───────────────────────────────────────────────────────
    print("\n[3/4] Computing full-simulation RMSE (intersecting timelines) ...")
    rmse_m4, rmse_m6, n_common = compute_fullsim_rmse(df_m4, df_m6)
    print(f"\n  Common timestamps: {n_common:,}")

    # ── 3. Sanity check ───────────────────────────────────────────────────────
    print("\nSanity check against dissertation table values:")
    ok = sanity_check(rmse_m4, rmse_m6)
    if not ok:
        print(
            "\n  [WARN] Some values deviate from expected. "
            "Verify that the correct prediction CSVs are being used."
        )

    # ── 4. Save CSV ───────────────────────────────────────────────────────────
    rows = [
        {
            "horizonte_min": h,
            "REQM_M4_LightGBM_cm": round(rmse_m4.get(h, np.nan), 3),
            "REQM_M6_MLR_cm": round(rmse_m6.get(h, np.nan), 3),
        }
        for h in config.HORIZONS_MIN
    ]
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)
    print(f"\n  Saved {OUT_CSV}")

    # ── 5. Plot ───────────────────────────────────────────────────────────────
    print("\n[4/4] Generating figure ...")
    plot_fullsim(rmse_m4, rmse_m6, n_common, OUT_PNG)

    print(f"\nAll outputs in: {config.OUTPUT_DIR}")
    print("=== REQM FULLSIM DONE ===\n")


if __name__ == "__main__":
    main()
