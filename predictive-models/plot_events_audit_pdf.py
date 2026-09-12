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
@file plot_events_audit_pdf.py
@brief Print-ready A3 PDF audit report for every catalogued flood event.

Standalone visual-audit tool (not part of the M4 or M6 numbered pipelines) built
to let the author cross-check, event by event, whether the lead-time and RMSE
figures reported in the dissertation for M4 (LightGBM) and M6 (MLR) match what
the underlying observed and predicted curves actually show.

Report structure:
  Page 0        — cover (purpose, how to read, scripts that produced the data).
  Page 1        — full-size table of the event catalogue (config.EVENTS_CSV,
                  all events), including the 6/12/24 h accumulated
                  precipitation before each peak.
  Per event (x2 pages):
    Header      — event metadata plus the 6/12/24 h accumulated precipitation
                  before the catalogued peak, from the same spliced series the
                  models are fed (MERGE before config.PRECIP_CUTOFF, Station-02
                  after), with a coverage warning when the source has gaps.
    Page A      — raw level_cm (from an offline SQL dump) stacked above
                  filtered level_delta_cm (the series that feeds the models),
                  both with Atenção/Alerta/Inundação threshold lines, the
                  catalogued peak, and threshold-crossing times.
    Page B      — a small M4-vs-M6 metrics table (RMSE and lead time per
                  horizon/threshold) followed by 4 stacked panels, one per
                  prediction horizon (+30/+60/+90/+120 min), each overlaying
                  observed vs. M4-predicted vs. M6-predicted at the prediction's
                  own issuance time (unshifted — the same timestamps the
                  official lead-time scripts search over), with markers on the
                  observed and predicted threshold crossings so the published
                  lead-time number is directly traceable on the chart.

Data sources (no live DB / API access from this host):
  - Raw level_cm      : offline SQL dump (DUMP_PATH), Station-01, physical-range
                        clip only — deliberately NOT delta-filtered, so sensor
                        outliers remain visible for inspection.
  - Filtered level    : results_final_m4_lgbm/real_utils.load_real_data() — the
                        exact pre-processing pipeline (clip + delta-filter +
                        5-min resample) used to train/evaluate M4 and M6.
  - M4/M6 predictions : results_final_m4_lgbm/output/continuous_predictions.csv
                        and results_final_m6_mlr/output/continuous_predictions_m6.csv.
  - Metrics           : lead_time_summary_m4.csv, lead_time_summary_m6.csv,
                        rmse_per_event.csv (results_final_m4_lgbm / results_final_m6_mlr).
  - Precipitation     : real_utils.load_real_data() spliced 5-min series, plus
                        the raw config.STATION02_CSV / config.MERGE_CSV
                        timestamps used only to detect coverage gaps.

Usage (requires the Darts venv — the system python3 has no Darts):
    cd AppTest/raspberry/predictive_model_darts/
    /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \\
        plot_events_audit_pdf.py [--dump /path/to/dump.sql]

Output:
    output_audit/auditoria_eventos_A3.pdf
    output_audit/precip_acumulada_eventos.csv

