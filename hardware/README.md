# Hardware — KiCad projects

KiCad 9 projects of the two custom shields used by the SAPI stations. Both are
fabrication-ready (gerbers in `gerber_to_order/`) and licensed under
[CERN-OHL-S-2.0](../LICENSES/CERN-OHL-S-2.0.txt).

| Project | Release | What it does |
|---------|---------|--------------|
| [`morpho-shield-v1.2/`](morpho-shield-v1.2/) | `shield-morpho-v1.2.0` | ST Morpho interface board: tipping-bucket rain-gauge pulse counting, serial and trigger/echo ultrasonic sensor interfaces (US-100, HC-SR04, AJ-SR04M), I²C sensor bus (SHT20, BMP280), ADC for solar-panel and battery voltages, ST-Link connector, switched 3.3 V/5 V rails, 5 spare GPIOs |
| [`lora-arduino-shield-v1.0/`](lora-arduino-shield-v1.0/) | `shield-lora-arduino-v1.0.0` | Arduino-footprint radio shield for RFM69HC and LilyGo LoRa32 modules (any frequency; SAPI uses 915 MHz), with a debug LED that can be disabled for low power, a reset button and reconfigurable GPIOs |

## Git LFS and the 3D models

The 3D models (`*.step`, `*.stp`, `*.stl`, `*.wrl`, and zipped models) are stored in
**Git LFS**, ~0.9 GB in total. To clone without them:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/alexandreberg/SAPI_an_open_source_FEWS.git
```

KiCad opens the projects without the models; only the 3D viewer needs them. Each release
also has the complete project, models included, as a `.tar.gz` attachment.

## Third-party content

The SAPI design files (schematics, layouts, gerbers, BOM) are the author's work. The
projects also contain material **not** authored here, which keeps its original terms and
is not covered by the CERN-OHL-S licence:

- **3D models** (80 files per project) downloaded from CAD-sharing sites — folders named
  `*.snapshot.N` follow their download naming — made in SolidWorks, CATIA, FreeCAD,
  PRO/ENGINEER, the ASCON kernel and KiCad StepUp. Among them: the STM32 BluePill model,
  BME280/BMP280 modules, an SW868 antenna, 2.54 mm jumpers and pin headers, tactile and
  push switches, an optocoupler.
- **Symbol and footprint libraries** from SnapEDA and Digi-Key (`Project_Libraries/`,
  `Libraries/`).
- **Datasheets** of the 74HC166, CD4020BC, CD4040BEE4 and TIL133
  (`morpho-shield-v1.2/datasheets/`).

Their licences were not individually verified. If you are a rights holder and want a file
removed, please open an issue.
