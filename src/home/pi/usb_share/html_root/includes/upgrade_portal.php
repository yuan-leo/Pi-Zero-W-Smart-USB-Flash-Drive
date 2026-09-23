<?php require_once __DIR__ . '/security.php'; ?>
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="csrf-token" content="<?php echo htmlspecialchars($GLOBALS['csrf_token'], ENT_QUOTES); ?>">
<title>Upgrade USB Share</title><link rel="stylesheet" href="/css/bootstrap.min.css"></head>
<body class="container py-4"><h1>Upgrade USB Share</h1>
<p id="status">Ready to install the release configured by your administrator.</p>
<button id="start" class="btn btn-primary">Install configured release</button>
<a href="/settings.php">Back to settings</a>
<script src="/js/usb_share_functions.js"></script>
<script>
const statusLabel = document.getElementById('status');
const startButton = document.getElementById('start');
let job = sessionStorage.getItem('upgradeJob');
async function request(action, args = {}, mutate = false) {
    const params = new URLSearchParams(Object.assign({a: action}, args));
    const options = mutate ? {method: 'POST', headers: {
        'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]').content,
        'Content-Type': 'application/x-www-form-urlencoded'}, body: params.toString()} : {};
    const response = await fetch('/includes/util_usb_share.php' + (mutate ? '' : '?' + params), options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Upgrade request failed');
    return data;
}
async function poll() {
    try {
        const data = await request('upgrade_status', {job_id: job});
        statusLabel.textContent = data.error || data.status;
        if (data.status === 'complete' || data.status === 'error') {
            sessionStorage.removeItem('upgradeJob');
            startButton.disabled = false;
        } else setTimeout(poll, 3000);
    } catch (error) {
        statusLabel.textContent = error.message + '. Reload to resume checking this job.';
    }
}
startButton.addEventListener('click', async function () {
    startButton.disabled = true;
    try {
        const data = await request('upgrade', {}, true);
        job = data.job_id;
        sessionStorage.setItem('upgradeJob', job);
        poll();
    } catch (error) {
        statusLabel.textContent = error.message;
        startButton.disabled = false;
    }
});
if (job) { startButton.disabled = true; poll(); }
</script></body></html>
