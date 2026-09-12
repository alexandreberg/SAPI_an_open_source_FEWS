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
@file 02_precip_gate_analysis.py
@brief Precipitation gate post-analysis for M4 continuous backtesting (Issue #105).

Post-processes ``output/continuous_predictions.csv`` (produced by
``01_model4_continuous.py``) by applying a rolling precipitation gate before the
debounce alert filter.  No model retraining or historical_forecasts re-run is
needed.

Gate logic (applied in order — gate before debounce):

    raw_signal  = (ANY horizon prediction >= threshold_cm)
                  AND (rolling_precip_{gate_hours}h >= gate_mm)
    gated_alert = debounce(raw_signal, n_consecutive)

A sweep over GATE_MM_VALUES quantifies FP reduction vs. recall trade-off.
The gate_mm=0 row is a sanity baseline that must reproduce ``alert_analysis.csv``
exactly.

Usage (run from the real_data_v3_continuous/ folder):

    cd AppTest/raspberry/predictive_model_darts/real_data_v3_continuous/
    python3 02_precip_gate_analysis.py

Output (real_data_v3_continuous/output/):

    precip_gate_analysis.csv          — 45 rows (5 gate_mm x 3 thresholds x 3 debounce)
    precip_gate_timeline_atencao.png  — comparison plot for Atenção (50 cm)
    precip_gate_timeline_alerta.png   — comparison plot for Alerta (60 cm)
    precip_gate_timeline_inundacao.png — comparison plot for Inundação (75 cm)
"""

import os
import sys
import warnings

warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names",
    category=UserWarning,
)

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import config
import real_utils

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRECIP_GATE_HOURS = 6
"""Rolling window for the precipitation gate (hours)."""

GATE_MM_VALUES = [0, 5, 10, 15, 20]
"""Gate thresholds to sweep (mm over PRECIP_GATE_HOURS).  0 = no gate (sanity baseline)."""

GATE_MM_OPERATIONAL = 5
"""Operationally chosen gate threshold (mm/6h).

Selected from the sweep: at 5 mm the model achieves recall=1.000 at both Alerta
and Inundação (zero missed events) while reducing FP by ~94-95% vs. no gate.
"""

GATE_MM_PLOT_TARGETS = [5, 10, 15]
"""Gate thresholds for which timeline comparison plots are generated (reference sweep)."""

THRESHOLDS = {
    "Atenção":   config.THRESHOLD_ATENCAO,
    "Alerta":    config.THRESHOLD_ALERTA,
    "Inundação": config.THRESHOLD_INUNDACAO,
}

THRESHOLD_COLORS = {
    "Atenção":   "gold",
    "Alerta":    "darkorange",
    "Inundação": "red",
}

LEVEL_PLOT_MAX = 270

DEBOUNCE_COLORS = ["#1976D2", "#388E3C", "#7B1FA2"]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_predictions(out_dir: str) -> pd.DataFrame:
    """Load the continuous predictions CSV produced by 01_model4_continuous.py.

    @param out_dir  Path to the output directory (contains continuous_predictions.csv).
    @return DataFrame with columns: timestamp, h_obs, h_pred_{30,60,90,120},
            h_actual_{30,60,90,120}.
    @raises SystemExit if the file does not exist.
    """
    path = os.path.join(out_dir, "continuous_predictions.csv")
    if not os.path.exists(path):
        print(
            f"ERROR: {path} not found.\n"
            "Run 01_model4_continuous.py first to generate continuous_predictions.csv."
        )
        sys.exit(1)

    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    print(f"  Loaded {len(df):,} rows from {os.path.basename(path)}")
    return df

# ---------------------------------------------------------------------------
# Gate + debounce alert logic
# ---------------------------------------------------------------------------

def apply_precip_gate_alert(
    df_preds: pd.DataFrame,
    precip_ser: pd.Series,
    threshold_cm: float,
    gate_hours: float,
    gate_mm: float,
    n_consecutive: int,
) -> pd.Series:
    """Compute gated boolean alert state for one parameter combination.

    Pipeline:

    1. Align precipitation to the prediction grid (fill missing with 0 mm).
    2. Compute rolling sum over ``gate_hours`` (min_periods=1 handles series start).
    3. Gate condition: rolling_precip >= gate_mm (always True when gate_mm=0).
    4. Raw signal: any horizon prediction >= threshold AND gate condition.
    5. Debounce: require n_consecutive consecutive raw-signal steps.

    @param df_preds       Full continuous predictions DataFrame (has 'timestamp' column).
    @param precip_ser     Precipitation pandas Series indexed by tz-naive timestamps,
                          5-min accumulations in mm.
    @param threshold_cm   Alert threshold in cm.
    @param gate_hours     Rolling precipitation window in hours.
    @param gate_mm        Minimum rolling precipitation sum required (mm).
                          Use 0 to disable the gate.
    @param n_consecutive  Debounce: number of consecutive raw-signal steps required.
    @return Boolean Series indexed by timestamp; True = alert active.
    """
    df = df_preds.set_index("timestamp").copy()
    idx = df.index

    gate_steps = int(gate_hours * 60 / config.RESAMPLE_MIN)
    precip_aln = precip_ser.reindex(idx, fill_value=0.0)
    rolling_precip = precip_aln.rolling(window=gate_steps, min_periods=1).sum()
    gate_cond = rolling_precip >= gate_mm

    raw_signal = pd.Series(False, index=idx)
    for h in config.HORIZONS_MIN:
        col = f"h_pred_{h}"
        if col in df.columns:
            raw_signal |= df[col].fillna(0) >= threshold_cm
    raw_signal &= gate_cond

    if n_consecutive <= 1:
        return raw_signal

    return raw_signal.rolling(window=n_consecutive, min_periods=n_consecutive).apply(
        lambda w: bool(w.all()), raw=True
    ).fillna(False).astype(bool)

# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------

def compute_gated_cm(
    df_preds: pd.DataFrame,
    precip_ser: pd.Series,
    df_events: pd.DataFrame,
    threshold_cm: float,
    threshold_name: str,
    gate_hours: float,
    gate_mm: float,
    n_consecutive: int,
) -> dict:
    """Compute operational VP/FP/FN/VN for one gate × threshold × debounce combo.

    VP/FN are evaluated per catalogued event that reaches threshold_cm:
      - VP if any alert step overlaps [analysis_start, analysis_end].
      - FN if no alert step overlaps.

    FP counts isolated alert periods with zero overlap with any catalogued event.

    @param df_preds        Full continuous predictions DataFrame.
    @param precip_ser      Precipitation Series (5-min, tz-naive).
    @param df_events       Events catalogue DataFrame.
    @param threshold_cm    Alert threshold in cm.
    @param threshold_name  Human-readable threshold name.
    @param gate_hours      Rolling precipitation window in hours.
    @param gate_mm         Gate threshold in mm.
    @param n_consecutive   Debounce steps applied.
    @return Dict with confusion-matrix fields plus gate parameters.
    """
    alert_ser = apply_precip_gate_alert(
        df_preds, precip_ser, threshold_cm, gate_hours, gate_mm, n_consecutive
    )
    alert_ser.index = pd.to_datetime(alert_ser.index)

    events_at_thresh = df_events[df_events["peak_cm"] >= threshold_cm].copy()

    VP = FN = 0
    covered_windows: list[tuple] = []

    for _, evt in events_at_thresh.iterrows():
        t_start = pd.Timestamp(evt["analysis_start"])
        t_end   = pd.Timestamp(evt["analysis_end"])
        covered_windows.append((t_start, t_end))
        window_alerts = alert_ser.loc[t_start:t_end]
        if window_alerts.any():
            VP += 1
        else:
            FN += 1

    alert_df = alert_ser.to_frame(name="alert")
    alert_df["group"] = (alert_df["alert"] != alert_df["alert"].shift()).cumsum()
    FP = 0
    for _, grp in alert_df[alert_df["alert"]].groupby("group"):
        period_start = grp.index[0]
        period_end   = grp.index[-1]
        overlaps = any(
            not (period_end < ws or period_start > we)
            for ws, we in covered_windows
        )
        if not overlaps:
            FP += 1

    total_steps   = len(alert_ser)
    covered_steps = sum(len(alert_ser.loc[ws:we]) for ws, we in covered_windows)
    VN = total_steps - covered_steps - int(alert_ser.sum())

    precision = VP / (VP + FP) if (VP + FP) > 0 else np.nan
    recall    = VP / (VP + FN) if (VP + FN) > 0 else np.nan
    f1        = (
        2 * precision * recall / (precision + recall)
        if not (np.isnan(precision) or np.isnan(recall)) and (precision + recall) > 0
        else np.nan
    )

    return {
        "threshold_name": threshold_name,
        "threshold_cm":   threshold_cm,
        "gate_hours":     gate_hours,
        "gate_mm":        gate_mm,
        "debounce_steps": n_consecutive,
        "debounce_min":   n_consecutive * config.RESAMPLE_MIN,
        "VP": VP, "FP": FP, "FN": FN, "VN": int(max(VN, 0)),
        "precision": round(precision, 3) if not np.isnan(precision) else np.nan,
        "recall":    round(recall,    3) if not np.isnan(recall)    else np.nan,
        "F1":        round(f1,        3) if not np.isnan(f1)        else np.nan,
    }

# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------

def run_sanity_check(df_gate: pd.DataFrame, alert_csv_path: str) -> None:
    """Verify that gate_mm=0 rows reproduce the original alert_analysis.csv.

    @param df_gate        Full precip_gate_analysis DataFrame (all gate_mm values).
    @param alert_csv_path Path to alert_analysis.csv from 01_model4_continuous.py.
    """
    if not os.path.exists(alert_csv_path):
        print(f"  [WARN] alert_analysis.csv not found at {alert_csv_path} — skipping sanity check.")
        return

    df_orig  = pd.read_csv(alert_csv_path)
    df_base  = df_gate[df_gate["gate_mm"] == 0].copy()

    print("\n  Sanity check (gate_mm=0 must match alert_analysis.csv):")
    all_ok = True
    for _, row_orig in df_orig.iterrows():
        match = df_base[
            (df_base["threshold_name"] == row_orig["threshold_name"]) &
            (df_base["debounce_steps"] == row_orig["debounce_steps"])
        ]
        if match.empty:
            print(f"    [WARN] No gate_mm=0 row for "
                  f"{row_orig['threshold_name']} debounce={row_orig['debounce_steps']}")
            all_ok = False
            continue

        row_gate = match.iloc[0]
        vp_ok = int(row_gate["VP"]) == int(row_orig["VP"])
        fp_ok = int(row_gate["FP"]) == int(row_orig["FP"])
        fn_ok = int(row_gate["FN"]) == int(row_orig["FN"])

        status = "OK" if (vp_ok and fp_ok and fn_ok) else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False
        print(
            f"    {status}  {row_orig['threshold_name']:10s} "
            f"debounce={int(row_orig['debounce_steps'])}  "
            f"VP {int(row_orig['VP'])}→{int(row_gate['VP'])}  "
            f"FP {int(row_orig['FP'])}→{int(row_gate['FP'])}  "
            f"FN {int(row_orig['FN'])}→{int(row_gate['FN'])}"
        )

    if all_ok:
        print("  All gate_mm=0 rows match alert_analysis.csv. ✓")
    else:
        print("  WARNING: Some rows do not match — check gate logic or CSV precision.")

# ---------------------------------------------------------------------------
# Timeline comparison plots
# ---------------------------------------------------------------------------

def _shade_alert_periods(ax: plt.Axes, alert_ser: pd.Series, color: str, alpha: float) -> None:
    """Fill consecutive alert-active spans on *ax*.

    @param ax         Axes to draw on.
    @param alert_ser  Boolean Series indexed by timestamp.
    @param color      Fill colour.
    @param alpha      Fill transparency.
    """
    in_alert = False
    a_start  = None
    for ts, active in alert_ser.items():
        if active and not in_alert:
            in_alert = True
            a_start  = ts
        elif not active and in_alert:
            ax.axvspan(a_start, ts, color=color, alpha=alpha, zorder=3)
            in_alert = False
    if in_alert and a_start is not None:
        ax.axvspan(a_start, alert_ser.index[-1], color=color, alpha=alpha, zorder=3)


def plot_gate_comparison_timeline(
    df_preds: pd.DataFrame,
    precip_ser: pd.Series,
    df_events: pd.DataFrame,
    alert_by_key: "dict[tuple, pd.Series]",
    threshold_cm: float,
    threshold_name: str,
    gate_hours: float,
    gate_mm_target: int,
    out_dir: str,
) -> None:
    """Save a 3-panel comparison PNG for one threshold level.

    Panel 1 — Original (gate_mm=0, debounce=3): alert state before gate.
    Panel 2 — Gated (gate_mm=gate_mm_target, debounce=3): alert state after gate.
    Panel 3 — Rolling precipitation (gate_hours window) with gate threshold line.

    @param df_preds        Full continuous predictions DataFrame.
    @param precip_ser      Precipitation Series (5-min, tz-naive, mm).
    @param df_events       Events catalogue DataFrame.
    @param alert_by_key    Dict keyed by (gate_mm, threshold_cm, debounce_steps) → bool Series.
    @param threshold_cm    Threshold in cm.
    @param threshold_name  Human-readable name.
    @param gate_hours      Rolling window used for the precipitation panel.
    @param gate_mm_target  Gate threshold shown as dashed line in precipitation panel.
    @param out_dir         Output directory.
    """
    df_ts = df_preds.set_index("timestamp")

    # Compute rolling precip for the precipitation panel.
    gate_steps = int(gate_hours * 60 / config.RESAMPLE_MIN)
    precip_aln = precip_ser.reindex(df_ts.index, fill_value=0.0)
    rolling_precip = precip_aln.rolling(window=gate_steps, min_periods=1).sum()

    debounce_ref = 3  # reference debounce scenario (best from Issue #104)

    key_orig  = (0,              threshold_cm, debounce_ref)
    key_gated = (gate_mm_target, threshold_cm, debounce_ref)

    alert_orig  = alert_by_key.get(key_orig,  pd.Series(dtype=bool))
    alert_gated = alert_by_key.get(key_gated, pd.Series(dtype=bool))

    fp_orig  = _count_fp_periods(alert_orig,  df_events, threshold_cm)
    fp_gated = _count_fp_periods(alert_gated, df_events, threshold_cm)

    events_at_thresh = df_events[df_events["peak_cm"] >= threshold_cm]
    color = THRESHOLD_COLORS[threshold_name]

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(22, 10), sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 2]},
    )

    for ax in (ax1, ax2):
        ax.plot(df_ts.index, df_ts["h_obs"], color="lightgray", lw=0.7, zorder=1)
        ax.axhline(threshold_cm, color=color, lw=1.2, ls="--", zorder=2)
        ax.set_ylim(0, LEVEL_PLOT_MAX)
        ax.set_ylabel("Cota (cm)", fontsize=8)
        ax.grid(which="major", ls="-", lw=0.4, color="lightgray", alpha=0.5)

    # Panel 1: original alert.
    _shade_alert_periods(ax1, alert_orig, color="red", alpha=0.25)
    _annotate_events(ax1, events_at_thresh, alert_orig, threshold_cm)
    ax1.set_title(
        f"Original (sem gate, debounce=3)  —  FP={fp_orig}",
        fontsize=9,
    )

    # Panel 2: gated alert.
    _shade_alert_periods(ax2, alert_gated, color="red", alpha=0.25)
    _annotate_events(ax2, events_at_thresh, alert_gated, threshold_cm)
    ax2.set_title(
        f"Com gate (≥{gate_mm_target} mm / {gate_hours:.0f}h, debounce=3)  —  FP={fp_gated}  "
        f"(redução {fp_orig - fp_gated} FP = "
        f"{100*(fp_orig - fp_gated)/fp_orig:.0f}% )" if fp_orig > 0 else
        f"Com gate (≥{gate_mm_target} mm / {gate_hours:.0f}h, debounce=3)  —  FP={fp_gated}",
        fontsize=9,
    )

    # Panel 3: rolling precipitation.
    ax3.fill_between(rolling_precip.index, 0, rolling_precip.values,
                     color="teal", alpha=0.4, label=f"Precip acum. {gate_hours:.0f}h")
    ax3.plot(rolling_precip.index, rolling_precip.values, color="teal", lw=0.7)
    ax3.axhline(gate_mm_target, color="navy", lw=1.3, ls="--",
                label=f"Gate = {gate_mm_target} mm")
    ax3.set_ylabel(f"Precip\nacum. {gate_hours:.0f}h (mm)", fontsize=8)
    ax3.legend(fontsize=7.5, loc="upper right")
    ax3.grid(which="major", ls="-", lw=0.4, color="lightgray", alpha=0.5)
    ax3.set_xlabel("Data/Hora (UTC)")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m\n%d"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator())

    fig.suptitle(
        f"Filtro de Precipitação — {threshold_name} (≥ {threshold_cm:.0f} cm)  "
        f"|  Verde=VP  Laranja=FN  Vermelho=Falso Alarme (FP)",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    slug = threshold_name.lower().replace("ã", "a").replace("ç", "c")
    path = os.path.join(out_dir, f"precip_gate_timeline_{slug}_gate{gate_mm_target}mm.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  Saved {path}")


def _count_fp_periods(
    alert_ser: pd.Series,
    df_events: pd.DataFrame,
    threshold_cm: float,
) -> int:
    """Count alert periods with no overlap with any catalogued event window.

    @param alert_ser    Boolean alert Series indexed by timestamp.
    @param df_events    Events catalogue DataFrame.
    @param threshold_cm Threshold used to select relevant events.
    @return Number of false-positive alert periods.
    """
    events_at_thresh = df_events[df_events["peak_cm"] >= threshold_cm]
    covered_windows = [
        (pd.Timestamp(r["analysis_start"]), pd.Timestamp(r["analysis_end"]))
        for _, r in events_at_thresh.iterrows()
    ]

    if alert_ser.empty:
        return 0

    alert_ser = alert_ser.copy()
    alert_ser.index = pd.to_datetime(alert_ser.index)
    alert_df = alert_ser.to_frame(name="alert")
    alert_df["group"] = (alert_df["alert"] != alert_df["alert"].shift()).cumsum()

    FP = 0
    for _, grp in alert_df[alert_df["alert"]].groupby("group"):
        p_start = grp.index[0]
        p_end   = grp.index[-1]
        if not any(not (p_end < ws or p_start > we) for ws, we in covered_windows):
            FP += 1
    return FP


def _annotate_events(
    ax: plt.Axes,
    events_at_thresh: pd.DataFrame,
    alert_ser: pd.Series,
    threshold_cm: float,
) -> None:
    """Draw VP/FN event markers on *ax*.

    @param ax               Target Axes.
    @param events_at_thresh Events catalogue filtered to current threshold.
    @param alert_ser        Boolean alert Series indexed by timestamp.
    @param threshold_cm     Threshold cm (used for label y-position).
    """
    for _, evt in events_at_thresh.iterrows():
        t_start = pd.Timestamp(evt["analysis_start"])
        t_end   = pd.Timestamp(evt["analysis_end"])
        window  = alert_ser.loc[t_start:t_end] if not alert_ser.empty else pd.Series(dtype=bool)
        outcome = "VP" if window.any() else "FN"
        color   = "forestgreen" if outcome == "VP" else "darkorange"
        ax.axvline(t_start, color=color, lw=1.6, ls="--", zorder=4, alpha=0.9)
        ax.text(
            t_start, threshold_cm + 3,
            f"E{int(evt['event_num']):02d}\n{outcome}",
            fontsize=6, color=color, ha="left", va="bottom",
            fontweight="bold", zorder=5,
        )

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run precipitation gate post-analysis on existing continuous_predictions.csv."""
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 66)
    print("  M4 — Filtro de Precipitação  [Issue #105]")
    print("=" * 66)

    # ── 1. Load predictions ──────────────────────────────────────────────────
    print("\n[1/4] Loading continuous_predictions.csv ...")
    df_preds = load_predictions(out_dir)

    # ── 2. Load real data (for precipitation and events) ─────────────────────
    print("\n[2/4] Loading real data (precipitation + events) ...")
    _, ts_precip, df_events = real_utils.load_real_data()
    precip_ser = ts_precip.to_series()
    print(f"  Precipitation steps: {len(precip_ser):,}  "
          f"({precip_ser.index[0]} → {precip_ser.index[-1]})")
    print(f"  Events: {len(df_events)}")

    # ── 3. Sweep gate_mm × threshold × debounce ──────────────────────────────
    print("\n[3/4] Computing confusion matrices ...")
    print(f"  Gate values: {GATE_MM_VALUES} mm  |  Window: {PRECIP_GATE_HOURS}h")
    print(f"  Thresholds: {list(THRESHOLDS.keys())}  |  Debounce: {config.DEBOUNCE_STEPS}")

    records: list[dict] = []
    alert_by_key: dict[tuple, pd.Series] = {}

    total = len(GATE_MM_VALUES) * len(THRESHOLDS) * len(config.DEBOUNCE_STEPS)
    done  = 0

    for gate_mm in GATE_MM_VALUES:
        for thresh_name, thresh_cm in THRESHOLDS.items():
            for n_steps in config.DEBOUNCE_STEPS:
                alert_ser = apply_precip_gate_alert(
                    df_preds, precip_ser,
                    thresh_cm, PRECIP_GATE_HOURS, gate_mm, n_steps,
                )
                alert_by_key[(gate_mm, thresh_cm, n_steps)] = alert_ser

                cm = compute_gated_cm(
                    df_preds, precip_ser, df_events,
                    thresh_cm, thresh_name,
                    PRECIP_GATE_HOURS, gate_mm, n_steps,
                )
                records.append(cm)
                done += 1

                print(
                    f"  [{done:2d}/{total}] gate={gate_mm:2d}mm  "
                    f"{thresh_name:10s}  debounce={n_steps}  "
                    f"VP={cm['VP']}  FP={cm['FP']}  FN={cm['FN']}  "
                    f"recall={cm['recall']}  precision={cm['precision']}"
                )

    df_gate = pd.DataFrame(records)
    gate_csv = os.path.join(out_dir, "precip_gate_analysis.csv")
    df_gate.to_csv(gate_csv, index=False)
    print(f"\n  Saved {gate_csv}  ({len(df_gate)} rows)")

    # ── Sanity check ─────────────────────────────────────────────────────────
    alert_csv = os.path.join(out_dir, "alert_analysis.csv")
    run_sanity_check(df_gate, alert_csv)

    # ── 4. Timeline comparison plots ─────────────────────────────────────────
    print("\n[4/4] Generating timeline comparison plots ...")
    for gate_mm_target in GATE_MM_PLOT_TARGETS:
        print(f"  gate_mm={gate_mm_target} mm ...")
        for thresh_name, thresh_cm in THRESHOLDS.items():
            plot_gate_comparison_timeline(
                df_preds, precip_ser, df_events,
                alert_by_key,
                thresh_cm, thresh_name,
                PRECIP_GATE_HOURS, gate_mm_target,
                out_dir,
            )

    print(f"\nAll outputs in: {out_dir}")
    print("=== FILTRO DE PRECIPITAÇÃO DONE ===\n")


if __name__ == "__main__":
    main()
