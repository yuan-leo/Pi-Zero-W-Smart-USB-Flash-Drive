<?php
require_once __DIR__ . '/api.php';
$a = action(['disk_stats', 'file_list', 'usb_reset_status', 'upgrade_status']);
$upload = '/home/pi/usb_share/upload/';
switch ($a) {
case 'disk_stats':
    $size = filesize('/home/pi/usb_share/usb_share_disk.img');
    $free = disk_free_space($upload);
    $total = disk_total_space($upload);
    $available = disk_free_space('/home/pi/usb_share');
    $data = ['disk_size' => round($size / 1048576, 2),
             'disk_used' => round(($total - $free) / 1048576, 2),
             'disk_free' => round($free / 1048576, 2),
             'disk_available' => round($available / 1073741824, 2),
             'max_usb_share' => max(0, floor($available / 1073741824) - 2)];
    break;
case 'file_list':
    $files = glob($upload . '*');
    natcasesort($files);
    $list = [];
    foreach ($files as $file) {
        if (!is_file($file) || is_link($file)) continue;
        $list[] = ['name' => basename($file), 'size' => number_format(filesize($file) / 1048576, 2),
                   'modified' => date('F d, Y H:i:s', filemtime($file))];
    }
    $data = ['file_list' => $list];
    break;
case 'delete_file':
    $lock = storage_lock();
    $path = upload_path(parameter('file'));
    if (!is_file($path) || !unlink($path)) fail_request('File could not be deleted.', 409);
    $data = ['status' => 'deleted'];
    break;
case 'usb_reset': case 'usb_unplug':
    $data = helper($a);
    break;
case 'usb_reset_status':
    $data = flag_status('usb_reset_status');
    break;
case 'upgrade':
    $data = helper('upgrade');
    break;
case 'upgrade_status':
    $data = job_status(parameter('job_id'));
    break;
default: fail_request('Unknown action.');
}
echo json_encode($data);
