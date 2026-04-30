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
            # Added -directinput for better responsiveness
            self.process = subprocess.Popen(
                [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-nodraw", "-warp", "1", "1", "-directinput"],
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
                env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25"}
            )
            
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
                    self.output_b64 = base64.b64encode(data).decode('utf-8')
            except: break

    def send_key(self, key):
        try:
            if self.process.poll() is None:
                if key == 'f': key = '\r\n'
                os.write(self.master_fd, key.encode())
        except: pass

game = DoomGame()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head><title>Doom Terminal</title></head>
            <body style="background:#000; color:#0F0; font-family:monospace; display:flex; flex-direction:column; align-items:center;">
                <pre id="display" style="border:1px solid #0F0; padding:10px;"></pre>
                <script>
                    async function update() {
                        const res = await fetch('/map');
                        const data = await res.json();
                        if (data.plain_text) {
                            document.getElementById('display').innerText = data.plain_text;
                        }
                    }
                    setInterval(update, 200);
                    window.addEventListener('keydown', e => {
                        const keys = {'w':'w','a':'a','s':'s','d':'d',' ':'f','y':'y','Enter':'f'};
                        const val = keys[e.key] || keys[e.key.toLowerCase()];
                        if(val) fetch('/move', {method:'POST', body:JSON.stringify({input:val}), headers:{'Content-Type':'application/json'}});
                    });
                </script>
            </body>
        </html>
    ''')

@app.route('/map')
def get_map():
    raw_text = ""
    if game.output_b64:
        # This decodes the bytes so EarSketch gets a clean string
        raw_text = base64.b64decode(game.output_b64).decode('utf-8', errors='ignore')
    return jsonify({"ascii_map": game.output_b64, "plain_text": raw_text})

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json() or {}
    game.send_key(data.get('input', ''))
    return jsonify({"status": "sent"})

if __name__ == '__main__':
    # The fix that keeps it running on Render
    app.run(host='0.0.0.0', port=10000, allow_unsafe_werkzeug=True)
