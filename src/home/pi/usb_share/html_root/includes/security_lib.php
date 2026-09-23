<?php
// This file is also required by every page, not just the JSON endpoints.
function fail_request($message, $status = 400) {
    http_response_code($status);
    header('Content-Type: application/json');
    echo json_encode(['error' => $message]);
    exit;
}

function authenticate($config_path = '/etc/usb-share/auth.json') {
    $config = @json_decode(@file_get_contents($config_path), true);
    if (!is_array($config) || empty($config['username']) || empty($config['password_hash'])) {
        fail_request('Portal access is disabled until an administrator configures a password.', 503);
    }
    if (empty($config['allow_http']) && (empty($_SERVER['HTTPS']) || $_SERVER['HTTPS'] === 'off')) {
        fail_request('HTTPS is required to protect portal credentials.', 426);
    }
    $user = $_SERVER['PHP_AUTH_USER'] ?? '';
    $password = $_SERVER['PHP_AUTH_PW'] ?? '';
    if (!hash_equals($config['username'], $user) || !password_verify($password, $config['password_hash'])) {
        header('WWW-Authenticate: Basic realm="USB Share", charset="UTF-8"');
        fail_request('Authentication required.', 401);
    }
    session_start(['use_strict_mode' => 1, 'cookie_httponly' => true,
                   'cookie_secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off',
                   'cookie_samesite' => 'Strict']);
    if (empty($_SESSION['csrf'])) {
        session_regenerate_id(true);
        $_SESSION['csrf'] = bin2hex(random_bytes(32));
    }
    $GLOBALS['csrf_token'] = $_SESSION['csrf'];
    session_write_close(); // Slow printer requests must not hold the session lock.
    header('Cache-Control: no-store');
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
}

function require_mutation() {
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
        header('Allow: POST');
        fail_request('Use POST for this action.', 405);
    }
    $token = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? ($_POST['csrf_token'] ?? '');
    if (!is_string($token) || !hash_equals($GLOBALS['csrf_token'], $token)) {
        fail_request('Invalid CSRF token.', 403);
    }
}

