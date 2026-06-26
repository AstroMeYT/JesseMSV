#!/usr/bin/env python3
"""
================================================================================
                    HEADLESS SMART ASSISTANT (PYTHON)
================================================================================
A pure Python, single-file smart assistant designed for headless devices 
(Raspberry Pi, local servers, etc.). 

Features:
  - Zero-Cost VAD: Uses SpeechRecognition to detect when you start speaking.
  - Local AI STT: Uses Faster-Whisper for high-speed, offline transcription.
  - Offline TTS: Uses pyttsx3 for voice responses.
  - Media Streaming: Uses VLC to play background internet radio.
  - NLP Routing: Timers, Weather, Wikipedia, Jokes, Math, and Notes.

Author: Gatlin Nicholson
================================================================================
"""

import os
import re
import time
import math
import random
import threading
import json
from datetime import datetime

# ==============================================================================
# DEPENDENCY IMPORTS & FALLBACKS
# ==============================================================================
try:
    import requests
except ImportError:
    print("CRITICAL: 'requests' module missing. Run: pip install requests")
    exit(1)

try:
    import pyttsx3
except ImportError:
    print("CRITICAL: 'pyttsx3' module missing. Run: pip install pyttsx3")
    exit(1)

try:
    import speech_recognition as sr
except ImportError:
    print("CRITICAL: 'SpeechRecognition' module missing. Run: pip install SpeechRecognition pyaudio")
    exit(1)

try:
    import numpy as np
    from faster_whisper import WhisperModel
except ImportError:
    print("CRITICAL: 'faster-whisper' module missing. Run: pip install faster-whisper")
    exit(1)

try:
    import vlc
except ImportError:
    print("WARNING: 'python-vlc' missing. Radio streaming will be disabled. Run: pip install python-vlc")
    vlc = None

try:
    import edge_tts
    import asyncio
    import pygame
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
    pygame.mixer.init()
    NEURAL_TTS_AVAILABLE = True
except ImportError:
    print("WARNING: 'edge-tts' or 'pygame' missing. Using robotic fallback. Run: pip install edge-tts pygame")
    NEURAL_TTS_AVAILABLE = False


# ==============================================================================
# SYSTEM STATE & CONFIGURATION
# ==============================================================================
WAKEWORD = "jesse"
USER_NAME = "Friend"
LOCATION_CITY = "Marshall, IL"

# Load notes from a local JSON file to persist across reboots
NOTES_FILE = "assistant_notes.json"
if os.path.exists(NOTES_FILE):
    with open(NOTES_FILE, "r") as f:
        local_notes = json.load(f)
else:
    local_notes = ["Buy groceries"]

# Media & Timers
media_player = vlc.MediaPlayer() if vlc else None
is_radio_playing = False
timer_threads = []

# Initialize Text-to-Speech Engine
print("[System] Initializing TTS Engine...")
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 175) # Slightly faster conversational speed

def speak(text):
    """Halts other audio, speaks the text, and restores state."""
    print(f"[Assistant]: {text}")
    # Lower radio volume if playing
    if media_player and is_radio_playing:
        media_player.audio_set_volume(30)
    
    if NEURAL_TTS_AVAILABLE:
        try:
            temp_file = "temp_speech.mp3"
            # Use a high-quality human neural voice (Free via Edge API)
            # Alternative voices: en-US-GuyNeural (Male), en-GB-SoniaNeural
            communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
            asyncio.run(communicate.save(temp_file))
            
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            try:
                # Cleanup audio file
                pygame.mixer.music.unload()
                os.remove(temp_file)
            except:
                pass
        except Exception as e:
            print(f"[Neural TTS Error]: {e}. Falling back to standard TTS.")
            tts_engine.say(text)
            tts_engine.runAndWait()
    else:
        tts_engine.say(text)
        tts_engine.runAndWait()
    
    if media_player and is_radio_playing:
        media_player.audio_set_volume(100)

# Initialize Faster-Whisper Model
print("[System] Loading Faster-Whisper Model (base.en)...")
# 'base.en' is fast and highly accurate. Change device="cuda" if you have an Nvidia GPU.
whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
print("[System] Whisper AI Ready.")


# ==============================================================================
# NLP HELPERS
# ==============================================================================
WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, 
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, 
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, 
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, 
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, 
    "hundred": 100
}

def parse_english_numbers(text):
    words = text.lower().replace("-", " ").split()
    result_words = []
    i = 0
    while i < len(words):
        word = words[i]
        if word in ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"] and i + 1 < len(words):
            next_word = words[i+1]
            if next_word in ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]:
                val = WORD_TO_NUM[word] + WORD_TO_NUM[next_word]
                result_words.append(str(val))
                i += 2
                continue
        if word in WORD_TO_NUM:
            result_words.append(str(WORD_TO_NUM[word]))
        else:
            result_words.append(word)
        i += 1
    return " ".join(result_words)

