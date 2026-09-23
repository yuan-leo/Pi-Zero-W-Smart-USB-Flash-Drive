<?php
function parameter($name, $default = null) {
    $source = ($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST' ? $_POST : $_GET;
    $value = $source[$name] ?? $default;
    if (!is_string($value) || strpos($value, "\0") !== false || strlen($value) > 512) {
        fail_request('Invalid parameter: ' . $name);
    }
    return $value;
}

function action($read_actions) {
    $a = parameter('a');
    if (!in_array($a, $read_actions, true)) require_mutation();
    return $a;
}

function helper($action, $args = []) {
    // PHP 7.3 supports string proc_open only. Every argument is independently quoted.
    $argv = array_merge(['/usr/bin/sudo', '-n', '/usr/local/lib/usb-share/admin.py', $action], $args);
    $command = implode(' ', array_map('escapeshellarg', $argv));
    $process = proc_open($command, [0 => ['file', '/dev/null', 'r'], 1 => ['pipe', 'w'],
                                  2 => ['file', '/dev/null', 'w']], $pipes);
    if (!is_resource($process)) fail_request('Cannot start administrative helper.', 500);
    $output = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    $exit = proc_close($process);
    $result = json_decode($output, true);
    if ($exit !== 0 || !is_array($result) || !empty($result['error'])) {
        fail_request($result['error'] ?? 'Administrative operation failed.', 409);
    }
    return $result;
}

function flag_status($name) {
    return ['status' => trim(@file_get_contents('/home/pi/usb_share/flags/' . $name) ?: 'stopped')];
}

function job_status($job) {
    if (!preg_match('/\A[0-9a-f]{32}\z/', $job)) fail_request('Invalid job ID.');
    $result = @json_decode(@file_get_contents('/run/usb-share/' . $job . '.json'), true);
    if (!is_array($result)) fail_request('Job not found; the Pi may have restarted.', 404);
    return $result;
}

function storage_lock() {
    $handle = fopen('/run/usb-share/storage.lock', 'r+');
    if (!$handle || !flock($handle, LOCK_EX | LOCK_NB)) fail_request('Storage is busy.', 409);
    // Returned resource stays locked until closed or the request exits.
    return $handle;
}

function upload_path($name, $directory = '/home/pi/usb_share/upload') {
    if ($name === '' || $name === '.' || $name === '..' || basename($name) !== $name
        || preg_match('/[\\\\\/\x00-\x1f]/', $name)) fail_request('Invalid filename.');
    $base = realpath($directory);
    if ($base === false || is_link($base . '/' . $name)) fail_request('Invalid upload destination.');
    $path = $base . '/' . $name;
    if (file_exists($path) && (!is_file($path) || dirname(realpath($path)) !== $base)) {
        fail_request('Invalid upload destination.');
    }
    return $path;
}
