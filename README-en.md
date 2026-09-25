# SAPI — Sistema de Alerta Prévio de Inundações

🇬🇧 **English** · 🇧🇷 [Leia em português](README-pt.md)

A LoRa-based flood early warning system: water level and rain gauge stations
report to a LoRa gateway, which forwards readings to a cloud backend that runs
machine-learning flood forecasts and issues multi-channel alerts.

## What is SAPI?

SAPI (*Sistema de Alerta Prévio de Inundações* — Flood Early Warning System) is a
low-cost, open-source flood monitoring and early-warning platform, developed and
validated as a Master's dissertation project. It targets a documented gap: the
effectiveness of flood early-warning systems depends on articulating risk
knowledge, real-time monitoring and forecasting, alert dissemination, and response
capacity — components that developing countries and small municipalities often
lack the resources to implement in full. SAPI directly tackles the monitoring/
forecasting and alert-dissemination pillars with low-cost, replicable, open-source
hardware and software.

The system has been in continuous field operation since December 2024 (Station-01),
with two more stations brought online during 2026, along an urban stream in the
Cachoeira do Bom Jesus neighborhood, Florianópolis, Brazil — a site chosen for
practical development reasons, since building the hardware and firmware from
scratch involved many points of failure that needed easy field access to debug.
It combines:

- **Real-time in-situ sensing** — ultrasonic water-level stations (Station-01,
  Station-03) and a tipping-bucket rain-gauge station (Station-02), LoRa-linked to
  a gateway.
- **External data fusion** — CPTEC/MERGE satellite-estimated precipitation, used to
  build historical training data predating Station-02 and as a real-time fallback
  whenever Station-02 is unavailable.
- **Machine-learning flood-level forecasting** — two independently trained models
  (LightGBM and Multiple Linear Regression) predicting water level 30 to 120
  minutes ahead, validated by continuous backtesting over 21 months of record
  against a catalogue of 37 episodes — 28 confirmed hydrological events, 9
  excluded as sensor artifacts — under a chronological train/test split.
- **Two complementary alert layers** — an observed-level threshold system (no lead
  time, but no missed events) and a predictive-forecast system (lead time, gated by
  a rain-accumulation filter and a persistence filter) — both notifying by email
  and Telegram.
- **A web dashboard** — real-time and historical monitoring, plus station/contact/
  alert management.

