from flask import Flask, request, jsonify
from flask_cors import CORS # Add this

app = Flask(__name__)
CORS(app) # Add this

# A simple 2D map: # is wall, . is floor
game_map = [
    ["#", "#", "#", "#", "#", "#", "#"],
    ["#", ".", ".", ".", ".", ".", "#"],
    ["#", ".", ".", ".", ".", ".", "#"],
    ["#", "#", "#", "#", "#", "#", "#"],
]

player_pos = [1, 1]

@app.route('/')
def home():
    return "Doom Engine is Awake!"

@app.route('/move', methods=['POST'])
def move():
    global player_pos
    data = request.get_json()
    cmd = data.get('input', '').lower()
    
    # Simple logic: W=Up, S=Down, A=Left, D=Right
    if cmd == 'w' and game_map[player_pos[0]-1][player_pos[1]] == ".":
        player_pos[0] -= 1
    elif cmd == 's' and game_map[player_pos[0]+1][player_pos[1]] == ".":
        player_pos[0] += 1
    # ... (you can add A and D logic here)

    # Build the ASCII string to send back
    ascii_screen = ""
    for r in range(len(game_map)):
        row_str = ""
        for c in range(len(game_map[0])):
            if [r, c] == player_pos:
                row_str += "P" # Player icon
            else:
                row_str += game_map[r][c]
        ascii_screen += row_str + "\n"

    return jsonify({
        "ascii_map": ascii_screen,
        "event": "step" if cmd else "idle"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
