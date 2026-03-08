/**
 * @file main.cpp
 * @brief SAPI Gateway-01 - Production firmware for LoRa Gateway
 *
 * Receives LoRa packets from Stations 01, 02, and 03, applies calibration,
 * and forwards data to the cloud server via WiFi (with cellular fallback).
 *
 * Supported stations:
 *  - Station-01 (STM32 BluePill, HC-SR04): legacy text protocol
 *  - Station-02 (STM32 Nucleo F103RB): SensorData struct, rain gauge
 *  - Station-03 (STM32 Nucleo L476RG, US-100): SensorData struct, temp-compensated level
 *
 * Hardware: LilyGO T-SIM7000G (ESP32 + SIM7000G + LoRa32)
 *
 * @author Alexandre Nuernberg - alexandreberg@gmail.com
 * @date 2026-03-01
 *
 * Changelog:
 *  2025-09-15 - Initial gateway development
 *  2025-12-25 - Migrated to SensorData struct and MessagePack/JSON serialization
 *  2026-03-01 - gateway-01: Added Station-03 support (levelZero = 236 cm)
 *  2026-03-08 - Issue #40: WiFi-primary + NB-IoT fallback state machine.
 *               GPRS connects on demand only when WiFi is unavailable.
 *               Auto-reverts to WiFi when it recovers. Periodic re-registration
 *               retry if modem failed to register at boot (every 5 min).
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

#include <Arduino.h>
#include <SD.h>
#include <stdio.h>
#include <string>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>

#include "sendData.h"
#include "stationConfig.h"

DataTransmitter* dataTransmitter = nullptr;

// Enable the Modules
#define enableSerialLog
#define enableCelular
#define enableLoRa
#define enableWiFi
#define atualizaGrafico
#define enableNTP
// #define enablePowerProfilerKit // Enable power consumption monitoring with Nordic Power Profiler Kit II connected in the GPIO ports

String versao = "LilyGO_T_SIM7000G_SAPI_LoRa_gateway-01_stations123_2026030801_cel_backup"; // variable to store the version number

// ================== Variáveis globais ==================
SPIClass SPI_LORA(HSPI);
volatile bool newLoRaPacketWithStruct = false;
volatile bool newDataReadyToSend = false;
SensorData receivedData;

// ─── Cellular / NB-IoT (SIM7000G via TinyGSM + SSLClient) ───────────────────
// TINY_GSM_MODEM_SIM7000 and TINY_GSM_RX_BUFFER are defined in platformio.ini
// build_flags so they are visible in every translation unit before any include.
#ifdef enableCelular
    #include <TinyGsmClient.h>

    // LilyGO T-SIM7000G UART pins (same as gateway_M2M_test-01/02)
    #define MODEM_UART_BAUD 115200
    #define MODEM_PIN_TX    27      ///< ESP32 TX → Modem RX
    #define MODEM_PIN_RX    26      ///< ESP32 RX ← Modem TX
    #define MODEM_PWR_PIN   4       ///< Pulse HIGH→LOW to toggle modem power

    // TIM Datatem NB-IoT credentials (SIM A — production SIM, confirmed working)
    static const char cel_apn[]      = "iot.datatem.com.br";
    static const char cel_gprsUser[] = "datatem";
    static const char cel_gprsPass[] = "datatem";

    TinyGsm       modem(Serial1);
    TinyGsmClient gsmClient(modem, 0);

    bool initModem();
    bool waitForRegistration();
    bool connectGPRS();
    void disconnectGPRS();
    bool checkCellularRegistration();
    void setupCellular();
#endif // enableCelular

#ifdef enableWiFi
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "credentials.h" // Credentials file - need to be created according to README file
const char *connection = "WiFi"; // Default connection type
#endif // enableWiFi

#ifdef enableNTP
// RTC demo for ESP32, that includes TZ and DST adjustments
// Get the POSIX style TZ format string from  https://github.com/nayarsystems/posix_tz_db/blob/master/zones.csv
// Created by Hardy Maxa
// Complete project details at: https://RandomNerdTutorials.com/esp32-ntp-timezones-daylight-saving/
#include "time.h"
volatile bool ntpInitialized = false; // Flag para garantir que o NTP só inicializa uma vez
volatile bool ntpDailyUpdateDoneForToday = false; // Try update from ntp daily
volatile bool sendLoraTimestamp_flag = false; // Flag to allow sending timestamp via lora to the remote sensors
#endif //enableNTP

boolean Station_01_flag = false;
boolean Station_02_flag = false;
boolean Station_Gateway_flag = false;
boolean atualizaGrafico_flag = false;
long Station_01_water_level_value = 0;
long Station_02_water_level_value = 0;
long Station_Gateway_water_level_value = 0;
String connection_type = "WiFi"; // Definie main connection type 'Celular' or "WiFi'
// String connection_type = "Celular"; // Definie main connection type 'Celular' or "WiFi'
// Connectivity tracking flags
volatile bool wifiReady = false;
volatile bool cellularReady = false;          ///< Modem registered on NB-IoT network
volatile bool gprsReady = false;              ///< GPRS data session currently active
volatile bool disconnectGprsRequested = false; ///< Deferred GPRS disconnect (scheduled from WiFi event callback)
// Rate limiting
unsigned long lastConnectionCheckLog = 0;
const unsigned long CONNECTION_CHECK_INTERVAL = 5000;
unsigned long currentMillis = 0;
int csq = 0;
// Cellular periodic registration retry (if modem failed to register at boot)
unsigned long lastCellularCheckMs = 0;
const unsigned long CELLULAR_RETRY_INTERVAL_MS = 5UL * 60UL * 1000UL; ///< 5 minutes between retries

#ifdef enableLoRa
  // Libraries for LoRa
  #include <SPI.h>
  #include <LoRa.h>

  // define the pins used by the LoRa transceiver module
  #define PIN_TX 27
  #define PIN_RX 26
  #define UART_BAUD 112500
  #define PWR_PIN 4

  #define SD_MISO 2
  #define SD_MOSI 15
  #define SD_SCLK 14
  #define SD_CS 13

  #define LORA_RST 12
  #define LORA_DI0 32
  #define RADIO_DIO_1 33
  #define RADIO_DIO_2 34
  #define LORA_SS 5
  #define LORA_MISO 19
  #define LORA_MOSI 23
  #define LORA_SCK 18

  // Set your LoRa Band
  // 433E6 for Asia
  // 866E6 for Europe
  // 915E6 for North America
  // Brazil	AU915-928
  #define BAND 915E6 // Brasil : 902-928 MHz

  SPIClass SPIRadio(HSPI);

  // Initialize variables to get and save LoRa data

  int loraPacketSize = 0;
  int rssi; // Returns the averaged RSSI of the last received packet (dBm).
  float snr; //Returns the estimated SNR (Signal Noise Ratio) of the received packet in dB.
  /*TODO:  Se SNR estiver alto (>8 dB) e ainda houver corrupção com CRC ativo, quase sempre é interferência/pacotes alheios (sync word resolve) ou saturação (reduzir TX / setGain(0)).*/
  String SensorID;
  String distance;

  // Use a character array instead of String to avoid volatile issues
  #define LORA_BUFFER_SIZE 256
  volatile char rawLoRaMessage[LORA_BUFFER_SIZE];
  volatile int packetSize = 0;
  volatile bool newLoRaPacketStation01 = false;
  volatile int receivedRssi = 0;
  volatile float receivedSnr = 0.0;
  volatile long receivedPacketCounter = 0;
  
