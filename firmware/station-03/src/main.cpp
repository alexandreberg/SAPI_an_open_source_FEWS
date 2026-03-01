/* Station-03 STM32 Nucleo L476-RG code
 * 
 *
 * Alexandre Nuernberg - alexandreberg@gmail.com
 *
 *
 * RFM95 LoRa Connection - STM32 Bluepill
 *    VCC - 3.3V
 *    GND - GND
 *    LoRa_SCK - LoRa_SCK (PA5)
 *    LoRa_MISO - LoRa_MISO (PA6)
 *    LoRa_MOSI - LoRa_MOSI (PA7)
 *    NSS - (PA4)
 *    RESET - (PA0)
 *    LoRa_DIO0 - (PA1)
 *
 * BackupRegisters:
 * See https://community.st.com/t5/stm32-mcus/how-to-use-the-stm32-s-backup-registers/ta-p/49892
 *
 * Backup registers can be written/read and protected and have the option of being preserved in VBAT mode when the VDD domain is powered off.
 * The BackUp Registers are part of the RTC peripheral so we will need to enable the RTC to be able to access them.
 * The STM32 Blue Pill, which typically uses the STM32F103C8T6 microcontroller, has 10 backup registers.
 * Each register is 16 bits wide, providing a total of 20 bytes of data that can be stored in the backup domain.
 *
 * (!) To be able to preserve the backup registers through a power cycle, VBAT must remain powered when VDD is removed, this is called the VBAT mode.
 *
 * 23.11.2024 - Changing the code to read and hibernate for 1 minute between ultrasound readings.
 *             - 1min on and 1min off, adjust to not stay on for so long and turn off as soon as it transmits
 * 24.11.2024 - changing the readUltrasonic() function to work with the median
 *
 * 24.12.2024 - Cleaning and organizing the file
 *
 * TODO:
 * reactivate hibernation and make it sleep for 1min
 *
 *
BackupRegister Values:
Register - Value - Description
BR0 - último estado (logState)
BR1  →
BR2  → != 0 - indicates that  STM32 should to go into deepsleep
BR3  → != 0 -//indicates that  have to go into deepsleep
BR4  → contador de boots
BR5 e BR6 → timestamp (parte baixa/alta)
BR7 - FREE
BR8 - FREE
BR9 - FREE

Flag to enter in deep sleep mode:
goToSleep_flag = 0; i boot flag
goToSleep_flag = 1; //hibernation flag normal deepsleep ?????
goToSleep_flag = 2; //hibernation flag 1min ?????

Last state before reset/sleep:
goToSleep = 10 // vai dormir
loop = 20 // entrou no loop
onReceive = 30
sendReadings = 40

-06.08.2025 OK  - Cleaning and organizing the file
            OK  - Identing the file
            OK - Increasing RSSI signal for LoRa power to 20dBm
            - Correcting problem that sends lora message before ending US routines.
-27.08.2025 - Trying to correct the problem that freezes the return of the sensor after the hibernation leaving the holes in the graphic.
 * Debug-enhanced version of BluePill LoRa Transmitter
 * - Logs last execution state into BackupRegisters
 * - Handles new LoRa timestamp message format: "TS:<timestamp>"
 * - Prints backup registers at startup
 * 
BR1 / BR2 → timestamp (parte baixa/alta)

Sobre a lib low power:
https://github.com/stm32duino/STM32LowPower
void shutdown(uint32_t ms): enter in shutdown mode param ms (optional): number of milliseconds before to exit the mode. The RTC is used in alarm mode to wakeup the board in ms milliseconds.
Important:
RTC used as Wakeup source requires to have LSE or LSI as clock source. If one of them is used nothing is changed else it will configure it to use LSI clock source. One exception exists when SHUTDOWN_MODE is requested and PWR_CR1_LPMS is defined, in that case LSE is required. So, if the board does not have LSE, it will fail.
Eu uso o: rtc.setClockSource(STM32RTC::LSE_CLOCK); está correto.
The board will restart when exit shutdown mode.

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

/*********************************************** Sensor Description ***********************************************/
#define sensor_id "Station_03"      // <<=== Sensor identification  ==>> CHANGE HERE!!
#define sensor_location "Bridge02" // <<=== Sensor location        ==>> CHANGE HERE!!

/*********************************************** Macro Definitions ***********************************************/
// Enable (uncommenting) or disable (commenting out) services and periferals
//#define enableVerbosity // Add more debbug log messages to serial monitor
#define enableSerialLog  // enable Serial debug on console
#define enableWatchDog   // enable watchdog for deepsleep
#define enableUltrasonic // enable Ultrasonic Sensor
//#define enableUS100Test  // Issue #24 diagnostic: disabled after confirming sensor failure and formula fix
#define enableRTCstm32   // using STM32 internal RTC Clock
#define enableLoRa // enable LoRa communication
#define enableDebug // Enable verbosity in debugging log
#define enableTPHSensor // Enable TPH (Temperature, Pressure, Humidity) sensor
#define enableADC // Enable ADC reading for solar pannel and battery voltages
//#define enableRainGauge // Enable the Rain Gauge

