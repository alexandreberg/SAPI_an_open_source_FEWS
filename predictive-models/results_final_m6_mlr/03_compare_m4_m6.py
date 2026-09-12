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
@file 03_compare_m4_m6.py
@brief M4 LightGBM vs M6 LinearRegressionModel comparison report.

Reads the validated outputs from both models and generates:
  1. RMSE bar chart by prediction horizon (+30/+60/+90/+120 min).
  2. Alert metric comparison table (Recall, Precision, FP count) at
     GATE_MM=5 mm / DEBOUNCE=3 steps — the operationally validated setting.
  3. Lead time comparison (advance warning minutes) per event and threshold —
     requires lead_time_summary.csv (M4) and lead_time_summary_m6.csv (M6).
     Run real_data_v2/01_model4_real.py and 04_lead_time_m6.py first.

This produces the primary comparison figures for the dissertation.

After running both models:
  - M4: results_final_m4_lgbm/output/continuous_predictions.csv
        results_final_m4_lgbm/output/precip_gate_analysis.csv
        real_data_v2/output/lead_time_summary.csv
  - M6: results_final_m6_mlr/output/continuous_predictions_m6.csv
        results_final_m6_mlr/output/precip_gate_analysis_m6.csv
        results_final_m6_mlr/output/lead_time_summary_m6.csv

Usage (run from the results_final_m6_mlr/ folder):

    cd AppTest/raspberry/predictive_model_darts/results_final_m6_mlr/
    python3 03_compare_m4_m6.py

Output (results_final_m6_mlr/output/):

    compare_m4_vs_m6.png           — two-panel RMSE + alert metrics figure
    compare_m4_vs_m6.csv           — tabular summary (RMSE + alert metrics + lead time)
    lead_time_comparison_m4_vs_m6.png  — lead time comparison per threshold (3 panels)
