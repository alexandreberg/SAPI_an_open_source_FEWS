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
@file api_client.py
@brief HTTPS client for the SAPI Hostinger prediction API (Issue #108).

Provides three public functions:
  - fetch_data()  — GET  /sapi/api/data.php        (level or precipitation)
  - fetch_merge() — GET  /sapi/api/data.php?field=merge  (MERGE/GPM hourly precip)
  - post_result() — POST /sapi/api/predictions.php  (prediction + alert state)

Authentication: X-API-Key header.  The key is read once from API_KEY_FILE and
cached in module scope so repeated calls within the same process do not hit disk.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

import config_production as cfg

logger = logging.getLogger(__name__)

# Module-level key cache — loaded lazily on first call.
_api_key: Optional[str] = None


def _load_api_key() -> str:
    """Read and cache the RPi prediction API key from disk.

    @return API key string (stripped of whitespace).
    @raises FileNotFoundError if the key file does not exist.
    @raises ValueError if the key file is empty.
    """
    global _api_key
    if _api_key is not None:
        return _api_key

    key_file = cfg.API_KEY_FILE
    if not os.path.isfile(key_file):
        raise FileNotFoundError(
            f"API key file not found: {key_file}\n"
            "Create it: echo 'YOUR_KEY' > " + key_file + " && chmod 600 " + key_file
        )

    key = open(key_file).read().strip()
    if not key:
        raise ValueError(f"API key file is empty: {key_file}")

    _api_key = key
    return _api_key


def fetch_data(
    station_id: int,
    field: str,
    hours: int,
) -> list[dict]:
    """Fetch recent sensor data from the Hostinger API.

    @param station_id  Station identifier (1 or 2 for precip, 1 or 3 for level).
    @param field       Data field: 'level' or 'precip'.
    @param hours       Lookback window in hours.
    @return List of dicts with keys 'timestamp' (ISO-8601 str) and 'value' (float).
            Returns an empty list on any network or server error.
    """
    url = f"{cfg.API_BASE_URL}/data.php"
    params = {"station_id": station_id, "field": field, "hours": hours}
    headers = {"X-API-Key": _load_api_key()}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=cfg.API_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list):
            logger.error("fetch_data: unexpected response shape: %s", type(data))
            return []

        logger.debug("fetch_data: station=%d field=%s hours=%d → %d rows",
                     station_id, field, hours, len(data))
        return data

    except requests.exceptions.Timeout:
        logger.warning("fetch_data: timeout (station=%d field=%s)", station_id, field)
    except requests.exceptions.ConnectionError as exc:
        logger.warning("fetch_data: connection error — %s", exc)
    except requests.exceptions.HTTPError as exc:
        logger.warning("fetch_data: HTTP %s — %s", exc.response.status_code, exc)
    except (ValueError, KeyError) as exc:
        logger.warning("fetch_data: response parse error — %s", exc)

    return []


def fetch_merge(hours: int) -> list[dict]:
    """Fetch recent MERGE/GPM hourly precipitation from the Hostinger API.

    Used as fallback when Station-02 is offline.  Returns hourly rows; the
    caller is responsible for 5-min resampling (forward-fill ÷ 12).

    @param hours  Lookback window in hours (use MERGE_FALLBACK_HOURS from config
                  to cover the 6-h gate window plus the ~5-h MERGE publication delay).
    @return List of dicts with keys 'timestamp' (ISO-8601 str) and 'value' (float).
            Returns an empty list on any network or server error.
    """
    url = f"{cfg.API_BASE_URL}/data.php"
    params = {"field": "merge", "hours": hours}
    headers = {"X-API-Key": _load_api_key()}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=cfg.API_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list):
            logger.error("fetch_merge: unexpected response shape: %s", type(data))
            return []

        logger.debug("fetch_merge: hours=%d → %d rows", hours, len(data))
        return data

    except requests.exceptions.Timeout:
        logger.warning("fetch_merge: timeout")
    except requests.exceptions.ConnectionError as exc:
        logger.warning("fetch_merge: connection error — %s", exc)
    except requests.exceptions.HTTPError as exc:
        logger.warning("fetch_merge: HTTP %s — %s", exc.response.status_code, exc)
    except (ValueError, KeyError) as exc:
        logger.warning("fetch_merge: response parse error — %s", exc)

    return []


def post_result(payload: dict) -> bool:
    """POST one prediction result to the Hostinger API.

    @param payload  Dict matching the predictions.php expected schema:
                    {
                      station_id, timestamp (ISO-8601),
                      h_pred_30, h_pred_60, h_pred_90, h_pred_120,
                      precip_rolling, precip_source,
                      gate_active, raw_alert_level, alert_level,
                      consecutive_steps
                    }
    @return True on HTTP 200/201, False on any error.
    """
    url = f"{cfg.API_BASE_URL}/predictions.php"
    headers = {
        "X-API-Key": _load_api_key(),
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            url,
            data=json.dumps(payload, default=_json_default),
            headers=headers,
            timeout=cfg.API_TIMEOUT_S,
        )
        resp.raise_for_status()
        logger.debug("post_result: station=%d → HTTP %d", payload.get("station_id"), resp.status_code)
        return True

    except requests.exceptions.Timeout:
        logger.warning("post_result: timeout (station=%d)", payload.get("station_id"))
    except requests.exceptions.ConnectionError as exc:
        logger.warning("post_result: connection error — %s", exc)
    except requests.exceptions.HTTPError as exc:
        logger.warning("post_result: HTTP %s — %s", exc.response.status_code, exc)

    return False


def _json_default(obj):
    """JSON serialiser fallback for datetime and numpy types.

    @param obj  Object that the default encoder cannot serialise.
    @return Serialisable representation.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    # numpy scalar types
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)