/*********************************************** Library Definitions ***********************************************/
#include <Arduino.h>
#include <stdlib.h>
#include <STM32LowPower.h> //Deep Sleep for STM32
#include <SPI.h>
#include <time.h>

#ifdef enableRTCstm32
#include <STM32RTC.h>
#endif

#ifdef enableWatchDog
#include <IWatchdog.h>
#endif


#ifdef enableLoRa
#include <LoRa.h> // sandeepmistry/LoRa library
#endif

#ifdef enableTPHSensor
#include "tph_sensor.h"
#endif

#ifdef enableADC
#include "adc.h"
#endif

#ifdef enableRainGauge
#include "raingauge.h"
#endif

#ifdef enableUltrasonic
#include "ultrasonic.h"
#endif

#ifdef enableUS100Test
#include "test-us100.h"
#endif

/*********************************************** Global Variables ***********************************************/
String version = "SAPI_Station03_Nucleo_L476RG v1.0.0"; // ==> CHANGE HERE! <==

// #define hibernation_time 880 // Hibernation time for deep sleep in seconds (15 min - 20 sec)
// #define hibernation_time 15  // Test mode: 15 s
// #define hibernation_time 60  // Test mode: 1 min
#define hibernation_time 300    // Production: 5 min

#ifdef enableWatchDog
#define ledPin PA0 // Choose LoRa_SCK2 (PB6) or LoRa_DIO_2 (PA0) - have to change jump (JP4) in the SAPI LoRA Arduino Shield  V1.0
#endif

#ifdef enableRTCstm32 // Working
boolean onReceive_flag = 0;
/* Get the rtc object */
STM32RTC &rtc = STM32RTC::getInstance();
byte startUpMinute = 0;
/* Change these values to set the current initial time */
byte seconds = 0;
byte minutes = 0;
byte hours = 0;

/* Change these values to set the current initial date */
byte weekDay = 0;
byte day = 0;
byte month = 0;
byte year = 0;

#endif // enableRTCstm32

/** @brief Measured distance in centimeters, used by fillSensorData() */
int32_t readingDistance = -99;

/**
 * @brief US-100 internal temperature in Celsius, used by fillSensorData().
 *
 * Stored into sensorData.surface_temperature (repurposed field, thesis scope).
 * Value -99.0 means "not available" (sensor not read or reading invalid).
 * See GitHub Issue #18 for context and Issue #17 for the long-term fix.
 */
float readingUSTemperature = -99.0f;

#ifdef enableTPHSensor
/* TPH sensor readings are now stored in the tph_sensor_readings_t struct */
#endif // enableTPHSensor

int goToSleep_flag = 0; // Flag to enter in deep sleep mode

#ifdef enableLoRa
// ================== LoRa Configuration Pins ==================
#define LoRa_SCK   PA5
#define LoRa_MISO  PA6
#define LoRa_MOSI  PA7
#define LoRa_NSS   PA4  // LoRa radio chip select
#define LoRa_RST   PA1  // LoRa radio reset
#define LoRa_DIO0  PB0  // Must be a hardware interrupt pin
#define LoRa_Pwr_enable PB3 // Enable LoRa power supply in the shield   

// Define LoRa Communication Band:
#define BAND 915E6 /*  915E6 for Brazil (902-928 MHz) \
                       433E6 for Asia                 \
                       866E6 for Europe               \
                       915E6 for North America */

int lora_startup_counter = 0; // Counter to check if LoRa chip started communication propperly
// long readingID = 0;           // Sending packet N°

// String LoRaMessage = ""; // String to store the LoRa Message that should be sent


#endif                   // enableLoRa

// ================== Data Struct ==================
struct __attribute__((packed)) SensorData {
  uint32_t idStation = 03; // Change for the station id number in the DB
  uint32_t reading_number; // increment each transmission
  uint32_t timestamp;   // createdAt
  int32_t level;        // ultrasonic measurement
  float temperature;    // TPH sensor temperature (C)
  float pressure;       // TPH sensor pressure (hPa)
  int32_t humidity;     // TPH sensor humidity (%)
  int16_t precipitation_pulses; // Rain Gauge pulses
  float surface_temperature; // Repurposed for Station-03: US-100 internal temperature (°C).
                             // Thesis-scope workaround — see GitHub Issue #18 and Issue #17.
  int32_t Vbat;         // in milivolts
  int32_t Vpanel;       // in milivolts
  int32_t rssi;         // actual LoRa RSSI
  float snr;          // Lora SNR
  int32_t sigWiFi;      // always 0
  int32_t sigCel;       // always 0
};
SensorData sensorData;
// uint32_t reading_counter = 0;

