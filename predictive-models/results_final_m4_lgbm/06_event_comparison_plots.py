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
@file 06_event_comparison_plots.py
@brief Standardized per-event comparison figures for M4 (LightGBM) and M6 (MLR) — Issue #142.

Generates 8 dissertation-quality figures — 4 events × 2 models — with a uniform
visual specification so that M4 and M6 plots can be placed side by side in cap4
(subseção "Análise Individual por Evento de Inundação").

Target events: E02, E09, E18, E19 (defined in event_windows_v2.csv).

Uniform specification (identical for M4 and M6):
  - Temporal window: analysis_start → analysis_end from event_windows_v2.csv (±1 h padding)
  - Thresholds displayed: 50 cm (Atenção), 60 cm (Alerta), 75 cm (Inundação) — predicted
  - Horizons displayed: +30, +60, +90, +120 min (time-shifted to verification time)
  - Lower subplot: real precipitation (mm/5min) — identical between M4 and M6
  - Black line: observed level — must be visually identical for the same event
  - Alert marker: first debounce trigger per threshold (gate 5 mm/6h, debounce 3×5 min)

Output:
  Documentation/predictive_model/methodology_images/m4_lgbm/event_E{XX}_m4.png
  Documentation/predictive_model/methodology_images/m6_mlr/event_E{XX}_m6.png

Usage (run from the results_final_m4_lgbm/ folder):
    cd AppTest/raspberry/predictive_model_darts/results_final_m4_lgbm/
    python3 06_event_comparison_plots.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import config  # M4 config — thresholds and DATA_DIR are identical to M6

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Four levels up from results_final_m4_lgbm/ reaches the repository root.
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
METHODOLOGY_DIR = os.path.join(
    _REPO, "Documentation", "predictive_model", "methodology_images"
)

M4_PREDS_CSV = os.path.join(_HERE, "output", "continuous_predictions.csv")
M6_PREDS_CSV = os.path.join(
    _HERE, "..", "results_final_m6_mlr", "output", "continuous_predictions_m6.csv"
)
EVENTS_CSV = os.path.join(_HERE, "event_windows_v2.csv")

# merge_20260404.csv covers the full historical period needed for E02 and E09
# (the rolling cache merge_precip.csv only covers the last 7 days).
MERGE_ARCHIVE_CSV = os.path.join(config.DATA_DIR, "merge_20260404.csv")
STATION02_CSV     = os.path.join(config.DATA_DIR, "station02_precip.csv")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_EVENTS  = [2, 9, 18, 19]
"""event_num values to generate plots for (E02, E09, E18, E19)."""

GATE_MM        = 5
"""Operational precipitation gate threshold (mm over GATE_HOURS)."""

GATE_HOURS     = 6
"""Rolling window for the precipitation gate (hours)."""

DEBOUNCE_STEPS = 3
"""Operational debounce: 3 consecutive 5-min steps = 15 min."""

PLOT_PAD_HOURS = 1
"""Hours of context added before/after analysis window for display."""

LEVEL_PLOT_MAX = 200
"""Y-axis ceiling for the level panel (cm)."""

RESAMPLE_MIN = config.RESAMPLE_MIN

PRECIP_CUTOFF_NAIVE = pd.Timestamp("2026-01-02")
"""Splice point for precipitation sources (tz-naive, UTC equivalent)."""

# Horizon colour + linestyle for the prediction lines.
HORIZON_STYLE: dict[int, tuple[str, str]] = {
    30:  ("cornflowerblue", ":"),
    60:  ("deeppink",       "--"),
    90:  ("darkorange",     "-."),
    120: ("purple",         (0, (5, 2))),
}

