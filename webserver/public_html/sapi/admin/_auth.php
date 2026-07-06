<?php
/**
 * @file _auth.php
 * @brief Session guard — include at the very top of every admin page.
 *
 * Starts the PHP session, checks that the user is authenticated, and
 * initialises a CSRF token.  If not authenticated, redirects to login.
 *
 * Usage (first lines of every admin/*.php):
 * @code
 *   require_once '_auth.php';
 * @endcode
 *
 * @author Alexandre Nuernberg
 */

if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

if (!isset($_SESSION['user_id'])) {
    header('Location: ../login.php');
    exit;
}

// Initialise CSRF token once per session
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

/**
 * @brief Validates the CSRF token submitted with a POST request.
 *
 * Terminates the script with a 403 if the token is missing or invalid.
 *
 * @return void
 */
function validateCsrf(): void
{
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'] ?? '')) {
        http_response_code(403);
        exit('CSRF validation failed.');
    }
}
