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
@file refresh_merge_csv.py
@brief Daily cron script — keeps merge_precip.csv up to date from the Hostinger API.

Reads the last timestamp in the local CSV, fetches all MERGE/GPM rows newer
than that from the live API, appends them, deduplicates, trims to KEEP_DAYS,
and overwrites the file.

On the first run (no CSV yet, or CSV stale by more than MAX_FETCH_HOURS) a
full MAX_FETCH_HOURS backfill is requested.

Run manually for initial backfill:
    /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \\
        /home/ilha3d/SAPI/LightGBM_Production/refresh_merge_csv.py

Cron (daily at 02:00 local — MERGE has ~5h publication delay so overnight
covers the previous day reliably):
    0 2 * * * /home/ilha3d/SAPI/LightGBM_Production/.venv/bin/python3 \\
        /home/ilha3d/SAPI/LightGBM_Production/refresh_merge_csv.py \\
        >> /home/ilha3d/SAPI/LightGBM_Production/logs/refresh_merge.log 2>&1
"""

import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import api_client
import config_production as cfg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KEEP_DAYS       = 7
"""Number of days to retain in the CSV.  7 days is far more than the 11-hour
fallback window; extra rows are kept to aid debugging."""

MAX_FETCH_HOURS = 720
"""Maximum lookback when the CSV is absent or very stale (30 days).
data.php allows up to 720h for field=merge."""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("refresh_merge_csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _last_timestamp(csv_path: str) -> datetime | None:
    """Return the latest timestamp in merge_precip.csv, or None if absent/empty.

    @param csv_path  Absolute path to merge_precip.csv.
    @return          Timezone-aware UTC datetime, or None.
    """
    if not os.path.isfile(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path, parse_dates=["reading_time"])
        if df.empty:
            return None
        ts = pd.to_datetime(df["reading_time"], utc=True).max()
        return ts.to_pydatetime()
    except Exception as exc:
        logger.warning("Could not read existing CSV: %s", exc)
        return None


def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
    """Convert API response rows to a DataFrame matching the CSV schema.

    @param rows  List of {timestamp, value} dicts from api_client.fetch_merge().
    @return      DataFrame with columns [reading_time (UTC-aware), prec_mm].
    """
    df = pd.DataFrame(rows)
    df = df.rename(columns={"timestamp": "reading_time", "value": "prec_mm"})
    df["reading_time"] = pd.to_datetime(df["reading_time"], utc=True)
    df["prec_mm"]      = pd.to_numeric(df["prec_mm"], errors="coerce")
    return df.dropna(subset=["prec_mm"])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Fetch new MERGE rows and append them to the local CSV.

    @return  0 on success, 1 if the API returned no data.
    """
    csv_path = cfg.MERGE_CSV
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    now_utc  = datetime.now(timezone.utc)
    last_ts  = _last_timestamp(csv_path)

    # Compute how many hours to request.
    if last_ts is None:
        hours_needed = MAX_FETCH_HOURS
        logger.info("No existing CSV — requesting %d-hour backfill", hours_needed)
    else:
        gap_h        = (now_utc - last_ts).total_seconds() / 3600
        hours_needed = min(int(gap_h) + 2, MAX_FETCH_HOURS)  # +2h safety margin
        logger.info("Last CSV entry: %s UTC — gap %.1f h — fetching %d h",
                    last_ts.strftime("%Y-%m-%d %H:%M"), gap_h, hours_needed)

    # Fetch from API.
    rows = api_client.fetch_merge(hours_needed)
    if not rows:
        logger.warning("API returned 0 rows — CSV not updated")
        return 1

    new_df = _rows_to_df(rows)
    logger.info("API returned %d rows (%s → %s UTC)",
                len(new_df),
                new_df["reading_time"].min().strftime("%Y-%m-%d %H:%M"),
                new_df["reading_time"].max().strftime("%Y-%m-%d %H:%M"))

    # Merge with existing CSV.
    if os.path.isfile(csv_path):
        old_df = pd.read_csv(csv_path, parse_dates=["reading_time"])
        old_df["reading_time"] = pd.to_datetime(old_df["reading_time"], utc=True)
        combined = pd.concat([old_df, new_df], ignore_index=True)
    else:
        combined = new_df

    # Deduplicate, sort, trim to KEEP_DAYS.
    combined = (
        combined
        .drop_duplicates(subset=["reading_time"])
        .sort_values("reading_time")
    )
    cutoff   = now_utc - timedelta(days=KEEP_DAYS)
    combined = combined[combined["reading_time"] >= cutoff].reset_index(drop=True)

    combined.to_csv(csv_path, index=False)
    logger.info("CSV written: %d rows, %s → %s UTC",
                len(combined),
                combined["reading_time"].iloc[0].strftime("%Y-%m-%d %H:%M"),
                combined["reading_time"].iloc[-1].strftime("%Y-%m-%d %H:%M"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
