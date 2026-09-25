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
//require_once dirname(__DIR__, 1) . '/site/functions.php';
require_once 'functions.php';

// Se quiser manter valores de data após recarregar:
$startDate = isset($_GET['startDate']) ? $_GET['startDate'] : '';
$endDate   = isset($_GET['endDate'])   ? $_GET['endDate']   : '';

// Gera o grid de SC
function grid(): array
{
    $grid = [
        'brazil' => [
            'sc' => []
        ]
    ];

    // Bounding box aproximado de Santa Catarina
    $north = -25.72; // 25.72° S
    $south = -29.49; // 29.49° S
    $west  = -53.98; // 53.98° W
    $east  = -48.32; // 48.32° W

    // Distância desejada entre pontos (km)
    $stepLatKm = 10.0;
    $stepLonKm = 10.0;

    // Aproximação: 1° de latitude ~ 111 km
    $kmPerDegLat = 111.0;
    $deltaLat = $stepLatKm / $kmPerDegLat;

    for ($lat = $south; $lat <= $north + 1e-9; $lat += $deltaLat) {
        $kmPerDegLon = $kmPerDegLat * cos(deg2rad($lat));
        if ($kmPerDegLon <= 0) {
            continue;
        }
        $deltaLon = $stepLonKm / $kmPerDegLon;

        for ($lon = $west; $lon <= $east + 1e-9; $lon += $deltaLon) {
            $grid['brazil']['sc'][] = [
                'lat' => round($lat, 6),
                'lon' => round($lon, 6),
            ];
        }
    }

    return $grid;
}

// gera o grid e pega só SC
$grid = grid();
$gridSc = $grid['brazil']['sc'];
?>

<!doctype html>
<html lang="en">
  <!--begin::Head-->
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <title>AdminLTE | Dashboard v2</title>
    <!--begin::Accessibility Meta Tags-->
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes" />
    <meta name="color-scheme" content="light dark" />
    <meta name="theme-color" content="#007bff" media="(prefers-color-scheme: light)" />
    <meta name="theme-color" content="#1a1a1a" media="(prefers-color-scheme: dark)" />
    <!--end::Accessibility Meta Tags-->
    <!--begin::Primary Meta Tags-->
    <meta name="title" content="AdminLTE | Dashboard v2" />
    <meta name="author" content="ColorlibHQ" />
    <meta
      name="description"
      content="AdminLTE is a Free Bootstrap 5 Admin Dashboard, 30 example pages using Vanilla JS. Fully accessible with WCAG 2.1 AA compliance."
    />
    <meta
      name="keywords"
      content="bootstrap 5, bootstrap, bootstrap 5 admin dashboard, bootstrap 5 dashboard, bootstrap 5 charts, bootstrap 5 calendar, bootstrap 5 datepicker, bootstrap 5 tables, bootstrap 5 datatable, vanilla js datatable, colorlibhq, colorlibhq dashboard, colorlibhq admin dashboard, accessible admin panel, WCAG compliant"
    />
    <!--end::Primary Meta Tags-->
    <!--begin::Accessibility Features-->
    <!-- Skip links will be dynamically added by accessibility.js -->
    <meta name="supported-color-schemes" content="light dark" />
    <link rel="preload" href="/css/adminlte.css" as="style" />
    <!--end::Accessibility Features-->
    <!--begin::Fonts-->
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/@fontsource/source-sans-3@5.0.12/index.css"
      integrity="sha256-tXJfXfp6Ewt1ilPzLDtQnJV4hclT9XuaZUKyUvmyr+Q="
      crossorigin="anonymous"
      media="print"
      onload="this.media='all'"
    />
    <!--end::Fonts-->
    <!--begin::Third Party Plugin(OverlayScrollbars)-->
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/overlayscrollbars@2.11.0/styles/overlayscrollbars.min.css"
      crossorigin="anonymous"
    />
    <!--end::Third Party Plugin(OverlayScrollbars)-->
    <!--begin::Third Party Plugin(Bootstrap Icons)-->
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css"
      crossorigin="anonymous"
    />
    <!--end::Third Party Plugin(Bootstrap Icons)-->
    <!--begin::Required Plugin(AdminLTE)-->
    <link rel="stylesheet" href="/css/adminlte.css" />
    <!--end::Required Plugin(AdminLTE)-->

<!-- Leaflet CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

<style>
  /* Corrige tiles quadriculados por causa do img { max-width:100% } do Bootstrap/AdminLTE */
  .leaflet-container img {
    max-width: none !important;
  }

  /* Altura do mapa */
  #map {
    width: 100%;
    height: 400px;
  }

  /* Aumenta o ícone SAPI no topo da sidebar — desktop only */
  @media (min-width: 992px) {
    .app-header {
      min-height: 90px !important;
    }
    .sidebar-brand {
      height: 90px !important;
      padding: 8px 0;
    }
    .brand-image {
      max-height: 74px !important;
      width: auto !important;
      margin-top: 0;
    }
  }