def parse_duration_to_seconds(text):
    normalized = parse_english_numbers(text)
    hours, minutes, seconds = 0, 0, 0
    
    h_match = re.search(r'(\d+)\s*(?:hour|hr|h)', normalized)
    m_match = re.search(r'(\d+)\s*(?:minute|min|m)', normalized)
    s_match = re.search(r'(\d+)\s*(?:second|sec|s)', normalized)
    
    if h_match: hours = int(h_match.group(1))
    if m_match: minutes = int(m_match.group(1))
    if s_match: seconds = int(s_match.group(1))
    
    if not (h_match or m_match or s_match):
        digits = [int(s) for s in normalized.split() if s.isdigit()]
        if len(digits) == 1:
            seconds = digits[0]
            
    return (hours * 3600) + (minutes * 60) + seconds

def calculate_equation(text):
    cleaned = text.lower().replace("calculate", "").replace("what is", "").replace("solve", "").strip()
    cleaned = parse_english_numbers(cleaned)
    
    operators = {
        "plus": "+", "minus": "-", "multiplied by": "*", "multiply": "*",
        "times": "*", "divided by": "/", "divide": "/", "over": "/", "x": "*"
    }
    for word, op in operators.items():
        cleaned = cleaned.replace(word, op)
        
    cleaned = re.sub(r'[^0-9\+\-\*\/\(\)\s\.]', '', cleaned)
    try:
        if not cleaned.strip(): return None, None
        result = eval(cleaned, {"__builtins__": None}, {})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return cleaned, result
    except:
        return cleaned, None


# ==============================================================================
# SKILL EXECUTORS
# ==============================================================================
def get_weather(city_name):
    try:
        # Geocode
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
        geo_data = requests.get(geo_url, timeout=5).json()[0]
        lat, lon = geo_data['lat'], geo_data['lon']
        
        # Open-Meteo
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=auto&forecast_days=1"
        data = requests.get(weather_url, timeout=5).json()
        
        temp = round(data['current']['temperature_2m'])
        high = round(data['daily']['temperature_2m_max'][0])
        low = round(data['daily']['temperature_2m_min'][0])
        
        # Simplified condition mapping
        code = data['current']['weather_code']
        if code <= 3: condition = "clear or cloudy"
        elif code <= 48: condition = "foggy"
        elif code <= 67: condition = "raining"
        elif code <= 77: condition = "snowing"
        else: condition = "stormy"
        
        speak(f"Currently in {city_name}, it is {temp} degrees and {condition}. Today's high is {high} with a low of {low}.")
    except Exception as e:
        print(f"Weather error: {e}")
        speak("I couldn't reach the weather network.")

def get_wikipedia(query):
    speak(f"Searching Wikipedia for {query}...")
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            extract = data.get("extract", "No description found.")
            summary = ". ".join(extract.split(".")[:2]) + "."
            speak(f"From Wikipedia: {summary}")
        else:
            speak(f"I couldn't find an article for {query}.")
    except Exception:
        speak("I'm having trouble connecting to Wikipedia.")

def get_joke():
    try:
        data = requests.get('https://v2.jokeapi.dev/joke/Any?blacklistFlags=nsfw,religious,political,racist,sexist,explicit', timeout=5).json()
        if data['type'] == 'twopart':
            speak(f"{data['setup']} ... {data['delivery']}")
        else:
            speak(data['joke'])
    except:
        speak("Why did the Python programmer quit his job? Because he didn't get arrays!")

def start_timer(seconds):
    def timer_worker(sec):
        time.sleep(sec)
        # Play terminal bell and speak
        print('\a\a\a') 
        speak("Beep beep! Your countdown timer is up!")
    
    t = threading.Thread(target=timer_worker, args=(seconds,), daemon=True)
    t.start()
    timer_threads.append(t)
    speak(f"I've set a timer for {seconds} seconds.")

def stream_radio(query):
    global is_radio_playing
    if not vlc:
        speak("Radio streaming is disabled because the VLC library is missing.")
        return
        
    speak(f"Searching public directories for {query}...")
    try:
        url = f"https://all.api.radio-browser.info/json/stations/search?limit=1&order=clickcount&reverse=true&hidebroken=true&name={query}"
        data = requests.get(url, timeout=5).json()
        
        if data:
            station = data[0]
            speak(f"Tuning into {station['name']}.")
            media_player.set_mrl(station['url_resolved'])
            media_player.play()
            is_radio_playing = True
        else:
            speak(f"I couldn't find a broadcast for {query}.")
    except Exception as e:
        print(f"Radio API Error: {e}")
        speak("I had trouble connecting to the radio network.")