/* Enable HardwareSerial when you dettach the STLINK from the nucleo board for saving battery
 Connect STLIN externally for proggramming and you can use FTDI in the pins:
 FTDI connection:
FTDI	|	CN10 Morpho	|	STM32 Pin	|	Function
RX		|	Pin 21		|	PA9			|	USART1_TX
TX		|	Pin 33		|	PA10		|	USART1_RX
GND		|	Pin 20		|	GND			|	GND
This option just should be used if the STLINK is detached and if the jumping bridges SB62 and SB63 are open on STM32 Nucleo F103RB.
If you weld these two jumpers so you can use the ordinary USART2 pins available in the SAPI Morpho Shield,
connect J10 (TX and RX USART2) to the separated STLINK CN3 and there is no need to uncomment the two following lines. */
// HardwareSerial Serial1(PA10, PA9);  // RX, TX
// #define Serial Serial1 // Avoid to change all the code whan STlink is disconnected from nucleo board.

/*********************************************** Function Prototypes ***********************************************/
void sketchSetup();
void logState(uint16_t code);

#ifdef enableRTCstm32
void setupRTC();
void setTime();
void readTime();
#endif // enableRTCstm32

#ifdef enableUltrasonic
void updateSensorDataUltrasonic(const ultrasonic_readings_t *readings);
#endif // enableUltrasonic

#ifdef enableLoRa
void LoRa_rxMode();
void LoRa_txMode();
void onReceive(int packetSize);
void LoRa_sendMessage(String message);
void onTxDone();
boolean runEvery(unsigned long interval);
void checkonReceive();
boolean runClockEvery(unsigned long interval);
void start_LoRa();
void sendSensorData();
#endif // enableLoRa

void goToSleep();
void updateSensorDataADC(const adc_readings_t *readings);
#ifdef enableRainGauge
void updateSensorDataRain(const raingauge_readings_t *readings);
#endif
#ifdef enableTPHSensor
void updateSensorDataTPH(const tph_sensor_readings_t *readings);
#endif
void fillSensorData();
void printSensorData(const SensorData &d);

/*********************************************** End Function Prototypes *******************************************/
// TODO: Need to be better documented and clarified!!!!
void setup()
{
  sketchSetup();           // Setup of the Serial log and initial serial setup
  pinMode(ledPin, OUTPUT); // Initialize digital ledPin (LED on SAPI Arduino Shield) as an output.

  // Blink pattern at startup
  for (int i = 0; i < 10; i++)
  {
    digitalWrite(ledPin, HIGH);
    delay(150);
    digitalWrite(ledPin, LOW);
    delay(150);
  }

  // Contador de reinicializações no BackupRegister 4
  /* Cada vez que o setup() roda (seja por reset, watchdog ou wake-up), ele incrementa o valor armazenado no BR4.*/
  enableBackupDomain();
  uint16_t bootCounter = getBackupRegister(4);
  bootCounter++;
  setBackupRegister(4, bootCounter);
  disableBackupDomain();
  Serial.print("Boot counter (BR4): ");
  Serial.println(bootCounter);

#ifdef enableWatchDog
  enableBackupDomain(); // Function of .platformio\packages\framework-arduinoststm32\cores\arduino\stm32\backup.h

  if (getBackupRegister(2) != 0)
  { // indicates that  STM32 should to go into deepsleep
    Serial.println("Sistema reinicializado pelo WatchDog ... === Ira entrar em hibernacao ... === BR2 = " + String(getBackupRegister(2)));
    setBackupRegister(2, 0);
    delay(100);
    setupRTC();
    LowPower.begin();
    goToSleep_flag = 2; // hibernation flag 1min
    goToSleep();
  }

  disableBackupDomain();
  IWatchdog.begin(10000000); // Init the watchdog timer with 10 seconds timeout
#endif

  // TODO: Enable the LoRa power supply HW-613 module
  // pinMode(LoRa_Pwr_enable, OUTPUT);
  // digitalWrite(LoRa_Pwr_enable, HIGH);

  delay(50); // delay for active the power supply

  Serial.println("Tentando inicializar o RTC com LSE...");
  setupRTC();
  delay(50);

#ifdef enableTPHSensor
  Serial.println("Initializing TPH sensor...");

  if (tph_sensor_init())
  {
    Serial.println("TPH sensor ready!");
  }
  else
  {
    Serial.println("Warning: TPH sensor initialization failed - continuing without sensor");
  }
  delay(50);
#endif

#ifdef enableADC
  Serial.println("Reading Voltages from Battery and Solar Panel ...");
  adc_init();
#endif

#ifdef enableRainGauge
  Serial.println("Initializing Rain Gauge pins ...");
  raingauge_init();
#endif

#ifdef enableUltrasonic
  Serial.println("Initializing Ultrasonic sensor ...");
  ultrasonic_init();
#endif

#ifdef enableUS100Test
  Serial.println("Initializing US-100 temperature diagnostic (Issue #24)...");
  us100_test_init();
#endif

  Serial.println("LowPower.begin()");
  LowPower.begin();
  goToSleep();

  Serial.println("start_LoRa()"); //ok
  start_LoRa();
}

