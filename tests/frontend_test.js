const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const location = {origin: 'https://printer.local'};
const context = {URL, window: {location}, location,
    document: {querySelector: () => ({content: 'test-token'})}, alert: () => {}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('src/home/pi/usb_share/html_root/js/usb_share_functions.js', 'utf8'), context);
function xhr() {
    return {headers: {}, timeout: 3000,
        open(method, url, async) { Object.assign(this, {method, url, async}); },
        setRequestHeader(name, value) { this.headers[name] = value; },
        addEventListener() {}, send(body) { this.body = body; }};
}
let request = xhr();
context.openApiRequest(request, '/includes/util_usb_share.php?a=disk_stats');
context.sendApiRequest(request);
assert.equal(request.method, 'GET');
assert.equal(request.body, null);
request = xhr();
const filename = "O'Brien & UPPERCASE.pwmx";
context.openApiRequest(request, '/includes/util_usb_share.php?' + new URLSearchParams({a: 'delete_file', file: filename}));
context.sendApiRequest(request);
assert.equal(request.method, 'POST');
assert.equal(request.url, '/includes/util_usb_share.php');
assert.equal(request.headers['X-CSRF-Token'], 'test-token');
assert.equal(new URLSearchParams(request.body).get('file'), filename);
assert.equal(request.async, true);
assert.ok(request.timeout >= 15000);
assert.throws(() => context.openApiRequest(xhr(), 'https://attacker.invalid/includes/util_rpi.php?a=reboot'));
console.log('Frontend GET/POST, CSRF, filename encoding and origin checks passed');
