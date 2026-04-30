import subprocess
import os
import pty
import threading
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
# WebSockets allow the server to "push" frames the moment they are ready
socketio = SocketIO(app, cors_allowed_origins="*")

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomTerminal:
    def __init__(self):
        self.master_fd, slave_fd = pty.openpty()
        self.process = subprocess.Popen(
            [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-nodraw", "-warp", "1", "1", "-directinput"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25"}
        )
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        while True:
            try:
                # Read a large chunk (a full frame is ~2000 bytes)
                data = os.read(self.master_fd, 4096)
                if data:
                    # Emit immediately to the frontend
                    socketio.emit('output', {'data': data.decode('utf-8', 'ignore')})
            except: break

    def write(self, data):
        if data == '\r' or data == '\n':
            os.write(self.master_fd, b'\r\n')
        else:
            os.write(self.master_fd, data.encode())

doom = DoomTerminal()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>Doom Real-Time Terminal</title>
                <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
                <style>
                    body { background: #000; color: #0F0; display: flex; flex-direction: column; align-items: center; margin: 0; }
                    #display { 
                        font-family: 'Courier New', monospace; 
                        font-size: 14px; line-height: 14px; 
                        white-space: pre; border: 2px solid #0F0; padding: 10px;
                        width: 80ch; height: 25lh; overflow: hidden;
                    }
                </style>
            </head>
            <body>
                <h1>Doom Live Stream</h1>
                <pre id="display">Connecting to engine...</pre>
                <script>
                    const socket = io();
                    const display = document.getElementById('display');
                    let buffer = "";

                    socket.on('output', (msg) => {
                        // We append data to a buffer and only draw when we see a "frame reset" 
                        // or enough data has accumulated to be a full screen.
                        buffer += msg.data;
                        if (buffer.length > 1800) {
                            display.innerText = buffer.slice(-2000); 
                            buffer = ""; // Clear buffer after draw to keep it snappy
                        }
                    });

                    window.addEventListener('keydown', e => {
                        const keys = {'w':'w','a':'a','s':'s','d':'d',' ':'f','Enter':'\r'};
                        const val = keys[e.key] || keys[e.key.toLowerCase()];
                        if(val) socket.emit('input', {data: val});
                    });
                </script>
            </body>
        </html>
    ''')

@socketio.on('input')
def handle_input(json):
    doom.write(json['data'])

if __name__ == '__main__':
    # Using socketio.run instead of app.run for WebSocket support
    socketio.run(app, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
