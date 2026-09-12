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
@file build_gapfilled_level.py
@brief Fill Station-01 level outages from Station-03, keeping provenance
       (Issue #225).

Station-01 (HC-SR04, trigger/echo, no temperature compensation, not bench
calibrated) was off the air 2026-08-13 to 2026-08-16 for a hardware repair,
with partial outages either side — exactly across the largest August events.
Station-03 (US-100 in serial mode, internal temperature compensation, bench
calibration curve) recorded them. The two sit 30 m apart on the same river and
correlate at 0.98, so the outage is an availability problem, not a hydrological
difference. Their outages do not coincide: over 2026-05-01 to 2026-09-09,
Station-01 alone covers 93.6% of the record and Station-03 alone 91.7%, but
either-one-of-them covers 99.5%.

**Donor correction: a per-band offset.** The offset is not constant across
level — about +2.0 cm at 40-60 cm, +1.0 at 60-75, -0.75 at 75-90 and -1.8 above
90 cm. Station-01 reads progressively higher relative to Station-03 as the
river rises, and the sign inverts at flood stage.

That has a physical cause. The single limnimetric ruler is bolted directly
below Station-03; Station-01 sits 30 m upstream, nearer the incoming flow,
where the surface is more turbulent during a flood. An uncompensated HC-SR04
reading a choppy surface returns the nearest strong echo — a wave crest — and
so over-reads level, the more so the rougher the surface. This also reconciles
the ruler validation table with the overlap statistics: the ruler's +2.65 cm
figure for Station-01 comes from 26 readings weighted towards flood days, while
the +2.00 cm overlap offset is dominated by the ordinary conditions that make
up almost all of the record. They describe different regimes rather than
contradicting each other.

Choosing the estimator on global RMSE would pick the wrong one. Under 5-fold
blocked cross-validation:

    method      global RMSE   >=70 cm RMSE   >=70 cm bias
    constant       2.58           4.10          -2.23
    per-band       2.64           3.36          -0.02
    regression     2.86           5.52          -4.31

The per-band offset is marginally worse globally and decisively better where
the fill is actually used, removing the flood-stage bias outright. The
least-squares fit is worst at flood stage: its 0.95 slope drags peaks down.
Only 521 overlap samples sit above 70 cm, so residual error there is still
about 3.4 cm.

**How that compares to the host series' own accuracy.** Against a limnimetric
ruler, Station-01 (HC-SR04) scores RMSE 4.04 cm with a +2.65 cm bias (n=26),
while Station-03 (US-100) scores RMSE 0.90 cm with a +0.40 cm bias (n=5,
which is thin). So the donor is the markedly more accurate instrument, and the
~3.7 cm residual of the scale conversion is no worse than the 4.04 cm
measurement error the host series carries everywhere. Filled samples should
not be held to a higher standard than the data around them: any event sitting
within ~4 cm of a threshold is inside instrument uncertainty whether it was
filled or not.

Note an unresolved discrepancy worth carrying into the methodology text. The
ruler biases imply Station-01 should read about 2.25 cm ABOVE Station-03 for
the same water, yet 40,000 overlapping samples show Station-03 reading 2.00 cm
above Station-01 — roughly 4 cm in the opposite direction. Either the two
rulers have different datums, or there is a real difference in water surface
between the two sections (4 cm over 30 m is a 0.14% slope, physically
plausible). This does not affect the fill, which converts between the two
series using their own measured offset regardless of what causes it, but it
does qualify any claim that the difference is purely sensor calibration.

**Consequence, and why provenance is written out.** The gap sits inside the
TEST period, so a filled sample is not merely model input — it would also be
the ground truth the model is scored against. Filled values are used to keep
the model's lag context continuous (a 5-day hole is far more damaging than a
3.7 cm uncertainty), but every sample carries a `source` column so evaluation
can report metrics with and without events that depend on them. One recovered
event peaks at 89 cm against a 90 cm Inundação threshold — inside the fill's
own uncertainty — so its classification must not be read as established.

Output: station01_level_gapfilled.csv (timestamp, level_delta_cm, source),
where source is "E01" or "E03+offset".

Usage:
    cd AppTest/raspberry/predictive_model_darts/
    /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 build_gapfilled_level.py

@author Alexandre Nuernberg
@date 2026-09-09
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "results_final_m4_lgbm"))
import config

import numpy as np
import pandas as pd

HOST_CSV = os.path.join(config.DATA_DIR, "station01_level_corrigido.csv")
"""Station-01 input, named explicitly rather than read from config.LEVEL_CSV:
that constant points at this script's OWN OUTPUT, so taking it from there would
feed each run its predecessor's fill instead of the reprocessed source."""

DONOR_CSV = os.path.join(config.DATA_DIR, "station03_level.csv")
OUTPUT_CSV = os.path.join(config.DATA_DIR, "station01_level_gapfilled.csv")

OFFSET_FIT_START = pd.Timestamp("2026-04-01", tz="UTC")
"""Start of the overlap used to measure the offset.

Station-03 came online 2026-03-01 and its first month reads 5 cm below
Station-01 with a correlation of only 0.63, consistent with post-installation
settling; from April the correlation is 0.94 or better. March is therefore
excluded from the fit.
"""

OFFSET_BAND_EDGES = [0, 50, 60, 75, 90, 999]
"""Level bands (cm, on the donor's scale) for the per-band offset.

Boundaries follow the alert thresholds so each band is a regime the reader
already recognises, with the top two isolating flood stage, where the
turbulence-driven divergence appears.
"""

MIN_BAND_SAMPLES = 20
"""Below this a band has too few overlap samples to fit its own offset and
inherits a neighbour's."""