</style>

  </head>
  <body class="layout-fixed sidebar-expand-lg sidebar-open bg-body-tertiary">
    <!--begin::App Wrapper-->
    <div class="app-wrapper">
      <!--begin::Header-->
      <nav class="app-header navbar navbar-expand bg-body">
        <!--begin::Container-->
        <div class="container-fluid">
          <!--begin::Start Navbar Links-->
          <ul class="navbar-nav">
            <li class="nav-item">
              <a class="nav-link" data-lte-toggle="sidebar" href="#" role="button">
                <i class="bi bi-list"></i>
              </a>
            </li>
            <li class="nav-item d-none d-md-block">
              <span class="nav-link fw-semibold text-body">
                SAPI — Sistema de Alerta Prévio de Inundações
              </span>
            </li>
          </ul>
          <!--end::Start Navbar Links-->
          <!--begin::End Navbar Links-->
          <ul class="navbar-nav ms-auto">
            <!--begin::Alert Log Link-->
            <li class="nav-item">
              <a class="nav-link" href="/sapi/alert_log.php" title="Log de Alertas">
                <i class="bi bi-bell-fill"></i>
              </a>
            </li>
            <!--end::Alert Log Link-->
            <!--begin::Admin Login Link-->
            <li class="nav-item">
              <a class="nav-link" href="/sapi/login.php" title="Área administrativa">
                <i class="bi bi-person-circle me-1"></i>
                <span class="d-none d-md-inline">Admin</span>
              </a>
            </li>
            <!--end::Admin Login Link-->
          </ul>
          <!--end::End Navbar Links-->
        </div>
        <!--end::Container-->
      </nav>
      <!--end::Header-->
      <!--begin::Sidebar-->
      <aside class="app-sidebar bg-body-secondary shadow" data-bs-theme="dark">
        <!--begin::Sidebar Brand-->
        <div class="sidebar-brand">
          <!--begin::Brand Link-->
          <a href="/sapi/" class="brand-link">
            <!--begin::Brand Image-->
            <img
              src="/sapi/assets/img/SAPI_icone-320x240.png"
              alt="Sapi Logo"
              class="brand-image opacity-75 shadow"
            />
            <!--end::Brand Image-->
            <!--begin::Brand Text-->
            <span class="brand-text fw-light">SAPI</span>
            <!--end::Brand Text-->
          </a>
          <!--end::Brand Link-->
        </div>
        <!--end::Sidebar Brand-->
        <!--begin::Sidebar Wrapper-->
        <div class="sidebar-wrapper">
          <nav class="mt-2">
            <!--begin::Sidebar Menu-->
            <ul
              class="nav sidebar-menu flex-column"
              data-lte-toggle="treeview"
              role="navigation"
              aria-label="Main navigation"
              data-accordion="false"
              id="navigation"
            >
              <!-- Mapa de estações -->
              <li class="nav-item">
                <a href="/sapi/index.php" class="nav-link">
                  <i class="nav-icon bi bi-map"></i>
                  <p>Mapa</p>
                </a>
              </li>

              <!-- Comparar estações -->
              <li class="nav-item">
                <a href="/sapi/compare.php" class="nav-link">
                  <i class="nav-icon bi bi-bar-chart-line"></i>
                  <p>Comparar</p>
                </a>
              </li>

              <!-- Previsões M4 LightGBM (Issue #108) -->
              <li class="nav-item">
                <a href="/sapi/predictions.php" class="nav-link">
                  <i class="nav-icon bi bi-graph-up-arrow"></i>
                  <p>Previsões</p>
                </a>
              </li>

              <!-- Lista de estações (dinâmica, carregada do banco) -->
              <?php
              // Busca lista de estações para o menu lateral (Issue #56 Phase 2)
              try {
                  $pdo_sidebar = db();
                  $stmt_sidebar = $pdo_sidebar->query(
                      "SELECT id, name FROM stations WHERE deleted_at IS NULL ORDER BY id ASC"
                  );
                  $sidebar_stations = $stmt_sidebar->fetchAll(PDO::FETCH_ASSOC);
              } catch (Throwable $e) {
                  $sidebar_stations = [];
              }

              if (!empty($sidebar_stations)):
              ?>
              <li class="nav-item menu-open">
                <a href="#" class="nav-link active">
                  <i class="nav-icon bi bi-broadcast-pin"></i>
                  <p>
                    Estações
                    <i class="nav-arrow bi bi-chevron-right"></i>
                  </p>
                </a>
                <ul class="nav nav-treeview">
                  <?php foreach ($sidebar_stations as $s): ?>
                  <li class="nav-item">
                    <a href="/sapi/station.php?id=<?= (int)$s['id'] ?>" class="nav-link">
                      <i class="nav-icon bi bi-reception-4"></i>
                      <p><?= htmlspecialchars($s['name']) ?></p>
                    </a>
                  </li>
                  <?php endforeach; ?>
                </ul>
              </li>
              <?php endif; ?>

            </ul>
            <!--end::Sidebar Menu-->
          </nav>
        </div>
        <!--end::Sidebar Wrapper-->
      </aside>
      <!--end::Sidebar-->