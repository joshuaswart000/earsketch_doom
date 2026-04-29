from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Vital for EarSketch connection

# The Game World: #=Wall, .=Floor, E=Enemy
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

@app.route('/move', methods=['POST', 'OPTIONS'])
def move():
    global player_pos
    if request.method == 'OPTIONS':
        return '', 200

    # Flexible data collection: Works for JSON or Form data
    data = request.get_json(silent=True) or request.form
    
    if not data:
        return jsonify({"ascii_map": "Waiting for input...", "event": "idle"})
    
    cmd = data.get('input', '').lower()
    event_type = "idle"
    
    # Calculate new potential position
    new_r, new_c = player_pos[0], player_pos[1]

    if cmd == 'w': new_r -= 1
    elif cmd == 's': new_r += 1
    elif cmd == 'a': new_c -= 1
    elif cmd == 'd': new_c += 1
    elif cmd == 'f': event_type = "fire"

    # Bounds checking and collision
    if 0 <= new_r < len(game_map) and 0 <= new_c < len(game_map[0]):
        target_tile = game_map[new_r][new_c]
        
        if target_tile == ".":
            player_pos = [new_r, new_c]
            event_type = "step"
        elif target_tile == "E" and cmd == 'f':
            event_type = "hit_enemy"
            # Optional: game_map[new_r][new_c] = "." (to kill the enemy)

    # Render the ASCII frame
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
    # Render uses port 10000 by default for Python services
    app.run(host='0.0.0.0', port=10000)
