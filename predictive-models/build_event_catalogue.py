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
@file build_event_catalogue.py
@brief Rebuild the Station-01 event catalogue from the corrected level series
       (Issue #225).

Replaces the hand-curated 20-event event_windows_v2.csv, which stopped at
2026-04-26, with a reproducible catalogue covering the whole record.

**Why episodes are segmented by amplitude, not by absolute level.** The channel
baseline is not stationary: Station-01's monthly median went from 29 cm
(Jul/2025) to 47 cm (Sep/2026). Cutting episodes at a fixed level therefore
behaves completely differently at the two ends of the record — at 45 cm the
detector returned 133 "events", 112 of them in 2026, some lasting 11 days,
because it was tracking normal flow. Segmenting on the rise ABOVE the local
baseline (trailing median) isolates the same kind of physical excursion in both
regimes.

This is a segmentation device only. It decides where one episode starts and
ends; it does not decide whether that episode counts as an alert. The alert
levels stay absolute and fixed (config.THRESHOLD_*), as they must for a
hydrometeorological station — those do not move between dry and wet years — and
each episode's ``level`` field is assigned from its peak against them.

Output columns match event_windows_v2.csv so every downstream script keeps
working unchanged: event_num, peak_time, peak_cm, analysis_start, analysis_end,
split_set, type, level, notes — plus donor_pct (Issue #225), and p24h_mm and
exclusion (Issue #227).

**Sensor artifacts (Issue #227).** Some episodes are not floods but HC-SR04
echo bursts the level filter merged into a fake rise. The physical premise is
field knowledge from the author, who lives at the site: there is no flood
there without rain. Such episodes are kept in the file — so event numbering
stays stable — but marked ``split_set = excluded`` and ``exclusion =
artifact``; real_utils then blanks their windows out of the level series:

- Station-02 period (the whole 24 h before the peak is on or after
  config.PRECIP_CUTOFF, rain gauge on site): accumulated rain in the 24 h
  before the peak below ARTIFACT_MAX_P24H_MM -> artifact, automatically.
- MERGE period: low MERGE rain does not prove absence of rain (E04 is a real
  98 cm flash flood with 5.3 mm/24 h in MERGE), so only episodes confirmed by
  visual inspection are excluded, listed in ARTIFACT_MANUAL.

The 24 h window is deliberate: with 6 h, the real event of 2026-03-20 (46 mm
from 00:00 to 06:00, then a 1h46 Station-02 gap) would read 0 mm.

Usage:
    cd AppTest/raspberry/predictive_model_darts/
    /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 build_event_catalogue.py

@author Alexandre Nuernberg
@date 2026-09-09
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "results_final_m4_lgbm"))
import config
import real_utils

import numpy as np
import pandas as pd

OUTPUT_CSV = os.path.join(_HERE, "results_final_m4_lgbm", "event_windows_v3.csv")

SEGMENT_TRIGGER_CM = 12.0
"""Rise above the local baseline that opens an episode.

Deliberately below the lowest catalogued v2 peak's own amplitude so no
previously catalogued event is lost, and above the noise of ordinary daily
variation.
"""

BASELINE_WINDOW = "7D"
"""Trailing window for the local baseline (median). Long enough not to be
dragged up by the event itself, short enough to follow seasonal drift."""

MIN_DURATION_MIN = 30
"""An excursion must hold above the trigger this long to count as an episode."""

MERGE_GAP_MIN = 180
"""Episodes separated by less than this are one event (recession dips)."""

PRE_BUFFER_MIN = 240
"""Analysis window lead-in before the episode starts. Matches
predictive_model/config.py's EVENT_PRE_WINDOW_MIN, and must exceed the
lead-time causality guard (180 min) so a genuinely early predicted crossing
still falls inside the window."""

POST_BUFFER_MIN = 120
"""Analysis window tail after the episode ends."""

FLASH_FLOOD_CM_PER_H = 50.0
"""Maximum 30-min rise rate separating flash_flood from flood.

Calibrated against the v2 hand labels: the three unambiguous flash floods
reach 67.9 (E04), 70.5 (E09) and 155.0 (E08) cm/h, while the fastest gradual
flood reaches 32.0 (E19) — a wide, empty gap. v2's fourth flash_flood label
(E05) measures only 8.0 cm/h on its own window, which starts after E04's peak;
it inherited the label from the episode it was split from, so this script
classifies it as flood.
"""

ARTIFACT_MAX_P24H_MM = 5.0
"""Station-02 period: an episode with less than this much rain in the 24 h
before its peak is a sensor artifact (Issue #227). Same 5 mm figure as the
operational precipitation gate (GATE_MM_OPERATIONAL, which applies it over
6 h). On the v3 record it reproduces the author's independent visual artifact
list exactly."""

ARTIFACT_RAIN_WINDOW_H = 24
"""Accumulation window for the rule above, in hours before the peak."""

STATION02_MAX_GAP_MIN = 30
"""A Station-02 interval longer than this inside the rain window is reported
in the exclusion note: the pipeline counts missing rain as 0 mm."""

ARTIFACT_MANUAL = {
    "2025-12-26 23:25:00": (
        "nível bruto muito ruidoso; o ruído somado pelo filtro criou uma falsa "
        "elevação (inspeção visual 2026-09-11)"
    ),
}
"""MERGE-period episodes excluded as artifacts by visual inspection, keyed by
catalogued peak time (UTC). The rain rule is not applied automatically there
(see module docstring). A key that stops matching after a rebuild is reported,
never silently ignored."""


def load_level() -> tuple[pd.Series, pd.Series]:
    """Load the Station-01 level and its provenance on a 5-min grid.

    @return (level series in cm, source series) — tz-aware UTC, short gaps
            interpolated. The source series marks which samples came from
            Station-03 via build_gapfilled_level.py.
    """
    df = pd.read_csv(config.LEVEL_CSV, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.set_index("timestamp").sort_index()
    s = df["level_delta_cm"]
    s = s[(s >= config.LEVEL_MIN_CM) & (s <= config.LEVEL_MAX_CM)]
    s = s.resample(f"{config.RESAMPLE_MIN}min").mean().interpolate(limit=3)

    if "source" in df.columns:
        src = (
            df["source"].resample(f"{config.RESAMPLE_MIN}min").first().reindex(s.index)
        )
    else:
        src = pd.Series("E01", index=s.index)
    return s, src


def segment_episodes(level: pd.Series) -> list[dict]:
    """Cut the record into discrete excursions above the local baseline.

    @param level Level series on the 5-min grid.
    @return List of dicts with start, end, peak_time, peak_cm, rise_cm_per_h.
    """
    baseline = level.rolling(BASELINE_WINDOW).median()
    above = ((level - baseline) >= SEGMENT_TRIGGER_CM).fillna(False)

    raw: list[tuple] = []
    run_start = None
    for ts, flag in above.items():
        if flag and run_start is None:
            run_start = ts
        elif not flag and run_start is not None:
            raw.append((run_start, ts))
            run_start = None
    if run_start is not None:
        raw.append((run_start, above.index[-1]))

    # Merge excursions separated by a short dip — one flood with a ragged crest
    # must not become several events.
    merged: list[list] = []
    for start, end in raw:
        if merged and (start - merged[-1][1]) <= pd.Timedelta(minutes=MERGE_GAP_MIN):
            merged[-1][1] = end
        else:
            merged.append([start, end])

    steps_30min = 30 // config.RESAMPLE_MIN
    episodes: list[dict] = []
    for start, end in merged:
        if (end - start).total_seconds() / 60 < MIN_DURATION_MIN:
            continue
        window = level.loc[start:end]
        if window.empty:
            continue
        peak_time = window.idxmax()
        rise = window.loc[:peak_time]
        # cm per 30 min -> cm/h
        rate = (rise.diff(steps_30min) * 2).max() if len(rise) > steps_30min else 0.0
        episodes.append(
            {
                "start": start,
                "end": end,
                "peak_time": peak_time,
                "peak_cm": float(window.max()),
                "rise_cm_per_h": float(rate) if np.isfinite(rate) else 0.0,
            }
        )
    return episodes


def classify_level(peak_cm: float) -> str:
    """Map a peak to its alert level using the fixed absolute thresholds.

    @param peak_cm Episode peak in cm.
    @return One of Inundação, Alerta, Atenção, Normal.
    """
    if peak_cm >= config.THRESHOLD_INUNDACAO:
        return "Inundação"
    if peak_cm >= config.THRESHOLD_ALERTA:
        return "Alerta"
    if peak_cm >= config.THRESHOLD_ATENCAO:
        return "Atenção"
    return "Normal"


def build_windows(
    episodes: list[dict], level: pd.Series, source: pd.Series
) -> pd.DataFrame:
    """Turn episodes into catalogue rows with non-overlapping analysis windows.

    Windows are the episode padded by PRE_BUFFER_MIN / POST_BUFFER_MIN. Where
    two padded windows would overlap, the boundary is placed at their midpoint
    so each timestamp belongs to exactly one event — otherwise the same
    observed crossing could be counted for two events.

    Each row also records `donor_pct` — the share of its analysis window that
    came from Station-03 rather than Station-01. That gap fill carries about
    3.7 cm of error in the flood range, so an event with a non-zero donor_pct
    has a peak, and therefore possibly a `level` label, the fill helped decide.
    Evaluation must be able to report with and without those events.

    @param episodes Output of segment_episodes().
    @param level    Level series, used only for its bounds.
    @param source   Provenance series aligned to `level`.
    @return Catalogue DataFrame ready to write.
    """
    pre = pd.Timedelta(minutes=PRE_BUFFER_MIN)
    post = pd.Timedelta(minutes=POST_BUFFER_MIN)

    starts = [max(level.index[0], e["start"] - pre) for e in episodes]
    ends = [min(level.index[-1], e["end"] + post) for e in episodes]

    for i in range(len(episodes) - 1):
        if ends[i] > starts[i + 1]:
            mid = starts[i + 1] + (ends[i] - starts[i + 1]) / 2
            ends[i] = mid
            starts[i + 1] = mid

    cut = pd.Timestamp(config.TRAIN_END)
    if cut.tz is None:
        cut = cut.tz_localize("UTC")

    rows = []
    for num, (ep, ws, we) in enumerate(zip(episodes, starts, ends), start=1):
        win_src = source.loc[ws:we]
        donor_pct = (
            round(100.0 * (win_src == "E03+offset").mean(), 1) if len(win_src) else 0.0
        )
        # The rate is the steepest 30-min rise doubled to cm/h — a peak rate,
        # not the average over the rise (E08: 78 cm in 30 min = 155 cm/h,
        # while the whole rise was 129 cm in 1h15). Print the 30-min rise in
        # cm so the note cannot be read as an hourly average.
        rise30 = ep["rise_cm_per_h"] / 2
        note = f"subida máx. em 30 min: {rise30:.0f} cm"
        if donor_pct > 0:
            note += f"; {donor_pct:.0f}% da janela vem da E03 (Issue #225)"

        exclusion = ""
        if we <= cut:
            split = "train"
        elif ws >= cut:
            split = "test"
        else:
            split = "excluded"
            exclusion = "straddles_train_end"
        rows.append(
            {
                "event_num": num,
                "peak_time": ep["peak_time"].strftime("%Y-%m-%d %H:%M:%S"),
                "peak_cm": int(round(ep["peak_cm"])),
                "analysis_start": ws.strftime("%Y-%m-%d %H:%M:%S"),
                "analysis_end": we.strftime("%Y-%m-%d %H:%M:%S"),
                "split_set": split,
                "type": (
                    "flash_flood"
                    if ep["rise_cm_per_h"] >= FLASH_FLOOD_CM_PER_H
                    else "flood"
                ),
                "level": classify_level(ep["peak_cm"]),
                "donor_pct": donor_pct,
                "notes": note,
                "exclusion": exclusion,
            }
        )
    return pd.DataFrame(rows)


def _largest_gap(idx: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp):
    """Longest stretch without a reading in (start, end], edges included.

    @param idx   Sorted reading timestamps (tz-naive UTC).
    @param start Window start (exclusive).
    @param end   Window end (inclusive).
    @return pd.Timedelta
    """
    inside = idx[(idx > start) & (idx <= end)]
    points = pd.DatetimeIndex([start]).append(inside).append(pd.DatetimeIndex([end]))
    return points.to_series().diff().max()


def flag_artifacts(df: pd.DataFrame) -> pd.DataFrame:
    """Add p24h_mm and mark sensor-artifact episodes as excluded (Issue #227).

    Rain is summed from real_utils.load_precip_5min() — the same spliced series
    the models are fed — over (peak - ARTIFACT_RAIN_WINDOW_H, peak]. See the
    module docstring for the rule and why it is automatic only in the
    Station-02 period.

    @param df Catalogue from build_windows() (peak_time as "%Y-%m-%d %H:%M:%S" UTC).
    @return The same DataFrame with p24h_mm added and artifact rows set to
            split_set="excluded", exclusion="artifact", reason in notes.
    """
    precip = real_utils.load_precip_5min()["prec_mm"]
    st02 = pd.read_csv(config.STATION02_CSV, usecols=["timestamp"])["timestamp"]
    st02_idx = pd.DatetimeIndex(
        pd.to_datetime(st02, utc=True).dt.tz_localize(None)
    ).sort_values()
    cutoff = config.PRECIP_CUTOFF.tz_localize(None)
    window = pd.Timedelta(hours=ARTIFACT_RAIN_WINDOW_H)

    p24_values = []
    matched_manual = set()
    for i, row in df.iterrows():
        peak = pd.Timestamp(row["peak_time"])
        start = peak - window
        p24 = float(precip[(precip.index > start) & (precip.index <= peak)].sum())
        p24_values.append(round(p24, 1))

        reason = None
        if row["peak_time"] in ARTIFACT_MANUAL:
            matched_manual.add(row["peak_time"])
            reason = (
                f"ARTEFATO: {ARTIFACT_MANUAL[row['peak_time']]}; "
                f"{p24:.1f} mm em {ARTIFACT_RAIN_WINDOW_H} h (MERGE)"
            )
        elif start >= cutoff and p24 < ARTIFACT_MAX_P24H_MM:
            reason = (
                f"ARTEFATO: {p24:.1f} mm em {ARTIFACT_RAIN_WINDOW_H} h antes do "
                "pico (Estação-02)"
            )
            gap = _largest_gap(st02_idx, start, peak)
            if gap > pd.Timedelta(minutes=STATION02_MAX_GAP_MIN):
                hours, minutes = divmod(int(gap.total_seconds() // 60), 60)
                reason += f", com lacuna de {hours}h{minutes:02d} na Estação-02"

        if reason:
            df.at[i, "split_set"] = "excluded"
            df.at[i, "exclusion"] = "artifact"
            df.at[i, "notes"] = f"{row['notes']}; {reason} (Issue #227)"

    df["p24h_mm"] = p24_values
    for key in sorted(set(ARTIFACT_MANUAL) - matched_manual):
        print(
            f"  [WARN] ARTIFACT_MANUAL key {key} matched no episode — the "
            "catalogue changed; re-check that exclusion by eye."
        )
    return df


def main() -> None:
    """Rebuild the catalogue and write event_windows_v3.csv."""
    print("=" * 70)
    print("  Reconstrução do catálogo de eventos — Estação-01 (Issue #225)")
    print("=" * 70)
    print(
        f"\n  Limiares fixos: Atenção={config.THRESHOLD_ATENCAO} "
        f"Alerta={config.THRESHOLD_ALERTA} "
        f"Inundação={config.THRESHOLD_INUNDACAO} cm"
    )
    print(f"  Corte treino/teste: {config.TRAIN_END}")

    level, source = load_level()
    print(f"\n  Nível: {level.index[0]} -> {level.index[-1]}  ({len(level):,} passos)")

    n_donor = int((source == "E03+offset").sum())
    print(
        f"  Amostras vindas da Estação-03: {n_donor:,} "
        f"({100 * n_donor / len(source):.1f}%)"
    )

    episodes = segment_episodes(level)
    print(f"  Episódios segmentados: {len(episodes)}")

    df = build_windows(episodes, level, source)
    df = flag_artifacts(df)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

    print(
        f"\n  {'':4} {'pico':>5}  {'nível':<10} {'tipo':<12} {'split':<9} "
        f"{'E03%':>5} {'P24h':>6}  pico em"
    )
    for r in df.itertuples():
        flag = f"{r.donor_pct:5.1f}" if r.donor_pct else "    -"
        art = "  ARTEFATO" if r.exclusion == "artifact" else ""
        print(
            f"  E{r.event_num:02d} {r.peak_cm:5d}  {r.level:<10} "
            f"{r.type:<12} {r.split_set:<9} {flag} {r.p24h_mm:6.1f}  "
            f"{r.peak_time}{art}"
        )

    print(
        f"\n  Por conjunto: "
        + ", ".join(f"{k}={v}" for k, v in df["split_set"].value_counts().items())
    )
    print(
        "  Por nível (teste): "
        + ", ".join(
            f"{k}={v}"
            for k, v in df[df.split_set == "test"]["level"].value_counts().items()
        )
    )
    print(f"\n  Gravado em: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