# Threshold definitions: (threshold_cm, line_colour, display_label)
THRESHOLD_DEFS: list[tuple] = [
    (config.THRESHOLD_ATENCAO,   "goldenrod",  "Atenção (50 cm)"),
    (config.THRESHOLD_ALERTA,    "darkorange", "Alerta (60 cm)"),
    (config.THRESHOLD_INUNDACAO, "red",        "Inundação (75 cm)"),
]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_precip_series() -> pd.Series:
    """Load spliced precipitation series: MERGE archive before PRECIP_CUTOFF,
    Station-02 tipping-bucket from PRECIP_CUTOFF onward.

    @return Pandas Series indexed by tz-naive timestamps (5-min grid), values in mm/5min.
    """
    freq = f"{RESAMPLE_MIN}min"

    # MERGE archive (timestamp column, tz-naive in CSV → treat as UTC then strip)
    df_merge = pd.read_csv(MERGE_ARCHIVE_CSV, parse_dates=["timestamp"])
    df_merge["timestamp"] = pd.to_datetime(df_merge["timestamp"], utc=True)
    df_merge = df_merge.set_index("timestamp").sort_index()[["prec_mm"]]
    df_merge_5min = df_merge.resample(freq).ffill() / 12   # hourly → 5-min slots
    df_merge_5min["prec_mm"] = df_merge_5min["prec_mm"].fillna(0.0)
    df_merge_5min.index = df_merge_5min.index.tz_localize(None)

    # Station-02 tipping-bucket (tz-aware UTC → strip)
    df_st02 = pd.read_csv(STATION02_CSV, parse_dates=["timestamp"])
    df_st02["timestamp"] = pd.to_datetime(df_st02["timestamp"], utc=True)
    df_st02 = df_st02.set_index("timestamp").sort_index()[["precipitation_mm"]]
    df_st02_5min = df_st02.resample(freq).sum()
    df_st02_5min.columns = ["prec_mm"]
    df_st02_5min["prec_mm"] = df_st02_5min["prec_mm"].fillna(0.0)
    df_st02_5min.index = df_st02_5min.index.tz_localize(None)

    # Splice at PRECIP_CUTOFF
    part_merge = df_merge_5min[df_merge_5min.index <  PRECIP_CUTOFF_NAIVE]
    part_st02  = df_st02_5min[ df_st02_5min.index  >= PRECIP_CUTOFF_NAIVE]
    combined   = pd.concat([part_merge, part_st02]).sort_index()
    combined   = combined[~combined.index.duplicated(keep="first")]
    return combined["prec_mm"].fillna(0.0)


def load_predictions(csv_path: str) -> pd.DataFrame:
    """Load a continuous predictions CSV (M4 or M6).

    @param csv_path  Absolute path to the CSV file.
    @return DataFrame with columns: timestamp, h_obs, h_pred_{30,60,90,120}, ...
    @raises SystemExit if the file does not exist.
    """
    if not os.path.exists(csv_path):
        print(f"ERROR: predictions file not found:\n  {csv_path}")
        sys.exit(1)
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_events() -> pd.DataFrame:
    """Load event windows CSV with tz-naive timestamps.

    @return DataFrame with columns: event_num, peak_time, peak_cm,
            analysis_start, analysis_end, split_set, type, level.
    """
    df = pd.read_csv(EVENTS_CSV, encoding="utf-8-sig")
    for col in ("peak_time", "analysis_start", "analysis_end"):
        df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
    df = df[df["split_set"] != "excluded"].reset_index(drop=True)
    return df

# ---------------------------------------------------------------------------
# Alert logic
# ---------------------------------------------------------------------------


def compute_gated_alert(
    df_preds: pd.DataFrame,
    precip_ser: pd.Series,
    threshold_cm: float,
) -> pd.Series:
    """Compute boolean alert series with operational gate + debounce.

    Pipeline:
      1. Rolling precipitation sum over GATE_HOURS (72 × 5-min steps).
      2. Gate condition: rolling_precip >= GATE_MM.
      3. Raw signal: any horizon prediction >= threshold_cm AND gate active.
      4. Debounce: DEBOUNCE_STEPS consecutive raw-signal steps required.

    @param df_preds       Full continuous predictions DataFrame.
    @param precip_ser     Precipitation Series (5-min, tz-naive), mm/5min.
    @param threshold_cm   Alert threshold in cm.
    @return Boolean Series indexed by timestamp; True = alert active.
    """
    df  = df_preds.set_index("timestamp").copy()
    idx = df.index

    gate_steps     = int(GATE_HOURS * 60 / RESAMPLE_MIN)
    precip_aln     = precip_ser.reindex(idx, fill_value=0.0)
    rolling_precip = precip_aln.rolling(window=gate_steps, min_periods=1).sum()
    gate_cond      = rolling_precip >= GATE_MM

    raw = pd.Series(False, index=idx)
    for h in config.HORIZONS_MIN:
        col = f"h_pred_{h}"
        if col in df.columns:
            raw |= df[col].fillna(0) >= threshold_cm
    raw &= gate_cond

    if DEBOUNCE_STEPS <= 1:
        return raw

    return (
        raw.rolling(window=DEBOUNCE_STEPS, min_periods=DEBOUNCE_STEPS)
        .apply(lambda w: bool(w.all()), raw=True)
        .fillna(False)
        .astype(bool)
    )

