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
@file replay_flood_event.py
@brief Replay a past flood through two production models and compare their alarms.

Written to validate the 2026-09-12 production retrain before the live model was
replaced. The training dump ends 2026-09-09, so the 2026-09-11 flood (~97 cm on the
staff gauge) is genuinely unseen by the new model — the one event that can say
whether the retrain helps without the answer being baked into the training set.

The replay walks the event 5 minutes at a time. At every step it shows each model only
the data that existed at that instant, runs the same `model.predict(n=24)` the cron job
runs, applies that arm's thresholds, and debounces exactly like `state.py`. What comes
out is the instant each arm would have fired each level, next to the instant the river
actually crossed it.

@note The gate is recomputed against the replayed instant, not `utcnow()` as
      `inference.compute_gate` does — otherwise every historical step would be judged
      against today's rain.

@warning This reads live data from the Hostinger API. It writes nothing to the database,
         posts nothing, and never touches the served model files.

Usage:
@code
    V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3
    $V replay_flood_event.py --hours 72 --station 1
@endcode
"""

from __future__ import annotations

import argparse
import importlib
import os
import pickle
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))

MODELS = {
    "m4": {
        "prod_dir": "production",
        "cfg_module": "config_production",
        "inference_module": "inference",
        "api_module": "api_client",
        "served": "/home/ilha3d/SAPI/LightGBM_Production/models/model4_lgbm.pkl",
        "candidate": "/home/ilha3d/SAPI/LightGBM_Production/models/model4_lgbm_v2.pkl",
    },
    "m6": {
        "prod_dir": "production_m6",
        "cfg_module": "config_production_m6",
        "inference_module": "inference_m6",
        "api_module": "api_client_m6",
        "served": "/home/ilha3d/SAPI/MLR_Production/models/model6_mlr.pkl",
        "candidate": "/home/ilha3d/SAPI/MLR_Production/models/model6_mlr_v2.pkl",
    },
}
"""Where each model's production code and its two model files live."""

OLD_THRESHOLDS = {"atencao": 50, "alerta": 60, "inundacao": 75}
"""What production served until 2026-09-12 (pre-Issue #225)."""

NEW_THRESHOLDS = {"atencao": 60, "alerta": 75, "inundacao": 90}
"""Issue #225 levels, carried by the candidate arm."""

# Bound in main() once the model is known — the two production folders define modules
# with the same names and cannot both be imported into one interpreter.
api_client = None
cfg = None
inference = None
ARMS: dict = {}

RANK = {"none": 0, "atencao": 1, "alerta": 2, "inundacao": 3}


def classify(preds: dict[int, float], thresholds: dict[str, float]) -> str:
    """Return the highest alert level any horizon reaches.

    Mirrors ``inference._classify_alert`` but takes the thresholds explicitly, so the
    two arms can be scored with different levels in one process.

    @param preds      Mapping of horizon (min) to forecast level in cm.
    @param thresholds Mapping of level name to threshold in cm.
    @return One of ``inundacao``, ``alerta``, ``atencao``, ``none``.
    """
    top = max(preds.values())
    for level in ("inundacao", "alerta", "atencao"):
        if top >= thresholds[level]:
            return level
    return "none"


def observed_crossings(
    level: pd.Series, thresholds: dict[str, float]
) -> dict[str, pd.Timestamp | None]:
    """Find when the observed level first crossed each threshold upward.

    A threshold the river was *already* above when the window opened has no crossing to
    measure against: the first sample would be reported as the crossing and every lead
    time computed from it would be an artefact of where the window starts. Those are
    returned as None instead. This is not a corner case here — the river sat above the
    old 50 cm Atencao threshold for 31 % of Sep/2026, which is why Issue #225 moved it.

    @param level      Observed 5-min level Series.
    @param thresholds Mapping of level name to threshold in cm.
    @return Mapping of level name to first crossing timestamp, or None when the level
            never crossed it or was already above it at the first sample.
    """
    out: dict[str, pd.Timestamp | None] = {}
    for name, thr in thresholds.items():
        above = level[level >= thr]
        if not len(above):
            out[name] = None
        elif above.index[0] == level.index[0]:
            out[name] = None  # already above when the window opened
        else:
            out[name] = above.index[0]
    return out


