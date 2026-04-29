import subprocess
import os
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Path to the binary created by 'make'
DOOM_PATH = "./doom_ascii" 
WAD_PATH = "./DOOM1.WAD"

class DoomGame:
    def __init__(self):
        self.output = "Initializing Doom..."
        # Start the game in 'nocolor' mode for best ASCII compatibility
        self.process = subprocess.Popen(
            [DOOM_PATH, "-wad", WAD_PATH, "-nocolor"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        threading.Thread(target=self._stream_stdout, daemon=True).start()

    def _stream_stdout(self):
        while True:
            line = self.process.stdout.readline()
            if line:
                self.output = line

    def send_key(self, key):
        if self.process.poll() is None:
            self.process.stdin.write(f"{key}\n")
            self.process.stdin.flush()

# Initialize the game instance
game = DoomGame()

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json(silent=True) or request.form
    user_input = data.get('input', '').lower()
    
    # Map keys: EarSketch W/A/S/D to Doom keys
    if user_input:
        game.send_key(user_input)
    
    return jsonify({
        "ascii_map": game.output,
        "event": "step"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
