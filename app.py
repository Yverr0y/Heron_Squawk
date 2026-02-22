from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import sys
import time
import random
import struct
from queue import Queue
import base64
import logging
import os

from rylr999 import RYLR999
from packet import Packet, PacketFactory, MSG_TEXT, BROADCAST
from crypto import MeshCrypto
from storage import MessageStorage

# Set up file logging with ABSOLUTE path for debugging
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'heronsquawk_debug.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('heronsquawk')
logger.info(f"=== HeronSquawk Starting - Log file: {LOG_FILE} ===")

# Mesh routing constants
MESH_MARKER = 0x4D  # 'M' - identifies mesh-routed packets
MESH_HEADER_SIZE = 7  # M + origin(2) + msg_id(2) + ttl(1) + hops(1)
DEFAULT_TTL = 5  # Max 5 hops
SEEN_CACHE_SIZE = 100  # Remember last 100 messages
SEEN_CACHE_TIMEOUT = 60  # Forget after 60 seconds


# Will be populated after global variables are defined
broadcast_task_ref = None


async def broadcast_messages_task():
    """Background task to broadcast messages from queue to all connected WebSocket clients."""
    while True:
        try:
            if not message_queue.empty():
                msg = message_queue.get()
                print(f"[WS] Broadcasting message: {msg}")
                print(f"[WS] Connected clients: {len(connected_websockets)}")
                # Broadcast to all connected websockets
                dead_websockets = []
                for ws in connected_websockets:
                    try:
                        await ws.send_json(msg)
                        print(f"[WS] Sent to client OK")
                    except Exception as e:
                        print(f"[WS] Error sending to websocket: {e}")
                        dead_websockets.append(ws)

                # Remove dead connections
                for ws in dead_websockets:
                    if ws in connected_websockets:
                        connected_websockets.remove(ws)

            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Broadcast error: {e}")
            await asyncio.sleep(1)


# Lifespan context manager for startup/shutdown tasks
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: Start the message broadcast task
    global broadcast_task_ref
    broadcast_task_ref = asyncio.create_task(broadcast_messages_task())
    yield
    # Shutdown: Clean up all resources properly
    print("Shutting down...")

    # 1. Cancel the broadcast task and wait for it
    if broadcast_task_ref:
        broadcast_task_ref.cancel()
        try:
            await broadcast_task_ref
        except asyncio.CancelledError:
            pass

    # 2. Close all WebSocket connections gracefully
    for ws in connected_websockets[:]:  # Copy list to avoid modification during iteration
        try:
            await ws.close(code=1001, reason="Server shutting down")
        except Exception:
            pass
    connected_websockets.clear()

    # 3. Stop the radio listener and close serial port
    if radio is not None:
        try:
            radio.close()
            print("Radio connection closed")
        except Exception as e:
            print(f"Error closing radio: {e}")

    print("Shutdown complete")


app = FastAPI(title="Heron Squawk Mesh Node", lifespan=lifespan)

radio = None
factory = None
crypto = None
storage = None  # Persistent message storage
message_queue = Queue()
connected_websockets = []

node_address = 0
known_nodes = {}

# Mesh routing: seen messages cache {(origin, msg_id): timestamp}
seen_messages = {}
mesh_msg_counter = 0

# Message chunk reassembly
# Format: {msg_id: {"chunks": {chunk_num: content}, "total": total_chunks, "from": sender, "channel": channel_name}}
pending_chunks = {}
chunk_timeout = 30  # Seconds before abandoning incomplete message


def next_mesh_msg_id():
    """Get next mesh message ID."""
    global mesh_msg_counter
    mesh_msg_counter = (mesh_msg_counter + 1) % 65536
    return mesh_msg_counter


def build_mesh_header(origin, msg_id, ttl=DEFAULT_TTL, hops=0):
    """
    Build mesh routing header.

    Format: M[origin:2][msg_id:2][ttl:1][hops:1]
    Returns 7 bytes.
    """
    return struct.pack('>BHHBB', MESH_MARKER, origin, msg_id, ttl, hops)


def parse_mesh_header(data):
    """
    Parse mesh routing header.

    Returns: (origin, msg_id, ttl, hops, payload) or None if not a mesh packet.
    """
    if len(data) < MESH_HEADER_SIZE:
        return None

    if data[0] != MESH_MARKER:
        return None

    marker, origin, msg_id, ttl, hops = struct.unpack('>BHHBB', data[:MESH_HEADER_SIZE])
    payload = data[MESH_HEADER_SIZE:]

    return (origin, msg_id, ttl, hops, payload)


def have_seen(origin, msg_id):
    """Check if we've seen this message recently."""
    key = (origin, msg_id)
    return key in seen_messages


def mark_seen(origin, msg_id):
    """Mark message as seen."""
    global seen_messages
    key = (origin, msg_id)
    seen_messages[key] = time.time()

    # Cleanup old entries if cache is too large
    if len(seen_messages) > SEEN_CACHE_SIZE:
        cleanup_seen()


def cleanup_seen():
    """Remove old entries from seen cache."""
    global seen_messages
    current_time = time.time()
    expired = [k for k, t in seen_messages.items()
               if current_time - t > SEEN_CACHE_TIMEOUT]
    for k in expired:
        del seen_messages[k]


def relay_message(origin, msg_id, ttl, hops, payload):
    """
    Relay a mesh message to other nodes.

    Decrements TTL, increments hop count, and re-broadcasts.
    """
    if radio is None:
        return

    # Build new mesh header with updated TTL and hops
    new_header = build_mesh_header(origin, msg_id, ttl, hops)
    full_payload = new_header + payload

    # Base64 encode for RYLR999
    b64_payload = base64.b64encode(full_payload).decode('ascii')

    # Small random delay to avoid collisions
    delay = (node_address % 10) * 0.05
    time.sleep(delay)

    print(f"  -> Relaying for {origin} (TTL={ttl}, hops={hops})")
    radio.send(BROADCAST, b64_payload)


HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Heron Squawk</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0a0e1a;
            color: #e4e8f0;
            height: 100vh;
            overflow: hidden;
        }
        
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-tertiary: #1a2332;
            --bg-hover: #202938;
            --border-color: #2d3748;
            --border-accent: #3d4a5c;
            --text-primary: #e4e8f0;
            --text-secondary: #9ca3af;
            --text-dim: #6b7280;
            --accent-primary: #3b82f6;
            --accent-secondary: #60a5fa;
            --accent-warning: #f59e0b;
            --accent-danger: #ef4444;
            --accent-info: #3b82f6;
        }

        @keyframes slideInHorizontal {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        .unread-badge {
            background: #3b82f6;
            color: white;
            font-size: 11px;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 10px;
            margin-left: 8px;
            min-width: 18px;
            text-align: center;
            display: inline-block;
        }

        .app {
            display: flex;
            height: 100vh;
        }

        .sidebar {
            width: 280px;
            background: var(--bg-secondary);
            display: flex;
            flex-direction: column;
            border-right: 2px solid var(--border-color);
            box-shadow: 4px 0 12px rgba(0,0,0,0.4);
        }

        .sidebar-header {
            padding: 20px;
            border-bottom: 2px solid var(--border-color);
            background: linear-gradient(135deg, var(--bg-secondary), var(--bg-tertiary));
        }

        .brand {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            font-size: 18px;
            font-weight: 700;
            color: var(--accent-primary);
            margin-bottom: 16px;
            letter-spacing: -0.5px;
            text-transform: uppercase;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .brand::before {
            content: "◆";
            font-size: 12px;
        }

        .node-info {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }

        .node-status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-primary);
            box-shadow: 0 0 8px var(--accent-primary);
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .node-status.offline {
            background: var(--accent-danger);
            box-shadow: 0 0 8px var(--accent-danger);
        }

        .node-addr {
            font-size: 11px;
            color: var(--text-dim);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            padding: 2px 6px;
            border-radius: 3px;
        }

        .sidebar-section {
            padding: 12px 20px;
            font-size: 10px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 1.2px;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }

        .sidebar-section button {
            background: var(--bg-tertiary);
            border: 1px solid var(--border-accent);
            color: var(--accent-primary);
            cursor: pointer;
            font-size: 14px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 4px;
            transition: all 0.15s;
        }

        .sidebar-section button:hover {
            background: var(--bg-hover);
            color: var(--accent-secondary);
            border-color: var(--accent-primary);
        }

        .channel-list, .dm-list {
            flex: 1;
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: var(--border-accent) var(--bg-secondary);
        }

        .channel-list::-webkit-scrollbar, .dm-list::-webkit-scrollbar {
            width: 6px;
        }

        .channel-list::-webkit-scrollbar-track, .dm-list::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }

        .channel-list::-webkit-scrollbar-thumb, .dm-list::-webkit-scrollbar-thumb {
            background: var(--border-accent);
            border-radius: 3px;
        }

        .channel-item, .dm-item {
            padding: 12px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 3px solid transparent;
            transition: all 0.12s;
            font-size: 14px;
        }

        .channel-item:hover, .dm-item:hover {
            background: var(--bg-hover);
            border-left-color: var(--border-accent);
        }

        .channel-item.active, .dm-item.active {
            background: var(--bg-tertiary);
            border-left-color: var(--accent-primary);
        }

        .channel-name {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 500;
        }

        .channel-icon {
            color: var(--accent-primary);
            font-weight: 700;
            font-size: 16px;
        }

        .delete-btn {
            background: none;
            border: none;
            color: var(--text-dim);
            cursor: pointer;
            font-size: 18px;
            opacity: 0;
            transition: all 0.15s;
            padding: 4px 8px;
            border-radius: 4px;
        }

        .channel-item:hover .delete-btn,
        .dm-item:hover .delete-btn {
            opacity: 1;
        }

        .delete-btn:hover {
            background: var(--accent-danger);
            color: white;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: var(--bg-primary);
        }

        .chat-header {
            padding: 20px 24px;
            background: var(--bg-secondary);
            border-bottom: 2px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .chat-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .chat-title::before {
            content: "▸";
            color: var(--accent-primary);
            font-size: 14px;
        }

        .chat-actions {
            display: flex;
            gap: 10px;
        }

        .chat-actions button {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border: 1px solid var(--border-accent);
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.15s;
        }

        .chat-actions button:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
            border-color: var(--accent-primary);
        }

        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            scrollbar-width: thin;
            scrollbar-color: var(--border-accent) var(--bg-primary);
        }

        .messages::-webkit-scrollbar {
            width: 8px;
        }

        .messages::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }

        .messages::-webkit-scrollbar-thumb {
            background: var(--border-accent);
            border-radius: 4px;
        }

        .message {
            margin-bottom: 20px;
            max-width: 75%;
            animation: slideIn 0.2s ease-out;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .message.sent {
            margin-left: auto;
        }

        .message-header {
            font-size: 11px;
            color: var(--text-dim);
            margin-bottom: 6px;
            display: flex;
            gap: 10px;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        .message-sender {
            color: var(--accent-info);
            font-weight: 600;
        }

        .message.sent .message-sender {
            color: var(--accent-primary);
        }

        .message-content {
            background: var(--bg-secondary);
            padding: 12px 16px;
            border-radius: 12px;
            border-top-left-radius: 4px;
            border: 1px solid var(--border-color);
            line-height: 1.5;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        }

        .message.sent .message-content {
            background: linear-gradient(135deg, #064e3b, #065f46);
            border: 1px solid #047857;
            border-top-left-radius: 12px;
            border-top-right-radius: 4px;
        }

        .message-meta {
            font-size: 10px;
            color: var(--text-dim);
            margin-top: 4px;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        .input-area {
            padding: 20px 24px;
            background: var(--bg-secondary);
            border-top: 2px solid var(--border-color);
            display: flex;
            gap: 12px;
        }

        .input-area input {
            flex: 1;
            background: var(--bg-tertiary);
            border: 2px solid var(--border-accent);
            color: var(--text-primary);
            padding: 14px 18px;
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
            transition: all 0.15s;
        }

        .input-area input:focus {
            outline: none;
            border-color: var(--accent-primary);
            background: var(--bg-hover);
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
        }

        .input-area button {
            background: var(--accent-primary);
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.15s;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }

        .input-area button:hover:not(:disabled) {
            background: var(--accent-secondary);
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
        }

        .input-area button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            box-shadow: none;
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            backdrop-filter: blur(4px);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }

        .modal.active {
            display: flex;
        }

        .modal-content {
            background: var(--bg-secondary);
            padding: 32px;
            border-radius: 12px;
            width: 400px;
            border: 2px solid var(--border-accent);
            box-shadow: 0 20px 60px rgba(0,0,0,0.6);
        }

        .modal-title {
            font-size: 20px;
            font-weight: 700;
            color: var(--accent-primary);
            margin-bottom: 24px;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .modal-input {
            width: 100%;
            background: var(--bg-tertiary);
            border: 2px solid var(--border-accent);
            color: var(--text-primary);
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 14px;
            font-family: inherit;
            transition: all 0.15s;
        }

        .modal-input:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
        }

        .modal-buttons {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
            margin-top: 24px;
        }

        .modal-buttons button {
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            border: none;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.15s;
        }

        .modal-buttons .cancel {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border: 2px solid var(--border-accent);
        }

        .modal-buttons .cancel:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }

        .modal-buttons .confirm {
            background: var(--accent-primary);
            color: white;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        }

        .modal-buttons .confirm:hover {
            background: var(--accent-secondary);
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4);
        }

        .settings-panel {
            padding: 20px;
            border-top: 2px solid var(--border-color);
            background: var(--bg-primary);
        }

        .settings-row {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }

        .settings-row input {
            flex: 1;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-accent);
            color: var(--text-primary);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        .settings-row button {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            border: 1px solid var(--border-accent);
            padding: 8px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.15s;
        }

        .settings-row button:hover {
            background: var(--bg-hover);
            color: var(--accent-primary);
            border-color: var(--accent-primary);
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-dim);
        }

        .empty-state-icon {
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.3;
        }
    </style>