def run_arm(
    name: str, spec: dict, ts_level, ts_precip, precip_ser, steps
) -> pd.DataFrame:
    """Replay one arm over the event and record its debounced alarm state.

    @param name       Arm label used in the output.
    @param spec       Arm definition: ``pkl`` path and ``thresholds``.
    @param ts_level   Full level TimeSeries for the window.
    @param ts_precip  Full precipitation TimeSeries for the window.
    @param precip_ser Same precipitation as a pandas Series, for the gate.
    @param steps      Timestamps to evaluate, in order.
    @return One row per step: forecasts, gate, raw and debounced alert level.
    """
    with open(spec["pkl"], "rb") as fh:
        model = pickle.load(fh)

    gate_window = pd.Timedelta(minutes=cfg.GATE_WINDOW_MIN)
    rows = []
    consecutive = 0
    debounced = "none"
    prev_gated = "none"

    for t in steps:
        # slice() keeps [start, t] inclusive; drop_after() would refuse the last step
        # because t + one step falls outside the series.
        hist = ts_level.slice(ts_level.start_time(), t)
        buffer_steps = getattr(cfg, "LGBM_BUFFER_STEPS", None) or cfg.MLR_BUFFER_STEPS
        if len(hist) < buffer_steps + 1:
            continue
        cov = ts_precip.slice(ts_precip.start_time(), t)

        try:
            pred = model.predict(
                n=cfg.OUTPUT_CHUNK_STEPS,
                series=hist,
                past_covariates=cov,
                verbose=False,
            )
        except (
            Exception
        ) as exc:  # a step the model cannot serve is a real-world outcome
            rows.append({"timestamp": t, "arm": name, "error": str(exc)[:80]})
            continue

        arr = pred.values().flatten()
        preds = {h: float(arr[i]) for h, i in cfg.HORIZON_STEP_IDX.items()}

        window = precip_ser[
            (precip_ser.index > t - gate_window) & (precip_ser.index <= t)
        ]
        rolling = float(window.sum())
        gate = rolling >= cfg.GATE_MM

        raw = classify(preds, spec["thresholds"])
        gated = raw if gate else "none"

        # Debounce, matching state.py: a level must hold for DEBOUNCE_STEPS steps
        # before it is acted on. `prev_gated` is the previous step's gated level.
        if gated == "none":
            consecutive = 0
            debounced = "none"
        elif gated == prev_gated:
            consecutive += 1
        else:
            consecutive = 1
        if gated != "none" and consecutive >= cfg.DEBOUNCE_STEPS:
            debounced = gated
        prev_gated = gated

        rows.append(
            {
                "timestamp": t,
                "arm": name,
                "h_pred_30": round(preds[30], 2),
                "h_pred_60": round(preds[60], 2),
                "h_pred_90": round(preds[90], 2),
                "h_pred_120": round(preds[120], 2),
                "precip_6h": round(rolling, 2),
                "gate": gate,
                "raw": raw,
                "gated": gated,
                "debounced": debounced,
            }
        )

    return pd.DataFrame(rows)


def first_fire(df: pd.DataFrame, level: str) -> pd.Timestamp | None:
    """Return the first instant the debounced state reached a level.

    @param df    Replay rows for one arm.
    @param level Level name to look for.
    @return Timestamp, or None if the arm never reached it.
    """
    if "debounced" not in df.columns:
        return None
    hit = df[df["debounced"].map(lambda v: RANK.get(v, 0)) >= RANK[level]]
    return hit["timestamp"].iloc[0] if len(hit) else None


