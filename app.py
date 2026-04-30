import subprocess
import os
import threading
import pty
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Paths verified from your Render build logs
DOOM_PATH = "./doom-ascii"
WAD_PATH = "./DOOM1.WAD"

class DoomGame:
    def __init__(self):
        self.output = "Initializing Doom..."
        
        if not os.path.exists(DOOM_PATH):
            self.output = f"ERROR: {DOOM_PATH} not found."
            return

        try:
            # Create a pseudo-terminal to trick Doom into thinking a screen is attached
            self.master_fd, slave_fd = pty.openpty()
            
            # Start Doom using the slave end of the PTY
            self.process = subprocess.Popen(
                [DOOM_PATH, "-wad", WAD_PATH, "-nocolor", "-i", "-reg"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                close_fds=True
            )
            
            # Start background thread to read the terminal output
            threading.Thread(target=self._stream_output, daemon=True).start()
        except Exception as e:
            self.output = f"Process start failed: {str(e)}"

    def _stream_output(self):
        while True:
            try:
                # Read from the master side of the PTY
                data = os.read(self.master_fd, 4096).decode('utf-8', errors='ignore')
                if data:
                    # Clean up ANSI escape codes and take the latest screen state
                    self.output = data
            except:
                break

    def send_key(self, key):
        try:
            if self.process and self.process.poll() is None:
                # Write the keypress directly to the terminal
                os.write(self.master_fd, f"{key}\n".encode())
        except:
            pass

# Initialize the game instance
game = DoomGame()

@app.route('/')
def index():
    # This creates the visual stream at https://earsketch-doom.onrender.com/
    return render_template_string('''
        <html>
            <head>
                <title>EarSketch Doom Stream</title>
                <style>
                    body { background: black; color: #00FF00; font-family: monospace; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
                    pre { border: 2px solid #333; padding: 20px; background: #050505; line-height: 1.1; font-size: 10px; white-space: pre-wrap; word-wrap: break-word; width: 90vw; height: 90vh; }
                </style>
                <script>
                    async function updateScreen() {
                        try {
                            const res = await fetch('/move', { 
                                method: 'POST', 
                                body: JSON.stringify({input: ''}), 
                                headers: {'Content-Type': 'application/json'} 
                            });
                            const data = await res.json();
                            if (data.ascii_map) {
                                document.getElementById('screen').innerText = data.ascii_map;
                            }
                        } catch (e) {}
                    }
                    setInterval(updateScreen, 150); 
                </script>
            </head>
            <body>
                <pre id="screen">Connecting to Engine...</pre>
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
    # Render uses port 10000 by default
    app.run(host='0.0.0.0', port=10000)
