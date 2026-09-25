# Changelog

All notable changes to the SAPI project are documented in this file.

This changelog starts from the open-source licensing milestone (2026-07-28) rather than
backfilling the full project history; for earlier work, see the
[Releases](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases). Entries up
to 2026-09-24 were written in the private development repository; the issue numbers they
cite (e.g. Issue #80) refer to it — see [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## 2026-09-25 — Public repository

SAPI is published in this new public repository, built from the private development
repository with one commit per release in chronological order (10 release commits, 11
tags), every tree compared with its original tag and audited for credentials. The
deployed web interface, 12 commits ahead of `webserver-v1.0.0`, is released as
`webserver-v1.1.0`. The gateway binary is not published because it embeds credentials.
Documentation curated into `docs/`, with a system overview, a provenance record and
component READMEs for the gateway, the web interface and the hardware; bench-test photos
re-encoded without EXIF metadata. Details in [`docs/PROVENANCE.md`](docs/PROVENANCE.md).

## 2026-09-24 — Bilingual README

The former `README.md` moved to [`README-en.md`](README-en.md) (`git mv`, history
preserved) and a full Portuguese version was added as [`README-pt.md`](README-pt.md).
The new `README.md` is a short landing page that links to both and states that all code,
comments and technical documentation are in English while the README is also available in
Portuguese, the language of the dissertation. Part of the pre-public-release audit
tracked in `Documentation/PUBLIC-RELEASE-CHECKUP-2026-09.md` (private development repository).

## 2026-09-12 — Predictive models retrained and redeployed

The production M4/M6 pipelines had been running the May/2026 models: thresholds
50/60/75 cm, training sliced to flood windows only, the v2 event catalogue, no
sensor-artifact mask and Station-02 rain dumped into a single 5-min step. None of
the five corrections behind the current published results had reached them.

Training now runs through the same code that produced those results
(`train_production_from_backtest.py` imports the backtest `config` and `real_utils`),
instead of a separate re-implementation that had drifted. Both models were retrained on
the full record — 177,154 steps — and deployed on 2026-09-12 13:08 UTC, with thresholds
moved to 60/75/90 cm and the Issue #124 rain spread added to the inference path so the
models are served the series they were trained on.

Validated by replaying the 2026-09-11 flood, which the training data (ending 09-09)
never saw: the old M6 forecast up to 130.7 cm for a flood that peaked at 100 cm and
declared Inundação with the river at 61 cm, while the new one peaks at 100.5 cm and
fires 5–10 minutes after each crossing. Releases `model4-lgbm-v2.0.0` and
`model6-mlr-v2.0.0` carry the models, their provenance sidecars, the full training code
and the data snapshot. Issues #124, #223, #225 and #227 are closed for production.

## 2026-09-08 — Public-release documentation overhaul

Prepared `README.md` and `docs/system-overview.md` for the repository's public release: added
direct release links, official license logos, a "What is SAPI?" overview and
architecture figures sourced from the dissertation, and a citation section —
and corrected inaccuracies that had crept into both files (a 48h STM32 flash
buffer described as implemented when it isn't; an incomplete objectives list;
a stale June 2026 defense date). Work is tracked step-by-step in
`Documentation/README-public-release-checklist.md` (private development repository).

## 2026-08-29 — Chart color conflicts and MERGE data-quality fix (Issues #205, #207, #209)

- Guarded MERGE precipitation stats against an undefined array index that
  produced a PHP warning when upstream CPTEC data lagged.
  (PR #206)
- Reworked `view.php` chart colors to resolve two visual conflicts: the
  filtered Δ series (orange → purple) clashed with the ±σ band, and the raw
  data series (yellow/amber → teal) clashed with MERGE's existing cyan.
  (PR #208,
  PR #210)

## 2026-08-22 — Station-03 power instability incident documented (Issues #202, #203)

Root-caused and mechanically repaired an intermittent power/connector fault on
Station-03 that produced bad ~335cm readings and a false-alert email
avalanche; measurements between 2026-08-20 13:46 and 2026-08-22 10:07:46 are
flagged invalid. Full write-up in
[`docs/hardware/station-03-power-instability-2026-08/README.md`](docs/hardware/station-03-power-instability-2026-08/README.md).
(PR #204)

## 2026-08-20 — Kalman filter retired

Removed Kalman smoothing entirely from level charts and the filter cron job;
the existing delta filter (`level_delta_cm`) is now the only filtered series
used anywhere in the system, including as the real-time alert-trigger input
(see the 2026-08-13 entry below).
(PR #201)

## 2026-08-16 — Retrospective forecast verification and formatter tooling

Added a per-alert view to `predictions.php` showing whether a fired
predictive alert's forecast actually came true (predicted vs. observed level
per horizon, predicted vs. actual threshold-crossing time), plus an aggregate
accuracy card and pagination on the transitions table.
(PR #199)

Also added `.clang-format`/`black` formatter configuration for the project,
replacing a dead VS Code-only formatting instruction in `docs/system-overview.md`.
(PR #200)

## 2026-08-13 — Alert trigger switched to the delta filter (Issue #63)

Fixed the real-time alert engine to use `level_delta_cm` instead of the
Kalman-filtered series as its trigger input.
(PR #196)

## 2026-08-12 — Predictive alert notification fixes (Issues #190, #193)

- Predictive alert emails now embed their chart inline via PHPMailer
  Content-ID instead of referencing a station-scoped static URL that got
  overwritten by the next alert.
  (PR #191)
- Predictive alert notifications are now held until the episode normalizes,
  fixing a message flood caused by the level oscillating around a threshold.
  (PR #194)

## 2026-08-04 — Official license logos

Added the official AGPLv3 logo and a generic Open Source Hardware gear mark
to `docs/licensing/logos/`, for use in the README and presentations.
(PR #188)

## 2026-07-28 — Open-source licensing (Issue #80)

Published the project under a formal open-source license as part of the
master's thesis. Previously the repository had no `LICENSE` file, meaning
all rights were reserved by default.

- **Software**: [AGPL-3.0-or-later](LICENSE) — root `LICENSE`, root
  [`NOTICE`](NOTICE) crediting third-party dependencies, SPDX license
  header on all own source files (`App/`, `AppTest/`).
  (PR #184)
- **Hardware**: [CERN-OHL-S-2.0](LICENSES/CERN-OHL-S-2.0.txt) for the KiCAD
  PCB designs published on `main` (Shield Morpho V1.2, LoRa Arduino Shield
  V1.0).
  (PR #183)
- Retroactively extended the applicable license to all 11 GitHub Releases
  published before this date, via a note added to each release description.
- Full rationale and third-party dependency compatibility audit:
  [`docs/licensing/SAPI_Licensing_Report.md`](docs/licensing/SAPI_Licensing_Report.md).
