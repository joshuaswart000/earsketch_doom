import subprocess
import os
import pty
import threading
import time
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Update these to the absolute paths where your build succeeded
DOOM_PATH = "/workspaces/earsketch_doom/src/game/doom-ascii"
WAD_PATH = "/workspaces/earsketch_doom/DOOM1.WAD"

class DoomTerminal:
    def __init__(self):
        self.master_fd, slave_fd = pty.openpty()
        self.process = subprocess.Popen(
            [DOOM_PATH, "-iwad", WAD_PATH, "-i", "-nosound", "-nodraw", "-warp", "1", "1", "-directinput"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
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
                data = os.read(self.master_fd, 8192)
                if data:
                    socketio.emit('output', {'data': data.decode('utf-8', 'ignore')})
            except:
                break

    def write(self, data):
        try:
            # Handle enter keys and raw input
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
    <title>Doom ASCII Live</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
    <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { background: #000; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; }
        #terminal-container { width: 800px; height: 480px; border: 2px solid #333; box-shadow: 0 0 20px rgba(0,255,0,0.1); }
    </script>
</head>
<body>
    <div id="terminal-container"></div>
    <script>
        const socket = io({transports: ['websocket', 'polling']});
        const term = new Terminal({
            cols: 80,
            rows: 25,
            scrollback: 0,
            cursorBlink: false,
            theme: { background: '#000000' }
        });
        term.open(document.getElementById('terminal-container'));

        let frameBuffer = "";

        socket.on('output', (msg) => {
            frameBuffer += msg.data;

            // A full Doom frame (80x25) is 2000 characters. 
            // We wait until we have a full "page" of data to avoid the 'Matrix' shredding effect.
            if (frameBuffer.length >= 2000) {
                // \x1b[H resets the cursor to the top-left (Home).
                // We write the last 2000 characters to show the most recent frame.
                term.write('\\x1b[H' + frameBuffer.slice(-2000));
                frameBuffer = ""; 
            }
        });

        // Forward keyboard input to the game
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
    socketio.run(app, host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
