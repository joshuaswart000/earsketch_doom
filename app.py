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
            self.master_fd, slave_fd = pty.openpty()
            self.process = subprocess.Popen(
                [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-nodraw", "-warp", "1", "1"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                close_fds=True
            )
            
            # --- ADD THIS STARTUP KICK ---
            import time
            time.sleep(2) # Wait for engine to load
            os.write(self.master_fd, b"\n") # Send an Enter key to wake up the screen
            # -----------------------------

            threading.Thread(target=self._stream_output, daemon=True).start()
        except Exception as e:
            self.output = f"Process start failed: {str(e)}"

    def _stream_output(self):
        while True:
            try:
                # Read absolutely everything available
                data = os.read(self.master_fd, 10240).decode('utf-8', errors='ignore')
                if data:
                    # Remove the specific character that might be clearing the screen 
                    # and just set the output to the raw text
                    clean_data = data.replace('\x0c', '')
                    if clean_data.strip():
                        self.output = clean_data
            except:
                break

    def send_key(self, key):
        try:
            if self.process and self.process.poll() is None:
                # Map 'f' to ' ' (Space) because Doom uses Space/Enter to skip intros
                if key == 'f':
                    key = ' '
                
                # Write the key AND a newline, then force it through
                os.write(self.master_fd, key.encode())
                # Small delay to let the engine process the "press"
                import time
                time.sleep(0.1)
        except Exception as e:
            print(f"Input Error: {e}")

# Initialize the game instance
game = DoomGame()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>EarSketch Doom Playable Stream</title>
                <style>
                    body { background: black; color: #00FF00; font-family: monospace; display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
                    pre { border: 2px solid #333; padding: 20px; background: #050505; line-height: 1.1; font-size: 10px; white-space: pre-wrap; word-wrap: break-word; width: 90vw; height: 80vh; }
                    .controls { color: #555; margin-top: 10px; font-size: 14px; }
                </style>
                <script>
                    async function sendInput(key) {
                        try {
                            await fetch('/move', {
                                method: 'POST',
                                body: JSON.stringify({input: key}),
                                headers: {'Content-Type': 'application/json'}
                            });
                        } catch (e) {}
                    }

                    // Listen for physical keyboard presses
                    window.addEventListener('keydown', (e) => {
                        const keyMap = {
                            'w': 'w', 's': 's', 'a': 'a', 'd': 'd', 
                            ' ': 'f', 'Enter': 'f', 'f': 'f'
                        };
                        const cmd = keyMap[e.key.toLowerCase()] || keyMap[e.key];
                        if (cmd) {
                            sendInput(cmd);
                            e.preventDefault(); // Stop page from scrolling
                        }
                    });

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
                <div class="controls">WASD to Move | Space/F to Interact/Fire</div>
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
