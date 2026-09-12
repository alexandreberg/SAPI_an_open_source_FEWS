# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024-2026 Alexandre Nuernberg <alexandreberg@gmail.com>
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
@file reprocess_level_spike_return_filter.py
@brief Offline reprocessing of Station-01 raw level_cm into a corrected
       level_delta_cm series for M4/M6 training and evaluation (Issue #211).

Context: both existing delta filters in this codebase reject a reading purely
by MAGNITUDE of the step change:
  - App/webserver/cron/filter_level.php (production): elastic window, rejects
    if |v - lastAccepted| > maxDelta(5.0 cm/min) x elapsed_minutes.
  - real_utils.py's apply_delta_filter (offline, second pass on top of the
    already-filtered level_delta_cm): flat 40cm cutoff from the last accepted
    value, not elapsed-time-scaled.
A confirmed echo-reflection artifact on Station-01 (HC-SR04) deviates only
~15-25cm for ~4 consecutive readings in each direction (~76-90s cadence)
before reverting. At that magnitude, the production elastic window only needs
~4-5 minutes of elapsed time (5cm/min x ~4-5min = ~20-25cm) to admit it, and
it is comfortably under the offline filter's flat 40cm ceiling too — neither
existing filter can catch it by magnitude alone. This contaminated the
catalogued Events 14 and 20 used in the M4/M6 dissertation backtests (see
Documentation/predictive_model/auditoria_lead_time_rmse_20eventos.md).

A real flood rise and a sensor echo of the same magnitude are indistinguishable
by a single step's size. What differs is what happens next: a genuine rise
does not revert back to the pre-rise baseline within a few minutes, while an
echo artifact does. This script exploits that a full historical dataset can be
inspected non-causally (unlike the live production filter, which can only see
the past): once a reading deviates from a trusted baseline by more than
SPIKE_TRIGGER_CM, it looks ahead (bounded by MAX_BUFFER_MIN) for the series to
return within RETURN_TOLERANCE_CM of that baseline. If it returns -> the whole
excursion is rejected as a transient artifact. If it does not return before
the timeout -> the excursion is accepted as a genuine, sustained change.

