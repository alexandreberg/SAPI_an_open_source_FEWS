# Station Comparison Tool — Guide and Use Cases

*Implemented: 2026-03-21 | Issue #56*
*Screenshots: `compare-tool-examples-2026-03-21/`*

---

## What is the Comparison Tool?

The **Comparar** page (`/sapi/compare.php`) allows overlaying time series from
multiple stations on a single chart. It is accessible directly from the sidebar
navigation.

### Controls

| Control | Description |
|---|---|
| **Estações** | Checkbox list — select any combination of stations |
| **Variável** | Single variable to compare across all selected stations |
| **Início / Fim** | Date range filter (same as `view.php`) |
| **+ MERGE** | Overlay MERGE `prec_mm` on a secondary Y axis |
| **Gerar** | Submit and render chart |

Each station gets a distinct color. MERGE precipitation uses teal on the right
Y axis. The chart supports zoom (scroll wheel), pan, image download, and CSV
export.

---

## Use Cases and Examples

### 1. Cross-sensor validation — Water level (all stations)

**Screenshot:** `143318.png`, `143342.png`

Both ultrasonic sensors (Station-01 HC-SR04 and Station-03 US-100) measure the
same river. Overlaying `level_cm` from both stations shows:

- Consistent level shapes during the same rain event
- Time offset between stations (they are ~30 m apart along the river course)
- Cross-validation: if both sensors peak at the same time with similar amplitude,
  the readings are credible; if one spikes alone it is likely a spurious echo

This is a direct empirical validation of sensor agreement — essential for the
thesis methodology chapter.

---

### 2. Power system diagnosis — Battery voltage delay (Station-02 vs Station-03)

**Screenshot:** `143507.png`

Comparing `bat_voltage` across Station-02 and Station-03 reveals a clear
anomaly: Station-02 battery continues discharging for ~1 hour after sunrise
before the charger begins bulk charge. Station-03 (with EPEVER Tracer2606BP)
shows a tighter recovery curve.

**Diagnosis:** The delay in Station-02 suggests the solar charger is not
triggering bulk charge at the correct panel/battery voltage threshold. This may
indicate a charger configuration mismatch or undersized panel.

**Thesis significance:** Demonstrates that multi-station power telemetry
(`bat_voltage`, `panel_voltage`) enables remote power system diagnostics
without field visits — a key advantage of the SAPI architecture.

> **Note:** The EPEVER Tracer2606BP on Station-03 also has a pending TODO:
> configure for lithium battery profile (currently likely in lead-acid mode).
> The battery voltage comparison provides empirical evidence that this
> configuration matters and should be corrected.

---

### 3. Precipitation influence on solar panel output

**Screenshot:** `143559.png`

Comparing `panel_voltage` across stations with MERGE `prec_mm` overlay shows:

- Characteristic daily sawtooth curve (sunrise → peak → sunset)
- Voltage dips that correlate with precipitation events in the MERGE data
- Cloud cover during rain events reduces panel output, which in turn reduces
  charging current — visible as a flattened or dipped sawtooth

This correlation is quantifiable and relevant for sizing solar systems for
continuous monitoring stations in a humid subtropical climate (SC).

---

### 4. RSSI correlation with weather events

**Screenshot:** `143405.png`

Comparing `rssi` across all three stations + MERGE precipitation shows:

- Station-01 maintains stable signal (~-73 dBm) — short, clear LoRa path
- Station-02 and Station-03 show more variation
- Transient RSSI changes appear to correlate with precipitation events,
  possibly due to atmospheric refraction effects on the 915 MHz band

**Thesis note:** LoRa signal quality under precipitation is a documented
phenomenon. This data could support a short analysis of link reliability
as a function of weather conditions.

---

### 5. Solar panel voltage — multi-station charging pattern

**Screenshot:** `143527.png`

Overlaying `panel_voltage` for Station-02 and Station-03 shows the daily
charging cycle for each solar installation. Differences in peak voltage and
curve shape reflect differences in panel orientation, shading, and charger
MPPT efficiency. Consistent with local sunrise/sunset times.

---

## Recommended comparison groups (thesis)

| Group | Variables | Stations | Purpose |
|---|---|---|---|
| Level cross-validation | `level_cm` | 01, 03 + MERGE | Sensor agreement + rain-level correlation |
| Power health | `bat_voltage`, `panel_voltage` | 02, 03 | Charger performance |
| Signal reliability | `rssi` | 01, 02, 03 + MERGE | Link quality vs weather |
| Temperature environment | `temperature_C`, `surface_temperature_C` | 02, 03 | Microclimate comparison |

---

## Technical notes

- Data is fetched independently per station — timestamps are not aligned.
  Chart.js time scale handles different sampling intervals transparently.
- Physical range limits are applied before rendering (same as `view.php`):
  outlier values from firmware crashes are excluded.
- MERGE `prec_mm` uses the secondary Y axis (right side) to preserve scale
  independence between level/voltage/signal and precipitation.
- CSV export includes all visible series aligned by timestamp.

---

*Last updated: 2026-03-21*