#endif // enableLoRa

#ifdef enablePowerProfilerKit // monitor power consumption of the board
const int PPK_D7 = 21; // monitor full program execution
const int PPK_D6 = 22;
const int PPK_D5 = 39;
const int PPK_D4 = 19;
const int PPK_D3 = 36;
#endif // enablePowerProfilerKit
/************************************** Function Prototypes ********************************************/
#ifdef enableWiFi
// WiFi Functions
void WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info);
void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info);
void WiFiStationDisconnected(WiFiEvent_t event, WiFiEventInfo_t info);
bool isConnectivityAvailable();
#endif // enableWiFi

#ifdef enableNTP
void initializeNTP();
// void setTimezone(String timezone);
void initTime(String timezone);
time_t getTimestamp();
void processTime();
void printLocalTime();
void setTime(int yr, int month, int mday, int hr, int minute, int sec, int isDst);
void syncNTP();
void updateTime();
#endif //enableNTP

// LoRa Functions
#ifdef enableLoRa
void LoRa_txMode();
void LoRa_sendMessage(String message);
void enviaRTC();
void LoRa_rxMode();
void onReceive(int packetSize);
void processLoRaPacketStation01(); // New function to process the packet in the main loop
void onTxDone();
boolean runEvery(unsigned long interval);
void startLoRA();
void sendLoraTimestamp();
#endif // enableLoRa

#ifdef atualizaGrafico
void graphicUpdate_Celular();
void graphicUpdate_WiFi();
void checkLinkStatusAndSend();
#endif // atualizaGrafico

void restartESP32();
void checkMemory();

void processLoRaPacketWithStruct();
void printSensorData(const SensorData &d);

/******************************************** Setup ****************************************************/
void setup()
{
  Serial.begin(115200);
  delay(50);

  // ============ FORÇA UTC NO SISTEMA ============
  setenv("TZ", "UTC0", 1);
  tzset();
  // ==============================================

  printStationConfigs();

#ifdef enablePowerProfilerKit
  pinMode(PPK_D7, OUTPUT);
  digitalWrite(PPK_D7, 0); // starts monitoring power consuption for all the code execution
  Serial.println("--------------------------------------------------------");
  Serial.println("\nIniciando a medição do consumo de energia\n");
  Serial.println("GPIO21 deve estar conectada no pino D7 do Power Profiler");
  Serial.println("GPIO21  = 0 ");
  Serial.println("--------------------------------------------------------");
#endif

  Serial.println("");
  Serial.println("Version: " + String(versao));
  Serial.println("");

#ifdef enableLoRa
  startLoRA();
#endif // enableLoRa

#ifdef enableWiFi
  // Wifi setup:
  WiFi.disconnect(true); // delete old config
  delay(1000);
  Serial.println("\nWaiting for WiFi connection...\n ");
  WiFi.onEvent(WiFiStationConnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_CONNECTED);
  WiFi.onEvent(WiFiGotIP, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_GOT_IP);
  WiFi.onEvent(WiFiStationDisconnected, WiFiEvent_t::ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.begin(ssid, wifi_password); // Start WiFi Communication

#endif // enableWiFi

  dataTransmitter = new DataTransmitter(serverName, apiKey);
  dataTransmitter->setDebugMode(true);

#ifdef enableCelular
  setupCellular();
  // Pass gsmClient (TinyGsmClient inherits from Client) to DataTransmitter.
  // server / resource / port come from credentials.h (same as WiFi path).
  dataTransmitter->initCellular(gsmClient, server, resource, port);
#endif // enableCelular
}

/******************************************** Loop *********************************************************/
void loop()
{
  updateTime();

#ifdef enableCelular
  // Deferred GPRS disconnect — requested by WiFiGotIP event callback.
  // Executed here (main loop context) to avoid calling TinyGSM AT commands
  // from inside a WiFi event callback.
  if (disconnectGprsRequested) {
    disconnectGprsRequested = false;
    disconnectGPRS();
  }

  // Periodic NB-IoT registration retry.
  // If the modem failed to register at boot (e.g. no tower coverage), retry
  // every CELLULAR_RETRY_INTERVAL_MS so cellular becomes available as backup
  // once coverage returns — without blocking the main loop.
  if (!cellularReady) {
    unsigned long nowMs = millis();
    if (nowMs - lastCellularCheckMs >= CELLULAR_RETRY_INTERVAL_MS) {
      lastCellularCheckMs = nowMs;
      Serial.println("[CEL] Periodic check: retrying NB-IoT registration...");
      if (checkCellularRegistration()) {
        Serial.println("[CEL] NB-IoT registered! Cellular now available as backup.");
        csq = modem.getSignalQuality();
        cellularReady = true;
      } else {
        Serial.println("[CEL] NB-IoT still not registered. Will retry in 5 min.");
      }
    }
  }
#endif // enableCelular

#ifdef enableLoRa
  // Check if new LoRa data is available to be processed from old station-01
  if (newLoRaPacketStation01)
  {
    processLoRaPacketStation01(); // All the heavy processing is done here, outside the ISR
  }

  // Check if new LoRa data is available to be processed from all new stations with data struct
  if (newLoRaPacketWithStruct)
  {
    newLoRaPacketWithStruct = false;
    processLoRaPacketWithStruct();
  }
#endif // enableLoRa

  // Verifica a flag para enviar o timestamp
  if (sendLoraTimestamp_flag)
  {
    sendLoraTimestamp();
    sendLoraTimestamp_flag = false;
  }

  // Se houver novos dados de sensores, decide qual link usar
  // if (Station_01_flag || Station_02_flag || Station_Gateway_flag)
  // {
  //   checkLinkStatusAndSend();
  // }

  if (newDataReadyToSend) {
    checkLinkStatusAndSend();
}

  // Se precisar rodar temporizado:
  // if (runEvery(5000)) {
  // comando }
}

/******************************************** Functions ****************************************************/
// WiFi Functions:
#ifdef enableWiFi
void WiFiStationConnected(WiFiEvent_t event, WiFiEventInfo_t info)
{
  Serial.println("Conexão com o AP bem sucedida!");
}

// void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info)
// {
//   Serial.println("WiFi conectado");
//   Serial.print("Endereço IP: ");
//   Serial.println(WiFi.localIP());
//   // Chama a função genérica de inicialização do NTP
//   initializeNTP();
// }

void WiFiGotIP(WiFiEvent_t event, WiFiEventInfo_t info) {
    Serial.println("WiFi conectado");
    Serial.print("Endereço IP: ");
    Serial.println(WiFi.localIP());

    // SET FLAG: WiFi is now ready for use (primary link)
    wifiReady = true;
    Serial.println("[WiFi] Ready for data transmission (primary link)");

#ifdef enableCelular
    // If GPRS was active as fallback, schedule disconnect to conserve data budget.
    // Cannot call TinyGSM AT commands directly from an event callback — defer to loop().
    if (gprsReady) {
        disconnectGprsRequested = true;
        Serial.println("[CEL] WiFi restored — GPRS disconnect scheduled");
    }
#endif // enableCelular

    // Initialize NTP
    initializeNTP();
}
// void WiFiStationDisconnected(WiFiEvent_t event, WiFiEventInfo_t info)
// {
//   Serial.println("Disconnected from WiFi access point");
//   Serial.print("WiFi lost connection. Reason: ");
//   Serial.println(info.wifi_sta_disconnected.reason);
//   Serial.println("Trying to Reconnect");
//   WiFi.begin(ssid, wifi_password);
// }

void WiFiStationDisconnected(WiFiEvent_t event, WiFiEventInfo_t info) {
    Serial.println("Disconnected from WiFi access point");
    Serial.print("WiFi lost connection. Reason: ");
    Serial.println(info.wifi_sta_disconnected.reason);
    
    // ✅ CLEAR FLAG: WiFi is no longer available
    wifiReady = false;
    Serial.println("✗ WiFi not ready - cannot transmit");
    
    Serial.println("Trying to Reconnect");
    WiFi.begin(ssid, wifi_password);
}

/**
 * @brief Check if any connectivity is available
 * @return true if WiFi or Cellular is ready
 */
bool isConnectivityAvailable() {
    // Check WiFi
    if (WiFi.status() == WL_CONNECTED && wifiReady) {
        return true;
    }
    
    // Check Cellular (for future implementation)
    if (cellularReady) {
        return true;
    }
    
    return false;
}
#endif // enableWiFi

#ifdef enableNTP
// Função para realizar a sincronização NTP
void syncNTP() {
  Serial.println("Sincronizando NTP...");
  
  // FORÇA UTC no sistema
  setenv("TZ", "UTC0", 1);
  tzset();
  
  configTime(0, 0, "pool.ntp.org");

  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("Falha ao obter o tempo do NTP na sincronização.");
    return;
  }
  Serial.println("Tempo obtido do NTP em UTC.");

  printLocalTime(); // Agora vai mostrar UTC
  time_t timestampUtcAtual = mktime(&timeinfo);
  Serial.print("Timestamp UTC após sincronização: ");
  Serial.println(timestampUtcAtual);
  Serial.println("Aguardando mensagens das Estações...");
  Serial.println("----------------------------------------------------------------------------");
}