MAX_FILL_GAP_H = 168
"""Longest Station-01 outage that will be filled from the donor (7 days).

Bounds the damage if the donor itself drifts unnoticed over a long stretch.
"""


def load_series(path: str) -> pd.Series:
    """Load a station level CSV onto the 5-min grid.

    @param path CSV with timestamp and level_delta_cm columns.
    @return Level series (cm), tz-aware UTC, physically clipped.
    """
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    s = df.set_index("timestamp").sort_index()["level_delta_cm"]
    s = s[(s >= config.LEVEL_MIN_CM) & (s <= config.LEVEL_MAX_CM)]
    return s.resample(f"{config.RESAMPLE_MIN}min").mean()


def fit_band_offsets(host: pd.Series, donor: pd.Series) -> list[float]:
    """Median donor-minus-host offset within each level band.

    Bands with fewer than MIN_BAND_SAMPLES overlap points inherit a neighbour's
    value rather than fitting noise.

    @param host  Station-01 level over the overlap.
    @param donor Station-03 level over the same index.
    @return One offset per band, ordered as OFFSET_BAND_EDGES.
    """
    raw: list[float] = []
    for i in range(len(OFFSET_BAND_EDGES) - 1):
        lo, hi = OFFSET_BAND_EDGES[i], OFFSET_BAND_EDGES[i + 1]
        mask = (donor >= lo) & (donor < hi)
        raw.append(
            float((donor[mask] - host[mask]).median())
            if mask.sum() >= MIN_BAND_SAMPLES
            else np.nan
        )
    return list(pd.Series(raw).ffill().bfill().values)


def apply_band_offsets(donor: pd.Series, offsets: list[float]) -> pd.Series:
    """Convert donor readings onto the host's scale, band by band.

    @param donor   Station-03 level values.
    @param offsets Output of fit_band_offsets().
    @return Donor values expressed on the Station-01 scale.
    """
    idx = np.clip(
        np.digitize(donor.values, OFFSET_BAND_EDGES) - 1,
        0,
        len(OFFSET_BAND_EDGES) - 2,
    )
    return pd.Series(donor.values - np.asarray(offsets)[idx], index=donor.index)


def main() -> None:
    """Build and write the gap-filled Station-01 series with provenance."""
    print("=" * 70)
    print("  Preenchimento de lacunas da Estação-01 com a Estação-03 (Issue #225)")
    print("=" * 70)

    host = load_series(HOST_CSV)
    donor = load_series(DONOR_CSV)

    idx = host.index.union(donor.index)
    host = host.reindex(idx)
    donor = donor.reindex(idx)

    both = pd.DataFrame({"host": host, "donor": donor}).dropna()
    both = both[both.index >= OFFSET_FIT_START]
    corr = float(both["host"].corr(both["donor"]))
    print(
        f"\n  Sobreposição usada: {both.index[0].date()} a {both.index[-1].date()}"
        f"  ({len(both):,} passos)"
    )
    print(f"  Correlação E01 x E03 : {corr:.4f}")

    offsets = fit_band_offsets(both["host"], both["donor"])
    print("\n  Offset por faixa (E03 acima da E01):")
    for i in range(len(OFFSET_BAND_EDGES) - 1):
        lo, hi = OFFSET_BAND_EDGES[i], OFFSET_BAND_EDGES[i + 1]
        n = int(((both["donor"] >= lo) & (both["donor"] < hi)).sum())
        print(f"    {lo:3d}-{hi:3d} cm  n={n:6d}  {offsets[i]:+.2f} cm")

    residual = apply_band_offsets(both["donor"], offsets) - both["host"]
    high = both["donor"] >= 70
    print(
        f"\n  Erro da conversão    : REQM={np.sqrt((residual**2).mean()):.2f} cm global, "
        f"{np.sqrt((residual[high]**2).mean()):.2f} cm em nível>=70cm "
        f"(n={int(high.sum())})"
    )

    # Only fill runs shorter than MAX_FILL_GAP_H.
    missing = host.isna()
    run_id = (missing != missing.shift()).cumsum()
    fillable = pd.Series(False, index=host.index)
    for _, block in host[missing].groupby(run_id[missing]):
        span_h = len(block) * config.RESAMPLE_MIN / 60
        if span_h <= MAX_FILL_GAP_H:
            fillable.loc[block.index] = True

    use_donor = fillable & donor.notna()
    filled = host.copy()
    filled[use_donor] = apply_band_offsets(donor[use_donor], offsets)

    source = pd.Series("E01", index=host.index, dtype=object)
    source[use_donor] = "E03+offset"
    source[filled.isna()] = "missing"

    out = pd.DataFrame({"level_delta_cm": filled, "source": source})
    out = out[out["level_delta_cm"].notna()]
    out.index.name = "timestamp"
    out.to_csv(OUTPUT_CSV)

    n_e01 = int((out["source"] == "E01").sum())
    n_e03 = int((out["source"] == "E03+offset").sum())
    print(f"\n  Cobertura antes  : {100 * host.notna().mean():.1f}%")
    print(f"  Cobertura depois : {100 * filled.notna().mean():.1f}%")
    print(f"  Amostras E01     : {n_e01:,}")
    print(f"  Amostras da E03  : {n_e03:,}  ({100 * n_e03 / len(out):.1f}% da série)")

    donor_days = (
        out[out["source"] == "E03+offset"]
        .groupby(out[out["source"] == "E03+offset"].index.date)
        .size()
    )
    if len(donor_days):
        print("\n  Dias com dado da E03 (passos de 5min):")
        for day, n in donor_days.items():
            print(f"    {day}: {n:4d}  ({n * 5 / 60:.1f} h)")

    print(f"\n  Gravado em: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
