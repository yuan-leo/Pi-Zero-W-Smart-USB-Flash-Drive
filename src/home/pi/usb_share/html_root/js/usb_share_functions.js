function updateElement(id,val) {
    var element_id = id;
    var new_content = val;
    document.getElementById(element_id).textContent = new_content;
}

function showElement(element_id) {
    $e = document.getElementById(element_id);
    $e.classList.remove("hidden");
    $e.classList.add("show");
}

function hideElement(element_id) {
    $e = document.getElementById(element_id);
    $e.classList.remove("show");
    $e.classList.add("hidden");
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
// Keep GET for reads; put every administrative mutation in a CSRF-checked POST body.
function openApiRequest(req, address) {
    const url = new URL(address, window.location.origin);
    const reads = {
        '/includes/util_rpi.php': ['host_info', 'update_status', 'reboot_status', 'rebuild_status', 'get_disk_size'],
        '/includes/util_usb_share.php': ['disk_stats', 'file_list', 'usb_reset_status', 'upgrade_status'],
        '/includes/util_anycubic.php': ['printer_status']
    };
    if (url.origin !== location.origin || !reads[url.pathname]) throw new Error('Invalid API URL');
    const read = reads[url.pathname].includes(url.searchParams.get('a'));
    req.open(read ? 'GET' : 'POST', read ? url.href : url.pathname, true);
    req.printerRequest = url.pathname === '/includes/util_anycubic.php' && read;
    if (!read) {
        req.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
        req.setRequestHeader('X-CSRF-Token', document.querySelector('meta[name="csrf-token"]').content);
        req.apiBody = url.searchParams.toString();
    }
    req.addEventListener('load', function () {
        if (req.status >= 400) {
            let message = 'Request failed (' + req.status + ')';
            try { message = JSON.parse(req.responseText).error || message; } catch (_) {}
            if (!read) alert(message);
        }
    });
}
function sendApiRequest(req) {
    if (req.apiBody) req.timeout = Math.max(req.timeout, 15000);
    if (req.printerRequest) req.timeout = Math.max(req.timeout, 10000);
    req.send(req.apiBody || null);
}