def main() -> int:
    """Fetch the window, replay both arms and print the comparison.

    @return 0 on success.
    """
    global api_client, cfg, inference, ARMS

    ap = argparse.ArgumentParser(
        description="Replay a flood through old and new models"
    )
    ap.add_argument("--hours", type=int, default=72, help="Lookback window to fetch.")
    ap.add_argument("--station", type=int, default=1, choices=[1, 3])
    ap.add_argument("--model", default="m4", choices=sorted(MODELS))
    ap.add_argument("--out", default=None, help="Write the per-step CSV here.")
    args = ap.parse_args()

    spec = MODELS[args.model]
    sys.path.insert(0, os.path.join(_HERE, spec["prod_dir"]))
    api_client = importlib.import_module(spec["api_module"])
    cfg = importlib.import_module(spec["cfg_module"])
    inference = importlib.import_module(spec["inference_module"])
    ARMS = {
        "antiga": {"pkl": spec["served"], "thresholds": OLD_THRESHOLDS},
        "nova": {"pkl": spec["candidate"], "thresholds": NEW_THRESHOLDS},
    }

    print(
        f"=== Replay {args.model.upper()}: station {args.station}, "
        f"last {args.hours} h ==="
    )

    level_rows = api_client.fetch_data(args.station, "level", args.hours)
    precip_rows = api_client.fetch_data(2, "precip", args.hours)
    print(f"  Fetched {len(level_rows)} level rows, {len(precip_rows)} precip rows")
    if not level_rows:
        print("  FAIL: no level data returned by the API.")
        return 1

    lvl_ser = inference.build_level_series(level_rows)
    precip_ser = inference.build_precip_series(precip_rows)
    ts_level = inference._to_timeseries(lvl_ser, "level_delta_cm")
    ts_precip = inference._to_timeseries(precip_ser, "prec_mm")
    if ts_level is None or ts_precip is None:
        print("  FAIL: could not build the series.")
        return 1

    print(f"  Level window : {lvl_ser.index[0]} -> {lvl_ser.index[-1]}")
    print(f"  Peak observed: {lvl_ser.max():.1f} cm at {lvl_ser.idxmax()}")
    print(f"  Rain total   : {precip_ser.sum():.1f} mm")

    buffer_steps = getattr(cfg, "LGBM_BUFFER_STEPS", None) or cfg.MLR_BUFFER_STEPS
    warmup = buffer_steps + 1
    steps = list(lvl_ser.index[warmup:])
    print(f"  Replaying {len(steps)} steps of 5 min ...\n")

    frames = []
    for name, spec in ARMS.items():
        if not os.path.exists(spec["pkl"]):
            print(f"  SKIP {name}: {spec['pkl']} not found")
            continue
        print(
            f"  [{name}] model {os.path.basename(spec['pkl'])}  thresholds "
            f"{spec['thresholds']['atencao']}/{spec['thresholds']['alerta']}/"
            f"{spec['thresholds']['inundacao']} cm"
        )
        frames.append(run_arm(name, spec, ts_level, ts_precip, precip_ser, steps))

    result = pd.concat(frames, ignore_index=True)
    out = args.out or os.path.join(_HERE, f"output_replay_flood_{args.model}.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    result.to_csv(out, index=False)
    print(f"\n  Per-step CSV : {out}")

    print("\n=== When each arm would have fired, vs the river ===")
    header = f"{'level':<11} {'observed crossing':<21}"
    for name in ARMS:
        header += f" {name + ' fired':<21} {'lead':<9}"
    print(header)

    for lvl in ("atencao", "alerta", "inundacao"):
        line = f"{lvl:<11}"
        obs_by_arm = {}
        for name, spec in ARMS.items():
            obs_by_arm[name] = observed_crossings(lvl_ser, spec["thresholds"]).get(lvl)
        # The two arms use different thresholds, so each has its own observed crossing.
        shown = obs_by_arm.get("nova") or obs_by_arm.get("antiga")
        line += f" {str(shown) if shown is not None else 'sem cruzamento':<21}"
        for name in ARMS:
            sub = result[result["arm"] == name]
            fired = first_fire(sub, lvl)
            obs = obs_by_arm[name]
            line += f" {str(fired) if fired is not None else '—':<21}"
            if fired is not None and obs is not None:
                mins = int((obs - fired).total_seconds() // 60)
                line += f" {str(f'{mins:+d} min'):<9}"
            elif fired is not None and obs is None:
                line += f" {'n/a':<9}"  # already above at window start: nothing to time
            else:
                line += f" {'—':<9}"
        print(line)

    print(
        "\n  Positive lead = alarm before the river crossed that arm's own threshold."
    )
    print(
        "  Each arm is scored against its own thresholds (old 50/60/75, new 60/75/90)."
    )

    for name in ARMS:
        sub = result[result["arm"] == name]
        if "h_pred_120" not in sub.columns or sub.empty:
            continue
        print(
            f"\n  [{name}] max forecast: +30 {sub['h_pred_30'].max():.1f} | "
            f"+60 {sub['h_pred_60'].max():.1f} | +90 {sub['h_pred_90'].max():.1f} | "
            f"+120 {sub['h_pred_120'].max():.1f} cm"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
