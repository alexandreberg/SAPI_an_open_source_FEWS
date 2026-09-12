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
@file lead_time_utils.py
@brief Lead time per threshold-crossing occurrence (Issue #229).

Single implementation of the lead-time rule, shared by
results_final_m4_lgbm/04_lead_time_m4.py, results_final_m6_mlr/04_lead_time_m6.py
and plot_events_audit_pdf.py (which used to carry three hand-synchronised
copies). Pure functions: every parameter is passed in, nothing is read from a
config module, so the M4 and M6 folders can both import it.

**Occurrence.** A catalogued event is a hydrological event and may have
several peaks. Each up-crossing of a threshold by the observed level is an
alert *occurrence*; a new one only counts after the level has fallen to
``threshold - hysteresis`` (re-arm), so sensor oscillation around the
threshold does not multiply occurrences.

**Predicted alarm.** For each forecast horizon, the model's alarm fires when
its forecast has stayed at or above the threshold for ``persistence_steps``
consecutive 5-min steps — the same persistence as the operational alarm. The
lead time is measured to that firing instant (option (a) agreed for #229):
the warning the population would actually receive, not the first touch.

**Search window.** The alarm is paired with an occurrence only if it fires in
``[max(window start, previous re-arm, t_obs - causality_max_lead_min),
this occurrence's re-arm]``. The lower bound stops an earlier peak's alarm, or
an unrelated early spike, from being credited; the upper bound stops a much
later peak's alarm from being paired with this crossing (the −2360 min case of
E33 before this rule). No firing inside the window means "not reached" (NaN).

**Alarm already active.** If the alarm is still firing from before the search
window opens (it never switched off after the previous peak), the lead time is
counted from the window start and the row is flagged ``active_<H>min``.

Lead time = t_obs − t_fire, in minutes: positive = the alarm fired before the
observed crossing, negative = after.

@author Alexandre Nuernberg
@date 2026-09-11
"""

import numpy as np
import pandas as pd


def find_occurrences(obs, threshold_cm, hysteresis_cm):
    """
    @brief Up-crossings of a threshold by the observed level, with re-arm
           hysteresis.

    @param obs pd.Series Observed level (cm) indexed by timestamp, sorted, for
           one event's analysis window. NaN steps are skipped.
    @param threshold_cm float Threshold (cm).
    @param hysteresis_cm float The level must fall to threshold_cm -
           hysteresis_cm before a new up-crossing counts as a new occurrence.
    @return list of dict, one per occurrence, in time order, with keys:
            - "occurrence": 1, 2, ...
            - "t_obs": timestamp of the up-crossing;
            - "armed_from": when the level was last re-armed before t_obs
              (the window start for the first occurrence);
            - "rearm": first timestamp after t_obs at which the level fell to
              threshold_cm - hysteresis_cm, or None if it never did inside the
              window;
            - "at_window_start": True if the level was already at or above the
              threshold at the first valid step (a censored crossing).
    """
    values = obs.dropna()
    if values.empty:
        return []
    occurrences = []
    armed = True
    armed_from = values.index[0]
    rearm_level = threshold_cm - hysteresis_cm
    for t, v in values.items():
        if armed and v >= threshold_cm:
            occurrences.append(
                {
                    "occurrence": len(occurrences) + 1,
                    "t_obs": t,
                    "armed_from": armed_from,
                    "rearm": None,
                    "at_window_start": t == values.index[0],
                }
            )
            armed = False
        elif not armed and v <= rearm_level:
            armed = True
            armed_from = t
            occurrences[-1]["rearm"] = t
    return occurrences


def alarm_state(pred, threshold_cm, persistence_steps):
    """
    @brief Boolean alarm state of one forecast horizon with persistence.

    @param pred pd.Series Forecast (cm) on a regular 5-min grid.
    @param threshold_cm float Threshold (cm).
    @param persistence_steps int Consecutive steps at or above the threshold
           required before the alarm is on (NaN counts as below).
    @return pd.Series of bool aligned to pred: True where the alarm is on.
    """
    above = (pred >= threshold_cm).astype(float)
    return (
        above.rolling(persistence_steps, min_periods=persistence_steps).sum()
        == persistence_steps
    )


def predicted_alarm(pred, threshold_cm, persistence_steps, search_start, search_end):
    """
    @brief First instant, inside a search window, at which the persistent
           alarm of one forecast horizon is on.

    @param pred pd.Series Forecast (cm) on a regular 5-min grid, covering the
           search window and at least persistence_steps steps before it.
    @param threshold_cm float Threshold (cm).
    @param persistence_steps int See alarm_state().
    @param search_start pd.Timestamp Window start (inclusive).
    @param search_end pd.Timestamp Window end (inclusive).
    @return tuple(pd.Timestamp or None, bool): the firing instant (None if the
            alarm is never on inside the window) and whether the alarm was
            already on at the step just before search_start.
    """
    state = alarm_state(pred, threshold_cm, persistence_steps)
    inside = state.loc[search_start:search_end]
    on = inside[inside]
    if on.empty:
        return None, False
    t_fire = on.index[0]
    before = state.loc[: search_start - pd.Timedelta(seconds=1)]
    already_active = bool(
        t_fire == inside.index[0] and not before.empty and before.iloc[-1]
    )
    return t_fire, already_active


def occurrence_lead_times(
    df_pred,
    win_start,
    win_end,
    threshold_cm,
    horizons,
    hysteresis_cm,
    persistence_steps,
    causality_max_lead_min,
):
    """
    @brief Lead time per occurrence and horizon for one event and threshold.

    @param df_pred pd.DataFrame Continuous predictions indexed by timestamp
           (regular 5-min grid), with columns h_obs and h_pred_<H> for each
           horizon. Must extend at least persistence_steps steps before
           win_start so an alarm already on at the window start is detected.
    @param win_start pd.Timestamp Event analysis window start.
    @param win_end pd.Timestamp Event analysis window end.
    @param threshold_cm float Threshold (cm).
    @param horizons list of int Forecast horizons in minutes (30, 60, ...).
    @param hysteresis_cm float Re-arm hysteresis, see find_occurrences().
    @param persistence_steps int See alarm_state().
    @param causality_max_lead_min float Earliest pairing, in minutes before
           the observed crossing.
    @return list of dict, one per occurrence, with keys occurrence,
            n_occurrences, t_obs, at_window_start, search_start, search_end,
            and for each horizon H: fire_<H>min (timestamp or None),
            lead_time_<H>min (float or NaN) and active_<H>min (bool).
    """
    window = df_pred.loc[win_start:win_end]
    occurrences = find_occurrences(window["h_obs"], threshold_cm, hysteresis_cm)
    lookback = df_pred.loc[:win_end].tail(len(window) + persistence_steps)
    rows = []
    for occ in occurrences:
        search_start = max(
            win_start,
            occ["armed_from"],
            occ["t_obs"] - pd.Timedelta(minutes=causality_max_lead_min),
        )
        search_end = occ["rearm"] if occ["rearm"] is not None else win_end
        row = {
            "occurrence": occ["occurrence"],
            "n_occurrences": len(occurrences),
            "t_obs": occ["t_obs"],
            "at_window_start": occ["at_window_start"],
            "search_start": search_start,
            "search_end": search_end,
        }
        for h in horizons:
            col = f"h_pred_{h}"
            if col not in lookback.columns:
                t_fire, active = None, False
            else:
                t_fire, active = predicted_alarm(
                    lookback[col],
                    threshold_cm,
                    persistence_steps,
                    search_start,
                    search_end,
                )
            row[f"fire_{h}min"] = t_fire
            row[f"lead_time_{h}min"] = (
                np.nan
                if t_fire is None
                else (occ["t_obs"] - t_fire).total_seconds() / 60.0
            )
            row[f"active_{h}min"] = active
        rows.append(row)
    return rows


def occurrence_label(event_num, occurrence, n_occurrences):
    """
    @brief Short label for charts and tables: "E33" for a single occurrence,
           "E33a", "E33b", ... when the event crosses the threshold more than
           once.
    @param event_num int Event number.
    @param occurrence int Occurrence number (1-based).
    @param n_occurrences int Occurrences of this threshold in the event.
    @return str
    """
    base = f"E{int(event_num):02d}"
    if n_occurrences <= 1:
        return base
    return base + "abcdefghijklmnopqrstuvwxyz"[int(occurrence) - 1]
