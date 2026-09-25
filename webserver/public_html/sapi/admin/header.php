<?php
/**
 * @file header.php (admin)
 * @brief Shared HTML header / layout opening for all admin pages.
 *
 * Expects the following variables to be set BEFORE including this file:
 *   - string $pageTitle — shown in the <title> tag and content header.
 *   - string $activePage — one of: stations | alert_rules | contacts | alert_log
 *
 * Session must already be started by _auth.php before this file is included.
 *
 * @author Alexandre Nuernberg
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

// functions.php must be included by the calling page before this header.
// (It provides db() which admin pages use for their CRUD operations.)

$pageTitle  = $pageTitle  ?? 'Admin';
$activePage = $activePage ?? '';
?>
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <title>SAPI Admin — <?= htmlspecialchars($pageTitle) ?></title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="robots" content="noindex, nofollow" />

    <!-- Fonts -->
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/@fontsource/source-sans-3@5.0.12/index.css"
          crossorigin="anonymous" />

    <!-- OverlayScrollbars -->
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/overlayscrollbars@2.11.0/styles/overlayscrollbars.min.css"
          crossorigin="anonymous" />

    <!-- Bootstrap Icons -->
    <link rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/bootstrap-icons.min.css"
          crossorigin="anonymous" />

    <!-- AdminLTE — absolute path, works from any subdirectory -->
    <link rel="stylesheet" href="/css/adminlte.css" />
  </head>
  <body class="layout-fixed sidebar-expand-lg sidebar-open bg-body-tertiary">
    <div class="app-wrapper">

      <!-- ===== Navbar ===== -->
      <nav class="app-header navbar navbar-expand bg-body">
        <div class="container-fluid">
          <!-- Toggle sidebar -->
          <ul class="navbar-nav">
            <li class="nav-item">
              <a class="nav-link" data-lte-toggle="sidebar" href="#" role="button">
                <i class="bi bi-list"></i>
              </a>
            </li>
            <li class="nav-item d-none d-md-block">
              <a href="../index.php" class="nav-link">
                <i class="bi bi-house me-1"></i> Painel público
              </a>
            </li>
          </ul>

          <!-- Right side: sign-out -->
          <ul class="navbar-nav ms-auto">
            <li class="nav-item dropdown user-menu">
              <a href="#" class="nav-link dropdown-toggle" data-bs-toggle="dropdown">
                <i class="bi bi-person-circle me-1"></i>
                <span class="d-none d-md-inline">Admin</span>
              </a>
              <ul class="dropdown-menu dropdown-menu-end">
                <li>
                  <a href="../logout.php" class="dropdown-item text-danger">
                    <i class="bi bi-box-arrow-right me-1"></i> Sair
                  </a>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </nav>
      <!-- ===== /Navbar ===== -->

      <!-- ===== Sidebar ===== -->
      <aside class="app-sidebar bg-body-secondary shadow" data-bs-theme="dark">
        <div class="sidebar-brand">
          <a href="../index.php" class="brand-link">
            <img src="/sapi/assets/img/alert-icon-1562.png" alt="SAPI" class="brand-image opacity-75 shadow" />
            <span class="brand-text fw-light">SAPI Admin</span>
          </a>
        </div>

        <div class="sidebar-wrapper">
          <nav class="mt-2">
            <ul class="nav sidebar-menu flex-column" data-lte-toggle="treeview"
                role="navigation" data-accordion="false">

              <li class="nav-item">
                <a href="stations.php"
                   class="nav-link <?= $activePage === 'stations' ? 'active' : '' ?>">
                  <i class="nav-icon bi bi-broadcast-pin"></i>
                  <p>Estações</p>
                </a>
              </li>

              <li class="nav-item">
                <a href="alert_rules.php"
                   class="nav-link <?= $activePage === 'alert_rules' ? 'active' : '' ?>">
                  <i class="nav-icon bi bi-sliders"></i>
                  <p>Regras de Alerta</p>
                </a>
              </li>

              <li class="nav-item">
                <a href="contacts.php"
                   class="nav-link <?= $activePage === 'contacts' ? 'active' : '' ?>">
                  <i class="nav-icon bi bi-people"></i>
                  <p>Contatos</p>
                </a>
              </li>

              <li class="nav-item">
                <a href="alert_log.php"
                   class="nav-link <?= $activePage === 'alert_log' ? 'active' : '' ?>">
                  <i class="nav-icon bi bi-journal-text"></i>
                  <p>Log de Alertas</p>
                </a>
              </li>

            </ul>
          </nav>
        </div>
      </aside>
      <!-- ===== /Sidebar ===== -->
