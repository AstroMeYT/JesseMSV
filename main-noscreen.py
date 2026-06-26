#!/usr/bin/env python3
"""
================================================================================
                    HEADLESS SMART ASSISTANT (PYTHON)
================================================================================
A pure Python, single-file smart assistant designed for headless devices 
(Raspberry Pi, local servers, etc.). 

Features:
  - Zero-Cost VAD: Uses SpeechRecognition to detect when you start speaking.
  - Local AI STT: Uses Faster-Whisper or Vosk for speed & lightweight execution.
  - Threaded TTS: Dedicated audio queue prevents UI/Mic freezing.
  - Media Streaming: Uses VLC to play background internet radio.
  - NLP Routing: Good Morning, Weather, Wiki, Radio, Timers, Math, and Notes.
  - Optional GUI: Run with `--gui` to open a debug console and text-input window.

Author: Gatlin Nicholson
================================================================================
"""

import os
import sys
import re
import time
import math
import random
import threading
import queue
import json
from datetime import datetime

# ==============================================================================
# DEPENDENCY IMPORTS & FALLBACKS
# ==============================================================================
try:
    import requests
except ImportError:
    print("CRITICAL: 'requests' module missing. Run: pip install requests")
    sys.exit(1)

try:
    import pyttsx3
except ImportError:
    print("CRITICAL: 'pyttsx3' module missing. Run: pip install pyttsx3")
    sys.exit(1)

try:
    import speech_recognition as sr
except ImportError:
    print("CRITICAL: 'SpeechRecognition' module missing. Run: pip install SpeechRecognition pyaudio")
    sys.exit(1)

try:
    import numpy as np
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False

try:
    import vosk
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

if not FASTER_WHISPER_AVAILABLE and not VOSK_AVAILABLE:
    print("CRITICAL: No STT engine found. Install either faster-whisper or vosk.")
    sys.exit(1)

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

# GUI Dependencies
try:
    import tkinter as tk
    from tkinter import scrolledtext
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False


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
media_player = None
is_radio_playing = False
timer_threads = []

# Safely initialize VLC. Catches the NameError if OS-level libvlc is missing.
if vlc:
    try:
        media_player = vlc.MediaPlayer()
    except NameError as e:
        print(f"WARNING: System VLC library (libvlc) is missing or broken. Radio disabled. ({e})")
        print("         Please install VLC on your OS (e.g., 'sudo apt install vlc').")
        vlc = None
    except Exception as e:
        print(f"WARNING: VLC initialization failed. Radio disabled. ({e})")
        vlc = None


# ==============================================================================
# DEDICATED AUDIO & TTS QUEUE (Prevents App Freezing!)
# ==============================================================================
tts_queue = queue.Queue()

def tts_worker():
    """Background thread that guarantees smooth speech without freezing the mic"""
    print("[System] Initializing TTS Engine...")
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate', 175) 
    
    # Create a dedicated, persistent asyncio loop for this thread to prevent segfaults
    if NEURAL_TTS_AVAILABLE:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    while True:
        text = tts_queue.get()
        if text is None: break
        
        print(f"[Assistant]: {text}")
        if media_player and is_radio_playing:
            media_player.audio_set_volume(30)
        
        if NEURAL_TTS_AVAILABLE:
            try:
                temp_file = "temp_speech.mp3"
                communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
                # Run the TTS generation using our persistent, safe event loop
                loop.run_until_complete(communicate.save(temp_file))
                
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
                
                try:
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
            
        tts_queue.task_done()

# Start TTS Queue Processor
threading.Thread(target=tts_worker, daemon=True).start()

def speak(text):
    """Puts text into the background speech queue instantly."""
    tts_queue.put(text)


# ==============================================================================
# INITIALIZE AI (Auto-Select Engine based on Hardware)
# ==============================================================================
def get_system_specs():
    """Detects System RAM and CPU cores to dynamically scale AI performance."""
    ram_gb = 2.0 # Default fallback
    cores = 2
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024**3)
        cores = psutil.cpu_count(logical=False) or 2
    except ImportError:
        try:
            # Linux specific fallback if psutil is not installed
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        ram_gb = int(line.split()[1]) / (1024**2)
                        break
            import multiprocessing
            cores = multiprocessing.cpu_count()
        except Exception:
            pass
    return ram_gb, cores

sys_ram, sys_cores = get_system_specs()
print(f"[System] Detected Hardware: {sys_ram:.1f} GB RAM | {sys_cores} CPU Cores")

