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
        if not os.path.exists(DOOM_PATH):
            return

        try:
            self.master_fd, slave_fd = pty.openpty()
            self.process = subprocess.Popen(
                [DOOM_PATH, "-iwad", WAD_PATH, "-nocolor", "-i", "-nosound", "-nodraw", "-warp", "1", "1"],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25"}
            )
            
            def kickstart():
                time.sleep(10) # Wait for engine to breathe
                os.write(self.master_fd, b"y\n\n")
            
            threading.Thread(target=kickstart, daemon=True).start()
            # FIX: Ensure this method exists below!
            threading.Thread(target=self._stream_output, daemon=True).start()
        except Exception as e:
            print(f"Init Error: {e}")

    def _stream_output(self):
        while True:
            try:
                # Read from the terminal master
                data = os.read(self.master_fd, 10240)
                if data:
                    self.output_b64 = base64.b64encode(data).decode('utf-8')
            except:
                break

    def send_key(self, key):
        try:
            if self.process.poll() is None:
                # Map 'f' to Space for EarSketch, and 'Enter' to \n
                if key == 'f': key = ' '
                if key == 'Enter': key = '\n'
                
                # We use os.write, but let's make sure we send a newline 
                # if the engine is stuck in a prompt
                os.write(self.master_fd, key.encode())
                # No flush needed for os.write on a pty, but let's be sure
        except Exception as e:
            print(f"Input Error: {e}")

game = DoomGame()

@app.route('/')
def index():
    return render_template_string('''
        <html>
            <head>
                <title>EarSketch Doom Terminal</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css" />
                <script src="https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js"></script>
            </head>
            <body style="background:#000; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; margin:0;">
                <div id="terminal" style="width:640px; height:400px; border:2px solid #00FF00;"></div>
                <div style="color:#0F0; margin-top:10px; font-family:monospace; text-align:center;">
                    WASD: Move | SPACE: Fire | Y: License<br>
                    Status: <span id="status">Connecting...</span>
                </div>
                <script>
                    const term = new Terminal({cols: 80, rows: 25, theme: {background:'#000', foreground:'#0F0'}, convertEol:true});
                    term.open(document.getElementById('terminal'));

                    async function update() {
                        try {
                            const res = await fetch('/map');
                            const data = await res.json();
                            if (data.ascii_map) {
                                term.clear();
                                term.reset();
                                term.write('\\x1b[H');
                                const raw = atob(data.ascii_map);
                                const bytes = new Uint8Array(raw.length);
                                for(let i=0; i<raw.length; i++) bytes[i] = raw.charCodeAt(i);
                                term.write(bytes);
                                document.getElementById('status').innerText = "Live";
                            }
                        } catch(e) {}
                    }
                    setInterval(update, 200);

                    window.addEventListener('keydown', e => {
                        const keys = {'w':'w','a':'a','s':'s','d':'d',' ':'f','f':'f','y':'y','Enter':'\\n'};
                        const val = keys[e.key] || keys[e.key.toLowerCase()];
                        if(val) {
                            fetch('/move', {
                                method:'POST', 
                                body:JSON.stringify({input:val}), 
                                headers:{'Content-Type':'application/json'}
                            });
                        }
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
    user_input = data.get('input', '')
    if user_input:
        game.send_key(user_input)
    return jsonify({"status": "sent"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
