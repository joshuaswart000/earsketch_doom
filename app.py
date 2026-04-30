import subprocess
import os
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- DEBUG: Print files so we can see what Render built ---
print("--- DIRECTORY CHECK ---")
print("Current Directory:", os.getcwd())
print("Files in folder:", os.listdir('.'))
if os.path.exists('src'):
    print("Files in src/ folder:", os.listdir('src'))
# ---------------------------------------------------------

DOOM_PATH = "./doom-ascii" 
WAD_PATH = "./DOOM1.WAD"

class DoomGame:
    def __init__(self):
        self.output = "Initializing Doom..."
        
        # Check if the file exists before trying to run it
        if not os.path.exists(DOOM_PATH):
            self.output = f"ERROR: {DOOM_PATH} not found. Check build logs."
            print(self.output)
            self.process = None
            return

        try:
            self.process = subprocess.Popen(
                [DOOM_PATH, "-wad", WAD_PATH, "-nocolor"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            threading.Thread(target=self._stream_stdout, daemon=True).start()
        except Exception as e:
            self.output = f"Process start failed: {str(e)}"
            self.process = None

    def _stream_stdout(self):
        if not self.process: return
        while True:
            line = self.process.stdout.readline()
            if line:
                self.output = line

    def send_key(self, key):
        if self.process and self.process.poll() is None:
            self.process.stdin.write(f"{key}\n")
            self.process.stdin.flush()

game = DoomGame()

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json(silent=True) or request.form
    user_input = data.get('input', '').lower()
    if user_input:
        game.send_key(user_input)
    
    return jsonify({"ascii_map": game.output, "event": "step"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