if sys_ram < 1.5:
    print("[System] Low RAM detected (< 1.5GB). Optimizing for Raspberry Pi / Low-end device.")
    if VOSK_AVAILABLE:
        ACTIVE_STT_ENGINE = "vosk"
    elif FASTER_WHISPER_AVAILABLE:
        print("[System] WARNING: Vosk is highly recommended for this hardware but not installed.")
        print("[System] Falling back to Whisper (Expect heavy lag/SD card swapping).")
        ACTIVE_STT_ENGINE = "whisper"
else:
    print("[System] High RAM detected. Optimizing for speed & accuracy.")
    if FASTER_WHISPER_AVAILABLE:
        ACTIVE_STT_ENGINE = "whisper"
    elif VOSK_AVAILABLE:
        print("[System] WARNING: Faster-Whisper is recommended for this hardware but not installed. Falling back to Vosk.")
        ACTIVE_STT_ENGINE = "vosk"

whisper_model = None
vosk_model = None

if ACTIVE_STT_ENGINE == "whisper":
    print("[System] Loading Faster-Whisper Model (base.en)...")
    whisper_model = WhisperModel("base.en", device="cpu", compute_type="int8")
    print("[System] Whisper AI Ready.")
else:
    print("[System] Loading Vosk Lightweight Acoustic Model...")
    vosk.SetLogLevel(-1) # Hide verbose kaldi logs
    try:
        vosk_model = vosk.Model(lang="en-us") 
    except Exception as e:
        print("\nCRITICAL: Vosk model missing! Older versions of Vosk require a downloaded model folder.")
        print("To fix: Download the small english model from https://alphacephei.com/vosk/models")
        print("Extract it into the same folder as this script and rename it to 'model'.")
        sys.exit(1)
    print("[System] Vosk AI Ready.")


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
        # Require User-Agent to prevent 403 Forbidden from modern Weather/Geo APIs
        headers = {'User-Agent': 'JesseAssistant/1.0 (contact: admin@jesseassistant.local)'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&limit=1"
        geo_data = requests.get(geo_url, headers=headers, timeout=5).json()[0]
        lat, lon = geo_data['lat'], geo_data['lon']
        
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

def run_good_morning_sequence():
    speak(f"Good morning, {USER_NAME}. Let me look up today's headlines...")
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    
    # 1. Weather
    weather_str = "I'm still loading the weather data."
    try:
        headers = {'User-Agent': 'JesseAssistant/1.0 (contact: admin@jesseassistant.local)'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={LOCATION_CITY}&format=json&limit=1"
        geo_data = requests.get(geo_url, headers=headers, timeout=5).json()[0]
        lat, lon = geo_data['lat'], geo_data['lon']
        
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&daily=weather_code,temperature_2m_max,temperature_2m_min&temperature_unit=fahrenheit&timezone=auto&forecast_days=1"
        data = requests.get(weather_url, timeout=5).json()
        temp = round(data['current']['temperature_2m'])
        high = round(data['daily']['temperature_2m_max'][0])
        low = round(data['daily']['temperature_2m_min'][0])
        weather_str = f"Currently in {LOCATION_CITY}, it is {temp} degrees. Today's high is {high} with a low of {low}."
    except Exception:
        pass
        
    # 2. News
    news_str = "I couldn't load the latest news right now."
    try:
        rss_url = "http://feeds.bbci.co.uk/news/world/rss.xml"
        news_res = requests.get(f"https://api.rss2json.com/v1/api.json?rss_url={rss_url}", timeout=5).json()
        if 'items' in news_res and len(news_res['items']) >= 2:
            h1 = news_res['items'][0]['title']
            h2 = news_res['items'][1]['title']
            news_str = f"Here are the top global stories: First, {h1}. Second, {h2}."
    except Exception:
        pass
        
    full_speech = f"It is currently {time_str}. {weather_str} {news_str} Have a wonderful day!"
    speak(full_speech)

def get_wikipedia(query):
    speak(f"Searching Wikipedia for {query}...")
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}"
        # FIX: Explicit User-Agent header bypasses Wikipedia's strict request blockers
        headers = {'User-Agent': 'JesseAssistant/1.0 (contact: admin@jesseassistant.local)'}
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            extract = data.get("extract", "No description found.")
            summary = ". ".join(extract.split(".")[:2]) + "."
            speak(f"From Wikipedia: {summary}")
        else:
            speak(f"I couldn't find an article for {query}.")
    except Exception as e:
        print(f"Wikipedia Error: {e}")
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
        
    speak(f"Searching radio directories for {query}...")
    try:
        url = f"https://all.api.radio-browser.info/json/stations/search?limit=5&order=clickcount&reverse=true&hidebroken=true"
        
        # Check by name first
        data = requests.get(f"{url}&name={query}", timeout=5).json()
        
        # Fallback to tag/genre search if name yields no results (fixes "Michael Jackson" queries)
        if not data:
            data = requests.get(f"{url}&tagList={query}", timeout=5).json()
            
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
# CORE ROUTER (Threaded to prevent app freezing!)
# ==============================================================================
def _process_command_logic(text):
    """Internal router executing inside a background thread."""
    clean_cmd = text.lower().strip()
    
    if clean_cmd.startswith(WAKEWORD):
        clean_cmd = clean_cmd[len(WAKEWORD):].strip()
        
    clean_cmd = re.sub(r'^[^a-zA-Z0-9]+', '', clean_cmd).strip()

    if not clean_cmd:
        speak("Yes?")
        return

    print(f"[Router] Evaluating Command: '{clean_cmd}'")

    if re.search(r'\b(good morning|morning sequence|wake up sequence)\b', clean_cmd):
        run_good_morning_sequence()
        
    elif re.search(r'\b(time|date|clock)\b', clean_cmd):
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        date_str = now.strftime("%A, %B %d")
        speak(f"It is {time_str} on {date_str}.")
        
    elif re.search(r'\b(weather|temperature|forecast)\b', clean_cmd) and not re.search(r'\b(watch|play|stream|tv|radio)\b', clean_cmd):
        get_weather(LOCATION_CITY)
        
    elif re.search(r'\b(calculate|plus|minus|times|divided)\b', clean_cmd) or ("what is" in clean_cmd and ("plus" in clean_cmd or "minus" in clean_cmd)):
        eq, ans = calculate_equation(clean_cmd)
        if ans is not None:
            speak(f"The answer is {ans}.")
        else:
            speak("I couldn't parse that math equation.")
            
    elif re.search(r'\b(timer|second|minute|hour)\b', clean_cmd):
        seconds = parse_duration_to_seconds(clean_cmd)
        if seconds > 0:
            start_timer(seconds)
        else:
            speak("How long should I set the timer for?")
            
    elif re.search(r'\b(flip|toss)\b', clean_cmd) and re.search(r'\b(coin)\b', clean_cmd):
        speak(f"I flipped a coin and got {random.choice(['Heads', 'Tails'])}!")
        
    elif re.search(r'\b(note|remember|write)\b', clean_cmd):
        if re.search(r'\b(read|list|show)\b', clean_cmd):
            if local_notes:
                speak(f"Your notes are: {', '.join(local_notes)}")
            else:
                speak("You don't have any notes.")
        else:
            content = re.sub(r'\b(write a note|remember that|note to|write down)\b', '', clean_cmd, flags=re.IGNORECASE).strip()
            if content:
                local_notes.append(content)
                with open(NOTES_FILE, "w") as f:
                    json.dump(local_notes, f)
                speak("I've saved your note.")
            else:
                speak("What would you like me to note?")
                
    elif re.search(r'\b(radio|music|stream|play|listen to)\b', clean_cmd):
        global is_radio_playing
        if re.search(r'\b(stop|pause|turn off)\b', clean_cmd):
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
            
    elif re.search(r'\b(wikipedia|wiki|search for|tell me about|who is|what is)\b', clean_cmd):
        query = re.sub(r'\b(wikipedia|wiki|search for|search|tell me about|who is|what is)\b(\s+for|\s+on|\s+about)?\s+', '', clean_cmd, flags=re.IGNORECASE).strip()
        get_wikipedia(query)
        
    elif re.search(r'\b(joke|funny)\b', clean_cmd):
        get_joke()
        
    elif re.search(r'\b(sleep|sleep mode)\b', clean_cmd):
        speak("I am a headless assistant. I run continuously in the background.")
        
    else:
        speak("I didn't quite catch that. You can ask for weather, timers, Wikipedia, or internet radio.")

def process_command(text):
    """Spawns a background thread to process NLP intents instantly without freezing the Mic Loop!"""
    threading.Thread(target=_process_command_logic, args=(text,), daemon=True).start()


# ==============================================================================
# MAIN MICROPHONE LOOP (VAD + WHISPER)
# ==============================================================================
def run_assistant():
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.energy_threshold = 300 
    recognizer.pause_threshold = 1.0 
    
    print("\n=======================================================")
    print(" Headless Assistant is Online & Listening")
    print(f" Wake Word: '{WAKEWORD.upper()}'")
    print("=======================================================\n")
    speak(f"System online. Listening for wake word: {WAKEWORD}.")

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=2.0)
            
            while True:
                try:
                    audio_chunk = recognizer.listen(source, phrase_time_limit=10)
                    raw_data = audio_chunk.get_raw_data(convert_rate=16000, convert_width=2)
                    
                    if ACTIVE_STT_ENGINE == "whisper":
                        np_audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                        segments, info = whisper_model.transcribe(np_audio, beam_size=1, language="en")
                        transcribed_text = " ".join([segment.text for segment in segments]).strip().lower()
                        transcribed_text = re.sub(r'\[.*?\]|\(.*?\)', '', transcribed_text).strip()
                    else:
                        # VOSK Lightweight Transcription Routing
                        rec = vosk.KaldiRecognizer(vosk_model, 16000)
                        rec.AcceptWaveform(raw_data)
                        res = json.loads(rec.FinalResult())
                        transcribed_text = res.get("text", "").strip().lower()
                    
                    if not transcribed_text:
                        continue

                    if transcribed_text.startswith(WAKEWORD) or WAKEWORD in transcribed_text:
                        print(f"\n[Command Received]: {transcribed_text}")
                        process_command(transcribed_text)
                    else:
                        print(f"[Ignored Background]: {transcribed_text}")
                        
                except sr.WaitTimeoutError:
                    continue 
                except Exception as e:
                    print(f"[Error in Mic Loop]: {e}")
    except Exception as e:
        print(f"\n[Mic Error]: Could not access microphone hardware ({e}).")
        print("Assistant is running, but will only respond to text commands (if --gui is active).")


