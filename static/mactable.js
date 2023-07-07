const content = document.getElementById('content');
const source = new EventSource('/stream');
const seenMacs = new Map();
const queue = [];
let processingQueue = false;

async function getVendor(mac) {
    const response = await fetch(`/vendor/${mac}`);
    const data = await response.json();
    return data.vendor;
}

async function processQueue() {
    while (queue.length > 0) {
        const event = queue.shift();
        const [mac, ip] = event.data.split(',');

        if (seenMacs.has(mac)) {
            [prevIP, row] = seenMacs.get(mac);

            if (ip !== '' && ip !== prevIP) {
                const ipCell = row.cells[1];
                ipCell.innerText = ip;
                prevIP = ip;
            }
        } else {
            const row = document.createElement('tr');
            const macCell = document.createElement('td');
            const ipCell = document.createElement('td');
            const vendorCell = document.createElement('td');

            macCell.innerText = mac;
            ipCell.innerText = ip;
            const vendor = await getVendor(mac);
            vendorCell.innerText = vendor; // Use await here to ensure the vendor data is fetched before it's added to the table.

            row.appendChild(macCell);
            row.appendChild(ipCell);
            row.appendChild(vendorCell);

            content.appendChild(row);
            seenMacs.set(mac, [ip, row]);
        }
    }
    sortTable();
    processingQueue = false;
}

source.onmessage = function (event) {
    queue.push(event);
    if (!processingQueue) {
        processingQueue = true;
        processQueue();
    }
};

function sortTable() {
    const rows = Array.from(content.getElementsByTagName('tr'))
        .sort((row1, row2) => row1.cells[0].innerHTML.localeCompare(row2.cells[0].innerHTML));
    content.innerHTML = '';
    rows.forEach((tr) => content.appendChild(tr));
}