/*********************************************** loop () ***********************************************/
void loop()
{
  logState(20); // entrou no loop

#ifdef enableWatchDog
  IWatchdog.reload();
#endif

#ifdef enableTPHSensor
  tph_sensor_readings_t tphReadings;
  if (tph_sensor_read(&tphReadings))
  {
    #ifdef enableVerbosity
	tph_sensor_printReadings(&tphReadings);
    #endif
    updateSensorDataTPH(&tphReadings);
  }
#endif

#ifdef enableWatchDog
  IWatchdog.reload();
#endif

#ifdef enableRainGauge
  raingauge_readings_t rain;

  if (raingauge_getReadings(&rain))
  {
    updateSensorDataRain(&rain);
    raingauge_printReadings(&rain);
    raingauge_resetCounter();
  }

#endif

#ifdef enableWatchDog
  IWatchdog.reload();
#endif

#ifdef enableUltrasonic
  ultrasonic_readings_t usReadings;

  if (ultrasonic_read(&usReadings))
  {
    #ifdef enableVerbosity
	ultrasonic_printReadings(&usReadings);
    #endif
    updateSensorDataUltrasonic(&usReadings);
  }
#endif

#ifdef enableUS100Test
  us100_test_read_temperature();
#endif

#ifdef enableVerbosity
#if defined(enableTPHSensor) && defined(enableUltrasonic)
  /*
   * Side-by-side temperature comparison:
   *   US-100 internal thermistor  vs  SHT20 IP65 external probe
   *
   * The US-100 uses its thermistor to compensate the speed-of-sound internally,
   * but this comparison helps validate how close the two sensors agree in the
   * actual installation environment.
   */
  if (usReadings.readingValid && tphReadings.readingValid &&
      !isnan(usReadings.internalTemperature) && !isnan(tphReadings.temperature)) {
    float tempDelta = usReadings.internalTemperature - tphReadings.temperature;
    Serial.println("========== Temperature Comparison ==========");
    Serial.print("  US-100 internal temp : ");
    Serial.print(usReadings.internalTemperature, 1);
    Serial.println(" C");
    Serial.print("  SHT20 (IP65) temp    : ");
    Serial.print(tphReadings.temperature, 2);
    Serial.println(" C");
    Serial.print("  Delta (US100 - SHT20): ");
    if (tempDelta >= 0.0f) Serial.print("+");
    Serial.print(tempDelta, 1);
    Serial.println(" C");
    Serial.println("============================================");
  }
#endif
#endif

#ifdef enableWatchDog
  IWatchdog.reload();
#endif

#ifdef enableADC
  adc_readings_t adcReadings;

  if (adc_read(&adcReadings))
  {
    // adc_printReadings(&adcReadings); // Reduce verbosity in serial log
    updateSensorDataADC(&adcReadings);
  }
#endif

    fillSensorData();
    sendSensorData();

#ifdef enableWatchDog
    IWatchdog.reload();
#endif

    enableBackupDomain();
    setBackupRegister(2, 10);
    disableBackupDomain();

    goToSleep();
    delay(15 * 1000); // DEBUG
  }

  /*********************************************** End loop () ***********************************************/

  /*********************************************** Function Definitions ***********************************************/
  //////////////////////////////////////////////////// sketchSetup ////////////////////////////////////////////////////
  // Shows system infomation and configures serial interface
  void sketchSetup()
  {
    Serial.begin(115200);
    // Serial1.begin(115200); 
    delay(200);

    Serial.println("\nStarting Sensor: " + String(sensor_id) + " on " + String(sensor_location));
    Serial.println("Ilha 3d");
    Serial.println("sapi.ilha3d.com");
    Serial.println("\n");
    Serial.println(String(version));
    Serial.println("");

    Serial.println("=== Boot STM32 Sensor Node ===");
    Serial.print("Last state before reset/sleep: ");
    Serial.println(getBackupRegister(0));
    Serial.print("BackupReg1 (TS low): ");
    Serial.println(getBackupRegister(5));
    Serial.print("BackupReg2 (TS high): ");
    Serial.println(getBackupRegister(6));

#ifdef enableVerbosity
  Serial.println("Last values of all Backup Registers:");
  Serial.println("BR0 = " + String(getBackupRegister(0)));
  Serial.println("BR1 = " + String(getBackupRegister(1)));
  Serial.println("BR2 = " + String(getBackupRegister(2)));
  Serial.println("BR3 = " + String(getBackupRegister(3)));
  Serial.println("BR4 = " + String(getBackupRegister(4)));
  Serial.println("BR5 = " + String(getBackupRegister(5)));
  Serial.println("BR6 = " + String(getBackupRegister(6)));
  Serial.println("BR7 = " + String(getBackupRegister(7)));
  Serial.println("BR8 = " + String(getBackupRegister(8)));
  Serial.println("BR9 = " + String(getBackupRegister(9)));
#endif
}

