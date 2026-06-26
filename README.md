# JesseMSV

A better version of the Jesse Assistant. Requires the ```main.py``` server to be running to use local speech-to-text. Made for embedded devices with screens (doesn't need one, but it is nice).

You can also run ```main-noscreen.py``` if your deivce is voice-and-audio-only (eg. something like an Alexa Echo Dot).

## Capabilities

- Tell you the time and date
- Tell you the current weather
- Create local notes
- Set timers
- Calcuate equations
- Flip a coin
- Play internet radio
- Read Wikipedia article summaries
- Set a new wakework
- Set a new voice
- Tell jokes
- Play internet radio and TV
- "Good Morning" sequence

## How to Use Jesse

First, you wake Jesse by saying "Hey Jesse" (or your wakeword). A sound will play, indicating Jesse is listening. Speak your command above, and let Jesse do it's thing! It's that simple.

If there was an issue when training the wakeword, you can wake Jesse by tapping the screen wih two fingers.

Jesse can be acessed [HERE](https://astromeyt.github.io/JesseMSV)

## Setting up for Stationary Devices

### Linux

Make sure to have a desktop environment installed, run ```pip install flask flask-cors faster-whisper numpy``` in the terminal, and add these to startup commands:

- ```YOUR_BROWSER --kiosk path/to/index.html```
- ```python3 path/to/main.py```
