# Yelp - Voice-Activated Response System for Dementia Care

A locally-running voice assistant that listens for calls (e.g., "hallo", "hilfe") and responds with comforting phrases. Designed for dementia care to provide reassurance when caregivers aren't immediately available.

## 🎯 Features

- **Voice-activated**: Detects specific trigger words ("hallo", "hilfe")
- **Time-aware responses**: Different comforting phrases based on time of day
- **Local operation**: No internet required, all processing on-device
- **Privacy-focused**: All audio stays on your local machine
- **Room microphone support**: Works with USB conference microphones (e.g., Jabra Speak2 55)
- **Web interface**: Remote configuration and monitoring
- **Auto-start**: Runs as systemd service, starts on boot

## 📋 Requirements

### Hardware
- Linux-based system (Debian/Ubuntu tested)
- Minimum 2GB RAM
- USB microphone with room pickup (tested: Jabra Speak2 55 UC)
- Speaker (can use microphone's built-in speaker)

### Software
- Debian 12+ or Ubuntu 20.04+
- Python 3.11
- Internet connection for initial setup only

## 🚀 Installation

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    git \
    portaudio19-dev \
    ffmpeg \
    alsa-utils \
    pulseaudio
```

### 2. Install Python 3.11

**If Python 3.11 is not available in your distribution:**

```bash
cd /tmp
wget https://www.python.org/ftp/python/3.11.8/Python-3.11.8.tgz
tar -xzf Python-3.11.8.tgz
cd Python-3.11.8

./configure --enable-optimizations
make -j $(nproc)
sudo make altinstall

# Verify installation
python3.11 --version
```

### 3. Clone Repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/yelp.git
cd yelp
```

### 4. Create Virtual Environment and Install Python Dependencies

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install pyaudio numpy openai-whisper piper-tts flask
```

### 5. Download German Voice Model

```bash
mkdir -p piper_voices
cd piper_voices

# Download Kerstin voice (German female)
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/kerstin/low/de_DE-kerstin-low.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/kerstin/low/de_DE-kerstin-low.onnx.json

cd ..
```

### 6. Configure Audio Devices

**Find your microphone device:**

```bash
source venv/bin/activate
python3 -c "import pyaudio; p=pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

Look for your USB microphone and note the device number for "default" (usually 14).

**Test audio output:**

```bash
# List playback devices
aplay -l

# Test speaker
speaker-test -c 2 -t wav -l 1
```

**Edit configuration if needed:**

Open `yelp_complete.py` and verify line 39:
```python
AUDIO_DEVICE_INDEX = 14  # Usually 14 for "default" (PulseAudio)
```

### 7. Create Required Directories and Files

```bash
# Create directories
mkdir -p logs temp

# Create silence file (1 second for speaker initialization)
bash create_silence.sh
```

### 8. Test Manual Run

```bash
source venv/bin/activate
python3 yelp_complete.py
```

Say "hallo" - you should hear a response. Press Ctrl+C to stop.

---

## 🔧 Install as System Service (Autostart)

### 1. Install Yelp Service

```bash
cd ~/yelp

# Copy service file
sudo cp yelp.service /etc/systemd/system/

# Update service file to use correct path
sudo sed -i "s|/home/ljung|$HOME|g" /etc/systemd/system/yelp.service

# Reload systemd
sudo systemctl daemon-reload

# Enable autostart
sudo systemctl enable yelp.service

# Start service
sudo systemctl start yelp.service

# Check status
sudo systemctl status yelp.service
```

### 2. Install Web Interface (Optional)

```bash
cd ~/yelp
bash install_web_interface.sh
```

The web interface will be available at:
- Local: http://localhost:5000
- Network: http://YOUR_IP:5000

---

## 🌐 Remote Access with Tailscale (Optional)

To access your device remotely from anywhere:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Get an auth key from https://login.tailscale.com/admin/settings/keys
# Generate a reusable key

# Connect (replace YOUR_AUTH_KEY)
sudo tailscale up --authkey=YOUR_AUTH_KEY

# Enable autostart
sudo systemctl enable tailscaled

# Get your Tailscale IP
tailscale ip -4
```

Access web interface via Tailscale: `http://100.x.x.x:5000`

---

## ⚙️ Configuration

### Via Web Interface

Access the web interface (http://localhost:5000) to adjust:
- **Volume Threshold**: Microphone sensitivity (lower = more sensitive)
- **Silence Duration**: How long to wait after detecting sound
- **Min Audio Length**: Minimum recording length to process
- **Cooldown**: Seconds between responses
- **Speech Speed**: TTS playback speed (1.0=normal, 1.5=slower)

### Via Configuration File

Edit `yelp_complete.py` lines 28-43:

```python
RUF_SCHWELLE = 0.0005         # Volume threshold
STILLE_DAUER = 1.0            # Silence duration (seconds)
MIN_AUDIO_LAENGE = 0.1        # Minimum audio length (seconds)
PAUSE_NACH_ANTWORT = 5        # Cooldown between responses (seconds)
PIPER_SPEECH_SPEED = 1.5      # Speech speed (1.0-2.0)
```

After changes, restart the service:
```bash
sudo systemctl restart yelp
```

---

## 📝 Customizing Responses

Edit the response phrases in `yelp_complete.py` (lines 56-91):

```python
ANTWORTEN_NACHT = [
    "Schlaf ruhig weiter, ich passe auf dich auf.",
    "Alles ist gut, ich bin bei dir.",
    # Add your own phrases here
]

ANTWORTEN_MORGEN = [...]
ANTWORTEN_TAG = [...]
ANTWORTEN_ABEND = [...]
```

Time periods:
- **NACHT** (Night): 22:00-05:59
- **MORGEN** (Morning): 06:00-11:59
- **TAG** (Day): 12:00-17:59
- **ABEND** (Evening): 18:00-21:59

---

## 🔍 Monitoring and Logs

### View Logs

```bash
# Via web interface
http://localhost:5000

# Via command line
tail -f ~/yelp/logs/yelp.log

# View last 50 entries
tail -n 50 ~/yelp/logs/yelp.log

# View only recognized calls
grep 'RUF_ERKANNT' ~/yelp/logs/yelp.log

# View errors
grep 'ERROR' ~/yelp/logs/yelp.log
```

### Log Files

- **Text log**: `~/yelp/logs/yelp.log` (human-readable)
- **JSON log**: `~/yelp/logs/yelp_events.json` (structured data)
- **Rotation**: Max 10 MB per file, keeps 3 backups

### Service Management

```bash
# Status
sudo systemctl status yelp

# Start
sudo systemctl start yelp

# Stop
sudo systemctl stop yelp

# Restart
sudo systemctl restart yelp

# View service logs
sudo journalctl -u yelp -f

# Disable autostart
sudo systemctl disable yelp
```

---

## 🐛 Troubleshooting

### No Audio Output

```bash
# Check volume (must be unmuted)
amixer get Master

# Unmute and set to 100%
amixer set Master 100% unmute

# Test playback
aplay ~/yelp/temp/test.wav
```

### Microphone Not Detecting Voice

```bash
# Test microphone levels
cd ~/yelp
source venv/bin/activate
bash test_jabra_pyaudio.sh

# If level is too low, adjust threshold in web interface or config file
```

### Service Not Starting

```bash
# Check service status
sudo systemctl status yelp

# View detailed logs
sudo journalctl -u yelp -n 50

# Check permissions
ls -l ~/yelp/yelp_complete.py
```

### PulseAudio Issues

```bash
# Restart PulseAudio
pulseaudio -k
pulseaudio --start

# Check if running
pactl info
```

---

## 🎙️ Tested Hardware

### USB Microphones (Room Pickup)
- ✅ **Jabra Speak2 55 UC** (recommended for room use)
- ✅ **Blue Yeti** (omnidirectional mode)
- ✅ **Anker PowerConf S3**

### Close-Range Microphones
- ✅ Zoom H2n (professional recorder)
- ✅ Audio-Technica ATR2100x-USB

---

## 📊 Performance Notes

- **CPU Usage**: ~10-15% during speech recognition (Whisper tiny model)
- **RAM Usage**: ~500 MB
- **Response Time**:
  - Detection: Instant
  - Processing: 5-10 seconds (CPU-only Whisper)
  - Playback: 2-4 seconds
  - **Total**: ~10-15 seconds from call to response

**For faster performance**: Add NVIDIA GPU and use Coqui XTTS-v2 for voice cloning with 1-3 second response times.

---

## 🔐 Privacy & Security

- ✅ **Fully local**: No cloud services, no internet required after setup
- ✅ **No data collection**: Audio never leaves the device
- ✅ **Open source**: Inspect all code yourself
- ⚠️ **Web interface**: Only accessible on local network (use Tailscale for secure remote access)

---

## 🛠️ Advanced: Voice Cloning (GPU Required)

For personalized voices using recordings:

**Requirements:**
- NVIDIA GPU with 4GB+ VRAM
- 1-2 hours of voice recordings

See [VOICE_CLONING.md](VOICE_CLONING.md) for detailed instructions.

---

## 📄 License

MIT License - feel free to use and modify for your needs.

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Test thoroughly
4. Submit a pull request

---

## 💬 Support

For issues or questions:
- Open an issue on GitHub
- Check existing issues for solutions

---

## 🙏 Acknowledgments

- **OpenAI Whisper** - Speech recognition
- **Piper TTS** by Rhasspy - Text-to-speech
- **PyAudio** - Audio I/O
- **Flask** - Web interface

---

## ⚠️ Disclaimer

This software is provided as-is for personal use. It is designed to assist with dementia care but should **not replace professional medical care or human supervision**. Always ensure proper care and monitoring by qualified caregivers.

---

**Made with ❤️ for caregivers and their loved ones**