void initializeNTP() {
  if (!ntpInitialized) {
    Serial.println("Rede conectada. Inicializando NTP pela primeira vez...");
    
    // GARANTE que o sistema está em UTC ANTES de inicializar
    setenv("TZ", "UTC0", 1);
    tzset();
    
    syncNTP();
    ntpInitialized = true;
  }
}



void initTime(String timezone){
  struct tm timeinfo;
  Serial.println("Configurando de pool.ntp.org");
  
  // MANTÉM UTC - NÃO aplica timezone
  setenv("TZ", "UTC0", 1);
  tzset();
  
  configTime(0, 0, "pool.ntp.org");
  
  if(!getLocalTime(&timeinfo)){
    Serial.println("  Failed to obtain time");
    return;
  }
  Serial.println("  Adquiriu data e hora do NTP em UTC");
}

time_t getTimestamp(){
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
    return 0;
  }
  return mktime(&timeinfo); // Já está em UTC se o sistema está em UTC
}

void printLocalTime(){
  struct tm timeinfo;
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
    return;
  }
  // Mostra como UTC
  Serial.print("Data e Hora UTC: ");
  Serial.println(&timeinfo, "%A, %B %d %Y %H:%M:%S");
}

void processTime() {
    time_t now;
    
    // Obtém o timestamp atual (já está em UTC porque o sistema está em UTC)
    time(&now);

    // Verificação básica
    if (now < 1000000) { 
        Serial.println("ERRO: O relógio ainda não sincronizou via NTP/RTC.");
        receivedData.timestamp = -99;
        return;
    }

    // Armazena direto - JÁ É UTC!
    receivedData.timestamp = (uint32_t)now;

    // Logs para debug
    struct tm timeinfo;
    gmtime_r(&now, &timeinfo); // gmtime_r sempre retorna UTC
    
    Serial.printf("DEBUG: Timestamp UTC armazenado: %lu\n", receivedData.timestamp);
    Serial.printf("DEBUG: Hora UTC: %02d:%02d:%02d\n", 
                  timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
}

void setTime(int yr, int month, int mday, int hr, int minute, int sec, int isDst){
  struct tm tm;

  tm.tm_year = yr - 1900;
  tm.tm_mon = month-1;
  tm.tm_mday = mday;
  tm.tm_hour = hr;
  tm.tm_min = minute;
  tm.tm_sec = sec;
  tm.tm_isdst = isDst;
  time_t t = mktime(&tm);
  Serial.printf("Setting time: %s", asctime(&tm));
  struct timeval now = { .tv_sec = t };
  settimeofday(&now, NULL);
}

// Tentando corrigir o problema de loop infinito em que o NTP fica atualziando constantemente por uma hora.
void updateTime() {
  bool networkIsUp = (WiFi.status() == WL_CONNECTED);

  if (networkIsUp) {
    struct tm timeinfo;
    if (getLocalTime(&timeinfo)) {

      // Se estamos na primeira hora do dia UTC e ainda não foi feito o update
      if (timeinfo.tm_hour == 0 && !ntpDailyUpdateDoneForToday) {
        Serial.println("----------------------------------------------------------------------------");
        Serial.println("Primeira hora do dia UTC (00:xx)! Atualizando NTP...");
        syncNTP();
        ntpDailyUpdateDoneForToday = true;
      }

      // Quando passar da primeira hora, libera para o próximo dia
      else if (timeinfo.tm_hour != 0) {
        ntpDailyUpdateDoneForToday = false;
      }

    } else {
      Serial.println("Não foi possível obter a hora. Tentando sincronizar NTP...");
      if (!ntpInitialized) {
        syncNTP();
        ntpInitialized = true;
      }
    }
  }
}

#endif //enableNTP

// LoRa Functions:
#ifdef enableLoRa
void LoRa_txMode()
{
  LoRa.idle();           // set standby mode
  LoRa.enableInvertIQ(); // active invert I and Q signals
}

void LoRa_sendMessage(String message)
{
  LoRa_txMode();        // set tx mode
  LoRa.beginPacket();   // start packet
  LoRa.print(message);  // add payload
  LoRa.endPacket(true); // finish packet and send it
}

void LoRa_rxMode()
{
  LoRa.disableInvertIQ(); // normal mode
  LoRa.receive();         // set receive mode
}

void onReceive(int packetSize_local)
{
  // If there is a packet, read it and store it
  if (packetSize_local > 0)
  {
    packetSize = packetSize_local;
    // Serial.println("DEBUG: LoRa packet received with size of: " + String (packetSize));

    receivedRssi = LoRa.packetRssi();
    receivedSnr = LoRa.packetSnr();

    // 1- Check if the packet is from the new data struct for new stations:
    if (packetSize == sizeof(SensorData))
    {
      LoRa.readBytes((uint8_t *)&receivedData, sizeof(SensorData));
      newLoRaPacketWithStruct = true;
    }
    
    // 2- Checks if the data is from the old station-01:
    else if (packetSize != sizeof(SensorData))
    {
      // Read the packet into the buffer
      int i = 0;
      while (LoRa.available() && i < LORA_BUFFER_SIZE - 1)
      {
        rawLoRaMessage[i] = (char)LoRa.read();
        i++;
      }
      rawLoRaMessage[i] = '\0'; // Null-terminate the string

      // receivedRssi = LoRa.packetRssi();
      // receivedSnr = LoRa.packetSnr();
      receivedPacketCounter++;
      newLoRaPacketStation01 = true; // Set the flag for processing in the main loop
    }
    
    // 3- Or it is trash and should be discarded.
    // else
    // {
    //   // Caso tamanho não bata, descarta
    //   Serial.printf("Pacote inválido (%d bytes esperados %d)\n", packetSize, sizeof(SensorData));
    //   while (LoRa.available())
    //     LoRa.read(); // limpa buffer
    // }
  }
}
// =====================================================================================

// ====================== NEW FUNCTION TO PROCESS THE PACKET ===========================
// Process LoRa packets comming only from old station-01
// This function is called in the main loop and handles all the heavy processing.
void processLoRaPacketStation01() {
    
    // Create a local copy of the raw data and reset the flag
    String LoRaData = "";
    int sz = 0;
    int rssi_local = 0;
    float snr_local = 0.0;
    long counter_local = 0;
    
    // Access volatile variables in a critical section to avoid race conditions
    // This is optional but good practice, as it ensures data integrity
    // Note: Mutexes are better for tasks, but for ISRs, critical sections are often used
    // and are more lightweight. For this example, let's stick with the core logic.
    
    // Safely copy the volatile data to local, non-volatile variables
    if (newLoRaPacketStation01) {
        LoRaData = String((char*)rawLoRaMessage);
        sz = packetSize;
        rssi_local = receivedRssi;
        snr_local = receivedSnr;
        counter_local = receivedPacketCounter;
        
        // Reset the flag for the next packet
        newLoRaPacketStation01 = false;
    } else {
        // Should not happen if the function is only called when the flag is true
        return;
    }

    if (LoRaData.length() == 0) {
        Serial.println("Empty LoRa message, discarding.");
        return;
    }

    // 1. Validação da Estrutura da Mensagem
    int pos1 = LoRaData.indexOf('/');
    int pos2 = LoRaData.indexOf('&');
    if (pos1 == -1 || pos2 == -1 || pos1 >= pos2) {
        Serial.println("----------------------------------------------------------------------------");
        Serial.println(String(counter_local) + "- Corrupted LoRa message (invalid struct), discarding.");
        Serial.print("Received Message: ");
        Serial.println(LoRaData);
        return; 
    }

    // 2. Extração e Validação dos Dados
    String SensorID = LoRaData.substring(0, pos1);
    
    long distanciaLida01 = LoRaData.substring(pos1 + 1, pos2).toInt();
    long distanciaLida02 = LoRaData.substring(pos2 + 1, LoRaData.length()).toInt();

    // Check if the values are valid after conversion.
    if (distanciaLida01 == 0 && distanciaLida02 == 0) {
        Serial.println("----------------------------------------------------------------------------");
        Serial.println(String(counter_local) + "- Corrupted LoRa message (invalid struct), discarding.");
        Serial.print("Received Message: ");
        Serial.println(LoRaData);
        return;
    }

    // 3. Sua lógica de processamento
    if (distanciaLida01 == distanciaLida02) {
        if (SensorID == "Station_01") {
            Station_01_water_level_value = distanciaLida01;
            Station_01_flag = true;
            sendLoraTimestamp_flag = true; // A flag to allow sending the timestamp back to the sensor
            
            // Adding station-01 data to the new struct
            receivedData.idStation = 1;
            receivedData.reading_number = counter_local;

            processTime(); // Getting current TS in UTC

            // receivedData.level = distanciaLida01;
            receivedData.level = calculateCalibratedLevel(receivedData.idStation, distanciaLida01);
            receivedData.temperature = -99;
            receivedData.pressure = -99;
            receivedData.humidity = -99;
            receivedData.precipitation_pulses = -99;
            receivedData.surface_temperature = -99;
            receivedData.Vbat = -99;
            receivedData.Vpanel = -99;
            receivedData.rssi = receivedRssi;
            receivedData.snr = receivedSnr;
            receivedData.sigWiFi = 0;
            receivedData.sigCel = 0;
            
            printSensorData(receivedData);
            newDataReadyToSend = true; 

        // } else if (SensorID == "Station_02") {
        //     Station_02_water_level_value = distanciaLida01;
        //     Station_02_flag = true;
        //     sendLoraTimestamp_flag = true; // A flag to allow sending the timestamp back to the sensor
        }
    } else {
        Serial.println("Data mismatch between readings, discarding.");
        Serial.print("Mensagem recebida: ");
        Serial.println(LoRaData);
        return;
    }

    // Log the successful reception
    Serial.println("----------------------------------------------------------------------------");
    Serial.println(String(counter_local) + "- Mensagem Recebida de Sensor: " + SensorID + " | Altura Lida: " + String(distanciaLida01) + "cm | Size: " + String(sz) + " RSSI: " + String(rssi_local) +  " | SNR: " + String(snr_local) );
    printLocalTime();
    checkMemory(); //Checks free memory
}
// =====================================================================================

void onTxDone()
{
#ifdef enableSerialLog
  Serial.println("TxDone");
#endif // enableSerialLog
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

//===============================================  void startLoRA ===============================================
// Initialize LoRa module
void startLoRA()
{

  // Specify pin to initialize SPI
  SPI.begin(SD_SCLK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS))
  {
    Serial.println("Montagem do SDCard Falhou");
  }
  else
  {
    uint32_t cardSize = SD.cardSize() / (1024 * 1024);
    String str = "SDCard Size: " + String(cardSize) + "MB";
    Serial.println(str);
  }

  // Specify pin to initialize SPI1
  SPIRadio.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setSPI(SPIRadio);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DI0);
#ifdef enableSerialLog
  Serial.print("Iniciando o LoRa na banda de: ");
  Serial.print(BAND);
  Serial.println(" Hz");
#endif // enableSerialLog

  if (!LoRa.begin(BAND))
  {
    Serial.println("Inicialização do LoRa falhou!");
    // Aqui deve fazer uma logica que mande valores fixos para o servidor, dai se sabe que o LoRa caiu.
    SensorID = "Station_Gateway";
    Station_Gateway_water_level_value = 9999; // Error code that the LoRa module was not detected
    Station_Gateway_flag = 1;
    atualizaGrafico_flag = 1;
    Serial.println("");
    Serial.println("Erro LoRa não detectado!");
    Serial.println("");
    while (1)
      ;
  }
  Serial.println("LoRa Iniciado!");
#ifdef enableSerialLog
  Serial.println("LoRa Simple Gateway");
  Serial.println("Tx: invertIQ enable");
  Serial.println("Rx: invertIQ disable");
  Serial.println();
#endif // enableSerialLog

/* Endurecer a recepção: CRC + Sync Word + parâmetros idênticos
Com CRC desativado e sync word default, qualquer ruído “LoRa-like” pode passar. Ative CRC e defina Sync Word e parametrização idêntica nos dois lados (sensor e gateway). 
Acrescente no setup do LoRa em ambos:
*/
LoRa.setSpreadingFactor(7);          /* igual nos dois
                                      Spreading Factor: Change the spreading factor of the radio.
                                      LoRa.setSpreadingFactor(spreadingFactor);
                                      spreadingFactor - spreading factor, defaults to 7
                                      Supported values are between 6 and 12. If a spreading factor of 6 is set, implicit header mode must be used to transmit and receive packets.*/
LoRa.setSignalBandwidth(125E3);      /* igual nos dois
                                      Signal Bandwidth:  Change the signal bandwidth of the radio.
                                      LoRa.setSignalBandwidth(signalBandwidth);
                                      signalBandwidth - signal bandwidth in Hz, defaults to 125E3.
                                      Supported values are 7.8E3, 10.4E3, 15.6E3, 20.8E3, 31.25E3, 41.7E3, 62.5E3, 125E3, 250E3, and 500E3.*/
LoRa.setCodingRate4(5);              /* CR 4/5 (igual nos dois)
                                      Coding Rate: Change the coding rate of the radio.
                                      LoRa.setCodingRate4(codingRateDenominator);
                                      codingRateDenominator - denominator of the coding rate, defaults to 5
                                      Supported values are between 5 and 8, these correspond to coding rates of 4/5 and 4/8. The coding rate numerator is fixed at 4.*/
LoRa.setPreambleLength(8);           /* igual nos dois
                                    Preamble Length: Change the preamble length of the radio.
                                    LoRa.setPreambleLength(preambleLength);
                                    preambleLength - preamble length in symbols, defaults to 8
                                    Supported values are between 6 and 65535.*/
LoRa.setSyncWord(0x12);              /* igual nos dois (privado) — escolha um e padronize
                                    Sync Word: Change the sync word of the radio.
                                    LoRa.setSyncWord(syncWord);
                                    syncWord - byte value to use as the sync word, defaults to 0x12 */
LoRa.enableCrc();                   /* ATIVAR CRC (nos dois)
                                    Enable or disable CRC usage, by default a CRC is not used.
                                    LoRa.enableCrc();
                                    LoRa.disableCrc();*/

LoRa.setGain(0);                    /* ganho automático (SOMENTE NO GATEWAY!)
                                      LNA Gain: Set LNA Gain for better RX sensitivity, by default AGC (Automatic Gain Control) is used and LNA gain is not used.
                                      LoRa.setGain(gain);
                                      gain - LNA gain. Supported values are between 0 and 6. If gain is 0, AGC will be enabled and LNA gain will not be used.
                                      Else if gain is from 1 to 6, AGC will be disabled and LNA gain will be used.*/




  // register the receive callback
  LoRa.onReceive(onReceive);
  LoRa.onTxDone(onTxDone);
  LoRa_rxMode();

  Serial.println("LoRa inicializado e aguardando pacotes...");
  Serial.printf("Esperando struct com %d bytes...\n\n", sizeof(SensorData));
}