#ifdef enableRTCstm32
void setupRTC()
{
  // Select RTC clock source: LSI_CLOCK, LSE_CLOCK or HSE_CLOCK.
  // By default the LSI is selected as source.
  // LSE is more accurate but requires external crystal
  // LSI is internal, faster to start but less accurate

  // Enable power clock and backup domain access
  __HAL_RCC_PWR_CLK_ENABLE();
  HAL_PWR_EnableBkUpAccess();

  // CRITICAL for STM32L4 series: Configure LSE drive strength BEFORE starting LSE
  // The Nucleo L476RG crystal may need higher drive strength to start reliably
  // Options: RCC_LSEDRIVE_LOW, RCC_LSEDRIVE_MEDIUMLOW, RCC_LSEDRIVE_MEDIUMHIGH, RCC_LSEDRIVE_HIGH
  __HAL_RCC_LSEDRIVE_CONFIG(RCC_LSEDRIVE_MEDIUMHIGH);

  // Check if LSE is already running (VBAT was powered)
  if (__HAL_RCC_GET_FLAG(RCC_FLAG_LSERDY)) {
    Serial.println("LSE already running, using LSE clock");
    rtc.setClockSource(STM32RTC::LSE_CLOCK);
    rtc.begin();
    return;
  }

  Serial.println("LSE not ready, configuring with proper drive strength...");

  // Configure LSE oscillator with proper settings for L4 series
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_LSE;
  RCC_OscInitStruct.LSEState = RCC_LSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;  // Don't touch PLL

  uint32_t startTime = millis();

  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) == HAL_OK) {
    // Wait for LSE to stabilize (can take up to 2 seconds on some boards)
    while ((millis() - startTime) < 3000) {
      if (__HAL_RCC_GET_FLAG(RCC_FLAG_LSERDY)) {
        Serial.print("LSE ready after ");
        Serial.print(millis() - startTime);
        Serial.println(" ms");
        rtc.setClockSource(STM32RTC::LSE_CLOCK);
        rtc.begin();
        return;
      }
      delay(10);
    }
  }

  // If LSE failed, try with HIGH drive strength as last resort
  Serial.println("LSE failed with MEDIUMHIGH, trying HIGH drive...");
  __HAL_RCC_LSEDRIVE_CONFIG(RCC_LSEDRIVE_HIGH);

  // Reset LSE and try again
  __HAL_RCC_LSE_CONFIG(RCC_LSE_OFF);
  delay(10);

  RCC_OscInitStruct.LSEState = RCC_LSE_ON;
  startTime = millis();

  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) == HAL_OK) {
    while ((millis() - startTime) < 3000) {
      if (__HAL_RCC_GET_FLAG(RCC_FLAG_LSERDY)) {
        Serial.print("LSE ready with HIGH drive after ");
        Serial.print(millis() - startTime);
        Serial.println(" ms");
        rtc.setClockSource(STM32RTC::LSE_CLOCK);
        rtc.begin();
        return;
      }
      delay(10);
    }
  }

  // Final fallback to LSI
  Serial.println("LSE timeout, falling back to LSI clock");
  rtc.setClockSource(STM32RTC::LSI_CLOCK);
  rtc.begin();
}

void setTime()
{
  // Set the time
  rtc.setHours(hours);
  rtc.setMinutes(minutes);
  rtc.setSeconds(seconds);

  // Set the date
  rtc.setWeekDay(weekDay);
  rtc.setDay(day);
  rtc.setMonth(month);
  rtc.setYear(year);
}

void readTime()
{
  // Print date...
  Serial.println("Data e hora armazenada no RTC Local");
  Serial.printf("%02d/%02d/%02d ", rtc.getDay(), rtc.getMonth(), rtc.getYear());

  // ...and time
  Serial.printf("%02d:%02d:%02d.%03d\n", rtc.getHours(), rtc.getMinutes(), rtc.getSeconds(), rtc.getSubSeconds());
}
#endif // enableRTCstm32

#ifdef enableUltrasonic
/**
 * @brief Update sensor data structure with ultrasonic readings
 *
 * @param readings Pointer to ultrasonic_readings_t structure
 *
 * @note Preserves special failure codes:
 *       US_SENSOR_FAILURE_CODE (-888): Sensor hardware failure (startup test failed)
 *       -99: Invalid reading (not enough valid samples)
 */
void updateSensorDataUltrasonic(const ultrasonic_readings_t *readings) {
    if (readings != nullptr && readings->readingValid) {
        readingDistance = readings->correctedDistance;
        // Capture US-100 internal temperature into repurposed surface_temperature field.
        // NaN means the sensor did not return a temperature (e.g. non-US-100 sensor type).
        // See GitHub Issue #18 (workaround) and Issue #17 (long-term dedicated field).
        readingUSTemperature = isnan(readings->internalTemperature) ? -99.0f : readings->internalTemperature;
    } else if (readings != nullptr && readings->distance == US_SENSOR_FAILURE_CODE) {
        // Preserve the sensor failure code for database tracking
        readingDistance = US_SENSOR_FAILURE_CODE;
        readingUSTemperature = -99.0f;
    } else {
        readingDistance = -99; // Invalid reading marker
        readingUSTemperature = -99.0f;
    }
}
#endif // enableUltrasonic

