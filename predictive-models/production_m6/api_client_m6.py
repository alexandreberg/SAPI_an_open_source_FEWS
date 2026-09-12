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
@file api_client_m6.py
@brief HTTPS client for the SAPI Hostinger M6 prediction API (Issue #120).

Provides three public functions:
  - fetch_data()  — GET  /sapi/api/data.php        (level or precipitation)
  - fetch_merge() — GET  /sapi/api/data.php?field=merge  (MERGE/GPM hourly precip)
  - post_result() — POST /sapi/api/predictions_m6.php  (M6 prediction + alert state)

Isolated from M4's api_client.py — posts to predictions_m6.php, not predictions.php.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

import config_production_m6 as cfg

logger = logging.getLogger(__name__)

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

    @param station_id  Station identifier.
    @param field       Data field: 'level' or 'precip'.
    @param hours       Lookback window in hours.
    @return List of dicts with keys 'timestamp' (ISO-8601 str) and 'value' (float).
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

    @param hours  Lookback window in hours.
    @return List of dicts with keys 'timestamp' (ISO-8601 str) and 'value' (float).
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
    """POST one M6 prediction result to the Hostinger API.

    Target endpoint: /sapi/api/predictions_m6.php (isolated from M4's predictions.php).

    @param payload  Dict matching the predictions_m6.php expected schema.
    @return True on HTTP 200/201, False on any error.
    """
    url = f"{cfg.API_BASE_URL}/predictions_m6.php"
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
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)
