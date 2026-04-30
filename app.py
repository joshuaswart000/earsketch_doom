import subprocess
import os
import pty
import base64
import threading
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomTerminal:
    def __init__(self):
        self.master_fd, slave_fd = pty.openpty()
        self.process = subprocess.Popen(
            [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-nodraw", "-warp", "1", "1"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25"}
        )
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        while True:
            try:
                data = os.read(self.master_fd, 1024)
                if data:
                    socketio.emit('output', {'data': data.decode('utf-8', 'ignore')})
            except: break

    def write(self, data):
        os.write(self.master_fd, data.encode())

doom = DoomTerminal()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
                <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
                <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
            </head>
            <body style="background:#000; margin:0;">
                <div id="terminal"></div>
                <script>
                    const term = new Terminal({cols: 80, rows: 25, convertEol: true});
                    term.open(document.getElementById('terminal'));
                    const socket = io();

                    // Real-time output from Doom
                    socket.on('output', (msg) => term.write(msg.data));

                    // Real-time input TO Doom
                    term.onData(data => socket.emit('input', {data: data}));
                </script>
            </body>
        </html>
    ''')

@socketio.on('input')
def handle_input(json):
    doom.write(json['data'])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