THREE-PASS DESIGN (why): starting this reprocessing from level_delta_cm (the
already production-filtered column) would inherit Issue #211's contamination
at its source, so this script starts from fully raw level_cm instead. But an
early, from-scratch attempt to run only a NEW look-ahead filter directly on
raw level_cm (skipping the production elastic filter's job entirely) either
missed the confirmed echo (too loose) or, once tightened enough to catch it,
turned a handful of genuinely noisy hours during the extreme/flash-flood
events (E8, E9) into 90-100% data loss — a single look-ahead buffer's "trusted
anchor" got poisoned by a not-yet-confirmed spurious reading, and every
subsequent GENUINE reading (now far from that bad anchor) was rejected
forever, deadlocking the buffer's own timeout resolution. The production
elastic filter's OWN pass over this same noise, already validated by every
one of the 20 catalogued events matching their published peak, has clearly
been doing real, non-trivial work that a single new filter stage was not
replicating. So this script chains three independent, narrowly-scoped passes
instead of trying to replace that work with one clever pass:

  Pass 0 (production_elastic_filter): a faithful Python port of
  filter_level.php's own elastic-window algorithm, run from scratch over the
  full raw level_cm history (this script does not touch the live DB or PHP
  filter — see the module's Usage section). Validated against the dump's own
  level_delta_cm column (what production itself already computed) before
  trusting it further — see main()'s agreement check.

  Pass 1 (real_utils.apply_delta_filter): the existing, already-validated
  flat 40cm single-last-accepted-value filter, run on Pass 0's output exactly
  as it already runs on level_delta_cm today. Unchanged.

  Pass 2 (_spike_return_pass2): the new look-ahead filter, run ONLY on
  readings Pass 0+1 already accepted. Because Pass 1 guarantees every
  consecutive accepted pair differs by at most 40cm, Pass 2 never needs a
  magnitude gate at all — it only ever decides, for a step bigger than
  SPIKE_TRIGGER_CM, whether the series reverts (reject) or sustains (accept).
  This is what catches the Issue #211 echo that Pass 0+1 already let through
  (its deviation is comfortably under both of their thresholds).

This methodology (Pass 2 specifically) is intended to be reusable in
production later (per user direction 2026-09-09), but that port is separate
future work — this script only fixes the offline training/test dataset used
for the dissertation's 20 catalogued events, and does not modify
filter_level.php, the production database, or any deployed pipeline.

Usage:
    cd AppTest/raspberry/predictive_model_darts/
    python3 reprocess_level_spike_return_filter.py [--dump /path/to/dump.sql]

Output:
    <config.DATA_DIR>/station01_level_corrigido.csv (timestamp, level_delta_cm)
    — same schema as station01_level.csv, which is left untouched.

@author Alexandre Nuernberg
@date 2026-09-09
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M4_DIR = os.path.join(_HERE, "results_final_m4_lgbm")
sys.path.insert(0, _M4_DIR)

import numpy as np
import pandas as pd

import config  # noqa: E402  (results_final_m4_lgbm/config.py)
from plot_events_audit_pdf import (  # noqa: E402
    DEFAULT_DUMP,
    _INSERT_HEADER_RE,
    _parse_sql_value,
    _split_row_tokens,
)
from real_utils import apply_delta_filter  # noqa: E402  (Pass 1, unchanged/proven)

OUTPUT_CSV = os.path.join(config.DATA_DIR, "station01_level_corrigido.csv")

STATION_ID = 1

PROD_HARD_MIN_CM = 0.0
PROD_HARD_MAX_CM = 500.0
"""Station-1 hardMin/hardMax exactly as configured in
App/webserver/cron/filter_level.php's STATION_CONFIG — wider than
config.LEVEL_MIN_CM/MAX_CM (25/250) used elsewhere in this pipeline, which is
a later, tighter physical-plausibility clip applied downstream, not part of
the production filter itself."""

PROD_MAX_DELTA_PER_MIN = 5.0
"""Station-1 maxDelta (cm/min) exactly as configured in filter_level.php."""

SPIKE_TRIGGER_CM = 12.0
"""Step deviation from the last clean value that opens a suspected-spike
buffer in Pass 2. Chosen from the empirical delta distribution of the full
raw Station-01 series: the 99th percentile step is 5cm and the 99.5th is
27cm, so 12cm sits just above ordinary sensor noise while still comfortably
catching the confirmed ~15-25cm echo deviation."""

HARD_MAX_DELTA_CM = config.LEVEL_MAX_DELTA
"""Pass 1's magnitude ceiling (40cm, same value as the existing single-value
filter in real_utils.py) — a step this large from the last accepted value is
rejected outright there, before Pass 2 ever runs."""

RETURN_TOLERANCE_CM = 5.0
"""How close a later reading must come back to the pre-spike baseline (Pass 2)
to confirm the excursion was transient. Looser than typical noise (~1cm at
the median) so a genuine return is reliably detected."""

MAX_BUFFER_MIN = 20.0
"""Pass 2 look-ahead timeout: if the series has not returned to baseline
within this many minutes, the excursion is treated as a real, sustained
change and accepted in full. Comfortably longer than the confirmed ~5-6 min
echo round-trip, comfortably shorter than any real recession timescale on
this river (hours), so it should not misclassify a genuine flash flood."""

SANITY_MAX_YEAR = 2030
"""Defensive guard against a distinct, already-known data-quality defect (not
Issue #211): a handful of rows in the raw dump carry timestamp=2106-02-07
06:26:37 exactly — the classic 32-bit-unsigned Unix-epoch-overflow value
(2^32 seconds since 1970). filter_level.php's own fetchUnprocessed() query
already guards against this class of defect for live processing (its
"timestamp <= NOW()" clause, whose comment explicitly names "Station-01
32-bit overflow bug producing year 2106"); this script needs its own guard
because it works from a historical dump instead of a live NOW(). All 20
catalogued events end by 2026-04-26, so this has zero effect on the
dissertation dataset either way."""


def load_measurements(dump_path, station_id=STATION_ID):
    """
    @brief Stream-parse the SQL dump and return level_cm, level_delta_cm and
           flag for one station, exactly as filter_level.php's fetchUnprocessed
           would see them (level_delta_cm is included only as a ground-truth
           reference for validating Pass 0 — see main()).

    Deliberately does NOT deduplicate or clip level_cm here: Pass 0
    (production_elastic_filter) replicates filter_level.php's own handling of
    duplicate/non-monotonic timestamps (its "elapsedMin <= 0" rejection) and
    physical range (hardMin/hardMax), so doing either here first would diverge
    from what it is meant to faithfully reproduce.

    @param dump_path str Path to the .sql dump file.
    @param station_id int Station id in the measurements table.
    @return pd.DataFrame indexed by tz-naive timestamp (NOT deduplicated,
            sorted ascending), columns: level_cm (float), level_delta_cm
            (float, NaN if NULL), flag (str or None).
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
                        rows.append(
                            (
                                values[col_idx["timestamp"]],
                                float(lvl),
                                values[col_idx["level_delta_cm"]],
                                values[col_idx["flag"]],
                            )
                        )
            if is_last:
                in_block = False

    df = pd.DataFrame(rows, columns=["timestamp", "level_cm", "level_delta_cm", "flag"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    df["level_delta_cm"] = pd.to_numeric(df["level_delta_cm"], errors="coerce")

    garbage = df.index.year >= SANITY_MAX_YEAR
    if garbage.any():
        print(
            f"  [AVISO] {garbage.sum()} leituras com timestamp >= {SANITY_MAX_YEAR} "
            f"descartadas (defeito conhecido, ver docstring de SANITY_MAX_YEAR)."
        )
        df = df[~garbage]

    return df


def production_elastic_filter(
    df,
    hard_min_cm=PROD_HARD_MIN_CM,
    hard_max_cm=PROD_HARD_MAX_CM,
    max_delta_per_min=PROD_MAX_DELTA_PER_MIN,
):
    """
    @brief Pass 0 — faithful Python port of filter_level.php's elastic-window
           delta filter, run from scratch (no resumed state) over the full
           raw history.

    Mirrors the PHP algorithm row by row, in timestamp order: a manual
    flag='b' or a hard-range violation rejects without advancing the anchor;
    otherwise the row is accepted only if its deviation from the last
    accepted value does not exceed max_delta_per_min x elapsed minutes since
    that accepted value (a non-positive elapsed time — a duplicate or
    out-of-order timestamp — is rejected the same way the PHP does). The
    first row is used to seed the anchor directly (the live script instead
    resumes from prior history or searches the batch for a seed row that
    passes the hard-range check; for a from-scratch, chronological
    reprocessing starting at the very first row in the dataset, this reduces
    to the same outcome).

    @param df pd.DataFrame From load_measurements(): columns level_cm, flag,
           DatetimeIndex (not necessarily unique or gap-free).
    @param hard_min_cm float Absolute physical floor.
    @param hard_max_cm float Absolute physical ceiling.
    @param max_delta_per_min float Maximum plausible rate of change (cm/min).
    @return pd.Series Same index as df; rejected readings set to NaN.
    """
    times = df.index
    values = df["level_cm"].to_numpy(dtype=float)
    flags = df["flag"].to_numpy(dtype=object)
    n = len(values)
    out = np.full(n, np.nan)

    if n == 0:
        return pd.Series(out, index=times)

    last_valid_value = values[0]
    last_valid_time = times[0]
    out[0] = values[0]

    for i in range(1, n):
        v = values[i]
        t = times[i]

        if flags[i] == "b":
            continue  # manual bad-data flag — reject, anchor unchanged

        if v < hard_min_cm or v > hard_max_cm:
            continue  # hard physical limit — reject, anchor unchanged

        elapsed_min = (t - last_valid_time).total_seconds() / 60.0
        if elapsed_min <= 0:
            continue  # non-monotonic/duplicate timestamp — reject

        max_allowed_delta = max_delta_per_min * elapsed_min
        if abs(v - last_valid_value) > max_allowed_delta:
            continue  # physically implausible rate of change — reject

        out[i] = v
        last_valid_value = v
        last_valid_time = t

    return pd.Series(out, index=times)


def _spike_return_pass2(
    accepted,
    spike_trigger_cm=SPIKE_TRIGGER_CM,
    return_tolerance_cm=RETURN_TOLERANCE_CM,
    max_buffer_min=MAX_BUFFER_MIN,
):
    """
    @brief Pass 2 — reject transient spike-and-return excursions among
           readings Pass 0+1 already accepted, using a bounded non-causal
           look-ahead (Issue #211 fix).

    No magnitude gate is needed here: by construction, every consecutive pair
    in `accepted` already differs by at most Pass 1's HARD_MAX_DELTA_CM, so a
    step bigger than spike_trigger_cm can only ever be a moderate, gray-zone
    deviation — exactly the band the confirmed Issue #211 echo (~15-25cm)
    lives in. Once a buffer is open, every following reading is held until
    either (1) it returns within return_tolerance_cm of the pre-spike
    baseline (the whole excursion is rejected as transient), or (2)
    max_buffer_min elapses without a return (the whole excursion is accepted
    as a genuine, sustained change). A buffer still open at the end of the
    series is accepted as-is.

    @param accepted pd.Series Readings already accepted by Pass 0+1 (Series
           of values, DatetimeIndex, sorted ascending, no NaN).
    @param spike_trigger_cm float Step deviation that opens a spike buffer.
    @param return_tolerance_cm float Tolerance to confirm a return to baseline.
    @param max_buffer_min float Look-ahead timeout in minutes.
    @return pd.Series Same index as accepted; rejected readings set to NaN.
    """
    times = accepted.index
    values = accepted.to_numpy(dtype=float)
    n = len(values)
    out = np.full(n, np.nan)
    max_buffer = pd.Timedelta(minutes=max_buffer_min)

    if n == 0:
        return pd.Series(out, index=times)

    last_clean = values[0]
    out[0] = values[0]

    buffering = False
    baseline_before_spike = None
    buffer_start_time = None
    buffer_indices = []

    i = 1
    while i < n:
        v = values[i]
        t = times[i]

        if buffering:
            elapsed = t - buffer_start_time
            if elapsed > max_buffer:
                # Timed out without returning: genuine, sustained change —
                # accept every buffered reading and close the buffer, then
                # re-evaluate the current reading against fresh state.
                for j in buffer_indices:
                    out[j] = values[j]
                buffering = False
                buffer_indices = []
                continue

            if abs(v - baseline_before_spike) <= return_tolerance_cm:
                # Confirmed transient: reject the whole buffered excursion,
                # the returning reading is genuine and becomes the new anchor.
                for j in buffer_indices:
                    out[j] = np.nan
                out[i] = v
                last_clean = v
                buffering = False
                buffer_indices = []
            else:
                buffer_indices.append(i)
                last_clean = v
            i += 1
            continue

        step_delta = abs(v - last_clean)
        if step_delta <= spike_trigger_cm:
            out[i] = v
            last_clean = v
        else:
            buffering = True
            baseline_before_spike = last_clean
            buffer_start_time = t
            buffer_indices = [i]
            last_clean = v
        i += 1

    if buffering:
        # Series ended mid-excursion — no future data to confirm either
        # outcome; accept what we have rather than discard the tail.
        for j in buffer_indices:
            out[j] = values[j]

    return pd.Series(out, index=times)


def three_pass_filter(
    df,
    spike_trigger_cm=SPIKE_TRIGGER_CM,
    hard_max_delta_cm=HARD_MAX_DELTA_CM,
    return_tolerance_cm=RETURN_TOLERANCE_CM,
    max_buffer_min=MAX_BUFFER_MIN,
):
    """
    @brief Chains Pass 0 (production_elastic_filter) -> Pass 1
           (real_utils.apply_delta_filter) -> Pass 2 (_spike_return_pass2).
           See the module docstring's "THREE-PASS DESIGN" section.

    @param df pd.DataFrame From load_measurements(): columns level_cm, flag.
    @param spike_trigger_cm float Pass 2 step deviation that opens a buffer.
    @param hard_max_delta_cm float Pass 1 magnitude ceiling.
    @param return_tolerance_cm float Pass 2 tolerance to confirm a return.
    @param max_buffer_min float Pass 2 look-ahead timeout in minutes.
    @return tuple(pd.Series pass0, pd.Series final) both indexed like df;
            pass0 is returned separately so callers can validate it against
            ground truth before trusting the rest of the chain.
    """
    pass0 = production_elastic_filter(df)
    pass1 = apply_delta_filter(pass0.dropna(), max_delta=hard_max_delta_cm)
    accepted = pass1.dropna()
    pass2 = _spike_return_pass2(
        accepted,
        spike_trigger_cm=spike_trigger_cm,
        return_tolerance_cm=return_tolerance_cm,
        max_buffer_min=max_buffer_min,
    )

    final = pass1.copy()
    final.loc[pass2[pass2.isna()].index] = np.nan
    return pass0, final


def summarize_window(raw, filtered, label, start=None, end=None):
    """
    @brief Print accepted/rejected counts for a raw vs. filtered series,
           optionally restricted to a time window (for spot-checking a known
           incident like Event 14 or Event 20).

    @param raw pd.Series Raw level_cm.
    @param filtered pd.Series Output of three_pass_filter()'s final series.
    @param label str Human-readable label for the printed line.
    @param start pd.Timestamp or None Window start (inclusive).
    @param end pd.Timestamp or None Window end (inclusive).
    """
    r = raw.loc[start:end] if (start is not None or end is not None) else raw
    f = filtered.loc[start:end] if (start is not None or end is not None) else filtered
    n_total = len(r)
    n_rejected = int(f.isna().sum())
    print(
        f"  {label}: {n_total} leituras brutas, {n_rejected} rejeitadas "
        f"({100.0 * n_rejected / n_total:.1f}%)"
        if n_total
        else f"  {label}: sem dados"
    )


def main():
    """
    @brief Load the raw SQL dump, validate Pass 0 against production's own
           level_delta_cm, apply the full three-pass filter, spot-check the
           two known-contaminated events, and write the corrected CSV.
    """
    dump_path = DEFAULT_DUMP
    if "--dump" in sys.argv:
        idx = sys.argv.index("--dump")
        if idx + 1 < len(sys.argv):
            dump_path = sys.argv[idx + 1]

    print("=== Reprocessamento do filtro delta em 3 passes (Issue #211) ===\n")
    print(f"Carregando medições brutas (Estação-01) de {dump_path} ...")
    df = load_measurements(dump_path)
    print(f"  {len(df)} leituras ({df.index.min()} -> {df.index.max()}).\n")

    print("Pass 0 — replicando filter_level.php (janela elástica de produção)...")
    pass0, final = three_pass_filter(df)

    ground_truth = df["level_delta_cm"]
    both_known = pd.concat(
        [pass0, ground_truth], axis=1, keys=["pass0", "prod"]
    ).dropna(how="all")
    pass0_accept = both_known["pass0"].notna()
    prod_accept = both_known["prod"].notna()
    agree = (pass0_accept == prod_accept).sum()
    print(
        f"  Concordância Pass 0 vs. level_delta_cm de produção (aceitar/rejeitar): "
        f"{agree}/{len(both_known)} ({100.0 * agree / len(both_known):.2f}%)"
    )
    both_accepted = pass0_accept & prod_accept
    if both_accepted.any():
        value_diff = (
            both_known.loc[both_accepted, "pass0"]
            - both_known.loc[both_accepted, "prod"]
        ).abs()
        print(
            f"  Onde ambos aceitam, diferença de valor: max={value_diff.max():.2f}cm, "
            f"média={value_diff.mean():.4f}cm"
        )

    print(
        f"\nPass 1 (limiar {HARD_MAX_DELTA_CM}cm) + Pass 2 spike-and-return "
        f"(gatilho {SPIKE_TRIGGER_CM}cm, retorno {RETURN_TOLERANCE_CM}cm, "
        f"timeout {MAX_BUFFER_MIN}min) já aplicados acima.\n"
    )

    raw_level = df["level_cm"]
    summarize_window(raw_level, final, "Total")
    summarize_window(
        raw_level,
        final,
        "Evento 14 (2026-02-14 16:00-17:00)",
        start="2026-02-14 16:00:00",
        end="2026-02-14 17:00:00",
    )
    summarize_window(
        raw_level,
        final,
        "Evento 20 (2026-04-26 22:00-22:30)",
        start="2026-04-26 22:00:00",
        end="2026-04-26 22:30:00",
    )

    out = final.dropna()
    out = out[~out.index.duplicated(keep="first")]
    out.index = out.index.tz_localize("UTC")
    df_out = (
        out.rename("level_delta_cm")
        .reset_index()
        .rename(columns={"index": "timestamp"})
    )
    df_out.to_csv(OUTPUT_CSV, index=False)
    print(f"\n{len(df_out)} leituras aceitas gravadas em: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