//////////////////////////////////////////////////// goToSleep() ////////////////////////////////////////////////////
void goToSleep()
{
  logState(10); // vai dormir
  if (goToSleep_flag == 2)
  { // hibernará por 1 minuto
#ifdef enableWatchDog
    IWatchdog.reload();
#endif
    Serial.println("Hibernando por " + String(hibernation_time) + " segundos... goToSleep_flag == " + String(goToSleep_flag));
    delay(10);
    LowPower.shutdown(1000 * hibernation_time); // sleeps by hibernation_time sec
  }
  // Entra em Deep Sleep e acorda em horas cheias hh:00 ou hh:30
  if (goToSleep_flag == 1)
  {
    //   //DateTime now = rtc.now();
    //   //int sleepTime = 59 - now.minute(); //TinyRTC
#ifdef enableWatchDog
    IWatchdog.reload();
#endif
    Serial.println("Hibernando por " + String(hibernation_time) + " segundos... goToSleep_flag == " + String(goToSleep_flag));
    delay(10);
    LowPower.shutdown(1000 * hibernation_time); // sleeps by hibernation_time sec
  }
}

#ifdef enableLoRa
void LoRa_rxMode()
{
  LoRa.enableInvertIQ(); // active invert I and Q signals
  LoRa.receive();        // set receive mode
}

void LoRa_txMode()
{
  LoRa.idle();            // set standby mode
  LoRa.disableInvertIQ(); // normal mode
}

//==================================== Lora Callback void onReceive ===================================================
void onReceive(int packetSize)
{
  if (packetSize == 0) return;

  String LoRaData = LoRa.readString();
  Serial.print("LoRaData recebida: ");
  Serial.println(LoRaData);

  if (LoRaData.startsWith("TS:"))
  {
    String tsStr = LoRaData.substring(3, LoRaData.indexOf('|') > 0 ? LoRaData.indexOf('|') : LoRaData.length());
    unsigned long ts = tsStr.toInt();
    Serial.print("Timestamp recebido: ");
    Serial.println(ts);

    // ===== Conversão do timestamp para hora normal =====
    time_t rawtime = (time_t)ts;
    struct tm *timeinfo = gmtime(&rawtime); // ou localtime() se quiser considerar fuso

    char buffer[30];
    sprintf(buffer, "%02d/%02d/%04d %02d:%02d:%02d",
            timeinfo->tm_mday,
            timeinfo->tm_mon + 1,
            timeinfo->tm_year + 1900,
            timeinfo->tm_hour,
            timeinfo->tm_min,
            timeinfo->tm_sec);

    Serial.print("Hora convertida: ");
    Serial.println(buffer);
    // ================================================

    logState(30); //onReceive
    enableBackupDomain();
    setBackupRegister(5, (uint16_t)(ts & 0xFFFF));
    setBackupRegister(6, (uint16_t)((ts >> 16) & 0xFFFF));
    disableBackupDomain();
  }
  else
  {
    Serial.println("Mensagem LoRa recebida em formato inesperado.");
  }
}


void LoRa_sendMessage(String message)
{
  // if (!distance_reading_done)
  // {
  LoRa_txMode();        // set tx mode
  LoRa.beginPacket();   // start packet
  LoRa.print(message);  // add payload
  LoRa.endPacket(true); // finish packet and send it
  // }
}

void onTxDone()
{
#ifdef enableSerialLog
  Serial.println("TxDone - Transmissão completa.");
#endif

  // Define a flag para hibernar. Isso só será executado quando a transmissão for finalizada.
  goToSleep_flag = 2;

  // Retorna ao modo de recepção para o próximo ciclo
  LoRa_rxMode();
}

boolean runEvery(unsigned long interval)
{
  static unsigned long previousMillis = 0;
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval)
  {
    previousMillis = currentMillis;
    return true;
  }
  return false;
}

void checkonReceive()
{ // TODO ver se essa é a função que recebe o retorno do gateway
  if (onReceive_flag == 0)
  {
    int time = (rtc.getMinutes() - startUpMinute);
    Serial.print("time:   ");
    Serial.println(time);
    if (rtc.getMinutes() - startUpMinute >= 2)
    {
      // #ifdef enableSerialLog
      Serial.print("Did not receive the Date from the Gateway! Going to sleep for 30 seconds");
      delay(100);
      // #endif
      // vai dormir por 30 segundos...
      //  LowPower.shutdown(1000 * hibernation_time); //D.S por 1000ms* 30s * sleepTime/
    }
  }
}

boolean runClockEvery(unsigned long interval)
{
  static unsigned long previousMillis = 0;
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval)
  {
    previousMillis = currentMillis;
    return true;
  }
  return false;
}

