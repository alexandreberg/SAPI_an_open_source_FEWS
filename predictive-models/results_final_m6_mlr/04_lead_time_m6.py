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
@file 04_lead_time_m6.py
@brief Lead time (advance warning) analysis for the M6 LinearRegressionModel.

Computes, for each test event × alert threshold × threshold-crossing
occurrence × prediction horizon, how many minutes before the observed crossing
the model's persistent alarm fired. Positive = early warning; negative = late.
The rule lives in results_final_m4_lgbm/lead_time_utils.py (Issue #229) and is
shared with 04_lead_time_m4.py and plot_events_audit_pdf.py, so M4 and M6 are
measured identically.

Input files:
  results_final_m6_mlr/output/continuous_predictions_m6.csv
  config.EVENTS_CSV   (shared catalogue, via real_utils.load_event_catalogue())

Output (results_final_m6_mlr/output/):
  lead_time_summary_m6.csv          — one row per event × threshold × occurrence
  lead_time_atencao_m6.png
  lead_time_alerta_m6.png
  lead_time_inundacao_m6.png

Usage (run from the results_final_m6_mlr/ folder):

    cd AppTest/raspberry/predictive_model_darts/results_final_m6_mlr/
    python3 04_lead_time_m6.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M4_DIR = os.path.join(_HERE, "..", "results_final_m4_lgbm")
sys.path.insert(0, _HERE)
# Appended (not prepended) so this folder's config/real_utils still win; only
# lead_time_utils, which reads no config, comes from the M4 folder.
sys.path.append(_M4_DIR)
import config
import lead_time_utils
import real_utils

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREDS_CSV = os.path.join(_HERE, "output", "continuous_predictions_m6.csv")
EVENTS_CSV = config.EVENTS_CSV

THRESHOLDS = {
    "Atenção": config.THRESHOLD_ATENCAO,
    "Alerta": config.THRESHOLD_ALERTA,
    "Inundação": config.THRESHOLD_INUNDACAO,
}

# ---------------------------------------------------------------------------
# Lead-time computation
# ---------------------------------------------------------------------------


def compute_lead_times(
    df_preds: pd.DataFrame,
    df_events: pd.DataFrame,
) -> pd.DataFrame:
    """Compute lead time (minutes) per test event × threshold × occurrence × horizon.

    Delegates the rule to lead_time_utils.occurrence_lead_times() with the
    parameters in config (REARM_HYSTERESIS_CM, PRED_PERSISTENCE_STEPS,
    CAUSALITY_MAX_LEAD_MIN) — see that module's docstring (Issue #229).
    Only thresholds the observed level actually crosses produce rows.

    @param df_preds   Continuous predictions DataFrame with columns: timestamp,
                      h_obs, h_pred_30, h_pred_60, h_pred_90, h_pred_120.
    @param df_events  Event windows catalogue DataFrame.
    @return           DataFrame with columns: event_num, peak_cm, threshold_name,
                      threshold_cm, occurrence, n_occurrences, t_obs,
                      at_window_start, search_start, search_end and, per
                      horizon H, lead_time_<H>min, active_<H>min, fire_<H>min.
    """
    test_events = df_events[df_events["split_set"] == "test"].copy()
    df_idx = df_preds.set_index("timestamp").sort_index()

    records: list[dict] = []
    for level_name, threshold_cm in THRESHOLDS.items():
        for _, evt in test_events.iterrows():
            rows = lead_time_utils.occurrence_lead_times(
                df_idx,
                pd.Timestamp(evt["analysis_start"]),
                pd.Timestamp(evt["analysis_end"]),
                threshold_cm,
                config.HORIZONS_MIN,
                config.REARM_HYSTERESIS_CM,
                config.PRED_PERSISTENCE_STEPS,
                config.CAUSALITY_MAX_LEAD_MIN,
            )
            for row in rows:
                records.append(
                    {
                        "event_num": int(evt["event_num"]),
                        "peak_cm": float(evt["peak_cm"]),
                        "threshold_name": level_name,
                        "threshold_cm": threshold_cm,
                        **row,
                    }
                )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

HORIZON_PALETTE = ["#d73027", "#fc8d59", "#4393c3", "#762a83"]
"""ColorBrewer divergent palette — perceptually distinct, readable in B&W.
+30 min = red, +60 min = light-orange, +90 min = blue, +120 min = purple.
"""

Y_CAP: dict[str, tuple[int, int]] = {
    "Atenção": (-60, 200),
    "Alerta": (-60, 200),
}
"""Y-axis cap per threshold level.  Inundação is left uncapped (only 4 events,
well-behaved scale).  Outlier bars are drawn to the cap limit and annotated
with the true value + directional arrow symbol (↑ / ↓)."""


def _plot_lead_time_single(
    df_lev: pd.DataFrame,
    level_name: str,
    threshold_cm: float,
    out_dir: str,
) -> None:
    """Save a grouped bar chart of advance-warning minutes for one alert level.

    Each bar group represents one event; each bar within the group is one
    prediction horizon.  Bar colour encodes the horizon (+30/+60/+90/+120 min)
    using a ColorBrewer divergent palette.  For Atenção and Alerta the Y-axis
    is capped at [-60, +200] min; bars that exceed the cap are drawn to the
    limit and annotated with the true value (Issue #144 Fix B).

    @param df_lev        Subset of compute_lead_times() for one threshold level.
    @param level_name    Human-readable alert level name (e.g. 'Inundação').
    @param threshold_cm  Threshold in cm (used in the chart title).
    @param out_dir       Directory where the PNG is written.
    """
    horizons = config.HORIZONS_MIN
    n_events = len(df_lev)
    n_horiz = len(horizons)
    width = 0.7 / n_horiz
    x = np.arange(n_events)
    y_cap = Y_CAP.get(level_name)  # None → free axis (Inundação)

    fig, ax = plt.subplots(figsize=(max(10, n_events * 1.4), 6))

    for i, (h, hcol) in enumerate(zip(horizons, HORIZON_PALETTE)):
        col = f"lead_time_{h}min"
        raw_vals = (
            df_lev[col].values if col in df_lev.columns else np.full(n_events, np.nan)
        )

        # Clip bar heights to cap boundary so bars stay inside the axes.
        if y_cap is not None:
            render_vals = np.where(
                np.isnan(raw_vals),
                np.nan,
                np.clip(raw_vals, y_cap[0], y_cap[1]),
            )
        else:
            render_vals = raw_vals

        bar_positions = x + (i - n_horiz / 2 + 0.5) * width
        ax.bar(
            bar_positions,
            render_vals,
            width,
            color=hcol,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.8,
        )

        for raw_v, rend_v, xpos in zip(raw_vals, render_vals, bar_positions):
            if np.isnan(raw_v):
                continue
            xc = xpos + width / 2

            if y_cap is not None and raw_v > y_cap[1]:
                # Positive overflow: annotate just inside top boundary
                ax.text(
                    xc,
                    y_cap[1] - 5,
                    f"↑{raw_v:.0f}",
                    ha="center",
                    va="top",
                    fontsize=6.5,
                    fontweight="bold",
                    color=hcol,
                )
            elif y_cap is not None and raw_v < y_cap[0]:
                # Negative overflow: annotate just inside bottom boundary
                ax.text(
                    xc,
                    y_cap[0] + 5,
                    f"↓{raw_v:.0f}",
                    ha="center",
                    va="bottom",
                    fontsize=6.5,
                    fontweight="bold",
                    color=hcol,
                )
            else:
                # Normal bar: show value adjacent to bar tip
                va = "bottom" if raw_v >= 0 else "top"
                off = 1 if raw_v >= 0 else -1
                ax.text(
                    xc,
                    rend_v + off,
                    f"{raw_v:.0f}",
                    ha="center",
                    va=va,
                    fontsize=7,
                    fontweight="bold",
                )

    ax.axhline(0, color="black", lw=1.2, zorder=3)

    if y_cap is not None:
        ax.set_ylim(y_cap[0] - 5, y_cap[1] + 15)

    ax.set_xticks(x)
    ax.set_xticklabels(
        [
            f"{lead_time_utils.occurrence_label(r.event_num, r.occurrence, r.n_occurrences)}"
            f"\n{r.peak_cm:.0f} cm"
            for r in df_lev.itertuples()
        ],
        fontsize=9,
    )
    ax.set_ylabel("Antecipação (min)  [+ = aviso antes  |  - = aviso após]")
    ax.set_title(
        f"M6 LinearRegressionModel — Tempo de antecipação  ≥ {threshold_cm:.0f} cm ({level_name})",
        fontsize=10,
    )

    legend_handles = [
        mpatches.Patch(color=c, label=f"+{h} min")
        for h, c in zip(horizons, HORIZON_PALETTE)
    ]
    ax.legend(handles=legend_handles, fontsize=8, ncol=4, loc="lower right")
    ax.grid(axis="y", alpha=0.4)
    fig.tight_layout()

    slug = level_name.lower().replace("ã", "a").replace("ç", "c")
    path = os.path.join(out_dir, f"lead_time_{slug}_m6.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def plot_lead_time_summary(df_lead: pd.DataFrame, out_dir: str) -> None:
    """Save one bar chart per alert level.

    @param df_lead  Output of compute_lead_times().
    @param out_dir  Output directory.
    """
    if df_lead.empty:
        print("  No events cross any threshold — lead-time charts skipped.")
        return
    for level_name, threshold_cm in THRESHOLDS.items():
        df_lev = df_lead[df_lead["threshold_name"] == level_name].copy()
        if df_lev.empty:
            print(
                f"  No test events cross {level_name} "
                f"({threshold_cm} cm) — chart skipped."
            )
            continue
        _plot_lead_time_single(df_lev, level_name, threshold_cm, out_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Compute and save M6 lead time analysis."""
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 66)
    print("  M6 LinearRegressionModel — Lead Time Analysis (Issue #125)")
    print("=" * 66)

    # ── 1. Load data ─────────────────────────────────────────────────────────
    print(f"\n[1/3] Loading continuous predictions:\n  {PREDS_CSV}")
    if not os.path.exists(PREDS_CSV):
        print(
            "  [ERROR] Predictions file not found.\n"
            "         Run 01_model6_mlr_continuous.py first."
        )
        sys.exit(1)
    df_preds = pd.read_csv(PREDS_CSV, parse_dates=["timestamp"])
    print(
        f"  Loaded {len(df_preds):,} rows  "
        f"({df_preds['timestamp'].min()} → {df_preds['timestamp'].max()})"
    )

    print(f"\n[2/3] Loading event catalogue:\n  {EVENTS_CSV}")
    # Via real_utils so the effective train/test split matches the mode the
    # model was actually fitted with (Issue #223).
    df_events = real_utils.load_event_catalogue()
    n_test = (df_events["split_set"] == "test").sum()
    print(f"  Loaded {len(df_events)} events ({n_test} test).")

    # ── 2. Compute lead times ────────────────────────────────────────────────
    print("\n[3/3] Computing lead times ...")
    df_lead = compute_lead_times(df_preds, df_events)

    if df_lead.empty:
        print("  [WARN] No lead-time records produced. Check prediction coverage.")
        return

    show = ["event_num", "occurrence", "t_obs"] + [
        f"lead_time_{h}min" for h in config.HORIZONS_MIN
    ]
    for level_name, threshold_cm in THRESHOLDS.items():
        sub = df_lead[df_lead["threshold_name"] == level_name]
        print(f"\n  {level_name} (>= {threshold_cm} cm) — {len(sub)} occurrence(s):")
        if not sub.empty:
            print(sub[show].to_string(index=False))

    # ── 3. Save CSV ───────────────────────────────────────────────────────────
    csv_path = os.path.join(out_dir, "lead_time_summary_m6.csv")
    df_lead.to_csv(csv_path, index=False)
    print(f"\n  Saved {csv_path}")

    # ── 4. Save plots ─────────────────────────────────────────────────────────
    plot_lead_time_summary(df_lead, out_dir)

    print(f"\nAll outputs in: {out_dir}")
    print("=== M6 LEAD TIME ANALYSIS DONE ===\n")


if __name__ == "__main__":
    main()