# ---------------------------------------------------------------------------
# Per-event figure
# ---------------------------------------------------------------------------


def plot_event(
    event_row: pd.Series,
    df_preds: pd.DataFrame,
    precip_ser: pd.Series,
    model_label: str,
    model_tag: str,
    out_dir: str,
) -> None:
    """Generate and save a standardized event comparison figure.

    @param event_row   Row from the events catalogue DataFrame.
    @param df_preds    Full predictions DataFrame for one model.
    @param precip_ser  Spliced precipitation Series (5-min, tz-naive).
    @param model_label Human-readable model name, e.g. "M4 LightGBM".
    @param model_tag   Short tag for the file name: "m4" or "m6".
    @param out_dir     Root methodology_images/ directory.
    """
    event_num = int(event_row["event_num"])
    t_start   = event_row["analysis_start"]
    t_end     = event_row["analysis_end"]
    peak_time = event_row["peak_time"]
    peak_cm   = float(event_row["peak_cm"])
    ev_level  = str(event_row.get("level", ""))

    # Display window with padding
    pad       = pd.Timedelta(hours=PLOT_PAD_HOURS)
    win_start = max(t_start - pad, df_preds["timestamp"].min())
    win_end   = min(t_end   + pad, df_preds["timestamp"].max())

    mask = (df_preds["timestamp"] >= win_start) & (df_preds["timestamp"] <= win_end)
    sub  = df_preds[mask].set_index("timestamp")
    if sub.empty:
        print(f"  [WARN] No data in window for E{event_num:02d} — skipping.")
        return

    precip_sub = precip_ser.reindex(sub.index, fill_value=0.0)

    # Pre-compute alert series for all 3 thresholds (full series, then subset)
    alert_sub: dict[float, pd.Series] = {}
    for thresh_cm, _, _ in THRESHOLD_DEFS:
        full_ser = compute_gated_alert(df_preds, precip_ser, thresh_cm)
        full_ser.index = pd.to_datetime(full_ser.index)
        alert_sub[thresh_cm] = full_ser.reindex(sub.index, fill_value=False)

    # ── Figure layout ─────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    for ax in (ax1, ax2):
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[0, 30]))
        ax.grid(which="major", ls="-",  lw=0.5, color="lightgray", alpha=0.55)
        ax.grid(which="minor", ls="--", lw=0.3, color="lightgray", alpha=0.30)

    # ── Level panel (ax1) ─────────────────────────────────────────────────────

    # Background threshold bands
    band_defs = [
        (config.THRESHOLD_ATENCAO,   config.THRESHOLD_ALERTA,    "goldenrod",  0.07),
        (config.THRESHOLD_ALERTA,    config.THRESHOLD_INUNDACAO,  "darkorange", 0.08),
        (config.THRESHOLD_INUNDACAO, LEVEL_PLOT_MAX + 20,         "red",        0.08),
    ]
    for ylo, yhi, color, alpha in band_defs:
        ax1.axhspan(ylo, yhi, color=color, alpha=alpha, zorder=1)

    # Threshold dashed lines
    for thresh_cm, color, _ in THRESHOLD_DEFS:
        ax1.axhline(thresh_cm, color=color, lw=1.0, ls="--", alpha=0.85, zorder=3)

    # Event analysis window boundary
    ax1.axvline(t_start, color="navy", lw=1.0, ls=":", alpha=0.7, zorder=4)
    ax1.axvline(t_end,   color="navy", lw=1.0, ls=":", alpha=0.7, zorder=4)
    ax1.axvspan(t_start, t_end, color="navy", alpha=0.04, zorder=2)

    # Observed level — the black reference line
    ax1.plot(
        sub.index, sub["h_obs"],
        color="black", lw=1.8, label="Cota observada", zorder=5,
    )

    # Predicted horizons shifted to verification time
    legend_handles: list[mpatches.Patch] = [
        mpatches.Patch(color="black", label="Cota observada"),
    ]
    for h in [30, 60, 90, 120]:
        col = f"h_pred_{h}"
        if col not in sub.columns:
            continue
        color, ls = HORIZON_STYLE[h]
        shifted_t = sub.index + pd.Timedelta(minutes=h)
        ax1.plot(
            shifted_t, sub[col],
            color=color, lw=1.1, ls=ls, alpha=0.85, zorder=4,
        )
        legend_handles.append(
            mpatches.Patch(color=color, label=f"{model_label} +{h} min")
        )

    # Alert trigger markers: first debounce fire per threshold within analysis window
    mask_win = (sub.index >= t_start) & (sub.index <= t_end)
    for thresh_cm, color, thresh_label in THRESHOLD_DEFS:
        ser_win = alert_sub[thresh_cm][mask_win]
        if not ser_win.any():
            continue
        first_t = ser_win[ser_win].index[0]
        # Vertical dotted line at trigger moment
        ax1.axvline(first_t, color=color, lw=2.0, ls=":", zorder=6, alpha=0.95)
        # Small upward-pointing triangle at threshold height
        ax1.plot(first_t, thresh_cm, marker="^", color=color, ms=7, zorder=7)
    # Threshold legend entries
    for thresh_cm, color, thresh_label in THRESHOLD_DEFS:
        legend_handles.append(mpatches.Patch(color=color, alpha=0.7, label=thresh_label))

    ax1.set_ylabel("Cota (cm)", fontsize=9)
    ax1.set_ylim(25, LEVEL_PLOT_MAX)
    ax1.legend(handles=legend_handles, loc="upper right", fontsize=7.5, ncol=2,
               framealpha=0.85, edgecolor="grey")
    ax1.set_title(
        f"{model_label} — Evento E{event_num:02d} ({ev_level})  |  "
        f"Pico {peak_cm:.0f} cm  {peak_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"Gate {GATE_MM} mm/{GATE_HOURS}h · Debounce {DEBOUNCE_STEPS}×{RESAMPLE_MIN} min  "
        f"| Janela: {t_start.strftime('%m-%d %H:%M')} → {t_end.strftime('%m-%d %H:%M')} UTC",
        fontsize=9,
    )

    # ── Precipitation panel (ax2) ─────────────────────────────────────────────
    ax2.bar(
        precip_sub.index, precip_sub.values,
        width=pd.Timedelta(minutes=RESAMPLE_MIN),
        color="steelblue", alpha=0.7, align="edge",
    )
    ax2.set_ylabel("Precip.\n(mm/5min)", fontsize=8)
    ax2.set_xlabel("Data/Hora (UTC)", fontsize=9)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d\n%H:%M"))
    ax2.set_xlim(win_start, win_end)
    ax2.tick_params(axis="x", which="major", labelsize=8)

    fig.tight_layout()

    # ── Save ──────────────────────────────────────────────────────────────────
    subdir   = "m4_lgbm" if model_tag == "m4" else "m6_mlr"
    fname    = f"event_E{event_num:02d}_{model_tag}.png"
    out_path = os.path.join(out_dir, subdir, fname)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out_path}")

