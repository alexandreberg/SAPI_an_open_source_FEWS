-- phpMyAdmin SQL Dump
-- version 5.2.2
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Tempo de geração: 14/03/2026 às 01:30
-- Versão do servidor: 11.8.3-MariaDB-log
-- Versão do PHP: 7.2.34

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Banco de dados: `<HOSTINGER_USER>_sapi`
--

-- --------------------------------------------------------

--
-- Estrutura para tabela `measurements`
--

CREATE TABLE `measurements` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `id_station` int(10) UNSIGNED NOT NULL,
  `reading_number` int(10) UNSIGNED DEFAULT NULL,
  `timestamp` datetime NOT NULL,
  `level_cm` smallint(5) UNSIGNED DEFAULT NULL,
  `temperature_C` smallint(6) DEFAULT NULL,
  `pressure` decimal(6,2) UNSIGNED DEFAULT NULL,
  `humidity_percentual` tinyint(3) UNSIGNED DEFAULT NULL,
  `surface_temperature_C` smallint(6) DEFAULT NULL,
  `precipitation_pulses` smallint(5) UNSIGNED DEFAULT NULL,
  `precipitation_mm` decimal(6,2) UNSIGNED DEFAULT NULL,
  `bat_voltage` decimal(4,2) UNSIGNED DEFAULT NULL,
  `panel_voltage` decimal(4,2) UNSIGNED DEFAULT NULL,
  `rssi` smallint(6) DEFAULT NULL,
  `snr` decimal(5,2) DEFAULT NULL,
  `s_wifi` smallint(6) DEFAULT NULL,
  `s_gsm` smallint(6) DEFAULT NULL,
  `flag` varchar(8) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `edited_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  `deleted_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `merge`
--

CREATE TABLE `merge` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `timestamp` datetime NOT NULL,
  `mode` enum('hourly','hourly_nowcast','daily','climatology') NOT NULL,
  `prec_mm` decimal(7,4) UNSIGNED NOT NULL,
  `prmsl` decimal(6,2) UNSIGNED DEFAULT NULL,
  `flag` varchar(2) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `edited_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  `deleted_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Estrutura para tabela `stations`
--

CREATE TABLE `stations` (
  `id` int(10) UNSIGNED NOT NULL,
  `name` varchar(30) NOT NULL,
  `description` varchar(150) DEFAULT NULL,
  `lat` decimal(9,6) NOT NULL,
  `lon` decimal(9,6) NOT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `edited_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  `deleted_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Índices para tabelas despejadas
--

--
-- Índices de tabela `measurements`
--
ALTER TABLE `measurements`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_measurements_station_ts` (`id_station`,`timestamp`),
  ADD KEY `idx_measurements_ts` (`timestamp`);

--
-- Índices de tabela `merge`
--
ALTER TABLE `merge`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `idx_timestamp_unique` (`timestamp`),
  ADD KEY `idx_merge_ts_mode` (`timestamp`,`mode`);

--
-- Índices de tabela `stations`
--
ALTER TABLE `stations`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT para tabelas despejadas
--

--
-- AUTO_INCREMENT de tabela `measurements`
--
ALTER TABLE `measurements`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `merge`
--
ALTER TABLE `merge`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT de tabela `stations`
--
ALTER TABLE `stations`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- Restrições para tabelas despejadas
--

--
-- Restrições para tabelas `measurements`
--
ALTER TABLE `measurements`
  ADD CONSTRAINT `fk_measurements_station` FOREIGN KEY (`id_station`) REFERENCES `stations` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