void sendLoraTimestamp() {

  struct tm timeinfo;

  if (!getLocalTime(&timeinfo)) {
    Serial.println("Falha ao obter o tempo do NTP para o timestamp.");
    return; // Não envia se não conseguir o tempo
  }

  time_t timestamp = mktime(&timeinfo);

  String message = "TS:" + String(timestamp);

  Serial.print("Enviando mensagem LoRa: ");
  Serial.println(message);

  LoRa_txMode(); // Entra no modo de transmissão
  LoRa_sendMessage(message); // Envia a mensagem
  LoRa_rxMode(); // Retorna ao modo de receção após o envio
}
#endif // enableLoRa

//////////////////////////////////////////////////// restartESP32() ////////////////////////////////////////////////////
// TODO (not tested)
void restartESP32()
{
  Serial.println("Restarting ESP32...");
  delay(1000); // Give some time for serial output to be sent
  // Perform the restart using the ESP.restart() function
  ESP.restart();
}

//////////////////////////////////////////////////// Cellular Setup (NB-IoT / SIM7000G) ////////////////////////////////////////////////////
#ifdef enableCelular

/**
 * @brief Power on the SIM7000G and configure NB-IoT radio.
 *
 * Configures LTE-only mode (AT+CNMP=38), NB-IoT preferred (AT+CMNB=2),
 * and Band 28 + Band 3. Identical to gateway_M2M_test-02_HTTPS/src/main.cpp.
 *
 * @return true if modem responds to AT after initialization
 */
