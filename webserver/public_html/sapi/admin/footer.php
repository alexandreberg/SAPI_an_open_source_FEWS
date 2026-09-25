<!--
SPDX-License-Identifier: AGPL-3.0-or-later
Copyright (C) 2024–2026 Alexandre Nuernberg <alexandreberg@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
-->
      <!-- ===== Footer ===== -->
      <footer class="app-footer">
        <div class="float-end d-none d-sm-inline">
          Desenvolvido por
          <a href="https://ilha3d.com/">Alexandre Nuernberg</a>.
        </div>
        <strong><a href="../index.php" class="text-decoration-none">SAPI</a></strong>
        — Área Administrativa.
      </footer>
      <!-- ===== /Footer ===== -->

    </div><!-- /.app-wrapper -->

    <!-- OverlayScrollbars -->
    <script src="https://cdn.jsdelivr.net/npm/overlayscrollbars@2.11.0/browser/overlayscrollbars.browser.es6.min.js"
            crossorigin="anonymous"></script>

    <!-- Popper + Bootstrap 5 -->
    <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.8/dist/umd/popper.min.js"
            crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.min.js"
            crossorigin="anonymous"></script>

    <!-- AdminLTE -->
    <script src="/js/adminlte.js"></script>

    <!-- OverlayScrollbars init -->
    <script>
      document.addEventListener('DOMContentLoaded', function () {
        const sw = document.querySelector('.sidebar-wrapper');
        if (sw && OverlayScrollbarsGlobal?.OverlayScrollbars) {
          OverlayScrollbarsGlobal.OverlayScrollbars(sw, {
            scrollbars: { theme: 'os-theme-light', autoHide: 'leave', clickScroll: true }
          });
        }
      });
    </script>

  </body>
</html>