@author Alexandre Nuernberg
@date 2026-09-08
"""

import os
import re
import subprocess
import sys
import textwrap

_HERE = os.path.dirname(os.path.abspath(__file__))
_M4_DIR = os.path.join(_HERE, "results_final_m4_lgbm")
_M6_DIR = os.path.join(_HERE, "results_final_m6_mlr")
sys.path.insert(0, _M4_DIR)

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42  # embed real (non-Type3) fonts for print
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D

import config  # M4 config.py — thresholds, LEVEL_MIN_CM/MAX_CM (results_final_m4_lgbm/)
import lead_time_utils  # results_final_m4_lgbm/lead_time_utils.py — Issue #229
import real_utils  # results_final_m4_lgbm/real_utils.py — load_real_data()
from build_event_catalogue import FLASH_FLOOD_CM_PER_H

FLASH_FLOOD_30MIN_CM = FLASH_FLOOD_CM_PER_H / 2
"""Flash-flood criterion expressed as it is printed in the catalogue notes:
the steepest 30-min rise in cm (the catalogue stores it doubled, in cm/h)."""

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DEFAULT_DUMP = "/home/ilha3d/SAPI/DB/<HOSTINGER_USER>_sapi_20260909.sql"
"""Most recent offline SQL dump available on this host (data through
2026-09-09), covering every event in the v3 catalogue (the last analysis
window ends 2026-09-01)."""

OUTPUT_DIR = os.path.join(_HERE, "output_audit")
OUTPUT_PDF = os.path.join(OUTPUT_DIR, "auditoria_eventos_A3.pdf")
OUTPUT_PRECIP_CSV = os.path.join(OUTPUT_DIR, "precip_acumulada_eventos.csv")

M4_LEAD_CSV = os.path.join(_M4_DIR, "output", "lead_time_summary_m4.csv")
M6_LEAD_CSV = os.path.join(_M6_DIR, "output", "lead_time_summary_m6.csv")
RMSE_CSV = os.path.join(_M6_DIR, "output", "rmse_per_event.csv")
M4_PRED_CSV = os.path.join(_M4_DIR, "output", "continuous_predictions.csv")
M6_PRED_CSV = os.path.join(_M6_DIR, "output", "continuous_predictions_m6.csv")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATION_LEVEL_1 = 1

A3_PORTRAIT_IN = (11.69, 16.54)
"""A3 page size in inches, portrait (297 x 420 mm)."""

THRESHOLDS = {
    "Atenção": config.THRESHOLD_ATENCAO,
    "Alerta": config.THRESHOLD_ALERTA,
    "Inundação": config.THRESHOLD_INUNDACAO,
}
THRESHOLD_COLORS = {
    "Atenção": "goldenrod",
    "Alerta": "darkorange",
    "Inundação": "purple",
}
THRESHOLD_ORDER = ["Atenção", "Alerta", "Inundação"]

# Lead-time rule parameters come from config (REARM_HYSTERESIS_CM,
# PRED_PERSISTENCE_STEPS, CAUSALITY_MAX_LEAD_MIN) and the rule itself from
# lead_time_utils.py — the same call the 04_lead_time_* scripts make, so the
# markers and numbers drawn here are the published ones (Issue #229).

COLOR_OBS = "black"
COLOR_M4 = "steelblue"
COLOR_M6 = "firebrick"
COLOR_PEAK = "dimgray"

TYPE_LABELS = {"flood": "Cheia", "flash_flood": "Enxurrada", "Normal": "Normal"}
SPLIT_LABELS = {"train": "Treino", "test": "Teste", "excluded": "Excluído"}
SPLIT_COLORS = {"train": "#1b7a3d", "test": "#555555", "excluded": "firebrick"}
"""Treino = verde escuro, Teste = cinza neutro, Excluído = vermelho (artefato
de sensor removido do treino e das métricas, Issue #227) — usado no catálogo
(Página 1) e no cabeçalho de cada evento para identificação visual rápida do
conjunto."""

EXCLUDED_NOTE = (
    "EXCLUÍDO — ARTEFATO DE SENSOR: este trecho foi removido da série que alimenta "
    "M4/M6, das métricas e da simulação de alertas (Issue #227). O painel filtrado "
    "mostra o que foi removido."
)
"""Aviso de cabeçalho dos eventos com exclusion == "artifact"."""

HORIZONS = [30, 60, 90, 120]

PEAK_TOLERANCE_CM = 2.0
"""Max allowed gap between the catalogued peak_cm and the filtered series' own
max within the event window before flagging a header warning. Deliberately
compared against the FILTERED series only — the raw series legitimately
contains sensor outliers that the delta filter is designed to reject, so a
raw/catalogue mismatch is expected and NOT evidence of a catalogue error."""

LOCAL_TZ_OFFSET_H = -3
"""America/Sao_Paulo has observed no DST since 2019 — a fixed UTC-3 offset is
accurate for the whole dataset period."""

PRECIP_WINDOWS_H = [6, 12, 24]
"""Accumulation windows (hours before the catalogued peak) printed per event."""

PRECIP_MAX_GAP_MIN = 30
"""Largest tolerated gap between consecutive Station-02 readings inside an
accumulation window before that window is flagged. Station-02 reports every
~15 min, so two consecutive missed reports are already suspicious. A flag is
needed because real_utils.load_real_data() turns a Station-02 gap into 0.0 mm
(empty 5-min bins sum to 0) — without it, "no data" and "no rain" print the
same 0.0 mm. A missing MERGE hour behaves differently: resample().ffill()
repeats the last available hour's value across the gap."""


# ---------------------------------------------------------------------------
# SQL dump parsing — raw level_cm, Station-01 only
#
# This dump is one row per line inside each multi-line "INSERT INTO
# `measurements` (...) VALUES" block (confirmed by inspection), which allows a
# fast single-pass line-by-line parse instead of a whole-file regex scan.
# ---------------------------------------------------------------------------


def _parse_sql_value(token):
    """
    @brief Convert a single SQL token string to a Python scalar.
    @param token str Raw token from a SQL VALUES row.
    @return int | float | str | None
    """
    token = token.strip()
    if token.upper() == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        inner = token[1:-1]
        inner = inner.replace("\\'", "'").replace("\\\\", "\\")
        return inner
    try:
        return float(token) if "." in token else int(token)
    except ValueError:
        return token


def _split_row_tokens(row_str):
    """
    @brief Split one "(...)"-wrapped SQL row into value tokens, respecting
           quoted strings that may themselves contain commas.
    @param row_str str Row content, e.g. "(2, 1, 'x, y', NULL),"
    @return list of str tokens
    """
    inner = row_str.strip().lstrip("(")
    for suffix in (");", "),", ")"):
        if inner.endswith(suffix):
            inner = inner[: -len(suffix)]
            break
    tokens = []
    current = ""
    in_string = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and in_string:
            current += ch + (inner[i + 1] if i + 1 < len(inner) else "")
            i += 2
            continue
        if ch == "'":
            in_string = not in_string
            current += ch
        elif ch == "," and not in_string:
            tokens.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1
    if current.strip():
        tokens.append(current.strip())
    return tokens


_INSERT_HEADER_RE = re.compile(r"INSERT INTO `measurements` \(([^)]+)\) VALUES")


def load_raw_level(dump_path, station_id=STATION_LEVEL_1):
    """
    @brief Stream-parse the SQL dump and return raw level_cm for one station.

    Only the physical-range clip is applied (config.LEVEL_MIN_CM/MAX_CM) — no
    delta filter — so sensor spikes remain visible for the raw panel.

    @param dump_path str Path to the .sql dump file.
    @param station_id int Station id in the measurements table.
    @return pd.Series indexed by tz-naive UTC timestamp, values in cm.
    """
    col_idx = None
    rows = []
    in_block = False

    with open(dump_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("INSERT INTO `measurements`"):
                m = _INSERT_HEADER_RE.match(line)
                col_names = [c.strip().strip("`") for c in m.group(1).split(",")]
                col_idx = {name: i for i, name in enumerate(col_names)}
                in_block = True
                continue
            if not in_block:
                continue
            stripped = line.strip()
            if not stripped:
                continue
            is_last = stripped.endswith(";")
            tokens = _split_row_tokens(stripped)
            values = [_parse_sql_value(t) for t in tokens]
            if len(values) == len(col_idx):
                if (
                    values[col_idx["id_station"]] == station_id
                    and values[col_idx["deleted_at"]] is None
                ):
                    lvl = values[col_idx["level_cm"]]
                    if lvl is not None:
                        rows.append((values[col_idx["timestamp"]], float(lvl)))
            if is_last:
                in_block = False

    df = pd.DataFrame(rows, columns=["timestamp", "level_cm"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    s = df["level_cm"]
    s = s.where((s >= config.LEVEL_MIN_CM) & (s <= config.LEVEL_MAX_CM))
    return s.dropna()


# ---------------------------------------------------------------------------
# Threshold-crossing helper (same convention as predictive_model_v2/03_plot_events.py)
# ---------------------------------------------------------------------------


def first_crossing(series, threshold):
    """
    @brief Return the timestamp of the first reading >= threshold, or NaT.
    @param series pd.Series Level time series (DatetimeIndex).
    @param threshold float Threshold in cm.
    @return pd.Timestamp or pd.NaT
    """
    above = series[series >= threshold]
    return above.index.min() if not above.empty else pd.NaT


# ---------------------------------------------------------------------------
# Accumulated precipitation before the peak (6/12/24 h)
#
# Summed from the SAME spliced 5-min series real_utils.load_real_data() feeds
# to M4/M6 (MERGE before config.PRECIP_CUTOFF, Station-02 from it, with
# config.PRECIP_MERGE_SCALE applied), so the printed totals are what the models
# actually saw. The raw source files are read here only for their timestamps,
# to detect gaps the pipeline's fillna(0.0) would otherwise hide.
# ---------------------------------------------------------------------------


def _read_naive_utc_index(csv_path):
    """
    @brief Read only the "timestamp" column of a source CSV as a sorted,
           tz-naive UTC DatetimeIndex (same convention as real_utils).
    @param csv_path str Path to the CSV (must have a "timestamp" column).
    @return pd.DatetimeIndex
    """
    ts = pd.read_csv(csv_path, usecols=["timestamp"])["timestamp"]
    ts = pd.to_datetime(ts, utc=True).dt.tz_localize(None)
    return pd.DatetimeIndex(ts).sort_values()


def load_precip_source_indexes():
    """
    @brief Load the raw Station-02 and MERGE reading timestamps used for the
           coverage check.
    @return tuple(pd.DatetimeIndex st02_idx, pd.DatetimeIndex merge_idx)
    """
    return (
        _read_naive_utc_index(config.STATION02_CSV),
        _read_naive_utc_index(config.MERGE_CSV),
    )


def _largest_gap(idx, win_start, win_end):
    """
    @brief Longest stretch without a reading inside (win_start, win_end],
           counting the window edges as boundaries.
    @param idx pd.DatetimeIndex Sorted reading timestamps.
    @param win_start pd.Timestamp Window start (exclusive).
    @param win_end pd.Timestamp Window end (inclusive).
    @return pd.Timedelta
    """
    inside = idx[(idx > win_start) & (idx <= win_end)]
    points = (
        pd.DatetimeIndex([win_start]).append(inside).append(pd.DatetimeIndex([win_end]))
    )
    return points.to_series().diff().max()


def _format_duration(td):
    """
    @brief Format a Timedelta as "6h49" (or "35min" under one hour).
    @param td pd.Timedelta
    @return str
    """
    total_min = int(td.total_seconds() // 60)
    hours, minutes = divmod(total_min, 60)
    return f"{hours}h{minutes:02d}" if hours else f"{minutes}min"


def _window_coverage(st02_idx, merge_idx, win_start, peak_time):
    """
    @brief Check source coverage of one accumulation window (win_start, peak].

    The part of the window from config.PRECIP_CUTOFF on is Station-02 (largest
    gap between readings vs. PRECIP_MAX_GAP_MIN); the part before it is MERGE
    (hourly rows missing from the archive).

    @param st02_idx pd.DatetimeIndex Station-02 reading timestamps.
    @param merge_idx pd.DatetimeIndex MERGE hourly timestamps.
    @param win_start pd.Timestamp Window start (exclusive).
    @param peak_time pd.Timestamp Catalogued peak (window end, inclusive).
    @return list of str, one problem description per affected source (empty
            when coverage is complete).
    """
    cutoff = config.PRECIP_CUTOFF.tz_localize(None)
    problems = []

    if peak_time >= cutoff:
        gap = _largest_gap(st02_idx, max(win_start, cutoff), peak_time)
        if gap > pd.Timedelta(minutes=PRECIP_MAX_GAP_MIN):
            problems.append(
                f"Estação-02 sem leituras por {_format_duration(gap)} (maior lacuna; "
                "o pipeline conta a falta como 0 mm, o acumulado pode estar subestimado)"
            )

    if win_start < cutoff:
        # Each 5-min slot in (win_start, last_slot] takes its value from the
        # MERGE row of its own hour (ffill / 12 in real_utils).
        last_slot = (
            peak_time if peak_time < cutoff else cutoff - pd.Timedelta(minutes=5)
        )
        expected = pd.date_range(
            (win_start + pd.Timedelta(minutes=5)).floor("h"),
            last_slot.floor("h"),
            freq="h",
        )
        n_missing = len(expected.difference(merge_idx))
        if n_missing:
            problems.append(
                f"MERGE sem {n_missing} h de dados (o pipeline repete o valor da última "
                "hora disponível, o acumulado é aproximado)"
            )

    return problems


def compute_precip_accumulations(precip, st02_idx, merge_idx, peak_time):
    """
    @brief Accumulated precipitation in the 6/12/24 h before an event's peak,
           with the source used and a per-window coverage flag.

    Each total is the sum of the 5-min slots with timestamp in
    (peak_time - H, peak_time] of the model's own spliced series.

    @param precip pd.Series Spliced 5-min precipitation (mm), tz-naive UTC
           index — ts_precip from real_utils.load_real_data().
    @param st02_idx pd.DatetimeIndex Raw Station-02 reading timestamps.
    @param merge_idx pd.DatetimeIndex Raw MERGE hourly timestamps.
    @param peak_time pd.Timestamp Catalogued peak time (tz-naive UTC).
    @return dict with keys:
            - 6, 12, 24     : float accumulated mm per window;
            - "flags"       : {H: bool} True when that window has a data gap;
            - "source"      : "MERGE", "Estação-02" or "MERGE+Estação-02"
                              (source of the widest window);
            - "warning"     : str or None, human-readable coverage warning for
                              the widest window that has a gap.
    """
    cutoff = config.PRECIP_CUTOFF.tz_localize(None)
    widest = max(PRECIP_WINDOWS_H)
    widest_start = peak_time - pd.Timedelta(hours=widest)

    if peak_time < cutoff:
        source = "MERGE"
    elif widest_start >= cutoff:
        source = "Estação-02"
    else:
        source = "MERGE+Estação-02"

    result = {"flags": {}, "source": source, "warning": None}
    for h in PRECIP_WINDOWS_H:
        win_start = peak_time - pd.Timedelta(hours=h)
        in_window = precip[(precip.index > win_start) & (precip.index <= peak_time)]
        result[h] = float(in_window.sum())
        result["flags"][h] = bool(
            _window_coverage(st02_idx, merge_idx, win_start, peak_time)
        )

    flagged = [h for h in PRECIP_WINDOWS_H if result["flags"][h]]
    if flagged:
        h_warn = max(flagged)
        problems = _window_coverage(
            st02_idx, merge_idx, peak_time - pd.Timedelta(hours=h_warn), peak_time
        )
        result["warning"] = f"⚠ Chuva nas {h_warn} h antes do pico: " + "; ".join(
            problems
        )
    return result


def format_precip_line(precip_info):
    """
    @brief One-line header text with the 6/12/24 h accumulations.
    @param precip_info dict Output of compute_precip_accumulations().
    @return str
    """
    parts = []
    for h in PRECIP_WINDOWS_H:
        mark = "*" if precip_info["flags"][h] else ""
        parts.append(f"{h} h = {precip_info[h]:.1f} mm{mark}")
    return (
        f"Chuva acumulada antes do pico ({precip_info['source']}):   "
        + "   |   ".join(parts)
    )


def save_precip_table(df_events, precip_by_event):
    """
    @brief Print the per-event accumulation table to the console and save it
           as OUTPUT_PRECIP_CSV.
    @param df_events pd.DataFrame Event catalogue (real_utils, parsed dates).
    @param precip_by_event dict {event_num: compute_precip_accumulations() dict}.
    """
    rows = []
    for _, evt in df_events.iterrows():
        info = precip_by_event[int(evt["event_num"])]
        row = {
            "event_num": int(evt["event_num"]),
            "peak_time_utc": evt["peak_time"],
            "peak_cm": evt["peak_cm"],
            "level": evt["level"],
            "split_set": evt["split_set"],
        }
        for h in PRECIP_WINDOWS_H:
            row[f"p{h}h_mm"] = round(info[h], 1)
        row["fonte"] = info["source"]
        for h in PRECIP_WINDOWS_H:
            row[f"p{h}h_lacuna"] = info["flags"][h]
        row["aviso"] = info["warning"] or ""
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_PRECIP_CSV, index=False, encoding="utf-8")

    print(f"  {'Evt':>3}  {'Pico (UTC)':16}  {'cm':>4}  {'Nível':10}", end="")
    print("".join(f"  {f'P{h}h':>7}" for h in PRECIP_WINDOWS_H) + "  Fonte")
    for r in rows:
        cells = "".join(
            f"  {r[f'p{h}h_mm']:6.1f}{'*' if r[f'p{h}h_lacuna'] else ' '}"
            for h in PRECIP_WINDOWS_H
        )
        print(
            f"  {r['event_num']:>3}  {r['peak_time_utc']:%Y-%m-%d %H:%M}  "
            f"{r['peak_cm']:>4.0f}  {r['level']:10}{cells}  {r['fonte']}"
        )
    print(f"  (* = lacuna na fonte)  Tabela salva em: {OUTPUT_PRECIP_CSV}")


# ---------------------------------------------------------------------------
# Metrics tables (RMSE / lead time)
# ---------------------------------------------------------------------------


def load_metrics():
    """
    @brief Load the M4/M6 lead-time and RMSE CSVs already produced by the
           backtest pipelines.
    @return tuple(pd.DataFrame lead_m4, pd.DataFrame lead_m6, pd.DataFrame rmse)
    """
    lead_m4 = pd.read_csv(M4_LEAD_CSV)
    lead_m6 = pd.read_csv(M6_LEAD_CSV)
    rmse = pd.read_csv(RMSE_CSV)
    return lead_m4, lead_m6, rmse


def format_lead(row, horizon_min):
    """
    @brief Text for one occurrence's lead time at one horizon.

    "—" when the alarm never fired inside the occurrence's search window;
    "≥+180" when the alarm was already on as the window opened, since the
    true lead is then at least the value counted from the window start.

    @param row dict One occurrence row from lead_time_utils.occurrence_lead_times().
    @param horizon_min int Horizon in minutes.
    @return str
    """
    v = row[f"lead_time_{horizon_min}min"]
    if pd.isna(v):
        return "—"
    return ("≥" if row[f"active_{horizon_min}min"] else "") + f"{v:+.0f}"


def build_metrics_grid(event_num, is_test, occ, rmse):
    """
    @brief Build the metrics grid for one event: RMSE per model, then one
           lead-time row per threshold-crossing occurrence and model, one
           column per horizon.

    Each lead-time row is labelled with its threshold, its crossing number
    (only when the threshold was crossed more than once) and the time the
    observed level crossed it, so a reader who never saw the code can tell
    which number belongs to which rise (Issue #229). A threshold the level
    never reached gets a single "não cruzado" row.

    @param event_num int Event number.
    @param is_test bool Only test events get a metrics table.
    @param occ dict Output of event_occurrences() for this event.
    @param rmse pd.DataFrame rmse_per_event.csv.
    @return tuple(list row_labels, list[list[str]] cell_text, list[bool]
            shaded) or None for events outside the test set. ``shaded``
            alternates per occurrence so each M4/M6 pair reads as a block.
    """
    if not is_test:
        return None
    rmse_evt = rmse[rmse["event_num"] == event_num]

    def _rmse_row(model):
        r = rmse_evt[rmse_evt["model"] == model]
        if r.empty:
            return ["—"] * len(HORIZONS)
        r = r.iloc[0]
        return [f"{r[f'rmse_{h}']:.1f}" for h in HORIZONS]

    row_labels = ["RMSE M4 (cm)", "RMSE M6 (cm)"]
    cell_text = [_rmse_row("M4"), _rmse_row("M6")]
    shaded = [False, False]
    shade = True
    for name in THRESHOLD_ORDER:
        rows_m4, rows_m6 = occ["M4"][name], occ["M6"][name]
        if not rows_m4:
            row_labels.append(
                f"Lead time {name} ({THRESHOLDS[name]} cm): nível não cruzou"
            )
            cell_text.append(["—"] * len(HORIZONS))
            shaded.append(shade)
            shade = not shade
            continue
        for r4, r6 in zip(rows_m4, rows_m6):
            num = f" #{r4['occurrence']}" if len(rows_m4) > 1 else ""
            base = f"Lead time {name}{num} ({r4['t_obs']:%d/%m %H:%M})"
            for model, r in (("M4", r4), ("M6", r6)):
                row_labels.append(f"{base} — {model} (min)")
                cell_text.append([format_lead(r, h) for h in HORIZONS])
                shaded.append(shade)
            shade = not shade
    return row_labels, cell_text, shaded


# ---------------------------------------------------------------------------
# Predictions (M4/M6) — plotted UNSHIFTED (at their own issuance time), which
# is what the official lead-time scripts (04_lead_time_m4.py / 04_lead_time_m6.py)
# search over. This is deliberately NOT the "shifted to verification time"
# convention used by results_final_m4_lgbm/06_event_comparison_plots.py: that
# convention is the right one for judging forecast ACCURACY (predicted vs.
# actual value at the same real-world time, i.e. the RMSE story), but it is
# the wrong one for making a lead-time NUMBER traceable on a chart — lead time
# is defined as (actual crossing time) minus (the timestamp at which a
# forecast, made using only data available up to that timestamp, already
# exceeded the threshold). Plotting h_pred_H unshifted, at its own issuance
# time, is what makes that definition directly visible: wherever the colored
# curve reaches a threshold line before the black observed curve does, that
# horizontal gap literally IS the lead time.
# ---------------------------------------------------------------------------


def load_predictions():
    """
    @brief Load the continuous backtest prediction CSVs for M4 and M6.
    @return tuple(pd.DataFrame m4, pd.DataFrame m6), both indexed by tz-naive
            UTC timestamp.
    """
    m4 = pd.read_csv(M4_PRED_CSV, parse_dates=["timestamp"]).set_index("timestamp")
    m6 = pd.read_csv(M6_PRED_CSV, parse_dates=["timestamp"]).set_index("timestamp")
    return m4, m6


def windowed_prediction(df_pred, horizon_min, win_start, win_end):
    """
    @brief Return the model's h_pred_{H} series at its own issuance timestamp
           (no shift), sliced to the event window.

    @param df_pred pd.DataFrame Prediction table (continuous_predictions*.csv).
    @param horizon_min int Horizon in minutes (30/60/90/120).
    @param win_start pd.Timestamp Window start (tz-naive UTC).
    @param win_end pd.Timestamp Window end (tz-naive UTC).
    @return pd.Series indexed by issuance time, values in cm (NaN dropped).
    """
    col = f"h_pred_{horizon_min}"
    return df_pred.loc[win_start:win_end, col].dropna()


def observed_from_predictions(df_pred, win_start, win_end):
    """
    @brief Return the model file's own ground-truth series (h_obs) for a window.
    @param df_pred pd.DataFrame Prediction table.
    @param win_start pd.Timestamp Window start.
    @param win_end pd.Timestamp Window end.
    @return pd.Series
    """
    return df_pred.loc[win_start:win_end, "h_obs"].dropna()


def check_against_csv(event_num, occ, lead_by_model):
    """
    @brief Warn if any lead time computed here differs from the published
           lead_time_summary_*.csv (both come from lead_time_utils with the
           same config, so a mismatch means the CSVs are stale).
    @param event_num int Event number.
    @param occ dict Output of event_occurrences() for this event.
    @param lead_by_model dict {"M4": DataFrame, "M6": DataFrame} of the CSVs.
    @return int Number of mismatching values (0 when consistent).
    """
    mismatches = 0
    for model, df in lead_by_model.items():
        for name in THRESHOLD_ORDER:
            for row in occ[model][name]:
                pub = df[
                    (df["event_num"] == event_num)
                    & (df["threshold_name"] == name)
                    & (df["occurrence"] == row["occurrence"])
                ]
                for h in HORIZONS:
                    mine = row[f"lead_time_{h}min"]
                    theirs = pub[f"lead_time_{h}min"].iloc[0] if len(pub) else np.nan
                    if not (pd.isna(mine) and pd.isna(theirs)) and mine != theirs:
                        mismatches += 1
    if mismatches:
        print(
            f"  ⚠ E{event_num:02d}: {mismatches} lead time(s) differ from "
            "lead_time_summary_*.csv — re-run the 04_lead_time_* scripts."
        )
    return mismatches


def event_occurrences(m4_pred, m6_pred, win_start, win_end):
    """
    @brief Lead time per threshold-crossing occurrence, both models, one event.

    Calls lead_time_utils.occurrence_lead_times() with config's parameters —
    exactly what 04_lead_time_m4.py / 04_lead_time_m6.py do — so every marker
    and number on the page is the published one (Issue #229).

    @param m4_pred pd.DataFrame M4 continuous predictions (timestamp index).
    @param m6_pred pd.DataFrame M6 continuous predictions (timestamp index).
    @param win_start pd.Timestamp Event window start.
    @param win_end pd.Timestamp Event window end.
    @return dict {"M4"|"M6": {threshold_name: list of occurrence rows}}.
    """
    return {
        model: {
            name: lead_time_utils.occurrence_lead_times(
                df,
                win_start,
                win_end,
                THRESHOLDS[name],
                HORIZONS,
                config.REARM_HYSTERESIS_CM,
                config.PRED_PERSISTENCE_STEPS,
                config.CAUSALITY_MAX_LEAD_MIN,
            )
            for name in THRESHOLD_ORDER
        }
        for model, df in (("M4", m4_pred), ("M6", m6_pred))
    }


# ---------------------------------------------------------------------------
# Shared plotting helpers
# ---------------------------------------------------------------------------


def draw_threshold_lines(ax, x_end):
    """
    @brief Draw the 3 horizontal Atenção/Alerta/Inundação threshold lines.
    @param ax matplotlib.Axes
    @param x_end datetime-like Right edge of the panel, used to anchor labels.
    """
    for name in THRESHOLD_ORDER:
        val = THRESHOLDS[name]
        color = THRESHOLD_COLORS[name]
        ax.axhline(
            val, color=color, linewidth=1.1, linestyle="--", alpha=0.85, zorder=3
        )
        ax.text(
            x_end,
            val,
            f" {name} ({val})",
            color=color,
            fontsize=7,
            va="bottom",
            ha="left",
            clip_on=False,
        )


def draw_time_guides(ax, peak_time, crossing_times):
    """
    @brief Draw the peak vertical guide and per-threshold crossing verticals,
           shared across all panels of both pages for visual alignment.

    @param ax matplotlib.Axes
    @param peak_time pd.Timestamp Catalogued peak time.
    @param crossing_times dict {threshold_name: pd.Timestamp or NaT}
    """
    if pd.notna(peak_time):
        ax.axvline(peak_time, color=COLOR_PEAK, linewidth=1.6, linestyle="-.", zorder=6)
    for name, t_cross in crossing_times.items():
        if pd.isna(t_cross):
            continue
        ax.axvline(
            t_cross,
            color=THRESHOLD_COLORS[name],
            linewidth=1.0,
            linestyle=":",
            alpha=0.9,
            zorder=5,
        )


def draw_crossing_markers(ax, horizon_min, occ):
    """
    @brief Mark, on top of the threshold lines, exactly the points the
           lead-time rule uses: each observed crossing occurrence (●) and the
           instant each model's persistent alarm fired for it (▲ M4 / ▼ M6).

    The horizontal gap between ● and ▲/▼ IS the lead time in the metrics table
    above. The values themselves go in one non-overlapping text box per panel
    (summarize_crossings()), not next to each marker, where they would overlap.

    @param ax matplotlib.Axes
    @param horizon_min int Horizon in minutes (30/60/90/120).
    @param occ dict Output of event_occurrences() for this event.
    """
    # Markers sit above the per-panel summary box (zorder 8), so the box can
    # never hide a crossing.
    for name in THRESHOLD_ORDER:
        threshold_cm = THRESHOLDS[name]
        rows = occ["M4"][name]
        for row in rows:
            ax.plot(
                row["t_obs"],
                threshold_cm,
                marker="o",
                color=COLOR_OBS,
                markersize=6,
                zorder=11,
            )
            if len(rows) > 1:
                ax.annotate(
                    f"#{row['occurrence']}",
                    xy=(row["t_obs"], threshold_cm),
                    xytext=(-5, 5),
                    textcoords="offset points",
                    ha="right",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                    color=THRESHOLD_COLORS[name],
                    bbox=dict(
                        boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8
                    ),
                    zorder=12,
                )
        for model, color, marker in (("M4", COLOR_M4, "^"), ("M6", COLOR_M6, "v")):
            for row in occ[model][name]:
                t_fire = row[f"fire_{horizon_min}min"]
                if t_fire is None:
                    continue
                ax.plot(
                    t_fire,
                    threshold_cm,
                    marker=marker,
                    color=color,
                    markersize=7,
                    markeredgecolor="white",
                    markeredgewidth=0.5,
                    zorder=11,
                )


def summarize_crossings(horizon_min, occ):
    """
    @brief Build the fixed, non-overlapping text-box lines summarizing every
           marker drawn by draw_crossing_markers() for one panel — one line
           per threshold-crossing occurrence.

    @param horizon_min int Horizon in minutes (30/60/90/120).
    @param occ dict Output of event_occurrences() for this event.
    @return list of str (empty if the observed level never reached any
            threshold).
    """
    lines = []
    for name in THRESHOLD_ORDER:
        rows_m4 = occ["M4"][name]
        for i, row in enumerate(rows_m4):
            label = name if len(rows_m4) == 1 else f"{name} #{row['occurrence']}"
            parts = [f"● {row['t_obs']:%d/%m %H:%M}"]
            for model in ("M4", "M6"):
                r = occ[model][name][i]
                t_fire = r[f"fire_{horizon_min}min"]
                if t_fire is None:
                    parts.append(f"{model} não atingido")
                else:
                    parts.append(
                        f"{model} {t_fire:%H:%M} ({format_lead(r, horizon_min)}min)"
                    )
            lines.append(f"{label}: " + "  ".join(parts))
    return lines


def format_time_axis(ax, x_start, x_end, is_bottom):
    """
    @brief Apply the shared 15-min-grid time axis formatting, with a major-tick
           interval that adapts to the window length so labels never overlap.

    @param ax matplotlib.Axes
    @param x_start datetime-like
    @param x_end datetime-like
    @param is_bottom bool Whether this is the bottom-most panel (gets tick labels).
    """
    ax.set_xlim(x_start, x_end)
    total_hours = (x_end - x_start).total_seconds() / 3600
    if total_hours <= 6:
        major_interval, fmt = 1, "%H:%M"
    elif total_hours <= 14:
        major_interval, fmt = 2, "%H:%M"
    elif total_hours <= 30:
        major_interval, fmt = 4, "%d/%m\n%H:%M"
    else:
        major_interval, fmt = 6, "%d/%m\n%H:%M"
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=major_interval))
    ax.xaxis.set_minor_locator(mdates.MinuteLocator(byminute=[0, 15, 30, 45]))
    ax.grid(which="minor", axis="x", linestyle=":", linewidth=0.4, alpha=0.35)
    ax.grid(which="major", axis="x", linestyle="-", linewidth=0.5, alpha=0.25)
    ax.grid(axis="y", linestyle=":", linewidth=0.4, alpha=0.3)
    if is_bottom:
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        ax.set_xlabel("Data/Hora (UTC)")
    else:
        ax.tick_params(labelbottom=False)


def compute_shared_ylim(filtered_series):
    """
    @brief Y-axis range shared by the raw and filtered panels on Page A.

    Deliberately derived from the FILTERED series only (padded around the
    threshold band), not the raw one: a raw-sensor outlier is expected to be
    rejected by the delta filter and must not be allowed to compress the
    readable vertical scale — "dado é dado, outlier é outlier". An outlier in
    the raw panel simply runs off the top/bottom of the fixed scale.

    @param filtered_series pd.Series Filtered level for the event window.
    @return tuple(float lo, float hi)
    """
    if filtered_series.empty:
        lo = THRESHOLDS["Atenção"] - 20
        hi = THRESHOLDS["Inundação"] + 20
    else:
        lo = min(filtered_series.min(), THRESHOLDS["Atenção"]) - 8
        hi = max(filtered_series.max(), THRESHOLDS["Inundação"]) + 8
    return lo, hi


# ---------------------------------------------------------------------------
# Page 0 — cover
# ---------------------------------------------------------------------------

REPORT_SCRIPTS = [
    (
        "reprocess_level_spike_return_filter.py",
        "Reprocessa o nível bruto (Issue #211): filtro elástico de produção + filtro de 40cm + spike-and-return.",
    ),
    (
        "build_gapfilled_level.py",
        "Preenche as falhas da Estação-01 com a Estação-03, com offset por faixa de nível e proveniência (Issue #225).",
    ),
    (
        "build_event_catalogue.py",
        "Reconstrói o catálogo de eventos a partir da série corrigida (Issue #225).",
    ),
    (
        "results_final_m4_lgbm/01_model4_continuous.py",
        "Treina o M4 (LightGBM) e roda a inferência contínua.",
    ),
    (
        "results_final_m6_mlr/01_model6_mlr_continuous.py",
        "Treina o M6 (Regressão Linear) e roda a inferência contínua.",
    ),
    (
        "results_final_m4_lgbm/lead_time_utils.py",
        "Regra do tempo de antecipação por cruzamento, usada pelos scripts abaixo e por este relatório (Issue #229).",
    ),
    (
        "04_lead_time_m4.py / 04_lead_time_m6.py",
        "Calculam o tempo de antecipação de cada cruzamento, por modelo e horizonte.",
    ),
    (
        "results_final_m6_mlr/05_rmse_per_event.py",
        "Calcula o RMSE por evento nos eventos de teste.",
    ),
    ("plot_events_audit_pdf.py", "Gera este relatório."),
    (
        "scan_audit_findings.py",
        "Varredura automática de achados (divergências, outliers, lead times extremos).",
    ),
]
"""Scripts cujo código gerou os dados deste relatório — listados na capa."""


def _current_git_branch():
    """
    @brief Name of the git branch this report is generated from, for the
           cover-page provenance footer.
    @return str Branch name, or "desconhecida" if git is unavailable.
    """
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=_HERE,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconhecida"


def _cover_paragraphs(fig, x, y, paragraphs, fontsize=10, width=112, step=0.0145):
    """
    @brief Draw wrapped paragraphs top-down on the cover and return the next y.
    @param fig matplotlib.Figure
    @param x float Left position (figure fraction).
    @param y float Top position (figure fraction) of the first line.
    @param paragraphs list of str One entry per paragraph.
    @param fontsize float Font size.
    @param width int Wrap width in characters.
    @param step float Vertical step per line (figure fraction).
    @return float y just below the last paragraph.
    """
    for para in paragraphs:
        for line in textwrap.wrap(para, width=width):
            fig.text(x, y, line, fontsize=fontsize)
            y -= step
        y -= 0.004
    return y


def _cover_heading(fig, x, y, text):
    """
    @brief Draw one cover section heading and return the y for its body.
    @param fig matplotlib.Figure
    @param x float Left position.
    @param y float Heading position.
    @param text str Heading text.
    @return float
    """
    fig.text(x, y, text, fontsize=12.5, fontweight="bold")
    return y - 0.019


def render_cover_page(pdf, n_events, n_train, n_test, n_excluded, dump_path):
    """
    @brief Render the cover page: what this report is, how to read it (in
           plain language, for a reader who does not know the code), the
           configuration that produced the numbers, and the scripts used.

    This is a deliberate SECOND front-matter page (after this, the catalogue
    is page 2) so that every event's two pages (A and B) land together on the
    same spread in a PDF viewer's "2 pages per view" mode.

    @param pdf PdfPages Open PDF being written.
    @param n_events int Total catalogued events.
    @param n_train int Number of training events.
    @param n_test int Number of test events.
    @param n_excluded int Number of events excluded as sensor artifacts.
    @param dump_path str Path to the raw SQL dump used, for provenance.
    """
    fig = plt.figure(figsize=A3_PORTRAIT_IN)
    fig.text(
        0.5,
        0.955,
        "SAPI — Relatório de Auditoria Visual",
        ha="center",
        fontsize=22,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.932,
        "Eventos de Treino e Teste — Lead Time e RMSE (M4 LightGBM vs. M6 MLR)",
        ha="center",
        fontsize=14,
        color="dimgray",
    )

    x = 0.07
    y = 0.895

    y = _cover_heading(fig, x, y, "O que é este relatório")
    y = _cover_paragraphs(
        fig,
        x,
        y,
        [
            f"Auditoria visual e numérica dos {n_events} eventos de cheia catalogados em "
            f"{os.path.basename(config.EVENTS_CSV)} ({n_train} de treino, {n_test} de teste, "
            f"{n_excluded} excluídos como artefato de sensor). Para cada evento, mostra o nível "
            "bruto medido, o nível filtrado que alimenta os modelos, a chuva antes do pico e as "
            "previsões dos modelos M4 (LightGBM) e M6 (regressão linear), para verificar se o "
            "dado está limpo, se o evento é explicado por chuva e se os modelos antecipam a cheia."
        ],
    )

    y -= 0.012
    y = _cover_heading(fig, x, y, "Como ler as páginas de cada evento")
    y = _cover_paragraphs(
        fig,
        x,
        y,
        [
            "Página A — nível bruto (em cima) e nível filtrado (embaixo), com os três limiares "
            "de alerta e o pico do evento marcados.",
            "Página B — tabela de erro (RMSE) e de tempo de antecipação, seguida de 4 gráficos, "
            "um por horizonte de previsão (+30, +60, +90 e +120 min), comparando o nível real "
            "com a previsão de cada modelo.",
            "Chuva — o cabeçalho traz a chuva acumulada nas 6, 12 e 24 h antes do pico. Um * e "
            "um aviso em vermelho indicam falha de dado na fonte de chuva.",
            "Excluídos — episódios que não são cheia, e sim leituras falsas do sensor (sem chuva). "
            "Aparecem no relatório para conferência, mas ficaram fora do treino e das métricas.",
            "Subida máx. 30 min — a maior subida do nível em qualquer intervalo de 30 min do "
            "evento, e não a média da subida inteira (E08: 78 cm em 30 min, numa subida total de "
            f"129 cm em 1h15). É Enxurrada quando chega a {FLASH_FLOOD_30MIN_CM:.0f} cm.",
            "O selo no canto de cada página indica o conjunto do evento:",
        ],
    )
    badge_y = y + 0.006
    for dx, label, key in (
        (0.02, "TREINO", "train"),
        (0.13, "TESTE", "test"),
        (0.235, "EXCLUÍDO", "excluded"),
    ):
        fig.text(
            x + dx,
            badge_y,
            label,
            fontsize=10.5,
            fontweight="bold",
            color="white",
            bbox=dict(
                boxstyle="round,pad=0.35",
                facecolor=SPLIT_COLORS[key],
                edgecolor="none",
            ),
        )
    y -= 0.03

    # Highlighted box: several crossings per event (the point most easily
    # misread by someone who has not followed the code).
    rearm = f"{config.REARM_HYSTERESIS_CM:.0f}"
    persist = config.PRED_PERSISTENCE_STEPS * config.RESAMPLE_MIN
    box_lines = textwrap.wrap(
        "ATENÇÃO: UM EVENTO PODE TER MAIS DE UM CRUZAMENTO DE LIMIAR. Cada evento do catálogo "
        "é uma cheia completa, que pode ter vários picos. Sempre que o nível cruza um limiar, "
        f"desce pelo menos {rearm} cm abaixo dele e volta a cruzá-lo, isso conta como um novo "
        "cruzamento, numerado #1, #2, #3... Cada cruzamento tem o seu próprio tempo de "
        "antecipação: na tabela da Página B há uma linha para cada um, com o horário em que "
        "o nível cruzou; nos gráficos, o número aparece ao lado do ●. Exemplo — Evento 31: o "
        "nível passou de 90 cm às 13:10, desceu a 81 cm e voltou a passar de 90 cm às 20:10, "
        "resultando em Inundação #1 e Inundação #2.",
        width=118,
    )
    fig.text(
        x,
        y,
        "\n".join(box_lines),
        fontsize=10,
        va="top",
        linespacing=1.45,
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#fff4d6", edgecolor="#d9a400"),
    )
    y -= len(box_lines) * 0.0118 + 0.035

    y = _cover_heading(fig, x, y, "Tempo de antecipação (lead time)")
    y = _cover_paragraphs(
        fig,
        x,
        y,
        [
            "É a diferença entre o horário em que o nível real cruzou o limiar (●) e o horário "
            "em que o alarme do modelo disparou (▲ M4, ▼ M6). O alarme dispara quando a "
            f"previsão fica acima do limiar por {persist} min seguidos, como no sistema em "
            "operação. Valor positivo = o modelo avisou antes do cruzamento; negativo = avisou "
            "depois; — = o modelo não alarmou para aquele cruzamento. O sinal ≥ indica que o "
            "alarme já estava ligado quando começou a busca, que vai até "
            f"{config.CAUSALITY_MAX_LEAD_MIN} min antes do cruzamento.",
        ],
    )

    y -= 0.012
    y = _cover_heading(fig, x, y, "Configuração que gerou estes números")
    thr = ", ".join(f"{n} {THRESHOLDS[n]} cm" for n in THRESHOLD_ORDER)
    train_end = pd.Timestamp(config.TRAIN_END)
    scale = config.PRECIP_MERGE_SCALE
    merge_txt = (
        "sem correção de escala (fator 1,0)"
        if scale == 1.0
        else f"multiplicado por {scale:.2f}".replace(".", ",")
    )
    config_lines = [
        ("Limiares", thr),
        ("Horizontes de previsão", ", ".join(f"+{h} min" for h in HORIZONS)),
        (
            "Treino / teste",
            f"treino no registro contínuo até {train_end:%d/%m/%Y} (sem os artefatos); "
            "teste depois dessa data",
        ),
        (
            "Cruzamentos e alarme",
            f"novo cruzamento após descer {rearm} cm; alarme após {persist} min acima do "
            f"limiar; busca até {config.CAUSALITY_MAX_LEAD_MIN} min antes",
        ),
        (
            "Chuva",
            f"MERGE (satélite) até {config.PRECIP_CUTOFF - pd.Timedelta(days=1):%d/%m/%Y}, "
            f"{merge_txt}; depois, Estação-02, cada transmissão de 15 min repartida em "
            f"{config.STATION02_REPORT_STEPS} passos de {config.RESAMPLE_MIN} min",
        ),
        (
            "Nível",
            "Estação-01 (sensor HC-SR04), filtro de picos em 3 passes; falhas preenchidas "
            "com a Estação-03",
        ),
        ("Dado bruto", f"dump SQL {os.path.basename(dump_path)}"),
    ]
    for key, val in config_lines:
        fig.text(x + 0.01, y, key, fontsize=9.5, fontweight="bold")
        wrapped = textwrap.wrap(val, width=100)
        for i, line in enumerate(wrapped):
            fig.text(x + 0.2, y - i * 0.013, line, fontsize=9.5)
        y -= 0.013 * len(wrapped) + 0.004

    y -= 0.012
    y = _cover_heading(fig, x, y, "Códigos que geraram os dados deste relatório")
    for script, desc in REPORT_SCRIPTS:
        fig.text(x + 0.01, y, f"{script} — {desc}", fontsize=7.5, color="dimgray")
        y -= 0.0115

    fig.text(
        x,
        0.036,
        f"Gerado em: {pd.Timestamp.now():%Y-%m-%d %H:%M} — AppTest/raspberry/"
        f"predictive_model_darts/ (branch {_current_git_branch()})",
        fontsize=8,
        color="dimgray",
    )
    fig.text(
        x,
        0.022,
        "Capa e catálogo somam 2 páginas, para que as Páginas A e B de cada evento fiquem "
        'lado a lado na visualização "2 páginas por vez".',
        fontsize=8,
        color="dimgray",
    )

    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page 1 — event catalogue table
# ---------------------------------------------------------------------------

NOTE_WRAP_CHARS = 30
NOTE_MAX_LINES = 3

RISE_NOTE_RE = re.compile(r"^subida máx\. em 30 min: (\d+) cm(?:; )?")
"""Leading "subida máx. em 30 min: N cm" written by build_event_catalogue.py —
the catalogue page shows it in its own column and keeps the rest as the note."""


def _format_note(note, width=NOTE_WRAP_CHARS, max_lines=NOTE_MAX_LINES):
    """
    @brief Wrap a note to a fixed character width, truncating with an
           ellipsis if it would need more than max_lines.

    Matplotlib table cells do not wrap text automatically — a long note
    (e.g. the training-set-expansion notes, ~140 chars) would otherwise
    overflow past the cell and off the page edge.

    @param note str Raw note text (already confirmed non-empty by caller).
    @param width int Wrap width in characters.
    @param max_lines int Max lines before truncating with "…".
    @return str Note text with embedded newlines, ready for a table cell.
    """
    wrapped = textwrap.wrap(note, width=width)
    if len(wrapped) <= max_lines:
        return "\n".join(wrapped)
    kept = wrapped[:max_lines]
    kept[-1] = kept[-1][: width - 1].rstrip() + "…"
    return "\n".join(kept)


def render_catalogue_page(pdf, df_events_raw, precip_by_event):
    """
    @brief Render the full event catalogue (config.EVENTS_CSV) as an A3 table
           page, including the 6/12/24 h accumulated precipitation before
           each peak.
    @param pdf PdfPages Open PDF being written.
    @param df_events_raw pd.DataFrame Raw catalogue CSV (string dates).
    @param precip_by_event dict {event_num: compute_precip_accumulations() dict}.
    """
    fig = plt.figure(figsize=A3_PORTRAIT_IN)
    fig.suptitle(
        f"SAPI — Catálogo de Eventos ({os.path.basename(config.EVENTS_CSV)}) — "
        "Auditoria de Lead Time e RMSE",
        fontsize=14,
        fontweight="bold",
        y=0.97,
    )
    # A dedicated sub-axes (rather than ax.table(bbox=...) on a full-figure
    # axes) so the table fills exactly this region with no unexplained gap —
    # same proven pattern as the metrics table in render_page_b().
    ax = fig.add_axes([0.02, 0.045, 0.96, 0.87])
    ax.axis("off")

    col_labels = [
        "Evt",
        "Início análise",
        "Fim análise",
        "Pico (UTC)",
        "Pico\n(cm)",
        "Conjunto",
        "Tipo",
        "Subida\nmáx. 30\nmin (cm)",
        "Nível\natingido",
    ]
    col_labels += [f"P{h}h" for h in PRECIP_WINDOWS_H]
    col_labels.append("Notas")
    split_col = col_labels.index("Conjunto")
    first_precip_col = col_labels.index(f"P{PRECIP_WINDOWS_H[0]}h")
    cell_text = []
    split_sets = []
    note_lines = []
    for _, r in df_events_raw.iterrows():
        note = "" if pd.isna(r.get("notes")) else str(r["notes"])
        # The rise gets its own column; keep only the rest of the note.
        rise_match = RISE_NOTE_RE.match(note)
        rise_cell = rise_match.group(1) if rise_match else ""
        note = note[rise_match.end() :] if rise_match else note
        formatted_note = _format_note(note) if note else ""
        precip_info = precip_by_event[int(r["event_num"])]
        precip_cells = [
            f"{precip_info[h]:.1f}" + ("*" if precip_info["flags"][h] else "")
            for h in PRECIP_WINDOWS_H
        ]
        cell_text.append(
            [
                f"{int(r['event_num']):02d}",
                str(r["analysis_start"])[:16],
                str(r["analysis_end"])[:16],
                str(r["peak_time"])[:16],
                f"{r['peak_cm']:.0f}",
                SPLIT_LABELS.get(r["split_set"], r["split_set"]),
                TYPE_LABELS.get(r["type"], r["type"]),
                rise_cell,
                r["level"],
            ]
            + precip_cells
            + [formatted_note]
        )
        split_sets.append(r["split_set"])
        note_lines.append(formatted_note.count("\n") + 1 if formatted_note else 1)

    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="upper left",
        cellLoc="left",
        colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.4)
    base_row_height = table[(1, 0)].get_height()
    # Widths sum to 0.96, not 1.0: loc="upper left" adds a small left pad, so
    # a full-width table overflows the right page edge.
    col_widths = [0.028, 0.102, 0.102, 0.102, 0.045, 0.062, 0.065, 0.058, 0.065]
    col_widths += [0.042] * len(PRECIP_WINDOWS_H)
    col_widths.append(0.96 - sum(col_widths))
    precip_cols = range(first_precip_col, first_precip_col + len(PRECIP_WINDOWS_H))
    for (row, col), cell in table.get_celld().items():
        cell.set_width(col_widths[col])
        if row == 0:
            # Headers wrap to up to three lines to keep the columns narrow.
            cell.set_height(base_row_height * 2.4)
            cell.set_text_props(fontweight="bold")
            cell.set_facecolor("#dddddd")
            continue
        # Rows with a multi-line wrapped note need a taller box, or the extra
        # lines bleed upward into the row above (tables don't auto-size row
        # height to content) — scale just this row's height by its line count.
        n_lines = note_lines[row - 1]
        if n_lines > 1:
            cell.set_height(base_row_height * (1 + 0.7 * (n_lines - 1)))
        if col == split_col:
            split = split_sets[row - 1]
            cell.set_text_props(
                fontweight="bold", color=SPLIT_COLORS.get(split, "black")
            )
        elif col in precip_cols and cell.get_text().get_text().endswith("*"):
            cell.set_text_props(color="firebrick", fontweight="bold")

    thresholds_txt = ", ".join(
        f"{name}={THRESHOLDS[name]}cm" for name in THRESHOLD_ORDER
    )
    fig.text(
        0.02,
        0.058,
        "Subida máx. 30 min: maior subida do nível em qualquer intervalo de 30 min do evento "
        "(valor de pico, não a média da subida inteira); Enxurrada quando chega a "
        f"{FLASH_FLOOD_30MIN_CM:.0f} cm.",
        fontsize=9,
        color="dimgray",
    )
    fig.text(
        0.02,
        0.042,
        f"Limiares: {thresholds_txt}  —  "
        "Fonte do dado bruto: dump SQL local  —  Fonte do dado filtrado/modelos: pipeline real_utils.py",
        fontsize=10,
        color="dimgray",
    )
    fig.text(
        0.02,
        0.026,
        "P6h/P12h/P24h: chuva acumulada (mm) nas 6/12/24 h antes do pico, da série que alimenta "
        f"os modelos (MERGE antes de {config.PRECIP_CUTOFF:%d/%m/%Y}, Estação-02 depois).",
        fontsize=9,
        color="dimgray",
    )
    fig.text(
        0.02,
        0.012,
        "* = janela com lacuna na fonte — ver aviso na página do evento.   "
        "Excluído = artefato de sensor, fora do treino e das métricas (Issue #227).",
        fontsize=9,
        color="dimgray",
    )
    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page A — raw vs filtered
# ---------------------------------------------------------------------------


def render_page_a(
    pdf, evt, raw_level, filtered_level, crossing_times, peak_flag, precip_info
):
    """
    @brief Render Page A (raw vs filtered level) for one event.

    @param pdf PdfPages
    @param evt pd.Series One row of df_events (tz-naive UTC dates).
    @param raw_level pd.Series Raw level_cm, sliced to the event window.
    @param filtered_level pd.Series Filtered level_delta_cm, sliced to the window.
    @param crossing_times dict {threshold_name: pd.Timestamp} from the filtered series.
    @param peak_flag str or None Warning text if the catalogued peak diverges
           from the filtered series' own max by more than PEAK_TOLERANCE_CM.
    @param precip_info dict Output of compute_precip_accumulations() for this event.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=A3_PORTRAIT_IN, sharex=True)

    header_bottom = _draw_header(
        fig,
        evt,
        page_label="Página A — Qualidade do dado (bruto vs. filtrado)",
        extra_note=peak_flag,
        precip_info=precip_info,
    )
    # Leave room for ax1's two-line title between the header and the plot.
    fig.subplots_adjust(
        top=min(0.86, header_bottom - 0.035),
        bottom=0.08,
        hspace=0.12,
        right=0.90,
        left=0.08,
    )

    win_start, win_end = evt["analysis_start"], evt["analysis_end"]
    y_lo, y_hi = compute_shared_ylim(filtered_level)

    ax1.plot(
        raw_level.index,
        raw_level.values,
        color=COLOR_OBS,
        linewidth=0.9,
        label="Nível bruto (level_cm)",
    )
    draw_threshold_lines(ax1, win_end)
    draw_time_guides(ax1, evt["peak_time"], crossing_times)
    ax1.set_ylim(y_lo, y_hi)
    ax1.set_ylabel("Nível bruto (cm)")
    ax1.set_title(
        textwrap.fill(
            "① Nível bruto — direto do dump SQL, sem filtro de delta. Escala vertical "
            "fixada pela série FILTRADA: outliers de sensor saem da área visível em vez "
            "de esmagar a escala.",
            width=100,
        ),
        loc="left",
        fontsize=10.5,
    )

    ax2.plot(
        filtered_level.index,
        filtered_level.values,
        color=COLOR_OBS,
        linewidth=1.1,
        label="Nível filtrado (level_delta_cm)",
    )
    draw_threshold_lines(ax2, win_end)
    draw_time_guides(ax2, evt["peak_time"], crossing_times)
    ax2.set_ylim(y_lo, y_hi)
    ax2.set_ylabel("Nível filtrado (cm)")
    ax2.set_title(
        "② Nível filtrado — pipeline real_utils.py (o que alimenta M4/M6)",
        loc="left",
        fontsize=10.5,
    )

    format_time_axis(ax1, win_start, win_end, is_bottom=False)
    format_time_axis(ax2, win_start, win_end, is_bottom=True)

    legend_elems = [
        Line2D([0], [0], color=COLOR_OBS, lw=1.1, label="Observado"),
        Line2D([0], [0], color=COLOR_PEAK, lw=1.6, ls="-.", label="Pico catalogado"),
    ]
    for name in THRESHOLD_ORDER:
        legend_elems.append(
            Line2D(
                [0],
                [0],
                color=THRESHOLD_COLORS[name],
                lw=1.1,
                ls="--",
                label=f"{name} ({THRESHOLDS[name]} cm)",
            )
        )
    fig.legend(
        handles=legend_elems,
        loc="lower center",
        ncol=5,
        fontsize=7,
        frameon=False,
        bbox_to_anchor=(0.5, 0.015),
    )

    pdf.savefig(fig)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Page B — per-horizon model audit
# ---------------------------------------------------------------------------


def render_page_b(
    pdf,
    evt,
    metrics_grid,
    horizon_data,
    crossing_times,
    occ,
    precip_info,
):
    """
    @brief Render Page B (M4 vs M6 per-horizon audit) for one event.

    @param pdf PdfPages
    @param evt pd.Series One row of df_events.
    @param metrics_grid tuple(row_labels, cell_text) or None (non-test event).
    @param horizon_data dict {horizon_min: (obs, m4_pred, m6_pred)} — each a
           pd.Series sliced to the event window, predictions UNSHIFTED
           (issuance time, matching how lead time is officially computed).
    @param crossing_times dict {threshold_name: pd.Timestamp} from the filtered
           series (used only for the peak/threshold vertical guide lines).
    @param occ dict Output of event_occurrences() — observed crossing
           occurrences and each model's alarm-firing instants (Issue #229).
    @param precip_info dict Output of compute_precip_accumulations() for this event.
    """
    fig = plt.figure(figsize=A3_PORTRAIT_IN)

    header_bottom = _draw_header(
        fig,
        evt,
        page_label="Página B — Auditoria de previsão M4 (LightGBM) vs. M6 (MLR)",
        extra_note=None,
        precip_info=precip_info,
    )

    win_start, win_end = evt["analysis_start"], evt["analysis_end"]

    # Explicit axes placement (fig.add_axes, not subplots_adjust) so the
    # metrics table and the 4 stacked panels never fight over the same space.
    # Pushed down when the header grows (precipitation warning, long notes).
    top_margin = min(0.895, header_bottom - 0.007)
    bottom_margin = 0.10
    left, width = 0.09, 0.80

    note_text = (
        "● = nível real cruzou o limiar (#1, #2 = cruzamentos repetidos); ▲ M4 / ▼ M6 = "
        f"alarme do modelo disparou (previsão acima do limiar por "
        f"{config.PRED_PERSISTENCE_STEPS * 5} min); ≥ = alarme já ligado no início da busca. "
        "Curvas na hora em que a previsão foi emitida."
    )

    if metrics_grid is None:
        fig.text(
            0.5,
            top_margin - 0.01,
            (
                "Evento excluído como artefato de sensor — sem previsões nem métricas "
                "(Issue #227)"
                if evt["split_set"] == "excluded"
                else "Sem métricas de backtest disponíveis — evento de treino"
            ),
            ha="center",
            fontsize=10,
            style="italic",
            color="dimgray",
        )
        note_y = top_margin - 0.045
        panels_top = top_margin - 0.065
    else:
        row_labels, cell_text, shaded = metrics_grid
        # One row per occurrence and model: the table grows with the number
        # of crossings and the panels below shrink to make room.
        table_height = 0.0125 * (len(row_labels) + 1)
        table_bottom = top_margin - table_height
        ax_table = fig.add_axes([left, table_bottom, width, table_height])
        ax_table.axis("off")
        # Row labels are prepended as an ordinary first column (rather than
        # matplotlib's built-in rowLabels=), which otherwise sizes/positions
        # that column outside our explicit width control and clips the text.
        full_rows = [[label] + row for label, row in zip(row_labels, cell_text)]
        table = ax_table.table(
            cellText=full_rows,
            colLabels=["Métrica"] + [f"+{h} min" for h in HORIZONS],
            bbox=[0, 0, 1, 1],  # fill the dedicated axes exactly
            cellLoc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        metric_col_widths = [0.40] + [0.60 / len(HORIZONS)] * len(HORIZONS)
        for (row, col), cell in table.get_celld().items():
            cell.set_width(metric_col_widths[col])
            if col == 0:
                cell.set_text_props(ha="left")
            if row == 0:
                cell.set_text_props(fontweight="bold")
            elif shaded[row - 1]:
                cell.set_facecolor("#eef2f7")
        note_y = table_bottom - 0.02
        panels_top = table_bottom - 0.045

    # Explicit wrap: matplotlib's wrap=True lets a centred line run into the
    # page's right edge.
    fig.text(
        0.5,
        note_y,
        textwrap.fill(note_text, width=150),
        ha="center",
        va="top",
        fontsize=9,
        style="italic",
        color="dimgray",
    )

    n_panels = len(HORIZONS)
    panel_gap = 0.012
    panel_height = (panels_top - bottom_margin - panel_gap * (n_panels - 1)) / n_panels
    axes = []
    for i in range(n_panels):
        y1 = panels_top - (i + 1) * panel_height - i * panel_gap
        axes.append(fig.add_axes([left, y1, width, panel_height]))

    for i, h in enumerate(HORIZONS):
        ax = axes[i]
        obs, m4_pred, m6_pred = horizon_data[h]
        ax.plot(
            obs.index, obs.values, color=COLOR_OBS, linewidth=1.1, label="Observado"
        )
        if not m4_pred.empty:
            ax.plot(
                m4_pred.index,
                m4_pred.values,
                color=COLOR_M4,
                linewidth=1.0,
                linestyle="--",
                label="Previsto M4",
            )
        if not m6_pred.empty:
            ax.plot(
                m6_pred.index,
                m6_pred.values,
                color=COLOR_M6,
                linewidth=1.0,
                linestyle="--",
                label="Previsto M6",
            )
        draw_threshold_lines(ax, win_end)
        draw_time_guides(ax, evt["peak_time"], crossing_times)
        draw_crossing_markers(ax, h, occ)
        summary_lines = summarize_crossings(h, occ)

        # Headroom: reserve the top of the panel for the summary box, so the
        # box sits above the curves instead of covering them (and the peak is
        # never clipped).
        values = pd.concat([obs, m4_pred, m6_pred]).dropna()
        lo = min(values.min() if len(values) else 50, THRESHOLDS["Atenção"]) - 3
        hi_data = max(values.max() if len(values) else 0, THRESHOLDS["Inundação"]) + 2
        panel_pt = panel_height * A3_PORTRAIT_IN[1] * 72
        box_frac = min(0.5, 0.05 + len(summary_lines) * 7 * 1.3 / panel_pt)
        ax.set_ylim(lo, lo + (hi_data - lo) / (1 - box_frac))

        if summary_lines:
            ax.text(
                0.01,
                0.97,
                "\n".join(summary_lines),
                transform=ax.transAxes,
                fontsize=7,
                va="top",
                ha="left",
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="white",
                    alpha=0.9,
                    edgecolor="lightgray",
                ),
                zorder=8,
            )
        ax.set_ylabel(f"+{h} min\n(cm)")
        format_time_axis(ax, win_start, win_end, is_bottom=(i == len(HORIZONS) - 1))

    legend_elems = [
        Line2D([0], [0], color=COLOR_OBS, lw=1.1, label="Observado"),
        Line2D([0], [0], color=COLOR_M4, lw=1.0, ls="--", label="Previsto M4"),
        Line2D([0], [0], color=COLOR_M6, lw=1.0, ls="--", label="Previsto M6"),
        Line2D([0], [0], color=COLOR_PEAK, lw=1.6, ls="-.", label="Pico catalogado"),
        Line2D(
            [0], [0], marker="o", color=COLOR_OBS, lw=0, label="Cruzamento observado"
        ),
        Line2D(
            [0], [0], marker="^", color=COLOR_M4, lw=0, label="Cruzamento previsto M4"
        ),
        Line2D(
            [0], [0], marker="v", color=COLOR_M6, lw=0, label="Cruzamento previsto M6"
        ),
    ]
    for name in THRESHOLD_ORDER:
        legend_elems.append(
            Line2D(
                [0],
                [0],
                color=THRESHOLD_COLORS[name],
                lw=1.1,
                ls="--",
                label=f"{name} ({THRESHOLDS[name]} cm)",
            )
        )
    fig.legend(
        handles=legend_elems,
        loc="lower center",
        ncol=5,
        fontsize=6.5,
        frameon=False,
        bbox_to_anchor=(0.5, 0.01),
    )

    pdf.savefig(fig)
    plt.close(fig)


def _draw_header(fig, evt, page_label, extra_note, precip_info=None):
    """
    @brief Draw the shared metadata header strip at the top of a page.
    @param fig matplotlib.Figure
    @param evt pd.Series Event row (tz-naive UTC dates).
    @param page_label str Sub-title identifying Page A or Page B.
    @param extra_note str or None Extra warning line (e.g. peak divergence).
    @param precip_info dict or None Output of compute_precip_accumulations();
           adds the 6/12/24 h accumulated-precipitation line (and its coverage
           warning, if any) below the peak line.
    @return float Figure y (0-1) just below the last header line, so the
            caller can keep its plot area clear of a taller header.
    """
    peak_time = evt["peak_time"]
    local_time = peak_time + pd.Timedelta(hours=LOCAL_TZ_OFFSET_H)
    type_label = TYPE_LABELS.get(evt["type"], evt["type"])
    split_label = SPLIT_LABELS.get(evt["split_set"], evt["split_set"])
    notes = evt.get("notes", "")
    notes = "" if pd.isna(notes) else str(notes)

    fig.suptitle(
        f"Evento {int(evt['event_num']):02d} — {page_label}",
        fontsize=13,
        fontweight="bold",
        y=0.985,
    )
    fig.text(
        0.965,
        0.985,
        split_label.upper(),
        ha="right",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="white",
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor=SPLIT_COLORS.get(evt["split_set"], "gray"),
            edgecolor="none",
        ),
    )

    line1 = (
        f"Janela: {evt['analysis_start']:%Y-%m-%d %H:%M} → {evt['analysis_end']:%Y-%m-%d %H:%M} UTC   |   "
        f"Tipo: {type_label}   |   Nível atingido: {evt['level']}"
    )
    line2 = (
        f"Pico: {evt['peak_cm']:.0f} cm às {peak_time:%Y-%m-%d %H:%M} UTC "
        f"({local_time:%H:%M} horário local)"
    )

    fig.text(0.5, 0.955, line1, ha="center", fontsize=9)
    fig.text(0.5, 0.938, line2, ha="center", fontsize=9)

    y = 0.921
    if precip_info is not None:
        fig.text(
            0.5,
            y,
            format_precip_line(precip_info),
            ha="center",
            fontsize=9,
            fontweight="bold",
        )
        y -= 0.016
        if precip_info["warning"]:
            for wline in textwrap.wrap(precip_info["warning"], width=130):
                fig.text(0.5, y, wline, ha="center", fontsize=8.5, color="firebrick")
                y -= 0.014
            y -= 0.002

    # Notes get their own wrapped, centered line(s) rather than being
    # appended to line2 — a long note (e.g. the training-set-expansion
    # notes) made line2 wide enough to run off the left edge of the page
    # when centered as a single string.
    if notes:
        for wline in textwrap.wrap(f"Notas: {notes}", width=130):
            fig.text(0.5, y, wline, ha="center", fontsize=8.5, color="dimgray")
            y -= 0.014
        y -= 0.004

    if extra_note:
        for wline in textwrap.wrap(extra_note, width=120):
            fig.text(
                0.5,
                y,
                wline,
                ha="center",
                fontsize=9,
                color="firebrick",
                fontweight="bold",
            )
            y -= 0.016

    return y


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def load_all_events():
    """
    @brief Every catalogue row, excluded ones included, with parsed dates.

    real_utils.load_event_catalogue() drops excluded rows, which is right for
    the models but not for an audit: the events excluded as sensor artifacts
    (Issue #227) must stay visible so the exclusion itself can be checked.

    @return pd.DataFrame with tz-naive UTC peak_time/analysis_start/analysis_end.
    """
    df = pd.read_csv(config.EVENTS_CSV, encoding="utf-8-sig")
    for col in ("peak_time", "analysis_start", "analysis_end"):
        df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
    return df


def main():
    """
    @brief Load all data sources and generate the full audit PDF.
    """
    dump_path = DEFAULT_DUMP
    if "--dump" in sys.argv:
        idx = sys.argv.index("--dump")
        if idx + 1 < len(sys.argv):
            dump_path = sys.argv[idx + 1]

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== SAPI — Auditoria de Eventos (raw/filtrado + M4 vs M6) ===\n")

    print(f"Carregando dado filtrado (real_utils.load_real_data())...")
    # Unmasked on purpose: the artifact windows (Issue #227) are blanked in
    # what the models see, but this report must show what was removed.
    ts_level, ts_precip, _ = real_utils.load_real_data(mask_artifacts=False)
    df_level_filtered = ts_level.to_dataframe()["level_delta_cm"]
    print(f"  {len(df_level_filtered)} pontos filtrados carregados.")

    df_events_raw = pd.read_csv(config.EVENTS_CSV, encoding="utf-8-sig")
    df_events = load_all_events()

    print("Calculando chuva acumulada 6/12/24 h antes de cada pico...")
    precip = ts_precip.to_dataframe()["prec_mm"]
    st02_idx, merge_idx = load_precip_source_indexes()
    precip_by_event = {
        int(evt["event_num"]): compute_precip_accumulations(
            precip, st02_idx, merge_idx, evt["peak_time"]
        )
        for _, evt in df_events.iterrows()
    }
    save_precip_table(df_events, precip_by_event)

    print(f"Fazendo parsing do dump SQL ({dump_path})...")
    raw_level_full = load_raw_level(dump_path)
    print(
        f"  {len(raw_level_full)} pontos brutos carregados "
        f"({raw_level_full.index.min()} → {raw_level_full.index.max()})."
    )

    print("Carregando previsões contínuas M4/M6...")
    m4_pred, m6_pred = load_predictions()
    print(f"  M4: {len(m4_pred)} linhas   M6: {len(m6_pred)} linhas.")

    print("Carregando métricas de RMSE/lead time...")
    lead_m4, lead_m6, rmse = load_metrics()

    n_train = int((df_events_raw["split_set"] == "train").sum())
    n_test = int((df_events_raw["split_set"] == "test").sum())
    n_excluded = int((df_events_raw["split_set"] == "excluded").sum())

    with PdfPages(OUTPUT_PDF) as pdf:
        print("\nRenderizando capa...")
        render_cover_page(
            pdf, len(df_events_raw), n_train, n_test, n_excluded, dump_path
        )

        print("Renderizando página de catálogo...")
        render_catalogue_page(pdf, df_events_raw, precip_by_event)

        for _, evt in df_events.iterrows():
            event_num = int(evt["event_num"])
            print(f"── Evento {event_num:02d} ...")

            win_start, win_end = evt["analysis_start"], evt["analysis_end"]

            filtered_win = df_level_filtered.loc[win_start:win_end]
            raw_win = raw_level_full.loc[win_start:win_end]

            crossing_times = {
                name: first_crossing(filtered_win, THRESHOLDS[name])
                for name in THRESHOLD_ORDER
            }

            peak_flag = None
            if not filtered_win.empty:
                observed_max = filtered_win.max()
                if abs(observed_max - evt["peak_cm"]) > PEAK_TOLERANCE_CM:
                    peak_flag = (
                        f"⚠ Pico catalogado ({evt['peak_cm']:.0f} cm) diverge do máximo da série "
                        f"FILTRADA na janela ({observed_max:.0f} cm) — conferir catálogo"
                    )
            if evt.get("exclusion") == "artifact":
                peak_flag = EXCLUDED_NOTE + (f"   {peak_flag}" if peak_flag else "")

            render_page_a(
                pdf,
                evt,
                raw_win,
                filtered_win,
                crossing_times,
                peak_flag,
                precip_by_event[event_num],
            )

            # Same rule and parameters as the 04_lead_time_* scripts
            # (Issue #229), so the table and markers match their CSVs.
            occ = event_occurrences(m4_pred, m6_pred, win_start, win_end)
            is_test = evt["split_set"] == "test"
            if is_test:
                check_against_csv(event_num, occ, {"M4": lead_m4, "M6": lead_m6})
            metrics_grid = build_metrics_grid(event_num, is_test, occ, rmse)

            horizon_data = {}
            for h in HORIZONS:
                obs = observed_from_predictions(m4_pred, win_start, win_end)
                m4_win = windowed_prediction(m4_pred, h, win_start, win_end)
                m6_win = windowed_prediction(m6_pred, h, win_start, win_end)
                horizon_data[h] = (obs, m4_win, m6_win)

            render_page_b(
                pdf,
                evt,
                metrics_grid,
                horizon_data,
                crossing_times,
                occ,
                precip_by_event[event_num],
            )

    print(f"\nConcluído. PDF salvo em: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
