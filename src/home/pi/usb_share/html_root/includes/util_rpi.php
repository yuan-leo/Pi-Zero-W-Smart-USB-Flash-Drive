<?php
require_once __DIR__ . '/api.php';
$request_type = action(['host_info', 'update_status', 'reboot_status', 'rebuild_status', 'get_disk_size']);
$data = array();
$data['date_run']  = date("Y-m-d H:i:s",time()) ;

if ($request_type === '') {
    $data['error']  = "no attributes provided." ;
}
else {


    $data['error']  = "" ;

    #
    # get usb share siize data
    # 

    if($request_type == 'host_info') {

        $ip_array = explode(" ",shell_exec('hostname -I')) ;
        $ip_address = $ip_array[0] ;
        
        $data['hostname'] = strtoupper(gethostname()) ;
        $data['ip_address']  = $ip_address ;

        $data['rpi_model'] = nl2br(shell_exec('cat /proc/device-tree/model'));

        $os_array = explode("\n", shell_exec('lsb_release -a'));
        $data['rpi_os'] = str_replace('Description:','',$os_array[1]);

        $data['http_user_agent'] = ($_SERVER['HTTP_USER_AGENT'] ?? '');

        # details on running usb share processes

        $data['rebuilding_usb_share'] = in_array(trim(@file_get_contents('/home/pi/usb_share/flags/rebuilding_usb') ?: ''), ['queued', 'create_image', 'create_fs', 'stop_services'], true) ? 'true' : 'false';
        $data['anycubic_enabled'] = file_exists('/home/pi/usb_share/flags/enable_anycubic') ? 'true' : 'false';
        $data['camera_enabled'] = file_exists('/home/pi/usb_share/flags/enable_camera') ? 'true' : 'false';

        $rotate = 0;
        if(file_exists('/home/pi/usb_share/flags/rotate_90') ) { $rotate = 90; }
        else if(file_exists('/home/pi/usb_share/flags/rotate_180') ) { $rotate = 180; }
        else if(file_exists('/home/pi/usb_share/flags/rotate_270') ) { $rotate = 270; }
        $data['camera_rotation'] = $rotate;

    } else if ($request_type == 'network_scan') {
        $ip_array = explode(" ",shell_exec('hostname -I')) ;
        $ip_address = $ip_array[0] ;
        $mac_address = shell_exec('cat /sys/class/net/wlan0/address ');

        $array_list = explode("\n", helper('network_scan')['status']);
        $devices = [];
        foreach ($array_list as $line) {
            $fields = preg_split('/\t+/', trim($line));
            if (count($fields) < 3 || !filter_var($fields[0], FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)
                || strpos($fields[2], '(DUP:') !== false) continue;
            $devices[$fields[0]] = ['IP' => $fields[0], 'MAC Address' => $fields[1],
                                   'Vendor' => str_replace('(Unknown)', '', $fields[2])];
        }
        if (filter_var(trim($ip_address), FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
            $devices[trim($ip_address)] = ['IP' => trim($ip_address), 'MAC Address' => trim($mac_address),
                                         'Vendor' => 'Raspberry Pi Foundation'];
        }
        uksort($devices, function ($a, $b) { return ip2long($a) <=> ip2long($b); });
        $data['device_list'] = array_values($devices);

    } else if ($request_type == 'update') {
      $data = helper('update_rpi', [parameter('current_hostname'), parameter('new_hostname'),
                                  parameter('enable_camera'), parameter('rotation')]);
    } else if ($request_type == 'update_status' || $request_type == 'reboot_status') {
      $data = flag_status('updating_rpi');
    } else if ($request_type == 'rebuild_usb') {
      $data = helper('rebuild', [parameter('usb_size')]);
    } else if ($request_type == 'rebuild_status') {
      $data = flag_status('rebuilding_usb');
    } else if ($request_type == 'get_disk_size') {
      $data = ['disk_size' => floor(filesize('/home/pi/usb_share/usb_share_disk.img') / 1048576)];
    } else if ($request_type == 'reboot' || $request_type == 'shutdown') {
      $data = helper($request_type);
    } else {
      fail_request('Unknown action.');
    }

    
}

#
# return the results as a json string
#
    
echo json_encode($data);


?>
