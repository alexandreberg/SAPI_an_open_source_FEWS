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
@file train_production_from_backtest.py
@brief Train the production M4/M6 models using the validated backtest code path.

The production folders (``production/``, ``production_m6/``) each carry their own
re-implementation of the preprocessing pipeline, and both have drifted away from the
reference implementation in ``results_final_m4_lgbm/`` and ``results_final_m6_mlr/``.
As of 2026-09-12 they still lacked all five corrections that define the current
results: continuous training (Issue #223), thresholds 60/75/90 (Issue #225), sensor
artifact exclusion (Issue #227), the Station-02 rain spread (Issue #124) and the
per-occurrence lead-time rule (Issue #229).

Rather than porting five fixes into two duplicated trainers — creating a third copy
that would drift again — this script trains the deployed model with the **same code
that produced the numbers published in the dissertation**. It imports ``config`` and
``real_utils`` from the chosen backtest folder, calls exactly the same functions, and
only writes out the serialized model plus a provenance sidecar.

Two deliberate differences from the backtest run:

1. ``TRAIN_END`` is pushed past the end of the record, so the deployed model is fitted
   on **all** available data. The chronological hold-out exists to *evaluate*; once the
   evaluation is done, the deployed model should use every sample. This means the
   published out-of-sample metrics describe a model trained to 2026-05-01, while the
   deployed model has seen more — the metrics are a conservative floor, not a
   description of the exact deployed weights. Say so when asked.
2. Nothing is predicted or plotted. Only ``fit()`` runs.

The override is applied to the imported module at runtime, so the backtest
``config.py`` keeps ``TRAIN_END = 2026-05-01`` for the dissertation.

@warning Do not point the training precipitation source at ``merge_precip.csv``. That
         file is rewritten daily by ``refresh_merge_csv.py`` and holds roughly six days
         of history; the frozen historical dump is ``merge_20260404.csv``, which is what
         the backtest config already uses. See the module docstring of
         ``production/refresh_merge_csv.py``.

Usage:
@code
    V=/home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3
    $V train_production_from_backtest.py --model m6     # ~5 min
    $V train_production_from_backtest.py --model m4     # ~25 min
@endcode

The model is written to a **staging** path (``*_v2.pkl``) and never overwrites the file
currently being served. Promotion is a separate, manual rename.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import pickle
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODELS = {
    "m4": {
        "backtest_dir": "results_final_m4_lgbm",
        "out_pkl": "/home/ilha3d/SAPI/LightGBM_Production/models/model4_lgbm_v2.pkl",
        "label": "M4 LightGBM",
    },
    "m6": {
        "backtest_dir": "results_final_m6_mlr",
        "out_pkl": "/home/ilha3d/SAPI/MLR_Production/models/model6_mlr_v2.pkl",
        "label": "M6 MLR",
    },
}
"""Per-model backtest source folder and staging output path."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_backtest_modules(backtest_dir: str):
    """Import ``config`` and ``real_utils`` from one backtest folder.

    Both backtest folders define modules with the same names, so only the chosen
    folder is placed on ``sys.path`` — importing both in one process would collide.

    @param backtest_dir Folder name under this script's directory, e.g.
           ``results_final_m4_lgbm``.
    @return Tuple of (config module, real_utils module).
    """
    path = os.path.join(_HERE, backtest_dir)
    if not os.path.isdir(path):
        raise SystemExit(f"Backtest folder not found: {path}")
    sys.path.insert(0, path)
    config = importlib.import_module("config")
    real_utils = importlib.import_module("real_utils")
    return config, real_utils


def build_model(model_key: str, config):
    """Instantiate the untrained model with the backtest hyper-parameters.

    Mirrors ``build_model()`` in ``01_model4_continuous.py`` /
    ``01_model6_mlr_continuous.py`` exactly — same lags, same output chunk, same seed.

    @param model_key Either ``m4`` or ``m6``.
    @param config    The backtest config module already imported.
    @return Configured but untrained Darts model.
    """
    if model_key == "m4":
        from darts.models import LightGBMModel

        return LightGBMModel(
            lags=config.LGBM_LAGS,
            lags_past_covariates=config.LGBM_PRECIP_LAGS,
            output_chunk_length=config.OUTPUT_CHUNK_STEPS,
            n_estimators=config.LGBM_N_ESTIMATORS,
            num_leaves=config.LGBM_NUM_LEAVES,
            random_state=config.RANDOM_STATE,
            verbose=-1,
        )

    from darts.models import LinearRegressionModel

    return LinearRegressionModel(
        lags=config.MLR_LAGS,
        lags_past_covariates=config.MLR_PRECIP_LAGS,
        output_chunk_length=config.OUTPUT_CHUNK_STEPS,
        fit_intercept=True,
        random_state=config.RANDOM_STATE,
    )


def sha256_of(path: str) -> dict:
    """Hash one input file so the trained model can be traced back to its data.

    @param path Absolute path to the file.
    @return Dict with size, mtime and sha256, or an ``error`` key if unreadable.
    """
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        st = os.stat(path)
        return {
            "path": path,
            "bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
            "sha256": h.hexdigest(),
        }
    except OSError as exc:
        return {"path": path, "error": str(exc)}


def package_versions() -> dict:
    """Record the versions of every library that affects the fitted model.

    @return Mapping of package name to version string (``"?"`` when absent).
    """
    from importlib.metadata import PackageNotFoundError, version

    out = {"python": sys.version.split()[0]}
    for pkg in ("darts", "lightgbm", "scikit-learn", "pandas", "numpy"):
        try:
            out[pkg] = version(pkg)
        except PackageNotFoundError:
            out[pkg] = "?"
    return out


def git_commit() -> str:
    """Return the repo commit this model was trained from.

    @return Short commit hash, with ``-dirty`` appended if the tree has changes,
            or ``"unknown"`` when git is unavailable.
    """
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=_HERE, text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=_HERE, text=True
        ).strip()
        return f"{rev}-dirty" if dirty else rev
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Train one production model and write it to its staging path.

    @return Process exit code (0 on success).
    """
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument(
        "--train-end",
        default="2026-09-10",
        help=(
            "Cut applied to config.TRAIN_END at runtime. The default sits past the end "
            "of the 2026-09-09 dump, so the whole record is used. The backtest config "
            "file is never modified."
        ),
    )
    ap.add_argument("--out", default=None, help="Override the output .pkl path.")
    args = ap.parse_args()

    spec = MODELS[args.model]
    out_pkl = args.out or spec["out_pkl"]
    meta_path = os.path.splitext(out_pkl)[0] + ".meta.json"

    print(f"=== Training {spec['label']} for production ===")
    print(f"  Backtest source : {spec['backtest_dir']}")

    config, real_utils = load_backtest_modules(spec["backtest_dir"])

    if config.TRAIN_MODE != "continuous":
        raise SystemExit(
            f"config.TRAIN_MODE is {config.TRAIN_MODE!r}, expected 'continuous'. "
            "Training on event windows only is the Issue #223 bias — refusing."
        )

    train_end_before = config.TRAIN_END
    config.TRAIN_END = pd.Timestamp(args.train_end)
    print(
        f"  TRAIN_END       : {train_end_before} -> {config.TRAIN_END} (runtime override)"
    )
    print(
        f"  Thresholds      : {config.THRESHOLD_ATENCAO}/"
        f"{config.THRESHOLD_ALERTA}/{config.THRESHOLD_INUNDACAO} cm"
    )

    # ── 1. Data ──────────────────────────────────────────────────────────────
    print(
        "\n[1/3] Loading data (3-pass filtered level, spliced rain, artifacts masked) ..."
    )
    ts_level, ts_precip, df_events = real_utils.load_real_data()
    # load_event_catalogue() already drops the excluded rows, so df_events cannot be
    # counted for this — ask real_utils for the windows it actually masked.
    artifact_windows = real_utils.load_artifact_windows()
    print(f"  Level steps     : {len(ts_level):,}")
    print(f"  Level range     : {ts_level.start_time()} -> {ts_level.end_time()}")
    print(
        f"  Catalogue       : {len(df_events)} valid rows, "
        f"{len(artifact_windows)} artifact windows masked out of the level series"
    )

    # ── 2. Continuous training segments ──────────────────────────────────────
    print("\n[2/3] Building continuous training segments (Issue #223) ...")
    ts_train, pc_train = real_utils.build_continuous_training_segment(
        ts_level, ts_precip
    )
    if not ts_train:
        raise SystemExit("No valid training segments — aborting.")
    total_steps = sum(len(s) for s in ts_train)
    print(
        f"  {len(ts_train)} segment(s)  |  {total_steps:,} steps  |  "
        f"lengths {min(len(s) for s in ts_train)}-{max(len(s) for s in ts_train)}"
    )

    # ── 3. Fit and serialize ─────────────────────────────────────────────────
    print(f"\n[3/3] Fitting {spec['label']} ...")
    model = build_model(args.model, config)
    model.fit(ts_train, past_covariates=pc_train)
    print("  Training complete.")

    os.makedirs(os.path.dirname(out_pkl), exist_ok=True)
    with open(out_pkl, "wb") as fh:
        pickle.dump(model, fh)
    print(f"  Model written   : {out_pkl} ({os.path.getsize(out_pkl):,} bytes)")

    meta = {
        "model": spec["label"],
        "model_key": args.model,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "trained_by": "train_production_from_backtest.py",
        "backtest_source": spec["backtest_dir"],
        "git_commit": git_commit(),
        "train_end_effective": str(config.TRAIN_END),
        "train_end_backtest": str(train_end_before),
        "train_mode": config.TRAIN_MODE,
        "n_segments": len(ts_train),
        "n_steps": int(total_steps),
        "level_range": [str(ts_level.start_time()), str(ts_level.end_time())],
        "artifact_windows_masked": len(artifact_windows),
        "thresholds_cm": {
            "atencao": config.THRESHOLD_ATENCAO,
            "alerta": config.THRESHOLD_ALERTA,
            "inundacao": config.THRESHOLD_INUNDACAO,
        },
        "precip": {
            "cutoff": str(config.PRECIP_CUTOFF),
            "merge_scale": config.PRECIP_MERGE_SCALE,
            "station02_report_steps": config.STATION02_REPORT_STEPS,
        },
        "hyperparameters": {
            "lags": config.LGBM_LAGS if args.model == "m4" else config.MLR_LAGS,
            "lags_past_covariates": (
                config.LGBM_PRECIP_LAGS
                if args.model == "m4"
                else config.MLR_PRECIP_LAGS
            ),
            "output_chunk_length": config.OUTPUT_CHUNK_STEPS,
            "random_state": config.RANDOM_STATE,
            **(
                {
                    "n_estimators": config.LGBM_N_ESTIMATORS,
                    "num_leaves": config.LGBM_NUM_LEAVES,
                }
                if args.model == "m4"
                else {"fit_intercept": True}
            ),
        },
        "inputs": {
            "level": sha256_of(config.LEVEL_CSV),
            "merge": sha256_of(config.MERGE_CSV),
            "station02": sha256_of(config.STATION02_CSV),
            "events": sha256_of(config.EVENTS_CSV),
        },
        "versions": package_versions(),
    }
    with open(meta_path, "w") as fh:
        json.dump(meta, fh, indent=2)
    print(f"  Provenance      : {meta_path}")

    print(
        "\nStaging only — the served model was NOT replaced. Promote with an explicit "
        "rename after the validation replay passes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
