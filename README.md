================================================================================
JESSE SMART ASSISTANT SUITE - README

An open-source, flexible, and resource-scalable smart assistant ecosystem.
This repository offers three distinct configurations, scaling from full visual
ambient smart screens down to completely headless, low-resource voice clients
designed to run smoothly on devices like the Raspberry Pi Zero 2 W.

                       TABLE OF CONTENTS


Ecosystem Overview & Versions

Universal One-Line Installer

Manual Setup & Dependencies

Skill Capabilities & Spoken Phrases

Troubleshooting & Diagnostics

================================================================================

ECOSYSTEM OVERVIEW & VERSIONS
================================================================================

A. Web GUI Version (index.html + local_stt_server.py)

A gorgeous, modern web application styled with Tailwind CSS glassmorphic cards
and cinematic background crossfades.

Uses a local Flask STT server backend powered by Faster-Whisper (base.en).

Perfect for desktop computers, tablets, or touchscreens.

Smooth loading animations and rotating command suggestions.

B. Headless Voice & Sound Version (main-noscreen.py)

A lightweight, background-only voice assistant that handles both VAD (Voice
Activity Detection) and STT locally.

Hardware Auto-Detection Engine: On boot, this script automatically detects
your system RAM.

If RAM >= 1.5GB: It initializes the highly accurate Faster-Whisper model.

If RAM < 1.5GB (e.g. Raspberry Pi Zero 2W): It falls back to a hyper-efficient
~40MB Vosk model to operate entirely within 512MB of RAM.

Non-freezing async architecture separates microphone listening, logic routing,
and Text-to-Speech playback.

Offers an optional graphical debugger via python3 main-noscreen.py --gui.

C. Desktop Echo Show App (echo_show.py)

A feature-rich, standalone desktop clone of the Amazon Echo Show built entirely
in Python using Tkinter.

Features real-time clock, dynamic weather widgets, a slide-out drawer panel
for notes, timers, and voice engine configuration.

Incorporates offline text-to-speech fallback engines.

================================================================================
2. UNIVERSAL ONE-LINE INSTALLER

If you are running on a Linux system (Debian/Ubuntu, Raspberry Pi OS, Arch,
Fedora, or openSUSE), you can install either version automatically. This helper
script will install system audio headers, compile Python packages inside a safe
Virtual Environment, and generate a systemd service so your assistant starts
automatically on boot.

Open your terminal and run:

```curl -sSL https://raw.githubusercontent.com/AstroMeYT/JesseMSV/refs/heads/main/install.bash | bash```

During the installer, choose option "1" for the Web GUI server, or option "2"
for the headless/Vosk-optimized assistant.

================================================================================
3. MANUAL SETUP & DEPENDENCIES

To set up the environment manually, you must install the following system dependencies
first so Python can talk to your soundcard and media systems:

A. System Requirements:

Debian / Ubuntu / Pi OS:
sudo apt-get update
sudo apt-get install python3-pip python3-venv portaudio19-dev vlc ffmpeg python3-tk

Arch Linux:
sudo pacman -Sy python-pip portaudio vlc ffmpeg tk

Fedora:
sudo dnf install python3-pip portaudio-devel vlc ffmpeg python3-tkinter

B. Python Virtual Environment & Pip Packages:

Set up your folder directory and install the necessary libraries:

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install requests pyttsx3 SpeechRecognition pyaudio faster-whisper 

flask flask-cors numpy python-vlc edge-tts pygame vosk psutil Pillow

Note on Vosk:
If your system triggers the lightweight Vosk STT engine, it will attempt to
auto-load the "en-us" model. If you run into compatibility issues with your OS,
download the small English model (e.g. vosk-model-small-en-us-0.15) manually from
https://alphacephei.com/vosk/models, extract it into your project folder, and
rename the extracted folder to "model".

================================================================================
4. SKILL CAPABILITIES & SPOKEN PHRASES

The Natural Language Processor (NLP) uses word boundary regex checks to avoid
command-hijacking. To trigger a response, prefix your commands with the wake word
"Jesse" (e.g., "Jesse, what time is it?").

Below is a cheat sheet of supported intents and examples:

"Good Morning Sequence":
Phrase: "Jesse, good morning"
Action: Tells you the time, provides a comprehensive weather outlook (current,
expected high, and low temperature), and reads the top two world news
headlines via BBC RSS.

"Time & Date":
Phrase: "Jesse, what's the date?" or "Jesse, what time is it?"
Action: Speaks the current hour, minute, and calendar date.

"Live Weather":
Phrase: "Jesse, what is the weather today?"
Action: Speaks current location conditions and temperatures. You can change
your default city by asking "Jesse, set location to Paris".

"Math Equations":
Phrase: "Jesse, calculate 15 plus thirty-five" or "Jesse, what is 100 divided by 4?"
Action: Evaluates the equation safely and speaks the calculated sum.

"Countdown Timers":
Phrase: "Jesse, set a timer for 1 minute and thirty seconds"
Action: Launches a non-blocking countdown in a separate thread. Plays a chime
when time runs out.

"Notes & Remembering":
Phrase: "Jesse, write a note to water the plants" or "Jesse, read my notes"
Action: Saves plain text items to a local JSON file (assistant_notes.json)
and reads them back on demand.

"Internet Radio / Media":
Phrase: "Jesse, play classic fm" or "Jesse, play country music"
Action: Queries public online radio directories using free API lookups, resolves
high-quality audio streams, and runs them via VLC.
Phrase: "Jesse, stop the music"
Action: Gracefully stops the background music player.

"Wikipedia Searches":
Phrase: "Jesse, who is Albert Einstein?" or "Jesse, tell me about Mars"
Action: Requests live concise details from the Wikipedia REST API using safe
User-Agent headers.

"Dynamic Jokes":
Phrase: "Jesse, tell me a joke"
Action: Connects to a free API to fetch clean, family-friendly humor.

================================================================================
5. TROUBLESHOOTING & DIAGNOSTICS

VLC NameError ("no function 'libvlc_new'"):
Ensure you have installed the actual VLC Media Player application on your
operating system level. python-vlc is only a wrapper and requires the physical
libvlc.so shared system library. If you still see that is it installed, make
sure that it is a system package and not a Flatpak package.

Segfaults when running --gui:
Ensure your desktop environment is loaded and running. Systemd services running
headless cannot boot TKinter graphical frames without an active desktop display
instance (Environment="DISPLAY=:0").

Microphone Error on Startup:
Check that no other services are holding an exclusive lock on your hardware audio
input device (e.g., PulseAudio or ALSA exclusive modes).
