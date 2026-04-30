import subprocess
import os
import threading
import pty
import base64
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
                stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, close_fds=True,
                env={"TERM": "xterm-256color", "COLUMNS": "80", "LINES": "25"}
            )
            
            def kickstart():
                import time
                for _ in range(3):
                    time.sleep(3)
                    os.write(self.master_fd, b" \n")
            
            threading.Thread(target=kickstart, daemon=True).start()
            threading.Thread(target=self._stream_output, daemon=True).start()
        except Exception as e:
            print(f"Error: {e}")

    def _stream_output(self):
        while True:
            try:
                # Read raw bytes instead of text
                data = os.read(self.master_fd, 10240)
                if data:
                    # Encode to Base64 to safely move binary ANSI codes to the browser
                    self.output_b64 = base64.b64encode(data).decode('utf-8')
            except:
                break

    def send_key(self, key):
        try:
            if self.process.poll() is None:
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
            </head>
            <body style="background:#000; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; margin:0;">
                <div id="terminal" style="width:640px; height:400px; border:2px solid #00FF00;"></div>
                <script>
                    const term = new Terminal({cols: 80, rows: 25, theme: {background:'#000', foreground:'#0F0'}, convertEol:true});
                    term.open(document.getElementById('terminal'));

                    async function update() {
                        const res = await fetch('/move', {method:'POST', body:JSON.stringify({input:''}), headers:{'Content-Type':'application/json'}});
                        const data = await res.json();
                        if (data.ascii_map) {
                            // 1. Fully wipe the terminal's internal state
                            term.clear();
                            term.reset();
                            // 2. Move cursor to 0,0 manually just in case
                            term.write('\x1b[H'); 

                            const raw = atob(data.ascii_map);
                            const bytes = new Uint8Array(raw.length);
                            for(let i=0; i<raw.length; i++) bytes[i] = raw.charCodeAt(i);
                            
                            // 3. Write the new frame
                            term.write(bytes);
                        }
                    }
                    setInterval(update, 100);

                    window.addEventListener('keydown', e => {
                        const keys = {'w':'w','a':'a','s':'s','d':'d',' ':'f','f':'f'};
                        if(keys[e.key]) fetch('/move', {method:'POST', body:JSON.stringify({input:keys[e.key]}), headers:{'Content-Type':'application/json'}});
                    });
                </script>
            </body>
        </html>
    ''')

@app.route('/move', methods=['POST'])
def move():
    data = request.get_json() or {}
    user_input = data.get('input', '')
    if user_input:
        game.send_key(user_input)
    
    # Send BOTH formats: Base64 for the web terminal, and Plain Text for EarSketch
    raw_text = base64.b64decode(game.output_b64).decode('utf-8', errors='ignore')
    return jsonify({
        "ascii_map": game.output_b64, 
        "plain_text": raw_text
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
