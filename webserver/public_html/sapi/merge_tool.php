<?php require_once 'header.php'; ?>

      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-6"><h3 class="mb-0">Dashboard</h3></div>
              <div class="col-sm-6">
                <?php // espaço para breadcrumbs/botões ?>
              </div>
            </div>
          </div>
        </div>
        <!--end::App Content Header-->

        <!--begin::App Content-->
        <div class="app-content">
          <div class="container-fluid">

            <div class="row">
              <div class="col-12">

                <!-- CARD DO MAPA -->
                <div class="card mb-3">
                  <div class="card-header d-flex justify-content-between align-items-center">
                    <h3 class="card-title mb-0">Seleção de área (10 km x 10 km)</h3>
                    <span class="text-muted small">Clique no mapa ou preencha latitude/longitude</span>
                  </div>
                  <div class="card-body">
                    <div id="map"></div>
                  </div>
                </div>

                <!-- LINHA: LAT / LON / BOTÃO -->
                <form id="coordsForm" class="mb-3" onsubmit="return false;">
                  <div class="row g-2 align-items-center">
                    <div class="col-12 col-md">
                      <label for="latitude" class="form-label mb-0">Latitude</label>
                    </div>
                    <div class="col-12 col-md">
                      <input
                        type="text"
                        class="form-control"
                        id="latitude"
                        placeholder="-27.594900"
                      >
                    </div>

                    <div class="col-12 col-md">
                      <label for="longitude" class="form-label mb-0">Longitude</label>
                    </div>
                    <div class="col-12 col-md">
                      <input
                        type="text"
                        class="form-control"
                        id="longitude"
                        placeholder="-48.548200"
                      >
                    </div>

                    <div class="col-12 col-md">
                      <button type="button" id="btnSelectCoords" class="btn btn-primary w-100">
                        Selecionar
                      </button>
                    </div>
                  </div>
                </form>

                <!-- LINHA: DATA INICIAL / DATA FINAL / BOTÃO -->
                <form id="datesForm" class="mb-3" method="get">
                  <div class="row g-2 align-items-center">
                    <div class="col-12 col-md">
                      <label for="startDate" class="form-label mb-0">Data inicial</label>
                    </div>
                    <div class="col-12 col-md">
                      <input
                        type="datetime-local"
                        class="form-control"
                        id="startDate"
                        name="startDate"
                        value="<?= htmlspecialchars($startDate, ENT_QUOTES, 'UTF-8') ?>"
                        required
                      >
                    </div>

                    <div class="col-12 col-md">
                      <label for="endDate" class="form-label mb-0">Data final</label>
                    </div>
                    <div class="col-12 col-md">
                      <input
                        type="datetime-local"
                        class="form-control"
                        id="endDate"
                        name="endDate"
                        value="<?= htmlspecialchars($endDate, ENT_QUOTES, 'UTF-8') ?>"
                        required
                      >
                    </div>

                    <div class="col-12 col-md">
                      <button type="submit" class="btn btn-primary w-100">
                        Selecionar
                      </button>
                    </div>
                  </div>
                </form>

              </div>
            </div>

          </div>
        </div>
        <!--end::App Content-->
      </main>
      <!--end::App Main-->

    <!--begin::Script-->
    <!--begin::Third Party Plugin(OverlayScrollbars)-->
    <script
      src="https://cdn.jsdelivr.net/npm/overlayscrollbars@2.11.0/browser/overlayscrollbars.browser.es6.min.js"
      crossorigin="anonymous"
    ></script>
    <!--end::Third Party Plugin(OverlayScrollbars)--><!--begin::Required Plugin(popperjs for Bootstrap 5)-->
    <script
      src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.8/dist/umd/popper.min.js"
      crossorigin="anonymous"
    ></script>
    <!--end::Required Plugin(popperjs for Bootstrap 5)--><!--begin::Required Plugin(Bootstrap 5)-->
    <script
      src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.7/dist/js/bootstrap.min.js"
      crossorigin="anonymous"
    ></script>
    <!--end::Required Plugin(Bootstrap 5)--><!--begin::Required Plugin(AdminLTE)-->
    <script src="./js/adminlte.js"></script>
    <!--end::Required Plugin(AdminLTE)--><!--begin::OverlayScrollbars Configure-->
    <script>
      const SELECTOR_SIDEBAR_WRAPPER = '.sidebar-wrapper';
      const Default = {
        scrollbarTheme: 'os-theme-light',
        scrollbarAutoHide: 'leave',
        scrollbarClickScroll: true,
      };
      document.addEventListener('DOMContentLoaded', function () {
        const sidebarWrapper = document.querySelector(SELECTOR_SIDEBAR_WRAPPER);
        if (sidebarWrapper && OverlayScrollbarsGlobal?.OverlayScrollbars !== undefined) {
          OverlayScrollbarsGlobal.OverlayScrollbars(sidebarWrapper, {
            scrollbars: {
              theme: Default.scrollbarTheme,
              autoHide: Default.scrollbarAutoHide,
              clickScroll: Default.scrollbarClickScroll,
            },
          });
        }
      });
    </script>
    <!--end::OverlayScrollbars Configure-->

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <script>
      // Grid de Santa Catarina vindo do PHP
      const gridSc = <?php echo json_encode($gridSc, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); ?>;
    </script>
    
    <script>
    document.addEventListener('DOMContentLoaded', function () {
      // Centro inicial em Florianópolis
      var initialLat = -27.5949;
      var initialLng = -48.5482;
    
      var map = L.map('map', {
        center: [initialLat, initialLng],
        zoom: 12,
        worldCopyJump: false
      });
    
    // Teste com OSM padrão
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);
    
      var marker = null;
      var square = null;
    
      var latInput = document.getElementById('latitude');
      var lngInput = document.getElementById('longitude');
      var btnSelectCoords = document.getElementById('btnSelectCoords');
    
      // Distância aproximada em km (haversine)
      function distanceKm(lat1, lon1, lat2, lon2) {
        const R = 6371; // raio da Terra em km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a =
          Math.sin(dLat / 2) * Math.sin(dLat / 2) +
          Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
          Math.sin(dLon / 2) * Math.sin(dLon / 2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
      }
    
      // Guarda os quadrados dos 4 pontos mais próximos para poder remover depois
      var nearestSquares = [];
      var nearestMarkers = [];
    
      function clearNearestLayers() {
        nearestSquares.forEach(function (sq) { map.removeLayer(sq); });
        nearestMarkers.forEach(function (mk) { map.removeLayer(mk); });
        nearestSquares = [];
        nearestMarkers = [];
      }
    
      function getSquareBounds(lat, lng, halfSideKm) {
        var earthRadiusKm = 6371.0;
        var latDelta = (halfSideKm / earthRadiusKm) * (180 / Math.PI);
        var lngDelta = (halfSideKm / earthRadiusKm) * (180 / Math.PI) / Math.cos(lat * Math.PI / 180);
    
        return [
          [lat - latDelta, lng - lngDelta],
          [lat + latDelta, lng + lngDelta]
        ];
      }
    
      function setSelection(lat, lng, zoomTo) {
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);
    
        if (marker) map.removeLayer(marker);
        if (square) map.removeLayer(square);
    
        marker = L.marker([lat, lng]).addTo(map);
    
        var bounds = getSquareBounds(lat, lng, 5.0); // 10 km de lado = 5 km pra cada lado
        square = L.rectangle(bounds, { color: 'red', weight: 1 }).addTo(map);
    
        if (zoomTo) {
          map.fitBounds(bounds.pad(0.5));
        }
      }
    
      map.on('click', function (e) {
        var lat = e.latlng.lat;
        var lng = e.latlng.lng;
    
        // quadrado do ponto clicado (vermelho)
        setSelection(lat, lng, false);
    
        // limpa quadrados marcados anteriormente
        clearNearestLayers();
    
        // calcula distâncias de todos os pontos do grid
        var distances = gridSc.map(function (p) {
          return {
            lat: p.lat,
            lon: p.lon,
            d: distanceKm(lat, lng, p.lat, p.lon)
          };
        });
    
        // ordena pelo mais próximo e pega os 4 primeiros
        distances.sort(function (a, b) { return a.d - b.d; });
        var nearest4 = distances.slice(0, 4);
    
        // para cada um dos 4 mais próximos: marcador + quadrado 10x10 km (cor diferente)
        nearest4.forEach(function (p) {
          var m = L.circleMarker([p.lat, p.lon], {
            radius: 4,
            color: '#0d6efd',
            weight: 2,
            fillOpacity: 0.7
          }).addTo(map);
    
          var b = getSquareBounds(p.lat, p.lon, 5.0); // 5 km pra cada lado
          var r = L.rectangle(b, {
            color: '#0d6efd',  // azul ou outra cor diferente do vermelho
            weight: 1
          }).addTo(map);
    
          nearestMarkers.push(m);
          nearestSquares.push(r);
        });
      });
    
      // Botão Selecionar (latitude/longitude -> mapa)
      btnSelectCoords.addEventListener('click', function () {
        var latVal = latInput.value.trim().replace(',', '.');
        var lngVal = lngInput.value.trim().replace(',', '.');
    
        if (!latVal || !lngVal) {
          alert('Preencha latitude e longitude.');
          return;
        }
    
        var lat = parseFloat(latVal);
        var lng = parseFloat(lngVal);
    
        if (!isFinite(lat) || !isFinite(lng)) {
          alert('Latitude e longitude devem ser números válidos.');
          return;
        }
    
        if (lat < -90 || lat > 90) {
          alert('Latitude deve estar entre -90 e 90.');
          return;
        }
    
        if (lng < -180 || lng > 180) {
          alert('Longitude deve estar entre -180 e 180.');
          return;
        }
    
        setSelection(lat, lng, true);
      });
    
      // Validação extra para datas
      var datesForm = document.getElementById('datesForm');
      datesForm.addEventListener('submit', function (e) {
        var start = document.getElementById('startDate').value;
        var end   = document.getElementById('endDate').value;
    
        if (!start || !end) {
          e.preventDefault();
          alert('Preencha as duas datas.');
          return;
        }
    
        if (start > end) {
          e.preventDefault();
          alert('Data inicial deve ser menor ou igual à data final.');
          return;
        }
      });
    });
    </script>

<?php require_once 'footer.php'; ?>