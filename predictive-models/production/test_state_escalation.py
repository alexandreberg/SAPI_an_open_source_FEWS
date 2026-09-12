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
@file test_state_escalation.py
@brief Verifies the escalation-detection fix (Issue #160) and the
       peak-notified notification hysteresis fix (Issue #193) in
       state.update().

Feeds a synthetic sequence of gated alert levels directly into state.update()
(pure/local — no DB, no network, no disk I/O) and asserts the fired/cleared
flags at each step, covering:
  1. none -> 3x atencao:       fired only on the 3rd step (DEBOUNCE_STEPS reached).
  2. atencao -> alerta:        fired immediately (escalation — the Issue #160 fix).
  3. alerta -> atencao:        neither fired nor cleared (documented boundary case).
  4. atencao -> alerta (again): NOT fired — same peak already notified this
                                episode (Issue #193 regression test; before the
                                fix this re-fired, flooding Telegram/email).
  5. alerta -> inundacao:      fired — genuine new peak still notifies.
  6. inundacao -> atencao:     neither fired nor cleared.
  7. atencao -> none:          cleared (peak was inundacao, not none).
  8. none -> 3x atencao:       fired on the 3rd step again — peak reset
                                correctly after a real clear (new episode).

Run against both the M4 (state.py) and M6 (state_m6.py) modules, since the
bug and fix are mirrored in both.

Usage:
    python3 test_state_escalation.py

@author Alexandre Nuernberg
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M6_DIR = os.path.join(_HERE, "..", "production_m6")


def _run_sequence(update_fn, debounce_steps: int, label: str) -> bool:
    """Run the synthetic escalation sequence against one state module.

    @param update_fn       The module's update(state, station_id, gated_alert_level) function.
    @param debounce_steps  cfg.DEBOUNCE_STEPS for the module under test.
    @param label           Human-readable name for pass/fail reporting.
    @return True if all assertions passed.
    """
    state: dict = {}
    station_id = 1
    ok = True

    def check(step_desc, fired, cleared, exp_fired, exp_cleared):
        nonlocal ok
        passed = (fired == exp_fired) and (cleared == exp_cleared)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {step_desc}: fired={fired} cleared={cleared} "
              f"(expected fired={exp_fired} cleared={exp_cleared})")
        if not passed:
            ok = False

    # 1. Ramp up to "atencao" over DEBOUNCE_STEPS consecutive steps.
    for i in range(1, debounce_steps + 1):
        fired, cleared, debounced_level, consecutive = update_fn(state, station_id, "atencao")
        is_last = (i == debounce_steps)
        check(f"step {i}/{debounce_steps} atencao", fired, cleared,
              exp_fired=is_last, exp_cleared=False)
    if debounced_level != "atencao":
        print(f"  [FAIL] expected debounced_level='atencao' after ramp-up, got '{debounced_level}'")
        ok = False

    # 2. Escalate to "alerta" — must fire immediately (the Issue #160 fix).
    fired, cleared, debounced_level, _ = update_fn(state, station_id, "alerta")
    check("escalation atencao->alerta", fired, cleared, exp_fired=True, exp_cleared=False)
    if debounced_level != "alerta":
        print(f"  [FAIL] expected debounced_level='alerta' after escalation, got '{debounced_level}'")
        ok = False

    # 3. De-escalate to "atencao" — documented boundary: neither fired nor cleared.
    fired, cleared, debounced_level, _ = update_fn(state, station_id, "atencao")
    check("de-escalation alerta->atencao", fired, cleared, exp_fired=False, exp_cleared=False)

    # 4. Re-escalate to "alerta" — Issue #193 regression test: this level was
    #    already notified this episode (step 2), so it must NOT re-fire even
    #    though it ranks above the immediately-previous step ("atencao").
    #    Before the fix this incorrectly fired again, causing the message flood.
    fired, cleared, debounced_level, _ = update_fn(state, station_id, "alerta")
    check("re-escalation atencao->alerta (already notified)", fired, cleared,
          exp_fired=False, exp_cleared=False)
    if debounced_level != "alerta":
        print(f"  [FAIL] expected debounced_level='alerta' after re-escalation, got '{debounced_level}'")
        ok = False

    # 5. Escalate to "inundacao" — a genuinely new peak, must still fire.
    fired, cleared, debounced_level, _ = update_fn(state, station_id, "inundacao")
    check("escalation alerta->inundacao (new peak)", fired, cleared, exp_fired=True, exp_cleared=False)

    # 6. De-escalate to "atencao" — still active, neither fired nor cleared.
    fired, cleared, debounced_level, _ = update_fn(state, station_id, "atencao")
    check("de-escalation inundacao->atencao", fired, cleared, exp_fired=False, exp_cleared=False)

    # 7. Drop to "none" — must clear (peak was "inundacao", not "none").
    fired, cleared, debounced_level, _ = update_fn(state, station_id, "none")
    check("clear atencao->none", fired, cleared, exp_fired=False, exp_cleared=True)

    # 8. New episode: ramp back up to "atencao" over DEBOUNCE_STEPS consecutive
    #    steps — must fire again on the last step, proving peak_notified_level
    #    was correctly reset by the clear in step 7.
    for i in range(1, debounce_steps + 1):
        fired, cleared, debounced_level, consecutive = update_fn(state, station_id, "atencao")
        is_last = (i == debounce_steps)
        check(f"new episode step {i}/{debounce_steps} atencao", fired, cleared,
              exp_fired=is_last, exp_cleared=False)

    print(f"  {'ALL PASS' if ok else 'SOME FAILED'} for {label}\n")
    return ok


def main() -> int:
    all_ok = True

    print("=== M4 (state.py) ===")
    import config_production as cfg_m4
    import state as state_m4
    all_ok &= _run_sequence(state_m4.update, cfg_m4.DEBOUNCE_STEPS, "M4 state.py")

    print("=== M6 (state_m6.py) ===")
    sys.path.insert(0, _M6_DIR)
    import config_production_m6 as cfg_m6
    import state_m6
    all_ok &= _run_sequence(state_m6.update, cfg_m6.DEBOUNCE_STEPS, "M6 state_m6.py")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
