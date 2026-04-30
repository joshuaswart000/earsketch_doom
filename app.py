import subprocess
import os
import pty
import threading
import time
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
# The logger=True will show us in the Render logs if the WebSocket is actually connecting
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomTerminal:
    def __init__(self):
        self.master_fd, slave_fd = pty.openpty()
        # Removed -nocolor so we get the full terminal experience
        self.process = subprocess.Popen(
            [DOOM_PATH, "-iwad", WAD_PATH, "-i", "-nosound", "-nodraw", "-warp", "1", "1", "-directinput"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            env={
                "TERM": "xterm-256color", 
                "COLUMNS": "80", 
                "LINES": "25",
                "PYTHONUNBUFFERED": "1"
            }
        )
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        while True:
            try:
                # We read small chunks and emit them immediately
                data = os.read(self.master_fd, 4096)
                if data:
                    socketio.emit('output', {'data': data.decode('utf-8', 'ignore')})
            except Exception as e:
                print(f"Terminal Read Error: {e}")
                break

    def write(self, data):
        try:
            # Doom engine expects \r for Enter in most PTY setups
            if data == "\n":
                os.write(self.master_fd, b"\r")
            else:
                os.write(self.master_fd, data.encode())
        except Exception as e:
            print(f"Terminal Write Error: {e}")

# Initialize the game instance
doom = DoomTerminal()

@app.route('/')
def index():
    return render_template_string('''
        <!DOCTYPE html>
        <html>
            <head>
                <title>Doom Color Terminal</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
                <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
                <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
                <style>
                    body { 
                        background: #1a1a1a; 
                        margin: 0; 
                        display: flex; 
                        flex-direction: column; 
                        justify-content: center; 
                        align-items: center; 
                        height: 100vh; 
                        color: white; 
                        font-family: sans-serif;
                    }
                    #terminal-container { 
                        width: 720px; 
                        height: 450px; 
                        border: 5px solid #333; 
                        box-shadow: 0 0 20px rgba(0,0,0,0.5);
                    }
                    .status { margin-bottom: 10px; font-size: 14px; color: #888; }
                </style>
            </head>
            <body>
                <div class="status">Status: <span id="socket-status">Connecting...</span></div>
                <div id="terminal-container"></div>
                <div style="margin-top: 10px; font-size: 12px; color: #666;">
                    Click terminal and press <b>'y'</b> then <b>'Enter'</b> to start.
                </div>

                <script>
                    const socket = io();
                    const statusText = document.getElementById('socket-status');
                    
                    const term = new Terminal({
                        cols: 80,
                        rows: 25,
                        cursorBlink: true,
                        theme: { background: '#000000' },
                        convertEol: true // Crucial for proper line breaks in raw PTY
                    });
                    
                    term.open(document.getElementById('terminal-container'));

                    socket.on('connect', () => {
                        statusText.innerText = "Connected";
                        statusText.style.color = "#0f0";
                        term.write('--- Socket Connected ---\\r\\n');
                    });

                    socket.on('disconnect', () => {
                        statusText.innerText = "Disconnected";
                        statusText.style.color = "#f00";
                    });

                    // This is where the frame logic happens
                    socket.on('output', (msg) => {
                        // If we see a large amount of data, it's likely a frame.
                        // We reset cursor to top-left to "overwrite" rather than scroll.
                        if (msg.data.length > 1000) {
                            term.write('\\x1b[H' + msg.data);
                        } else {
                            term.write(msg.data);
                        }
                    });

                    // Send keyboard data directly
                    term.onData(data => {
                        socket.emit('input', {data: data});
                    });
                </script>
            </body>
        </html>
    ''')

@socketio.on('input')
def handle_input(json):
    doom.write(json.get('data', ''))

if __name__ == '__main__':
    # Use socketio.run for the websocket server to function correctly
    socketio.run(app, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
