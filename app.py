import subprocess
import os
import threading
import pty
import base64
import time
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomGame:
    def __init__(self):
        self.output_b64 = ""
        if not os.path.exists(DOOM_PATH): return

        try:
            self.master_fd, slave_fd = pty.openpty()
            # -directinput helps the engine listen to raw bytes better
            self.process = subprocess.Popen(
                [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-nodraw", "-warp", "1", "1", "-directinput"],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25"}
            )
            
            # This handles the "y" and "Enter" sequence automatically after 10 seconds
            def kickstart():
                time.sleep(10)
                os.write(self.master_fd, b"y\r\n\r\n\r\n")
            
            threading.Thread(target=kickstart, daemon=True).start()
            threading.Thread(target=self._stream_output, daemon=True).start()
        except Exception as e:
            print(f"Init Error: {e}")

    def _stream_output(self):
        while True:
            try:
                data = os.read(self.master_fd, 10240)
                if data:
                    # Store the latest "frame" as base64
                    self.output_b64 = base64.b64encode(data).decode('utf-8')
            except: break

    def send_key(self, key):
        try:
            if self.process.poll() is None:
                # Map 'f' to Enter
                if key == 'f': key = '\r\n'
                os.write(self.master_fd, key.encode())
        except: pass

game = DoomGame()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>Doom Terminal</title>
                <style>
                    body { 
                        background: #000; 
                        color: #0F0;
                        display: flex; 
                        flex-direction: column; 
                        align-items: center; 
                        margin: 0; 
                    }
                    #display { 
                        font-family: 'Courier New', monospace; 
                        font-size: 14px; 
                        line-height: 14px; 
                        letter-spacing: 0px;
                        border: 2px solid #0F0; 
                        padding: 10px;
                        white-space: pre;
                        display: inline-block;
                        /* This prevents the "too wide" look by forcing a container */
                        width: 80ch; 
                        overflow: hidden;
                    }
                </style>
            </head>
            <body>
                <h1 style="margin: 10px;">Doom Terminal</h1>
                <pre id="display">Initializing Doom Engine...</pre>
                <script>
                    let lastFrame = "";
                    async function update() {
                        try {
                            const res = await fetch('/map');
                            const data = await res.json();
                            
                            if (data.plain_text && data.plain_text !== lastFrame) {
                                // A full 80x25 frame is 2000 chars. 
                                // Checking for > 1500 ensures we have almost a whole screen.
                                if (data.plain_text.length > 1500) {
                                    document.getElementById('display').innerText = data.plain_text;
                                    lastFrame = data.plain_text;
                                }
                            }
                        } catch (e) {}
                    }
                    // Refresh slightly slower (250ms) to allow the buffer to fill
                    setInterval(update, 250);
                    
                    window.addEventListener('keydown', e => {
                        const keys = {'w':'w','a':'a','s':'s','d':'d',' ':'f','y':'y','Enter':'f'};
                        const val = keys[e.key] || keys[e.key.toLowerCase()];
                        if(val) fetch('/move', {
                            method:'POST', 
                            body:JSON.stringify({input:val}), 
                            headers:{'Content-Type':'application/json'}
                        });
                    });
                </script>
            </body>
        </html>
    ''')

@app.route('/map')
def get_map():
    raw_text = ""
    if game.output_b64:
        raw_text = base64.b64decode(game.output_b64).decode('utf-8', errors='ignore')
    return jsonify({"ascii_map": game.output_b64, "plain_text": raw_text})

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json() or {}
    game.send_key(data.get('input', ''))
    return jsonify({"status": "sent"})

if __name__ == '__main__':
    # Using run_simple to avoid the safety crashes on Render
    from werkzeug.serving import run_simple
    run_simple('0.0.0.0', 10000, app, use_reloader=False, use_debugger=False, threaded=True)
