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
@file scan_audit_findings.py
@brief Numeric scan across the 20 catalogued events, flagging exactly the
       anomalies documented in Documentation/predictive_model/auditoria_lead_time_rmse_20eventos.md.

Reuses the data-loading functions from plot_events_audit_pdf.py (raw level from
the SQL dump, filtered level from real_utils.load_real_data(), and the already
published M4/M6 lead-time and RMSE CSVs) to print, without generating the PDF:

  0. Forecast calibration — mean bias and threshold-exceedance frequency per
     model and horizon, split in-sample vs out-of-sample. This is the only
     scan that looks at the dry weather making up ~98% of the record, and so
     the only one able to catch a model that is permanently in alarm
     (Issue #223). Available on its own via --calibration, which skips the
     slow SQL dump parse.
  1. Catalogued peak_cm vs. the FILTERED series' own max within the event
     window (flags a mismatch — evidence of a residual outlier that survived
     the delta filter, e.g. Events 14 and 20).
  2. "Normal" (non-flood) events that nonetheless appear in the lead-time
     summary tables — they should not, since there is no real threshold
     crossing to time.
  3. Lead times with |value| > 180 min (implausible for windows a few hours
     wide — usually a symptom of #1, or of prediction noise crossing a
     threshold early).
  4. Negative lead times (the model's predicted crossing happened AFTER the
     real one — a late warning, not an early one).
  5. Per-event RMSE outliers (> 2.5x the median for that horizon/model).

Usage (requires the Darts venv, same as plot_events_audit_pdf.py):
    cd AppTest/raspberry/predictive_model_darts/
    /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 scan_audit_findings.py

    # calibration table only (~40 s, no SQL dump needed):
    /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 scan_audit_findings.py --calibration

@author Alexandre Nuernberg
@date 2026-09-08
"""

import sys

import pandas as pd

import plot_events_audit_pdf as audit

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def scan_peak_divergence(df_events, df_filtered, df_raw):
    """
    @brief Compare each event's catalogued peak_cm against the FILTERED
           series' own max within the analysis window.

    Deliberately does not compare against the raw series — a raw-only
    outlier is expected to be rejected by the delta filter and is not
    evidence of a catalogue error (see PEAK_TOLERANCE_CM in
    plot_events_audit_pdf.py).

    @param df_events pd.DataFrame Event catalogue (tz-naive UTC dates).
    @param df_filtered pd.Series Filtered level_delta_cm, full history.
    @param df_raw pd.Series Raw level_cm, full history.
    @return pd.DataFrame One row per event with peak/max/diff columns.
    """
    rows = []
    for _, evt in df_events.iterrows():
        win_start, win_end = evt["analysis_start"], evt["analysis_end"]
        filt_win = df_filtered.loc[win_start:win_end]
        raw_win = df_raw.loc[win_start:win_end]
        if filt_win.empty:
            continue
        filt_max = filt_win.max()
        rows.append(
            {
                "event": int(evt["event_num"]),
                "type": evt["type"],
                "level": evt["level"],
                "peak_cm": evt["peak_cm"],
                "peak_time": evt["peak_time"],
                "filt_max": round(filt_max, 1),
                "filt_max_t": filt_win.idxmax(),
                "raw_max": (
                    round(raw_win.max(), 1) if not raw_win.empty else float("nan")
                ),
                "raw_max_t": raw_win.idxmax() if not raw_win.empty else None,
                "diff": round(filt_max - evt["peak_cm"], 1),
            }
        )
    return pd.DataFrame(rows)


def scan_normal_events_in_lead_time(df_events, lead_m4, lead_m6):
    """
    @brief Flag catalogue events of type "Normal" that still appear in the
           lead-time summary tables (they should not — no real crossing).

    @param df_events pd.DataFrame Event catalogue.
    @param lead_m4 pd.DataFrame lead_time_summary_m4.csv.
    @param lead_m6 pd.DataFrame lead_time_summary_m6.csv.
    @return tuple(set normal_events, set flagged_m4, set flagged_m6)
    """
    normal_events = set(
        df_events.loc[df_events["type"] == "Normal", "event_num"].astype(int)
    )
    flagged_m4 = normal_events & set(lead_m4["event_num"].unique())
    flagged_m6 = normal_events & set(lead_m6["event_num"].unique())
    return normal_events, flagged_m4, flagged_m6


def scan_extreme_lead_times(df, threshold_min=180):
    """
    @brief Melt a lead_time_summary_* table and return rows with
           |lead_time| above threshold_min.
    @param df pd.DataFrame lead_time_summary_m4/m6.csv.
    @param threshold_min float Absolute lead-time threshold in minutes.
    @return pd.DataFrame Long-format rows exceeding the threshold.
    """
    cols = [c for c in df.columns if c.startswith("lead_time_")]
    melted = df.melt(
        id_vars=["event_num", "peak_cm", "threshold_name", "threshold_cm"],
        value_vars=cols,
        var_name="horizon",
        value_name="lead_time_min",
    )
    return melted[melted["lead_time_min"].abs() > threshold_min].sort_values(
        "event_num"
    )


def scan_negative_lead_times(df):
    """
    @brief Melt a lead_time_summary_* table and return negative rows (late
           warning — the model crossed the threshold after the real crossing).
    @param df pd.DataFrame lead_time_summary_m4/m6.csv.
    @return pd.DataFrame Long-format negative rows.
    """
    cols = [c for c in df.columns if c.startswith("lead_time_")]
    melted = df.melt(
        id_vars=["event_num", "peak_cm", "threshold_name", "threshold_cm"],
        value_vars=cols,
        var_name="horizon",
        value_name="lead_time_min",
    )
    return melted[melted["lead_time_min"] < 0].sort_values(
        ["event_num", "threshold_name"]
    )


def scan_rmse_outliers(rmse, horizons=(30, 60, 90, 120), factor=2.5):
    """
    @brief Flag per-event RMSE values above factor times the per-model median
           for that horizon.
    @param rmse pd.DataFrame rmse_per_event.csv (columns: model, event_num,
           peak_cm, rmse_30/60/90/120).
    @param horizons tuple Horizons in minutes to check.
    @param factor float Outlier multiplier applied to the median.
    @return dict {horizon: pd.DataFrame} outlier rows per horizon.
    """
    out = {}
    for h in horizons:
        col = f"rmse_{h}"
        med = rmse.groupby("model")[col].transform("median")
        flagged = rmse[rmse[col] > med * factor]
        if not flagged.empty:
            out[h] = flagged[["model", "event_num", "peak_cm", col]]
    return out


def explain_event_crossings(
    event_num,
    df_events,
    m4_pred,
    m6_pred,
    lead_m4,
    lead_m6,
    df_precip=None,
    context_min=15,
):
    """
    @brief Print, for one event, exactly why each published lead-time number
           looks the way it does: every observed crossing occurrence, the
           instant each model's persistent alarm fired for it per horizon
           (Issue #229 rule, via audit.event_occurrences()), and a
           +/-context_min window of h_obs/h_pred_H/h_actual_H (and
           precipitation, if given) around every firing — enough to tell a
           genuine early signal apart from a noise/precipitation blip.

    This is the same manual check used to explain Events 13, 14 and 20 in
    Documentation/predictive_model/auditoria_lead_time_rmse_20eventos.md —
    generalized so it can be pointed at any event number.

    @param event_num int Event number to inspect.
    @param df_events pd.DataFrame Event catalogue (tz-naive UTC dates).
    @param m4_pred pd.DataFrame continuous_predictions.csv (M4).
    @param m6_pred pd.DataFrame continuous_predictions_m6.csv (M6).
    @param lead_m4 pd.DataFrame lead_time_summary_m4.csv (consistency check).
    @param lead_m6 pd.DataFrame lead_time_summary_m6.csv (consistency check).
    @param df_precip pd.Series or None Precipitation (prec_mm), 5-min grid —
           pass real_utils.load_real_data()'s ts_precip.to_dataframe()["prec_mm"]
           to also print rainfall around each alarm firing.
    @param context_min int Minutes of context to show before/after each
           alarm-firing timestamp.
    """
    evt = df_events[df_events["event_num"] == event_num].iloc[0]
    win_start, win_end = evt["analysis_start"], evt["analysis_end"]
    print(
        f"\n{'='*100}\nEVENTO {event_num} — janela {win_start} -> {win_end}\n{'='*100}"
    )

    occ = audit.event_occurrences(m4_pred, m6_pred, win_start, win_end)
    audit.check_against_csv(event_num, occ, {"M4": lead_m4, "M6": lead_m6})
    delta = pd.Timedelta(minutes=context_min)

    for name in audit.THRESHOLD_ORDER:
        for i, row in enumerate(occ["M4"][name]):
            print(
                f"\n--- Limiar {name} ({audit.THRESHOLDS[name]}cm), ocorrência "
                f"{row['occurrence']}/{row['n_occurrences']} — observado cruzou às "
                f"{row['t_obs']}; busca {row['search_start']} -> {row['search_end']} ---"
            )
            for h in audit.HORIZONS:
                r4, r6 = row, occ["M6"][name][i]
                print(
                    f"  +{h}min:  M4 alarme às {r4[f'fire_{h}min']} "
                    f"(lead={audit.format_lead(r4, h)})   M6 às {r6[f'fire_{h}min']} "
                    f"(lead={audit.format_lead(r6, h)})"
                )
                for label, r, df_pred in (("M4", r4, m4_pred), ("M6", r6, m6_pred)):
                    t_fire = r[f"fire_{h}min"]
                    if t_fire is None:
                        continue
                    cols = ["h_obs", f"h_pred_{h}", f"h_actual_{h}"]
                    ctx = df_pred.loc[t_fire - delta : t_fire + delta, cols].copy()
                    if df_precip is not None:
                        ctx["prec_mm"] = df_precip.reindex(ctx.index)
                    print(f"    contexto ao redor do alarme {label} (+{h}min):")
                    print("      " + ctx.to_string().replace("\n", "\n      "))


DRY_BAND_CM = (32, 35)
"""Observed-level band treated as "channel dry" in the calibration scan.

Just above LEVEL_MIN_CM and well below the 50 cm Atencao threshold, so a
forecast issued here has no legitimate reason to approach any alert level.
"""


def scan_forecast_calibration(m4_pred, m6_pred, train_end=None):
    """Bias and threshold-exceedance frequency per model and horizon (Issue #223).

    The per-event RMSE tables say how far off a forecast is inside a flood, but
    they cannot reveal a model that is *permanently* in alarm: they never look
    at the dry weather that makes up 98% of the record. This scan does, and it
    is what exposed the training-set selection bias — at +120 min the
    event-only-trained M4 forecast 50 cm or more in 75.2% of all steps while
    the observed level did so in 1.8%, and averaged 85.6 cm with the channel
    dry.

    Three columns carry the signal:

    - ``bias`` — mean(predicted - actual). Should sit near zero. A large
      positive value at long horizons is the fingerprint of a model that has
      regressed to a flood-shaped training prior.
    - ``pred_ge_thr`` vs ``obs_ge_thr`` — how often the forecast claims the
      Atencao threshold (config.THRESHOLD_ATENCAO, not a hardcoded value —
      these levels were recalibrated in Issue #225) against how often reality
      does. These should be
      comparable; a forecast exceeding it an order of magnitude more often is
      raising false alarms regardless of what its RMSE says.
    - ``dry_pred`` — mean forecast issued while the channel sits in
      DRY_BAND_CM. Should stay inside that band.

    Results are reported separately for the in-sample and out-of-sample halves
    when *train_end* is given, since only the out-of-sample half is evidence.

    @param m4_pred    M4 continuous predictions DataFrame (timestamp index or column).
    @param m6_pred    M6 continuous predictions DataFrame, same shape.
    @param train_end  Chronological train/test cut, or None to report the whole
                      series as a single block.
    @return DataFrame with one row per model x horizon x period.
    """
    thr = audit.real_utils.config.THRESHOLD_ATENCAO
    rows = []
    for name, df in (("M4", m4_pred), ("M6", m6_pred)):
        df = df.copy()
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        df.index = pd.to_datetime(df.index)

        if train_end is None:
            periods = [("full", df)]
        else:
            cut = pd.Timestamp(train_end)
            periods = [
                ("in-sample", df[df.index < cut]),
                ("out-of-sample", df[df.index >= cut]),
            ]

        for period, sub in periods:
            for h in (30, 60, 90, 120):
                pred_col, act_col = f"h_pred_{h}", f"h_actual_{h}"
                if pred_col not in sub.columns or act_col not in sub.columns:
                    continue
                d = sub[[pred_col, act_col, "h_obs"]].dropna()
                if d.empty:
                    continue
                err = d[pred_col] - d[act_col]
                dry = d[d["h_obs"].between(*DRY_BAND_CM)]
                rows.append(
                    {
                        "model": name,
                        "period": period,
                        "horizon": f"+{h}min",
                        "n": len(d),
                        "bias": round(err.mean(), 2),
                        "rmse": round((err**2).mean() ** 0.5, 2),
                        "pred_ge_thr": round((d[pred_col] >= thr).mean(), 4),
                        "obs_ge_thr": round((d[act_col] >= thr).mean(), 4),
                        "dry_pred": (
                            round(dry[pred_col].mean(), 1) if len(dry) else float("nan")
                        ),
                    }
                )
    return pd.DataFrame(rows)


def main():
    """
    @brief Load all data sources once and print every scan's results, or —
           with --event N on the command line — print only the detailed
           crossing explanation for event N (skips the slow SQL dump parse,
           which that mode does not need).
    """
    event_arg = None
    if "--event" in sys.argv:
        idx = sys.argv.index("--event")
        if idx + 1 < len(sys.argv):
            event_arg = int(sys.argv[idx + 1])
    calibration_only = "--calibration" in sys.argv

    print("Carregando dado filtrado + catálogo de eventos...")
    ts_level, ts_precip, df_events = audit.real_utils.load_real_data()
    df_filtered = ts_level.to_dataframe()["level_delta_cm"]
    df_precip = ts_precip.to_dataframe()["prec_mm"]

    print("Carregando previsões contínuas M4/M6...")
    m4_pred, m6_pred = audit.load_predictions()
    lead_m4, lead_m6, rmse = audit.load_metrics()

    if event_arg is not None:
        explain_event_crossings(
            event_arg, df_events, m4_pred, m6_pred, lead_m4, lead_m6, df_precip
        )
        return

    train_end = (
        audit.real_utils.config.TRAIN_END
        if audit.real_utils.config.TRAIN_MODE == "continuous"
        else None
    )
    print("\n=== 0) Calibração da previsão (viés e frequência de excedência) ===")
    print(scan_forecast_calibration(m4_pred, m6_pred, train_end).to_string(index=False))

    if calibration_only:
        return

    print("Fazendo parsing do dump SQL (etapa mais lenta)...")
    df_raw = audit.load_raw_level(audit.DEFAULT_DUMP)

    print("\n=== 1) Divergência pico catalogado vs. máximo da série FILTRADA ===")
    df_flags = scan_peak_divergence(df_events, df_filtered, df_raw)
    print(
        df_flags[df_flags["diff"].abs() > audit.PEAK_TOLERANCE_CM].to_string(
            index=False
        )
    )
    print("\n--- tabela completa ---")
    print(df_flags.to_string(index=False))

    print(
        "\n=== 2) Eventos 'Normal' presentes indevidamente nas tabelas de lead time ==="
    )
    normal_events, flagged_m4, flagged_m6 = scan_normal_events_in_lead_time(
        df_events, lead_m4, lead_m6
    )
    print("Eventos 'Normal' no catálogo:", sorted(normal_events))
    print("Presentes em lead_time_summary_m4:", sorted(flagged_m4))
    print("Presentes em lead_time_summary_m6:", sorted(flagged_m6))

    print("\n=== 3) Lead times extremos (|valor| > 180 min) ===")
    for name, df in [("M4", lead_m4), ("M6", lead_m6)]:
        extreme = scan_extreme_lead_times(df)
        print(f"--- {name}: {len(extreme)} linhas ---")
        print(extreme.to_string(index=False))

    print("\n=== 4) Lead times negativos (aviso atrasado) ===")
    for name, df in [("M4", lead_m4), ("M6", lead_m6)]:
        neg = scan_negative_lead_times(df)
        print(f"--- {name}: {len(neg)} linhas ---")
        print(neg.to_string(index=False))

    print("\n=== 5) Outliers de RMSE por horizonte (> 2.5x a mediana do modelo) ===")
    for h, flagged in scan_rmse_outliers(rmse).items():
        print(f"--- horizonte +{h}min ---")
        print(flagged.to_string(index=False))


if __name__ == "__main__":
    main()
