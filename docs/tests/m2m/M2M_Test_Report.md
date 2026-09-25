# SAPI — M2M Cellular Uplink Test Report

**Date:** 2026-03-03
**Author:** Alexandre Nuernberg
**GitHub Issue:** #37
**Sketch path:** `AppTest/gateways/gateway_M2M_test-01/` (test sketch, kept in the private development repository)

---

## 1. Purpose

Validate NB-IoT cellular uplink on the LilyGO T-SIM7000G hardware
using different SIM cards and frequency bands, confirming that data can be
transmitted from the field to the production SAPI server without WiFi.

Five SIM cards are available for testing, covering two operators and two
APN providers. For each SIM, all supported frequency bands will be tested
where possible (Band 28, Band 3, Band 8 — see Section 4).

---

## 2. Test Hardware

| Parameter         | Value                                      |
|-------------------|--------------------------------------------|
| Board             | LilyGO T-SIM7000G V1.1                     |
| MCU               | ESP32-D0WD-V3 rev3.1, 240 MHz, 4 MB Flash |
| PSRAM             | Enabled (`-DBOARD_HAS_PSRAM`)              |
| Modem             | SIMCOM SIM7000G firmware R1529             |
| USB-Serial port   | `/dev/ttyACM0`, 115200 baud                |
| Upload speed      | 921600 baud                                |

### 2.1 Modem Pin Mapping (LilyGO T-SIM7000G V1.1)

| Signal    | ESP32 GPIO | Direction        | Notes                                                    |
|-----------|-----------|------------------|----------------------------------------------------------|
| UART TX   | GPIO 27   | ESP32 → Modem    | AT command serial                                        |
| UART RX   | GPIO 26   | Modem → ESP32    | AT response serial                                       |
| PWRKEY    | GPIO 4    | ESP32 → Modem    | HIGH = PWRKEY active (transistor-inverted). Requires ≥ 1.5 s pulse to power on |
| DTR       | GPIO 25   | ESP32 → Modem    | Sleep control — not used in this sketch                  |
| LED       | GPIO 12   | ESP32 output     | Active LOW. Blinks briefly on HTTP 200                   |

### 2.2 LED Indicators

| LED                             | Behaviour                       | Meaning                         |
|---------------------------------|---------------------------------|---------------------------------|
| ESP32 onboard (GPIO 12)         | OFF (normal)                    | Running, no event               |
| ESP32 onboard (GPIO 12)         | Brief ON (~200 ms)              | HTTP 200 received successfully  |
| SIM7000G **STATUS** (red solid) | ON                              | Modem powered on                |
| SIM7000G **NETLIGHT** (red)     | Fast blink (~300 ms period)     | Searching for network           |
| SIM7000G **NETLIGHT** (red)     | Slow blink (1 s ON / 3 s OFF)  | Registered, data session active |
| SIM7000G **NETLIGHT** (red)     | OFF                             | Modem off or deep sleep         |

---

## 3. Software

### 3.1 PlatformIO Configuration

```ini
[env:esp32dev]
platform  = espressif32
board     = esp32dev
framework = arduino

build_flags =
    -DBOARD_HAS_PSRAM
    -DCORE_DEBUG_LEVEL=3
    -mfix-esp32-psram-cache-issue

lib_deps =
    vshymanskyy/TinyGSM          @ ^0.12.0
    vshymanskyy/StreamDebugger   @ ^1.0.1
    arduino-libraries/ArduinoHttpClient @ ^0.6.1
    bblanchon/ArduinoJson        @ ^7.4.2
    # mbedTLS is built into the ESP32 Arduino core — no extra lib needed
```

### 3.2 Key TinyGSM Define

```cpp
#define TINY_GSM_MODEM_SIM7000   // plain TCP, NOT SIM7000SSL — see Section 5.1
```

HMAC-SHA256 signing uses `mbedtls/md.h` (built into ESP32 Arduino core).

### 3.3 AT Command Modem Configuration

Applied inside a `CFUN=0 → settings → CFUN=1` cycle on every boot
(see Section 5.2 for why the CFUN cycle is mandatory):

| AT Command                  | Purpose                                              |
|-----------------------------|------------------------------------------------------|
| `AT+CFUN=0`                 | Disable radio — clears any stuck CGATT state         |
| `AT+CNMP=38`                | LTE only (no 2G/3G fallback)                         |
| `AT+CMNB=2`                 | NB-IoT (`2` = NB-IoT, `1` = LTE-M/CAT-M1, `3` = auto) |
| `AT+CBANDCFG="NB-IOT",28`  | Band 28 (700 MHz) — change per test, see table below |
| `AT+CFUN=1`                 | Re-enable radio with new settings                    |

**Band configuration for each NB-IoT test:**

| Target           | `AT+CMNB` | `AT+CBANDCFG`  |
|------------------|-----------|----------------|
| NB-IoT — Band 28 | `2`       | `"NB-IOT",28`  |
| NB-IoT — Band 3  | `2`       | `"NB-IOT",3`   |
| NB-IoT — Band 8  | `2`       | `"NB-IOT",8`   |

> All SIM cards in this test (A, B, C, D) are provisioned for **NB-IoT only**.
> They will not register on LTE-M or standard LTE. See Section 8 for the
> difference between NB-IoT, LTE-M, and LTE.

### 3.4 CEREG / CREG Registration Status Reference

`AT+CEREG?` is the key command for LTE/NB-IoT registration. The modem responds
with `+CEREG: <n>,<stat>` where `stat` is the registration state:

| `stat` | Name | Meaning for NB-IoT | What to do |
|--------|------|--------------------|------------|
| `0` | Not registered, not searching | Modem gave up scanning — radio may be off, SIM not inserted, or `AT+CGATT=0` was called | Force `CFUN=0` → `CFUN=1` cycle to reset radio |
| `1` | **Registered — home network** | ✅ SIM attached to its own operator's cell | Proceed with `gprsConnect()` |
| `2` | Searching | Modem is actively scanning for a cell on the configured band | Wait — normal during attach procedure |
| `3` | **Registration denied** | Modem found a cell and sent an attach request, but the **network rejected the SIM** | Check provisioning: wrong band (roaming not allowed), SIM not activated for NB-IoT, or IMEI not whitelisted |
| `4` | Unknown | Transitional / uncertain state | Wait briefly, then re-poll |
| `5` | **Registered — roaming** | ✅ SIM attached to a foreign operator's cell | Proceed with `gprsConnect()` |
| `ERROR` | Command not supported | `AT+CEREG` is LTE/EPS-specific — returned when the modem's EPS subsystem is **not initialised**, typically because the SIM has no LTE provisioning (2G/GPRS-only SIM) | Confirm SIM type with provider; test with `AT+CNMP=2` (auto) + `AT+CREG?` to check 2G registration |

> **`stat=3` vs `stat=2` — key diagnostic difference:**
> - `stat=2` forever → no cell found on this band (no coverage, or wrong band)
> - `stat=3` → cell found, attach attempted, **network rejected the SIM**
>
> Getting `stat=3` means the band and coverage are fine — the problem is with the
> SIM's provisioning or roaming permissions on that specific operator/cell.

`AT+CREG?` works the same way but for **2G/3G circuit-switched** registration —
it never reaches `stat=1` in LTE-only mode (`AT+CNMP=38`) and is shown in the logs
only as a secondary diagnostic.