</head>
<body>
    <div class="app">
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="brand">Heron Squawk</div>
                <div class="node-info">
                    <div class="node-status" id="statusDot"></div>
                    <div>
                        <div class="node-addr" id="nodeAddr">--</div>
                    </div>
                </div>
            </div>

            <div class="sidebar-section">
                <span>Channels</span>
                <button onclick="showJoinChannel()" title="Join Channel">+</button>
            </div>
            <div class="channel-list" id="channelList"></div>

            <div class="sidebar-section">
                <span>Direct Messages</span>
                <button onclick="showNewDM()">+</button>
            </div>
            <div class="dm-list" id="dmList"></div>

            <div class="settings-panel">
                <div class="settings-row">
                    <input type="text" id="callSignInput" placeholder="Call Sign / Name" maxlength="20">
                    <button onclick="saveCallSign()">Save</button>
                </div>
                <div class="settings-row">
                    <button onclick="showSettings()" style="flex:1">Radio Config</button>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="chat-header">
                <div class="chat-title" id="chatTitle">Select a channel or DM</div>
                <div class="chat-actions">
                    <button onclick="loadMessages()">Refresh</button>
                    <button onclick="clearChat()" style="background: var(--accent-danger);">Clear</button>
                </div>
            </div>
            
            <div class="messages" id="messages">
                <div class="empty-state">
                    <div class="empty-state-icon">💬</div>
                    <div>Select a channel or start a conversation</div>
                </div>
            </div>
            
            <div class="input-area">
                <input type="text" id="messageInput" placeholder="Type a message..." disabled>
                <button onclick="sendMessage()" id="sendBtn" disabled>Send</button>
            </div>
        </div>
    </div>
    
    <div class="modal" id="joinChannelModal">
        <div class="modal-content">
            <div class="modal-title">Join Channel</div>
            <input type="text" class="modal-input" id="joinChannelNameInput" placeholder="Channel Name">
            <div class="modal-buttons">
                <button class="cancel" onclick="closeModals()">Cancel</button>
                <button class="confirm" onclick="joinChannel()">Join</button>
            </div>
        </div>
    </div>
    
    <div class="modal" id="newDMModal">
        <div class="modal-content">
            <div class="modal-title">New Direct Message</div>
            <input type="number" class="modal-input" id="dmAddrInput" placeholder="Node Address">
            <div class="modal-buttons">
                <button class="cancel" onclick="closeModals()">Cancel</button>
                <button class="confirm" onclick="startDM()">Start Chat</button>
            </div>
        </div>
    </div>
    
    <div class="modal" id="settingsModal">
        <div class="modal-content">
            <div class="modal-title">Radio Settings</div>
            <label style="font-size:12px;color:#888;">Address</label>
            <input type="number" class="modal-input" id="settingsAddress" min="0" max="65535">
            <label style="font-size:12px;color:#888;">Frequency (Hz)</label>
            <input type="number" class="modal-input" id="settingsFreq">
            <label style="font-size:12px;color:#888;">TX Power (dBm)</label>
            <input type="number" class="modal-input" id="settingsPower" min="0" max="30">
            <label style="font-size:12px;color:#888;">Network ID</label>
            <input type="number" class="modal-input" id="settingsNetId" min="3" max="18">
            <div class="modal-buttons">
                <button class="cancel" onclick="closeModals()">Cancel</button>
                <button class="confirm" onclick="applySettings()">Apply</button>
            </div>
        </div>
    </div>


    <script>
        let ws;
        let currentChat = null;
        let channels = {};  // {channel_name: channel_name}
        let dms = {};  // {addr: addr}
        let myAddr = 0;
        let pendingChannel = null;
        let unreadMessages = {};  // Track unread messages per channel/DM
        let callSign = localStorage.getItem('callSign') || '';  // Persistent call sign
        
        function connect() {
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                document.getElementById('statusDot').classList.remove('offline');
                loadState();
            };
            
            ws.onclose = () => {
                document.getElementById('statusDot').classList.add('offline');
                setTimeout(connect, 2000);
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
        }
        
        function handleMessage(data) {
            if (data.type === 'message') {
                addIncomingMessage(data);
            } else if (data.type === 'new_dm') {
                dms[data.from] = data.from;
                renderSidebar();
            }
        }
        
        function loadState() {
            fetch('/state').then(r => r.json()).then(data => {
                myAddr = data.address;
                channels = data.channels;
                dms = data.dms;

                document.getElementById('nodeAddr').textContent = `Address: ${myAddr}`;

                renderSidebar();
            });
        }
        
        function renderSidebar() {
            // Render joined channels
            const channelList = document.getElementById('channelList');
            channelList.innerHTML = '';

            for (const [name, _] of Object.entries(channels)) {
                const chatId = `ch_${name}`;
                const unread = unreadMessages[chatId] || 0;
                const div = document.createElement('div');
                div.className = 'channel-item' + (currentChat === chatId ? ' active' : '');
                div.innerHTML = `
                    <div class="channel-name">
                        <span class="channel-icon">#</span>
                        <span>${name}</span>
                        ${unread > 0 ? `<span class="unread-badge">${unread}</span>` : ''}
                    </div>
                    <button class="delete-btn" onclick="event.stopPropagation();deleteChannel('${name}')">×</button>
                `;
                div.onclick = () => selectChannel(name);
                channelList.appendChild(div);
            }

            // Render DMs
            const dmList = document.getElementById('dmList');
            dmList.innerHTML = '';

            for (const addr of Object.keys(dms)) {
                const chatId = `dm_${addr}`;
                const unread = unreadMessages[chatId] || 0;
                const div = document.createElement('div');
                div.className = 'dm-item' + (currentChat === chatId ? ' active' : '');
                div.innerHTML = `
                    <div class="channel-name">
                        <span class="channel-icon">@</span>
                        <span>Node ${addr}</span>
                        ${unread > 0 ? `<span class="unread-badge">${unread}</span>` : ''}
                    </div>
                    <button class="delete-btn" onclick="event.stopPropagation();deleteDM(${addr})">×</button>
                `;
                div.onclick = () => selectDM(addr);
                dmList.appendChild(div);
            }
        }
        
        function selectChannel(name) {
            const chatId = `ch_${name}`;
            currentChat = chatId;
            unreadMessages[chatId] = 0;  // Clear unread
            document.getElementById('chatTitle').textContent = `# ${name}`;
            document.getElementById('messageInput').disabled = false;
            document.getElementById('sendBtn').disabled = false;
            renderSidebar();
            loadMessages();
        }

        function selectDM(addr) {
            const chatId = `dm_${addr}`;
            currentChat = chatId;
            unreadMessages[chatId] = 0;  // Clear unread
            document.getElementById('chatTitle').textContent = `@ Node ${addr}`;
            document.getElementById('messageInput').disabled = false;
            document.getElementById('sendBtn').disabled = false;
            renderSidebar();
            loadMessages();
        }
        
        function loadMessages() {
            if (!currentChat) return;
            fetch(`/messages/${currentChat}`).then(r => r.json()).then(data => {
                const container = document.getElementById('messages');
                container.innerHTML = '';
                
                for (const msg of data.messages) {
                    appendMessage(msg);
                }
                
                container.scrollTop = container.scrollHeight;
            });
        }
        
        function appendMessage(msg) {
            const container = document.getElementById('messages');
            const div = document.createElement('div');
            const isSent = msg.from_addr === myAddr;
            div.className = 'message' + (isSent ? ' sent' : '');

            div.innerHTML = `
                <div class="message-header">
                    <span class="message-sender">${isSent ? 'You' : 'Node ' + msg.from_addr}</span>
                    <span>${msg.time}</span>
                </div>
                <div class="message-content">${msg.payload}</div>
                ${msg.rssi ? `<div class="message-meta">RSSI: ${msg.rssi} dBm | SNR: ${msg.snr}</div>` : ''}
            `;

            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }
        
        function addIncomingMessage(data) {
            const chatId = data.channel ? `ch_${data.channel}` : `dm_${data.from}`;

            if (currentChat === chatId) {
                appendMessage({
                    from_addr: data.from,
                    payload: data.payload,
                    rssi: data.rssi,
                    snr: data.snr,
                    time: new Date().toLocaleTimeString()
                });

                // Auto-scroll to bottom
                const container = document.getElementById('messages');
                container.scrollTop = container.scrollHeight;
            } else {
                // Increment unread counter for this channel/DM
                unreadMessages[chatId] = (unreadMessages[chatId] || 0) + 1;
                renderSidebar();  // Update badge display

                // Show notification for messages in other channels
                showNotification(data);
            }
        }

        function showNotification(data) {
            const source = data.channel ? `#${data.channel}` : `@Node ${data.from}`;
            const preview = data.payload.substring(0, 50) + (data.payload.length > 50 ? '...' : '');

            // Create notification element
            const notif = document.createElement('div');
            notif.className = 'notification';
            notif.innerHTML = `
                <div style="font-weight: 600; margin-bottom: 4px;">${source}</div>
                <div style="color: #9ca3af;">Node ${data.from}: ${preview}</div>
            `;
            notif.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: #1f2937;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 16px;
                max-width: 300px;
                z-index: 10000;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                cursor: pointer;
                animation: slideInHorizontal 0.3s ease;
            `;

            // Click to go to that chat
            notif.onclick = () => {
                if (data.channel) {
                    selectChannel(data.channel);
                } else {
                    selectDM(data.from);
                }
                notif.remove();
            };

            document.body.appendChild(notif);

            // Auto-remove after 5 seconds
            setTimeout(() => notif.remove(), 5000);
        }
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const msg = input.value.trim();
            if (!msg || !currentChat) return;

            // Prepend call sign if set
            const messageToSend = callSign ? `${callSign}: ${msg}` : msg;

            let endpoint, body;

            if (currentChat.startsWith('ch_')) {
                const channelName = currentChat.substring(3);  // Remove 'ch_' prefix
                endpoint = '/send/channel';
                body = { channel: channelName, message: messageToSend };
            } else {
                const addr = parseInt(currentChat.split('_')[1]);
                endpoint = '/send/dm';
                body = { address: addr, message: messageToSend };
            }

            // Clear input and show message instantly (with call sign)
            input.value = '';
            appendMessage({
                from_addr: myAddr,
                payload: messageToSend,
                time: new Date().toLocaleTimeString()
            });

            // Send to backend
            fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }
        
        function showNewDM() {
            document.getElementById('dmAddrInput').value = '';
            document.getElementById('newDMModal').classList.add('active');
        }
        
        function showSettings() {
            fetch('/config').then(r => r.json()).then(data => {
                document.getElementById('settingsAddress').value = data.address;
                document.getElementById('settingsFreq').value = data.frequency;
                document.getElementById('settingsPower').value = data.power;
                document.getElementById('settingsNetId').value = data.network_id || 18;
                document.getElementById('settingsModal').classList.add('active');
            });
        }

        function closeModals() {
            document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
        }
        
        function showJoinChannel() {
            document.getElementById('joinChannelNameInput').value = '';
            document.getElementById('joinChannelModal').classList.add('active');
        }

        function joinChannel() {
            const name = document.getElementById('joinChannelNameInput').value.trim();

            if (!name) {
                alert('Enter channel name');
                return;
            }

            fetch('/channel/join', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name })
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    channels[name] = name;
                    renderSidebar();
                    closeModals();
                    selectChannel(name);
                    document.getElementById('joinChannelNameInput').value = '';
                } else {
                    alert(data.error || 'Failed to join channel');
                }
            });
        }

        function deleteChannel(name) {
            if (confirm(`Delete channel "${name}"?`)) {
                fetch('/channel/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name })
                }).then(r => r.json()).then(data => {
                    if (data.success) {
                        delete channels[name];
                        if (currentChat === `ch_${name}`) {
                            currentChat = null;
                            document.getElementById('chatTitle').textContent = 'Select a channel or DM';
                            document.getElementById('messages').innerHTML = '<div class="empty-state"><div class="empty-state-icon">💬</div><div>Select a channel or start a conversation</div></div>';
                            document.getElementById('messageInput').disabled = true;
                            document.getElementById('sendBtn').disabled = true;
                        }
                        renderSidebar();
                    }
                });
            }
        }

        function clearChat() {
            if (!currentChat) return;

            const chatType = currentChat.startsWith('ch_') ? 'channel' : 'DM';
            if (confirm(`Clear all messages in this ${chatType}?`)) {
                fetch('/messages/clear', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ chat_id: currentChat })
                }).then(r => r.json()).then(data => {
                    if (data.success) {
                        document.getElementById('messages').innerHTML = '';
                    }
                });
            }
        }
        
        function startDM() {
            const addr = parseInt(document.getElementById('dmAddrInput').value);

            if (!addr) {
                alert('Enter a node address');
                return;
            }

            fetch('/dm/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ address: addr })
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    dms[addr] = addr;
                    renderSidebar();
                    closeModals();
                    selectDM(addr);
                }
            });
        }
        
        function deleteDM(addr) {
            if (confirm('Delete this conversation?')) {
                fetch('/dm/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ address: parseInt(addr) })
                }).then(r => r.json()).then(data => {
                    if (data.success) {
                        delete dms[addr];
                        if (currentChat === `dm_${addr}`) {
                            currentChat = null;
                            document.getElementById('chatTitle').textContent = 'Select a channel or DM';
                            document.getElementById('messages').innerHTML = '<div class="empty-state"><div class="empty-state-icon">💬</div><div>Select a channel or start a conversation</div></div>';
                            document.getElementById('messageInput').disabled = true;
                            document.getElementById('sendBtn').disabled = true;
                        }
                        renderSidebar();
                    }
                });
            }
        }
        
        function applySettings() {
            const config = {
                address: parseInt(document.getElementById('settingsAddress').value),
                frequency: parseInt(document.getElementById('settingsFreq').value),
                power: parseInt(document.getElementById('settingsPower').value),
                network_id: parseInt(document.getElementById('settingsNetId').value)
            };

            fetch('/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    closeModals();
                    loadState();
                }
            });
        }

        function saveCallSign() {
            const input = document.getElementById('callSignInput');
            callSign = input.value.trim();
            localStorage.setItem('callSign', callSign);
            alert(callSign ? `Call sign set to: ${callSign}` : 'Call sign cleared');
        }

        function loadCallSign() {
            document.getElementById('callSignInput').value = callSign;
        }
        
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });

        // Initialize call sign input
        loadCallSign();

        connect();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_index():
    return HTML_PAGE


@app.get("/state")
async def get_state():
    if radio is None:
        return {"address": 0, "channels": {}, "dms": {}}
    try:
        config = radio.get_config()
        # Return joined channels and DM conversations
        joined_channels = {name: name for name in storage.list_channels()}
        return {
            "address": config['address'],
            "channels": joined_channels,
            "dms": storage.list_dms()
        }
    except Exception as e:
        print(f"Error getting state: {e}")
        return {"address": node_address, "channels": {}, "dms": {}}


@app.get("/config")
async def get_config():
    if radio is None:
        return {"error": "Radio not connected"}
    
    config = radio.get_config()
    config['temperature'] = radio.get_temperature()
    return config


@app.post("/config")
async def set_config(data: dict):
    global node_address
    
    if radio is None:
        return {"error": "Radio not connected", "success": False}
    
    try:
        if 'address' in data:
            radio.set_address(data['address'])
            factory.my_address = data['address']
            node_address = data['address']
        if 'network_id' in data:
            radio.set_network_id(data['network_id'])
        if 'frequency' in data:
            radio.set_frequency(data['frequency'])
        if 'power' in data:
            radio.set_power(data['power'])
        
        return {"success": True}
    except Exception as e:
        return {"error": str(e), "success": False}


@app.post("/channel/join")
async def join_channel(data: dict):
    """Join or create a channel (no passkey needed - mesh passkey provides access control)."""
    channel_name = data['name']

    # Join or create channel
    success = storage.join_channel(channel_name)  # Auto-creates if doesn't exist
    if not success:
        return {"success": False, "error": "Failed to join channel"}

    return {"success": True}


@app.post("/channel/delete")
async def delete_channel(data: dict):
    """Leave a channel."""
    channel_name = data['name']

    # Remove from storage
    if channel_name in storage.channels:
        del storage.channels[channel_name]

    return {"success": True}


@app.post("/dm/create")
async def create_dm(data: dict):
    addr = data['address']

    # Initialize DM in storage if needed
    addr_str = str(addr)
    if addr_str not in storage.dms:
        storage.dms[addr_str] = {'messages': []}

    return {"success": True}


@app.post("/dm/delete")
async def delete_dm(data: dict):
    addr = data['address']
    addr_str = str(addr)

    if addr_str in storage.dms:
        del storage.dms[addr_str]

    return {"success": True}




@app.get("/messages/{chat_id}")
async def get_messages(chat_id: str):
    if chat_id.startswith('ch_'):
        # Channel messages - extract channel name
        channel_name = chat_id[3:]  # Remove 'ch_' prefix
        messages = storage.get_channel_messages(channel_name)
    else:
        # DM messages - extract address
        addr = int(chat_id.split('_')[1])
        messages = storage.get_dm_messages(addr)

    return {"messages": messages}


@app.post("/messages/clear")
async def clear_messages(data: dict):
    """Clear all messages in a channel or DM."""
    chat_id = data.get('chat_id')
    if not chat_id:
        return {"success": False, "error": "No chat_id provided"}

    if chat_id.startswith('ch_'):
        # Clear channel messages
        channel_name = chat_id[3:]
        if channel_name in storage.channels:
            storage.channels[channel_name]['messages'] = []
            return {"success": True}
    else:
        # Clear DM messages
        addr = chat_id.split('_')[1]
        if addr in storage.dms:
            storage.dms[addr]['messages'] = []
            return {"success": True}

    return {"success": False, "error": "Chat not found"}


@app.post("/send/channel")
async def send_channel_message(data: dict):
    """Send channel message with double encryption and automatic chunking.

    Due to double encryption overhead, messages are split into 4-character chunks.
    - Messages up to 4 chars: instant (1 chunk)
    - Longer messages: automatically chunked (e.g., 20 chars = 5 chunks ~1 second)
    The receiver automatically reassembles them.
    """
    try:
        channel_name = data['channel']
        msg = data['message']

        # Verify we're in this channel
        if channel_name not in storage.list_channels():
            return {"error": "Not joined to this channel", "success": False}

        # Determine max payload size empirically
        # Single encryption (mesh only) + chunk headers like "[1234:1/2]"
        # Header is ~11 chars, leaving ~25-30 chars per chunk to stay under 240 hex chars
        max_chunk_size = 25  # Conservative - ensures chunks + headers fit with single encryption

        # Split message into chunks if needed
        chunks = []
        if len(msg) <= max_chunk_size:
            chunks = [msg]
        else:
            # Split into chunks
            for i in range(0, len(msg), max_chunk_size):
                chunks.append(msg[i:i + max_chunk_size])

        # Generate a unique message ID for this multi-chunk message
        msg_id = random.randint(1000, 9999)
        total_chunks = len(chunks)

        success_count = 0
        for chunk_num, chunk in enumerate(chunks, 1):
            # Format: CH:channel_name:[msg_id:chunk_num/total]content
            # or CH:channel_name:content for single chunk
            if total_chunks > 1:
                chunk_msg = f"CH:{channel_name}:[{msg_id}:{chunk_num}/{total_chunks}]{chunk}"
            else:
                chunk_msg = f"CH:{channel_name}:{chunk}"

            # Single encryption only (mesh) - channel encryption removed due to size limits
            # Just use mesh encryption - passkey is for access control, not additional encryption
            mesh_encrypted = crypto.encrypt(chunk_msg.encode() if isinstance(chunk_msg, str) else chunk_msg)

            # Add mesh routing header for multi-hop support
            mesh_id = next_mesh_msg_id()
            mesh_header = build_mesh_header(node_address, mesh_id, DEFAULT_TTL, 0)
            mesh_payload = mesh_header + mesh_encrypted

            # Mark as seen so we don't process our own relayed messages
            mark_seen(node_address, mesh_id)

            # Base64 encode the binary encrypted data to make it ASCII-safe for the radio
            # RYLR999 AT+SEND expects ASCII format data, not raw binary
            base64_data = base64.b64encode(mesh_payload).decode('ascii')

            # Verify chunk size before sending (240 byte ASCII limit)
            if len(base64_data) > 240:
                print(f"ERROR: Chunk {chunk_num} still too large ({len(base64_data)} ASCII chars) - reduce max_chunk_size")
                return {
                    "success": False,
                    "error": f"Chunk too large even after splitting. Contact developer.",
                    "chunks_sent": success_count,
                    "total_chunks": total_chunks
                }

            # Send chunk using radio.send() with ASCII base64 data
            try:
                print(f"Sending chunk {chunk_num}/{total_chunks}: {len(mesh_encrypted)} bytes encrypted -> {len(base64_data)} ASCII chars, content: '{chunk_msg[:50]}'")
                send_result = radio.send(BROADCAST, base64_data)
                print(f"Radio send result: {send_result}")
                if send_result:
                    success_count += 1
                    # Small delay between chunks to avoid flooding
                    if chunk_num < total_chunks:
                        await asyncio.sleep(0.2)
                else:
                    print(f"Failed to send chunk {chunk_num}/{total_chunks} - radio.send returned False")
                    break
            except ValueError as e:
                print(f"Chunk {chunk_num}/{total_chunks} send error: {e}")
                break

        # Save the full original message to storage (not chunks)
        if success_count == total_chunks:
            storage.add_channel_message(
                channel_name,
                node_address,
                msg
            )
            if total_chunks > 1:
                print(f"Sent message in {total_chunks} chunks")

        return {
            "success": success_count == total_chunks,
            "chunks_sent": success_count,
            "total_chunks": total_chunks
        }

    except Exception as e:
        print(f"Channel send error: {e}")
        return {"error": str(e), "success": False}


@app.post("/send/dm")
async def send_dm_message(data: dict):
    """Send DM with mesh routing for multi-hop delivery."""
    try:
        addr = data['address']
        msg = data['message']

        # Format: DM:target_address:content
        dm_msg = f"DM:{addr}:{msg}"

        # Encrypt with mesh key
        encrypted = crypto.encrypt(dm_msg.encode())

        # Add mesh routing header for multi-hop support
        mesh_id = next_mesh_msg_id()
        mesh_header = build_mesh_header(node_address, mesh_id, DEFAULT_TTL, 0)
        mesh_payload = mesh_header + encrypted

        # Mark as seen so we don't process our own relayed messages
        mark_seen(node_address, mesh_id)

        # Base64 encode and broadcast (mesh routing will deliver)
        base64_data = base64.b64encode(mesh_payload).decode('ascii')
        success = radio.send(BROADCAST, base64_data)

        if success:
            # Save to storage
            storage.add_dm_message(
                addr,
                node_address,
                msg
            )

        return {"success": success}
    except Exception as e:
        return {"error": str(e), "success": False}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    print(f"[WS] Client connected! Total clients: {len(connected_websockets)}")

    try:
        # Keep connection alive with periodic pings
        while True:
            try:
                # Wait for message or timeout
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break  # Connection lost
    except WebSocketDisconnect:
        print(f"[WS] Client disconnected (normal)")
    except Exception as e:
        print(f"[WS] Client disconnected (error: {e})")
    finally:
        # Always clean up the connection
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)
        print(f"[WS] Client removed. Total clients: {len(connected_websockets)}")


def parse_rylr_frame(data):
    """
    Parse RYLR999-compatible frame from Heltec.

    Format: [Dest: 2 bytes LE] [Src: 2 bytes LE] [Len: 1 byte] [Data]
    Returns: (src_addr, dest_addr, payload) or None if invalid

    Validation: length field must exactly match remaining data.
    This distinguishes RYLR frames from base64 data which would
    have random length values.
    """
    if len(data) < 6:  # Need at least header + 1 byte payload
        return None

    try:
        dest_addr, src_addr, length = struct.unpack('<HHB', data[:5])

        # Critical validation: length must exactly match remaining data
        remaining = len(data) - 5
        if length != remaining:
            return None  # Not a valid RYLR frame

        # Additional sanity check: addresses should be valid (1-65535 for src)
        if src_addr == 0:
            return None

        payload = data[5:5+length]
        return (src_addr, dest_addr, payload)
    except (struct.error, ValueError, IndexError):
        return None


def on_receive(sender, data, rssi, snr):
    """
    Receive handler with support for:
    - RYLR frame format from Heltec (binary framed)
    - Base64 mesh messages from other RYLR999 nodes
    - Legacy packet format
    """
    print(f"\n[APP] ========== ON_RECEIVE ==========")
    print(f"[APP] sender={sender}, rssi={rssi}, snr={snr}")
    print(f"[APP] data type={type(data).__name__}, len={len(data)}")
    print(f"[APP] data={data[:80]}...")
    try:
        # Ignore our own messages
        if sender == node_address:
            print(f"[APP] Ignoring own message")
            logger.debug(f"Ignoring own message from {sender}")
            return

        logger.info(f"=== RECEIVE HANDLER CALLED ===")
        logger.info(f"From sender={sender}, RSSI={rssi}, SNR={snr}")
        logger.info(f"Data type: {type(data)}, len: {len(data)}")
        logger.info(f"Data: {data[:100]}{'...' if len(data) > 100 else ''}")

        # Convert data to bytes if it's a string
        if isinstance(data, str):
            data_bytes = data.encode('latin-1')  # Preserve byte values
        else:
            data_bytes = data

        # Try to parse as RYLR frame from Heltec first
        rylr_frame = parse_rylr_frame(data_bytes)
        if rylr_frame:
            src_addr, dest_addr, payload = rylr_frame
            logger.info(f"RYLR frame: src={src_addr}, dest={dest_addr}, len={len(payload)}")
            # Use the source address from the frame as the actual sender
            sender = src_addr
            # The payload is mesh_header + base64_data
            data_bytes = payload
            data = payload.decode('latin-1') if isinstance(payload, bytes) else payload
        else:
            logger.debug("Not RYLR frame - treating as base64")

        # Try base64 decode (mesh format from RYLR999 or Heltec payload)
        decoded_bytes = None
        try:
            # First try: data might be pure base64
            decoded_bytes = base64.b64decode(data)
            print(f"[APP] Base64 decode OK: {len(decoded_bytes)} bytes")
            print(f"[APP] First bytes hex: {decoded_bytes[:10].hex()}")
            logger.debug(f"Base64 OK: {len(decoded_bytes)} bytes, first byte: {decoded_bytes[0]:02x}")
        except Exception as e:
            print(f"[APP] Base64 decode FAILED: {e}")
            logger.debug(f"Base64 failed: {e}")
            # Second try: might be binary with mesh header already
            if len(data_bytes) >= MESH_HEADER_SIZE and data_bytes[0] == MESH_MARKER:
                decoded_bytes = data_bytes
                print(f"[APP] Using raw binary (has mesh marker)")
                logger.debug("Using raw binary (has mesh marker)")

        if decoded_bytes is None:
            print(f"[APP] Could not decode data - returning")
            logger.warning(f"Could not decode data: {data[:50]}...")
            return

        # Check for mesh routing header
        mesh_info = parse_mesh_header(decoded_bytes)
        print(f"[APP] parse_mesh_header returned: {mesh_info is not None}")
        if mesh_info:
            origin, msg_id, ttl, hops, encrypted_bytes = mesh_info
            print(f"[APP] Mesh: origin={origin}, msg_id={msg_id}, ttl={ttl}, hops={hops}")
            print(f"[APP] Encrypted payload: {len(encrypted_bytes)} bytes")
            logger.debug(f"Mesh header: origin={origin}, msg_id={msg_id}, ttl={ttl}, hops={hops}")

            # Check if we've already seen this message
            if have_seen(origin, msg_id):
                print(f"[APP] Already seen - skipping")
                logger.info(f"Skipping already-seen message {msg_id} from {origin}")
                return

            # Mark as seen
            mark_seen(origin, msg_id)

            # Use origin as the actual sender for display
            sender = origin
            logger.info(f"Mesh message from {origin} (TTL={ttl}, hops={hops})")

            # Relay if TTL > 1 and not from us
            if ttl > 1 and origin != node_address:
                relay_message(origin, msg_id, ttl - 1, hops + 1, encrypted_bytes)
        else:
            # Legacy non-mesh packet (direct from sender)
            print(f"[APP] No mesh header - legacy packet")
            logger.debug("No mesh header found, treating as legacy")
            encrypted_bytes = decoded_bytes

        # Mesh decrypt only
        print(f"[APP] Attempting decrypt of {len(encrypted_bytes)} bytes...")
        logger.debug(f"Attempting decrypt, {len(encrypted_bytes)} encrypted bytes")
        try:
            mesh_decrypted = crypto.decrypt(encrypted_bytes)
            plaintext = mesh_decrypted.decode()
            print(f"[APP] DECRYPTED OK: {plaintext[:80]}...")
            logger.debug(f"Decrypted OK: {plaintext[:80]}...")
        except Exception as e:
            print(f"[APP] DECRYPTION FAILED: {e}")
            logger.error(f"Decryption failed: {e}")
            return

        # Parse channel identifier: CH:channel_name:content
        if plaintext.startswith('CH:'):
            parts = plaintext.split(':', 2)  # Split into max 3 parts
            if len(parts) >= 3:
                channel_name = parts[1]
                message_content = parts[2]
                logger.debug(f"Channel message: channel={channel_name}, content={message_content[:50]}")

                # Verify we're in this channel
                if channel_name not in storage.list_channels():
                    logger.warning(f"Received message for channel '{channel_name}' which we're not in")
                    logger.debug(f"Our channels: {storage.list_channels()}")
                    return

                # Check if this is a chunked message
                if message_content.startswith('[') and ']' in message_content[:20]:
                    # Parse chunk header: [msg_id:chunk_num/total]content
                    try:
                        header_end = message_content.index(']')
                        header = message_content[1:header_end]
                        content = message_content[header_end+1:]

                        msg_id_part, chunk_part = header.split(':')
                        msg_id = int(msg_id_part)
                        chunk_num, total_chunks = map(int, chunk_part.split('/'))

                        # Initialize chunk storage for this message
                        if msg_id not in pending_chunks:
                            pending_chunks[msg_id] = {
                                "chunks": {},
                                "total": total_chunks,
                                "from": sender,
                                "channel": channel_name,
                                "timestamp": time.time()
                            }

                        # Store this chunk
                        pending_chunks[msg_id]["chunks"][chunk_num] = content
                        logger.info(f"Received chunk {chunk_num}/{total_chunks} of message {msg_id} for channel '{channel_name}'")

                        # Check if we have all chunks
                        if len(pending_chunks[msg_id]["chunks"]) == total_chunks:
                            # Reassemble message
                            full_message = ""
                            for i in range(1, total_chunks + 1):
                                full_message += pending_chunks[msg_id]["chunks"][i]

                            logger.info(f"Reassembled complete message {msg_id}: {len(full_message)} chars")

                            # Save and display the complete message
                            storage.add_channel_message(channel_name, sender, full_message, rssi=rssi, snr=snr)

                            message_queue.put({
                                "type": "message",
                                "from": sender,
                                "channel": channel_name,
                                "payload": full_message,
                                "rssi": rssi,
                                "snr": snr
                            })

                            # Clean up
                            del pending_chunks[msg_id]

                        return  # Chunk handled

                    except (ValueError, KeyError, IndexError) as e:
                        logger.error(f"Error parsing chunk header: {e}")
                        # Treat as regular message
                        pass

                # Not a chunk or parsing failed - treat as single message
                logger.info(f"MESSAGE RECEIVED: channel={channel_name}, from={sender}, content={message_content[:50]}")
                storage.add_channel_message(channel_name, sender, message_content, rssi=rssi, snr=snr)

                message_queue.put({
                    "type": "message",
                    "from": sender,
                    "channel": channel_name,
                    "payload": message_content,
                    "rssi": rssi,
                    "snr": snr
                })
                return  # Message handled

        # Check for DM format: DM:target_address:content
        elif plaintext.startswith('DM:'):
            parts = plaintext.split(':', 2)
            if len(parts) >= 3:
                try:
                    target_addr = int(parts[1])
                    message_content = parts[2]

                    # Only process if this DM is for us
                    if target_addr == node_address:
                        storage.add_dm_message(sender, sender, message_content, rssi=rssi, snr=snr)

                        message_queue.put({
                            "type": "message",
                            "from": sender,
                            "channel": None,
                            "payload": message_content,
                            "rssi": rssi,
                            "snr": snr
                        })

                        if str(sender) not in storage.list_dms():
                            message_queue.put({
                                "type": "new_dm",
                                "from": sender
                            })
                        logger.info(f"Received DM from {sender}: {message_content[:50]}...")
                    else:
                        # DM not for us - already relayed above if needed
                        logger.debug(f"DM for {target_addr}, not us ({node_address})")
                    return
                except ValueError:
                    logger.error("Invalid DM target address format")

        logger.warning(f"Received non-channel/non-DM message or invalid format: {plaintext[:50]}...")

        # Clean up old incomplete chunks (timeout cleanup)
        current_time = time.time()
        expired_msgs = [msg_id for msg_id, data in pending_chunks.items()
                       if current_time - data["timestamp"] > chunk_timeout]
        for msg_id in expired_msgs:
            logger.warning(f"Timeout: Abandoned incomplete message {msg_id}")
            del pending_chunks[msg_id]

    except Exception as e:
        print(f"Fatal receive error: {e}")


def start_radio(port, passphrase):
    global radio, factory, crypto, node_address, storage

    # Connect to radio first (without setting address yet)
    radio = RYLR999(port, address=None)

    # Set Network ID to 18 (0x12) - private LoRa sync word (matches Heltec)
    radio.set_network_id(18)
    print(f"Set Network ID to 18 (private LoRa sync word 0x12)")

    # Generate random address (1-65535, avoiding 0 which is broadcast)
    address = random.randint(1, 65535)
    radio.set_address(address)
    print(f"Generated random address: {address}")

    # Initialize in-memory storage (no persistence)
    storage = MessageStorage()

    factory = PacketFactory(my_address=address)
    # Initialize crypto with shared mesh key
    crypto = MeshCrypto(passphrase, node_address=address)
    node_address = address

    radio.start_listening(on_receive)
    print(f"Radio started on {port} with address {address}")
    print(f"Mesh mode: All nodes with same passphrase can communicate")


def generate_self_signed_cert(cert_file="cert.pem", key_file="key.pem"):
    """Generate a self-signed certificate for HTTPS."""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime
        import ipaddress
        import os

        # Check if certs already exist
        if os.path.exists(cert_file) and os.path.exists(key_file):
            print(f"Using existing certificates: {cert_file}, {key_file}")
            return cert_file, key_file

        print("Generating self-signed certificate for HTTPS...")

        # Generate private key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Local"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HeronSquawk"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        # Write private key
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # Write certificate
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print(f"Generated self-signed certificate: {cert_file}, {key_file}")
        return cert_file, key_file

    except ImportError:
        print("WARNING: 'cryptography' package not installed. HTTPS disabled.")
        print("Install with: pip install cryptography")
        return None, None




if __name__ == '__main__':
    import os
    import signal

    def force_exit(signum, frame):
        """Immediately terminate on Ctrl+C."""
        print("\nShutting down...")
        if radio is not None:
            try:
                radio.close()
                print("Radio closed")
            except Exception:
                pass
        print("Goodbye!")
        os._exit(0)

    # Register signal handler BEFORE uvicorn can override it
    signal.signal(signal.SIGINT, force_exit)
    if sys.platform == 'win32':
        signal.signal(signal.SIGBREAK, force_exit)

    if len(sys.argv) < 3:
        print("Usage: python app.py <COM_PORT> <PASSPHRASE> [WEB_PORT] [--https]")
        print("Example (Linux):   python app.py /dev/ttyUSB0 mysecretkey")
        print("Example (Windows): python app.py COM8 mysecretkey 8000")
        print("Example with HTTPS: python app.py /dev/ttyUSB0 mysecretkey 8000 --https")
        print("")
        print("A random address (1-65535) is generated on each startup.")
        sys.exit(1)

    port = sys.argv[1]
    passphrase = sys.argv[2]

    # Parse remaining arguments (web_port, --https)
    web_port = 8000
    use_https = '--https' in sys.argv

    # Filter out --https from args for easier parsing
    args = [a for a in sys.argv[3:] if not a.startswith('--')]

    if len(args) >= 1:
        web_port = int(args[0])

    start_radio(port, passphrase)

    # Common uvicorn config
    config = {
        "host": "0.0.0.0",
        "port": web_port,
        "log_level": "warning",
    }

    if use_https:
        cert_file, key_file = generate_self_signed_cert()
        if cert_file and key_file:
            print(f"Starting web UI at https://localhost:{web_port}")
            print("NOTE: Your browser will show a security warning for the self-signed certificate.")
            print("      This is expected - click 'Advanced' and 'Proceed' to continue.")
            config["ssl_keyfile"] = key_file
            config["ssl_certfile"] = cert_file
        else:
            print("HTTPS requested but certificate generation failed. Falling back to HTTP.")
            print(f"Starting web UI at http://localhost:{web_port}")
    else:
        print(f"Starting web UI at http://localhost:{web_port}")

    print("Press Ctrl+C to stop\n")

    try:
        uvicorn.run(app, **config)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down...")
        if radio is not None:
            try:
                radio.close()
                print("Radio closed")
            except Exception:
                pass
        print("Goodbye!")
        os._exit(0)