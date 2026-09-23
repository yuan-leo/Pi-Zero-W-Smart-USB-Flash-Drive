<?php
// Each rejection exits, so exercise the production functions in isolated children.
$root = dirname(__DIR__) . '/src/home/pi/usb_share/html_root/includes';
if (isset($argv[1])) {
    require $root . '/security_lib.php';
    require $root . '/api_helpers.php';
    register_shutdown_function(function () { echo "\nSTATUS=" . (http_response_code() ?: 200); });
    $case = $argv[1];
    if (strpos($case, 'auth_') === 0) {
        $_SERVER['HTTPS'] = 'on';
        $_SERVER['PHP_AUTH_USER'] = 'admin';
        $_SERVER['PHP_AUTH_PW'] = $case === 'auth_bad' ? 'incorrect' : 'a-long-test-password';
        if ($case === 'auth_http') $_SERVER['HTTPS'] = 'off';
        authenticate($case === 'auth_missing' ? $argv[2] . '/missing' : $argv[2] . '/auth.json');
        echo 'authenticated';
    } elseif ($case === 'get_mutation' || $case === 'bad_csrf' || $case === 'valid_csrf') {
        $GLOBALS['csrf_token'] = 'correct';
        $_SERVER['REQUEST_METHOD'] = $case === 'get_mutation' ? 'GET' : 'POST';
        $_SERVER['HTTP_X_CSRF_TOKEN'] = $case === 'valid_csrf' ? 'correct' : 'wrong';
        require_mutation();
        echo 'accepted';
    } elseif ($case === 'path') {
        echo upload_path($argv[3], $argv[2]);
    } elseif ($case === 'parameter_array') {
        $_GET['file'] = ['bad'];
        parameter('file');
    }
    exit;
}
$temp = sys_get_temp_dir() . '/usb-share-test-' . bin2hex(random_bytes(8));
mkdir($temp, 0700);
file_put_contents($temp . '/auth.json', json_encode(['username' => 'admin',
    'password_hash' => password_hash('a-long-test-password', PASSWORD_DEFAULT)]));
$cases = [['auth_good', 200], ['auth_bad', 401], ['auth_missing', 503], ['auth_http', 426],
          ['get_mutation', 405], ['bad_csrf', 403], ['valid_csrf', 200], ['parameter_array', 400],
          ['path', 400, '../outside'], ['path', 400, '/absolute'], ['path', 400, '..\\outside'],
          ['path', 400, '.'], ['path', 200, "O'Brien.pwmx"], ['path', 200, 'UPPERCASE.pwmx']];
$failed = 0;
try {
    foreach ($cases as $case) {
        $args = [PHP_BINARY, __FILE__, $case[0], $temp, $case[2] ?? ''];
        // Array form is available on modern CI/local PHP; production remains PHP 7.3 compatible.
        $process = proc_open($args, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
        $output = stream_get_contents($pipes[1]);
        $errors = stream_get_contents($pipes[2]);
        fclose($pipes[1]); fclose($pipes[2]);
        $exit = proc_close($process);
        if ($exit !== 0 || strpos($output, 'STATUS=' . $case[1]) === false || $errors !== '') {
            fwrite(STDERR, 'FAIL ' . json_encode($case) . ': ' . $output . $errors . "\n");
            $failed++;
        }
    }
} finally {
    unlink($temp . '/auth.json');
    rmdir($temp);
}
echo count($cases) . ' PHP security cases; ' . $failed . " failures\n";
exit($failed ? 1 : 0);
