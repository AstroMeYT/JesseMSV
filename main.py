from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sock import Sock
from faster_whisper import WhisperModel
import numpy as np
import openwakeword
from openwakeword.model import Model
import os
import sys

app = Flask(__name__)
CORS(app) 
sock = Sock(app) # Enables High-Speed WebSocket Streaming

print("Loading Faster-Whisper Command Model...")
whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")

print("Loading OpenWakeWord Trigger Model...")
openwakeword.utils.download_models() # Ensure base models exist

if os.path.exists("neo.onnx"):
    print("Found neo.onnx! Loading custom Neo wake word...")
    oww_model = Model(wakeword_models=["neo.onnx"], inference_framework="onnx")
elif os.path.exists("neo.tflite"):
    print("Found neo.tflite! Loading custom Neo wake word...")
    oww_model = Model(wakeword_models=["neo.tflite"], inference_framework="tflite")
else:
    print("\n[CRITICAL ERROR] Wake word model not found!")
    print("Please place 'neo.onnx' or 'neo.tflite' in the same directory as this script.")
    sys.exit(1)

print("Models Loaded! System is now listening on 0.0.0.0:5000")

@sock.route('/wakeword')
def wakeword_stream(ws):
    """
    Persistent WebSocket connection. 
    Receives endless 8KB audio chunks with 0 HTTP overhead!
    """
    oww_model.reset()
    while True:
        data = ws.receive()
        
        # If the client stopped talking, reset the memory to prevent false alarms
        if isinstance(data, str) and data == "RESET":
            oww_model.reset()
            continue
            
        if not isinstance(data, str):
            audio_data = np.frombuffer(data, dtype=np.int16)
            
            detected = False
            for i in range(0, len(audio_data), 1280):
                chunk = audio_data[i:i+1280]
                if len(chunk) == 1280:
                    prediction = oww_model.predict(chunk)
                    for score in prediction.values():
                        if score > 0.5:
                            detected = True
                            break
                if detected:
                    break
                    
            if detected:
                ws.send('{"detected": true}')
                oww_model.reset()


@app.route('/transcribe', methods=['POST'])
def transcribe():
    """
    Standard HTTP Endpoint used AFTER the wake word is confirmed
    for the single payload command block.
    """
    try:
        pcm16_bytes = request.data
        audio_data = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        segments, info = whisper_model.transcribe(audio_data, beam_size=1, language="en")
        text = " ".join([segment.text for segment in segments]).strip()
        
        print(f"Transcribed Command: {text}")
        return jsonify({"text": text, "status": "success"})
    except Exception as e:
        print(f"Error processing audio: {e}")
        return jsonify({"text": "", "status": "error"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)