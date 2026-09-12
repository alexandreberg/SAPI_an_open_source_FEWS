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
@file test_precip_parity.py
@brief Assert the served rain series equals the trained rain series (Issue #124).

The models are trained on a Station-02 series where each 15-min report is spread over
three 5-min steps, and they must be *served* the same shape. Training builds that series
in ``results_final_*/real_utils.py::load_precip_5min``; production builds it in
``inference.py`` / ``inference_m6.py``. These are four separate implementations in four
folders with no shared module, so nothing but this test stops them from drifting apart —
and a drift here is silent: the pipeline keeps running and merely forecasts worse.

Both models are checked, because the M4/M6 pair has drifted apart before: the Issue #160
fix was merged in the repo and never reached the deployed copies (Issue #174).

The check replays real Station-02 rows through the production path and compares against
the training loader over the same window.

@note The first ``STATION02_REPORT_STEPS - 1`` steps of the window are excluded from the
      comparison by design. The rolling spread needs that much history, and the live
      pipeline has it (it fetches ``PRECIP_FETCH_HOURS`` of rows) while a window sliced
      out of the middle of the record does not.

Usage:
@code
    V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3
    $V production/test_precip_parity.py              # both models
    $V production/test_precip_parity.py --model m4   # one of them
@endcode
"""

from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_DARTS_ROOT = os.path.dirname(_HERE)

TARGETS = {
    "m4": {
        "backtest_dir": "results_final_m4_lgbm",
        "prod_dir": os.path.join(_DARTS_ROOT, "production"),
        "cfg_module": "config_production",
        "inference_module": "inference",
    },
    "m6": {
        "backtest_dir": "results_final_m6_mlr",
        "prod_dir": os.path.join(_DARTS_ROOT, "production_m6"),
        "cfg_module": "config_production_m6",
        "inference_module": "inference_m6",
    },
}
"""Where each model's training and serving implementation of the rain series lives."""

# The rainiest stretch of the record covered by Station-02: the E35 flood (101 cm,
# peak 2026-09-01 02:20). A window with real rain is the only one that can expose a
# spread bug — a dry window compares zeros against zeros.
WINDOW_START = pd.Timestamp("2026-08-30 00:00:00")
WINDOW_END = pd.Timestamp("2026-09-02 00:00:00")

TOLERANCE_MM = 1e-9
"""Both paths do the same float arithmetic, so anything above rounding noise is a bug."""


def check(model_key: str) -> bool:
    """Compare the training and serving rain series for one model.

    @param model_key Either ``m4`` or ``m6``.
    @return True when the two series match within tolerance.
    """
    spec = TARGETS[model_key]

    sys.path.insert(0, os.path.join(_DARTS_ROOT, spec["backtest_dir"]))
    real_utils = importlib.import_module("real_utils")
    reference = real_utils.load_precip_5min().loc[WINDOW_START:WINDOW_END, "prec_mm"]

    sys.path.insert(0, spec["prod_dir"])
    cfg = importlib.import_module(spec["cfg_module"])
    inference = importlib.import_module(spec["inference_module"])

    raw = pd.read_csv(cfg.STATION02_CSV, parse_dates=["timestamp"])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True).dt.tz_localize(None)
    raw = raw[(raw["timestamp"] >= WINDOW_START) & (raw["timestamp"] <= WINDOW_END)]
    rows = [
        {"timestamp": ts.isoformat(), "value": val}
        for ts, val in zip(raw["timestamp"], raw["precipitation_mm"])
    ]
    served = inference.build_precip_series(rows).loc[WINDOW_START:WINDOW_END]

    skip = cfg.STATION02_REPORT_STEPS - 1
    common = reference.index.intersection(served.index)
    if len(common) == 0:
        print(f"  [{model_key}] FAIL: the two series share no timestamps at all.")
        return False
    common = common[skip:]

    ref = reference.reindex(common)
    ser = served.reindex(common)
    diff = (ref - ser).abs()

    print(f"  [{model_key}] steps {len(common):,} (first {skip} skipped: warm-up)")
    print(
        f"  [{model_key}] rain  training {ref.sum():.4f} mm | served {ser.sum():.4f} mm"
    )
    print(f"  [{model_key}] max |difference| {diff.max():.3e} mm")

    if ref.sum() <= 0:
        print(f"  [{model_key}] FAIL: window carries no rain — it proves nothing.")
        return False

    if diff.max() > TOLERANCE_MM:
        worst = diff.idxmax()
        print(
            f"  [{model_key}] FAIL: diverge at {worst} — "
            f"training {ref.loc[worst]:.6f} mm vs served {ser.loc[worst]:.6f} mm "
            f"({int((diff > TOLERANCE_MM).sum())} of {len(common)} steps differ)"
        )
        return False

    print(f"  [{model_key}] PASS: served series is identical to the trained one.")
    return True


def main() -> int:
    """Run the parity check for the requested model(s).

    @return 0 when every checked model passes, 1 otherwise.
    """
    ap = argparse.ArgumentParser(
        description="Station-02 rain parity check (Issue #124)"
    )
    ap.add_argument("--model", choices=sorted(TARGETS), default=None)
    args = ap.parse_args()

    if args.model:
        return 0 if check(args.model) else 1

    print("=== Station-02 rain parity: training vs production (Issue #124) ===")
    print(f"  Window: {WINDOW_START} -> {WINDOW_END}")

    # One interpreter per model: both backtest folders define modules named `config`
    # and `real_utils`, so importing them in the same process would collide.
    ok = True
    for key in sorted(TARGETS):
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--model", key],
            capture_output=True,
            text=True,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("  ["):
                print(line)
        if proc.returncode != 0:
            ok = False
            if proc.stderr.strip():
                print(f"  [{key}] stderr: {proc.stderr.strip().splitlines()[-1]}")

    print("\n  ALL PASS" if ok else "\n  FAILURES ABOVE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
