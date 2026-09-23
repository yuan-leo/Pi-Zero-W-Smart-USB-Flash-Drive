<?php
require_once __DIR__ . '/api.php';
require_mutation();
$file = $_FILES['file'] ?? null;
if (!is_array($file) || ($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK
    || !is_string($file['name']) || !is_uploaded_file($file['tmp_name'])) {
    fail_request('Upload failed or exceeded the configured size limit.');
}
$lock = storage_lock();
$path = upload_path($file['name']);
if (file_exists($path)) fail_request('A file with that name already exists.', 409);
if (filesize($file['tmp_name']) > disk_free_space(dirname($path)) - 1048576) {
    fail_request('Insufficient USB storage.', 413);
}
$destination = @fopen($path, 'x+b'); // Atomic reservation also rejects symlink replacement races.
if (!$destination) fail_request('The destination already exists or is not writable.', 409);
$source = fopen($file['tmp_name'], 'rb');
$copied = $source ? stream_copy_to_stream($source, $destination) : false;
if ($source) fclose($source);
$flushed = fflush($destination);
fclose($destination);
if ($copied === false || $copied !== filesize($file['tmp_name']) || !$flushed) {
    @unlink($path);
    fail_request('Could not store the complete upload.', 500);
}
echo json_encode(['status' => 'uploaded']);
