<?php
require_once __DIR__ . '/security.php';
    $ip_array = explode(" ",shell_exec('hostname -I')) ;
    $os_array = explode("\n", shell_exec('lsb_release -a'));

    $hostname = strtoupper(gethostname()) ;
    $bonjour_name = strtolower($hostname) . ".local";
    $ip_address = $ip_array[0] ;
    $rpi_model = nl2br(shell_exec('cat /proc/device-tree/model')) ;
    $rpi_os = str_replace('Description:','',$os_array[1]) ;
    
    $user_agent = ($_SERVER['HTTP_USER_AGENT'] ?? '');
 
    # details on running usb share processes

    $rebuilding_usb_share = in_array(trim(@file_get_contents('/home/pi/usb_share/flags/rebuilding_usb') ?: ''), ['queued', 'create_image', 'create_fs', 'stop_services'], true) ? 'true' : 'false';
    $anycubic_enabled = file_exists('/home/pi/usb_share/flags/enable_anycubic') ? 'true' : 'false';
    $camera_enabled = file_exists('/home/pi/usb_share/flags/enable_camera') ? 'true' : 'false';

    $rotate = 0;
    if(file_exists('/home/pi/usb_share/flags/rotate_90') ) { $rotate = 90; }
    else if(file_exists('/home/pi/usb_share/flags/rotate_180') ) { $rotate = 180; }
    else if(file_exists('/home/pi/usb_share/flags/rotate_270') ) { $rotate = 270; }

?>