bool initModem() {
    pinMode(MODEM_PWR_PIN, OUTPUT);
    digitalWrite(MODEM_PWR_PIN, LOW);

    Serial1.begin(MODEM_UART_BAUD, SERIAL_8N1, MODEM_PIN_RX, MODEM_PIN_TX);
    delay(500);

    Serial.println("[MODEM] Checking if modem is already responding...");
    if (modem.testAT(2000)) {
        Serial.println("[MODEM] Modem already on. Calling init()...");
        modem.init();
    } else {
        Serial.println("[MODEM] Modem not responding. Pulsing PWRKEY (1.5 s)...");
        digitalWrite(MODEM_PWR_PIN, HIGH);
        delay(1500);
        digitalWrite(MODEM_PWR_PIN, LOW);
        Serial.println("[MODEM] Waiting 8 s for module to boot...");
        delay(8000);

        if (!modem.testAT(3000)) {
            Serial.println("[MODEM] Still not responding. Pulsing PWRKEY again...");
            digitalWrite(MODEM_PWR_PIN, HIGH);
            delay(1500);
            digitalWrite(MODEM_PWR_PIN, LOW);
            delay(8000);

            if (!modem.init()) {
                Serial.println("[MODEM] ERROR: Modem not responding after two power pulses");
                return false;
            }
        } else {
            modem.init();
        }
    }

    Serial.println("[MODEM] Modem OK — " + modem.getModemName());

    Serial.println("[MODEM] Disabling radio for clean configuration...");
    modem.sendAT("+CFUN=0");
    modem.waitResponse(10000L);
    delay(500);

    Serial.println("[MODEM] Setting LTE-only mode (CNMP=38)...");
    modem.setNetworkMode(38);
    delay(200);

    Serial.println("[MODEM] Setting NB-IoT preferred (CMNB=2)...");
    modem.setPreferredMode(2);
    delay(200);

    Serial.println("[MODEM] Setting NB-IoT bands 28+3...");
    modem.sendAT("+CBANDCFG=\"NB-IOT\",28,3");
    modem.waitResponse(10000L);
    delay(200);

    Serial.println("[MODEM] Re-enabling radio...");
    modem.sendAT("+CFUN=1");
    modem.waitResponse(10000L);
    Serial.println("[MODEM] Waiting 5 s for radio to start scanning...");
    delay(5000);

    return true;
}

