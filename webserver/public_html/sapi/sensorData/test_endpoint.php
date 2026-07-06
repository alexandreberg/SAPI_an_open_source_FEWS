<?php
/**
 * @file test_endpoint.php
 * @brief Testing tool to verify server endpoint is working
 * 
 * Installation path: /home/<HOSTINGER_USER>/public_html/sapi/sensorData/test_endpoint.php
 * Config file path:  /home/<HOSTINGER_USER>/private_configs/sapi/db_config.php
 * 
 * Access via: https://ilha3d.com/sapi/sensorData/test_endpoint.php
 * 
 * @author Alexandre Nuernberg
 * @date 2025-12-29
 * @version 1.0.2
 */

// CRITICAL: Load autoload FIRST, before any class checks
$autoloadPath = __DIR__ . '/vendor/autoload.php';
$autoloadLoaded = false;

if (file_exists($autoloadPath)) {
    require_once $autoloadPath;
    $autoloadLoaded = true;
}

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Endpoint Test - LoRa Gateway</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1000px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }
        .test-section {
            margin: 30px 0;
            padding: 20px;
            background: #f9f9f9;
            border-left: 4px solid #2196F3;
            border-radius: 5px;
        }
        .success {
            color: #4CAF50;
            font-weight: bold;
        }
        .error {
            color: #f44336;
            font-weight: bold;
        }
        .info {
            color: #2196F3;
        }
        button {
            background: #4CAF50;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 5px;
        }
        button:hover {
            background: #45a049;
        }
        button.secondary {
            background: #2196F3;
        }
        button.secondary:hover {
            background: #0b7dda;
        }
        pre {
            background: #263238;
            color: #aed581;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 13px;
        }
        .status-box {
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .status-box.success {
            background: #e8f5e9;
            border: 1px solid #4CAF50;
        }
        .status-box.error {
            background: #ffebee;
            border: 1px solid #f44336;
        }
        .status-box.info {
            background: #e3f2fd;
            border: 1px solid #2196F3;
        }
        .status-box.warning {
            background: #fff3e0;
            border: 1px solid #ff9800;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #4CAF50;
            color: white;
        }
        tr:hover {
            background: #f5f5f5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 LoRa Gateway Endpoint Test Suite</h1>
        
        <?php
        // Check autoload
        if (!$autoloadLoaded) {
            echo '<div class="status-box error">';
            echo '<strong>❌ CRITICAL ERROR:</strong> Composer autoload not found!<br>';
            echo 'Expected location: <code>' . htmlspecialchars($autoloadPath) . '</code><br>';
            echo '<br><strong>Action required:</strong>';
            echo '<ol>';
            echo '<li>Run: <code>cd ~/public_html/sapi/sensorData && composer install</code></li>';
            echo '<li>Verify vendor/ directory exists</li>';
            echo '</ol>';
            echo '</div>';
        }
        
        // Define config path for your Hostinger account
        $configPath = '/home/<HOSTINGER_USER>/private_configs/sapi/db_config.php';
        
        // Check if config file exists
        if (!file_exists($configPath)) {
            echo '<div class="status-box error">';
            echo '<strong>❌ CRITICAL ERROR:</strong> db_config.php not found!<br>';
            echo 'Expected location: <code>' . htmlspecialchars($configPath) . '</code><br>';
            echo '<br><strong>Action required:</strong>';
            echo '<ol>';
            echo '<li>Create directory: <code>mkdir -p /home/<HOSTINGER_USER>/private_configs/sapi/</code></li>';
            echo '<li>Upload db_config.php to that directory</li>';
            echo '<li>Set permissions: <code>chmod 600 ' . htmlspecialchars($configPath) . '</code></li>';
            echo '</ol>';
            echo '</div>';
            die();
        }
        
        // Include configuration
        require_once $configPath;
        
        // Security check - verify config is outside public_html
        if (strpos($configPath, 'public_html') !== false || strpos($configPath, 'www') !== false) {
            echo '<div class="status-box error">';
            echo '<strong>⚠️ SECURITY WARNING:</strong> db_config.php is inside public directory!<br>';
            echo 'Current location: <code>' . htmlspecialchars($configPath) . '</code><br>';
            echo '<strong>Action required:</strong> Move to /home/<HOSTINGER_USER>/private_configs/sapi/<br>';
            echo '</div>';
        } else {
            echo '<div class="status-box success">';
            echo '<strong>✅ Security Check:</strong> db_config.php is outside public directory<br>';
            echo 'Location: <code>' . htmlspecialchars($configPath) . '</code>';
            echo '</div>';
        }
        
        // Test flags
        $testsRun = false;
        
        // Run tests if requested
        if (isset($_GET['action'])) {
            $testsRun = true;
            $action = $_GET['action'];
            
            echo '<div class="test-section">';
            echo '<h2>Test Results</h2>';
            
            switch ($action) {
                case 'db_connection':
                    testDatabaseConnection();
                    break;
                case 'api_key':
                    testApiKey();
                    break;
                case 'recent_data':
                    showRecentData();
                    break;
                case 'full_test':
                    runFullTest();
                    break;
            }
            
            echo '</div>';
        }
        ?>
        
        <?php if (!$testsRun): ?>
        <div class="status-box info">
            <strong>ℹ️ Information:</strong> This tool helps verify that your server is properly configured to receive data from ESP32 gateways.
        </div>
        <?php endif; ?>
        
        <div class="test-section">
            <h2>Available Tests</h2>
            
            <button onclick="location.href='?action=db_connection'">
                Test Database Connection
            </button>
            
            <button onclick="location.href='?action=api_key'" class="secondary">
                Verify API Key
            </button>
            
            <button onclick="location.href='?action=recent_data'">
                Show Recent Data
            </button>
            
            <button onclick="location.href='?action=full_test'" class="secondary">
                Run Full Test Suite
            </button>
        </div>
        
        <div class="test-section">
            <h2>Server Information</h2>
            <table>
                <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>PHP Version</td>
                    <td><?php echo phpversion(); ?></td>
                </tr>
                <tr>
                    <td>Server Software</td>
                    <td><?php echo $_SERVER['SERVER_SOFTWARE'] ?? 'Unknown'; ?></td>
                </tr>
                <tr>
                    <td>Autoload Loaded</td>
                    <td><?php echo $autoloadLoaded ? '✅ Yes' : '❌ No'; ?></td>
                </tr>
                <tr>
                    <td>MessagePack Class</td>
                    <td><?php 
                        // Check multiple possible class names
                        $msgpackFound = false;
                        $possibleClasses = [
                            'MessagePack\\MessagePack',
                            'MessagePack\\Packer',
                            'MessagePack\\BufferUnpacker'
                        ];
                        
                        foreach ($possibleClasses as $className) {
                            if (class_exists($className)) {
                                echo '✅ Yes (' . $className . ')';
                                $msgpackFound = true;
                                break;
                            }
                        }
                        
                        if (!$msgpackFound) {
                            echo '❌ No (run: composer install)';
                        }
                    ?></td>
                </tr>
                <tr>
                    <td>Database Host</td>
                    <td><?php echo DB_HOST; ?></td>
                </tr>
                <tr>
                    <td>Database Name</td>
                    <td><?php echo DB_NAME; ?></td>
                </tr>
                <tr>
                    <td>Config File Path</td>
                    <td><code><?php echo $configPath; ?></code></td>
                </tr>
                <tr>
                    <td>Endpoint URL</td>
                    <td><?php echo 'https://' . $_SERVER['HTTP_HOST'] . dirname($_SERVER['PHP_SELF']) . '/receive-data.php'; ?></td>
                </tr>
            </table>
        </div>
        
        <div class="test-section">
            <h2>ESP32 Configuration</h2>
            <p>Use these values in your <code>credentials.h</code> file:</p>
            <pre>
const char* serverName = "<?php echo 'https://' . $_SERVER['HTTP_HOST'] . dirname($_SERVER['PHP_SELF']) . '/receive-data.php'; ?>";
String apiKey = "<?php echo substr($VALID_API_KEY, 0, 3) . '...' . substr($VALID_API_KEY, -3); ?>"; // Your full API key
            </pre>
        </div>
    </div>
</body>
</html>

<?php
/**
 * Test database connection
 */
function testDatabaseConnection() {
    echo '<h3>Database Connection Test</h3>';
    
    try {
        $pdo = getDatabaseConnection();
        echo '<div class="status-box success">';
        echo '<strong>✅ Success!</strong> Database connection established.';
        echo '</div>';
        
        // Test query
        $stmt = $pdo->query('SELECT COUNT(*) as count FROM measurements');
        $result = $stmt->fetch();
        
        echo '<p class="info">Total measurements in database: <strong>' . number_format($result['count']) . '</strong></p>';
        
        // Check tables
        $stmt = $pdo->query('SHOW TABLES');
        $tables = $stmt->fetchAll(PDO::FETCH_COLUMN);
        
        echo '<p class="info">Available tables:</p>';
        echo '<ul>';
        foreach ($tables as $table) {
            echo '<li>' . htmlspecialchars($table) . '</li>';
        }
        echo '</ul>';
        
    } catch (Exception $e) {
        echo '<div class="status-box error">';
        echo '<strong>❌ Error!</strong> ' . htmlspecialchars($e->getMessage());
        echo '</div>';
        echo '<p>Check your <code>db_config.php</code> settings.</p>';
    }
}

/**
 * Test API key configuration
 */
function testApiKey() {
    global $VALID_API_KEY;
    
    echo '<h3>API Key Verification</h3>';
    
    if (empty($VALID_API_KEY) || $VALID_API_KEY === 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX') {
        echo '<div class="status-box error">';
        echo '<strong>❌ Error!</strong> API key not configured properly.';
        echo '</div>';
        echo '<p>Please edit <code>db_config.php</code> and set a valid API key.</p>';
        echo '<p>Generate one with: <code>openssl rand -hex 32</code></p>';
    } else {
        echo '<div class="status-box success">';
        echo '<strong>✅ Success!</strong> API key is configured.';
        echo '</div>';
        echo '<p class="info">Key length: ' . strlen($VALID_API_KEY) . ' characters</p>';
        echo '<p class="info">Key preview: ' . substr($VALID_API_KEY, 0, 3) . '...' . substr($VALID_API_KEY, -3) . '</p>';
        echo '<p><strong>⚠️ Warning:</strong> Never share your complete API key publicly!</p>';
    }
}

/**
 * Show recent data
 */
function showRecentData() {
    echo '<h3>Recent Measurements</h3>';
    
    try {
        $pdo = getDatabaseConnection();
        
        $stmt = $pdo->query('
            SELECT m.*, s.name as station_name 
            FROM measurements m
            LEFT JOIN stations s ON m.id_station = s.id
            ORDER BY m.timestamp DESC 
            LIMIT 20
        ');
        
        $results = $stmt->fetchAll();
        
        if (empty($results)) {
            echo '<div class="status-box info">';
            echo '<strong>ℹ️ Info:</strong> No measurements found in database.';
            echo '</div>';
            return;
        }
        
        echo '<div class="status-box success">';
        echo '<strong>✅ Found ' . count($results) . ' recent measurements</strong>';
        echo '</div>';
        
        echo '<div style="overflow-x: auto;">';
        echo '<table>';
        echo '<tr>';
        echo '<th>ID</th>';
        echo '<th>Station</th>';
        echo '<th>Timestamp</th>';
        echo '<th>Level (cm)</th>';
        echo '<th>Temp (°C)</th>';
        echo '<th>Battery (V)</th>';
        echo '<th>RSSI</th>';
        echo '</tr>';
        
        foreach ($results as $row) {
            echo '<tr>';
            echo '<td>' . $row['id'] . '</td>';
            echo '<td>' . ($row['station_name'] ?? 'Station ' . $row['id_station']) . '</td>';
            echo '<td>' . $row['timestamp'] . '</td>';
            echo '<td>' . ($row['level_cm'] ?? '-') . '</td>';
            echo '<td>' . ($row['temperature_C'] ?? '-') . '</td>';
            echo '<td>' . ($row['bat_voltage'] ?? '-') . '</td>';
            echo '<td>' . ($row['rssi'] ?? '-') . '</td>';
            echo '</tr>';
        }
        
        echo '</table>';
        echo '</div>';
        
    } catch (Exception $e) {
        echo '<div class="status-box error">';
        echo '<strong>❌ Error!</strong> ' . htmlspecialchars($e->getMessage());
        echo '</div>';
    }
}

/**
 * Run full test suite
 */
function runFullTest() {
    echo '<h3>Full Test Suite</h3>';
    
    // Check for multiple possible MessagePack class names
    $msgpackAvailable = false;
    $possibleClasses = [
        'MessagePack\\MessagePack',
        'MessagePack\\Packer',
        'MessagePack\\BufferUnpacker'
    ];
    
    foreach ($possibleClasses as $className) {
        if (class_exists($className)) {
            $msgpackAvailable = true;
            break;
        }
    }
    
    $tests = [
        'PHP Version >= 7.2' => version_compare(PHP_VERSION, '7.2.0', '>='),
        'MessagePack Extension' => $msgpackAvailable,
        'PDO Extension' => extension_loaded('pdo'),
        'PDO MySQL Driver' => extension_loaded('pdo_mysql'),
        'OpenSSL Extension' => extension_loaded('openssl'),
        'MBString Extension' => extension_loaded('mbstring'),
    ];
    
    $allPassed = true;
    
    echo '<table>';
    echo '<tr><th>Test</th><th>Result</th></tr>';
    
    foreach ($tests as $test => $result) {
        echo '<tr>';
        echo '<td>' . $test . '</td>';
        echo '<td>' . ($result ? '✅ Pass' : '❌ Fail') . '</td>';
        echo '</tr>';
        
        if (!$result) {
            $allPassed = false;
        }
    }
    
    echo '</table>';
    
    if ($allPassed) {
        echo '<div class="status-box success">';
        echo '<strong>✅ All tests passed!</strong> Server is ready to receive data.';
        echo '</div>';
    } else {
        echo '<div class="status-box error">';
        echo '<strong>❌ Some tests failed.</strong> Please fix the issues before deploying.';
        echo '</div>';
    }
    
    // Test database
    echo '<hr>';
    testDatabaseConnection();
    
    // Test API key
    echo '<hr>';
    testApiKey();
}
?>