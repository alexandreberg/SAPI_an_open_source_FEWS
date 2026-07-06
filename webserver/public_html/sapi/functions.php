<?php

require_once dirname(__DIR__, 2) . '/sapi.php';

function db() {
    static $pdo;
    if (!$pdo) {
        $dsn = 'mysql:host=' . servidor . ';dbname=' . banco . ';charset=' . DB_CHARSET;
        $opts = [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES => false,
        ];
        $pdo = new PDO($dsn, usuario, senhaDB, $opts);
    }
    return $pdo;
}

?>