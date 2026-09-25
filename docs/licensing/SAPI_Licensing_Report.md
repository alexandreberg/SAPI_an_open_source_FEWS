# SAPI — Open-Source Licensing Report

**Author**: Alexandre Nuernberg  
**Institution**: IFSC — Federal Institute of Santa Catarina, Florianópolis Campus  
**Program**: Master's Program in Climate and Environment  
**Date**: April 2026  
**Tracking issue**: #80

---

## 1. Introduction

The SAPI (Sistema de Alerta Prévio de Inundações) project is being published as open source as part of a master's thesis. The project encompasses several artifact types:

- **Embedded firmware** — C/C++ code for STM32 and ESP32 microcontrollers (PlatformIO/Arduino framework)
- **Web interface** — PHP server-side application for data visualization and alert management
- **Data processing scripts** — Python scripts for MERGE ingestion, data quality, and predictive modeling
- **Hardware designs** — KiCAD 9 PCB schematics (added in issue #151); Fusion 360 CAD files TBD

Choosing the correct license matters for three reasons specific to this project:

1. **Scientific reproducibility** — The thesis committee, reviewers, and future researchers must be able to inspect, replicate, and verify every component of the system that generated the thesis data.
2. **Public-good protection** — A flood early warning system serves the public interest. Keeping the ecosystem open ensures that improvements made by governments, NGOs, or companies flow back to the community.
3. **Academic traceability** — The license is part of the permanent record of what was published, when, and under what terms.

---

## 2. License Categories

### 2.1 Permissive Licenses (MIT, Apache 2.0, BSD)

Permissive licenses place almost no restrictions on what recipients can do with the code.

| Property | Detail |
|----------|--------|
| Can use commercially | Yes |
| Can modify | Yes |
| Must share modifications | **No** |
| Must credit original author | Yes (attribution) |
| Patent protection | Apache 2.0 includes explicit patent grant; MIT/BSD do not |

**Examples**: Arduino core, most Arduino libraries, Python packages (NumPy, pandas, scikit-learn), the Linux kernel modules ecosystem.

**Pro**: Maximum adoption. Zero friction for companies or governments wanting to use the code.  
**Con**: Nothing legally prevents a company from taking the code, improving it, and never sharing those improvements.

---

### 2.2 Weak Copyleft (LGPL — GNU Lesser General Public License)

LGPL is designed for **libraries**. It allows using the library inside proprietary software without triggering copyleft, but modifications *to the library itself* must be released.

| Property | Detail |
|----------|--------|
| Use as library in proprietary code | Yes (this is the key relaxation) |
| Modify and redistribute | Must share modifications to the LGPL component |
| Link dynamically from proprietary code | Allowed |

**Example**: Ultimaker's Cura slicer uses LGPL, which allows third-party plugin developers to sell proprietary paid plugins.

**Relevance to SAPI**: TinyGSM (LGPL 2.1) is used in the gateway firmware. SAPI's own code can be under AGPL v3 and still use TinyGSM because LGPL libraries are compatible with AGPL.

---

### 2.3 Strong Copyleft (GPL v3 — GNU General Public License)

GPL is the classic copyleft license. If you distribute a product that contains GPL code, you **must** release the complete corresponding source code under GPL v3.

| Property | Detail |
|----------|--------|
| Distribute binary product | Must release all source code |
| Modify and redistribute | Must release under GPL v3 |
| Network use (SaaS/server) | **Not covered** — the server-side loophole |
| Patent retaliation | Included |

**Server-side loophole**: If someone runs GPL software on a server and users access it over a network, they are not "distributing" the software in the legal sense. They are not required to release the source code. This is a significant gap for a project like SAPI that has a web interface.

---

### 2.4 Network Copyleft (AGPL v3 — GNU Affero General Public License)

AGPL v3 is GPL v3 with one additional clause (Section 13): if you run a modified version of the software **over a network** and users interact with it, you must offer them the complete source code. This closes the server-side loophole.

| Property | Detail |
|----------|--------|
| Distribute binary product | Must release source under AGPL v3 |
| Run modified version as web service | **Must offer source code to users** |
| Patent retaliation | Included (inherits from GPL v3) |
| Compatible with GPL v3 | Yes (one-way: AGPL can use GPL; GPL cannot use AGPL) |

**Why this matters for SAPI**: The web interface (PHP) runs on a server. If a municipal government or company deploys a modified version of SAPI's web interface, AGPL v3 requires them to publish their modifications. GPL v3 alone would not cover this scenario.

---

### 2.5 Hardware Licenses (for future reference)

Software licenses were not designed for hardware designs. Two dedicated options exist:

#### CERN Open Hardware Licence v2 (CERN OHL v2-S — Strongly Reciprocal)

The hardware equivalent of AGPL v3. Developed by CERN for scientific instruments.

- If you manufacture and distribute a product based on CERN OHL v2-S hardware designs, you must release the design sources.
- Covers: schematics, PCB layouts, mechanical drawings, BOMs (bills of materials).
- Widely used in open scientific hardware (particle physics, astronomy instruments).
- Website: [ohwr.org/cernohl](https://ohwr.org/cernohl)

#### Creative Commons BY-SA 4.0

Simpler and more widely understood. The "SA" (ShareAlike) clause is the copyleft equivalent for creative works including hardware documentation and schematics.

- Easier to communicate to non-engineers.
- Used by: Arduino (hardware), many maker community projects.
- **Limitation**: Not specifically designed for hardware; less precise about what "source files" means for PCBs.

#### Recommendation for SAPI hardware (when KiCAD/CAD files are added)

**CERN OHL v2-S** for PCB schematics and layouts (KiCAD files).  
**CC BY-SA 4.0** is an acceptable alternative if simplicity is preferred.  
For Fusion 360 / STEP files: publish both `.f3d` (full parametric editability) and `.step` (open ISO 10303 standard, readable by any CAD tool including FreeCAD). Fusion 360 licenses the tool, not your designs — you own and can freely distribute what you create.

---

## 3. Real-World Examples: The 3D Printer Case Study

The 3D printer ecosystem illustrates all license types in practice and the consequences of each choice.

| Company / Project | License | Behavior | Outcome |
|---|---|---|---|
| **Marlin firmware** | GPL v3 | Base firmware for most FDM printers | Everyone who builds on Marlin must release source |
| **Prusa Research** | GPL v3 | Fully embraces open source; publishes all firmware modifications on GitHub | True open source; community trusts and contributes back |
| **Creality** | GPL v3 (violated) | Used Marlin for years without releasing modifications | Community called them out; eventually released incomplete code under sustained pressure |
| **Ultimaker / Cura** | LGPL v3 | Slicer software; uses LGPL so plugin ecosystem can be proprietary | Paid plugins exist legally; base slicer stays open |
| **BambuLab** | Proprietary | Closed-source firmware; only recently opened parts under pressure | Community cannot audit or modify the printer |

**Key insight from Creality**: GPL copyleft enforcement depends on the community applying social and legal pressure. It is not automatic. For a public-good project like SAPI, the copyleft clause is most valuable as a clear signal of intent — and as a legal mechanism if a well-resourced actor ever commercializes the system.

---

## 4. Third-Party Dependency Audit

All SAPI dependencies must be **compatible** with AGPL v3. A dependency is compatible if its license allows it to be combined with AGPL v3 code. MIT, BSD, Apache 2.0, and LGPL are all compatible with AGPL v3.

### 4.1 Firmware (C/C++ — PlatformIO)

| Library | Author | License | Component | Compatible with AGPL v3 |
|---------|--------|---------|-----------|------------------------|
| Arduino-LoRa | Sandeep Mistry | MIT | Station-02, 03, Gateway-01 | ✅ Yes |
| TinyGSM | Volodymyr Shymanskyy | LGPL 2.1 | Gateway-01 | ✅ Yes |
| StreamDebugger | Volodymyr Shymanskyy | MIT | Gateway-01 | ✅ Yes |
| ArduinoJson | Benoit Blanchon | MIT | Gateway-01 | ✅ Yes |
| SSLClient | Open Source Labs (OSU) | MIT | Gateway-01 | ✅ Yes |
| ArduinoHttpClient | Arduino Libraries | Apache 2.0 | Gateway-01 | ✅ Yes |
| NewPing | Tim Eckel | MIT | Station-02 | ✅ Yes |
| RTClib | Adafruit / JeeLabs | MIT | Station-02, 03 | ✅ Yes |
| Adafruit BMP280 | Adafruit | BSD | Station-02, 03 | ✅ Yes |
| STM32duino Low Power | STMicroelectronics | BSD | Station-02, 03 | ✅ Yes |
| STM32duino RTC | STMicroelectronics | BSD | Station-02, 03 | ✅ Yes |
| DFRobot SHT20 | DFRobot | MIT | Station-03 | ✅ Yes |

### 4.2 Web Interface (PHP)

| Package | Author | License | Compatible with AGPL v3 |
|---------|--------|---------|------------------------|
| rybakit/msgpack | Eugene Batyaev | MIT | ✅ Yes |
| phpunit/phpunit (dev) | Sebastian Bergmann | BSD 3-Clause | ✅ Yes |
| phpmailer/phpmailer | PHPMailer contributors | LGPL-2.1 | ✅ Yes |

> Added `phpmailer/phpmailer` during issue #80 implementation — used by
> `webserver/composer.json` and `webserver/cron/composer.json` for
> alert emails, but was missing from the original April audit above.

### 4.3 Data Processing (Python)

| Package | License | Compatible with AGPL v3 |
|---------|---------|------------------------|
| pandas | BSD 3-Clause | ✅ Yes |
| numpy | BSD 3-Clause | ✅ Yes |
| scipy | BSD 3-Clause | ✅ Yes |
| scikit-learn | BSD 3-Clause | ✅ Yes |
| matplotlib | PSF/BSD-style | ✅ Yes |
| sqlalchemy | MIT | ✅ Yes |
| python-dotenv | BSD 3-Clause | ✅ Yes |
| pymysql | MIT | ✅ Yes |
| mysql-connector-python | GPL 2.0 | ✅ Yes (GPL is compatible with AGPL) |
| darts | Apache-2.0 | ✅ Yes |
| lightgbm | MIT | ✅ Yes |
| requests | Apache-2.0 | ✅ Yes |

> Added `darts`, `lightgbm`, and `requests` during issue #80 implementation —
> these are the actual pinned dependencies of the production predictive-model
> pipelines (`predictive-models/production/requirements_production.txt`
> for Model4-LGBM, issue #108; `.../production_m6/requirements_production_m6.txt`
> for Model6-MLR, issue #120), which were deployed after the original April
> audit above and were missing from it.

**Conclusion**: All dependencies are compatible with AGPL v3. No license conflicts exist.

---

## 5. Decision and Rationale

### Chosen License: GNU Affero General Public License v3.0 (AGPL v3)

**Applied to**: All software components — embedded firmware (C/C++), web interface (PHP), data processing scripts (Python).

**Hardware**: **CERN OHL v2-S** applied to KiCAD 9 PCB designs (issue #151). Fusion 360 CAD files deferred.

### Why AGPL v3

| Factor | Analysis |
|--------|----------|
| Public-good mission | SAPI serves communities at flood risk. Copyleft ensures improvements by governments or companies flow back, not into proprietary products. |
| Web interface exists | GPL v3 alone has the server-side loophole. AGPL v3 covers it: if someone deploys a modified SAPI web interface, they must publish the source. |
| All dependencies compatible | Every library used (MIT, BSD, LGPL, Apache 2.0) is compatible with AGPL v3. No conflicts, no re-licensing required. |
| Single license for everything | One AGPL v3 covers firmware + web + Python. Simpler to communicate, simpler to enforce. |
| IP ownership clear | The project IP belongs entirely to the student/author. No institutional approval needed. |
| Academic reproducibility | The copyleft clause guarantees that derivative works remain inspectable — important for scientific verification. |

### What AGPL v3 does NOT restrict

- Reading, running, and studying the code — always free
- Contributing back via pull requests — always welcome
- Using the system for flood monitoring — always free, commercial or not
- Publishing papers that cite the system — always free

What it *does* require: anyone who **distributes** a modified version or **runs it as a network service** must publish their source code under AGPL v3.

---

## 6. Implementation Checklist

The following tasks must be completed to properly apply AGPL v3 to the repository. Tracked in issue #80.

- [x] Add `LICENSE` file at repository root — full AGPL v3 text (from [gnu.org/licenses/agpl-3.0.txt](https://www.gnu.org/licenses/agpl-3.0.txt))
- [x] Add SPDX license identifier header to each source file:
  - C/C++ firmware files: `// SPDX-License-Identifier: AGPL-3.0-or-later`
  - PHP files: `// SPDX-License-Identifier: AGPL-3.0-or-later`
  - Python files: `# SPDX-License-Identifier: AGPL-3.0-or-later`
- [x] Add copyright line to each file header: `// Copyright (C) 2024–2026 Alexandre Nuernberg`
- [x] Add license badge and section to `README.md`
- [x] Add `NOTICE` file at root crediting key third-party dependencies and their licenses
- [x] Add `LICENSES/` directory with CERN OHL v2-S text (hardware files now published in issue #151)

> Items above implemented in issue #80 (branch `feature/issue-80-agpl-license`).

### Recommended file header (C/C++ example)

```cpp
/**
 * @file    main.cpp
 * @brief   Station-03 firmware — water level monitoring with US-100 sensor
 *
 * SPDX-License-Identifier: AGPL-3.0-or-later
 * Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
```

### Recommended file header (Python example)

```python
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
```

---

## 7. Hardware Licensing

KiCAD 9 PCB designs (SAPI LoRa Arduino Shield V1.0 and Rain Gauge ST Morpho Shield V1.2) were added to the repository in issue #151 under **CERN OHL v2-S**. Fusion 360 / STEP mechanical CAD files are still to be added.

### Applied License — CERN OHL v2-S

- Full name: *CERN Open Hardware Licence Version 2 — Strongly Reciprocal*
- Hardware equivalent of AGPL v3 (strong copyleft for physical designs)
- Requires: anyone who manufactures and distributes a product based on the designs must release their design sources
- Used by: CERN scientific instruments, many open scientific hardware projects
- Text: [ohwr.org/project/cernohl](https://ohwr.org/project/cernohl)

### Alternative considered — Creative Commons BY-SA 4.0

- Simpler, more widely understood
- ShareAlike clause is the copyleft equivalent for creative works
- Less precise about what constitutes "source" for hardware (gerber files? KiCAD project? BOM?)
- Used by: Arduino hardware, many maker projects

### Note on Fusion 360 and STEP files

Autodesk licenses the **software** (Fusion 360), not the **designs** you create with it. You own your designs and may distribute them under any license. For maximum compatibility:

- Publish `.f3d` files for full parametric editability (requires Fusion 360)
- Publish `.step` files (ISO 10303) for tool-agnostic compatibility — readable by FreeCAD, SolidWorks, Onshape, and any other CAD application

This is analogous to writing a document in Microsoft Word and distributing the PDF — Microsoft owns Word, but you own the document.

---

## 8. License Logos (for presentations)

Official-source logo files (not tiny web badges) are kept in
[`docs/licensing/logos/`](logos/) for use in slides, posters, and the
dissertation defense presentation.

| File | Represents | Size | Source | License of the logo itself |
|------|------------|------|--------|------------------------------|
| `logos/agplv3-with-text-162x68.png` | Software license (AGPL-3.0-or-later) | 162×68 px, the largest raster size FSF publishes | [gnu.org/graphics/agplv3-with-text-162x68.png](https://www.gnu.org/graphics/agplv3-with-text-162x68.png) | Public domain (FSF license-logos page) |
| `logos/lgpl-agpl-v3-logos.svg` | Software license (AGPL-3.0-or-later), vector source | Scalable — crop/extract the AGPL mark in Inkscape/Illustrator for print-quality enlargement beyond 162×68 | [gnu.org/graphics/lgpl-agpl-v3-logos.svg](https://www.gnu.org/graphics/lgpl-agpl-v3-logos.svg) | Public domain (FSF license-logos page) |
| `logos/open-source-hardware-logo.svg` | Hardware license (CERN-OHL-S-2.0) — generic stand-in, see note below | Scalable vector | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Open-source-hardware-logo.svg) | CC-SA / public domain (simple geometric mark) |

**Important note on the hardware logo**: unlike the GNU project, **CERN does not
publish a dedicated logo/mark for CERN-OHL-S-2.0** specifically (checked
[ohwr.org/licences](https://ohwr.org/licences/), CERN's OHL site, and the
Wikipedia article — none carry a license-specific graphic, only the license
text/PDF). The gear logo above is the community "Open Source Hardware" (OSHW)
mark designed by Macklin Chaffee, used generically to indicate hardware that
complies with the Open Source Hardware Definition — it is **not**
CERN-specific and doesn't name the exact license variant. If the presentation
needs the license identified unambiguously, pair the gear icon with the text
"CERN-OHL-S-2.0" rather than presenting the gear alone as if it were an
official CERN mark.

---

## 9. References

| Resource | URL |
|----------|-----|
| AGPL v3 full text | https://www.gnu.org/licenses/agpl-3.0.html |
| GPL v3 full text | https://www.gnu.org/licenses/gpl-3.0.html |
| LGPL v2.1 full text | https://www.gnu.org/licenses/lgpl-2.1.html |
| Choose a License (GitHub) | https://choosealicense.com |
| SPDX License List | https://spdx.org/licenses/ |
| CERN OHL v2 | https://ohwr.org/cernohl |
| Creative Commons BY-SA 4.0 | https://creativecommons.org/licenses/by-sa/4.0/ |
| Open Source Initiative | https://opensource.org/licenses |
| License compatibility chart | https://www.gnu.org/licenses/license-compatibility.html |

---

*This document was produced as part of the SAPI master's thesis research. It serves as both a decision record and a reference for contributors and reviewers.*
