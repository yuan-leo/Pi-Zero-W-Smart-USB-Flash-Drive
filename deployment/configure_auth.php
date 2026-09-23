#!/usr/bin/php
<?php
if (PHP_SAPI !== 'cli' || posix_geteuid() !== 0) exit("Run this command as root.\n");
$username = trim(readline('Portal username: '));
if (!preg_match('/\A[a-zA-Z0-9_.-]{1,64}\z/', $username)) exit("Invalid username.\n");
system('stty -echo');
try {
    $password = readline('Portal password (at least 12 characters): ');
    echo "\n";
    $confirm = readline('Repeat password: ');
    echo "\n";
} finally {
    system('stty echo');
}
if (strlen($password) < 12 || !hash_equals($password, $confirm)) exit("Passwords do not match or are too short.\n");
$data = ['username' => $username, 'password_hash' => password_hash($password, PASSWORD_DEFAULT),
         'allow_http' => false];
$temp = tempnam('/etc/usb-share', '.auth-');
file_put_contents($temp, json_encode($data) . "\n");
chown($temp, 'root');
chgrp($temp, 'www-data');
chmod($temp, 0640);
rename($temp, '/etc/usb-share/auth.json');
echo "Password saved. HTTPS is required.\n";
