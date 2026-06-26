#!/bin/bash
# ==============================================================================
# JESSE SMART ASSISTANT INSTALLER
# ==============================================================================
# This script detects your OS, installs system audio dependencies, sets up a 
# Python virtual environment, downloads the requested GitHub files, and sets 
# up a systemd service to run the assistant automatically on boot.
#
# PIPE-SAFE: Uses </dev/tty to allow interactive prompt inputs when curl'd.
# ==============================================================================

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

INSTALL_DIR="$HOME/JesseMSV"
VENV_DIR="$INSTALL_DIR/venv"

echo -e "${CYAN}=======================================================${NC}"
echo -e "${GREEN}       JESSE SMART ASSISTANT - AUTO INSTALLER          ${NC}"
echo -e "${CYAN}=======================================================${NC}"
echo ""

# 1. Ask user for installation type (Redirected input to /dev/tty for pipe safety)
echo -e "${YELLOW}Which version of the assistant would you like to install?${NC}"
echo "  1) Web GUI Version (HTML Interface + Python STT Server)"
echo "  2) Headless Version (Voice & Sound Only)"
echo ""
read -p "Enter choice [1 or 2]: " INSTALL_CHOICE < /dev/tty

if [[ "$INSTALL_CHOICE" != "1" && "$INSTALL_CHOICE" != "2" ]]; then
    echo -e "${RED}Invalid choice. Exiting.${NC}"
    exit 1
fi

# 2. Check for sudo privileges upfront
echo -e "\n${CYAN}[1/5] Checking system permissions...${NC}"
if ! sudo -v &>/dev/null; then
    echo -e "${RED}You need sudo privileges to install system packages and services. Exiting.${NC}"
    exit 1
fi

# 3. Detect Package Manager and Install System Dependencies
echo -e "\n${CYAN}[2/5] Detecting Package Manager & Installing System Dependencies...${NC}"
echo "We need to install PortAudio (for PyAudio), VLC (for radio streaming), and Tkinter (for GUI)."

if command -v apt-get >/dev/null; then
    echo -e "${GREEN}Debian/Ubuntu/Raspberry Pi OS detected.${NC}"
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv wget curl vlc libportaudio2 libportaudiocpp0 portaudio19-dev python3-pyaudio espeak ffmpeg python3-tk
elif command -v pacman >/dev/null; then
    echo -e "${GREEN}Arch Linux detected.${NC}"
    sudo pacman -Sy --noconfirm python python-pip wget curl vlc portaudio python-pyaudio espeak-ng ffmpeg tk
elif command -v dnf >/dev/null; then
    echo -e "${GREEN}Fedora detected.${NC}"
    sudo dnf install -y python3 python3-pip wget curl vlc portaudio-devel python3-pyaudio espeak ffmpeg python3-tkinter
elif command -v zypper >/dev/null; then
    echo -e "${GREEN}openSUSE detected.${NC}"
    sudo zypper install -y python3 python3-pip wget curl vlc portaudio-devel python3-pyaudio espeak ffmpeg python3-tk
else
    echo -e "${RED}Unsupported package manager. Please manually install: portaudio development headers, vlc, python3-venv, ffmpeg, and python3-tk.${NC}"
    read -p "Press Enter to attempt continuing anyway, or Ctrl+C to abort..." < /dev/tty
fi

# 4. Setup Directory and Virtual Environment
echo -e "\n${CYAN}[3/5] Setting up Python Virtual Environment...${NC}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR" || exit

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo -e "${YELLOW}Installing Python packages via pip (this may take a minute)...${NC}"
pip install --upgrade pip
pip install requests pyttsx3 SpeechRecognition pyaudio faster-whisper flask flask-cors numpy python-vlc edge-tts pygame vosk psutil

# 5. Download GitHub Files based on user choice
echo -e "\n${CYAN}[4/5] Downloading Application Files...${NC}"

if [[ "$INSTALL_CHOICE" == "1" ]]; then
    # Web GUI
    echo -e "${YELLOW}Downloading Web GUI index.html...${NC}"
    wget -q -O index.html "https://raw.githubusercontent.com/AstroMeYT/JesseMSV/refs/heads/main/index.html"
    
    echo -e "${YELLOW}Downloading Web GUI main.py (STT Server)...${NC}"
    wget -q -O main.py "https://raw.githubusercontent.com/AstroMeYT/JesseMSV/refs/heads/main/main.py"
    
    SERVICE_EXEC="$VENV_DIR/bin/python $INSTALL_DIR/main.py"
    SERVICE_DESC="JesseMSV Web Backend STT Server"
else
    # Headless
    echo -e "${YELLOW}Downloading Headless main-noscreen.py...${NC}"
    wget -q -O main-noscreen.py "https://raw.githubusercontent.com/AstroMeYT/JesseMSV/refs/heads/main/main-noscreen.py"
    
    SERVICE_EXEC="$VENV_DIR/bin/python $INSTALL_DIR/main-noscreen.py"
    SERVICE_DESC="JesseMSV Headless Voice Assistant"
fi

# 6. Setup Systemd Auto-Start Service
echo -e "\n${CYAN}[5/5] Configuring Auto-Start (systemd)...${NC}"

SERVICE_NAME="jesse-assistant.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

# Create the service file dynamically
sudo bash -c "cat > $SERVICE_PATH" <<EOL
[Unit]
Description=$SERVICE_DESC
After=network-online.target sound.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin:/usr/bin:/usr/local/bin"
# Ensure audio engines like PulseAudio/ALSA can be accessed by the service
Environment="XDG_RUNTIME_DIR=/run/user/\$(id -u)"
Environment="PULSE_SERVER=unix:/run/user/\$(id -u)/pulse/native"
# Provide access to the display if running the optional GUI
Environment="DISPLAY=:0"
ExecStart=$SERVICE_EXEC
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOL

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo -e "\n${CYAN}=======================================================${NC}"
echo -e "${GREEN}                 INSTALLATION COMPLETE!                  ${NC}"
echo -e "${CYAN}=======================================================${NC}"
echo ""
echo -e "The assistant has been installed to: ${YELLOW}$INSTALL_DIR${NC}"
echo -e "It is currently running in the background and will start on boot."
echo ""
echo -e "To view live logs/debug, run:"
echo -e "  ${YELLOW}sudo journalctl -u $SERVICE_NAME -f${NC}"
echo ""
echo -e "To stop the assistant manually, run:"
echo -e "  ${YELLOW}sudo systemctl stop $SERVICE_NAME${NC}"
echo ""

if [[ "$INSTALL_CHOICE" == "1" ]]; then
    echo -e "${GREEN}Since you installed the Web GUI, the STT Server is now running on port 5000.${NC}"
    echo -e "To use the assistant, simply open the downloaded HTML file in any browser:"
    echo -e "  ${YELLOW}file://$INSTALL_DIR/index.html${NC}"
else
    echo -e "${GREEN}Since you installed the Headless version, the microphone should now be active!${NC}"
    echo -e "Try speaking your wake word to test the audio engines."
    echo -e "To use the graphical debugger interface later, run: ${YELLOW}$VENV_DIR/bin/python $INSTALL_DIR/main-noscreen.py --gui${NC}"
fi
echo ""