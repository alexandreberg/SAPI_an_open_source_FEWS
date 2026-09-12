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
@file state_m6.py
@brief Debounce state persistence for the SAPI M6 MLR production pipeline (Issue #120).

Reads and writes a JSON file at STATE_PATH (debounce_state_m6.json).
Isolated from M4 state — each cron run operates on its own state file.

State schema (per station, keyed by str(station_id)):
  {
    "consecutive_steps":   int,
    "last_alert_level":    str,
    "peak_notified_level": str,  // highest level a notification was sent for in the
                                 // current active episode (Issue #193) — resets to
                                 // 'none' on clear, drives fired/cleared instead of
                                 // last_alert_level so re-escalation within an
                                 // already-notified episode does not re-notify
    "last_update":          str
  }
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import config_production_m6 as cfg

logger = logging.getLogger(__name__)

_ALERT_RANK = {"none": 0, "atencao": 1, "alerta": 2, "inundacao": 3}
"""Numeric rank for alert levels — used by update() to compare the current
debounced level against peak_notified_level and decide whether this step is
notification-worthy (see update() docstring, Issue #193)."""


def _default_station_state() -> dict:
    """Return a blank debounce state for a station.

    @return Dict with consecutive_steps=0, last_alert_level='none',
            peak_notified_level='none'.
    """
    return {
        "consecutive_steps":   0,
        "last_alert_level":    "none",
        "peak_notified_level": "none",
        "last_update":         "",
    }


def load_state() -> dict:
    """Load the full debounce state dict from disk.

    @return Dict keyed by str(station_id).  Returns an empty dict if the file
            does not exist or cannot be parsed.
    """
    path = cfg.STATE_PATH
    if not os.path.isfile(path):
        return {}

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("load_state: could not read %s — %s.  Starting fresh.", path, exc)
        return {}


def save_state(state: dict) -> None:
    """Persist the full debounce state dict to disk.

    Creates the parent directory if it does not exist.

    @param state  Full state dict (all stations).
    """
    path = cfg.STATE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
    except OSError as exc:
        logger.error("save_state: could not write %s — %s", path, exc)


def update(
    state: dict,
    station_id: int,
    gated_alert_level: str,
) -> tuple[bool, bool, str, int]:
    """Update debounce state for one station and determine alert transitions.

    The debounce filter increments consecutive_steps while gated_alert_level
    is not 'none', and resets to 0 when it is.  A debounced classification is
    active only after DEBOUNCE_STEPS consecutive active steps — this drives
    the displayed/logged level every run (dashboard, predictions_m6 table)
    and is unrelated to the notification decision below.

    Notification decision (fired/cleared) is based on peak_notified_level,
    not on the debounced level from the previous run (Issue #193). Within
    one active episode the debounced level can legitimately bounce between
    ranks (e.g. alerta -> atencao -> alerta) run to run as a noisy forecast
    sits near a boundary; comparing only against the immediately-previous
    step (the pre-#193 behaviour) treated every such re-escalation as a
    fresh notification-worthy event, flooding Telegram/email with repeated
    messages for what was really one continuous episode. peak_notified_level
    tracks the highest level already notified since the last full clear, so
    a re-escalation back to a level already notified this episode does not
    re-notify — only a genuinely new high (or a fresh episode after a real
    clear to 'none') does.

    @param state              Full state dict (mutated in place).
    @param station_id         Station identifier.
    @param gated_alert_level  Current gated raw alert level from inference.
    @return Tuple (fired, cleared, alert_level, consecutive_steps):
            - fired:             True if the debounced level exceeds
                                  peak_notified_level's rank this step, per
                                  _ALERT_RANK — covers a fresh none→active
                                  transition and any escalation beyond the
                                  highest level already notified this
                                  episode. Re-escalating to a level already
                                  notified this episode (e.g. alerta after a
                                  dip to atencao, without an intervening
                                  clear to 'none') does not re-fire.
            - cleared:           True if the episode fully normalizes this
                                  step (debounced level drops to 'none' after
                                  a notification had been sent this episode)
                                  — resets peak_notified_level.
            - alert_level:       Debounced alert level ('none' until DEBOUNCE_STEPS met).
            - consecutive_steps: Updated counter value.
    """
    key = str(station_id)
    if key not in state:
        state[key] = _default_station_state()

    st = state[key]
    prev_alert = st["last_alert_level"]
    # Fallback to prev_alert (not "none") for state files written before
    # Issue #193 that lack this key — assumes whatever was already the
    # active classification had already been notified, avoiding a spurious
    # re-notification for an already-active episode on first run post-deploy.
    prev_peak  = st.get("peak_notified_level", prev_alert)
    now_iso    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if gated_alert_level != "none":
        st["consecutive_steps"] = min(
            st["consecutive_steps"] + 1,
            cfg.DEBOUNCE_STEPS * 2,
        )
    else:
        st["consecutive_steps"] = 0

    consecutive = st["consecutive_steps"]

    if consecutive >= cfg.DEBOUNCE_STEPS and gated_alert_level != "none":
        debounced_level = gated_alert_level
    else:
        debounced_level = "none"

    # Detect notification-worthy transitions against the notified peak, not
    # the previous step's debounced level (Issue #193).
    fired   = debounced_level != "none" and _ALERT_RANK[debounced_level] > _ALERT_RANK[prev_peak]
    cleared = debounced_level == "none" and prev_peak != "none"

    if fired:
        st["peak_notified_level"] = debounced_level
    elif cleared:
        st["peak_notified_level"] = "none"
    else:
        st["peak_notified_level"] = prev_peak

    st["last_alert_level"] = debounced_level
    st["last_update"]      = now_iso
    state[key]             = st

    return fired, cleared, debounced_level, consecutive