//=============================================================================================================
// Initialize LoRa module
void start_LoRa()
{
  // LoRa.setTxPower(20); // Change LoRa transmission power to 20dBm
  // Serial.println("LoRa Power Trasnmission set to: 20dBm"); // ok 

  LoRa.setPins(LoRa_NSS, LoRa_RST, LoRa_DIO0); // SPI LoRa pins

  while (!LoRa.begin(BAND) && lora_startup_counter < 10)
  {
    Serial.print(".");
    lora_startup_counter++;
    delay(500);
  }
  if (lora_startup_counter == 10)
  {
    Serial.println("LoRa initialization Failed!");
    delay (100);
  }
  if (lora_startup_counter < 10)
  {
#ifdef enableSerialLog
    Serial.println("LoRa initialization OK!");
#endif
  }

  /* Endurecer a recepção: CRC + Sync Word + parâmetros idênticos
  Com CRC desativado e sync word default, qualquer ruído “LoRa-like” pode passar. Ative CRC e defina Sync Word e parametrização idêntica nos dois lados (sensor e gateway). 
  Acrescente no setup do LoRa em ambos:
  */
  // LoRa.setSpreadingFactor(7);          
  /* igual nos dois
                                        Spreading Factor: Change the spreading factor of the radio.
                                        LoRa.setSpreadingFactor(spreadingFactor);
                                        spreadingFactor - spreading factor, defaults to 7
                                        Supported values are between 6 and 12. If a spreading factor of 6 is set, implicit header mode must be used to transmit and receive packets.*/
  // LoRa.setSignalBandwidth(125E3);      
  /* igual nos dois
                                        Signal Bandwidth:  Change the signal bandwidth of the radio.
                                        LoRa.setSignalBandwidth(signalBandwidth);
                                        signalBandwidth - signal bandwidth in Hz, defaults to 125E3.
                                        Supported values are 7.8E3, 10.4E3, 15.6E3, 20.8E3, 31.25E3, 41.7E3, 62.5E3, 125E3, 250E3, and 500E3.*/
  // LoRa.setCodingRate4(5);              
  /* CR 4/5 (igual nos dois)
                                        Coding Rate: Change the coding rate of the radio.
                                        LoRa.setCodingRate4(codingRateDenominator);
                                        codingRateDenominator - denominator of the coding rate, defaults to 5
                                        Supported values are between 5 and 8, these correspond to coding rates of 4/5 and 4/8. The coding rate numerator is fixed at 4.*/
  // LoRa.setPreambleLength(8);          
   /* igual nos dois
                                      Preamble Length: Change the preamble length of the radio.
                                      LoRa.setPreambleLength(preambleLength);
                                      preambleLength - preamble length in symbols, defaults to 8
                                      Supported values are between 6 and 65535.*/
  // LoRa.setSyncWord(0x12);             
   /* igual nos dois (privado) — escolha um e padronize
                                      Sync Word: Change the sync word of the radio.
                                      LoRa.setSyncWord(syncWord);
                                      syncWord - byte value to use as the sync word, defaults to 0x12 */
  // LoRa.enableCrc();                  
   /* ATIVAR CRC (nos dois)
                                      Enable or disable CRC usage, by default a CRC is not used.
                                      LoRa.enableCrc();
                                      LoRa.disableCrc();*/
                                      
  // register the receive callback
  // LoRa.onReceive(onReceive);
  // LoRa.onTxDone(onTxDone);
  // LoRa_rxMode();
} // end start_LoRa


// ================== New LoRa implementation sends struct trough LoRa ==================
// void sendSensorData() {
//   printSensorData(sensorData);
//   LoRa.beginPacket();
//   LoRa.write((uint8_t *)&sensorData, sizeof(sensorData)); // envia bytes crus
//   LoRa.endPacket();
// }

/**
 * @brief Sends sensor data via LoRa radio transmission
 * 
 * Transmits the sensorData struct as raw bytes over LoRa.
 * Prints debug information to serial console before and after transmission.
 * 
 * @note Requires fillSensorData() to be called before this function
 * @note Uses blocking LoRa transmission
 */
// void sendSensorData() {
//     Serial.println("\n\nEnviando os dados por radio =====>\n\n");
//     printSensorData(sensorData); // ok chega aqui

//     // Start LoRa packet transmission
//     LoRa.beginPacket();
    
//     // Write raw struct bytes to LoRa buffer
//     size_t bytesEnviados = LoRa.write((uint8_t *)&sensorData, sizeof(sensorData));
    
//     // Finalize and transmit the packet
//     LoRa.endPacket();
    
//     // Print transmission confirmation
//     Serial.println(">>> Pacote enviado!"); // TODO: nok não imprime
//     Serial.print(">>> Tamanho do Payload: ");
//     Serial.print(bytesEnviados);
//     Serial.println(" bytes.");
//     Serial.println("-------------------------------------------------");
// }

/**
 * @brief Send sensor data via LoRa radio
 * 
 * Transmits the packed sensor data using LoRa radio with the configured
 * transmission parameters. Prints confirmation and statistics after successful transmission.
 * 
 * @note Uses global lora_buffer[] and lora_buffer_size from fillSensorData()
 * @note Transmission parameters configured in setup(): frequency, TX power, spreading factor, bandwidth
 * 
 * @see fillSensorData()
 */
