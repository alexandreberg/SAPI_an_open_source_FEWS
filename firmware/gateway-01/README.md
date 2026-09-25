# Gateway-01 — LoRa to HTTPS gateway

Firmware of the SAPI gateway: an ESP32 (LilyGO T-SIM7000G) that receives the stations'
LoRa packets and forwards them to the web server over HTTPS, on Wi-Fi with automatic
NB-IoT cellular failover. Release: `gateway-01-v2.0.0` (deployed 2026-03-08).

**No compiled binary is published.** A build embeds the Wi-Fi password and the API key,
so you build your own with your credentials, as described below.

## Hardware

- LilyGO T-SIM7000G (ESP32 + SIM7000G NB-IoT/LTE-M modem)
- LoRa radio (LilyGo LoRa32), 915 MHz
- Optional: an **NB-IoT** M2M SIM card for the cellular failover (LTE-M-only SIMs do not
  work with this firmware)

## Build and flash

1. Install [PlatformIO](https://platformio.org/) (VS Code extension or CLI).
2. Create your credentials file from the template — it is ignored by git:

   ```bash
   cp include/credentials_sample.h include/credentials.h
   ```

3. Edit `include/credentials.h`:
   - `ssid`, `wifi_password` — your Wi-Fi network;
   - `apiKey` — a random key (`openssl rand -hex 32`). It must be **identical** to
     `$VALID_API_KEY` in the server's `private_configs/sapi/db_config.php` (see
     [`../../webserver/`](../../webserver/)): the gateway sends it in the `X-API-Key`
     header and also uses it as the HMAC-SHA256 key that signs every payload;
   - `server`, `resource`, `serverName` — your own server and endpoint
     (`/sapi/sensorData/receive-data.php`).
4. Adjust the per-station calibration (`levelZero`, in cm) in `src/stationConfig.cpp`:
   the gateway computes `level = levelZero − distance_raw` for each water-level station.
5. Build and upload (the upload port is set in `platformio.ini`; change it for your
   system):

   ```bash
   pio run -t upload
   pio device monitor -b 115200
   ```

## Files

| File | Purpose |
|------|---------|
| `src/main.cpp` | LoRa reception, Wi-Fi/NB-IoT link management, failover logic |
| `src/sendData.cpp`, `include/sendData.h` | MessagePack payload, HMAC signature, HTTPS POST over Wi-Fi or cellular |
| `src/stationConfig.cpp`, `include/stationConfig.h` | Per-station configuration and level calibration |
| `include/trust_anchors.h` | TLS trust anchor (ISRG Root X1) for the cellular path |
| `include/credentials_sample.h` | Credentials template |

## Validation

The NB-IoT failover was validated on 2026-03-08: 260 transmissions, 247 over Wi-Fi and
13 over NB-IoT, all delivered (HTTP 200), through several Wi-Fi down/up cycles. See
[`docs/tests/m2m/`](../../docs/tests/m2m/M2M_Test_Report.md).
