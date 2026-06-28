"""
Ultra-Lightweight GPIO Web Server
Runs on Raspberry Pi to expose physical pins to the Web Assistant.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import sys

# Attempt to load Raspberry Pi hardware libraries
try:
    from gpiozero import LED
    # Set this to the physical GPIO pin your LED is connected to (Default: GPIO 18)
    my_led = LED(18)
    has_hardware = True
    print("Hardware detected! Bound to GPIO 18.")
except ImportError:
    print("Warning: 'gpiozero' not found. Running in mock/simulation mode.")
    has_hardware = False
    mock_state = False

app = Flask(__name__)
# Enable CORS so your web browser can send requests to the Pi
CORS(app)

@app.route('/led/<action>', methods=['GET'])
def control_led(action):
    global mock_state
    
    if action == "on":
        if has_hardware:
            my_led.on()
        else:
            mock_state = True
        print("-> LED turned ON")
        return jsonify({"status": "success", "state": "on"})
        
    elif action == "off":
        if has_hardware:
            my_led.off()
        else:
            mock_state = False
        print("-> LED turned OFF")
        return jsonify({"status": "success", "state": "off"})
        
    elif action == "flash":
        if has_hardware:
            # blink() automatically handles background thread intervals in gpiozero
            my_led.blink(on_time=0.5, off_time=0.5)
        else:
            mock_state = "flashing"
        print("-> LED FLASHING (0.5s intervals)")
        return jsonify({"status": "success", "state": "flashing"})
        
    else:
        return jsonify({"status": "error", "message": "Invalid command"}), 400

if __name__ == '__main__':
    # Run on port 5001 to avoid conflicting with the STT server on port 5000
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=False)