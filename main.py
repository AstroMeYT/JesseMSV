from flask import Flask, request, jsonify
from flask_cors import CORS
from faster_whisper import WhisperModel
import numpy as np

app = Flask(__name__)
# Allow your local HTML file to securely talk to this Python server
CORS(app) 

# Load the AI model into memory. 
# "base.en" is a great balance of blazing fast speed and high accuracy. 
# If you have a dedicated GPU, change device to "cuda".
print("Loading Faster-Whisper AI Model...")
model = WhisperModel("base.en", device="cpu", compute_type="int8")
print("Model Loaded! System is now listening on http://127.0.0.1:5000")

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        # The HTML frontend sends us raw PCM16 audio bytes
        pcm16_bytes = request.data
        
        # Whisper expects a normalized float32 numpy array at 16000Hz
        audio_data = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Run the audio through the local Whisper model
        # beam_size=1 makes it slightly faster but less accurate. Change to 5 for better accuracy.
        segments, info = model.transcribe(audio_data, beam_size=1, language="en")
        
        # Combine all transcribed segments into a single string
        text = " ".join([segment.text for segment in segments]).strip()
        print(f"Transcribed Command: {text}")

        return jsonify({"text": text, "status": "success"})

    except Exception as e:
        print(f"Error processing audio: {e}")
        return jsonify({"text": "", "status": "error"}), 500

if __name__ == '__main__':
    # Run the server on port 5000
    app.run(host='127.0.0.1', port=5000, debug=False)