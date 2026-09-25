<?php
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
# link para testar: https://ilha3d.com/rioDoSitio/alerta_sensor-01.php

require_once "credenciais.php";

// Configuração do e-mail
$to = "alexandreberg@gmail.com";
$subject = "Alerta de Inundação - sensor-01!";
$headers = "MIME-Version: 1.0\r\n";
$headers .= "Content-type:text/html;charset=UTF-8\r\n";
$headers .= "From: alerta.ilha3d@gmail.com\r\n";

// Função para registrar a hora de execução da crontab
function registrar_execucao() {
    $hora_execucao = date('Y-m-d H:i:s');
    $logfile = '/home/<HOSTINGER_USER>/public_html/rioDoSitio/cron_log.txt';
    //file_put_contents($logfile, "Script executado em: $hora_execucao\n", FILE_APPEND);
    file_put_contents($logfile, "Script executado em: $hora_execucao\n");
}

// Conectar ao banco de dados
$conn = new mysqli($servername, $username, $password, $dbname);
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Obter o valor mais recente do sensor
$sql = "SELECT value1 FROM Sensor ORDER BY reading_time DESC LIMIT 1";
$result = $conn->query($sql);
if ($result->num_rows > 0) {
    $row = $result->fetch_assoc();
    $level_zero = 291.0; // Renivelado em 14.06.2025 com travas no sensor-01 com a régua linimetrica medindo 30cm e o US 261cm
    $value1 = $row['value1'];
    $cota = $level_zero - $value1;
    $level_alerta = 100;    // Nivel de alerta para envio das mensagens, em cm.

    if ($cota >= $level_alerta) {
        $subject = "Alerta de Inundação - sensor-01! Nível de alerta: " . $cota . " cm";
        $body = "
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset='UTF-8'>
            <title>Alerta de Inundação do sensor-01</title>
            <style>
                body {
                    font-family: sans-serif;
                    text-align: center;
                }
                h1 {
                    margin-top: 50px; /* Adiciona espaço acima do título */
                }
                a {
                    display: block; /* Faz com que os links ocupem toda a largura */
                    padding: 20px;
                    margin: 20px auto; /* Centraliza os links horizontalmente */
                    background-color: #f2f2f2;
                    color: #333;
                    text-decoration: none;
                    border-radius: 5px;
                    width: 200px; /* Largura dos links */
                }
                a:hover {
                    background-color: #ddd;
                }
            </style>
        </head>
        <body><center>
            <h1>Para conferir se o alerta procede, cheque o gráfico abaixo.</h1>
            <h2>Nível de alerta atual: " . $cota . " cm</h2>
            <h2><a href='https://ilha3d.com/rioDoSitio/grafico_barra_mediana.php'>Gráficos de Barras com filtro de mediana</a></h2>
            <a href='https://ilha3d.com/rioDoSitio/registros.php'>Registros</a>
            <img src='https://ilha3d.com/rioDoSitio/sensor_01_ponte_02_1024x768.jpg' alt='Imagem do Sensor'>
        </center></body>
        </html>";

        // Enviar o e-mail
        if (mail($to, $subject, $body, $headers)) {
            echo "Email enviado com sucesso!";
        } else {
            echo "Erro ao enviar o email.";
        }
    }
} else {
    echo "Nenhum dado encontrado.";
}
$conn->close();

// Registrar a execução
registrar_execucao();

?>

