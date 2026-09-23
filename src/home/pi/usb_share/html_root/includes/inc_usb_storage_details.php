<?php
require_once __DIR__ . '/security.php';
$upload_str = '/home/pi/usb_share/upload/';
$disk_size_bytes = filesize('/home/pi/usb_share/usb_share_disk.img');
$disk_size = round($disk_size_bytes / 1048576, 2);
$disk_size_gb = round($disk_size_bytes / 1073741824, 2);
$disk_free = round(disk_free_space($upload_str) / 1048576, 2);
$disk_used = round(disk_total_space($upload_str) / 1048576 - $disk_free, 2);
$avail_disk_space = disk_free_space('/home/pi/usb_share') / 1073741824;
$max_usb_share = max(0, floor($avail_disk_space) - 2);
