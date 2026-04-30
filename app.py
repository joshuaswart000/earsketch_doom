import subprocess
import os
import pty
import threading
import time
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomTerminal:
    def __init__(self):
        self.master_fd, slave_fd = pty.openpty()
        self.process = subprocess.Popen(
            [DOOM_PATH, "-iwad", WAD_PATH, "-i", "-nosound", "-nodraw", "-warp", "1", "1", "-directinput"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25", "PYTHONUNBUFFERED": "1"}
        )
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        while True:
            try:
                data = os.read(self.master_fd, 4096)
                if data:
                    socketio.emit('output', {'data': data.decode('utf-8', 'ignore')})
            except:
                break

    def write(self, data):
        try:
            val = b"\r" if data == "\n" else data.encode()
            os.write(self.master_fd, val)
        except:
            pass

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
                    body { background: #111; margin: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; color: #eee; font-family: monospace; }
                    #terminal-container { width: 800px; height: 480px; background: black; border: 5px solid #444; overflow: hidden; }
                </style>
            </head>
            <body>
                <div style="margin-bottom:10px;">Network Status: <span id="socket-status">Connecting...</span></div>
                <div id="terminal-container"></div>
                <script>
                    const socket = io({transports: ['websocket', 'polling']});
                    const statusText = document.getElementById('socket-status');
                    const term = new Terminal({
                        cols: 80, rows: 25,
                        cursorBlink: false,
                        convertEol: true,
                        theme: { background: '#000000' }
                    });
                    term.open(document.getElementById('terminal-container'));

                    let frameBuffer = "";

                    socket.on('connect', () => {
                        statusText.innerText = "ONLINE";
                        statusText.style.color = "#0f0";
                    });

                    socket.on('output', (msg) => {
                        frameBuffer += msg.data;
                        
                        // Wait for a significant chunk of data (approx 1 full frame)
                        if (frameBuffer.length >= 1800) {
                            // FIXED: Removed space in \x1b[H
                            // This sequence sends the cursor to Row 1, Col 1 instantly.
                            term.write('\\x1b[H' + frameBuffer);
                            frameBuffer = ""; 
                        }
                    });

                    // Flush any remaining text every 50ms so menus stay responsive
                    setInterval(() => {
                        if (frameBuffer.length > 0) {
                            term.write(frameBuffer);
                            frameBuffer = "";
                        }
                    }, 50);

                    term.onData(data => { socket.emit('input', {data: data}); });
                </script>
            </body>
        </html>
    ''')

@socketio.on('input')
def handle_input(json):
    doom.write(json.get('data', ''))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
