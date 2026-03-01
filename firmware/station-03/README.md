# Water Level Station - Nucleo L476RG (Estacao-03)

This is the main production code for the Water Level Station **estacao-03**, developed for a master's degree project.

## Hardware Architecture

The station is based on the **STM32 Nucleo L476RG** MCU and utilizes two specialized shields:
* **SAPI LoRa Arduino Shield**: Responsible for long-range wireless communication.
* **SAPI Morpho Shield**: Used for sensor interfacing and power management.

---

## GPIO Pin Mapping

### LoRa Radio (SX1276/RFM95W) - SPI Interface

| Pin   | Function        | Description                          |
|-------|-----------------|--------------------------------------|
| PA4   | LoRa_NSS        | SPI Chip Select                      |
| PA5   | LoRa_SCK        | SPI Clock                            |
| PA6   | LoRa_MISO       | SPI Data In (Master In Slave Out)    |
| PA7   | LoRa_MOSI       | SPI Data Out (Master Out Slave In)   |
| PA1   | LoRa_RST        | Radio Reset                          |
| PB0   | LoRa_DIO0       | Interrupt (hardware interrupt pin)   |
| PB3   | LoRa_Pwr_enable | Power supply enable (HW-613 module)  |

### Ultrasonic Sensor - Multi-sensor Support

The module supports 3 ultrasonic sensor types with a unified API:

| Sensor   | Mode   | Range     | Baud | Command | Notes |
|----------|--------|-----------|------|---------|-------|
| HC-SR04  | Echo   | 2-400 cm  | -    | -       | Default sensor |
| US-100   | Serial | 2-450 cm  | 9600 | 0x55    | Jumper required for serial mode |
| AJ-SR04M | Serial | 20-800 cm | 9600 | 0x01    | 120K resistor on R19 for mode 2 |

**Pin mapping:**

| Pin   | Echo Mode      | Serial Mode |
|-------|----------------|-------------|
| PC11  | Trigger output | UART TX     |
| PC10  | Echo input     | UART RX     |

**Sensor selection:** Change `US_SENSOR_TYPE` in `ultrasonic.cpp` or add build flag:
```ini
build_flags = -D US_SENSOR_TYPE=US_SENSOR_US100
```

**US-100 Serial Mode Note:** To use US-100 in serial mode, the jumper on the back of the sensor board must be installed (short the two pads). Without the jumper, the sensor operates in Echo mode (like HC-SR04).

### BME280/BMP280 Sensor - I2C Interface

| Pin   | Function | Description           |
|-------|----------|-----------------------|
| PB8   | SCL      | I2C Clock             |
| PB9   | SDA      | I2C Data              |

I2C Address: `0x76` (default, may be `0x77` depending on sensor)

### ADC Voltage Measurement

| Pin   | Function      | Description                      |
|-------|---------------|----------------------------------|
| PC0   | Vpanel (A5)   | Solar panel voltage (20V max)    |
| PC1   | Vbat (A4)     | Battery voltage (15V max)        |

Note: Uses voltage dividers for level shifting to 3.3V ADC range.

### Rain Gauge Interface (CD4040 Counter + 74HC166 Shift Register)

| Pin   | Function       | Description                        |
|-------|----------------|------------------------------------|
| PA8   | Counter Reset  | CD4040 reset (active HIGH)         |
| PB10  | Clock          | 74HC166 clock (CLK)                |
| PB4   | Shift/Load     | 74HC166 SH/!LD control             |
| PB5   | Serial Out     | 74HC166 QH (serial data output)    |

### Status LED

| Pin   | Function | Description                              |
|-------|----------|------------------------------------------|
| PA0   | LED      | Status LED on SAPI Arduino Shield        |

---

## Board Configuration

### VBAT Solder Bridge (SB45) - Recommended

On both **Nucleo L476RG** and **Nucleo F103RB** boards, solder the **SB45** jumper to connect VDD to VBAT.

**Why:** The RTC uses the LSE (Low Speed External) 32.768 kHz crystal oscillator. Without VBAT powered, the LSE oscillator must restart from scratch on every boot, which can take several hundred milliseconds to several seconds. During this time, the system may appear to hang at "Tentando inicializar o RTC com LSE..." message.

**Benefits of closing SB45:**
- LSE oscillator remains running during resets (watchdog, software reset)
- Instant RTC startup instead of waiting for crystal stabilization
- Backup registers are preserved across resets
- Only a complete power loss requires LSE to restart

**Location:** SB45 is located on the bottom side of the Nucleo board, near the STM32 MCU.

---

## GPIO Summary by Port

| Port A | Port B | Port C |
|--------|--------|--------|
| PA0 - LED | PB0 - LoRa DIO0 | PC0 - Vpanel ADC |
| PA1 - LoRa RST | PB3 - LoRa Power | PC1 - Vbat ADC |
| PA4 - LoRa NSS | PB4 - RG Shift/Load | PC10 - US Echo |
| PA5 - LoRa SCK | PB5 - RG Serial Out | PC11 - US Trigger |
| PA6 - LoRa MISO | PB8 - I2C SCL | |
| PA7 - LoRa MOSI | PB9 - I2C SDA | |
| PA8 - RG Reset | PB10 - RG Clock | |

---

## Live Data & Graphics

You can monitor the real-time sensor data through the following links:

| Variable | Data Visualization Link |
| :--- | :--- |
| **Water Level** | [View Level (cm)](https://ilha3d.com/sapi/view.php?id_station=33&var=level) |
| **Temperature** | [View Temperature (C)](https://ilha3d.com/sapi/view.php?id_station=33&var=temperature_C) |
| **Pressure** | [View Atmospheric Pressure](https://ilha3d.com/sapi/view.php?id_station=33&var=pressure) |
| **Precipitation** | [View Precipitation Pulses](https://ilha3d.com/sapi/view.php?id_station=33&var=precipitation_pulses) |
| **Signal (RSSI)** | [View Radio Signal Strength](https://ilha3d.com/sapi/view.php?id_station=33&var=rssi) |
| **Panel Voltage** | [View Solar Panel Voltage](https://ilha3d.com/sapi/view.php?id_station=33&var=panel_voltage) |
| **Battery** | [View Battery Voltage](https://ilha3d.com/sapi/view.php?id_station=33&var=bat_voltage) |

---

*Developed as part of a Master's Degree project - SAPI (Sistema de Alerta Previo de Inundacoes)*
