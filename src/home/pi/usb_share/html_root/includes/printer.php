<?php
function printer_snapshot() {
    $cache_path = '/var/cache/usb-share/printer.json';
    $lock = fopen('/var/cache/usb-share/printer.lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX)) throw new RuntimeException('Printer cache unavailable');
    clearstatcache(true, $cache_path);
    $data = @json_decode(@file_get_contents($cache_path), true);
    if (!is_array($data) || time() - (@filemtime($cache_path) ?: 0) >= 3) {
        $output = shell_exec('/usr/bin/python3 -E -s /usr/local/lib/usb-share/anycubic_status.py');
        $data = json_decode($output, true);
        if (!is_array($data)) $data = ['connection' => 'Not Connected', 'ip_address' => '',
            'printer_model' => '', 'printer_status' => '', 'files' => '', 'print_job' => '',
            'layers_complete' => '', 'percent_complete' => '', 'seconds_remaining' => 0, 'resin_required' => ''];
        file_put_contents($cache_path, json_encode($data));
    }
    flock($lock, LOCK_UN);
    fclose($lock);
    return $data;
}