/**
 * @brief Poll AT+CEREG?/AT+CREG? until the modem registers on the NB-IoT network.
 *
 * Blocks up to 180 s. Called once at boot by setupCellular().
 * Does NOT open a GPRS data session — that is done on demand by connectGPRS().
 *
 * @return true if registered (stat=1 home or stat=5 roaming)
 */
bool waitForRegistration() {
    const unsigned long timeout      = 180000UL;
    const unsigned long pollInterval = 10000UL;
    unsigned long start = millis();
    bool registered = false;

    Serial.println("[NET] Polling AT+CEREG? for LTE registration (up to 180 s)...");

    while (millis() - start < timeout) {
        modem.sendAT("+CREG?");
        delay(300);
        String cregResp = "";
        if (Serial1.available()) {
            cregResp = Serial1.readString();
            Serial.print("[NET] AT+CREG?  -> "); Serial.print(cregResp);
        }

        modem.sendAT("+CEREG?");
        delay(300);
        String ceregResp = "";
        if (Serial1.available()) {
            ceregResp = Serial1.readString();
            Serial.print("[NET] AT+CEREG? -> "); Serial.print(ceregResp);
        }

        if (cregResp.indexOf(",1")  >= 0 || cregResp.indexOf(",5")  >= 0 ||
            ceregResp.indexOf(",1") >= 0 || ceregResp.indexOf(",5") >= 0) {
            Serial.println("[NET] Registered OK");
            registered = true;
            break;
        }

        Serial.printf("[NET] Not registered yet. Elapsed: %lu s\n", (millis() - start) / 1000);
        delay(pollInterval - 900);
    }

    if (!registered) {
        Serial.println("[NET] ERROR: registration timeout after 180 s");
        return false;
    }

    return true;
}

/**
 * @brief Quick CEREG/CREG poll (~600 ms) — non-blocking alternative to waitForRegistration().
 *
 * Used by the periodic retry in loop() to check whether the modem has registered
 * since a failed boot attempt, without blocking for up to 180 s.
 *
 * @return true if currently registered
 */
bool checkCellularRegistration() {
    modem.sendAT("+CREG?");
    delay(300);
    String cregResp = "";
    if (Serial1.available()) {
        cregResp = Serial1.readString();
        Serial.print("[NET] Quick CREG  -> "); Serial.print(cregResp);
    }

    modem.sendAT("+CEREG?");
    delay(300);
    String ceregResp = "";
    if (Serial1.available()) {
        ceregResp = Serial1.readString();
        Serial.print("[NET] Quick CEREG -> "); Serial.print(ceregResp);
    }

    return (cregResp.indexOf(",1")  >= 0 || cregResp.indexOf(",5")  >= 0 ||
            ceregResp.indexOf(",1") >= 0 || ceregResp.indexOf(",5") >= 0);
}

/**
 * @brief Open a GPRS data session on demand.
 *
 * Called from checkLinkStatusAndSend() only when WiFi is unavailable.
 * Sets gprsReady=true on success.
 *
 * @return true if GPRS connected and local IP assigned
 */
bool connectGPRS() {
    Serial.printf("[NET] Connecting GPRS | APN: %s\n", cel_apn);
    if (!modem.gprsConnect(cel_apn, cel_gprsUser, cel_gprsPass)) {
        Serial.println("[NET] ERROR: gprsConnect() failed");
        return false;
    }

    if (modem.isGprsConnected()) {
        Serial.printf("[NET] GPRS connected | Local IP: %s\n", modem.localIP().toString().c_str());
        gprsReady = true;
        return true;
    }

    Serial.println("[NET] ERROR: GPRS not active after gprsConnect()");
    return false;
}

/**
 * @brief Close the GPRS data session to conserve the monthly data budget.
 *
 * Called when WiFi becomes available again (deferred from WiFiGotIP event via
 * disconnectGprsRequested flag), or directly from checkLinkStatusAndSend()
 * when switching back to WiFi.
 * Sets gprsReady=false.
 */
void disconnectGPRS() {
    Serial.println("[NET] Disconnecting GPRS...");
    modem.gprsDisconnect();
    gprsReady = false;
    Serial.println("[NET] GPRS disconnected — data budget preserved");
}

/**
 * @brief Initialize modem and register on the NB-IoT network.
 *
 * Called from setup(). Intentionally does NOT open a GPRS data session —
 * GPRS is connected on demand only when WiFi is unavailable (connectGPRS()).
 * This preserves the 20 MB/month data budget during normal WiFi operation.
 *
 * On failure, prints a warning and returns without halting — the gateway
 * will run on WiFi only. The loop() periodic check retries registration
 * every CELLULAR_RETRY_INTERVAL_MS until the modem registers.
 */
void setupCellular() {
    Serial.println("[CEL] Initializing SIM7000G modem...");

    if (!initModem()) {
        Serial.println("[CEL] WARNING: Modem init failed — cellular unavailable");
        Serial.println("[CEL] Will retry registration periodically every 5 min.");
        cellularReady = false;
        return;
    }

    if (!waitForRegistration()) {
        Serial.println("[CEL] WARNING: NB-IoT registration failed — cellular unavailable");
        Serial.println("[CEL] Will retry registration periodically every 5 min.");
        cellularReady = false;
        return;
    }

    csq = modem.getSignalQuality();
    Serial.printf("[CEL] Modem registered | CSQ: %d | IMEI: %s\n",
                  csq, modem.getIMEI().c_str());
    Serial.println("[CEL] GPRS NOT connected at boot — will connect on demand if WiFi fails.");

    cellularReady = true;
    // gprsReady stays false — GPRS connects only when WiFi is unavailable
}

#endif // enableCelular