### 3.5 AT Command Debug Mode

Uncomment to dump every AT exchange to Serial:

```cpp
#define DUMP_AT_COMMANDS
```

Capture serial to file (Linux, run before flashing):

```bash
stty -F /dev/ttyACM0 115200 raw -echo && cat /dev/ttyACM0 | tee /var/tmp/gateway-M2M.log
```

---

## 4. SIM Cards

| # | Color | CCID ends in | Owner  | Operator        | APN Provider | APN                    | User / Pass         | Notes                             |
|---|-------|--------------|--------|-----------------|--------------|------------------------|---------------------|-----------------------------------|
| A | 🟡 Yellow | <ICCID> | Job    | TIM Brasil      | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | NB-IoT only (no 2G/3G/LTE-M)     |
| B | 🔴 Red    | …00859     | Job    | Vivo            | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | NB-IoT only (same provisioning as A) |
| C | 🟢 Green  | …64104     | Job    | Vivo            | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | NB-IoT only (same provisioning as A) |
| D | 🩵 Cyan   | …529146    | Personal | Vivo (consumer M2M) | Vivo M2M | `smart.m2m.vivo.com.br` | (none)           | **Confirmed LTE-M only** (Kite Platform: `LTE/LTE-M ativo ✅`, NB-IoT not provisioned). Data roaming **disabled** — SIM denied on TIM towers. See §5.8. |
| E | 🩷 Pink   | …68771     | Job    | Vivo            | Datatem IoT  | `iot.datatem.com.br`   | `datatem`/`datatem` | `AT+CEREG` returns ERROR — **hypothesis: 2G/GPRS-only SIM, no LTE provisioning** |

---

## 5. Test Results

### 5.1 Results Table

One row per (SIM × band) combination.
**Payload** = MessagePack-serialized `SensorData` struct (15 fields).