# ==============================================================================
# OPTIONAL GUI DEBUGGER (--gui)
# ==============================================================================
def run_gui_console():
    if not TKINTER_AVAILABLE:
        print("CRITICAL: 'tkinter' module missing. Please install python3-tk via your package manager.")
        sys.exit(1)
        
    root = tk.Tk()
    root.title("Jesse Smart Assistant - Live Console")
    root.geometry("650x450")
    root.configure(bg="#1e1e1e")
    
    console_txt = scrolledtext.ScrolledText(root, state=tk.DISABLED, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10), bd=0, highlightthickness=0)
    console_txt.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    
    # THREAD-SAFE GUI LOGGING: Prevents Tkinter Segmentation Faults!
    log_queue = queue.Queue()
    
    def process_gui_logs():
        """Safely pulls print statements from background threads into the GUI"""
        while not log_queue.empty():
            s = log_queue.get()
            console_txt.config(state=tk.NORMAL)
            console_txt.insert(tk.END, s)
            console_txt.see(tk.END)
            console_txt.config(state=tk.DISABLED)
        root.after(50, process_gui_logs)
    
    class ConsoleRedirector:
        def write(self, s):
            # Put the print statement into the safe queue instead of forcing a UI update
            log_queue.put(s)
            sys.__stdout__.write(s) 
            
        def flush(self):
            sys.__stdout__.flush()

    sys.stdout = ConsoleRedirector()
    sys.stderr = ConsoleRedirector()
    
    # Start the GUI log polling loop safely on the main thread
    process_gui_logs()
    
    input_frame = tk.Frame(root, bg="#1e1e1e")
    input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    entry = tk.Entry(input_frame, bg="#2d2d2d", fg="#ffffff", font=("Consolas", 12), insertbackground="white", bd=1, relief=tk.FLAT)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 10))
    
    def on_send(event=None):
        text = entry.get().strip()
        if text:
            entry.delete(0, tk.END)
            print(f"\n[GUI Input Received]: {text}")
            process_command(text)
            
    btn = tk.Button(input_frame, text="SEND COMMAND", bg="#0066cc", fg="white", font=("Consolas", 10, "bold"), bd=0, padx=15, pady=4, command=on_send)
    btn.pack(side=tk.RIGHT)
    entry.bind("<Return>", on_send)
    
    mic_thread = threading.Thread(target=run_assistant, daemon=True)
    mic_thread.start()
    
    root.mainloop()


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    try:
        if "--gui" in sys.argv:
            run_gui_console()
        else:
            run_assistant()
    except KeyboardInterrupt:
        print("\n[System] Shutting down cleanly...")
        sys.exit(0)