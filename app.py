import subprocess
import os
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Path to your compiled doom-ascii binary
DOOM_PATH = "./doom_ascii" 
WAD_PATH = "./doom1.wad" # You need to upload a shareware WAD to your repo

# This class manages the actual game process
class DoomWrapper:
    def __init__(self):
        self.process = subprocess.Popen(
            [DOOM_PATH, "-wad", WAD_PATH, "-nocolor"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.last_frame = "Loading Doom..."
        # Thread to constantly read the game output
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        while True:
            line = self.process.stdout.readline()
            if line:
                # We store lines to build the frame
                # In a real terminal, we'd look for ANSI clear codes
                self.last_frame = line 

    def send_cmd(self, char):
        if self.process.poll() is None:
            self.process.stdin.write(char + "\n")
            self.process.stdin.flush()

doom = DoomWrapper()

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json(silent=True) or request.form
    cmd = data.get('input', '').lower()
    
    # Map EarSketch inputs to Doom keys
    key_map = {'w': 'w', 's': 's', 'a': 'a', 'd': 'd', 'f': ' '}
    if cmd in key_map:
        doom.send_cmd(key_map[cmd])
    
    return jsonify({
        "ascii_map": doom.last_frame,
        "event": "step" if cmd != 'f' else "fire"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
