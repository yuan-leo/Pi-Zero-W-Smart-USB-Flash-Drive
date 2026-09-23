<?php
require_once __DIR__ . '/api.php';
require_once __DIR__ . '/printer.php';
$a = action(['printer_status']);
if ($a === 'printer_status') {
    $p = printer_snapshot();
    $flags = '/home/pi/usb_share/flags/';
    $data = ['anycubic_enabled' => file_exists($flags . 'enable_anycubic') ? 'true' : 'false',
             'wifi_enabled' => file_exists($flags . 'enable_wifi_file') ? 'true' : 'false',
             'protection_enabled' => !file_exists($flags . 'disable_print_protection'),
             'printer_ip_address' => $p['ip_address'] ?? '',
             'printer_model' => $p['printer_model'] ?? '',
             'printer_connection' => $p['connection'] ?? 'Not Connected',
             'printer_status' => $p['printer_status'] ?? '',
             'printer_files' => preg_replace('/^(getfiles?,)|,end,?$/', '', $p['files'] ?? ''),
             'print_job_name' => explode('/', $p['print_job'] ?? '')[0]];
    foreach (['layers_complete', 'percent_complete', 'seconds_remaining', 'resin_required'] as $key) {
        $data[$key] = $p[$key] ?? '';
    }
} elseif ($a === 'enable_anycubic' || $a === 'disable_anycubic') {
    $data = helper($a);
} elseif ($a === 'update') {
    $data = helper('update_anycubic', [parameter('printer_ip'), parameter('printer_model'),
                   parameter('enable_wifi_file'), parameter('enable_print_protection')]);
} elseif ($a === 'anycubic_action') {
    $data = helper($a, [parameter('cmd')]);
} else {
    fail_request('Unknown action.');
}
if ($a !== 'printer_status') @unlink('/var/cache/usb-share/printer.json');
echo json_encode($data);
