<?php
/**
 * @file logout.php
 * @brief Destroys the admin session and redirects to login.
 *
 * @author Alexandre Nuernberg
 */

session_start();
session_destroy();
header('Location: login.php');
exit;
