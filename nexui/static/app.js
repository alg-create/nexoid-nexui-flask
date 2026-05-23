// Connect to Socket.IO Server
const socket = io();

// UI Elements
const statusDot = document.getElementById('connection-dot');
const statusText = document.getElementById('connection-status');
const btnStartTransaction = document.getElementById('btn-start-transaction');
const inputAmount = document.getElementById('transaction-amount');
const logContainer = document.getElementById('log-container');
const btnClearLogs = document.getElementById('btn-clear-logs');
const mainMessage = document.getElementById('main-message');
const subMessage = document.getElementById('sub-message');
const inputArea = document.getElementById('input-area');

// State
let isConnected = false;

// Socket Events
socket.on('connect', () => {
    isConnected = true;
    statusDot.classList.add('connected');
    statusText.textContent = 'Connected';
    addLog('System', 'Connected to Orchestrator');
});

socket.on('disconnect', () => {
    isConnected = false;
    statusDot.classList.remove('connected');
    statusText.textContent = 'Disconnected';
    addLog('System', 'Disconnected from Orchestrator');
});

socket.on('ui_request', (dataStr) => {
    try {
        const data = JSON.parse(dataStr);
        addLog('RX', `Received SCAPI Request: ${JSON.stringify(data)}`);
        handleUiRequest(data);
    } catch (e) {
        addLog('Error', 'Failed to parse UI request');
        console.error(e);
    }
});

// UI Event Listeners
btnStartTransaction.addEventListener('click', () => {
    if (!isConnected) return alert('Not connected to server.');
    
    const amount = parseFloat(inputAmount.value) * 100; // raw amount in cents
    
    // Simulate Nexo start transaction notification
    const startNotification = {
        ntf: {
            events: {
                languageSelection: { language: 'en' },
                serviceSelection: { serviceId: { payment: null } },
                amountEntry: { totalAmount: Math.round(amount) },
                manualEntry: {
                    pan: "",
                    expirationDate: { year: "", month: "" },
                    cvdData: { cvd: "" }
                }
            }
        },
        id: Math.floor(Math.random() * 10000)
    };
    
    addLog('TX', 'Starting Transaction Notification');
    socket.emit('ui_notification', startNotification);
    
    // Update UI
    mainMessage.textContent = 'Processing...';
    subMessage.textContent = 'Waiting for terminal instructions';
});

btnClearLogs.addEventListener('click', () => {
    logContainer.innerHTML = '';
});

// Logic
function addLog(type, message) {
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    const time = document.createElement('span');
    time.className = 'log-time';
    time.textContent = new Date().toLocaleTimeString();
    
    const msg = document.createElement('span');
    msg.className = 'log-message';
    msg.textContent = `[${type}] ${message}`;
    
    entry.appendChild(time);
    entry.appendChild(msg);
    
    // Prepend
    logContainer.insertBefore(entry, logContainer.firstChild);
}

function handleUiRequest(data) {
    // Process payload commands
    if (data && data.payload && Array.isArray(data.payload)) {
        data.payload.forEach(cmd => {
            const api = cmd.api;
            const lines = cmd.line || [];
            
            if (api === 'msg' || api === 'output') {
                // Display message
                if (lines.length > 0) {
                    mainMessage.textContent = lines[0] || '...';
                    subMessage.textContent = lines[1] || '';
                }
                // Send basic ack
                socket.emit('ui_response', { ack: null });
            } 
            else if (api === 'pin') {
                // Actually this is used for PIN and PAN entry in the old UI 
                // Let's render an input
                const promptMsg = lines[0] || '';
                mainMessage.textContent = promptMsg;
                subMessage.textContent = 'Please enter required data';
                
                inputArea.innerHTML = ''; // Clear current inputs
                
                if (promptMsg.toLowerCase().includes('pan') || promptMsg.toLowerCase().includes('karty')) {
                    renderPanInput();
                } else if (promptMsg.toLowerCase().includes('expiry') || promptMsg.toLowerCase().includes('ważna')) {
                    renderExpiryInput();
                } else if (promptMsg.toLowerCase().includes('cvd') || promptMsg.toLowerCase().includes('cvv')) {
                    renderCvdInput();
                } else {
                    // Default fallback ack if we don't know how to handle
                    socket.emit('ui_response', { ack: null });
                }
            }
            else {
                // Default ack for other stuff
                socket.emit('ui_response', { ack: null });
            }
        });
    }
}

// Render Input Helpers
function renderPanInput() {
    const tpl = document.getElementById('tpl-card-input').content.cloneNode(true);
    inputArea.appendChild(tpl);
    
    const input = document.getElementById('input-pan');
    const btn = inputArea.querySelector('.btn-submit-pan');
    
    btn.addEventListener('click', () => {
        const val = input.value.replace(/\s+/g, '');
        if (val) {
            socket.emit('ui_response', { ackEntry: [{ pin: { plainTextPin: val } }] });
            inputArea.innerHTML = '';
            mainMessage.textContent = 'Processing...';
        }
    });
}

function renderExpiryInput() {
    const tpl = document.getElementById('tpl-expiry-input').content.cloneNode(true);
    inputArea.appendChild(tpl);
    
    const inputM = document.getElementById('input-month');
    const inputY = document.getElementById('input-year');
    const btn = inputArea.querySelector('.btn-submit-expiry');
    
    btn.addEventListener('click', () => {
        const m = inputM.value;
        const y = inputY.value;
        if (m && y) {
            const val = m + y; // or whatever format nexoid expects (MMYY or YYMM?)
            socket.emit('ui_response', { ackEntry: [{ pin: { plainTextPin: val } }] });
            inputArea.innerHTML = '';
            mainMessage.textContent = 'Processing...';
        }
    });
}

function renderCvdInput() {
    const tpl = document.getElementById('tpl-cvd-input').content.cloneNode(true);
    inputArea.appendChild(tpl);
    
    const input = document.getElementById('input-cvd');
    const btn = inputArea.querySelector('.btn-submit-cvd');
    
    btn.addEventListener('click', () => {
        const val = input.value;
        if (val) {
            socket.emit('ui_response', { ackEntry: [{ pin: { plainTextPin: val } }] });
            inputArea.innerHTML = '';
            mainMessage.textContent = 'Processing...';
        }
    });
}
