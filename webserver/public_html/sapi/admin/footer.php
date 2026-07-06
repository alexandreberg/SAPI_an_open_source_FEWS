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
