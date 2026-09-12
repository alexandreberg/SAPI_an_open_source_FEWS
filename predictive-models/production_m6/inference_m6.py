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
@file inference_m6.py
@brief Single-step inference for the SAPI M6 MLR production pipeline (Issue #120).

Takes raw API response lists (level + precip), pre-processes them into Darts
TimeSeries objects, runs model.predict(), computes the precipitation gate, and
returns a structured result dict.  This module is stateless — debounce tracking
lives in state_m6.py.

Key difference from M4's inference.py:
  - Uses LinearRegressionModel (sklearn MultiOutputRegressor) instead of LightGBMModel.
  - LinearRegression cannot route NaN values in lag windows (unlike LightGBM tree splits),
    so the level TimeSeries is forward-filled before predict().
  - Buffer threshold uses MLR_BUFFER_STEPS instead of LGBM_BUFFER_STEPS.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from darts import TimeSeries
from darts.models import LinearRegressionModel

import api_client_m6 as api_client
import config_production_m6 as cfg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-processing helpers
# ---------------------------------------------------------------------------

def _apply_delta_filter(series: pd.Series) -> pd.Series:
    """Replace spikes where |v - prev_clean| > LEVEL_MAX_DELTA with NaN.

    @param series  Raw level pandas Series.
    @return Filtered Series with outliers set to NaN.
    """
    out = series.copy().astype(float)
    prev_clean = np.nan
    for idx in out.index:
        v = out.at[idx]
        if np.isnan(v):
            continue
        if not np.isnan(prev_clean) and abs(v - prev_clean) > cfg.LEVEL_MAX_DELTA:
            out.at[idx] = np.nan
        else:
            prev_clean = v
    return out


def _parse_api_rows(rows: list[dict], value_key: str) -> pd.Series:
    """Convert a list of {timestamp, value} API dicts into a tz-naive pandas Series.

    @param rows       List of dicts from api_client_m6.fetch_data().
    @param value_key  Key to use as the value column.
    @return Pandas Series indexed by tz-naive UTC timestamps, sorted ascending.
    """
    if not rows:
        return pd.Series(dtype=float)

    ts_list  = [pd.Timestamp(r["timestamp"], tz="UTC") for r in rows]
    val_list = [float(r[value_key]) if r[value_key] is not None else np.nan
                for r in rows]

    ser = pd.Series(val_list, index=ts_list, name=value_key, dtype=float)
    ser.index = ser.index.tz_localize(None)
    return ser.sort_index()


def build_level_series(rows: list[dict]) -> Optional[pd.Series]:
    """Pre-process raw level API rows into a clean 5-min resampled Series.

    Pipeline: parse → clip → delta-filter → resample 5-min mean → gap-fill.

    @param rows  Raw API rows from fetch_data(station_id, 'level', ...).
    @return Clean 5-min Series, or None if there are fewer than MLR_BUFFER_STEPS rows.
    """
    freq = f"{cfg.RESAMPLE_MIN}min"

    raw = _parse_api_rows(rows, "value")
    if raw.empty:
        logger.warning("build_level_series: empty input")
        return None

    raw = raw.clip(lower=cfg.LEVEL_MIN_CM, upper=cfg.LEVEL_MAX_CM)
    raw = _apply_delta_filter(raw)

    rs = raw.resample(freq).mean()

    max_gap = cfg.GAP_FILL_MAX_MIN // cfg.RESAMPLE_MIN
    rs = rs.interpolate(method="linear", limit=max_gap)

    if rs.notna().sum() < cfg.MLR_BUFFER_STEPS:
        logger.warning(
            "build_level_series: only %d non-NaN steps after resampling (need %d)",
            rs.notna().sum(), cfg.MLR_BUFFER_STEPS,
        )
        return None

    return rs


def _build_merge_series_from_rows(rows: list[dict], now_naive: pd.Timestamp) -> pd.Series | None:
    """Convert MERGE API rows into a 5-min forward-filled precipitation Series.

    @param rows       List of {timestamp, value} dicts from fetch_merge().
    @param now_naive  Current UTC timestamp (tz-naive) for zero-padding the tail.
    @return 5-min Series, or None if rows is empty.
    """
    if not rows:
        return None

    freq = f"{cfg.RESAMPLE_MIN}min"
    raw = _parse_api_rows(rows, "value")
    if raw.empty:
        return None

    raw.name = "prec_mm"
    df = raw.to_frame()
    rs = df.resample(freq).ffill() / 12
    rs["prec_mm"] = rs["prec_mm"].fillna(0.0)
    return rs["prec_mm"]


def build_precip_series(
    station02_rows: list[dict],
    merge_fallback: bool = False,
) -> pd.Series:
    """Pre-process precipitation API rows into a 5-min resampled Series.

    Station-02 tipping-bucket tips are summed per 5-min slot and then spread over
    STATION02_REPORT_STEPS consecutive steps (Issue #124), matching how the training
    series is built in results_final_m6_mlr/real_utils.py::load_precip_5min.
    MERGE hourly totals are forward-filled and divided by 12 (5-min distribution).

    @param station02_rows  Raw API rows from fetch_data(2, 'precip', ...).
    @param merge_fallback  If True, use MERGE source instead of station02_rows.
    @return 5-min precipitation Series (NaN filled with 0.0).
    """
    freq = f"{cfg.RESAMPLE_MIN}min"
    now_naive = pd.Timestamp.utcnow().tz_localize(None)

    if merge_fallback:
        try:
            merge_rows = api_client.fetch_merge(cfg.MERGE_FALLBACK_HOURS)
            ser = _build_merge_series_from_rows(merge_rows, now_naive)
            if ser is not None:
                logger.info("build_precip_series: MERGE fallback via API (%d rows)", len(ser))
                return ser
            logger.warning("build_precip_series: MERGE API returned 0 rows — trying local CSV")
        except Exception as exc:
            logger.warning("build_precip_series: MERGE API error — %s — trying local CSV", exc)

        try:
            df = pd.read_csv(cfg.MERGE_CSV, parse_dates=["reading_time"])
            df["reading_time"] = pd.to_datetime(df["reading_time"], utc=True)
            df = df.set_index("reading_time").sort_index()[["prec_mm"]]

            cutoff = now_naive - pd.Timedelta(hours=cfg.MERGE_FALLBACK_HOURS)
            df.index = df.index.tz_localize(None)
            df = df[df.index >= cutoff]

            rs = df.resample(freq).ffill() / 12
            rs["prec_mm"] = rs["prec_mm"].fillna(0.0)
            logger.warning("build_precip_series: MERGE fallback via local CSV (%d rows) — CSV may be stale",
                           len(rs))
            return rs["prec_mm"]
        except Exception as exc:
            logger.warning("build_precip_series: local CSV also failed — %s — using zeros", exc)

        cutoff = now_naive - pd.Timedelta(hours=cfg.GATE_WINDOW_MIN // 60)
        idx = pd.date_range(start=cutoff, end=now_naive, freq=freq)
        return pd.Series(0.0, index=idx, name="prec_mm")

    raw = _parse_api_rows(station02_rows, "value")
    if raw.empty:
        cutoff = now_naive - pd.Timedelta(hours=cfg.GATE_WINDOW_MIN // 60)
        idx = pd.date_range(start=cutoff, end=now_naive, freq=freq)
        return pd.Series(0.0, index=idx, name="prec_mm")

    rs = raw.resample(freq).sum()
    rs = rs.fillna(0.0)

    # Spread each Station-02 report over STATION02_REPORT_STEPS steps (Issue #124).
    # The tipping-bucket transmits an accumulated 15-min total; dropping it into a
    # single 5-min slot followed by two zeros makes the forecast jump at every
    # transmission.  Forward-only, so rain never appears before it was transmitted,
    # and the total is conserved exactly.  This MUST mirror
    # results_final_m4_lgbm/real_utils.py::load_precip_5min — the model is trained on
    # the spread series, so it has to be served the spread series.
    n = cfg.STATION02_REPORT_STEPS
    if n > 1:
        ext = pd.date_range(
            rs.index[0],
            rs.index[-1] + (n - 1) * pd.Timedelta(freq),
            freq=freq,
        )
        rs = rs.reindex(ext, fill_value=0.0)
        rs = rs.rolling(n, min_periods=1).sum() / n
        rs.name = "prec_mm"

    # Zero-pad forward to now so past_covariates always reach the current time.
    now_rounded = now_naive.floor(freq)
    if len(rs) > 0 and rs.index[-1] < now_rounded:
        ext = pd.date_range(
            start=rs.index[-1] + pd.Timedelta(minutes=cfg.RESAMPLE_MIN),
            end=now_rounded,
            freq=freq,
        )
        rs = pd.concat([rs, pd.Series(0.0, index=ext, name=rs.name)])

    return rs


# ---------------------------------------------------------------------------
# Darts TimeSeries construction
# ---------------------------------------------------------------------------

def _to_timeseries(series: pd.Series, value_col: str) -> Optional[TimeSeries]:
    """Wrap a pandas Series into a Darts TimeSeries on the 5-min grid.

    @param series     Input Series (tz-naive, roughly 5-min spaced).
    @param value_col  Column name for the resulting TimeSeries.
    @return Darts TimeSeries, or None if the Series is empty.
    """
    freq = f"{cfg.RESAMPLE_MIN}min"
    df = series.to_frame(name=value_col)
    df = df[~df.index.duplicated(keep="last")]

    try:
        ts = TimeSeries.from_dataframe(
            df,
            value_cols=[value_col],
            freq=freq,
            fill_missing_dates=True,
        )
        return ts
    except Exception as exc:
        logger.warning("_to_timeseries: failed — %s", exc)
        return None


# ---------------------------------------------------------------------------
# Gate computation
# ---------------------------------------------------------------------------

def compute_gate(precip_series: pd.Series) -> tuple[float, bool]:
    """Compute 6-hour rolling precipitation sum and gate state.

    @param precip_series  5-min precipitation Series.
    @return Tuple (rolling_sum_mm, gate_active).
    """
    gate_cutoff = pd.Timestamp.utcnow().tz_localize(None) - pd.Timedelta(minutes=cfg.GATE_WINDOW_MIN)
    recent = precip_series[precip_series.index >= gate_cutoff]
    rolling_sum = float(recent.sum())
    gate_active = rolling_sum >= cfg.GATE_MM
    return rolling_sum, gate_active


# ---------------------------------------------------------------------------
# Alert level
# ---------------------------------------------------------------------------

def _classify_alert(preds: dict[int, float], station_id: int) -> str:
    """Map prediction values to the highest alert level triggered.

    @param preds       Dict {horizon_min: predicted_level_cm}.
    @param station_id  Station identifier (for per-station thresholds).
    @return One of 'inundacao', 'alerta', 'atencao', or 'none'.
    """
    thresh = cfg.THRESHOLDS[station_id]
    max_pred = max(v for v in preds.values() if v is not None and not np.isnan(v))

    if max_pred >= thresh["inundacao"]:
        return "inundacao"
    if max_pred >= thresh["alerta"]:
        return "alerta"
    if max_pred >= thresh["atencao"]:
        return "atencao"
    return "none"


# ---------------------------------------------------------------------------
# Main inference entry point
# ---------------------------------------------------------------------------

def run_inference(
    model: LinearRegressionModel,
    level_rows: list[dict],
    precip_rows: list[dict],
    station_id: int,
    use_merge_fallback: bool = False,
) -> Optional[dict]:
    """Run one M6 MLR prediction step for a station.

    @param model             Trained Darts LinearRegressionModel loaded from pkl.
    @param level_rows        Raw level API rows.
    @param precip_rows       Raw precip API rows for station-02.
    @param station_id        Station identifier.
    @param use_merge_fallback  If True, ignore precip_rows and load MERGE CSV.
    @return Dict with prediction results, or None if inference is not possible.
    """
    freq = f"{cfg.RESAMPLE_MIN}min"

    # ── Level ─────────────────────────────────────────────────────────────────
    lvl_ser = build_level_series(level_rows)
    if lvl_ser is None:
        logger.error("run_inference[%d]: insufficient level data — skipping", station_id)
        return None

    ts_level = _to_timeseries(lvl_ser, "level_delta_cm")
    if ts_level is None or len(ts_level) < cfg.MLR_BUFFER_STEPS:
        logger.error("run_inference[%d]: level TimeSeries too short — skipping", station_id)
        return None

    # LinearRegression cannot handle NaN in lag feature windows — fill before predict.
    df_filled = ts_level.to_dataframe().ffill().bfill()
    ts_level  = TimeSeries.from_dataframe(df_filled, freq=freq)

    # ── Precipitation ──────────────────────────────────────────────────────────
    precip_ser = build_precip_series(precip_rows, merge_fallback=use_merge_fallback)
    precip_source = "merge" if use_merge_fallback else "station02"

    ts_precip = _to_timeseries(precip_ser, "prec_mm")
    if ts_precip is None:
        logger.warning("run_inference[%d]: precip TimeSeries failed; using zeros", station_id)
        idx = lvl_ser.index
        zero_ser = pd.Series(0.0, index=idx, name="prec_mm")
        ts_precip = _to_timeseries(zero_ser, "prec_mm")

    # Fill NaN in precip as well (LinearRegression requires complete feature vectors).
    df_prec_filled = ts_precip.to_dataframe().fillna(0.0)
    ts_precip = TimeSeries.from_dataframe(df_prec_filled, freq=freq)

    # ── Prediction ────────────────────────────────────────────────────────────
    try:
        ts_pred = model.predict(
            n=cfg.OUTPUT_CHUNK_STEPS,
            series=ts_level,
            past_covariates=ts_precip,
            verbose=False,
        )
    except Exception as exc:
        logger.error("run_inference[%d]: model.predict() failed — %s", station_id, exc)
        return None

    pred_arr = ts_pred.values().flatten()   # shape (24,)

    h_preds: dict[int, float] = {}
    for h_min, step_idx in cfg.HORIZON_STEP_IDX.items():
        val = float(pred_arr[step_idx]) if step_idx < len(pred_arr) else np.nan
        h_preds[h_min] = round(val, 2)

    # ── Gate ──────────────────────────────────────────────────────────────────
    precip_rolling, gate_active = compute_gate(precip_ser)

    # ── Alert level ───────────────────────────────────────────────────────────
    raw_alert_level = _classify_alert(h_preds, station_id)
    alert_level_gated = raw_alert_level if gate_active else "none"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "station_id":      station_id,
        "timestamp":       now_utc,
        "h_pred_30":       h_preds[30],
        "h_pred_60":       h_preds[60],
        "h_pred_90":       h_preds[90],
        "h_pred_120":      h_preds[120],
        "precip_rolling":  round(precip_rolling, 3),
        "precip_source":   precip_source,
        "gate_active":     gate_active,
        "raw_alert_level": raw_alert_level,
        "alert_level":     alert_level_gated,
    }
