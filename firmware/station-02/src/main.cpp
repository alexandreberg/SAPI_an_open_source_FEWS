/* Blue_Pill_Lora_Transmitter_with_RFM95_BPLTwR_23.09.2021-01
 * Código do sensor que está ativo na ponte pequena
 *
 * Alexandre Nuernbegr - alexandreberg@gmail.com
 *
 * Code available on: https://github.com/alexandreberg/SAPM_Sensor_BluePill
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

Hardware state
shutdown mode: high wake-up latency (possible hundereds of ms or second timeframe), voltage supplies are cut except always-on domain, memory content are lost and system basically reboots.

- 16/Dec/2025 - Migrating the sketch from STM32 Bluepill to STM32 Nucleo F103RB
Testing radio with no US:
Station_02:
Sending packet N°: 0
LoRaMessage: Station_02/9999&9999

Gateway:
[2025-12-17 08:17:20] 7461- Mensagem Recebida de Sensor: Station_02 | Altura Lida: 9999cm | Size: 20 RSSI: -51 | SNR: 9

- 17/Dec/2025:
 - adding BME280 (Tested OK)
 - adding ADC for measure Vbat and Vpanel
 - adding RainGauge
- 24/Dec/2025:
 - migrating LoRa for struct to deal with all the variables

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
#define sensor_id "Station_02"      // <<=== Sensor identification  ==>> CHANGE HERE!!
#define sensor_location "Front_House" // <<=== Sensor location        ==>> CHANGE HERE!!

/*********************************************** Macro Definitions ***********************************************/
// Enable (uncommenting) or disable (commenting out) services and periferals
#define enableSerialLog  // enable Serial debug on console
#define enableWatchDog   // enable watchdog for deepsleep
#define enableUltrasonic // enable Ultrasonic Sensor
#define enableRTCstm32   // using STM32 internal RTC Clock
#define enableLoRa // enable LoRa communication
#define enableDebug // Enable verbosity in debugging log
#define enableBME280 // Enable BME280 temperature and pressure sensor
#define enableADC // Enable ADC reading for solar pannel and battery voltages
#define enableRainGauge // Enable the Rain Gauge

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

#ifdef enableUltrasonic
#include <NewPing.h>
#endif

#ifdef enableLoRa
#include <LoRa.h> // sandeepmistry/LoRa library
#endif

#ifdef enableBME280
#include "bme280_sensor.h"
#endif

#ifdef enableADC
#include "adc.h"
#endif

#ifdef enableRainGauge
#include "raingauge.h"
#endif

/*********************************************** Global Variables ***********************************************/
String version = "System Version: SAPI_Station02_Nucleo_F103RB_2026010201 - Rain Gauge"; // ==> CHANGE HERE! <==

#define hibernation_time 880 // Hibernation time for deep sleep in seconds (15 min - 20 sec)

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

#ifdef enableUltrasonic
const unsigned int triggerPin = PC11;
const unsigned int echoPin = PC10;
// long lastEchoDistance = 0;             // We want to keep these values after reset
unsigned long pulseLength = 0;
int32_t readingDistance = 0; // Measured distance in centimeters
// unsigned long maxReadingNumber = 0;    // Number of ultrasonic readings to do the calculation of mean and average
bool distance_reading_done = false;
#endif // enableUltrasonic

#ifdef enableBME280
float bme_temperature = 0.0;
float bme_pressure = 0.0;
bool bme_reading_done = false;
#endif // enableBME280

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
  uint32_t idStation = 2; // Change for the station id number in the DB
  uint32_t reading_number; // increment each transmission
  uint32_t timestamp;   // createdAt
  int32_t level;        // ultrasonic measurement
  float temperature;    // BME280 temperature
  float pressure;       // BME280 pressure
  int32_t humidity;     // BME280 humidity
  int16_t precipitation_pulses; // Rain Gauge pulses
  float surface_temperature; // always 0
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
This option just should be used if the STLINK is detached and if the jumping bridges SB62 and SB63 are open.
If you weld these two jumpers so you can use the ordinary USART2 pins available in the SAPI Morpho Shield,
connect J10 (TX and RX USART2) to the separated STLINK CN3 and there is no need to uncomment the two following lines. */
// HardwareSerial Serial1(PA10, PA9);  // RX, TX
// #define Serial Serial1 // Avoid to change all the code whan STlink is disconnected from nucleo board.

/*********************************************** Function Prototypes ***********************************************/
void sketchSetup();
void readUltrasonic();
float calculateMedian(int *array, int arraySize);
int compareReadings(const void *a, const void *b);
void logState(uint16_t code);

#ifdef enableRTCstm32
void setupRTC();
void setTime();
void readTime();
#endif // enableRTCstm32

#ifdef enableUltrasonic
void ultrasonic_setup();
void readUltrasonic();
float calculateMedian(int *array, int arraySize);
int compareReadings(const void *a, const void *b);
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
void updateSensorDataRain(const raingauge_readings_t *readings);
void updateSensorDataBME(float temp, float press);
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
    Serial.println("Sistema reinicializado pelo WatchDog ... === Irá entrar em hibernação ... === BR2 = " + String(getBackupRegister(2)));
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

