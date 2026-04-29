from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # This fixes the "Connection Error" in EarSketch

# The Game World
game_map = [
    ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
    ["#", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
    ["#", ".", "#", "#", ".", ".", "E", ".", ".", "#"],
    ["#", ".", ".", ".", ".", ".", ".", ".", ".", "#"],
    ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
]

player_pos = [1, 1]

@app.route('/')
def home():
    return "Doom Engine is Online! Ready for EarSketch."

@app.route('/move', methods=['POST'])
def move():
    global player_pos
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ascii_map": "No Data Received", "event": "idle"})
    
    cmd = data.get('input', '').lower()
    event_type = "idle"
    
    # Store old position to check for walls
    new_r, new_c = player_pos[0], player_pos[1]

    if cmd == 'w': new_r -= 1
    elif cmd == 's': new_r += 1
    elif cmd == 'a': new_c -= 1
    elif cmd == 'd': new_c += 1
    elif cmd == 'f': event_type = "fire"

    # Collision detection
    if game_map[new_r][new_c] == ".":
        player_pos = [new_r, new_c]
        event_type = "step"
    elif game_map[new_r][new_c] == "E" and cmd == 'f':
        event_type = "hit_enemy" # Future: remove enemy from map

    # Build the screen
    ascii_screen = ""
    for r in range(len(game_map)):
        row_str = ""
        for c in range(len(game_map[0])):
            if [r, c] == player_pos:
                row_str += "P"
            else:
                row_str += game_map[r][c]
        ascii_screen += row_str + "\n"

    return jsonify({
        "ascii_map": ascii_screen,
        "event": event_type
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
