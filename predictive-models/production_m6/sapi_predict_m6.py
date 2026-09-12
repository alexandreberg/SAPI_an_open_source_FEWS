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
@file sapi_predict_m6.py
@brief Cron entry point for the SAPI real-time M6 MLR prediction pipeline (Issue #120).

Runs every 5 minutes in parallel with the M4 LightGBM cron (sapi_predict.py).
Offset by 2 min to avoid simultaneous API calls hitting Hostinger at the same instant.

Cron entry (add to crontab -e on RPi):
    */5 * * * * sleep 120 && /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \\
        /home/ilha3d/SAPI/MLR_Production/sapi_predict_m6.py \\
        >> /home/ilha3d/SAPI/MLR_Production/logs/sapi_predict_m6.log 2>&1

Venv: shared with M4 (/home/ilha3d/SAPI/LightGBM_Production/.venv).
      LinearRegressionModel is part of darts[ml] already installed there.

The script is self-contained: it loads the M6 model from disk, fetches live data
from the Hostinger API, runs inference for Station-01 and Station-03, applies
the precipitation gate + debounce, posts results to predictions_m6.php, and
updates the last-run log.  Exits with code 0 on full success or 1 if any station fails.

Isolation: no imports from LightGBM_Production or any M4-specific module.
"""

import base64
import logging
import os
import pickle
import sys
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore", message="X does not have valid feature names", category=UserWarning)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import config_production_m6 as cfg
import api_client_m6       as api_client
import inference_m6        as inference
import state_m6            as state_mod
import telegram_notifier_m6 as telegram_notifier

from darts.models import LinearRegressionModel

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    """Configure root logger to emit timestamped lines to stdout.

    @return None
    """
    fmt = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")


logger = logging.getLogger("sapi_predict_m6")


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_model() -> LinearRegressionModel:
    """Load the serialised LinearRegressionModel from disk.

    @return Loaded Darts LinearRegressionModel.
    @raises FileNotFoundError  If the pkl file does not exist.
    @raises RuntimeError       If the file cannot be unpickled.
    """
    path = cfg.MODEL_PATH
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"M6 model not found: {path}\n"
            "Run train_production_model_m6.py first."
        )

    try:
        with open(path, "rb") as f:
            model = pickle.load(f)
        logger.info("M6 model loaded from %s", path)
        return model
    except Exception as exc:
        raise RuntimeError(f"Failed to load M6 model from {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Last-run log
# ---------------------------------------------------------------------------

def write_last_run_log(results: list[dict]) -> None:
    """Write a human-readable summary of this M6 run to ultima_predicao_m6.log.

    Overwritten on each run so it always reflects the most recent state.

    @param results  List of result dicts returned by inference.run_inference().
    """
    path = cfg.LOG_LAST_PRED
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines = [
        f"=== SAPI M6 MLR Última Predição — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC ===",
        "",
    ]
    for r in results:
        if r is None:
            lines.append("  [ERRO] resultado None para esta estação")
            continue
        lines += [
            f"  Estação {r['station_id']}",
            f"    Timestamp     : {r['timestamp']}",
            f"    h_pred_30     : {r['h_pred_30']:.1f} cm",
            f"    h_pred_60     : {r['h_pred_60']:.1f} cm",
            f"    h_pred_90     : {r['h_pred_90']:.1f} cm",
            f"    h_pred_120    : {r['h_pred_120']:.1f} cm",
            f"    Precip 6h     : {r['precip_rolling']:.2f} mm  ({r['precip_source']})",
            f"    Gate ativo    : {'SIM' if r['gate_active'] else 'NÃO'}",
            f"    Nível bruto   : {r['raw_alert_level']}",
            f"    Nível alerta  : {r.get('alert_level', '?')}",
            f"    Debounce steps: {r.get('consecutive_steps', '?')}",
            "",
        ]

    with open(path, "w") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Per-station processing
# ---------------------------------------------------------------------------

def process_station(
    station_id: int,
    model: LinearRegressionModel,
    debounce_state: dict,
) -> dict | None:
    """Fetch data, run M6 inference, apply debounce, and POST result for one station.

    @param station_id      Station identifier (1 or 3).
    @param model           Loaded LinearRegressionModel.
    @param debounce_state  Mutable full state dict (updated in place).
    @return Enriched result dict or None if inference failed.
    """
    logger.info("--- M6 Station %d ---", station_id)

    level_rows = api_client.fetch_data(station_id, "level", cfg.LEVEL_FETCH_HOURS)
    logger.info("  Level rows fetched: %d", len(level_rows))

    precip_rows = api_client.fetch_data(2, "precip", cfg.PRECIP_FETCH_HOURS)
    use_merge   = len(precip_rows) < cfg.MIN_PRECIP_ROWS

    if use_merge:
        logger.warning("  Station-02 returned only %d rows → falling back to MERGE CSV",
                       len(precip_rows))
    else:
        logger.info("  Precip rows fetched: %d (Station-02)", len(precip_rows))

    result = inference.run_inference(
        model=model,
        level_rows=level_rows,
        precip_rows=precip_rows,
        station_id=station_id,
        use_merge_fallback=use_merge,
    )

    if result is None:
        logger.error("  M6 Inference failed for station %d — skipping POST", station_id)
        return None

    logger.info(
        "  M6 Predictions (cm): +30=%.1f +60=%.1f +90=%.1f +120=%.1f",
        result["h_pred_30"], result["h_pred_60"],
        result["h_pred_90"], result["h_pred_120"],
    )
    logger.info(
        "  Gate: %.2f mm  active=%s  raw_level=%s",
        result["precip_rolling"], result["gate_active"], result["raw_alert_level"],
    )

    fired, cleared, debounced_level, consecutive = state_mod.update(
        state=debounce_state,
        station_id=station_id,
        gated_alert_level=result["alert_level"],
    )

    result["alert_level"]       = debounced_level
    result["consecutive_steps"] = consecutive

    if fired:
        logger.warning("  *** M6 ALERTA DISPARADO: %s (estação %d) ***", debounced_level, station_id)
    elif cleared:
        logger.info("  M6 Alert cleared for station %d", station_id)
    else:
        logger.info("  M6 Debounced level: %s  (steps=%d/%d)",
                    debounced_level, consecutive, cfg.DEBOUNCE_STEPS)

    chart_b64: str | None = None
    if fired or cleared:
        try:
            img_bytes = telegram_notifier.notify_alert(
                result=result,
                level_rows=level_rows,
                station_id=station_id,
                fired=fired,
                cleared=cleared,
            )
            if img_bytes:
                chart_b64 = base64.b64encode(img_bytes).decode("ascii")
        except Exception as exc:
            logger.error("  Telegram/chart error: %s", exc)

    payload = dict(result)
    payload["alert_transition"] = (
        "fired"   if fired   else
        "cleared" if cleared else
        "none"
    )
    if chart_b64:
        payload["chart_b64"] = chart_b64

    ok = api_client.post_result(payload)
    if ok:
        logger.info("  M6 POST OK")
    else:
        logger.warning("  M6 POST FAILED — result not stored in DB this run")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Run one M6 MLR prediction cycle for all configured stations.

    @return Exit code: 0 = all stations succeeded, 1 = at least one failed.
    """
    _setup_logging()
    run_start = datetime.now(timezone.utc)
    logger.info("=== sapi_predict_m6 start %s ===", run_start.strftime("%Y-%m-%d %H:%M:%S UTC"))

    os.makedirs(os.path.join(cfg.PRODUCTION_DIR, "logs"), exist_ok=True)

    try:
        model = load_model()
    except (FileNotFoundError, RuntimeError) as exc:
        logger.critical("Cannot load M6 model: %s", exc)
        return 1

    debounce_state = state_mod.load_state()

    results   = []
    any_error = False

    for station_id in cfg.STATIONS:
        try:
            r = process_station(station_id, model, debounce_state)
            results.append(r)
            if r is None:
                any_error = True
        except Exception as exc:
            logger.exception("Unhandled error for station %d: %s", station_id, exc)
            results.append(None)
            any_error = True

    state_mod.save_state(debounce_state)
    write_last_run_log(results)

    elapsed = (datetime.now(timezone.utc) - run_start).total_seconds()
    logger.info("=== sapi_predict_m6 done in %.1f s ===", elapsed)

    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