#ifdef enableBME280
  Serial.println("Initializing BME280 sensor...");

  if (bme280_init())
  {
    Serial.println("BME280 ready!");
  }
  else
  {
    Serial.println("Warning: BME280 initialization failed - continuing without sensor");
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

  Serial.println("LowPower.begin()");
  LowPower.begin();
  goToSleep();

  // Serial.println("ultrasonic_setup()");
  // ultrasonic_setup();

  Serial.println("start_LoRa()"); //ok
  start_LoRa();
}

/*********************************************** loop () ***********************************************/
void loop()
{
  logState(20); // entrou no loop

#ifdef enableBME280
  // readBME280(); // Read BME280 sensor data
  float bmeTemp, bmePress;
  if (bme280_read(&bmeTemp, &bmePress))
  {
    bme280_printReadings(); //OK
    updateSensorDataBME(bmeTemp, bmePress);
  }
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

  // readUltrasonic();

#ifdef enableADC
  adc_readings_t adcReadings;

  if (adc_read(&adcReadings))
  {
    adc_printReadings(&adcReadings);
    updateSensorDataADC(&adcReadings);
  }
#endif

    fillSensorData();
    sendSensorData(); // New Lora function

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
    // Serial1.println("\nStarting Sensor: " + String(sensor_id) + " on " + String(sensor_location)); // ok it worked
    Serial.println("\nIlha 3d");
    Serial.println("\nwww.ilha3d.com");
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

#ifdef enableDebug
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
  // rtc.setClockSource(STM32RTC::LSI_CLOCK); //3V3 ligado com diodo no VBAT
  rtc.setClockSource(STM32RTC::LSE_CLOCK); // 3V3 wired with a diode on VBAT
  rtc.begin();                             // initialize RTC 24H format
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
// Ultrasonic Distance Sensor setup
void ultrasonic_setup()
{
  pinMode(triggerPin, OUTPUT);
  pinMode(echoPin, INPUT);
#ifdef enableSerialLog
  Serial.println("Setting up Ultrasonic Sensor.");
#endif
} // end ultrasonic_setup

// Function adapted to calculate the median of 11 readings from the ultrasonic sensor and display it as the read distance
void readUltrasonic()
{
  int readings[11]; // 11 readings (To calculate the median it is better to use an odd number)
  int ultrasonic_readings_array_size = sizeof(readings) / sizeof(readings[0]);

#ifdef enableSerialLog
  Serial.println("ultrasonic_readings_array_size = " + String(ultrasonic_readings_array_size));
#endif

  // Take 11 consecutive readings to calculate the median and eliminate undue readings and outliers due to ultrasound reflection:
  for (int i = 0; i < ultrasonic_readings_array_size; i++)
  {               // for1
  check_distance: // Label for goto
    digitalWrite(triggerPin, LOW);
    delayMicroseconds(5);
    digitalWrite(triggerPin, HIGH);
    delayMicroseconds(10);
    pulseLength = pulseIn(echoPin, HIGH);
    readingDistance = pulseLength / 58; // Measured distance in centimeters
    delay(50);

    if (readingDistance > 500 || readingDistance < 0)
    { // eliminate erroneous readings above or below the sensor range
      goto check_distance;
    }
    readings[i] = readingDistance;

#ifdef enableSerialLog
    Serial.println("readings-" + String(i) + " = " + String(readings[i]));
#endif
  } // for1

  float median = calculateMedian(readings, ultrasonic_readings_array_size); // Calculate the Median

  // TODO: Verifica se a median mudou significativamente
  // if (abs(median - lastEchoDistance) >= 1) { // check for change in distance só manda msg se mudar o valor > 1cm
  // lastEchoDistance = median;

#ifdef enableSerialLog
  Serial.println("Distância lida pelo sensor ultrassônico (mediana): " + String(median) + "cm");
  distance_reading_done = true;
  // Serial.println("distance_reading_done: " + String(distance_reading_done));
#endif
  // }

  delay(50); // para economizar bateria, pode-se reduzir esse tempo
}

// TODO: improve commenting
float calculateMedian(int *array, int arraySize)
{
  qsort(array, arraySize, sizeof(int), compareReadings);

// Print the sorted values
#ifdef enableSerialLog
  Serial.println("Leituras das distâncias ordenadas:");
  for (int i = 0; i < arraySize; i++)
  {
    Serial.println(array[i]);
  }
  Serial.println("\n");
#endif

  if (arraySize % 2 == 0)
  {
    return (float)(array[arraySize / 2 - 1] + array[arraySize / 2]) / 2;
  }
  else
  {
    return (float)array[arraySize / 2];
  }
}

int compareReadings(const void *a, const void *b)
{
  return (*(int *)a - *(int *)b);
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

void updateSensorDataRain(const raingauge_readings_t *readings) {
    sensorData.precipitation_pulses = (int16_t)readings->pulseCount;
}

void updateSensorDataBME(float temp, float press) {
    sensorData.temperature = temp;
    sensorData.pressure = press;
    sensorData.humidity = -99;  
}

// Fills data struct to send via LoRa
void fillSensorData()
{
  readingDistance = -99; // There is no USsensor installed

  enableBackupDomain();
  uint16_t bootCounter = getBackupRegister(4);
  disableBackupDomain();

  sensorData.reading_number = bootCounter; 
  sensorData.timestamp = 0; // TODO: implement need to get the clock from the gateway
  sensorData.level = readingDistance;
  sensorData.surface_temperature = -99.0;
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
  Serial.print("Surface temperature: "); Serial.println(d.surface_temperature, 2);
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
