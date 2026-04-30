import subprocess
import os
import pty
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
            # REMOVED -nocolor HERE
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
                # High-speed read for smooth color transitions
                data = os.read(self.master_fd, 10240)
                if data:
                    # Send raw bytes to the frontend for xterm.js to decode
                    socketio.emit('output', {'data': data.decode('utf-8', 'ignore')})
            except: break

    def write(self, data):
        try:
            os.write(self.master_fd, data.encode())
        except: pass

doom = DoomTerminal()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>Doom Color Terminal</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
                <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
                <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
                <style>
                    body { background: #000; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
                    #terminal { width: 800px; height: 500px; border: 2px solid #444; }
                </style>
            </head>
            <body>
                <div id="terminal"></div>
                <script>
                    const term = new Terminal({
                        cursorBlink: false, // Blink off for cleaner frame swaps
                        cols: 80,
                        rows: 25,
                        theme: { background: '#000000' }
                    });
                    term.open(document.getElementById('terminal'));
                    
                    const socket = io();
                    let frameBuffer = ""; // Our storage for the incoming frame
                
                    socket.on('output', (msg) => {
                        frameBuffer += msg.data;
                
                        // A full Doom frame (80x25) is exactly 2,000 characters.
                        // Once we hit that limit, we clear the screen and draw the whole block.
                        if (frameBuffer.length >= 2000) {
                            // \x1b[H moves the cursor to the top-left (Home)
                            // This is faster than term.clear()
                            term.write('\x1b[H' + frameBuffer.slice(0, 2000));
                            
                            // Keep any leftover data for the next frame
                            frameBuffer = frameBuffer.slice(2000);
                        }
                    });
                
                    term.onData(data => {
                        socket.emit('input', {data: data});
                    });
                
                    socket.on('connect', () => term.write('\r\nConnected. Press any key to start...\r\n'));
                </script>
            </body>
        </html>
    ''')

@socketio.on('input')
def handle_input(json):
    doom.write(json['data'])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