This repository holds every released and deployed component of the dissertation —
embedded firmware, gateway, web interface, data pipelines, predictive-model
training/inference and PCB designs (see [Citation](#citation) and
[How this repository was built](#how-this-repository-was-built)).

**Dissertation objectives**:

- **General**: develop and validate a flood monitoring and early-warning system.
- **Specific**: (1) implement real-time monitoring of water level and
  precipitation; (2) apply a machine-learning model to predict flood level;
  (3) validate the system's prediction and alert performance in a real
  environment.

## About this project

- **Institution**: Federal Institute of Santa Catarina (IFSC) — Florianópolis Campus
- **Program**: Master's Program in Climate and Environment (*Stricto Sensu*)
- **Research Line**: Instrumentation and Technological Development
- **Student**: Alexandre Nuernberg
- **Status**: dissertation in its final writing stage; defense date to be scheduled

The project context and the hardware/software specifications are documented in [`docs/system-overview.md`](docs/system-overview.md). Notable project-level changes are tracked in
[`CHANGELOG.md`](CHANGELOG.md).

## System overview

- **Monitoring stations** — three STM32-based units transmitting over LoRa
  (915 MHz) (see [Releases](#releases)): Station-01 (grid-powered, water level,
  HC-SR04 ultrasonic, operating since Dec 2024) and Station-03 (solar-powered,
  water level, US-100 ultrasonic, since Mar 2026) measure river level; Station-02
  (solar-powered, tipping-bucket rain gauge, since Jan 2026) measures
  precipitation.
- **LoRa gateway** — ESP32-based receiver (LILYGO T-SIM7000G) that authenticates
  and decodes station packets (MessagePack + HMAC-SHA256) and forwards them to the
  cloud over Wi-Fi, with automatic NB-IoT cellular failover.
- **MERGE/CPTEC pipeline** — hourly ETL ingesting CPTEC/MERGE satellite-estimated
  precipitation, used to backfill historical training data and as a real-time
  fallback whenever Station-02 is unavailable.
- **Web interface** — PHP/MySQL application for real-time monitoring, historical
  data, station/contact/alert management, and a predictions dashboard.
- **Predictive models** — two independently trained models (LightGBM and Multiple
  Linear Regression) forecasting water level 30 to 120 minutes ahead.
- **Automated alerting** — two complementary layers: an observed-level threshold
  system (Atenção/Alerta/Inundação severity levels, immediate, no lead time) and a
  predictive-forecast alert system (lead time, gated by a rain-accumulation filter
  and a persistence filter) — both notifying registered contacts by email and
  Telegram.

See [`docs/system-overview.md`](docs/system-overview.md) for full hardware/software specifications of each component.

## Architecture

![Topologia da rede SAPI](docs/architecture/topologia-rede-sapi.png)

### Station locations

![Mapa de localização das estações](docs/architecture/mapa-localizacao-estacoes.png)

Stations 01 and 03 (water level) and Station 02 (precipitation) sit along the same
urban stream in the Cachoeira do Bom Jesus neighborhood, Florianópolis Norte — see
[`docs/system-overview.md`](docs/system-overview.md) for exact GPS coordinates. A higher-resolution
[PDF version](docs/architecture/mapa-localizacao-estacoes.pdf) of
this map is also available.

## Repository layout

| Path | Contents |
|------|----------|
| [`firmware/`](firmware/) | Station-01, Station-02, Station-03 (STM32, PlatformIO) and Gateway-01 (ESP32) |
| [`hardware/`](hardware/) | KiCad 9 projects of the two custom shields: schematics, layouts, gerbers, BOM and 3D models (Git LFS) |
| [`pipelines/merge2mysql/`](pipelines/merge2mysql/) | MERGE/CPTEC precipitation ingestion (FTP → CDO → MySQL) |
| [`webserver/`](webserver/) | PHP/MySQL web interface, alert cron jobs, API, database schema |
| [`predictive-models/`](predictive-models/) | M4 (LightGBM) and M6 (MLR): training, production inference, final backtest results and the audit PDF |
| [`docs/`](docs/) | System overview, architecture figures, deployment and design guides, bench tests, provenance |
| [`tools/`](tools/) | The credential audit run by pre-commit and CI |

## Releases

Each production component is tagged and published as a
[GitHub Release](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases),
typically with the compiled firmware, trained model, or source archive attached:

| Component | Tag | Contents |
|-----------|-----|----------|
| Station-01 (water level) | [`station-01-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/station-01-v1.0.0) | STM32 BluePill firmware |
| Station-02 (rain gauge) | [`station-02-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/station-02-v1.0.0) | STM32 Nucleo F103RB firmware |
| Station-03 (water level) | [`station-03-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/station-03-v1.0.0) | STM32 Nucleo L476RG firmware |
| Gateway-01 | [`gateway-01-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/gateway-01-v2.0.0) | ESP32 firmware — Wi-Fi primary + NB-IoT cellular failover |
| Shield Morpho V1.2 | [`shield-morpho-v1.2.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/shield-morpho-v1.2.0) | KiCad hardware design |
| SAPI LoRa Arduino Shield V1.0 | [`shield-lora-arduino-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/shield-lora-arduino-v1.0.0) | KiCad hardware design |
| MERGE2MySQL pipeline | [`merge2mysql-v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/merge2mysql-v1.0.0) | Precipitation ingestion scripts |
| Web Interface | [`webserver-v1.1.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/webserver-v1.1.0) | PHP/MySQL application source — the deployed version ([`v1.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/webserver-v1.0.0) is the first release) |
| Model4 (LightGBM) | [`model4-lgbm-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/model4-lgbm-v2.0.0) | Trained model + provenance sidecar + training code + data snapshot |
| Model6 (Multiple Linear Regression) | [`model6-mlr-v2.0.0`](https://github.com/alexandreberg/SAPI_an_open_source_FEWS/releases/tag/model6-mlr-v2.0.0) | Trained model + provenance sidecar + training code + data snapshot |

## Getting started

Each component has its own README with build/wiring/configuration details:

- Stations: [`firmware/station-01/`](firmware/station-01/README.md),
  [`firmware/station-02/`](firmware/station-02/README.md),
  [`firmware/station-03/`](firmware/station-03/README.md)
- Gateway: [`firmware/gateway-01/`](firmware/gateway-01/README.md) — no binary is
  published (it would embed Wi-Fi and API credentials); build it from
  `credentials_sample.h`
- MERGE/CPTEC pipeline: [`pipelines/merge2mysql/`](pipelines/merge2mysql/README.md)
- Web interface: [`webserver/`](webserver/README.md) (see
  [`docs/webserver/deployment-guide.md`](docs/webserver/deployment-guide.md))
- PCB designs: [`hardware/`](hardware/README.md)
- Predictive models (LightGBM / MLR): see
  [`predictive-models/README.md`](predictive-models/README.md) for the production
  entry points and setup. Production models are trained by
  [`train_production_from_backtest.py`](predictive-models/train_production_from_backtest.py),
  which runs the same code path as the backtest rather than a separate
  implementation. The flood catalog used for training/testing is
  [`results_final_m4_lgbm/event_windows_v3.csv`](predictive-models/results_final_m4_lgbm/event_windows_v3.csv)
  — 37 episodes, 28 valid; the summary M4-vs-M6 comparison plots are
  [`compare_m4_vs_m6.png`](predictive-models/results_final_m6_mlr/output/compare_m4_vs_m6.png)
  and
  [`lead_time_comparison_m4_vs_m6.png`](predictive-models/results_final_m6_mlr/output/lead_time_comparison_m4_vs_m6.png);
  the per-plot
  [`event_detected_NNN.png` → catalogued event mapping table](predictive-models/results_final_m4_lgbm/README.md#auto-detected-period--catalogued-event-mapping)
  is in the `results_final_m4_lgbm/README.md`.

Firmware is built with [PlatformIO](https://platformio.org/); the web interface
requires PHP and MySQL.

### Cloning without the 3D models

The KiCad projects carry ~0.9 GB of third-party 3D models in Git LFS. If you only
need the code, skip them:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/alexandreberg/SAPI_an_open_source_FEWS.git
```

The complete KiCad projects, 3D models included, are also attached to the
`shield-*` releases as `.tar.gz` files.

## How this repository was built

SAPI was developed in a private repository with ~520 commits of experiments. This
public repository was built from it on 2026-09-24 with **one commit per release, in
chronological order**, so every tag points at a tree in which its component is
exactly that version. Author dates are the original release dates; committer dates
are the import date. The development history stays private; issue numbers such as
`#80` in the release notes and documents refer to it.

Before each commit the tree was compared file by file with the original tag
(differences allowed: the licence headers added later and the replacement of the
hosting account id by `<HOSTINGER_USER>`) and audited for credentials. The details —
tag mapping, what was changed and what was left out — are in
[`docs/PROVENANCE.md`](docs/PROVENANCE.md).

## License

<a href="LICENSE"><img alt="AGPL v3" src="docs/licensing/logos/agplv3-with-text-162x68.png" height="60"></a>
<a href="LICENSES/CERN-OHL-S-2.0.txt"><img alt="Open Source Hardware" src="docs/licensing/logos/open-source-hardware-logo.svg" height="60"></a>

Copyright (C) 2024–2026 Alexandre Nuernberg.

- **Software** (firmware, web interface, Python scripts) — [GNU Affero General
  Public License v3.0 or later](LICENSE) (AGPL-3.0-or-later).
- **Hardware** (`hardware/` PCB designs) — [CERN Open Hardware Licence
  v2 — Strongly Reciprocal](LICENSES/CERN-OHL-S-2.0.txt) (CERN-OHL-S-2.0).

Third-party dependencies are credited in [`NOTICE`](NOTICE). See
[`docs/licensing/SAPI_Licensing_Report.md`](docs/licensing/SAPI_Licensing_Report.md)
for the full licensing rationale and dependency compatibility audit.

## Citation

If you use SAPI, its data, or its codebase in academic work, please cite:

> NUERNBERG, Alexandre. *Desenvolvimento e Validação do SAPI: Um Sistema
> Integrado de Monitoramento, Alerta e Predição de Inundações*. Dissertação
> (Mestrado) — Instituto Federal de Santa Catarina (IFSC), Programa de
> Pós-Graduação em Clima e Ambiente. Florianópolis, 2026. Defesa a ser
> agendada — verifique as [Releases](#releases) deste repositório para a
> versão do código associada à versão final do trabalho.

Machine-readable citation metadata is in [`CITATION.cff`](CITATION.cff) (GitHub shows it as *Cite this repository*).

## Author

Alexandre Nuernberg