# ==============================================================================
# CORE ROUTER
# ==============================================================================
def process_command(text):
    """Routes the transcribed text to the correct Python skill."""
    clean_cmd = text.lower().strip()
    
    # Strip the wakeword from the beginning if it exists
    if clean_cmd.startswith(WAKEWORD):
        clean_cmd = clean_cmd[len(WAKEWORD):].strip()
        
    # Remove leading punctuation
    clean_cmd = re.sub(r'^[^a-zA-Z0-9]+', '', clean_cmd).strip()

    if not clean_cmd:
        speak("Yes?")
        return

    print(f"[Router] Evaluating Command: '{clean_cmd}'")

    if "time" in clean_cmd or "date" in clean_cmd:
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d")
        speak(f"It is {time_str} on {date_str}.")
        
    elif "weather" in clean_cmd or "forecast" in clean_cmd:
        get_weather(LOCATION_CITY)
        
    elif "calculate" in clean_cmd or "plus" in clean_cmd or "minus" in clean_cmd:
        eq, ans = calculate_equation(clean_cmd)
        if ans is not None:
            speak(f"The answer is {ans}.")
        else:
            speak("I couldn't parse that math equation.")
            
    elif "timer" in clean_cmd:
        seconds = parse_duration_to_seconds(clean_cmd)
        if seconds > 0:
            start_timer(seconds)
        else:
            speak("How long should I set the timer for?")
            
    elif "flip" in clean_cmd and "coin" in clean_cmd:
        speak(f"I flipped a coin and got {random.choice(['Heads', 'Tails'])}!")
        
    elif "note" in clean_cmd or "remember" in clean_cmd:
        if "read" in clean_cmd or "list" in clean_cmd:
            if local_notes:
                speak(f"Your notes are: {', '.join(local_notes)}")
            else:
                speak("You don't have any notes.")
        else:
            content = re.sub(r'\b(write a note|remember that|note to)\b', '', clean_cmd, flags=re.IGNORECASE).strip()
            if content:
                local_notes.append(content)
                with open(NOTES_FILE, "w") as f:
                    json.dump(local_notes, f)
                speak("I've saved your note.")
            else:
                speak("What would you like me to note?")
                
    elif "radio" in clean_cmd or "play" in clean_cmd or "music" in clean_cmd:
        global is_radio_playing
        if "stop" in clean_cmd or "pause" in clean_cmd:
            if media_player and is_radio_playing:
                media_player.stop()
                is_radio_playing = False
                speak("Playback stopped.")
            else:
                speak("Nothing is currently playing.")
        else:
            query = re.sub(r'\b(play|listen to|stream)\b', '', clean_cmd, flags=re.IGNORECASE).strip()
            if not query or query == "radio" or query == "music":
                query = "classic fm"
            stream_radio(query)
            
    elif "wikipedia" in clean_cmd or "who is" in clean_cmd or "what is" in clean_cmd:
        query = re.sub(r'\b(wikipedia|search for|tell me about|who is|what is)\b', '', clean_cmd, flags=re.IGNORECASE).strip()
        get_wikipedia(query)
        
    elif "joke" in clean_cmd or "funny" in clean_cmd:
        get_joke()
        
    elif "sleep" in clean_cmd:
        speak("I am a headless assistant. I run continuously in the background.")
        
    else:
        speak("I didn't quite catch that. You can ask for weather, timers, Wikipedia, or internet radio.")


# ==============================================================================
# MAIN MICROPHONE LOOP (VAD + WHISPER)
# ==============================================================================
def run_assistant():
    recognizer = sr.Recognizer()
    # Optimize VAD parameters for snappier responses
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 300 
    recognizer.pause_threshold = 1.0 # Seconds of silence before finalizing chunk
    
    print("\n=======================================================")
    print(" Headless Assistant is Online & Listening")
    print(f" Wake Word: '{WAKEWORD.upper()}'")
    print("=======================================================\n")
    speak(f"System online. Listening for wake word: {WAKEWORD}.")

    with sr.Microphone() as source:
        # Calibrate background noise
        recognizer.adjust_for_ambient_noise(source, duration=2.0)
        
        while True:
            try:
                # 1. Listen for audio (This blocks CPU efficiently until volume spikes)
                audio_chunk = recognizer.listen(source, phrase_time_limit=10)
                
                # 2. Extract raw bytes and normalize for Whisper (Float32, 16000Hz)
                raw_data = audio_chunk.get_raw_data(convert_rate=16000, convert_width=2)
                np_audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # 3. Fast STT Transcription
                segments, info = whisper_model.transcribe(np_audio, beam_size=1, language="en")
                transcribed_text = " ".join([segment.text for segment in segments]).strip().lower()
                
                # Strip out Whisper hallucinations
                transcribed_text = re.sub(r'\[.*?\]|\(.*?\)', '', transcribed_text).strip()
                
                if not transcribed_text:
                    continue

                # 4. Check for Wake Word
                if transcribed_text.startswith(WAKEWORD) or WAKEWORD in transcribed_text:
                    print(f"\n[Command Received]: {transcribed_text}")
                    process_command(transcribed_text)
                else:
                    # Ignore background chatter that didn't include the wake word
                    print(f"[Ignored Background]: {transcribed_text}")
                    
            except sr.WaitTimeoutError:
                continue # Loop quietly
            except KeyboardInterrupt:
                print("\n[System] Shutting down...")
                break
            except Exception as e:
                print(f"[Error in Mic Loop]: {e}")

if __name__ == "__main__":
    run_assistant()