// void sendSensorData() {
//     Serial.println("\nEnviando os dados por radio =====>");
    
//     // Print current data structure for debugging
//     printSensorData();
    
//     // Verify buffer has data
//     if (lora_buffer_size == 0) {
//         Serial.println(">>> ERRO: Buffer vazio, nada para enviar!");
//         return;
//     }
    
//     // Start LoRa packet transmission
//     LoRa.beginPacket();
    
//     // Write buffer data to LoRa packet
//     size_t bytesEnviados = LoRa.write(lora_buffer, lora_buffer_size);
    
//     // Finalize and transmit packet
//     if (LoRa.endPacket()) {
//         // Print transmission confirmation
//         Serial.println(">>> Pacote enviado com sucesso!");
//         Serial.print(">>> Tamanho do Payload: ");
//         Serial.print(bytesEnviados);
//         Serial.println(" bytes.");
//         Serial.println("-------------------------------------------------");
//     } else {
//         Serial.println(">>> ERRO: Falha ao enviar pacote LoRa!");
//         Serial.println("-------------------------------------------------");
//     }
// }

void sendSensorData() {
  fillSensorData();
  printSensorData(sensorData);

  LoRa.beginPacket();
  LoRa.write((uint8_t *)&sensorData, sizeof(sensorData)); // envia bytes crus
  LoRa.endPacket();
}

#endif // enableLoRa

/*********************************************** Helpers ***********************************************/
void logState(uint16_t code)
{
  enableBackupDomain();
  setBackupRegister(0, code);
  disableBackupDomain();
}

// Funções auxiliares no seu main.cpp ou arquivo de utilitários
void updateSensorDataADC(const adc_readings_t *readings) {
    sensorData.Vbat = (int32_t)(readings->batteryVoltage * 1000);
    sensorData.Vpanel = (int32_t)(readings->panelVoltage * 1000);
}

#ifdef enableRainGauge
void updateSensorDataRain(const raingauge_readings_t *readings) {
    sensorData.precipitation_pulses = (int16_t)readings->pulseCount;
}
#endif // enableRainGauge

#ifdef enableTPHSensor
/**
 * @brief Update sensor data structure with TPH sensor readings
 *
 * @param readings Pointer to tph_sensor_readings_t structure
 */
void updateSensorDataTPH(const tph_sensor_readings_t *readings) {
    if (readings == nullptr || !readings->readingValid) {
        return;
    }

    if (!isnan(readings->temperature)) {
        sensorData.temperature = readings->temperature;
    }
    if (!isnan(readings->pressure)) {
        sensorData.pressure = readings->pressure;
    }
    if (!isnan(readings->humidity)) {
        sensorData.humidity = (int32_t)readings->humidity;
    } else {
        sensorData.humidity = -99;  /* Not available marker */
    }
}
#endif

// Fills data struct to send via LoRa
void fillSensorData()
{
  enableBackupDomain();
  uint16_t bootCounter = getBackupRegister(4);
  disableBackupDomain();

  sensorData.reading_number = bootCounter;
  sensorData.timestamp = 0; // TODO: implement need to get the clock from the gateway
  sensorData.level = readingDistance;
  sensorData.surface_temperature = readingUSTemperature;
  sensorData.rssi = LoRa.packetRssi();
  sensorData.snr = LoRa.packetSnr();
  sensorData.sigWiFi = 0;
  sensorData.sigCel = 0;
}

void printSensorData(const SensorData &d) {
  Serial.println("------------------ Data Struct -------------------------------");
  Serial.print("ID Station: "); Serial.println(d.idStation);
  Serial.print("Reading #: "); Serial.println(d.reading_number);
  Serial.print("Timestamp: "); Serial.println(d.timestamp);
  Serial.print("Level: "); Serial.println(d.level);
  Serial.print("Temperature: "); Serial.println(d.temperature, 2);
  Serial.print("Pressure: "); Serial.println(d.pressure, 2);
  Serial.print("Humidity: "); Serial.println(d.humidity);
  Serial.print("Precipitation pulses: "); Serial.println(d.precipitation_pulses);
  Serial.print("US temperature (surface_temp): "); Serial.println(d.surface_temperature, 2);
  Serial.print("Vbat: "); Serial.println(d.Vbat);
  Serial.print("Vpanel: "); Serial.println(d.Vpanel);
  Serial.print("RSSI: "); Serial.println(d.rssi);
  Serial.print("SNR: "); Serial.println(d.snr);
  Serial.print("sigWiFi: "); Serial.println(d.sigWiFi);
  Serial.print("sigCel: "); Serial.println(d.sigCel);
  Serial.print("Payload size (bytes): "); Serial.println(sizeof(SensorData));
  Serial.println("-------------------------------------------------\n");
}
/*********************************************** End Function Definitions ********************************************/
