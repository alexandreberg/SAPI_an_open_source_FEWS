/**
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
//Arduino Credentials file
//Not synced with GitHub!

#include <Arduino.h> //Include Arduino Headers

// MySQL database to store sensor data.
const char server[] = "ilha3d.com"; 
const char resource[] = "/sapi/sensorData/receive-data.php";
const int  port = 443;

// Changed in 2025-12-29:
// Generate new API key (run in terminal):
// openssl rand -hex 32
String apiKey = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx";

// Replace with your WiFi network credentials
const char* ssid            = "SSID";
const char* wifi_password   = "password";


const char* serverName = "https://ilha3d.com/sapi/sensorData/receive-data.php";