| # | SIM | Color | Operator | Network | Band | APN | CCID | IMEI | CSQ | Payload | Result |
|---|-----|-------|----------|---------|------|-----|------|------|-----|---------|--------|
| 1 | A | 🟡 Yellow | TIM (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br` | <ICCID> | <IMEI> | 18 (Good) | 212 B | ✅ HTTP 200 |
| 2 | A | 🟡 Yellow | TIM (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br` | <ICCID> | <IMEI> | 13 (Good) | 212 B | ✅ HTTP 200 |
| 3 | A | 🟡 Yellow | TIM (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br` | <ICCID> | <IMEI> | — | — | ⏳ |
| 4 | B | 🔴 Red    | Vivo (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=3 (§5.4) |
| 5 | B | 🔴 Red    | Vivo (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=3 (§5.4) |
| 6 | B | 🔴 Red    | Vivo (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br` | — | — | — | — | ⏳ |
| 7 | C | 🟢 Green  | Vivo (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=3 (§5.4) |
| 8 | C | 🟢 Green  | Vivo (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br` | — | — | — | — | ❌ CEREG=2 timeout (§5.4) |
| 9 | C | 🟢 Green  | Vivo (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br` | — | — | — | — | ⏳ |
| 10 | D | 🩵 Cyan   | Vivo (personal) | NB-IoT | Band 28 — 700 MHz | `smart.m2m.vivo.com.br` | …529146 | — | — | — | ❌ CEREG=3 (§5.3, §5.4) |
| 11 | D | 🩵 Cyan   | Vivo (personal) | NB-IoT | Band 3 — 1800 MHz | `smart.m2m.vivo.com.br` | …529146 | — | — | — | ❌ CEREG=ERROR ⚠️ (§5.5, §5.7) |
| 12 | D | 🩵 Cyan   | Vivo (personal) | NB-IoT | Band 8 — 900 MHz  | `smart.m2m.vivo.com.br` | …529146 | — | — | — | ⏳ |
| 13 | E | 🩷 Pink   | Vivo (Datatem) | NB-IoT | Band 28 — 700 MHz | `iot.datatem.com.br`   | — | — | — | — | ❌ CEREG=ERROR (§5.5) |
| 14 | E | 🩷 Pink   | Vivo (Datatem) | NB-IoT | Band 3 — 1800 MHz | `iot.datatem.com.br`   | — | — | — | — | ❌ CEREG=ERROR (§5.5) |
| 15 | E | 🩷 Pink   | Vivo (Datatem) | NB-IoT | Band 8 — 900 MHz  | `iot.datatem.com.br`   | — | — | — | — | ⏳ |

> **CSQ scale note:** CSQ (returned by `AT+CSQ`) ranges from 0 to 31, plus 99 for unknown.
> It maps to RSSI via: `RSSI (dBm) = (CSQ × 2) − 113`. Standard industry categories:
>
> | CSQ   | RSSI (dBm)        | Category   |
> |-------|-------------------|------------|
> | 0–9   | ≤ −95 dBm         | Marginal   |
> | 10–14 | −93 to −85 dBm    | OK         |
> | 15–19 | −83 to −75 dBm    | Good       |
> | 20–24 | −73 to −65 dBm    | Very Good  |
> | 25–31 | −63 dBm or better | Excellent  |
> | 99    | —                 | Unknown    |
>
> For NB-IoT, the technology is specifically designed to work at low signal levels
> (down to −120 dBm RSRP / ~CSQ 5). A CSQ of 10–18 is typical and fully adequate for NB-IoT uplinks.

### 5.2 Successful Test Detail — SIM A, TIM, NB-IoT Band 28 (2026-03-03)

**Log file:** `M2M_TIM_datatem.txt`

#### AT+CPSI? Output

```
+CPSI: LTE NB-IOT,Online,724-04,0xAF3C,75508013,260,EUTRAN-BAND28,9362,0,0,-3,-89,-87,19
```

> **What is AT+CPSI?**
> This is a SIM7000-specific command that queries the modem's current serving cell
> information. **All values come from measurements received over the air from the cell
> tower** — they represent the actual radio conditions the modem has detected, not what
> was configured in software. The modem continuously measures these from the base
> station's reference signals.

| Field | Value | Meaning |
|-------|-------|---------|
| System Mode | `LTE NB-IOT` | Technology actually connected. Confirms NB-IoT (not LTE-M or GSM). |
| Operation Mode | `Online` | Active data session (PDP context open and IP assigned). |
| MCC-MNC | `724-04` | Mobile Country Code 724 = Brazil; MNC 04 = TIM Brasil. Identifies the operator the modem registered with. |
| TAC | `0xAF3C` (= 44860) | Tracking Area Code — a network-assigned ID for a group of cells used for paging. The value comes from the network; it has no fixed geographic meaning visible to us. |
| Serving Cell ID | `75508013` | E-UTRAN Cell Global ID. The unique identifier of the specific cell tower the modem is connected to. |
| Physical Cell ID | `260` | PCellID (0–503). A local radio identifier used by the modem for cell synchronisation and reselection. Not globally unique. |
| Freq Band | `EUTRAN-BAND28` | Band 28 = 700 MHz (as configured with `AT+CBANDCFG`). Confirms the modem found and connected to a tower on the requested band. |
| EARFCN | `9362` | E-UTRA Absolute Radio Frequency Channel Number. In Band 28, EARFCN 9362 → DL frequency ≈ 773.2 MHz. This is the exact carrier frequency of the cell. |
| DL BW / UL BW | `0` / `0` | Downlink / Uplink bandwidth. In NB-IoT, `0` = 200 kHz narrowband channel (normal for NB-IoT). |
| RSRQ | `−3 dB` | Reference Signal Received Quality. Ratio of signal to total received power (range −34 to 0 dB). **−3 dB is very good** — means the reference signals are strong relative to interference. |
| RSRP | `−89 dBm` | Reference Signal Received Power. Actual power of the tower's reference signals at the modem (range −140 to −44 dBm). **−89 dBm is moderate — typical urban NB-IoT.** Coverage threshold for NB-IoT is around −115 dBm. |
| RSSI | `−87 dBm` | Total Received Signal Strength — includes all signals and noise. Should be close to RSRP for a clean band. |
| RSSNR | `19 dB` | Reference Signal Signal-to-Noise Ratio. **19 dB is good.** > 10 dB is generally sufficient for reliable data. |

#### HTTP Result

```
POST http://ilha3d.com/sapi/sensorData/receive-data.php
HTTP 200 OK
{"success":true,"message":"Data received and stored successfully","station_id":99}
```

Confirmed in `measurements` table with all 15 sentinel fields correct:
`level_cm=888`, `temperature_C=100`, `pressure=999`, `s_gsm=<real CSQ>`, etc.

### 5.3 Failed Test — SIM D 🩵 Cyan, Vivo Personal, Band 28 (2026-03-03)

**Log file:** `M2M_VIVO_ilha3d.txt`

`CEREG stat=3` = registration denied. The modem went searching (stat=2) for ~84 s,
found a cell, then was denied. Pattern is consistent with §5.4 (roaming rejection on
TIM Band 28). Additionally, SIM D may be provisioned for **LTE-M** rather than NB-IoT
— this would explain persistent CEREG=3 even on Band 3/8 (to be confirmed in a
separate LTE-M test with `AT+CMNB=1`).

**Next step:** Test SIM D with `AT+CMNB=1` (LTE-M mode) after the NB-IoT band sweep
for SIMs B and C is complete.

### 5.4 Failed Tests — SIM B and C (Vivo Datatem), Band 28 (2026-03-04)

**Log files:** `M2M_VIVO_00859_datatem.txt` (SIM B) · `M2M_VIVO_64104_datatem.txt` (SIM C)

Both SIMs followed the same pattern:

1. After CFUN=1, modem starts searching: `CEREG: 0,2`
2. ~60–84 s later, transitions to `CEREG: 0,3` (registration **denied**)
3. Stays at stat=3 until 180 s timeout → ESP32 restarts → same result on retry

#### Why stat=3 and not stat=2 (stuck searching)?

`CEREG stat=3` means the modem **did find** a NB-IoT cell on Band 28 and sent an
attach request — but the **network rejected it**. If no coverage existed, the modem
would remain at stat=2 (still searching) indefinitely.

#### Root cause hypothesis: roaming rejection on TIM's infrastructure

The Band 28 NB-IoT cell in the area belongs to **TIM** (confirmed by SIM A succeeding
with MCC-MNC `724-04` = TIM Brasil). Vivo NB-IoT SIMs (B and C) are not permitted to
roam onto TIM's NB-IoT infrastructure — NB-IoT roaming agreements in Brazil are
limited and often not enabled between operators.

Vivo may deploy NB-IoT on a **different band** in the Florianópolis area. Known Vivo
NB-IoT deployment bands in Brazil include Band 3 (1800 MHz) and Band 8 (900 MHz).

#### Next steps

Test SIMs B and C on Band 3 and Band 8 with the same firmware sketch
(`#define NBIOT_BAND` changed accordingly). If Vivo has a NB-IoT cell on one of
these bands in the area, CEREG should reach stat=1 (home) instead of stat=3.

### 5.6 Successful Test Detail — SIM A 🟡 Yellow, TIM, NB-IoT Band 3 (2026-03-04)

**Log file:** `M2M_TIM_Band-3_yellow.txt`

#### AT+CPSI? Output

```
+CPSI: LTE NB-IOT,Online,724-04,0xAF3C,75508009,17,EUTRAN-BAND3,1352,0,0,-3,-88,-87,18
```

| Field | Value | Meaning |
|-------|-------|---------|
| System Mode | `LTE NB-IOT` | NB-IoT confirmed |
| MCC-MNC | `724-04` | TIM Brasil |
| TAC | `0xAF3C` (44860) | Same tracking area as Band 28 — same tower cluster |
| Serving Cell ID | `75508009` | Different cell from Band 28 (75508013) — Band 3 carrier on same tower |
| Freq Band | `EUTRAN-BAND3` | 1800 MHz confirmed |
| EARFCN | `1352` | DL ≈ 1835.2 MHz (Band 3) |
| RSRQ | `−3 dB` | Very good |
| RSRP | `−88 dBm` | Equivalent to Band 28 (−89 dBm) |
| RSSNR | `18 dB` | Good |

All 3 transmissions returned HTTP 200. CSQ dropped 13 → 6 → 3 during the test
(signal fading), but NB-IoT's deep-penetration capability kept the link viable.

**TIM is confirmed working on both Band 28 and Band 3 — it is the viable SIM for
the SAPI gateway cellular backup.**

---

### 5.5 Failed Test — SIM E 🩷 Pink, Vivo (job), Band 28 + Band 3 (2026-03-04)

**Log file:** `M2M_VIVO_8771.txt`

This SIM shows a **completely different failure pattern** from SIMs B, C, and D:

| Register | Response | Meaning |
|----------|----------|---------|
| `AT+CREG?` | `+CREG: 0,0` | Not registered, not searching (2G/3G) |
| `AT+CEREG?` | `ERROR` | Command not recognised in current modem state |

The modem never enters a searching state (`stat=2`) — `CREG` stays at `0,0`
throughout all 180 s. More significantly, `AT+CEREG` returns `ERROR` (not
`+CEREG: 0,x`) on every poll.

#### Why is `AT+CEREG` returning ERROR?

`AT+CEREG` is an LTE/EPS-specific command. On the SIM7000G, it returns ERROR when
the modem's EPS (Evolved Packet System) subsystem is not initialised — which happens
when the SIM has no LTE provisioning. The modem cannot set up an EPS context for a
non-LTE SIM, so the command itself fails.

Compare with SIMs B and C: those returned `+CEREG: 0,2` (modem is scanning for LTE
cells), which means their EPS subsystem **did** initialise — only the attach was
later denied.

#### Root cause hypothesis: 2G/GPRS-only SIM

SIM E is likely provisioned for **2G GPRS only** — not NB-IoT or LTE-M. With
`AT+CNMP=38` (LTE-only mode), the modem locks out 2G scanning, so:

1. The modem never scans 2G → `CREG: 0,0` (not searching)
2. The EPS bearer is never initialised → `AT+CEREG` returns ERROR
3. 180 s timeout → restart → same result

#### Next step

- Confirm with the SIM provider whether this SIM is provisioned for LTE (NB-IoT or LTE-M)
- Quick diagnostic: change `AT+CNMP=38` → `AT+CNMP=2` (automatic 2G/3G/LTE) and
  check if `AT+CREG?` reaches stat=1. If it registers on 2G, the SIM is GPRS-only.
- Band 3 result (2026-03-04): CEREG=ERROR confirmed — same as Band 28 (see row 14)

### 5.7 Anomaly — SIM D 🩵 Cyan, Band 3 shows CEREG=ERROR (2026-03-04)

**Log file:** `M2M_VIVO_Band-3_ilha3d_cian.txt`

The original Band 28 test (`M2M_VIVO_ilha3d.txt`, 2026-03-03) showed `CEREG: 0,3`
(registration denied — SIM found a cell and was rejected). However, the Band 3 test
log shows `CEREG=ERROR` — the same pattern as SIM E 🩷 Pink (2G-only SIM).

The log also captures a Band 28 boot (old firmware) before the Band 3 run, and both
show `CEREG=ERROR` throughout.

**Possible explanations:**

1. **Wrong chip inserted:** The cyan chip was accidentally swapped for the pink chip
   when changing SIMs — the log was labeled cyan but is actually pink's behaviour.
   This is the most likely explanation given the first test clearly showed CEREG=3.
2. **SIM suspended:** The Vivo M2M SIM (personal) may have been deactivated or
   suspended between tests (e.g. data quota exceeded).
3. **Different initialisation state:** Unlikely to change stat from 3 to ERROR.

**Action:** Physically verify which chip is in the board when running this test and
re-run with the cyan SIM confirmed in place.

### 5.8 LTE-M Test — SIM D 🩵 Cyan, Band 28, Indoor (2026-03-04)

**Log file:** `M2M_VIVO_LTE-M_B28_ilha3d_cian.txt`

**Result:** ❌ CEREG=3 throughout — registration denied immediately (stat=3 from the
very first poll at 2 s). Two full 180 s cycles were captured before the log was stopped.

#### Kite Platform analysis (Vivo M2M portal)

The SIM was inspected on [kiteplatform-vivo-br.telefonica.com](https://kiteplatform-vivo-br.telefonica.com/).
Key findings:

| Parameter | Value | Implication |
|-----------|-------|-------------|
| SIM Status | **Ativo** | SIM is active — not suspended |
| LTE/LTE-M ativo | ✅ ON | LTE-M technology is correctly provisioned |
| NB-IoT | not listed | **NB-IoT is NOT in this plan** — explains all NB-IoT CEREG=3/ERROR results |
| 2G ativo | ❌ OFF | No 2G fallback |
| 3G ativo | ❌ OFF | No 3G fallback |
| Tráfego de dados — Local | ✅ ON | Data on Vivo's own network: enabled |
| **Tráfego de dados — Em roaming** | ❌ **OFF** | **Data on other operators' networks: DISABLED** ← root cause |
| Serviço de VPN | ✅ ON | APN `smart.m2m.vivo.com.br` routes through private VPN |
| Tecnologias Usadas (LTE-M) | ❌ never used | Confirms no successful LTE-M session has ever occurred |
| Last connection event | 03-03-2026 — "SIM não registrado no GSM" | No successful registration since provisioning |

#### Root cause

The area (Cachoeira do Bom Jesus, Florianópolis) has **TIM LTE-M cells on Band 28**
(confirmed by SIM A NB-IoT tests on MCC-MNC `724-04` = TIM). Vivo's own LTE-M
infrastructure may not be present at this location. With **data roaming disabled**,
the Vivo SIM finds TIM's cell immediately but the network rejects the attach —
hence the instantaneous CEREG=3.

This is **not a firmware or hardware problem**. The fix requires enabling national
data roaming on the SIM.

#### Why the option is not visible in Kite Platform

The "Activate data traffic roaming" operation (Kite Platform manual p. 125) requires
**Administrator or Demo Kit user profile**. The current account is a standard end-customer
profile and the toggle appears read-only. To enable roaming:

- Contact Vivo M2M support and request: *"Ativar tráfego de dados em roaming nacional
  no ICC <ICCID>"*
- Or: test at a location with confirmed **Vivo LTE-M coverage** (no roaming needed)

#### Outdoor location test — completed (2026-03-04)

**Log file:** `M2M_VIVO_LTE-M_B28_ilha3d_cian_outside.txt` — see §10.3 for full analysis.

---

## 6. Known Issues and Workarounds

### 6.1 TINY_GSM_MODEM_SIM7000SSL Fails on NB-IoT

TinyGSM's SSL variant uses `AT+CNACT=1` for GPRS activation and waits for the
unsolicited response `+APP PDP: ACTIVE`. On the SIM7000G in NB-IoT mode (`AT+CMNB=2`)
this command is not supported and the activation always fails.

**Workaround:** Use `#define TINY_GSM_MODEM_SIM7000` (plain TCP) with `TinyGsmClient`.
HTTP (port 80) is used instead of HTTPS. The plain variant's `AT+SAPBR`/`AT+CGACT`
path works correctly on NB-IoT.

**Future HTTPS path:** Wrap `TinyGsmClient` with
[OPEnSLab-OSU/SSLClient](https://github.com/OPEnSLab-OSU/SSLClient) to handle TLS
on the ESP32 side via BearSSL, bypassing the modem's SSL stack entirely.

### 6.2 AT+CGATT=0 Stops NB-IoT Registration

On NB-IoT, `AT+CGATT=0` (issued internally by TinyGSM's `gprsDisconnect()`) halts EPS
registration entirely. The modem then reports `CEREG: 0,0` (not searching — radio appears
off) on the next boot and never recovers on its own.

**Root cause:** On NB-IoT, the EPS attach and PDN connection are coupled; deactivating
GPRS with CGATT=0 also stops the radio from scanning.

**Workaround:** Force a `CFUN=0` → apply settings → `CFUN=1` cycle in `initModem()` on
every boot. This resets the radio cleanly regardless of the previous session state.

### 6.3 PWRKEY Pulse Must Be ≥ 1.5 s

The SIM7000G datasheet requires PWRKEY asserted for ≥ 1 s to trigger power-on. The
LilyGO board uses a transistor that inverts the logic (GPIO 4 HIGH = PWRKEY LOW = active).
A 300 ms pulse is insufficient — the module does not respond.

### 6.4 Vivo M2M SIM — Registration Denied (CEREG stat=3)

The personal Vivo M2M SIM (SIM D) returned `CEREG stat=3` (denied). This is not a
firmware issue — needs investigation via the Vivo M2M operator portal (see §5.3).

---

## 7. Steps to Replicate

1. **Flash sketch:** `AppTest/gateways/gateway_M2M_test-01/` (test sketch, kept in the private development repository)
   ```bash
   cd AppTest/gateways/gateway_M2M_test-01/
   cp include/credentials_sample.h include/credentials.h
   # fill in apiKey in credentials.h
   ~/.platformio/penv/bin/pio run -t upload
   ```
2. **Set APN and band** in `src/main.cpp` before flashing (see Section 3.3).
3. **Monitor serial:**
   ```bash
   minicom -D /dev/ttyACM0 -b 115200 | tee /var/tmp/gateway-M2M.log
   ```
   > Kill minicom before flashing: `pkill -f "minicom.*ttyACM0"`
4. **Expected boot sequence:**
   - `[MODEM] Disabling radio...` → `[MODEM] Re-enabling radio...`
   - `[NET] AT+CEREG? → +CEREG: 0,2` (searching)
   - `[NET] LTE/EPS registered via CEREG ✓`
   - `[NET] GPRS connected | Local IP: ...`
   - `[HTTP] Status: 200`
5. **Verify in DB:**
   ```sql
   SELECT * FROM measurements WHERE id_station = 99 ORDER BY id DESC LIMIT 5;
   ```

---

---

## 8. Terminology: NB-IoT, LTE-M, and LTE

These three names are related but refer to different technologies. All three belong
to the LTE standards family, which is why they share frequency bands and infrastructure
— but their speed, latency, and intended use differ significantly.

```
LTE family (4G radio standard):
├── LTE broadband (Cat-4, Cat-6, Cat-12…)  ← standard 4G on smartphones
├── LTE-M  / CAT-M1  (Cat-M1)              ← IoT, moderate speed, supports voice/mobility
└── NB-IoT / Cat-NB1 / Cat-NB2             ← IoT, low speed, deep penetration, low power
```

### NB-IoT ≠ LTE (broadband)

NB-IoT is **technically built on the LTE radio standard** — that is why the SIM7000G
reports `LTE NB-IOT` in the `AT+CPSI?` output. It reuses LTE's frequency bands and
cell tower infrastructure. However, it is a completely separate service from the
"LTE" your smartphone uses:

| | LTE broadband | NB-IoT |
|---|---|---|
| Channel width | 20 MHz | 200 kHz (narrowband) |
| Typical downlink speed | 50–300 Mbps | 20–200 kbps |
| Designed for | Smartphones, video | IoT sensors, low data |
| Battery life (device) | Hours | Months to years |
| Penetration (basements, etc.) | Standard | Excellent (+20 dB gain vs. LTE) |

### LTE-M = CAT-M = CAT-M1 (all the same)

These are three names for the same 3GPP standard:

| Name | Origin |
|------|--------|
| **LTE-M** | LTE for Machines — the commercial marketing name |
| **CAT-M1** | LTE Category M1 — the 3GPP technical designation |
| **eMTC** | enhanced Machine Type Communication — the spec name in standards documents |

LTE-M sits between NB-IoT and standard LTE: faster than NB-IoT (~1 Mbps), supports
voice and device mobility (handover between cells), but consumes more power than NB-IoT.

### AT+CMNB Parameter Summary

The SIM7000G selects the IoT variant via `AT+CMNB`:

| `AT+CMNB` value | Technology | 3GPP name |
|-----------------|------------|-----------|
| `1` | LTE-M | Cat-M1 / eMTC |
| `2` | NB-IoT | Cat-NB1 |
| `3` | Auto (modem chooses) | — |

The Datatem SIM cards (A, B, C) are provisioned for **NB-IoT only** (`AT+CMNB=2`).
SIM D (cyan, personal Vivo M2M) is confirmed **LTE-M only** (`AT+CMNB=1`) — see §5.8.
SIM E (pink) is likely 2G/GPRS-only — see §5.5.

---

---

## 9. NB-IoT Frequency Bands — Global Reference and Brazil Deployment

### 9.1 All NB-IoT Bands Defined by 3GPP

3GPP has defined NB-IoT support across many frequency bands. The table below lists all
bands supported by the **SIM7000G modem** (relevant subset), with Brazil deployment
status for each operator.

| Band | Frequency | Common name | SIM7000G | TIM Brasil | Vivo Brasil | Claro Brasil | Notes |
|------|-----------|-------------|----------|------------|-------------|--------------|-------|
| **B1** | 2100 MHz | IMT | ✅ | ⚠️ Possible | ⚠️ SP metro only | ✗ | Mainly Asia/Europe; limited NB-IoT in Brazil |
| **B2** | 1900 MHz | PCS | ✅ | ✗ | ✗ | ✗ | North America only |
| **B3** | 1800 MHz | GSM-1800 | ✅ | ✅ **deployed** | ✅ **deployed** | ✅ **deployed** | ✅ **Tested — TIM works** |
| **B4** | 1700/2100 MHz | AWS | ✅ | ✗ | ✗ | ✗ | North America only |
| **B5** | 850 MHz | CLR-850 | ✅ | ✗ | LTE only | LTE only | 850 MHz used for LTE in Brazil, **not NB-IoT** |
| **B8** | 900 MHz | E-GSM | ✅ | ✗ | ✗ | ✗ | Used in Europe/Asia; **no Brazilian operator has 900 MHz NB-IoT** |
| **B12** | 700 MHz lower | US 700 lower | ✅ | ✗ | ✗ | ✗ | US-specific (AT&T) |
| **B13** | 700 MHz upper | US 700 C | ✅ | ✗ | ✗ | ✗ | US-specific (Verizon) |
| **B17** | 700 MHz | US 700 b | ✅ | ✗ | ✗ | ✗ | US-specific (AT&T) |
| **B18** | 850 MHz | Japan 850 | ✅ | ✗ | ✗ | ✗ | Japan only |
| **B19** | 850 MHz | Japan 850 ext | ✅ | ✗ | ✗ | ✗ | Japan only |
| **B20** | 800 MHz | EU 800 | ✅ | ✗ | ✗ | ✗ | Europe only (digital dividend) |
| **B26** | 850 MHz extended | CLR-850 ext | ✅ | ✗ | ✗ | ✗ | No NB-IoT deployment in Brazil |
| **B28** | 700 MHz | APT 700 | ✅ | ✅ **deployed** | ✅ **deployed** | ✅ **deployed** | ✅ **Tested — TIM works** — primary NB-IoT band in Brazil |
| **B66** | 1700/2100 MHz | AWS-3 | ✅ | ✗ | ✗ | ✗ | Americas, mainly Canada/US |

> **⚠️ = Possible but not confirmed.** Operator has LTE on this band, but NB-IoT deployment is
> not confirmed or is limited to major metro areas (São Paulo).

### 9.2 Why Only Band 28 and Band 3 Matter in Brazil

Brazilian spectrum regulation (ANATEL) allocates frequencies differently from Europe and
North America. The key points:

- **Brazil has no 900 MHz LTE/NB-IoT allocation.** The 900 MHz band (Band 8) is used for
  GSM legacy in some countries, but Brazilian operators use **850 MHz (Band 5)** for legacy
  and have not deployed NB-IoT there. Testing Band 8 on a Brazilian SIM is pointless.
- **700 MHz APT (Band 28)** is the primary broadband/IoT band in Brazil. TIM, Vivo, and
  Claro all deployed NB-IoT here first (2018–2019).
- **1800 MHz (Band 3)** is the secondary NB-IoT band, reusing GSM-1800 infrastructure.
  All three operators have it.
- **2100 MHz (Band 1)** is used for 3G/4G but NB-IoT deployment is minimal and restricted
  to large cities.

### 9.3 SAPI Test Conclusion — NB-IoT Band Sweep Complete

All practically relevant NB-IoT bands for Brazil have been tested at the SAPI gateway
location (Cachoeira do Bom Jesus, Florianópolis, SC):

| Band | Tested | TIM 🟡 | Vivo B 🔴 | Vivo C 🟢 | Result |
|------|--------|--------|-----------|-----------|--------|
| **Band 28** (700 MHz) | ✅ | ✅ HTTP 200 | ❌ CEREG=3 | ❌ CEREG=3 | TIM only |
| **Band 3** (1800 MHz) | ✅ | ✅ HTTP 200 | ❌ CEREG=3 | ❌ CEREG=2 | TIM only |
| **Band 8** (900 MHz) | — | — | — | — | **Not deployed in Brazil — skip** |
| **Band 1** (2100 MHz) | — | — | — | — | Not relevant for Florianópolis |

**The NB-IoT band sweep is complete. TIM works on both deployed bands. Vivo Datatem SIMs
are consistently rejected — this is a SIM provisioning issue, not a coverage or band issue.**

---

## 10. LTE-M Tests — SIM D 🩵 Cyan (Vivo Personal M2M)

Testing all available SIMs for LTE-M support. NB-IoT-only SIMs are expected to fail
but are tested for completeness.

**Firmware config for LTE-M tests:**

```cpp
#define IOT_MODE  "LTE-M"
#define IOT_CMNB  1                        // AT+CMNB=1 → LTE-M/CAT-M1
// AT+CBANDCFG="CAT-M",<band>
const char apn[] = "smart.m2m.vivo.com.br";
```

### 10.1 LTE-M Results Table

| # | SIM | Color | Band | Location | APN | Result | Log file |
|---|-----|-------|------|----------|-----|--------|----------|
| 1 | D | 🩵 Cyan | Band 28 — 700 MHz | Indoor (home) | `smart.m2m.vivo.com.br` | ❌ CEREG=3 — roaming denied (§5.8) | `M2M_VIVO_LTE-M_B28_ilha3d_cian.txt` |
| 2 | D | 🩵 Cyan | Band 28 — 700 MHz | **Outdoor** (Vivo coverage search) | `smart.m2m.vivo.com.br` | ❌ CEREG=2 timeout — no Vivo cell found (§10.3) | `M2M_VIVO_LTE-M_B28_ilha3d_cian_outside.txt` |
| 3 | A | 🟡 Yellow | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=2 timeout — TIM SIM is NB-IoT only; no LTE-M cell found (§11.1) | `M2M_TIM_LTE-M_B28_yellow.txt` |
| 4 | C | 🟢 Green | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=3 — Vivo Datatem supports LTE-M but roaming denied on TIM cell (§11.2) | `M2M_VIVO_LTE-M_B28__green.txt` |
| 5 | E | 🩷 Pink | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=3 — LTE-M provisioned, roaming denied; **not 2G-only** (§11.3) | `M2M_VIVO_LTE-M_B28_pink.txt` |
| 6 | B | 🔴 Red | Band 28 — 700 MHz | Indoor (home) | `iot.datatem.com.br` | ❌ CEREG=3→2 — NB-IoT+LTE-M provisioned, TIM cell denied then no Vivo cell found (§11.4) | `M2M_VIVO_LTE-M_B28_red.txt` |

### 10.2 LTE-M Band Reference for Brazil

| Band | Frequency | TIM LTE-M | Vivo LTE-M | Notes |
|------|-----------|-----------|------------|-------|
| **B28** | 700 MHz | ✅ deployed | ✅ deployed | Primary IoT band in Brazil |
| **B3** | 1800 MHz | ✅ deployed | ✅ deployed | Secondary; good urban coverage |

### 10.3 Outdoor Test Analysis — SIM D 🩵 Cyan, Band 28 (2026-03-04)

**Log file:** `M2M_VIVO_LTE-M_B28_ilha3d_cian_outside.txt`

The outdoor test revealed a **different CEREG pattern** from the indoor test:

| Phase | Indoor result | Outdoor result |
|-------|--------------|----------------|
| 0–2 s | CEREG=3 (TIM cell found, denied) | CEREG=3 (TIM cell found, denied) |
| 14 s onwards | CEREG=3 throughout | **CEREG=2** (searching, no cell found) |
| Outcome | Timeout at 180 s | Timeout at 180 s |

**Interpretation:** Outdoors, the modem initially found TIM's Band 28 LTE-M cell and
was denied (stat=3, roaming not allowed). After moving away from TIM's coverage, it
scanned the entire 180 s window searching for a **Vivo home cell** and found none.
This confirms that **Vivo has no LTE-M Band 28 infrastructure in this area**.

#### Why Band 3 LTE-M is also not worth testing

Vivo deploys Band 28 and Band 3 LTE-M on the **same physical towers**. Since no Vivo
tower is visible on Band 28, no Vivo tower will be visible on Band 3 either. Testing
Band 3 would produce the same CEREG=2 timeout.

#### SIM D — Testing concluded

| Root cause | No Vivo LTE-M infrastructure in the area (Cachoeira do Bom Jesus, Florianópolis) |
|---|---|
| Secondary cause | Data roaming disabled — cannot use TIM's nearby LTE-M cells |
| Fix option 1 | Contact Vivo M2M support: enable national data roaming on ICC …529146 |
| Fix option 2 | Deploy gateway in area with confirmed Vivo LTE-M coverage |
| **SAPI decision** | **SIM D not viable for SAPI gateway cellular backup at current location** |

**SIM A 🟡 Yellow (TIM Datatem NB-IoT) remains the only confirmed working SIM.**
Testing continues with SIM A — see §11.

---

## 11. TIM Datatem SIM — Production Validation (SIM A 🟡 Yellow)

SIM A already passed Band 28 and Band 3 NB-IoT tests (§5.2, §5.6). This section
documents additional validation toward production use as the SAPI gateway cellular
backup.

### 11.1 TIM LTE-M test — concluded ❌

**Log file:** `M2M_TIM_LTE-M_B28_yellow.txt`

**Result: CEREG=2 throughout** — the modem scanned for 180 s and found no LTE-M cell.
This is a distinct pattern from the Vivo roaming failures (CEREG=3):

| CEREG pattern | Meaning |
|---------------|---------|
| stat=3 (Vivo SIMs) | Cell found, attach denied — provisioning/roaming issue |
| **stat=2 (TIM yellow)** | **No LTE-M cell found at all — SIM or network not LTE-M** |

Two combined reasons:
1. **TIM Datatem SIM is provisioned for NB-IoT only** — not LTE-M
2. **TIM has no LTE-M (CAT-M1) carrier on Band 28 in this area** — only NB-IoT subcarriers

NB-IoT and LTE-M occupy different sub-channels within the same band; TIM has deployed
NB-IoT on Band 28 here but not LTE-M. Testing Band 3 LTE-M with TIM would also fail
for the same reasons.

**SIM A — NB-IoT is the correct mode. LTE-M testing concluded.**

### 11.2 Vivo Datatem LTE-M test (SIM C 🟢 Green) — concluded ❌

**Log file:** `M2M_VIVO_LTE-M_B28__green.txt`

**Result: CEREG=3 immediately at 2 s** — the modem found TIM's LTE-M cell instantly
and was denied. Same roaming-rejection pattern as NB-IoT Band 28 with this SIM.

**Key finding:** Unlike TIM (CEREG=2 on LTE-M), the Vivo Datatem green SIM gets
CEREG=3 — meaning its EPS subsystem initialises and it actively attempts LTE-M attach.
**Datatem provisions Vivo SIMs for both NB-IoT and LTE-M.** The failure is purely
the roaming denial on TIM's infrastructure, not the SIM technology.

### 11.3 Vivo Datatem LTE-M test (SIM E 🩷 Pink) — concluded ❌

**Log file:** `M2M_VIVO_LTE-M_B28_pink.txt`

**Result: CEREG=3 immediately at 2 s** — same roaming-denial pattern as green.

**Key revision to §5.5 hypothesis:** SIM E is **not** 2G-only. It is provisioned for
**LTE-M only** (same profile as SIM D cyan). The CEREG=ERROR seen on NB-IoT tests is
now explained: the SIM has no NB-IoT provisioning, so the NB-IoT EPS subsystem fails
to initialise → `AT+CEREG` returns ERROR. Switching to LTE-M mode (CMNB=1), the EPS
initialises correctly and the modem attempts LTE-M attach — which gets denied by the
network (roaming on TIM).

| SIM | NB-IoT result | LTE-M result | Profile conclusion |
|-----|--------------|--------------|-------------------|
| A 🟡 TIM | ✅ CEREG=1 | ❌ CEREG=2 | **NB-IoT only** |
| B 🔴 Vivo | ❌ CEREG=3 | ⏳ pending | NB-IoT + LTE-M? |
| C 🟢 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | **NB-IoT + LTE-M** |
| D 🩵 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | **LTE-M only** |
| E 🩷 Vivo | ❌ CEREG=ERROR | ❌ CEREG=3 | **LTE-M only** (no NB-IoT) |

### 11.4 Vivo Datatem LTE-M test (SIM B 🔴 Red) — concluded ❌

**Log file:** `M2M_VIVO_LTE-M_B28_red.txt`

**Result: CEREG=3 at 2 s → CEREG=2 from 14 s onwards → timeout.** The modem found
TIM's LTE-M cell instantly, was denied (roaming), then searched for a Vivo home cell
for the remaining 166 s and found none. Same pattern as the cyan outdoor test (§10.3).

Red is provisioned for both NB-IoT and LTE-M (consistent with green), but neither
technology can register because Vivo has no infrastructure on either band in this area.

### 11.5 Final SIM Profile Summary

| SIM | NB-IoT B28 | LTE-M B28 | Technology profile | Root cause of failure |
|-----|-----------|-----------|-------------------|-----------------------|
| A 🟡 TIM | ✅ **HTTP 200** | ❌ CEREG=2 | **NB-IoT only** | No TIM LTE-M cell in area |
| B 🔴 Vivo | ❌ CEREG=3 | ❌ CEREG=3→2 | NB-IoT + LTE-M | No Vivo cell; TIM cell denied |
| C 🟢 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | NB-IoT + LTE-M | No Vivo cell; TIM cell denied |
| D 🩵 Vivo | ❌ CEREG=3 | ❌ CEREG=3 | **LTE-M only** | Roaming disabled; no Vivo LTE-M cell |
| E 🩷 Vivo | ❌ CEREG=ERROR | ❌ CEREG=3 | **LTE-M only** (no NB-IoT) | Roaming disabled; no Vivo LTE-M cell |

---

## 12. Final Conclusion — Issue #37

### 12.1 Result

**TIM Datatem NB-IoT is the only viable cellular technology for the SAPI gateway
at Cachoeira do Bom Jesus, Florianópolis, SC.**

| Aspect | Conclusion |
|--------|-----------|
| **Working SIM** | SIM A 🟡 Yellow — TIM Datatem (`iot.datatem.com.br`) |
| **Working technology** | NB-IoT (`AT+CMNB=2`) |
| **Primary band** | Band 28 — 700 MHz ✅ HTTP 200 (§5.2) |
| **Backup band** | Band 3 — 1800 MHz ✅ HTTP 200 (§5.6) |
| **Payload** | 212 bytes MessagePack, HMAC-SHA256 signed |
| **Server response** | HTTP 200, data stored in production DB |

### 12.2 Why All Vivo SIMs Failed

All five Vivo SIMs (B, C, D, E) failed at this location for the same fundamental reason:
**there is no Vivo NB-IoT or LTE-M infrastructure in the area.** The only visible IoT
cells belong to TIM. Vivo SIMs cannot roam onto TIM's NB-IoT/LTE-M network (roaming
agreements for these technologies are not enabled between operators in Brazil).

The Vivo personal M2M SIM (D) additionally has data roaming explicitly disabled in
the Kite Platform portal, which would prevent it from using TIM's infrastructure even
if a roaming agreement existed.

### 12.3 Production Recommendation

**Multiband configuration confirmed working** (2026-03-04): `AT+CBANDCFG="NB-IOT",28,3`
allows the modem to automatically select the best available band. In testing it
connected to Band 28 (strongest signal) with CSQ 22 — better than the single-band
Band 28 test (CSQ 18). Log: `M2M_TIM_LTE-M_Multiband_yellow.txt`.

The SAPI gateway (`gateway-01`) cellular backup shall use:

```cpp
// Production cellular backup configuration
#define IOT_MODE        "NB-IoT"
#define IOT_CMNB        2                        // AT+CMNB=2
#define IOT_BAND        "28,3"                   // Modem auto-selects best band
#define IOT_BAND_LABEL  "Band 28 + Band 3 (auto)"
const char apn[]      = "iot.datatem.com.br";
const char gprsUser[] = "datatem";
const char gprsPass[] = "datatem";
```

#### Multiband AT+CPSI? result

```
+CPSI: LTE NB-IOT,Online,724-04,0xAF3C,75508013,260,EUTRAN-BAND28,9362,0,0,-12,-82,-70,20
```

| Metric | Band 28 only (§5.2) | **Multiband auto** | Change |
|--------|--------------------|--------------------|--------|
| Band selected | EUTRAN-BAND28 | EUTRAN-BAND28 | Same — B28 is best |
| CSQ | 18 | **22** | +4 ↑ |
| RSRP | −89 dBm | **−82 dBm** | +7 dB ↑ |
| RSSI | −87 dBm | **−70 dBm** | +17 dB ↑ |
| RSSNR | 19 dB | **20 dB** | +1 dB ↑ |

### 12.4 Open Items

| Item | Priority | Notes |
|------|----------|-------|
| Implement NB-IoT cellular backup in `gateway-01` production firmware | High | Use TIM Datatem SIM A; Band 28 primary, Band 3 fallback |
| Add offline queue (SQLite) for buffering packets during WiFi outages | High | Cellular backup only useful if packets aren't lost during switchover |
| Contact Vivo M2M support to enable roaming on SIM D (cyan) | Low | Optional; only needed if TIM Datatem SIM is unavailable |
| Re-test Vivo Datatem SIMs (B, C) at a location with Vivo NB-IoT coverage | Low | Would confirm SIM provisioning is correct; not needed for SAPI deployment |

*Last updated: 2026-03-04 — All tests complete. Issue #37 concluded.*

---

## 13. Differences Between Vivo Datatem SIMs (B 🔴 Red vs C 🟢 Green)

Although B and C are nominally identical (same operator, same APN provider, same
provisioning type), their failure patterns differ in two tests:

| Test | B 🔴 Red | C 🟢 Green | Interpretation |
|------|---------|-----------|----------------|
| NB-IoT Band 28 | ❌ CEREG=3 | ❌ CEREG=3 | Identical — both find TIM's cell, both denied |
| **NB-IoT Band 3** | ❌ **CEREG=3** | ❌ **CEREG=2** | **Different** — Red finds a Band 3 cell; Green finds none |
| LTE-M Band 28 | ❌ CEREG=3→2 | ❌ CEREG=3 | Slightly different — Red loses the cell after denial; Green stays denied |

### Key difference — NB-IoT Band 3

- **Red CEREG=3**: the modem found a NB-IoT Band 3 cell (possibly a Vivo cell visible
  in that direction) and sent an attach request that was rejected
- **Green CEREG=2**: the modem scanned the entire 180 s window and found no Band 3 cell

This suggests Red may have slightly better Band 3 sensitivity or was positioned
differently during the test, briefly seeing a Vivo (or TIM) Band 3 cell that Green
could not. Both end in failure but Red's CEREG=3 on Band 3 is a more interesting
result — it means a Band 3 cell exists nearby and, **if Vivo were to enable roaming or
if a TIM-provisioned chip were used, Band 3 NB-IoT would register successfully**
(confirmed by SIM A 🟡 on Band 3 §5.6).

### LTE-M difference

Red transitions CEREG=3→2 (finds TIM's LTE-M cell, denied, then no Vivo cell found),
while Green stays at CEREG=3 throughout. This is consistent with Red being tested
slightly later when TIM's LTE-M cell may have had stronger signal momentarily.
Not a provisioning difference — both SIMs behave identically in principle.

---

## 14. Checklist — Possible Solutions for Vivo Datatem SIMs

The Vivo Datatem chips (B 🔴, C 🟢, E 🩷) consistently fail due to Vivo having no
NB-IoT infrastructure at the SAPI gateway location and roaming onto TIM not being
permitted. The following actions may resolve the issue, in order of likelihood and ease.

Sources consulted: [Datatem NB-IoT/LTE-M](https://datatem.com.br/nb-iot-e-lte-m/) ·
[Datatem M2M Chip & APN](https://datatem.com.br/chip-m2m-apn-privada/) ·
[Datatem NB-IoT/CAT-1/CAT-M1](https://datatem.com.br/nb-iot-cat-1-e-cat-m1/)

---

### ✅ Solution 1 — Request a Multioperator (Multi-MVNO) chip from Datatem  ⭐ Most likely to work

- [ ] Contact Datatem and request a **multioperator M2M chip** (also called chip
  multi-operadora or multi-MVNO)
- Datatem explicitly offers chips that can roam between **TIM, Vivo, and Claro**
  automatically, selecting the best available signal at each location
- With a multioperator chip, the modem would attach to TIM's NB-IoT cell (Band 28 or
  Band 3) at the SAPI location without any roaming restriction
- Same APN (`iot.datatem.com.br`), same credentials — **no firmware change needed**
- Datatem offers free coverage analysis per technology and location before purchasing

> **Contact**: [datatem.com.br](https://datatem.com.br/) — free technical support
> includes coverage analysis by technology type for your specific address.

---

### ✅ Solution 2 — Replace Vivo Datatem chips with TIM Datatem chips

- [ ] Request TIM-provisioned chips from Datatem (same APN, TIM operator)
- TIM NB-IoT works on **both Band 28 and Band 3** at this location (confirmed by SIM A)
- TIM has NB-IoT coverage in **5,167 municipalities** vs Vivo's 4,006 (June 2024,
  source: Teleco) — broader NB-IoT footprint nationally
- Same `iot.datatem.com.br` APN — zero firmware changes needed
- **This is already validated**: SIM A 🟡 is a TIM Datatem chip and works perfectly

---

### 🔧 Solution 3 — Contact Datatem support to diagnose Vivo chip roaming

- [ ] Open a support ticket with Datatem describing the CEREG=3 failures on NB-IoT
  Band 28 and Band 3 for the Vivo chips
- Provide: chip CCIDs, location (GPS coordinates), modem model (SIM7000G), AT+CPSI
  output from the working TIM test for reference
- Ask specifically: *"O chip Vivo está habilitado para roaming nacional NB-IoT na
  infraestrutura TIM?"*
- Datatem manages roaming agreements and may be able to enable roaming on existing
  Vivo chips without replacing them
- **Datatem offers free technical support** including connectivity configuration on devices

---

### 🔧 Solution 4 — Verify Vivo NB-IoT coverage map for the specific address

- [ ] Ask Datatem (or check Vivo's coverage portal) for NB-IoT coverage at the
  exact GPS coordinates: **27°25'53"S, 48°25'18"W** (Cachoeira do Bom Jesus, Florianópolis)
- Vivo has NB-IoT in 4,006 municipalities — but municipal coverage does not guarantee
  street-level coverage; a tower must be within range
- If Vivo has no NB-IoT cell within ~5 km of the location, no firmware or SIM change
  will fix this — only Solutions 1 or 2 apply
- The consistent CEREG=3 on Band 28 (not CEREG=2) suggests a Vivo cell **may exist
  nearby** but the SIM is not authorised to roam — worth confirming before replacing chips

---

### 🔧 Solution 5 — Enable national data roaming on Vivo personal M2M SIM D 🩵 Cyan

- [ ] Contact Vivo M2M commercial support and request: *"Ativar tráfego de dados em
  roaming nacional no ICC <ICCID>"*
- The "Activate data traffic roaming" option on Kite Platform requires Administrator
  profile — Vivo support can enable it directly
- Once enabled, SIM D should register on TIM's LTE-M Band 28 cell (consistently visible
  at the indoor location — CEREG=3 means the cell is there)
- This only resolves SIM D (personal chip) — does not fix the job Datatem chips (B, C, E)
- **Cost note**: national roaming may incur extra charges — confirm with Vivo M2M support

---

### 🧪 Solution 6 — Test Vivo Datatem chips at a location with confirmed Vivo NB-IoT coverage

- [ ] Use Vivo's coverage checker to find a nearby location with confirmed Vivo NB-IoT
- Take the gateway (with chip B 🔴 or C 🟢) and test NB-IoT Band 28
- If CEREG=1 (registered home), the SIM is correctly provisioned and the problem is
  purely geographic (no Vivo tower at the SAPI installation site)
- This diagnostic step would confirm whether Solutions 3/4 are worth pursuing vs
  going directly to Solutions 1/2
- The notable **CEREG=3 for Red on Band 3** (§13) means a cell was found — testing Red
  in a stronger Vivo coverage area on Band 3 would be particularly informative

---

### Summary

| # | Solution | Effort | Cost | Recommended |
|---|----------|--------|------|-------------|
| 1 | Multioperator chip from Datatem | Low — contact + swap SIM | New chip cost | ⭐ **Yes — best option** |
| 2 | TIM Datatem chip (already validated) | Low — contact + swap SIM | New chip cost | ✅ Yes — proven to work |
| 3 | Datatem support to enable roaming on existing chips | Low — support ticket | None | ✅ Try first |
| 4 | Verify Vivo NB-IoT coverage map | Very low — one query | None | ✅ Quick diagnostic |
| 5 | Enable roaming on Vivo personal SIM D (cyan) | Low — call Vivo M2M | Possible extra charge | Optional |
| 6 | Field test Vivo chips at Vivo coverage location | Medium — physical test | None | Diagnostic only |
