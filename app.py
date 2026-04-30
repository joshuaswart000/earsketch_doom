import subprocess
import os
import threading
import pty
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomGame:
    def __init__(self):
        self.output = ""
        if not os.path.exists(DOOM_PATH):
            self.output = "ERROR: doom-ascii not found."
            return

        try:
            self.master_fd, slave_fd = pty.openpty()
            # 1. REMOVED -nodraw (this was likely blocking the 3D view)
            # 2. Added -interactive to force it to accept our PTY inputs
            self.process = subprocess.Popen(
                [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-warp", "1", "1", "-width", "80", "-height", "25"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                close_fds=True
            )
            
            # Use a more aggressive startup kick
            def kickstart():
                import time
                for _ in range(5): # Try 5 times to wake it up
                    time.sleep(2)
                    os.write(self.master_fd, b" \n") # Space + Enter
            
            threading.Thread(target=kickstart, daemon=True).start()
            threading.Thread(target=self._stream_output, daemon=True).start()
        except Exception as e:
            self.output = f"Init Failed: {str(e)}"

    def _stream_output(self):
        while True:
            try:
                data = os.read(self.master_fd, 10240).decode('utf-8', errors='ignore')
                if data:
                    # We look for the 'Home' ANSI code. If found, we treat it as a new frame.
                    if '\x1b[H' in data:
                        self.output = data
                    else:
                        # Append small updates, but cap the length to avoid overflow
                        self.output = (self.output + data)[-10240:]
            except:
                break

    def send_key(self, key):
        try:
            if self.process and self.process.poll() is None:
                if key == 'f': key = ' '
                os.write(self.master_fd, key.encode())
        except:
            pass

game = DoomGame()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>EarSketch Doom Terminal</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
                <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
                <style>
                    body { background: #000; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                    #terminal { width: 640px; height: 400px; border: 2px solid #00FF00; }
                    .controls { color: #00FF00; margin-top: 15px; font-family: monospace; }
                </style>
            </head>
            <body>
                <div id="terminal"></div>
                <div class="controls">WASD: Move | SPACE: Fire | Browser focused to play</div>
                <script>
                    const term = new Terminal({ cols: 80, rows: 25, theme: { background: '#000000', foreground: '#00FF00' }, convertEol: true });
                    term.open(document.getElementById('terminal'));

                    async function sendInput(key) {
                        fetch('/move', { method: 'POST', body: JSON.stringify({input: key}), headers: {'Content-Type': 'application/json'} });
                    }

                    window.addEventListener('keydown', (e) => {
                        const keyMap = {'w':'w','a':'a','s':'s','d':'d',' ':'f','f':'f','Enter':'f'};
                        const cmd = keyMap[e.key.toLowerCase()];
                        if (cmd) { sendInput(cmd); e.preventDefault(); }
                    });

                    async function updateScreen() {
                        const res = await fetch('/move', { method: 'POST', body: JSON.stringify({input: ''}), headers: {'Content-Type': 'application/json'} });
                        const data = await res.json();
                        if (data.ascii_map) {
                            // If the data contains the "Home" code, clear the terminal for a fresh draw
                            if (data.ascii_map.includes('\\x1b[H') || data.ascii_map.includes('\\033[H')) {
                                term.reset();
                            }
                            term.write(data.ascii_map);
                        }
                    }
                    setInterval(updateScreen, 100);
                </script>
            </body>
        </html>
    ''')

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json(silent=True) or {}
    user_input = data.get('input', '').lower()
    if user_input:
        game.send_key(user_input)
    return jsonify({"ascii_map": game.output, "event": "step"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
