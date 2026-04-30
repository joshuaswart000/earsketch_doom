import subprocess
import os
import threading
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomGame:
    def __init__(self):
        self.output = "Initializing Doom..."
        self.error_log = ""
        
        if not os.path.exists(DOOM_PATH):
            self.output = "Binary missing."
            return

        # Added stderr capture to see why it might be hanging
        try:
            self.process = subprocess.Popen(
                [DOOM_PATH, "-wad", WAD_PATH, "-nocolor", "-nodraw", "-nosound", "-nomouse"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            threading.Thread(target=self._stream_stdout, daemon=True).start()
            threading.Thread(target=self._stream_stderr, daemon=True).start()
        except Exception as e:
            self.output = f"Failed to start: {str(e)}"

    def _stream_stdout(self):
        while True:
            line = self.process.stdout.readline()
            if line:
                self.output = line

    def _stream_stderr(self):
        while True:
            line = self.process.stderr.readline()
            if line:
                print(f"ENGINE ERROR: {line.strip()}")
                self.error_log += line

    def send_key(self, key):
        if self.process and self.process.poll() is None:
            self.process.stdin.write(f"{key}\n")
            self.process.stdin.flush()

game = DoomGame()

# --- WEB DISPLAY ---
@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>EarSketch Doom Stream</title>
                <style>
                    body { background: black; color: #00FF00; font-family: monospace; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                    pre { border: 2px solid #333; padding: 20px; background: #050505; line-height: 1.2; font-size: 12px; }
                </style>
                <script>
                    async function updateScreen() {
                        const res = await fetch('/move', { method: 'POST', body: JSON.stringify({input: ''}), headers: {'Content-Type': 'application/json'} });
                        const data = await res.json();
                        document.getElementById('screen').innerText = data.ascii_map;
                    }
                    setInterval(updateScreen, 200); // Refresh 5 times per second
                </script>
            </head>
            <body>
                <pre id="screen">Loading Engine...</pre>
            </body>
        </html>
    ''')

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json(silent=True) or request.form
    user_input = data.get('input', '').lower()
    if user_input:
        game.send_key(user_input)
    return jsonify({"ascii_map": game.output, "event": "step"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
