<?php
require_once __DIR__ . '/includes/security.php';
// Fixed loopback destination; no user-controlled proxy URLs or camera commands.
$context = stream_context_create(['http' => ['timeout' => 3, 'follow_location' => 0]]);
$stream = @fopen('http://127.0.0.1:8080/?action=stream', 'rb', false, $context);
if (!$stream) fail_request('Camera unavailable.', 503);
$type = '';
foreach ($http_response_header ?? [] as $line) {
    if (preg_match('/^Content-Type:\s*(multipart\/x-mixed-replace;\s*boundary=[A-Za-z0-9_-]+)\s*$/i', $line, $match)) {
        $type = $match[1];
    }
}
if (!$type) { fclose($stream); fail_request('Invalid camera response.', 502); }
header('Content-Type: ' . $type);
header('X-Accel-Buffering: no');
while (ob_get_level() > 0) ob_end_clean();
$deadline = microtime(true) + 28;
while (!feof($stream) && !connection_aborted() && microtime(true) < $deadline) {
    $chunk = fread($stream, 8192);
    if ($chunk === false || $chunk === '') break;
    echo $chunk;
    flush();
}
fclose($stream);