"""

import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_M4_DIR = os.path.join(_HERE, "..", "results_final_m4_lgbm")
sys.path.insert(0, _HERE)
sys.path.append(_M4_DIR)  # for lead_time_utils only (reads no config)
import config
import lead_time_utils

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
from matplotlib.transforms import blended_transform_factory

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

M4_PREDS_CSV = os.path.join(_M4_DIR, "output", "continuous_predictions.csv")
M4_GATE_CSV = os.path.join(_M4_DIR, "output", "precip_gate_analysis.csv")
M4_LEAD_CSV = os.path.join(_M4_DIR, "output", "lead_time_summary_m4.csv")
M6_PREDS_CSV = os.path.join(_HERE, "output", "continuous_predictions_m6.csv")
M6_GATE_CSV = os.path.join(_HERE, "output", "precip_gate_analysis_m6.csv")
M6_LEAD_CSV = os.path.join(_HERE, "output", "lead_time_summary_m6.csv")

GATE_MM_OPERATIONAL = 5
DEBOUNCE_OPERATIONAL = 3

THRESHOLDS = {
    "Atenção": config.THRESHOLD_ATENCAO,
    "Alerta": config.THRESHOLD_ALERTA,
    "Inundação": config.THRESHOLD_INUNDACAO,
}

COLORS = {
    "M4 LightGBM": "#2166ac",  # blue — high-contrast M4/M6 (Issue #144)
    "M6 LinearRegression": "#d6604d",  # coral/orange — high-contrast M4/M6
}

COLOR_NEG = "#8B0000"
"""Dark red used for bars with negative lead time (late warnings) in both models."""

HORIZON_PALETTE = ["#d73027", "#fc8d59", "#4393c3", "#762a83"]
"""ColorBrewer divergent palette — one colour per prediction horizon.
H30 = red, H60 = orange, H90 = blue, H120 = purple.
Used in the lead-time comparison figure so colour encodes horizon, not model."""

# ---------------------------------------------------------------------------
# RMSE computation
# ---------------------------------------------------------------------------


def compute_rmse(df_preds: pd.DataFrame, label: str) -> dict[int, float]:
    """Compute RMSE per horizon from a continuous predictions DataFrame.

    Only rows where both h_pred_H and h_actual_H are non-NaN are used.

    @param df_preds  Continuous predictions DataFrame.
    @param label     Model label for logging.
    @return Dict {horizon_min: rmse_cm}.
    """
    rmse: dict[int, float] = {}
    for h in config.HORIZONS_MIN:
        pred_col = f"h_pred_{h}"
        actual_col = f"h_actual_{h}"
        if pred_col not in df_preds.columns or actual_col not in df_preds.columns:
            rmse[h] = np.nan
            continue
        mask = df_preds[pred_col].notna() & df_preds[actual_col].notna()
        n = mask.sum()
        if n == 0:
            rmse[h] = np.nan
            continue
        err = df_preds.loc[mask, pred_col] - df_preds.loc[mask, actual_col]
        rmse[h] = float(np.sqrt((err**2).mean()))
        print(f"  {label}  +{h:3d} min  RMSE={rmse[h]:.2f} cm  (n={n:,})")
    return rmse


# ---------------------------------------------------------------------------
# Alert metrics extraction
# ---------------------------------------------------------------------------


def extract_alert_metrics(gate_csv_path: str, label: str) -> pd.DataFrame:
    """Extract VP/FP/FN/recall/precision for GATE_MM_OPERATIONAL × DEBOUNCE_OPERATIONAL.

    @param gate_csv_path  Path to precip_gate_analysis CSV.
    @param label          Model label for logging.
    @return DataFrame with columns: threshold_name, VP, FP, FN, recall, precision.
    """
    if not os.path.exists(gate_csv_path):
        print(f"  [WARN] {gate_csv_path} not found — metrics will be NaN.")
        return pd.DataFrame()

    df = pd.read_csv(gate_csv_path)
    mask = (df["gate_mm"] == GATE_MM_OPERATIONAL) & (
        df["debounce_steps"] == DEBOUNCE_OPERATIONAL
    )
    subset = df[mask][
        ["threshold_name", "VP", "FP", "FN", "recall", "precision"]
    ].copy()
    subset = subset.reset_index(drop=True)

    for _, row in subset.iterrows():
        print(
            f"  {label}  {row['threshold_name']:10s}  "
            f"VP={row['VP']}  FP={row['FP']}  FN={row['FN']}  "
            f"recall={row['recall']}  precision={row['precision']}"
        )
    return subset


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def plot_comparison(
    rmse_m4: dict[int, float],
    rmse_m6: dict[int, float],
    metrics_m4: pd.DataFrame,
    metrics_m6: pd.DataFrame,
    out_dir: str,
) -> None:
    """Generate the two-panel comparison figure.

    Panel 1 — RMSE bar chart by horizon.
    Panel 2 — Alert metrics table (Recall and FP count at gate=5mm, debounce=3).

    @param rmse_m4     RMSE dict for M4 {horizon_min: rmse_cm}.
    @param rmse_m6     RMSE dict for M6 {horizon_min: rmse_cm}.
    @param metrics_m4  Alert metrics DataFrame for M4.
    @param metrics_m6  Alert metrics DataFrame for M6.
    @param out_dir     Output directory.
    """
    horizons = config.HORIZONS_MIN
    x = np.arange(len(horizons))
    bar_w = 0.35

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # ── Panel 1: RMSE by horizon ─────────────────────────────────────────────
    vals_m4 = [rmse_m4.get(h, np.nan) for h in horizons]
    vals_m6 = [rmse_m6.get(h, np.nan) for h in horizons]

    bars_m4 = ax1.bar(
        x - bar_w / 2,
        vals_m4,
        bar_w,
        color=COLORS["M4 LightGBM"],
        label="M4 LightGBM",
        alpha=0.85,
        edgecolor="white",
        linewidth=0.6,
    )
    bars_m6 = ax1.bar(
        x + bar_w / 2,
        vals_m6,
        bar_w,
        color=COLORS["M6 LinearRegression"],
        label="M6 LinearRegression",
        alpha=0.85,
        edgecolor="white",
        linewidth=0.6,
    )

    for bars, vals in [(bars_m4, vals_m4), (bars_m6, vals_m6)]:
        for bar, v in zip(bars, vals):
            if not np.isnan(v):
                ax1.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.05,
                    f"{v:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                )

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"+{h} min" for h in horizons])
    ax1.set_ylabel("RMSE (cm)")
    ax1.set_xlabel("Horizonte de Previsão")
    ax1.set_title(
        "RMSE por Horizonte\n(Simulado Contínuo — todos os passos)",
        fontsize=10,
        fontweight="bold",
    )
    ax1.legend(fontsize=9)
    ax1.yaxis.set_minor_locator(mticker.AutoMinorLocator())
    ax1.grid(axis="y", which="major", ls="-", lw=0.5, alpha=0.5)
    ax1.grid(axis="y", which="minor", ls="--", lw=0.3, alpha=0.35)

    # ── Panel 2: Alert metrics table ─────────────────────────────────────────
    ax2.axis("off")

    threshold_order = ["Atenção", "Alerta", "Inundação"]

    def _row(metrics: pd.DataFrame, thresh_name: str, col: str) -> str:
        if metrics.empty:
            return "—"
        match = metrics[metrics["threshold_name"] == thresh_name]
        if match.empty:
            return "—"
        v = match.iloc[0][col]
        if pd.isna(v):
            return "—"
        if col in ("VP", "FP", "FN"):
            return str(int(v))
        return f"{float(v):.3f}"

    col_labels = [
        "Threshold",
        "Model",
        "VP",
        "FP",
        "FN",
        "Recall",
        "Precision",
    ]

    table_data = []
    for thresh_name in threshold_order:
        table_data.append(
            [
                thresh_name,
                "M4 LightGBM",
                _row(metrics_m4, thresh_name, "VP"),
                _row(metrics_m4, thresh_name, "FP"),
                _row(metrics_m4, thresh_name, "FN"),
                _row(metrics_m4, thresh_name, "recall"),
                _row(metrics_m4, thresh_name, "precision"),
            ]
        )
        table_data.append(
            [
                "",
                "M6 LinearReg.",
                _row(metrics_m6, thresh_name, "VP"),
                _row(metrics_m6, thresh_name, "FP"),
                _row(metrics_m6, thresh_name, "FN"),
                _row(metrics_m6, thresh_name, "recall"),
                _row(metrics_m6, thresh_name, "precision"),
            ]
        )

    tbl = ax2.table(
        cellText=table_data,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.2, 1.6)

    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#37474F")
            cell.set_text_props(color="white", fontweight="bold")
        elif row % 2 == 1:
            cell.set_facecolor(COLORS["M4 LightGBM"] + "22")
        else:
            cell.set_facecolor(COLORS["M6 LinearRegression"] + "22")

    ax2.set_title(
        f"Métricas de Alerta\n"
        f"(gate = {GATE_MM_OPERATIONAL} mm/6h, debounce = {DEBOUNCE_OPERATIONAL} passos)",
        fontsize=10,
        fontweight="bold",
        pad=12,
    )

    fig.suptitle(
        "Comparação M4 LightGBM vs M6 LinearRegressionModel (Darts)\n"
        "Parâmetros idênticos — apenas o algoritmo de aprendizado difere",
        fontsize=11,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.93])

    out_png = os.path.join(out_dir, "compare_m4_vs_m6.png")
    fig.savefig(out_png, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out_png}")


# ---------------------------------------------------------------------------
# Lead time comparison
# ---------------------------------------------------------------------------


def load_lead_times(csv_path: str, label: str) -> pd.DataFrame:
    """Load a lead_time_summary CSV and return an empty DataFrame on missing file.

    @param csv_path  Path to the lead time summary CSV.
    @param label     Model label used in log messages.
    @return          Lead time DataFrame or empty DataFrame if file is absent.
    """
    if not os.path.exists(csv_path):
        print(
            f"  [WARN] Lead time CSV not found for {label}:\n"
            f"         {csv_path}\n"
            f"         Run the corresponding lead time script first."
        )
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    # Since Issue #229 each row is one threshold-crossing occurrence; older
    # CSVs (one row per event) are read as a single occurrence per event.
    if "occurrence" not in df.columns:
        df["occurrence"] = 1
        df["n_occurrences"] = 1
    n = len(df)
    print(f"  {label}: {n} records loaded from {csv_path}")
    return df


Y_BOTTOM = -65
"""Fixed lower bound (min) for all lead-time comparison panels."""


def plot_lead_time_comparison(
    df_m4: pd.DataFrame,
    df_m6: pd.DataFrame,
    out_dir: str,
) -> None:
    """Save a three-panel figure comparing M4 vs M6 lead times per threshold.

    Redesigned for Issue #148 (Option A — fixed positions):
    - Each event shows 8 fixed bar slots: M4 [H30 H60 H90 H120] | M6 [H30 H60 H90 H120]
    - Colour encodes prediction horizon (HORIZON_PALETTE), NOT the model.
    - M4 bars are solid; M6 bars carry hatch '//' to distinguish model without
      relying on position alone.
    - When a model produces no threshold crossing for a given event/horizon the
      bar is rendered as a ghost (transparent, dashed outline) and labelled '∅'.
    - Atenção and Alerta panels are Y-capped at [-60, +200] min; overflow bars
      are annotated with the true value.

    @param df_m4    M4 lead time DataFrame (lead_time_summary_m4.csv).
    @param df_m6    M6 lead time DataFrame (lead_time_summary_m6.csv).
    @param out_dir  Output directory.
    """
    if df_m4.empty and df_m6.empty:
        print("  No lead time data available — comparison chart skipped.")
        return

    thresholds = [
        ("Inundação", config.THRESHOLD_INUNDACAO),
        ("Alerta", config.THRESHOLD_ALERTA),
        ("Atenção", config.THRESHOLD_ATENCAO),
    ]
    horizons = config.HORIZONS_MIN  # [30, 60, 90, 120]
    n_horiz = len(horizons)  # 4

    # ── Bar geometry ────────────────────────────────────────────────────────────
    # Each event occupies 1 unit on the X axis.
    # Within each unit: M4 cluster of 4 bars | gap | M6 cluster of 4 bars.
    total_w = 0.82  # fraction of 1 unit devoted to all 8 bars
    gap_m4m6 = 0.06  # gap between the two model clusters
    bar_w = (total_w - gap_m4m6) / (2 * n_horiz)  # width of each single bar

    # Left-edge offsets from the event-group centre (x_base[i]):
    m4_offsets = [-(total_w / 2) + k * bar_w for k in range(n_horiz)]
    m6_offsets = [
        -(total_w / 2) + n_horiz * bar_w + gap_m4m6 + k * bar_w for k in range(n_horiz)
    ]

    fig, axes = plt.subplots(3, 1, figsize=(14, 15))
    fig.suptitle(
        "Comparação M4 LightGBM vs M6 LinearRegressionModel — Tempo de antecipação\n"
        "Cor = horizonte  |  Sólido = M4  |  Hachura = M6  |  ∅ = sem previsão de cruzamento",
        fontsize=11,
        fontweight="bold",
    )

    for ax, (level_name, threshold_cm) in zip(axes, thresholds):
        sub_m4 = (
            df_m4[df_m4["threshold_name"] == level_name]
            if not df_m4.empty
            else pd.DataFrame()
        )
        sub_m6 = (
            df_m6[df_m6["threshold_name"] == level_name]
            if not df_m6.empty
            else pd.DataFrame()
        )

        # Dynamic Y cap: max finite value across all events/horizons/models + 30 min
        _all_finite: list[float] = []
        for _sub in (sub_m4, sub_m6):
            for _h in horizons:
                _col = f"lead_time_{_h}min"
                if not _sub.empty and _col in _sub.columns:
                    _all_finite.extend(_sub[_col].dropna().tolist())
        y_top = (max(_all_finite) + 30) if _all_finite else 250
        y_cap = (Y_BOTTOM, int(np.ceil(y_top / 15) * 15))  # round up to nearest 15

        # One bar group per (event, threshold-crossing occurrence) — Issue #229.
        def _keys(sub: pd.DataFrame) -> set:
            if sub.empty:
                return set()
            return set(zip(sub["event_num"].astype(int), sub["occurrence"].astype(int)))

        all_events = sorted(_keys(sub_m4) | _keys(sub_m6))

        if not all_events:
            ax.text(
                0.5,
                0.5,
                f"Sem eventos para {level_name}",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title(
                f"{level_name} (≥ {threshold_cm} cm)", fontsize=10, fontweight="bold"
            )
            continue

        n_events = len(all_events)
        x_base = np.arange(n_events, dtype=float)

        # Helpers ────────────────────────────────────────────────────────────────

        def _row(sub: pd.DataFrame, key: tuple) -> pd.DataFrame:
            """Rows of sub for one (event_num, occurrence) key."""
            if sub.empty:
                return sub
            return sub[(sub["event_num"] == key[0]) & (sub["occurrence"] == key[1])]

        def _lead(sub: pd.DataFrame, key: tuple, h: int) -> float:
            """Return lead time (min) for occurrence/horizon, or NaN if absent."""
            row = _row(sub, key)
            if row.empty:
                return np.nan
            v = row.iloc[0][f"lead_time_{h}min"]
            return float(v) if pd.notna(v) else np.nan

        def _peak(key: tuple) -> float:
            """Return peak_cm for the event from whichever sub-df has it."""
            for sub in (sub_m4, sub_m6):
                row = _row(sub, key)
                if not row.empty:
                    return float(row.iloc[0]["peak_cm"])
            return float("nan")

        def _label(key: tuple) -> str:
            """E33 / E33a, E33b ... via lead_time_utils.occurrence_label()."""
            for sub in (sub_m4, sub_m6):
                row = _row(sub, key)
                if not row.empty:
                    n = int(row.iloc[0]["n_occurrences"])
                    return lead_time_utils.occurrence_label(key[0], key[1], n)
            return f"E{key[0]:02d}"

        # Ghost-bar height: 3 % of visible Y range, always > 0
        y_range = abs(y_cap[1] - y_cap[0])
        ghost_h = max(y_range * 0.03, 1.0)
        # ∅ label position: just above the ghost bar
        y_null = ghost_h * 1.5

        # ── Draw bars ────────────────────────────────────────────────────────────
        for ev_idx, ev in enumerate(all_events):
            xc = x_base[ev_idx]

            for m_idx, (sub, offsets) in enumerate(
                [(sub_m4, m4_offsets), (sub_m6, m6_offsets)]
            ):
                hatch = "" if m_idx == 0 else "//"

                for h_idx, h in enumerate(horizons):
                    hcol = HORIZON_PALETTE[h_idx]
                    raw_v = _lead(sub, ev, h)
                    bar_left = xc + offsets[h_idx]
                    bar_cx = bar_left + bar_w / 2  # bar centre (for annotations)

                    if np.isnan(raw_v):
                        # Ghost bar: transparent rectangle with dashed outline
                        ax.bar(
                            bar_left,
                            ghost_h,
                            bar_w,
                            align="edge",
                            facecolor="none",
                            edgecolor=hcol,
                            linestyle="--",
                            linewidth=0.9,
                            zorder=2,
                        )
                        ax.text(
                            bar_cx,
                            y_null,
                            "∅",
                            ha="center",
                            va="bottom",
                            fontsize=7,
                            color="dimgray",
                        )
                    else:
                        rend_v = np.clip(raw_v, y_cap[0], y_cap[1])
                        bar_color = hcol if raw_v >= 0 else COLOR_NEG

                        ax.bar(
                            bar_left,
                            rend_v,
                            bar_w,
                            align="edge",
                            color=bar_color,
                            hatch=hatch,
                            alpha=0.88,
                            edgecolor="white",
                            linewidth=0.7,
                            zorder=2,
                        )

                        # Only annotate overflow bars — normal bar values are
                        # readable from the 15-min Y gridlines.
                        if y_cap and raw_v > y_cap[1]:
                            ax.text(
                                bar_cx,
                                y_cap[1] - 4,
                                f"↑{raw_v:.0f}",
                                ha="center",
                                va="top",
                                fontsize=5.5,
                                fontweight="bold",
                                color=bar_color,
                            )
                        elif y_cap and raw_v < y_cap[0]:
                            ax.text(
                                bar_cx,
                                y_cap[0] + 4,
                                f"↓{raw_v:.0f}",
                                ha="center",
                                va="bottom",
                                fontsize=5.5,
                                fontweight="bold",
                                color=COLOR_NEG,
                            )

        # ── X-axis labels ────────────────────────────────────────────────────────
        # Remove default matplotlib ticks; place labels manually via blended
        # transform (data x, axes y) so they sit below the plot regardless of
        # the data Y range.
        ax.set_xticks([])
        trans = blended_transform_factory(ax.transData, ax.transAxes)

        for ev_idx, ev in enumerate(all_events):
            xc = x_base[ev_idx]
            peak = _peak(ev)

            # Event label at group centre — placed further below to clear H-labels
            ax.text(
                xc,
                -0.11,
                f"{_label(ev)}\n{peak:.0f} cm",
                ha="center",
                va="top",
                fontsize=8,
                transform=trans,
                clip_on=False,
            )

            # H30/H60/H90/H120 sub-labels below each individual bar (vertical)
            for m_idx, offsets in enumerate([m4_offsets, m6_offsets]):
                for h_idx, h in enumerate(horizons):
                    bar_cx = xc + offsets[h_idx] + bar_w / 2
                    ax.text(
                        bar_cx,
                        -0.02,
                        f"H{h}",
                        ha="center",
                        va="top",
                        fontsize=5,
                        rotation=90,
                        transform=trans,
                        clip_on=False,
                    )

        # ── M4 / M6 cluster labels (first event only, as a positional guide) ─────
        if all_events:
            first_x = x_base[0]
            m4_cx = first_x + m4_offsets[0] + (n_horiz * bar_w) / 2
            m6_cx = first_x + m6_offsets[0] + (n_horiz * bar_w) / 2
            for cx, lbl in [(m4_cx, "M4"), (m6_cx, "M6")]:
                ax.text(
                    cx,
                    -0.19,
                    lbl,
                    ha="center",
                    va="top",
                    fontsize=7,
                    fontstyle="italic",
                    transform=trans,
                    clip_on=False,
                )

        # ── Legend ───────────────────────────────────────────────────────────────
        legend_handles: list = []
        for h, hcol in zip(horizons, HORIZON_PALETTE):
            legend_handles.append(
                mpatches.Patch(facecolor=hcol, alpha=0.88, label=f"+{h} min")
            )
        legend_handles.append(
            mpatches.Patch(facecolor="gray", alpha=0.70, label="M4 sólido")
        )
        legend_handles.append(
            mpatches.Patch(facecolor="gray", alpha=0.70, hatch="//", label="M6 hachura")
        )
        legend_handles.append(
            mpatches.Patch(
                facecolor="none",
                edgecolor="gray",
                linestyle="--",
                linewidth=0.9,
                label="∅ sem cruzamento",
            )
        )
        legend_handles.append(
            mpatches.Patch(facecolor=COLOR_NEG, alpha=0.88, label="aviso tardio (−)")
        )

        ax.axhline(0, color="black", lw=1.2, zorder=3)
        ax.set_ylim(y_cap[0] - 5, y_cap[1] + 5)

        ax.set_xlim(x_base[0] - 0.55, x_base[-1] + 0.55)
        ax.set_ylabel("Antecipação (min)  [+ = aviso antes  |  − = aviso após]")
        ax.set_title(
            f"{level_name} (≥ {threshold_cm} cm)",
            fontsize=10,
            fontweight="bold",
        )
        ax.legend(handles=legend_handles, fontsize=7, ncol=8, loc="upper left")

        # Tick labels every 60 min; minor gridlines every 15 min (no labels)
        ax.yaxis.set_major_locator(mticker.MultipleLocator(60))
        ax.yaxis.set_minor_locator(mticker.MultipleLocator(15))
        ax.grid(axis="y", which="major", alpha=0.40, linestyle="-", linewidth=0.6)
        ax.grid(axis="y", which="minor", alpha=0.18, linestyle="--", linewidth=0.4)

    fig.subplots_adjust(bottom=0.16, hspace=0.55, top=0.93)
    out_png = os.path.join(out_dir, "lead_time_comparison_m4_vs_m6.png")
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out_png}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate M4 vs M6 comparison report."""
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 66)
    print("  Comparação M4 LightGBM vs M6 LinearRegressionModel")
    print("=" * 66)

    # ── 1. RMSE ──────────────────────────────────────────────────────────────
    print("\n[1/3] Computing RMSE ...")

    rmse_m4 = rmse_m6 = {}

    if os.path.exists(M4_PREDS_CSV):
        print(f"  Loading M4 predictions from: {M4_PREDS_CSV}")
        df_m4 = pd.read_csv(M4_PREDS_CSV, parse_dates=["timestamp"])
        rmse_m4 = compute_rmse(df_m4, "M4 LightGBM        ")
    else:
        print(f"  [WARN] M4 predictions not found at {M4_PREDS_CSV}")
        print("         Run results_final_m4_lgbm/01_model4_continuous.py first.")

    if os.path.exists(M6_PREDS_CSV):
        print(f"  Loading M6 predictions from: {M6_PREDS_CSV}")
        df_m6 = pd.read_csv(M6_PREDS_CSV, parse_dates=["timestamp"])
        rmse_m6 = compute_rmse(df_m6, "M6 LinearRegression")
    else:
        print(f"  [WARN] M6 predictions not found at {M6_PREDS_CSV}")
        print("         Run 01_model6_mlr_continuous.py first.")

    # ── 2. Alert metrics ─────────────────────────────────────────────────────
    print(
        f"\n[2/3] Extracting alert metrics "
        f"(gate={GATE_MM_OPERATIONAL}mm, debounce={DEBOUNCE_OPERATIONAL}) ..."
    )

    print("  M4 LightGBM:")
    metrics_m4 = extract_alert_metrics(M4_GATE_CSV, "M4 LightGBM        ")
    print("  M6 LinearRegression:")
    metrics_m6 = extract_alert_metrics(M6_GATE_CSV, "M6 LinearRegression")

    # ── 3. Comparison plot ───────────────────────────────────────────────────
    print("\n[3/4] Generating RMSE + alert metrics comparison plot ...")
    plot_comparison(rmse_m4, rmse_m6, metrics_m4, metrics_m6, out_dir)

    # ── 4. Lead time comparison ──────────────────────────────────────────────
    print(f"\n[4/4] Lead time comparison ...")
    print("  M4 LightGBM:")
    df_lead_m4 = load_lead_times(M4_LEAD_CSV, "M4 LightGBM")
    print("  M6 LinearRegression:")
    df_lead_m6 = load_lead_times(M6_LEAD_CSV, "M6 LinearRegression")
    plot_lead_time_comparison(df_lead_m4, df_lead_m6, out_dir)

    # ── Tabular summary ──────────────────────────────────────────────────────
    rows = []
    for h in config.HORIZONS_MIN:
        rows.append(
            {
                "metric": f"RMSE +{h}min (cm)",
                "M4_LightGBM": round(rmse_m4.get(h, np.nan), 3),
                "M6_LinearReg": round(rmse_m6.get(h, np.nan), 3),
            }
        )
    for thresh_name in ["Atenção", "Alerta", "Inundação"]:
        for col in ["recall", "FP"]:

            def _v(
                metrics: pd.DataFrame, _tn: str = thresh_name, _col: str = col
            ) -> float | int | str:
                if metrics.empty:
                    return np.nan
                match = metrics[metrics["threshold_name"] == _tn]
                if match.empty:
                    return np.nan
                return match.iloc[0][_col]

            rows.append(
                {
                    "metric": f"{thresh_name} {col} (gate={GATE_MM_OPERATIONAL}mm, db={DEBOUNCE_OPERATIONAL})",
                    "M4_LightGBM": _v(metrics_m4),
                    "M6_LinearReg": _v(metrics_m6),
                }
            )

    # Include mean lead times per threshold in the tabular summary
    for thresh_name in ["Atenção", "Alerta", "Inundação"]:
        for h in config.HORIZONS_MIN:
            col = f"lead_time_{h}min"

            def _lt(df: pd.DataFrame, _tn: str = thresh_name, _col: str = col) -> float:
                if df.empty or _col not in df.columns:
                    return np.nan
                sub = df[df["threshold_name"] == _tn][_col]
                return round(float(sub.mean()), 1) if not sub.empty else np.nan

            rows.append(
                {
                    "metric": f"Lead time +{h}min {thresh_name} mean (min)",
                    "M4_LightGBM": _lt(df_lead_m4),
                    "M6_LinearReg": _lt(df_lead_m6),
                }
            )

    df_summary = pd.DataFrame(rows)
    summary_csv = os.path.join(out_dir, "compare_m4_vs_m6.csv")
    df_summary.to_csv(summary_csv, index=False)
    print(f"  Saved {summary_csv}")

    print(f"\nAll outputs in: {out_dir}")
    print("=== COMPARAÇÃO M4 vs M6 DONE ===\n")


if __name__ == "__main__":
    main()
