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
@file 01_model4_continuous.py
@brief M4 LightGBM continuous backtesting — Simulado Contínuo (v3).

Trains the same LightGBM model as real_data_v2 on the four real training events
(E1, E4, E7, E8) and then runs a continuous rolling prediction over the FULL
available dataset — from the first Station-01 reading to the last available
MySQL dump — without any event-window boundaries.

This is the "Backtesting Histórico de Simulação de Fluxo" described in the PDF
evaluation. It exposes the model to dry-period behaviour (false alarm rate),
event-onset detection (fires before analysis_start?), and validates the pipeline
robustness over 16+ months of real data.

Usage (run from the real_data_v3_continuous/ folder):
    cd AppTest/raspberry/predictive_model_darts/real_data_v3_continuous/
    python3 01_model4_continuous.py

Output (real_data_v3_continuous/output/):
    continuous_predictions.csv       — full prediction log (~170k rows)
    alert_analysis.csv               — VP/FP/FN/VN × 3 thresholds × 3 debounce
    event_detected_NNN.png           — one plot per auto-detected flood period
    alert_timeline_atencao.png       — alert state timeline, Atenção (50 cm)
    alert_timeline_alerta.png        — alert state timeline, Alerta (60 cm)
    alert_timeline_inundacao.png     — alert state timeline, Inundação (75 cm)
