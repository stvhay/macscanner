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

async function getSystem(mac) {
    const response = await fetch(`/system/${mac}`);
    const data = await response.json();
    return data.system;
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
            const systemCell = document.createElement('td');

            macCell.innerText = mac;
            ipCell.innerText = ip;
            const vendor = await getVendor(mac);
            vendorCell.innerText = vendor; // Use await here to ensure the vendor data is fetched before it's added to the table.
            const system = await getSystem(mac);
            systemCell.innerText = system; // Use await here to ensure the vendor data is fetched before it's added to the table.

            row.appendChild(macCell);
            row.appendChild(ipCell);
            row.appendChild(vendorCell);
            row.appendChild(systemCell);

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
        .sort((row1, row2) => {
            // Split each IP into its octets
            let ip1 = row1.cells[1].innerHTML.split(".");
            let ip2 = row2.cells[1].innerHTML.split(".");
            
            // Compare each octet
            for (let i = 0; i < 4; i++) {
                let octet1 = Number(ip1[i]);
                let octet2 = Number(ip2[i]);

                if (octet1 > octet2) {
                    return 1;
                } else if (octet1 < octet2) {
                    return -1;
                }
            }

            // If all octets are equal, the IPs are equal
            return 0;
        });
    content.innerHTML = '';
    rows.forEach((tr) => content.appendChild(tr));
}


function pingNetwork() {
    var network = document.getElementById('network').value;
    // Check for valid IPv4 network format
    var pattern = new RegExp('^((\\d{1,3}\\.){3}\\d{1,3})/\\d{1,2}$');
    if (pattern.test(network)) {
        var xhr = new XMLHttpRequest();
        document.getElementById('result').innerText = "Pinging " + network + "...";
        xhr.open("POST", '/ping', true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onload = function () {
            document.getElementById('result').innerText = JSON.parse(this.responseText).message;
        };
        xhr.send(JSON.stringify({"network": network}));
    } else {
        alert("Invalid IPv4 network");
    }
}

function startPublisher() {
    var interface = document.getElementById('interface').value;
    var timeout = document.getElementById('timeout').value;
    
    var xhr = new XMLHttpRequest();
    xhr.open("POST", '/publish', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = function () {
        console.log(this.responseText);
    };
    xhr.send(JSON.stringify({"interface": interface, "timeout": timeout}));
}