//////////////////////////////////////////////////// graphicUpdate_Celular() ////////////////////////////////////////////////////
#ifdef atualizaGrafico
void graphicUpdate_Celular()
{
  if (atualizaGrafico_flag == 1 && connection_type == "Celular")
  { // if Celular
    Serial.println(" Connexão é Celular");
#if TINY_GSM_USE_GPRS // TODO: precisa ativar a logica do 4G com a lib TinyGSM
    // GPRS connection parameters are usually set after network registration
    Serial.print("Conectando com a rede GSM:  ");
    Serial.println(apn);

    for (int i = 1; i <= 6; i++)
    { // tenta reconectar 6x em intervalos de 60s
      if (!modem.gprsConnect(apn, gprsUser, gprsPass))
      {
        Serial.println("Conexão com a rede GSM falhou!!");
        // delay(60000); // 60s TODO: dando erro no WiFi

        /*
        if (i == 6) {
          Serial.println("i = 6, Vai dormir pois não conseguiu conectar com a rede GSM");
          vaiDormir();
        }
        */
      }
      else
      {
        // #ifdef enableSerialLog
        Serial.println("Conectado com a rede GSM!");
        // #endif
        // Gets signal quality report
        int csq = modem.getSignalQuality();
        DBG("Qualidade do Sinal GSM (CSQ): ", csq);
        Serial.print("Qualidade do Sinal GSM (CSQ):");
        Serial.println(csq);

        // #ifdef enableSerialLog
        Serial.print("Conectando ao servidor: ");
        Serial.println(server);
        // #endif
        for (int i = 1; i <= 6; i++)
        { // tenta reconectar 6x em intervalos de 60s
          if (!client.connect(server, port))
          {
            Serial.println(" Conexão com o servidor web falhou! Tentando novamente...");
            // delay(60000); // 60s TODO: dando erro no WiFi
            /*
            if (i == 6) {
              Serial.println("i = 6, Vai dormir pois não conseguiu conectar com a rede GSM");
              vaiDormir();
            }
            */
            Serial.println("Falhou por 6x. Não conseguiu conectar com a rede GSM!");
          }

          else
          {
            i = 6;
            Serial.println(" Conexão com o servidor OK - Enviando requisição HTTP POST...");
            // #ifdef enableSerialLog
            Serial.println("Enviando requisição HTTP POST...");
            // #endif
            // Habilite apenas para testar sem sendores ==>
            /* String httpRequestData = "api_key=" + apiKey + "&value1=" + Station_01_water_level_value
                                + "&value2=" + Station_02_water_level_value + "&value3=" + Station_Gateway_water_level_value + "&value4=" + csq + "";
                Serial.println("");
                Serial.print("Station_01_water_level_value: "); Serial.println(Station_01_water_level_value);
                Serial.print("Station_02_water_level_value: "); Serial.println(Station_02_water_level_value);
                Serial.print("Station_Gateway_water_level_value: "); Serial.println(Station_Gateway_water_level_value);
                Serial.println("");
              */
            // Testing if it sends data withouth the sensors.
            // Uncoment the next lines to test:
            /*Station_01_water_level_value=77777;
            Station_02_water_level_value=66666;
            Station_Gateway_water_level_value=55555;*/

            String httpRequestData = "api_key=" + apiKey + "&value1=" + Station_01_water_level_value + "&value2=" + Station_02_water_level_value + "&value3=" + Station_Gateway_water_level_value + "&value4=" + csq + "";

            client.print(String("POST ") + resource + " HTTP/1.1\r\n");
            client.print(String("Host: ") + server + "\r\n");
            client.println("Connection: close");
            client.println("Content-Type: application/x-www-form-urlencoded");
            client.print("Content-Length: ");
            client.println(httpRequestData.length());
            client.println();

            // client.println(httpRequestData); //Comentando para ver se não loga mais a api_key no serial
            unsigned long timeout = millis();
            while (client.connected() && millis() - timeout < 5000L)
            {
              // Print available data (HTTP response from server)
              while (client.available())
              {
                char c = client.read();
                // #ifdef enableSerialLog
                // SerialMon.print(c);
                // #endif
                timeout = millis();
              }
            }
            // Close client and disconnect
            client.stop();
            // #ifdef enableSerialLog
            Serial.println(F("WebServer desconectado"));
            // #endif

            enableBackupDomain();
            setBackupRegister(2, 10); // indica que os dados foram salvos no servidor
            disableBackupDomain();

            modem.gprsDisconnect();
            // #ifdef enableSerialLog
            Serial.println(F("GPRS desconectado"));
            // #endif
            atualizaGrafico_flag = 0;

#ifdef enableRTCstm32
            // setTime(); //Não vejo pq tenho que resetar o time aqui, comentando em 23.09
            // #ifdef enableSerialLog
            // readTimeRTCstm32();
            // #endif
#endif

            digitalWrite(PB13, LOW); // desliga a energia do LoRa e Ultrasom
            delay(100);              // Enable do MP2307 no MINI360 precisa de 16ms para ativar a Vout
            pinMode(PB12, OUTPUT);   // Controle do enable da fonte regulada do SIM800L
            digitalWrite(PB12, LOW); // desliga a energia do SIM800L
            delay(100);              // Enable do MP2307 no MINI360 precisa de 16ms para ativar a Vout

            // vaiDormir(); //Entra em Deep Sleep
          }
        }
      }
    }

#endif // TINY_GSM_USE_GPRS
  } // if Celular
  else
  {
    Serial.println("Connexão é WiFi");
  } // else
}

#endif // atualizaGrafico

//////////////////////////////////////////////////// graphicUpdate_WiFi() ////////////////////////////////////////////////////
#ifdef atualizaGrafico

/*Correção do vazamento de memória (cliente criado na pilha, sem new)
Keep-Alive habilitado para reduzir custo do handshake SSL
Checagem de memória antes de tentar a conexão
Fallback simples caso o servidor recuse a conexão*/

void graphicUpdate_WiFi()
{
  if (WiFi.status() == WL_CONNECTED && connection_type == "WiFi")
  {
    // Garante memória suficiente para handshake SSL (~50 KB)
    if (ESP.getFreeHeap() < 55000) {
      Serial.printf("Memória insuficiente para SSL (%d bytes). Abortando envio.\n", ESP.getFreeHeap());
      return;
    }

    WiFiClientSecure client; // Criado na pilha, memória liberada ao sair da função
    client.setInsecure();    // Ignora verificação do certificado, a conexão ainda é HTTPS (TLS ativo, dados criptografados), mas sem autenticação do servidor
                             // Sem setInsecure() e com certificado válido → conexão HTTPS com criptografia e autenticação confiável do servidor.

    HTTPClient https;

    if (!https.begin(client, serverName)) {
      Serial.println("Falha ao iniciar conexão HTTPS.");
      return;
    }

    // Habilita Keep-Alive
    https.addHeader("Connection", "keep-alive");
    https.addHeader("Content-Type", "application/x-www-form-urlencoded");

    // Prepara dados do POST
    String httpRequestData = "api_key=" + apiKey +
                             "&value1=" + Station_01_water_level_value +
                             "&value2=" + Station_02_water_level_value +
                             "&value3=" + Station_Gateway_water_level_value +
                             "&value4=" + csq;

    Serial.println("Enviando requisição HTTP POST com Keep-Alive...");
    Serial.printf("Memória livre antes do POST: %d bytes\n", ESP.getFreeHeap());

    // Envia o POST
    int httpResponseCode = https.POST(httpRequestData);

    if (httpResponseCode > 0) {
      Serial.printf("HTTP Response code: %d\n", httpResponseCode);
      if (httpResponseCode == 200) {
        Serial.println("Mensagem enviada para o Servidor com sucesso.");
      }
    }
    else {
      Serial.printf("Erro no envio HTTPS. Código: %d\n", httpResponseCode);
    }

    Serial.printf("Memória livre após POST: %d bytes\n", ESP.getFreeHeap());

    https.end(); // Fecha a conexão, mas Keep-Alive permite reutilização até timeout do servidor
  }
  else
  {
    Serial.println("WiFi Desconectado");
  }
}

