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
@file real_utils.py
@brief Pre-processing utilities for real SAPI measurement data (Issue #99).

Loads Station-01 level and combined precipitation (MERGE + Station-02),
applies quality filters, resamples to 5-min grid, and returns Darts TimeSeries
objects ready for model training and evaluation.

No imports from predictive_model_v2/.  Only reads CSVs from DATA_DIR.
"""

import warnings
import numpy as np
import pandas as pd
from darts import TimeSeries

import config


def apply_delta_filter(
    series: pd.Series,
    max_delta: float = config.LEVEL_MAX_DELTA,
) -> pd.Series:
    """Remove spike outliers from a level series.

    Iterates the series and replaces any reading where
    |v − prev_clean| > *max_delta* with NaN.  The 'clean' reference tracks the
    last accepted value so consecutive spikes are all flagged until the level
    returns to a plausible range.

    :param series: Raw level series (any temporal resolution).
    :param max_delta: Maximum allowed change in cm from the previous clean value.
    :return: Filtered series with spikes set to NaN.
    :rtype: pd.Series
    """
    out = series.copy().astype(float)
    prev_clean = np.nan
    for idx in out.index:
        v = out.at[idx]
        if np.isnan(v):
            continue
        if not np.isnan(prev_clean) and abs(v - prev_clean) > max_delta:
            out.at[idx] = np.nan
        else:
            prev_clean = v
    return out


def load_precip_5min() -> pd.DataFrame:
    """
    @brief Spliced 5-min precipitation series exactly as the models see it.

    Before config.PRECIP_CUTOFF: MERGE hourly totals spread evenly over 12
    five-minute slots (ffill / 12, times config.PRECIP_MERGE_SCALE). From
    PRECIP_CUTOFF: Station-02 reports summed per slot, then each slot's total
    spread evenly over itself and the next STATION02_REPORT_STEPS - 1 slots
    (Issue #124) — a report covers ~15 min, so leaving it in one slot made a
    one-wet-two-dry sawtooth. The spread is forward-only (causal) and
    conserves the total exactly. Missing values become 0.0 mm.

    Factored out of load_real_data() so build_event_catalogue.py can read the
    precipitation without also reading the catalogue it is about to write.

    @return DataFrame with one "prec_mm" column on a tz-naive UTC 5-min index.
    """
    freq = f"{config.RESAMPLE_MIN}min"

    # ── MERGE precipitation (hourly → 5-min) ───────────────────────────────
    # Historical archive uses "timestamp" column (not "reading_time" from the rolling cache).
    df_merge = pd.read_csv(config.MERGE_CSV, parse_dates=["timestamp"])
    df_merge["timestamp"] = pd.to_datetime(df_merge["timestamp"], utc=True)
    df_merge = df_merge.set_index("timestamp").sort_index()[["prec_mm"]]
    # Each hourly total is spread evenly across 12 five-minute slots.
    df_merge_5min = df_merge.resample(freq).ffill() / 12
    # Optional bias correction against Station-02 (Issue #223 ablation arm);
    # no-op at the default PRECIP_MERGE_SCALE of 1.0.
    df_merge_5min = df_merge_5min * config.PRECIP_MERGE_SCALE
    df_merge_5min["prec_mm"] = df_merge_5min["prec_mm"].fillna(0.0)
    df_merge_5min.index = df_merge_5min.index.tz_localize(None)

    # ── Station-02 precipitation (15-min reports → 5-min, spread) ──────────
    df_st02 = pd.read_csv(config.STATION02_CSV, parse_dates=["timestamp"])
    df_st02["timestamp"] = pd.to_datetime(df_st02["timestamp"], utc=True)
    df_st02 = df_st02.set_index("timestamp").sort_index()[["precipitation_mm"]]
    df_st02_5min = df_st02.resample(freq).sum()
    # Spread each report forward over the slot it lands in and the next ones
    # (Issue #124). The index is extended first so the last report keeps its
    # full total; sum-then-roll (not ffill) also keeps the rain of the few
    # slots that receive two reports.
    n = config.STATION02_REPORT_STEPS
    ext = pd.date_range(
        df_st02_5min.index[0],
        df_st02_5min.index[-1] + (n - 1) * pd.Timedelta(freq),
        freq=freq,
    )
    df_st02_5min = df_st02_5min.reindex(ext, fill_value=0.0)
    df_st02_5min = df_st02_5min.rolling(n, min_periods=1).sum() / n
    df_st02_5min.columns = ["prec_mm"]
    df_st02_5min["prec_mm"] = df_st02_5min["prec_mm"].fillna(0.0)
    df_st02_5min.index = df_st02_5min.index.tz_localize(None)

    # ── Splice at PRECIP_CUTOFF ──────────────────────────────────────────────
    cutoff_naive = config.PRECIP_CUTOFF.tz_localize(None)
    part_merge = df_merge_5min[df_merge_5min.index < cutoff_naive]
    part_st02 = df_st02_5min[df_st02_5min.index >= cutoff_naive]
    df_precip_rs = pd.concat([part_merge, part_st02]).sort_index()
    df_precip_rs = df_precip_rs[~df_precip_rs.index.duplicated(keep="first")]
    df_precip_rs["prec_mm"] = df_precip_rs["prec_mm"].fillna(0.0)
    return df_precip_rs


def load_artifact_windows() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    @brief Analysis windows of the catalogue rows excluded as sensor artifacts
           (Issue #227).

    build_event_catalogue.py marks an episode ``exclusion == "artifact"`` when
    it is not a flood but an HC-SR04 echo burst the level filter merged into a
    fake rise. The level inside these windows is not a river level and must not
    reach training, inference metrics or the alert simulation. Rows excluded
    only because they straddle TRAIN_END are real floods and are NOT returned.

    @return List of (start, end) tz-naive UTC timestamps, inclusive. Empty if
            the catalogue has no ``exclusion`` column (pre-#227 catalogues).
    """
    df = pd.read_csv(config.EVENTS_CSV, encoding="utf-8-sig")
    if "exclusion" not in df.columns:
        return []
    art = df[df["exclusion"] == "artifact"]
    to_naive = lambda s: pd.to_datetime(s, utc=True).tz_localize(None)
    return [
        (to_naive(s), to_naive(e))
        for s, e in zip(art["analysis_start"], art["analysis_end"])
    ]


def in_artifact_windows(index: pd.DatetimeIndex) -> np.ndarray:
    """
    @brief Boolean mask of the timestamps that fall inside an artifact window.
    @param index tz-naive UTC DatetimeIndex.
    @return np.ndarray of bool, aligned to ``index``.
    """
    mask = np.zeros(len(index), dtype=bool)
    for start, end in load_artifact_windows():
        mask |= (index >= start) & (index <= end)
    return mask


def mask_artifact_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    @brief Blank every level/prediction column of a continuous-prediction
           table inside the artifact windows (Issue #227).

    The level input is already NaN there, but M6 forward-fills its inputs for
    inference, so its forecasts would otherwise exist over a window that is
    not river level. Blanking both models' rows keeps those windows out of
    every downstream metric and of the alert simulation.

    @param df Prediction table with a "timestamp" column (tz-naive UTC) and
           h_obs / h_pred_* / h_actual_* columns.
    @return The same DataFrame, modified in place and returned.
    """
    mask = in_artifact_windows(pd.DatetimeIndex(df["timestamp"]))
    cols = [
        c for c in df.columns if c == "h_obs" or c.startswith(("h_pred_", "h_actual_"))
    ]
    df.loc[mask, cols] = np.nan
    return df


def load_real_data(
    mask_artifacts: bool = True,
) -> tuple[TimeSeries, TimeSeries, pd.DataFrame]:
    """Load and pre-process real Station-01 level and precipitation data.

    Processing pipeline:

    **Level (Station-01)**
    1. Read ``station01_level.csv`` (UTC-aware timestamps, ``level_delta_cm`` column).
    2. Clip to physical range [LEVEL_MIN_CM, LEVEL_MAX_CM].
    3. Apply delta filter (removes spikes > LEVEL_MAX_DELTA cm step).
    4. Resample to 5-min mean.
    5. Gap-fill short gaps (≤ GAP_FILL_MAX_MIN) by linear interpolation.
    6. Strip timezone (Darts 0.43 requires tz-naive timestamps).

    **Precipitation (spliced)**
    - Before PRECIP_CUTOFF: MERGE satellite/radar hourly totals distributed
      evenly over 12 × 5-min slots (ffill / 12).
    - From PRECIP_CUTOFF: Station-02 tipping-bucket tips summed per 5-min slot.

    **Sensor artifacts (Issue #227)**
    - Level inside the windows of catalogue rows marked ``exclusion ==
      "artifact"`` is set to NaN (see load_artifact_windows()).

    **Event windows**
    - load_event_catalogue(): config.EVENTS_CSV, excluded rows dropped.

    :param mask_artifacts: Blank the artifact windows (default). Pass False
        only to inspect what was removed (the audit PDF does).
    :return: Tuple of (ts_level, ts_precip, df_events) with tz-naive timestamps.
    :rtype: tuple[TimeSeries, TimeSeries, pd.DataFrame]
    """
    freq = f"{config.RESAMPLE_MIN}min"

    # ── Station-01 level ────────────────────────────────────────────────────
    df_lvl = pd.read_csv(config.LEVEL_CSV, parse_dates=["timestamp"])
    df_lvl["timestamp"] = pd.to_datetime(df_lvl["timestamp"], utc=True)
    df_lvl = df_lvl.set_index("timestamp").sort_index()
    # The gap-filled CSV carries a non-numeric `source` column alongside the
    # level; keep only the level so the later resample().mean() stays valid.
    df_lvl = df_lvl[["level_delta_cm"]]

    df_lvl["level_delta_cm"] = df_lvl["level_delta_cm"].clip(
        lower=config.LEVEL_MIN_CM, upper=config.LEVEL_MAX_CM
    )
    df_lvl["level_delta_cm"] = apply_delta_filter(df_lvl["level_delta_cm"])

    df_lvl_rs = df_lvl.resample(freq).mean()

    max_gap_steps = config.GAP_FILL_MAX_MIN // config.RESAMPLE_MIN
    df_lvl_rs["level_delta_cm"] = df_lvl_rs["level_delta_cm"].interpolate(
        method="linear", limit=max_gap_steps
    )

    # Strip timezone for Darts 0.43
    df_lvl_rs.index = df_lvl_rs.index.tz_localize(None)

    # ── Sensor-artifact windows (Issue #227) ────────────────────────────────
    # Not river level: blank them so they never reach training or metrics.
    if mask_artifacts:
        df_lvl_rs.loc[in_artifact_windows(df_lvl_rs.index), "level_delta_cm"] = np.nan

    # ── Precipitation (MERGE + Station-02 splice) ───────────────────────────
    df_precip_rs = load_precip_5min()

    # ── Event windows ────────────────────────────────────────────────────────
    df_events = load_event_catalogue()

    # ── Darts TimeSeries ─────────────────────────────────────────────────────
    df_lvl_clean = df_lvl_rs.dropna(subset=["level_delta_cm"])
    ts_level = TimeSeries.from_dataframe(
        df_lvl_clean,
        value_cols=["level_delta_cm"],
        freq=freq,
        fill_missing_dates=True,
    )
    ts_precip = TimeSeries.from_dataframe(
        df_precip_rs,
        value_cols=["prec_mm"],
        freq=freq,
        fill_missing_dates=True,
    )

    return ts_level, ts_precip, df_events


def build_training_segments(
    ts_level: TimeSeries,
    ts_precip: TimeSeries,
    df_events: pd.DataFrame,
    buffer_steps: int,
) -> tuple[list[TimeSeries], list[TimeSeries]]:
    """Slice train events (with pre-event buffer) into segment pairs for fit().

    Each segment spans from (analysis_start − buffer) to analysis_end so that
    the lag features at event onset are well-defined.  Segments that are too
    short to produce any training sample are skipped with a warning.

    :param ts_level: Full level TimeSeries.
    :param ts_precip: Full precipitation TimeSeries.
    :param df_events: Events DataFrame (excluded rows already removed).
    :param buffer_steps: Number of 5-min steps to prepend before analysis_start.
    :return: Tuple (ts_train_list, pc_train_list).
    :rtype: tuple[list[TimeSeries], list[TimeSeries]]
    """
    buffer = pd.Timedelta(minutes=buffer_steps * config.RESAMPLE_MIN)
    ts_list: list[TimeSeries] = []
    pc_list: list[TimeSeries] = []

    for _, evt in df_events[df_events["split_set"] == "train"].iterrows():
        buf_start = evt["analysis_start"] - buffer
        seg_start = max(ts_level.start_time(), buf_start)
        seg_end = evt["analysis_end"]

        ts_seg = ts_level.slice(seg_start, seg_end)
        pc_seg = ts_precip.slice(seg_start, seg_end)

        min_len = buffer_steps + config.OUTPUT_CHUNK_STEPS + 1
        if len(ts_seg) < min_len:
            print(
                f"  [WARN] Train event {evt['event_num']} too short "
                f"({len(ts_seg)} steps, need {min_len}) — skipped"
            )
            continue

        # Fill any remaining NaN (gaps > GAP_FILL_MAX_MIN) within the training
        # segment using forward-fill then backward-fill.  Training data cannot
        # contain NaN targets; long-gap interpolation is acceptable here because
        # it only affects training quality, not evaluation integrity.
        df_seg = ts_seg.to_dataframe()
        df_seg = df_seg.ffill().bfill()
        if df_seg.isnull().values.any():
            print(
                f"  [WARN] Train event {evt['event_num']} still has NaN after fill — skipped"
            )
            continue
        freq = f"{config.RESAMPLE_MIN}min"
        ts_seg = TimeSeries.from_dataframe(df_seg, freq=freq)

        ts_list.append(ts_seg)
        pc_list.append(pc_seg)

    return ts_list, pc_list


def load_event_catalogue() -> pd.DataFrame:
    """Load the event catalogue with the split that matches the training mode.

    Single source of truth for ``split_set`` across every script in this
    folder.  Reads ``config.EVENTS_CSV`` (UTF-8-BOM safe), parses the three
    timestamp columns as tz-naive UTC, and drops excluded rows.

    Under ``TRAIN_MODE == "continuous"`` the catalogue's hand-assigned
    ``split_set`` no longer describes what the model actually saw — training is
    a contiguous period ending at ``config.TRAIN_END``, not a set of picked
    windows — so the column is recomputed chronologically:

    - ``analysis_end <= TRAIN_END``    -> ``train``
    - ``analysis_start >= TRAIN_END``  -> ``test``
    - straddling the cut              -> ``excluded`` (and dropped), so that no
      test event shares any data with training

    Under ``TRAIN_MODE == "events"`` the catalogue is returned unchanged.

    :return: Events DataFrame with tz-naive timestamps and no excluded rows.
    :rtype: pd.DataFrame
    """
    df = pd.read_csv(config.EVENTS_CSV, encoding="utf-8-sig")
    for col in ("peak_time", "analysis_start", "analysis_end"):
        df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)

    if config.TRAIN_MODE == "continuous":
        cut = pd.Timestamp(config.TRAIN_END)
        if cut.tz is not None:
            cut = cut.tz_localize(None)
        chronological = np.where(
            df["analysis_end"] <= cut,
            "train",
            np.where(df["analysis_start"] >= cut, "test", "excluded"),
        )
        # A row the catalogue itself excluded stays excluded — the
        # chronological rule reassigns the split, it does not reinstate events.
        df["split_set"] = np.where(
            df["split_set"] == "excluded", "excluded", chronological
        )

    # Excluded rows: sensor artifacts (Issue #227) and, under the continuous
    # split, events straddling TRAIN_END.
    return df[df["split_set"] != "excluded"].reset_index(drop=True)


def build_continuous_training_segment(
    ts_level: TimeSeries,
    ts_precip: TimeSeries,
) -> tuple[list[TimeSeries], list[TimeSeries]]:
    """Slice one contiguous training period covering floods *and* dry weather.

    Counterpart to :func:`build_training_segments` for
    ``TRAIN_MODE == "continuous"`` (Issue #223).  Instead of concatenating the
    catalogued flood windows — which makes the training sample 100% flood
    episodes and biases every long-horizon forecast upward — this returns the
    single unbroken stretch from the start of the record to
    ``config.TRAIN_END``, so the model is fitted on the same population it is
    later asked to predict.

    Residual NaN (gaps longer than ``GAP_FILL_MAX_MIN``) are forward- then
    backward-filled, exactly as :func:`build_training_segments` does, because
    the regressors cannot take NaN targets.

    Sensor-artifact windows (Issue #227) are the exception: filling them would
    paint an invented flat level into training, so the period is instead split
    into contiguous pieces around them and fitted as a list of series. Pieces
    shorter than WINDOW_STEPS + OUTPUT_CHUNK_STEPS + 1 cannot yield a single
    training sample and are skipped with a warning.

    :param ts_level: Full level TimeSeries.
    :param ts_precip: Full precipitation TimeSeries.
    :return: Tuple (ts_train_list, pc_train_list) — one pair per contiguous
        piece (a single pair when there are no artifact windows).
    :rtype: tuple[list[TimeSeries], list[TimeSeries]]
    """
    cut = pd.Timestamp(config.TRAIN_END)
    if cut.tz is not None:
        cut = cut.tz_localize(None)
    seg_end = min(cut, ts_level.end_time())

    ts_seg = ts_level.slice(ts_level.start_time(), seg_end)
    pc_seg = ts_precip.slice(ts_seg.start_time(), ts_seg.end_time())

    # Precipitation gaps mean "no measurement", which for a tipping bucket is
    # indistinguishable from no rain — same convention the simulation step uses.
    # LightGBM would route NaN natively but LinearRegression rejects it, and the
    # M4-vs-M6 comparison is only controlled if both see identical inputs.
    freq = f"{config.RESAMPLE_MIN}min"
    df_pc = pc_seg.to_dataframe().fillna(0.0)

    # Split around the artifact windows: each run of consecutive
    # non-artifact steps becomes its own series (Issue #227).
    df_lvl = ts_seg.to_dataframe()
    is_artifact = in_artifact_windows(df_lvl.index)
    run_id = np.cumsum(np.r_[True, is_artifact[1:] != is_artifact[:-1]])
    min_len = config.WINDOW_STEPS + config.OUTPUT_CHUNK_STEPS + 1

    ts_list: list[TimeSeries] = []
    pc_list: list[TimeSeries] = []
    for rid in np.unique(run_id[~is_artifact]):
        piece = df_lvl[run_id == rid]
        if len(piece) < min_len:
            print(
                f"  [WARN] Training piece {piece.index[0]} -> {piece.index[-1]} "
                f"too short ({len(piece)} steps, need {min_len}) — skipped"
            )
            continue
        piece = piece.ffill().bfill()
        if piece.isnull().values.any():
            raise ValueError(
                "Continuous training segment still has NaN after ffill/bfill — "
                "check LEVEL_CSV coverage before TRAIN_END."
            )
        ts_list.append(TimeSeries.from_dataframe(piece, freq=freq))
        pc_list.append(
            TimeSeries.from_dataframe(
                df_pc.loc[piece.index[0] : piece.index[-1]], freq=freq
            )
        )

    if is_artifact.any():
        print(
            f"  Training split into {len(ts_list)} contiguous pieces around "
            f"{len(load_artifact_windows())} artifact windows "
            f"({int(is_artifact.sum()):,} steps removed, Issue #227)."
        )
    return ts_list, pc_list