# ---------------------------------------------------------------------------
# h_obs consistency check
# ---------------------------------------------------------------------------


def check_hobs_consistency(
    df_m4: pd.DataFrame,
    df_m6: pd.DataFrame,
    df_events: pd.DataFrame,
) -> None:
    """Verify that the observed level is identical between M4 and M6.

    For each target event the maximum absolute difference is reported.
    Any divergence > 0.01 cm indicates a data-loading inconsistency and must
    be investigated before the plots are used in the dissertation.

    @param df_m4       M4 predictions DataFrame.
    @param df_m6       M6 predictions DataFrame.
    @param df_events   Events catalogue DataFrame.
    """
    print("\n[CHECK] h_obs consistency M4 vs M6:")
    all_ok = True
    for ev_num in TARGET_EVENTS:
        rows = df_events[df_events["event_num"] == ev_num]
        if rows.empty:
            print(f"  E{ev_num:02d}: event not found in catalogue")
            continue
        ev    = rows.iloc[0]
        t_s   = ev["analysis_start"]
        t_e   = ev["analysis_end"]
        m4_s  = df_m4[(df_m4["timestamp"] >= t_s) & (df_m4["timestamp"] <= t_e)] \
                    .set_index("timestamp")["h_obs"]
        m6_s  = df_m6[(df_m6["timestamp"] >= t_s) & (df_m6["timestamp"] <= t_e)] \
                    .set_index("timestamp")["h_obs"]
        common = m4_s.index.intersection(m6_s.index)
        if len(common) == 0:
            print(f"  E{ev_num:02d}: NO common timestamps — investigation needed!")
            all_ok = False
            continue
        diff = (m4_s.reindex(common) - m6_s.reindex(common)).abs().max()
        status = "OK" if diff < 0.01 else "DIVERGING — investigate!"
        if diff >= 0.01:
            all_ok = False
        print(f"  E{ev_num:02d}: max |h_obs_M4 - h_obs_M6| = {diff:.4f} cm  [{status}]")
    if all_ok:
        print("  All events: h_obs identical between M4 and M6 ✓")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Load predictions, verify consistency, and generate comparison plots."""
    print("=" * 66)
    print("  Event Comparison Plots — M4 vs M6  (Issue #142)")
    print("=" * 66)

    print(f"\n[1/4] Loading M4 predictions:\n  {M4_PREDS_CSV}")
    df_m4 = load_predictions(M4_PREDS_CSV)
    print(f"  {len(df_m4):,} rows  ({df_m4['timestamp'].min()} → {df_m4['timestamp'].max()})")

    print(f"\n[2/4] Loading M6 predictions:\n  {M6_PREDS_CSV}")
    df_m6 = load_predictions(M6_PREDS_CSV)
    print(f"  {len(df_m6):,} rows  ({df_m6['timestamp'].min()} → {df_m6['timestamp'].max()})")

    print(f"\n[3/4] Loading precipitation (MERGE archive + Station-02) ...")
    precip = load_precip_series()
    print(f"  {len(precip):,} steps  ({precip.index.min()} → {precip.index.max()})")

    print(f"\n[4/4] Loading event windows:\n  {EVENTS_CSV}")
    df_events = load_events()
    print(f"  {len(df_events)} events loaded")

    check_hobs_consistency(df_m4, df_m6, df_events)

    print(f"\nGenerating plots for events: {TARGET_EVENTS}")
    print(f"Gate: {GATE_MM} mm/{GATE_HOURS}h  |  Debounce: {DEBOUNCE_STEPS}×{RESAMPLE_MIN} min")
    print(f"Output directory: {METHODOLOGY_DIR}")

    os.makedirs(os.path.join(METHODOLOGY_DIR, "m4_lgbm"), exist_ok=True)
    os.makedirs(os.path.join(METHODOLOGY_DIR, "m6_mlr"),  exist_ok=True)

    for ev_num in TARGET_EVENTS:
        rows = df_events[df_events["event_num"] == ev_num]
        if rows.empty:
            print(f"\n[WARN] Event {ev_num} not found in catalogue — skipping.")
            continue
        ev = rows.iloc[0]
        print(
            f"\n--- E{ev_num:02d}  peak={ev['peak_cm']} cm  "
            f"({ev['analysis_start'].strftime('%Y-%m-%d %H:%M')} → "
            f"{ev['analysis_end'].strftime('%Y-%m-%d %H:%M')}) ---"
        )
        plot_event(ev, df_m4, precip, "M4 LightGBM", "m4", METHODOLOGY_DIR)
        plot_event(ev, df_m6, precip, "M6 MLR",      "m6", METHODOLOGY_DIR)

    print("\n=== EVENT COMPARISON PLOTS DONE ===\n")


if __name__ == "__main__":
    main()