// void checkLinkStatusAndSend() {
//     if (!dataTransmitter) return;
    
//     TransmissionResult result = dataTransmitter->sendDataAuto(receivedData);
    
//     if (result == TX_SUCCESS) {
//         Serial.println("✓ Data sent successfully");
//         Station_01_flag = false;
//         Station_02_flag = false;
//         Station_Gateway_flag = false;
//         newDataReadyToSend = false;
//     } else {
//         Serial.println("✗ Failed: " + dataTransmitter->getLastError());
//     }
// }

/**
 * @brief WiFi-primary / NB-IoT-fallback transmission state machine.
 *
 * Decision logic (Issue #40):
 *  1. WiFi available  → send via WiFi; disconnect GPRS if it was active (data budget).
 *  2. WiFi down + modem registered → connect GPRS on demand; send via cellular.
 *  3. Neither available → wait, log every CONNECTION_CHECK_INTERVAL ms.
 *
 * WiFi recovery is handled automatically by the WiFiGotIP event which sets
 * wifiReady=true and schedules a GPRS disconnect via disconnectGprsRequested.
 *
 * Signal-quality fields (sigWiFi / sigCel) are populated here, just before
 * transmission, so they always reflect the active link at send time.
 */
void checkLinkStatusAndSend() {
    if (!dataTransmitter) {
        Serial.println("[TX] DataTransmitter not initialized!");
        return;
    }

    TransmissionResult result = TX_ERROR_WIFI; // default

    Serial.println("============================================================");

    if (wifiReady) {
        // ── Primary path: WiFi ──────────────────────────────────────────────
#ifdef enableCelular
        // GPRS may have been active as fallback — disconnect to save data budget.
        // (Also handled by disconnectGprsRequested in loop(), but explicit here
        //  in case the WiFiGotIP event fired after data was already queued.)
        if (gprsReady) {
            Serial.println("[TX] WiFi available — disconnecting GPRS to save data budget");
            disconnectGPRS();
        }
#endif // enableCelular

        // Populate gateway signal-quality fields
        receivedData.sigWiFi = WiFi.RSSI();
        receivedData.sigCel  = 0;

        Serial.printf("[TX] Sending via WiFi (primary) | RSSI: %ld dBm\n", receivedData.sigWiFi);
        printSensorData(receivedData);
        result = dataTransmitter->sendDataWiFi(receivedData);

#ifdef enableCelular
    } else if (cellularReady) {
        // ── Fallback path: NB-IoT cellular ──────────────────────────────────
        if (!gprsReady) {
            Serial.println("[TX] WiFi down — connecting GPRS for NB-IoT fallback...");
            if (!connectGPRS()) {
                Serial.println("[TX] GPRS connect failed — cannot send data this cycle.");
                newDataReadyToSend = false;
                Station_01_flag = false;
                Station_02_flag = false;
                Station_Gateway_flag = false;
                Serial.println("============================================================\n");
                return;
            }
            csq = modem.getSignalQuality();
        }

        // Populate gateway signal-quality fields
        receivedData.sigWiFi = 0;
        receivedData.sigCel  = csq;

        Serial.printf("[TX] Sending via Cellular NB-IoT (fallback) | CSQ: %d\n", csq);
        printSensorData(receivedData);
        result = dataTransmitter->sendDataCellular(receivedData);
#endif // enableCelular

    } else {
        // ── No connectivity ─────────────────────────────────────────────────
        unsigned long now = millis();
        if (now - lastConnectionCheckLog > CONNECTION_CHECK_INTERVAL) {
            Serial.println("[TX] Waiting for connectivity...");
            Serial.printf("   WiFi: %s | Cellular: %s\n",
                         wifiReady    ? "READY" : "NOT READY",
                         cellularReady ? "READY" : "NOT READY");
            lastConnectionCheckLog = now;
        }
        Serial.println("============================================================\n");
        return; // Don't reset flags — keep data queued until a link is available
    }

    // ── Handle transmission result ───────────────────────────────────────────
    if (result == TX_SUCCESS) {
        Serial.println("[TX] Data successfully transmitted | HTTP " +
                       String(dataTransmitter->getLastHttpCode()));
    } else {
        Serial.println("[TX] Transmission failed: " + String(transmissionResultToString(result)));
        Serial.println("[TX] Details: " + dataTransmitter->getLastError());
        Serial.println("[TX] HTTP Code: " + String(dataTransmitter->getLastHttpCode()));
        // NOTE: When SD offline buffer is implemented, failed data will be queued here.
    }

    // Reset flags regardless of outcome (one attempt per reading cycle)
    Station_01_flag     = false;
    Station_02_flag     = false;
    Station_Gateway_flag = false;
    newDataReadyToSend  = false;

    Serial.println("============================================================\n");
}
#endif // atualizaGrafico

void checkMemory() {
  Serial.printf("Memória livre: %d bytes\n", ESP.getFreeHeap());
}

// ================== Processa e imprime a struct ==================
void processLoRaPacketWithStruct() {
  receivedData.rssi = receivedRssi;
  receivedData.snr = receivedSnr;

  // Update timestamp in the struct:
  processTime(); // Getting current TS in UTC

  // Apply calibration to level reading
  int32_t rawLevel = receivedData.level;
  receivedData.level = calculateCalibratedLevel(receivedData.idStation, rawLevel);

  Serial.println("-------------------------------------------------");
  Serial.println("Pacote recebido via LoRa:");
  printSensorData(receivedData);
  // Serial.printf("RSSI LoRa: %d dBm | SNR: %.2f dB\n", rssi, snr);
  Serial.printf("RSSI LoRa: %d dBm | SNR: %.2f dB\n", receivedRssi, receivedSnr); // here it is right!
  Serial.println("-------------------------------------------------\n");
  newDataReadyToSend = true;
}

// ================== Exibe os campos da struct ==================
void printSensorData(const SensorData &d) {
  Serial.printf("ID Station: %lu\n", d.idStation);
  Serial.printf("Reading #: %lu\n", d.reading_number);

  // TODO: Station timestamp is not implemented yet 
  // Gateway Timestamp is being used by now since it has a ntp sync time:
  Serial.printf("Timestamp: %lu\n", d.timestamp);

  Serial.printf("Level: %ld\n", d.level);
  Serial.printf("Temperature: %.2f\n", d.temperature);
  Serial.printf("Pressure: %.2f\n", d.pressure);
  Serial.printf("Humidity: %ld\n", d.humidity);
  Serial.printf("Precipitation pulses: %d\n", d.precipitation_pulses);
  Serial.printf("Surface temperature: %.2f\n", d.surface_temperature);
  Serial.printf("Vbat: %ld\n", d.Vbat);
  Serial.printf("Vpanel: %ld\n", d.Vpanel);
  Serial.printf("RSSI (sensor): %ld\n", d.rssi);
  Serial.printf("SNR (sensor): %.2f\n", d.snr);
  Serial.printf("sigWiFi: %ld\n", d.sigWiFi);
  Serial.printf("sigCel: %ld\n", d.sigCel);
}
