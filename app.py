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
                    let lastDataTime = Date.now();

                    socket.on('connect', () => {
                        statusText.innerText = "ONLINE";
                        statusText.style.color = "#0f0";
                    });

                    socket.on('output', (msg) => {
                        frameBuffer += msg.data;
                        lastDataTime = Date.now();
                        
                        // If we have a full frame (roughly 2000 chars), draw it all at once
                        if (frameBuffer.length >= 2000) {
                            term.write('\\x1b[H' + frameBuffer.substring(0, 2000));
                            frameBuffer = frameBuffer.substring(2000); 
                        }
                    });

                    // Fallback: Only print if data has been sitting for 200ms 
                    // This prevents the "fragmented" look during active gameplay
                    setInterval(() => {
                        const timeSinceLastData = Date.now() - lastDataTime;
                        if (frameBuffer.length > 0 && timeSinceLastData > 200) {
                            term.write(frameBuffer);
                            frameBuffer = "";
                        }
                    }, 100);

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