"""

import os
import sys
import warnings

# Suppress sklearn "X does not have valid feature names" warnings — they fire on
# every predict() call because the MultiOutputRegressor was fitted with named
# DataFrame columns but receives a plain numpy array.  Results are unaffected.
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

from darts.models import LightGBMModel
from darts import TimeSeries

# ---------------------------------------------------------------------------
# Plot constants
# ---------------------------------------------------------------------------

THRESHOLD_COLORS = {
    "Atenção": "gold",
    "Alerta": "darkorange",
    "Inundação": "red",
}
THRESHOLDS = {
    "Atenção": config.THRESHOLD_ATENCAO,
    "Alerta": config.THRESHOLD_ALERTA,
    "Inundação": config.THRESHOLD_INUNDACAO,
}
LEVEL_PLOT_MAX = 270

DEBOUNCE_COLORS = ["#1976D2", "#388E3C", "#7B1FA2"]
"""One colour per debounce scenario (A=blue, B=green, C=purple)."""

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def build_model() -> LightGBMModel:
    """Instantiate LightGBMModel with the same hyper-parameters as real_data_v2.

    @return Configured but untrained LightGBMModel.
    """
    return LightGBMModel(
        lags=config.LGBM_LAGS,
        lags_past_covariates=config.LGBM_PRECIP_LAGS,
        output_chunk_length=config.OUTPUT_CHUNK_STEPS,
        n_estimators=config.LGBM_N_ESTIMATORS,
        num_leaves=config.LGBM_NUM_LEAVES,
        random_state=config.RANDOM_STATE,
        verbose=-1,
    )


# ---------------------------------------------------------------------------
# Continuous rolling prediction
# ---------------------------------------------------------------------------


def _has_nan_in_tail(lvl_ser: pd.Series, T: pd.Timestamp, n_steps: int) -> bool:
    """Return True if the last *n_steps* values up to T contain any NaN.

    @param lvl_ser  Level pandas Series (5-min grid, tz-naive).
    @param T        Current simulation timestamp.
    @param n_steps  Number of tail steps to check.
    @return True if any of the last n_steps values are NaN.
    """
    tail_start = T - pd.Timedelta(minutes=n_steps * config.RESAMPLE_MIN)
    tail = lvl_ser.loc[tail_start:T]
    return tail.isnull().any()


def continuous_rolling_predict(
    model: LightGBMModel,
    ts_level: TimeSeries,
    ts_precip: TimeSeries,
) -> pd.DataFrame:
    """Run rolling prediction using Darts' vectorised historical_forecasts().

    Replaces a Python loop of 140k individual predict() calls with Darts'
    optimised SKLearnModel path: it builds the full feature matrix once via
    sliding_window_view, then calls model._predict() on all rows in a single
    batch.  Typically 50–100× faster on RPi 4.

    historical_forecasts() is called four times (once per prediction horizon)
    with last_points_only=True.  This avoids creating 140k TimeSeries objects
    while still leveraging the vectorised batch path for each call.

    Steps before sufficient level/precipitation history are absent from the
    historical_forecasts output and recorded with NaN predictions.

    @param model      Trained LightGBMModel.
    @param ts_level   Full level TimeSeries (tz-naive, 5-min grid).
    @param ts_precip  Full precipitation TimeSeries (tz-naive, 5-min grid).
    @return DataFrame with columns: timestamp, h_obs, h_pred_{30,60,90,120},
            h_actual_{30,60,90,120}.
    """
    freq_min = config.RESAMPLE_MIN
    freq_str = f"{freq_min}min"
    lvl_ser = ts_level.to_series()

    sim_start = ts_level.start_time()
    sim_end = ts_level.end_time()
    sim_grid = pd.date_range(start=sim_start, end=sim_end, freq=freq_str)
    print(f"  Simulation grid: {sim_start} → {sim_end}  ({len(sim_grid):,} steps)")

    # HORIZON_STEP_IDX is 0-based; Darts' forecast_horizon is 1-based step count.
    # E.g.  h=30 min → step index 5 (0-based) → forecast_horizon=6 (1-based).
    horizon_to_fh = {h: config.HORIZON_STEP_IDX[h] + 1 for h in config.HORIZONS_MIN}

    pred_sers: dict[int, pd.Series] = {}  # h_min → pandas Series indexed by T
    for h_min, fh in horizon_to_fh.items():
        print(f"  historical_forecasts(forecast_horizon={fh}) → h_pred_{h_min} min ...")
        hfc_ts = model.historical_forecasts(
            series=ts_level,
            past_covariates=ts_precip,
            start=None,  # Darts auto-computes earliest valid start
            forecast_horizon=fh,
            stride=1,
            retrain=False,
            last_points_only=True,
            overlap_end=True,
            show_warnings=False,
            verbose=False,
        )
        # hfc_ts is indexed by T+h_min (the predicted time); shift back to T.
        raw_ser = hfc_ts.to_series()
        raw_ser.index = raw_ser.index - pd.Timedelta(minutes=h_min)
        pred_sers[h_min] = raw_ser
        n_preds = len(raw_ser)
        print(f"    → {n_preds:,} predictions")

    # ── Build result DataFrame (vectorised) ──────────────────────────────────
    print("  Building result DataFrame ...")
    lvl_rs = lvl_ser.reindex(sim_grid)  # level on the full 5-min grid

    df = pd.DataFrame({"timestamp": sim_grid})
    df["h_obs"] = lvl_rs.values

    for h in config.HORIZONS_MIN:
        steps_ahead = h // freq_min
        df[f"h_pred_{h}"] = pred_sers[h].reindex(sim_grid).values
        df[f"h_actual_{h}"] = lvl_rs.shift(-steps_ahead).values

    n_pred = int(df["h_pred_30"].notna().sum())
    n_nan = int(df["h_pred_30"].isna().sum())
    print(
        f"  Done. {len(df):,} rows total  "
        f"({n_pred:,} with predictions, {n_nan:,} NaN rows at start/gaps)."
    )
    return df


# ---------------------------------------------------------------------------
# Alert logic
# ---------------------------------------------------------------------------


def apply_debounce_alert(
    df_preds: pd.DataFrame,
    threshold_cm: float,
    n_consecutive: int,
) -> pd.Series:
    """Compute boolean alert state for one threshold × debounce combination.

    At each step T, a raw signal fires when ANY horizon prediction equals or
    exceeds *threshold_cm*.  The debounce filter requires *n_consecutive*
    consecutive raw-signal steps before the alert is considered active.

    @param df_preds      Full continuous predictions DataFrame.
    @param threshold_cm  Alert threshold in cm.
    @param n_consecutive Number of consecutive steps required (1 = no filter).
    @return Boolean Series indexed by timestamp: True = alert active.
    """
    df = df_preds.set_index("timestamp").copy()

    raw_signal = pd.Series(False, index=df.index)
    for h in config.HORIZONS_MIN:
        col = f"h_pred_{h}"
        if col in df.columns:
            raw_signal |= df[col].fillna(0) >= threshold_cm

    if n_consecutive <= 1:
        return raw_signal

    return (
        raw_signal.rolling(window=n_consecutive, min_periods=n_consecutive)
        .apply(lambda w: bool(w.all()), raw=True)
        .fillna(False)
        .astype(bool)
    )


# ---------------------------------------------------------------------------
# Confusion matrix
# ---------------------------------------------------------------------------


def compute_confusion_matrix(
    df_preds: pd.DataFrame,
    df_events: pd.DataFrame,
    threshold_cm: float,
    threshold_name: str,
    n_consecutive: int,
) -> dict:
    """Compute operational VP/FP/FN/VN for one threshold × debounce scenario.

    VP / FN are evaluated per catalogued event that reaches *threshold_cm*:
      - VP if any alert step overlaps the event window [analysis_start, analysis_end].
      - FN if no alert step overlaps.

    FP counts isolated alert periods (groups of consecutive True steps) that
    have zero overlap with any catalogued event window at this threshold.

    @param df_preds        Full continuous predictions DataFrame.
    @param df_events       Events catalogue DataFrame.
    @param threshold_cm    Alert threshold in cm.
    @param threshold_name  Human-readable name (for the output dict).
    @param n_consecutive   Debounce steps applied.
    @return Dict with keys: threshold_name, debounce_steps, VP, FP, FN, VN,
            precision, recall, F1.
    """
    alert_ser = apply_debounce_alert(df_preds, threshold_cm, n_consecutive)
    alert_ser.index = pd.to_datetime(alert_ser.index)

    events_at_thresh = df_events[df_events["peak_cm"] >= threshold_cm].copy()

    VP = FN = 0
    covered_windows: list[tuple] = []

    for _, evt in events_at_thresh.iterrows():
        t_start = pd.Timestamp(evt["analysis_start"])
        t_end = pd.Timestamp(evt["analysis_end"])
        covered_windows.append((t_start, t_end))
        window_alerts = alert_ser.loc[t_start:t_end]
        if window_alerts.any():
            VP += 1
        else:
            FN += 1

    # Detect alert periods (runs of consecutive True) outside all event windows.
    alert_df = alert_ser.to_frame(name="alert")
    alert_df["group"] = (alert_df["alert"] != alert_df["alert"].shift()).cumsum()
    FP = 0
    for _, grp in alert_df[alert_df["alert"]].groupby("group"):
        period_start = grp.index[0]
        period_end = grp.index[-1]
        overlaps = any(
            not (period_end < ws or period_start > we) for ws, we in covered_windows
        )
        if not overlaps:
            FP += 1

    total_steps = len(alert_ser)
    covered_steps = sum(len(alert_ser.loc[ws:we]) for ws, we in covered_windows)
    VN = total_steps - covered_steps - alert_ser.sum()

    precision = VP / (VP + FP) if (VP + FP) > 0 else np.nan
    recall = VP / (VP + FN) if (VP + FN) > 0 else np.nan
    f1 = (
        2 * precision * recall / (precision + recall)
        if not np.isnan(precision) and not np.isnan(recall) and (precision + recall) > 0
        else np.nan
    )

    return {
        "threshold_name": threshold_name,
        "threshold_cm": threshold_cm,
        "debounce_steps": n_consecutive,
        "debounce_min": n_consecutive * config.RESAMPLE_MIN,
        "VP": VP,
        "FP": FP,
        "FN": FN,
        "VN": int(max(VN, 0)),
        "precision": round(precision, 3) if not np.isnan(precision) else np.nan,
        "recall": round(recall, 3) if not np.isnan(recall) else np.nan,
        "F1": round(f1, 3) if not np.isnan(f1) else np.nan,
    }


# ---------------------------------------------------------------------------
# Detected flood periods
# ---------------------------------------------------------------------------


def detect_flood_periods(
    df_preds: pd.DataFrame,
    threshold_cm: float = None,
    merge_gap_min: int = None,
) -> list[tuple]:
    """Find continuous periods where the observed level equals or exceeds threshold_cm.

    Consecutive above-threshold steps separated by gaps <= merge_gap_min are
    merged into a single period.  The returned windows are padded by 2 hours on
    each side for better plot context.

    @param df_preds       Full continuous predictions DataFrame.
    @param threshold_cm   Detection threshold (default: THRESHOLD_ATENCAO).
    @param merge_gap_min  Maximum gap to merge adjacent periods (default: EVENT_MERGE_GAP_MIN).
    @return List of (period_start, period_end) Timestamp tuples (with padding).
    """
    if threshold_cm is None:
        threshold_cm = config.THRESHOLD_ATENCAO
    if merge_gap_min is None:
        merge_gap_min = config.EVENT_MERGE_GAP_MIN

    df = df_preds.set_index("timestamp").copy()
    above = df["h_obs"] >= threshold_cm
    above = above.fillna(False)

    periods: list[tuple] = []
    in_period = False
    p_start = p_end = None

    for ts, val in above.items():
        if val and not in_period:
            in_period = True
            p_start = p_end = ts
        elif val and in_period:
            p_end = ts
        elif not val and in_period:
            if (
                periods
                and (p_start - periods[-1][1]).total_seconds() / 60 <= merge_gap_min
            ):
                periods[-1] = (periods[-1][0], p_end)
            else:
                periods.append((p_start, p_end))
            in_period = False

    if in_period:
        periods.append((p_start, p_end))

    pad = pd.Timedelta(hours=2)
    padded = [
        (max(df.index[0], s - pad), min(df.index[-1], e + pad)) for s, e in periods
    ]
    return padded


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def plot_detected_event(
    df_preds: pd.DataFrame,
    df_events: pd.DataFrame,
    alert_series: "dict[str, pd.Series]",
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    period_idx: int,
    out_dir: str,
) -> None:
    """Save one zoomed plot for a detected flood period.

    Shows observed level, +60 and +120 min predictions, precipitation,
    threshold zones, alert-state bands for each debounce scenario, and
    annotations for overlapping catalogued events.

    @param df_preds       Full predictions DataFrame.
    @param df_events      Events catalogue DataFrame.
    @param alert_series   Dict keyed by debounce_steps → boolean Series indexed by timestamp.
    @param period_start   Start of the plot window.
    @param period_end     End of the plot window.
    @param period_idx     Sequential index for the file name.
    @param out_dir        Output directory.
    """
    mask = (df_preds["timestamp"] >= period_start) & (
        df_preds["timestamp"] <= period_end
    )
    sub = df_preds[mask].set_index("timestamp")
    if sub.empty:
        return

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(16, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    for ax in (ax1, ax2):
        ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[0, 15, 30, 45]))
        ax.grid(which="major", ls="-", lw=0.5, color="lightgray", alpha=0.6, zorder=0)
        ax.grid(which="minor", ls="--", lw=0.3, color="lightgray", alpha=0.35, zorder=0)

    # Threshold bands.
    for zname, ylo, yhi, alpha in [
        ("Atenção", config.THRESHOLD_ATENCAO, config.THRESHOLD_ALERTA, 0.07),
        ("Alerta", config.THRESHOLD_ALERTA, config.THRESHOLD_INUNDACAO, 0.08),
        ("Inundação", config.THRESHOLD_INUNDACAO, LEVEL_PLOT_MAX + 20, 0.09),
    ]:
        ax1.axhspan(ylo, yhi, color=THRESHOLD_COLORS[zname], alpha=alpha, zorder=1)
    for name, thresh in THRESHOLDS.items():
        ax1.axhline(thresh, color=THRESHOLD_COLORS[name], lw=1.1, ls="--", zorder=3)

    # Observed level.
    ax1.plot(
        sub.index, sub["h_obs"], color="black", lw=1.6, label="Observado", zorder=5
    )

    # +60 min prediction shifted right by 60 min.
    if "h_pred_60" in sub.columns:
        shifted_t60 = sub.index + pd.Timedelta(minutes=60)
        ax1.plot(
            shifted_t60,
            sub["h_pred_60"],
            color="deeppink",
            lw=1.2,
            ls="--",
            alpha=0.9,
            label="M4 +60 min deslocado",
            zorder=6,
        )

    # +120 min prediction shifted right by 120 min.
    if "h_pred_120" in sub.columns:
        shifted_t120 = sub.index + pd.Timedelta(minutes=120)
        ax1.plot(
            shifted_t120,
            sub["h_pred_120"],
            color="purple",
            lw=1.0,
            ls=":",
            alpha=0.8,
            label="M4 +120 min deslocado",
            zorder=6,
        )

    # Debounce alert bands.
    for n_steps, color in zip(config.DEBOUNCE_STEPS, DEBOUNCE_COLORS):
        key = n_steps
        if key not in alert_series:
            continue
        ser = alert_series[key]
        ser.index = pd.to_datetime(ser.index)
        ser_sub = ser.reindex(sub.index, fill_value=False)
        # Shade alert-active periods.
        in_alert = False
        a_start = None
        for ts, active in ser_sub.items():
            if active and not in_alert:
                in_alert = True
                a_start = ts
            elif not active and in_alert:
                ax1.axvspan(a_start, ts, color=color, alpha=0.15, zorder=2)
                in_alert = False
        if in_alert and a_start is not None:
            ax1.axvspan(a_start, ser_sub.index[-1], color=color, alpha=0.15, zorder=2)

    # Catalogued event window markers.
    overlapping_events = []
    for _, evt in df_events.iterrows():
        t_s = pd.Timestamp(evt["analysis_start"])
        t_e = pd.Timestamp(evt["analysis_end"])
        if t_e >= period_start and t_s <= period_end:
            overlapping_events.append(evt)
            ax1.axvline(t_s, color="navy", lw=1.0, ls=":", alpha=0.7, zorder=4)
            ax1.axvline(t_e, color="navy", lw=1.0, ls=":", alpha=0.7, zorder=4)
            ax1.axvspan(t_s, t_e, color="navy", alpha=0.04, zorder=2)
            ax1.text(
                t_s,
                LEVEL_PLOT_MAX - 10,
                f"E{int(evt['event_num']):02d}\n{evt['level']}",
                fontsize=6.5,
                color="navy",
                va="top",
                ha="left",
                zorder=8,
                fontweight="bold",
            )

    ax1.set_ylabel("Cota (cm)")
    ax1.set_ylim(0, LEVEL_PLOT_MAX + 20)

    # Legend.
    legend_patches = [
        mpatches.Patch(color="black", label="Observado"),
        mpatches.Patch(color="deeppink", label="M4 +60 min deslocado"),
        mpatches.Patch(color="purple", label="M4 +120 min deslocado"),
        mpatches.Patch(color="navy", label="Janela evento catalogado"),
    ]
    for n_steps, color in zip(config.DEBOUNCE_STEPS, DEBOUNCE_COLORS):
        legend_patches.append(
            mpatches.Patch(
                color=color,
                alpha=0.5,
                label=f"Alerta debounce={n_steps} ({n_steps*5} min)",
            )
        )
    ax1.legend(handles=legend_patches, loc="upper right", fontsize=7.5, ncol=2)

    event_label = (
        f"E{int(overlapping_events[0]['event_num']):02d} "
        f"({overlapping_events[0]['level']})"
        if overlapping_events
        else "Período detectado"
    )
    ax1.set_title(
        f"Simulado Contínuo — Período detectado #{period_idx:03d}  |  {event_label}\n"
        f"{period_start.strftime('%Y-%m-%d %H:%M')} → {period_end.strftime('%Y-%m-%d %H:%M')} UTC",
        fontsize=9,
    )

    # Precipitation panel.
    if "h_obs" in sub.columns:
        precip_col = "prec_obs"
        # No precip in df_preds — draw dh/dt as a proxy for rate.
        dh = sub["h_obs"].diff() / config.RESAMPLE_MIN
        dh_pos = dh.clip(lower=0)
        ax2.fill_between(
            sub.index, 0, dh_pos, color="teal", alpha=0.4, label="dh/dt (subida)"
        )
        ax2.plot(sub.index, dh, color="teal", lw=0.8)
        ax2.axhline(0, color="gray", lw=0.7)
        ax2.set_ylabel("dh/dt\n(cm/min)", fontsize=8)

    ax2.set_xlabel("Data/Hora (UTC)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))

    fig.tight_layout()
    path = os.path.join(out_dir, f"event_detected_{period_idx:03d}.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"    Saved {os.path.basename(path)}")


def plot_alert_timeline(
    df_preds: pd.DataFrame,
    df_events: pd.DataFrame,
    alert_by_thresh_debounce: "dict[tuple, pd.Series]",
    threshold_cm: float,
    threshold_name: str,
    out_dir: str,
) -> None:
    """Save alert-state timeline for one threshold across all debounce scenarios.

    Three vertically-stacked subplots (one per debounce scenario) show the binary
    alert state as red shading, the observed level as a grey line, and catalogued
    events as vertical markers colour-coded by VP / FP / FN outcome.

    @param df_preds                   Full predictions DataFrame.
    @param df_events                  Events catalogue DataFrame.
    @param alert_by_thresh_debounce   Dict keyed by (threshold_cm, n_consecutive) → boolean Series.
    @param threshold_cm               Threshold being plotted.
    @param threshold_name             Human-readable threshold name.
    @param out_dir                    Output directory.
    """
    fig, axes = plt.subplots(
        len(config.DEBOUNCE_STEPS),
        1,
        figsize=(22, 3.5 * len(config.DEBOUNCE_STEPS)),
        sharex=True,
    )
    if len(config.DEBOUNCE_STEPS) == 1:
        axes = [axes]

    events_at_thresh = df_events[df_events["peak_cm"] >= threshold_cm]
    df_ts = df_preds.set_index("timestamp")

    for ax, n_steps in zip(axes, config.DEBOUNCE_STEPS):
        key = (threshold_cm, n_steps)
        alert_ser = alert_by_thresh_debounce.get(key, pd.Series(dtype=bool))
        alert_ser.index = pd.to_datetime(alert_ser.index)

        # Observed level (background reference).
        ax.plot(
            df_ts.index,
            df_ts["h_obs"],
            color="lightgray",
            lw=0.7,
            zorder=1,
            label="Observado",
        )
        ax.axhline(
            threshold_cm,
            color=THRESHOLD_COLORS[threshold_name],
            lw=1.2,
            ls="--",
            zorder=2,
        )

        # Alert shading.
        in_alert = False
        a_start = None
        for ts, active in alert_ser.items():
            if active and not in_alert:
                in_alert = True
                a_start = ts
            elif not active and in_alert:
                ax.axvspan(a_start, ts, color="red", alpha=0.25, zorder=3)
                in_alert = False
        if in_alert and a_start is not None:
            ax.axvspan(a_start, alert_ser.index[-1], color="red", alpha=0.25, zorder=3)

        # Catalogued events: VP (green) / FN (orange).
        for _, evt in events_at_thresh.iterrows():
            t_start = pd.Timestamp(evt["analysis_start"])
            t_end = pd.Timestamp(evt["analysis_end"])
            window_alerts = (
                alert_ser.loc[t_start:t_end]
                if t_start in alert_ser.index or t_end in alert_ser.index
                else pd.Series(dtype=bool)
            )
            outcome = "VP" if window_alerts.any() else "FN"
            color = "forestgreen" if outcome == "VP" else "darkorange"
            ax.axvline(t_start, color=color, lw=1.6, ls="--", zorder=4, alpha=0.9)
            ax.text(
                t_start,
                threshold_cm + 3,
                f"E{int(evt['event_num']):02d}\n{outcome}",
                fontsize=6,
                color=color,
                ha="left",
                va="bottom",
                fontweight="bold",
                zorder=5,
            )

        ax.set_ylabel("Cota (cm)", fontsize=8)
        ax.set_ylim(0, LEVEL_PLOT_MAX)
        ax.set_title(
            f"Debounce {n_steps} passo{'s' if n_steps > 1 else ''} ({n_steps * config.RESAMPLE_MIN} min)",
            fontsize=9,
        )
        ax.grid(which="major", ls="-", lw=0.4, color="lightgray", alpha=0.5)

    axes[-1].set_xlabel("Data/Hora (UTC)")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m\n%d"))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())

    fig.suptitle(
        f"Simulado Contínuo — Estado de alerta: {threshold_name} (≥ {threshold_cm:.0f} cm)  "
        f"|  Verde=VP  Laranja=FN  Vermelho=Falso Alarme (FP)",
        fontsize=11,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    slug = threshold_name.lower().replace("ã", "a").replace("ç", "c")
    path = os.path.join(out_dir, f"alert_timeline_{slug}.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  Saved {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Train M4 on real training events (E1/4/7/8) and run full continuous backtesting."""
    out_dir = config.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 66)
    print("  M4 LightGBM (Darts) — Simulado Contínuo  [v3]")
    print("=" * 66)

    # ── 1. Data ──────────────────────────────────────────────────────────────
    print("\n[1/5] Loading real data ...")
    ts_level, ts_precip, df_events = real_utils.load_real_data()
    n_train = (df_events["split_set"] == "train").sum()
    n_test = (df_events["split_set"] == "test").sum()
    print(f"  Level steps  : {len(ts_level):,}  |  Precip steps: {len(ts_precip):,}")
    print(f"  Level range  : {ts_level.start_time()} → {ts_level.end_time()}")
    print(f"  Events       : {len(df_events)} total  ({n_train} train / {n_test} test)")

    # ── 2. Training segments ─────────────────────────────────────────────────
    print("\n[2/5] Building training segments ...")
    print(f"  Mode: {config.TRAIN_MODE}")
    if config.TRAIN_MODE == "continuous":
        # Fit on an unbroken period of record (floods AND dry weather) so the
        # training and inference populations match — see Issue #223.
        print(f"  Train period: record start -> {config.TRAIN_END}")
        ts_train, pc_train = real_utils.build_continuous_training_segment(
            ts_level, ts_precip
        )
    else:
        ts_train, pc_train = real_utils.build_training_segments(
            ts_level, ts_precip, df_events, buffer_steps=config.LGBM_BUFFER_STEPS
        )
    if not ts_train:
        print("  ERROR: No valid training segments. Aborting.")
        return
    print(
        f"  {len(ts_train)} segments  |  "
        f"Lengths: {min(len(s) for s in ts_train)}–{max(len(s) for s in ts_train)} steps"
    )

    # ── 3. Training ──────────────────────────────────────────────────────────
    print("\n[3/5] Training LightGBM ...")
    model = build_model()
    model.fit(ts_train, past_covariates=pc_train)
    print("  Training complete.")

    # ── 4. Continuous rolling prediction ─────────────────────────────────────
    print("\n[4/5] Continuous rolling prediction (vectorised historical_forecasts) ...")
    print(f"  Debounce scenarios: {config.DEBOUNCE_STEPS}")
    df_preds = continuous_rolling_predict(model, ts_level, ts_precip)
    # Sensor-artifact windows are not river level (Issue #227).
    df_preds = real_utils.mask_artifact_rows(df_preds)

    csv_path = os.path.join(out_dir, "continuous_predictions.csv")
    df_preds.to_csv(csv_path, index=False)
    print(f"  Saved {csv_path}  ({len(df_preds):,} rows)")

    # ── 5. Alert analysis ────────────────────────────────────────────────────
    print("\n[5/5] Alert analysis and plots ...")
    alert_by_td: dict[tuple, pd.Series] = {}
    cm_records: list[dict] = []

    for thresh_name, thresh_cm in THRESHOLDS.items():
        for n_steps in config.DEBOUNCE_STEPS:
            alert_ser = apply_debounce_alert(df_preds, thresh_cm, n_steps)
            alert_by_td[(thresh_cm, n_steps)] = alert_ser

            cm = compute_confusion_matrix(
                df_preds, df_events, thresh_cm, thresh_name, n_steps
            )
            cm_records.append(cm)
            print(
                f"  {thresh_name:10s} debounce={n_steps}  "
                f"VP={cm['VP']} FP={cm['FP']} FN={cm['FN']}  "
                f"precision={cm['precision']}  recall={cm['recall']}  F1={cm['F1']}"
            )

    df_cm = pd.DataFrame(cm_records)
    cm_path = os.path.join(out_dir, "alert_analysis.csv")
    df_cm.to_csv(cm_path, index=False)
    print(f"  Saved {cm_path}")

    # Alert-state timeline plots (one per threshold).
    for thresh_name, thresh_cm in THRESHOLDS.items():
        plot_alert_timeline(
            df_preds,
            df_events,
            alert_by_td,
            thresh_cm,
            thresh_name,
            out_dir,
        )

    # Per-detected-period zoomed plots.
    periods = detect_flood_periods(df_preds)
    print(f"\n  Auto-detected flood periods: {len(periods)}")

    # Build per-Inundação-debounce alert series for the zoomed plots (all scenarios).
    alert_by_steps: dict[int, pd.Series] = {
        n: alert_by_td[(config.THRESHOLD_INUNDACAO, n)]
        for n in config.DEBOUNCE_STEPS
        if (config.THRESHOLD_INUNDACAO, n) in alert_by_td
    }

    for idx, (p_start, p_end) in enumerate(periods, start=1):
        plot_detected_event(
            df_preds,
            df_events,
            alert_by_steps,
            p_start,
            p_end,
            idx,
            out_dir,
        )

    print(f"\nAll outputs in: {out_dir}")
    print("=== SIMULADO CONTÍNUO DONE ===\n")


if __name__ == "__main__":
    main()
