# Documentation

Documents are in English unless marked **(pt)**; a few were written in Portuguese, the
language of the dissertation, and are kept as they are.

## Start here

- [`system-overview.md`](system-overview.md) — stations, gateway, communication,
  requirements, software stack, known limitations
- [`PROVENANCE.md`](PROVENANCE.md) — how this repository was built from the private
  development repository, what was changed and what was left out
- [`architecture/`](architecture/) — network topology and station location map
  ([PDF](architecture/mapa-localizacao-estacoes.pdf))

## Web interface

- [`webserver/deployment-guide.md`](webserver/deployment-guide.md) — installing on shared hosting
- [`webserver/webserver-design.md`](webserver/webserver-design.md) — design and database
- [`webserver/alert-systems-overview.md`](webserver/alert-systems-overview.md) — the alert
  systems (observed-level thresholds and predictive alerts)
- [`webserver/predictions-forecast-verification.md`](webserver/predictions-forecast-verification.md)
  — retrospective verification of fired forecasts
- [`webserver/compare-tool-guide.md`](webserver/compare-tool-guide.md) — the station comparison tool

## Predictive models

- [`predictive-models/production_pipeline_guide.md`](predictive-models/production_pipeline_guide.md) — M4 (LightGBM) in production
- [`predictive-models/production_pipeline_m6_guide.md`](predictive-models/production_pipeline_m6_guide.md) — M6 (MLR) in production
- [`predictive-models/limiares_e_catalogo_v3.md`](predictive-models/limiares_e_catalogo_v3.md) **(pt)** — thresholds and the v3 event catalogue
- [`predictive-models/artefatos_catalogo_v3.md`](predictive-models/artefatos_catalogo_v3.md) **(pt)** — the sensor artifacts excluded from the catalogue

The code, results and audit report are in [`../predictive-models/`](../predictive-models/).

## Hardware

- [`hardware/BOM_custos.md`](hardware/BOM_custos.md) **(pt)** — bill of materials and costs
- [`hardware/station-03-power-instability-2026-08/`](hardware/station-03-power-instability-2026-08/README.md)
  — diagnosis of the Station-03 power/connector fault of August 2026

The KiCad projects are in [`../hardware/`](../hardware/).

## Bench and field tests

- [`tests/us-100/`](tests/us-100/) — US-100 ultrasonic sensor, serial mode (tests 01–04) and
  trigger/echo mode, with photos and readings
- [`tests/m2m/`](tests/m2m/M2M_Test_Report.md) — NB-IoT/LTE-M cellular tests of the gateway
  ([pt](tests/m2m/M2M_Test_Report_Portuguese.md)); modem logs in the same folder, SIM and
  modem identifiers masked
- [`tests/notifications-m4-m6/`](tests/notifications-m4-m6/notification_test_m4_m6.md) —
  Telegram and e-mail notifications of the predictive alerts

## Licensing

- [`licensing/SAPI_Licensing_Report.md`](licensing/SAPI_Licensing_Report.md) — why
  AGPL-3.0-or-later for software and CERN-OHL-S-2.0 for hardware, and the dependency
  compatibility audit
