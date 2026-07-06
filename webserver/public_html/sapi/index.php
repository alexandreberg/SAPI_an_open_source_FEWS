<?php
require_once 'header.php';

// Busca estações no banco
$pdo = db();
$sql = "SELECT id, name, description, lat, lon 
        FROM stations
        WHERE deleted_at IS NULL";
$stmt = $pdo->query($sql);
$stations = $stmt->fetchAll(PDO::FETCH_ASSOC);

// Mesma whitelist de variáveis usada no view.php
$variables = [
    'level_cm'              => 'Nível (cm)',
    'temperature_C'         => 'Temperatura do ar (°C)',
    'pressure'              => 'Pressão (hPa)',
    'humidity_percentual'   => 'Umidade relativa (%)',
    'surface_temperature_C' => 'Temperatura superfície (°C)',
    'precipitation_pulses'  => 'Pulsos de precipitação',
    'bat_voltage'           => 'Tensão bateria (V)',
    'panel_voltage'         => 'Tensão painel (V)',
    'rssi'                  => 'RSSI',
    's_wifi'                => 'Sinal Wi-Fi',
    's_gsm'                 => 'Sinal GSM',
    // descomente se tiver essas colunas:
    // 'prec_mm'              => 'Precipitação (mm)',
    // 'prmsl'                => 'Pressão ao nível do mar (hPa)',
];
?>

      <!--begin::App Main-->
      <main class="app-main">
        <!--begin::App Content Header-->
        <div class="app-content-header">
          <div class="container-fluid">
            <div class="row">
              <div class="col-sm-6"><h3 class="mb-0">Estações</h3></div>
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
                    <h3 class="card-title mb-0">Mapa de estações</h3>
                    <span class="text-muted small">Clique em um pin para ver detalhes da estação</span>
                  </div>
                  <div class="card-body">
                    <div id="map" style="height: 500px;"></div>
                  </div>
                </div>

              </div>
            </div>

          </div>
        </div>
        <!--end::App Content-->
      </main>
      <!--end::App Main-->

    <!--begin::Script-->
 
    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

    <!-- Dados vindos do PHP -->
    <script>
      const stations  = <?= json_encode($stations,   JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_NUMERIC_CHECK); ?>;
      const variables = <?= json_encode($variables, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES); ?>;
    </script>

    <script>
    document.addEventListener('DOMContentLoaded', function () {

      // Centro padrão (Florianópolis)
      let initialLat = -27.5949;
      let initialLng = -48.5482;
      let initialZoom = 11;

      // Se houver estação, centraliza na primeira
      if (stations.length > 0) {
        initialLat = stations[0].lat;
        initialLng = stations[0].lon;
      }

      const map = L.map('map', {
        center: [initialLat, initialLng],
        zoom: initialZoom,
        worldCopyJump: false
      });

      // Camada base OSM
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
      }).addTo(map);

      const markers = [];

      stations.forEach(function (s) {
        if (s.lat === null || s.lon === null) return;

        const marker = L.marker([s.lat, s.lon]).addTo(map);

        let popupHtml = '<strong>' + (s.name || ('Estação ' + s.id)) + '</strong>';
        if (s.description) {
          popupHtml += '<br>' + s.description;
        }
        popupHtml += '<br>Lat: ' + s.lat + ', Lon: ' + s.lon + '';

        // Links das variáveis -> view.php?id_station=ID&var=VAR
        popupHtml += '<br><strong>Variáveis:</strong> ';

        const links = [];
        for (const key in variables) {
          if (!Object.prototype.hasOwnProperty.call(variables, key)) continue;
          const label = variables[key];
          const url   = '/sapi/view.php?id_station=' + encodeURIComponent(s.id) +
                        '&var=' + encodeURIComponent(key);
          links.push('<a href="' + url + '">' + label + '</a>');
        }

        popupHtml += links.join(' | ') + '';

        marker.bindPopup(popupHtml);
        markers.push(marker);
      });

      // Ajusta o zoom para caber todos os marcadores, se houver mais de um
      if (markers.length > 1) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.2));
      }
    });
    </script>

<?php require_once 'footer.php'; ?>
